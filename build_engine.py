import os
import json
import time
import shutil
import tarfile
import tempfile
import glob
from datetime import datetime

from state_manager import read_manifest, write_manifest, store_layer
from cache_engine import compute_cache_key, check_cache, update_cache
from runtime import assemble_rootfs, execute_isolated

def create_deterministic_tar(source_dir, prefix="/"):
    # Create temp file for tar
    fd, tar_path = tempfile.mkstemp(suffix=".tar")
    os.close(fd)
    
    def zero_tarinfo(ti):
        ti.mtime = 0
        ti.uid = 0
        ti.gid = 0
        ti.uname = 'root'
        ti.gname = 'root'
        return ti

    with tarfile.open(tar_path, "w") as tar:
        # Sort for determinism
        for root, dirs, files in sorted(os.walk(source_dir)):
            dirs.sort()
            for f in sorted(files):
                abs_path = os.path.join(root, f)
                rel_path = os.path.relpath(abs_path, source_dir)
                
                # Combine prefix 
                arcname = os.path.join(prefix, rel_path).lstrip('/')
                
                ti = tar.gettarinfo(abs_path, arcname)
                zero_tarinfo(ti)
                
                if ti.isreg():
                    with open(abs_path, "rb") as fp:
                        tar.addfile(ti, fp)
                else:
                    tar.addfile(ti)
                    
    with open(tar_path, "rb") as tp:
        tar_bytes = tp.read()
    os.remove(tar_path)
    return tar_bytes

def snapshot_dir(path):
    snap = {}
    for root, _, files in os.walk(path):
        for f in files:
            abs_p = os.path.join(root, f)
            rel_p = os.path.relpath(abs_p, path)
            st = os.stat(abs_p)
            snap[rel_p] = (st.st_mtime, st.st_size)
    return snap

