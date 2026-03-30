import argparse
import sys
import os

from state_manager import list_images, delete_image_and_layers, read_manifest
from build_engine import build_image
from runtime import assemble_rootfs, execute_isolated
import shutil

def cmd_build(args):
    try:
        build_image(args.t, args.context, getattr(args, "no-cache"))
    except Exception as e:
        print(f"Build failed: {e}")
        sys.exit(1)

def cmd_images(args):
    images = list_images()
    print(f"{'Name':<20} {'Tag':<15} {'ID':<15} {'Created':<25}")
    for img in images:
        name = img.get("name", "<none>")
        tag = img.get("tag", "<none>")
        digest = img.get("digest", "")
        short_id = digest.split("sha256:")[-1][:12] if digest else ""
        created = img.get("created", "")
        print(f"{name:<20} {tag:<15} {short_id:<15} {created:<25}")

def cmd_rmi(args):
    tag = args.image
    if delete_image_and_layers(tag):
        print(f"Removed image: {tag}")
    else:
        print(f"Error: No such image: {tag}")
        sys.exit(1)

def cmd_run(args):
    tag = args.image
    manifest = read_manifest(tag)
    if not manifest:
        print(f"Error: No such image: {tag}")
        sys.exit(1)
        
    # Command priorities: CLI overrides Manifest CMD
    run_cmd = args.cmd if args.cmd else manifest.get("config", {}).get("Cmd", [])
    if not run_cmd:
        print("Error: No CMD defined in image and no command provided.")
        sys.exit(1)
        
    # Build env
    env_dict = {}
    for ev in manifest.get("config", {}).get("Env", []):
        if "=" in ev:
            k, v = ev.split("=", 1)
            env_dict[k] = v
            
    if args.e:
        for ev in args.e:
            if "=" in ev:
                k, v = ev.split("=", 1)
                env_dict[k] = v
                
    workdir = manifest.get("config", {}).get("WorkingDir", "/")
    
    # Extract
    temp_dir = assemble_rootfs(manifest)
    
    try:
        code = execute_isolated(temp_dir, run_cmd, workdir, env_dict)
        sys.exit(code)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def main():
    parser = argparse.ArgumentParser(prog="docksmith", description="A simplified container build and runtime system.")
    subparsers = parser.add_subparsers(required=True, dest="command")
    
    # build
    parser_build = subparsers.add_parser("build", help="Build an image from a Docksmithfile")
    parser_build.add_argument("-t", required=True, help="<name:tag>")
    parser_build.add_argument("context", help="Build context directory")
    parser_build.add_argument("--no-cache", dest="no-cache", action="store_true", help="Do not use cache when building the image")
    
    # images
    parser_images = subparsers.add_parser("images", help="List images")
    
    # rmi
    parser_rmi = subparsers.add_parser("rmi", help="Remove an image")
    parser_rmi.add_argument("image", help="<name:tag>")
    
    # run
    parser_run = subparsers.add_parser("run", help="Run a command in a new container")
    parser_run.add_argument("image", help="<name:tag>")
    parser_run.add_argument("cmd", nargs="*", help="Command to run")
    parser_run.add_argument("-e", action="append", help="Set environment variables")
    
    args = parser.parse_args()
    
    if args.command == "build":
        cmd_build(args)
    elif args.command == "images":
        cmd_images(args)
    elif args.command == "rmi":
        cmd_rmi(args)
    elif args.command == "run":
        cmd_run(args)

if __name__ == "__main__":
    main()
