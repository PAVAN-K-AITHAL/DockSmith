# DockSmith

DockSmith is a simplified container build and runtime system, designed to mimic core functionalities of Docker. It allows you to build container images from a `Docksmithfile`, manage local images, and run isolated commands dynamically using Linux namespaces.

## Features

- **Custom Image Builder:** Uses a `Docksmithfile` to parse steps like `FROM`, `WORKDIR`, `ENV`, `CMD`, `COPY`, and `RUN`.
- **Layered Architecture:** Efficiently captures delta changes for `COPY` and `RUN` commands into deterministic tar layers.
- **Image Caching:** Implements caching during builds. Each layer build verifies against previously cached digests to speed up the process. A `--no-cache` option is available.
- **Process Isolation:** Uses Linux `unshare` utility to run commands in isolated mount, UTS, IPC, network, and PID namespaces.
- **Local Registry:** Stores images, layers, and caches within your home directory `~/.docksmith`.

## Prerequisites & Installation

DockSmith is designed to be fundamentally lightweight and has **zero external Python dependencies**. Everything runs exclusively on the standard Python 3 toolchain!

**Requirements:**
- **Python 3.6+** installed.
- A **Linux OS** environment to leverage namespace isolation (relies on the built-in `unshare` utility). Windows/macOS can run builds but lack true kernel isolation.

No `pip install` commands or virtual environments are needed. Just download the files and run!

## Commands to Run the Project

DockSmith operates largely like docker. You run it by executing Python directly, or linking the executable:

### 1. Build an Image
Build a new image using a `Docksmithfile` located in your context directory.
```bash
python3 docksmith.py build -t <name:tag> <context_directory>
```
**Options:**
- `--no-cache`: Do not use the cache when building the image.

**Supported Docksmithfile Instructions:** `FROM`, `WORKDIR`, `ENV`, `CMD`, `COPY`, `RUN`.

### 2. List Images
Display all images currently stored in the local registry with their short ID and creation timestamp.
```bash
python3 docksmith.py images
```

### 3. Run a Container
Run an isolated process from a specified image.
```bash
python3 docksmith.py run <name:tag> [command...]
```
**Options:**
- `-e key=value`: Set environment variables dynamically prior to runtime.

**Notes:** If you provide `[command...]` via the CLI, it will override the default `CMD` specified in the image manifest. 

### 4. Remove an Image
Remove the given image manifest and delete all its associated layers.
```bash
python3 docksmith.py rmi <name:tag>
```

## Step-by-Step Demo Guide

To see DockSmith in action, you can build and run the provided `sample_app`. Follow these exact commands sequentially:

### 1. Download Base Image
Pull the Alpine base layer into the root registry:
```bash
sudo python3 setup_base_image.py
```

### 2. Build the Image
Build the container and observe cache misses on the first run:
```bash
sudo python3 docksmith.py build -t myapp:latest ./sample_app
```

### 3. Demonstrate Cache Hit
Run the exact same build command again to see the cache instantly answer for all layers:
```bash
sudo python3 docksmith.py build -t myapp:latest ./sample_app
```

### 4. Demonstrate Cache Invalidation
Modify a local context file, and rebuild. You'll see the hash detect changes:
```bash
echo " " >> ./sample_app/main.sh
sudo python3 docksmith.py build -t myapp:latest ./sample_app
```

### 5. Verify the Image Exists
List images to ensure `myapp` is stored correctly:
```bash
sudo python3 docksmith.py images
```

### 6. Run the Default Command
Execute the container:
```bash
sudo python3 docksmith.py run myapp:latest
```

### 7. Override the Environment Variable
Run the container but inject a customized environment variable:
```bash
sudo python3 docksmith.py run -e GREETING="Im changing this from the terminal!" myapp:latest
```

### 8. Test Isolation (Write and Read)
Create a file inside the container and prove it exists inside the isolated namespace:
```bash
sudo python3 docksmith.py run myapp:latest -- /bin/sh -c "echo 'secret data' > /tmp/secret-container-file.txt && cat /tmp/secret-container-file.txt"
```

### 9. Verify Host Independence
Try to read that temporary file from your Ubuntu terminal to prove the container didn't leak files to the host OS:
```bash
cat /tmp/secret-container-file.txt
```
*(This should safely fail with `No such file or directory`)*

### 10. Clean Up
Finally, clear out the image and all its associated layers:
```bash
sudo python3 docksmith.py rmi myapp:latest
```

## Key Edge Cases Handled

- **Platform Fallback:** If running on Windows or macOS (not Linux), strict process isolation (namespaces/chroot) via `unshare` is gracefully disabled and processes run natively with a warning.
- **Command Precedence:** CLI commands passed to `run` strictly override the internal Manifest `CMD`. If neither is provided, an error is properly thrown and execution halts.
- **Missing Base Image Validation:** The build engine cross-verifies base image existence locally in the registry when executing the `FROM` step. Halts with a clear error if missing.
- **Invalid Instructions:** Passing unrecognised instructions in a `Docksmithfile` or malformed JSON into a `CMD` block halts the build reliably displaying the faulty instruction and line number.
- **Deterministic Archiving:** Modifies all tar layer metadata, like setting MTIME, UID, GID, UNAME, and GNAME to zero, ensuring cache keys remain pure and deterministic across varying system constraints.
- **Clean Fallback on Execution Errors:** Always recursively deletes temporary isolated filesystems assembled for layer deltas and runtime executions, even if commands fail.