def build_image(tag, context_dir, no_cache=False):
    docksmith_file = os.path.join(context_dir, "Docksmithfile")
    if not os.path.exists(docksmith_file):
        raise FileNotFoundError(f"Missing Docksmithfile in {context_dir}")
        
    with open(docksmith_file, "r") as df:
        instructions = [l.strip() for l in df.readlines() if l.strip() and not l.startswith("#")]
        
    manifest = {
        "name": tag.split(":")[0],
        "tag": tag.split(":")[1] if ":" in tag else "latest",
        "digest": "",
        "created": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config": {
            "Env": [],
            "Cmd": [],
            "WorkingDir": "/"
        },
        "layers": []
    }
    
    current_env = {}
    current_workdir = ""
    prev_digest = ""
    cascade_miss = False
    
    start_time = time.time()
    
    for idx, inst in enumerate(instructions):
        step_num = idx + 1
        parts = inst.split(maxsplit=1)
        cmd = parts[0].upper()
        args = parts[1] if len(parts) > 1 else ""
        
        print(f"Step {step_num}/{len(instructions)} : {inst}")
        step_start_time = time.time()

        if cmd == "FROM":
            base_manifest = read_manifest(args)
            if not base_manifest:
                print(f"Error on line {step_num}: Base image {args} not found in local store.")
                return False
            
            # Inherit layers and config
            manifest["layers"] = base_manifest.get("layers", []).copy()
            manifest["config"] = base_manifest.get("config", {}).copy()
            
            # Init states
            for e in manifest["config"].get("Env", []):
                if "=" in e:
                    k, v = e.split("=", 1)
                    current_env[k] = v
            current_workdir = manifest["config"].get("WorkingDir", "")
            prev_digest = base_manifest.get("digest", "")
            
        elif cmd in ["WORKDIR", "ENV", "CMD"]:
            if cmd == "WORKDIR":
                current_workdir = args
                manifest["config"]["WorkingDir"] = current_workdir
            elif cmd == "ENV":
                if "=" in args:
                    k, v = args.split("=", 1)
                    current_env[k] = v
                    # Update config Env array cleanly
                    manifest["config"]["Env"] = [f"{ek}={ev}" for ek, ev in current_env.items()]
            elif cmd == "CMD":
                try:
                    cmd_arr = json.loads(args)
                    manifest["config"]["Cmd"] = cmd_arr
                except json.JSONDecodeError:
                    print(f"Error on line {step_num}: CMD must be a valid JSON array.")
                    return False

        elif cmd in ["COPY", "RUN"]:
            # Compute cache key
            copy_sources = {}
            if cmd == "COPY":
                src, dest = args.rsplit(" ", 1)
                
                # Expand globs in context
                matches = glob.glob(os.path.join(context_dir, src), recursive=True)
                for m in matches:
                    if os.path.isfile(m):
                        rel = os.path.relpath(m, context_dir)
                        copy_sources[rel] = m
            
            cache_key = compute_cache_key(prev_digest, inst, current_workdir, current_env, copy_sources)

            hit_digest = check_cache(cache_key) if not no_cache else None
            
            if hit_digest and not cascade_miss:
                dur = time.time() - step_start_time
                print(f" ---> [CACHE HIT] {hit_digest[:12]} ({dur:.2f}s)")
                prev_digest = hit_digest
                
                # Check what the actual digest corresponds to, and inherit it properly if needed.
                # However, the `layers` lists are tricky if there's multiple layers per FROM.
                # To perfectly mimic docker, we append the hit_digest layer to `manifest['layers']`.
                # But we need its size. Let's get size from state_manager logic
                layer_path = os.path.join(os.path.expanduser("~"), ".docksmith", "layers", f"{hit_digest.replace(':', '_')}.tar")
                size = os.path.getsize(layer_path)
                manifest["layers"].append({"digest": hit_digest, "size": size, "createdBy": inst})

            else:
                cascade_miss = True
                tar_bytes = b""
                
                if cmd == "COPY":
                    dest_path = dest.lstrip("/")
                    # Create a temporary directory mimicking the destination structure
                    temp_dir = tempfile.mkdtemp()
                    for rel, abs_path in copy_sources.items():
                        target = os.path.join(temp_dir, rel)
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        shutil.copy2(abs_path, target)
                        
                    tar_bytes = create_deterministic_tar(temp_dir, prefix=dest)
                    shutil.rmtree(temp_dir)
                
                elif cmd == "RUN":
                    # Assemble isolated rootfs to execute the run
                    temp_dir = assemble_rootfs(manifest)
                    
                    # Snapshot before
                    snap_before = snapshot_dir(temp_dir)
                    
                    shlex_cmd = ["sh", "-c", args] 
                    code = execute_isolated(temp_dir, shlex_cmd, current_workdir, current_env)
                    if code != 0:
                        print(f"Error on line {step_num}: command failed with exit code {code}")
                        shutil.rmtree(temp_dir)
                        return False
                        
                    # Snapshot after and extract deltas
                    delta_dir = tempfile.mkdtemp()
                    for root, _, files in os.walk(temp_dir):
                        for f in files:
                            abs_p = os.path.join(root, f)
                            rel_p = os.path.relpath(abs_p, temp_dir)
                            st = os.stat(abs_p)

                            if rel_p not in snap_before or snap_before[rel_p] != (st.st_mtime, st.st_size):
                                # It's a new or modified file
                                out_p = os.path.join(delta_dir, rel_p)
                                os.makedirs(os.path.dirname(out_p), exist_ok=True)
                                shutil.copy2(abs_p, out_p)
                    
                    # Build tar from delta_dir
                    tar_bytes = create_deterministic_tar(delta_dir, prefix="/")
                    shutil.rmtree(delta_dir)
                    shutil.rmtree(temp_dir)

                # Store the new layer
                new_layer_digest, size = store_layer(tar_bytes)
                manifest["layers"].append({
                    "digest": new_layer_digest, 
                    "size": size, 
                    "createdBy": inst
                })
                prev_digest = new_layer_digest
                
                # Update Cache index
                if not no_cache:
                    update_cache(cache_key, new_layer_digest)
                    
                dur = time.time() - step_start_time
                print(f" ---> [CACHE MISS] {new_layer_digest[:12]} ({dur:.2f}s)")
        else:
            print(f"Error on line {step_num}: Unrecognised instruction '{cmd}'")
            return False

    write_manifest(tag, manifest)
    total_time = time.time() - start_time
    print(f"Successfully built {manifest['digest']} {tag} ({total_time:.2f}s)")
    return True
