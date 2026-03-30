import os
import sys
import shutil
import tarfile
import tempfile
import subprocess
from state_manager import get_layer_path

def extract_layer(digest, target_dir):
    layer_tar = get_layer_path(digest)
    if os.path.exists(layer_tar):
        with tarfile.open(layer_tar, "r") as tar:
            tar.extractall(path=target_dir)

def assemble_rootfs(manifest):
    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix="docksmith-root-")
    layers = manifest.get("layers", [])
    
    # Extract them in order
    for layer in layers:
        digest = layer.get("digest")
        extract_layer(digest, temp_dir)
        
    return temp_dir

def prepare_env_list(env_dict):
    return [f"{k}={v}" for k, v in env_dict.items()]

def execute_isolated(root_dir, cmd_array, workdir, env_dict):
    """
    Executes a command isolated within root_dir. 
    Uses `unshare -mufpir -R root_dir` on Linux if available, to provide strict isolation.
    """
    workdir = workdir if workdir else "/"
    # Ensure workdir exists in rootfs
    abs_wd = os.path.join(root_dir, workdir.lstrip("/"))
    os.makedirs(abs_wd, exist_ok=True)
    
    # Environment variables
    env_vars = os.environ.copy()
    env_vars.update(env_dict)

    if sys.platform.startswith("linux"):
        # We use unshare to create mount, UTS, IPC, network, and PID namespaces.
        # -R acts implicitly as a chroot.
        # No network namespace for absolute isolation since specs say "No network access".
        # We use 'unshare -mupfinr -R <root_dir>'
        # Options: -m (mount), -u (uts), -p (pid), -f (fork), -i (ipc), -n (net), -r (map-root-user), -R (root)
        unshare_cmd = ["unshare", "-mupfinr", "-R", root_dir, "--wd", workdir] + cmd_array
        try:
            result = subprocess.run(unshare_cmd, env=env_vars)
            return result.returncode
        except FileNotFoundError:
            print("Error: 'unshare' utility not found on this Linux system.")
            return 1
    else:
        print("[WARNING] Not on Linux. Strict process isolation (chroot/namespaces) is disabled.")
        # Fallback for Windows/macOS mock development
        # This will just execute in the specific cwd
        try:
            result = subprocess.run(cmd_array, cwd=abs_wd, env=env_vars)
            return result.returncode
        except Exception as e:
            print(f"Execution failed: {e}")
            return 1
