# DockSmith

A simplified Docker-like build and runtime system built from scratch. DockSmith implements container image building with layer caching, content-addressed storage, and Linux process isolation — all without depending on Docker, runc, or any existing container runtime.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Usage](#usage)
  - [Building an Image](#building-an-image)
  - [Listing Images](#listing-images)
  - [Running a Container](#running-a-container)
  - [Removing an Image](#removing-an-image)
- [Demo Walkthrough](#demo-walkthrough)
- [Docksmithfile Reference](#docksmithfile-reference)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Operating System

DockSmith **requires Linux** for process isolation. If you are on Windows or macOS, use one of:

- **WSL2** (Windows Subsystem for Linux 2) — recommended for Windows users
- **VirtualBox / VMware** with a Linux guest (Ubuntu 22.04+ recommended)

### System Dependencies

| Dependency | Purpose | How to check |
|---|---|---|
| **Python 3.8+** | Runtime for DockSmith | `python3 --version` |
| **unshare** (part of `util-linux`) | Process isolation (namespaces + chroot) | `which unshare` |
| **tar** | Layer extraction (used by Python's `tarfile`) | `which tar` |
| **Internet access** | One-time only — to download the Alpine base image | `curl -I https://dl-cdn.alpinelinux.org` |

#### Installing dependencies (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y python3 util-linux
```

#### Installing dependencies (Fedora/RHEL)

```bash
sudo dnf install -y python3 util-linux
```

#### Installing dependencies (Arch Linux)

```bash
sudo pacman -S python util-linux
```

> **Note:** `util-linux` (which provides `unshare`) is pre-installed on virtually all Linux distributions. You likely already have it.

### Python Dependencies

**None.** DockSmith uses only the Python standard library. No `pip install` required.

---

## Initial Setup

### 1. Clone the repository

```bash
git clone <your-repo-url> DockSmith
cd DockSmith
```

### 2. Import the base image (one-time, requires internet)

This downloads the Alpine Linux 3.18 mini-rootfs and imports it into the local store at `~/.docksmith/`. This is the **only** step that requires internet access. After this, everything works fully offline.

```bash
python3 setup_base_image.py
```

Expected output:

```
Downloading https://dl-cdn.alpinelinux.org/alpine/v3.18/releases/x86_64/alpine-minirootfs-3.18.4-x86_64.tar.gz...
Downloaded. Storing layer...
Alpine imported as alpine:latest
```

### 3. Verify the base image was imported

```bash
python3 docksmith.py images
```

Expected output:

```
Name                 Tag             ID              Created
alpine               latest          <12-char-id>    2023-11-20T00:00:00Z
```

You're ready to go. The state directory `~/.docksmith/` now contains:

```
~/.docksmith/
├── images/          # alpine_latest.json
├── layers/          # sha256_<hash>.tar (Alpine rootfs)
└── cache/           # (empty for now)
```

---

## Usage

### Building an Image

```bash
python3 docksmith.py build -t <name:tag> <context-directory>
```

**Arguments:**

| Argument | Description |
|---|---|
| `-t <name:tag>` | **Required.** Name and tag for the image (e.g., `myapp:latest`) |
| `<context-directory>` | **Required.** Path to directory containing the `Docksmithfile` and source files |
| `--no-cache` | Optional. Skip all cache lookups and writes for this build |

**Examples:**

```bash
# Build the sample app
python3 docksmith.py build -t myapp:latest ./sample_app

# Build without cache
python3 docksmith.py build -t myapp:latest --no-cache ./sample_app
```

**Sample output (cold build):**

```
Step 1/6 : FROM alpine:latest
Step 2/6 : ENV GREETING=Hello from the customized env
Step 3/6 : WORKDIR /app
Step 4/6 : COPY . /app
 ---> [CACHE MISS] sha256:abc123 (0.09s)
Step 5/6 : RUN chmod +x main.sh && echo "Ready!" > myapp.txt
 ---> [CACHE MISS] sha256:def456 (1.23s)
Step 6/6 : CMD ["./main.sh"]
Successfully built sha256:a3f9b2c1e5d7 myapp:latest (1.32s)
```

### Listing Images

```bash
python3 docksmith.py images
```

Displays all images in the local store with columns: **Name**, **Tag**, **ID** (first 12 characters of the SHA-256 digest), and **Created** timestamp.

**Sample output:**

```
Name                 Tag             ID              Created
alpine               latest          7a8b9c0d1e2f    2023-11-20T00:00:00Z
myapp                latest          a3f9b2c1e5d7    2026-04-15T07:10:00Z
```

### Running a Container

```bash
python3 docksmith.py run <name:tag> [command...]
```

> **Important:** Running containers requires **root privileges** (for `unshare` with namespace creation). Use `sudo`.

**Arguments:**

| Argument | Description |
|---|---|
| `<name:tag>` | **Required.** Image to run (e.g., `myapp:latest`) |
| `[command...]` | Optional. Overrides the image's CMD |
| `-e KEY=VALUE` | Optional. Set/override environment variable. Repeatable. |

**Examples:**

```bash
# Run with the image's default CMD
sudo python3 docksmith.py run myapp:latest

# Override the command
sudo python3 docksmith.py run myapp:latest /bin/sh -c "echo hello from inside"

# Override an environment variable
sudo python3 docksmith.py run -e GREETING="Overridden!" myapp:latest

# Multiple environment overrides
sudo python3 docksmith.py run -e GREETING="Hi" -e FOO=bar myapp:latest
```

**Sample output:**

```
=== SAMPLE APP RUNNING ===
GREETING: Hello from the customized env
Current directory is: /app
Catting myapp.txt:
Ready!
=========================
```

> **Note:** `docksmith run` also requires `sudo` because the build engine uses the same `execute_isolated()` function for `RUN` steps. If you want to build images that contain `RUN` instructions, you need `sudo` for building too:
>
> ```bash
> sudo python3 docksmith.py build -t myapp:latest ./sample_app
> ```

### Removing an Image

```bash
python3 docksmith.py rmi <name:tag>
```

Removes the image manifest **and** all of its layer files from `~/.docksmith/`. Fails with a clear error if the image doesn't exist.

> **Warning:** Layers are not reference-counted. If two images share a layer and you delete one, the shared layer file is deleted and the other image will be broken. This is expected behavior per the specification.

**Examples:**

```bash
python3 docksmith.py rmi myapp:latest
# Output: Removed image: myapp:latest

python3 docksmith.py rmi nonexistent:image
# Output: Error: No such image: nonexistent:image
```

---

## Demo Walkthrough

This walks through the complete 8-step demo sequence from the specification. Run all commands from the repository root.

### Prerequisites

```bash
# Make sure base image is imported
python3 setup_base_image.py

# Navigate to the repo root
cd /path/to/DockSmith
```

### Step 1 — Cold Build (all CACHE MISS)

```bash
sudo python3 docksmith.py build -t myapp:latest ./sample_app
```

All layer-producing steps (COPY, RUN) should show `[CACHE MISS]`. Build completes with total time printed.

### Step 2 — Warm Build (all CACHE HIT)

```bash
sudo python3 docksmith.py build -t myapp:latest ./sample_app
```

All layer-producing steps should now show `[CACHE HIT]`. Build completes near-instantly.

### Step 3 — Edit Source File, Then Rebuild

```bash
# Edit a source file
echo "# modified" >> ./sample_app/main.sh

# Rebuild
sudo python3 docksmith.py build -t myapp:latest ./sample_app

# Undo the edit (optional)
head -n 8 ./sample_app/main.sh > ./sample_app/main.sh.tmp && mv ./sample_app/main.sh.tmp ./sample_app/main.sh
```

The `COPY` step should show `[CACHE MISS]` (because a source file changed). The `RUN` step below it should also show `[CACHE MISS]` (cascade). Steps above the change would show `[CACHE HIT]` if there were any.

### Step 4 — List Images

```bash
python3 docksmith.py images
```

The image should be listed with correct Name (`myapp`), Tag (`latest`), ID (12-char digest prefix), and Created timestamp.

### Step 5 — Run Container

```bash
sudo python3 docksmith.py run myapp:latest
```

The container starts, prints output from `main.sh` (GREETING, current directory, myapp.txt contents), and exits cleanly.

### Step 6 — Run with Environment Override

```bash
sudo python3 docksmith.py run -e GREETING="Overridden value!" myapp:latest
```

The output should show `GREETING: Overridden value!` instead of the default.

### Step 7 — Verify Isolation (PASS/FAIL)

```bash
# Run a container that writes a file inside the container root
sudo python3 docksmith.py run myapp:latest /bin/sh -c "echo 'secret' > /tmp/isolation_test.txt"

# Check if the file appears anywhere on the host
find /tmp -name "isolation_test.txt" 2>/dev/null

# Expected: no output (PASS)
# If the file is found on the host: FAIL
```

The file written inside the container must **not** appear on the host filesystem.

### Step 8 — Remove Image

```bash
python3 docksmith.py rmi myapp:latest

# Verify it's gone
python3 docksmith.py images

# Verify layer files are removed
ls ~/.docksmith/layers/
# Only the Alpine base layer should remain (if alpine:latest still exists)
```

---

## Docksmithfile Reference

DockSmith reads build instructions from a file named `Docksmithfile` in the build context directory.

| Instruction | Syntax | Produces Layer? | Description |
|---|---|---|---|
| `FROM` | `FROM <image>:<tag>` | No | Uses the specified image's layers as the base filesystem. Must be present in local store. |
| `COPY` | `COPY <src> <dest>` | **Yes** | Copies files from build context into the image. Supports `*` and `**` globs. |
| `RUN` | `RUN <command>` | **Yes** | Executes a shell command inside the assembled filesystem (not on host). |
| `WORKDIR` | `WORKDIR <path>` | No | Sets the working directory for subsequent instructions. |
| `ENV` | `ENV <key>=<value>` | No | Stores an environment variable in the image config. |
| `CMD` | `CMD ["exec","arg"]` | No | Default command on container start. JSON array form required. |

**Example Docksmithfile:**

```dockerfile
FROM alpine:latest
ENV GREETING=Hello from the customized env
WORKDIR /app
COPY . /app
RUN chmod +x main.sh && echo "Ready!" > myapp.txt
CMD ["./main.sh"]
```

### Rules

- Only the 6 instructions above are supported. Any unrecognized instruction fails the build immediately with an error and line number.
- `RUN` commands must not require network access. All dependencies must be present in the build context or a prior layer.
- `CMD` must be in JSON array format (e.g., `CMD ["./main.sh"]`).
- Comments (lines starting with `#`) and blank lines are ignored.

---

## Project Structure

```
DockSmith/
│
├── docksmith.py            # CLI entry point — argparse, subcommands (build/images/rmi/run)
├── build_engine.py         # Build engine — parses Docksmithfile, executes instructions,
│                           #   manages layers and cache, writes manifests
├── cache_engine.py         # Build cache — cache key computation, hit/miss checks, index I/O
├── runtime.py              # Container runtime — rootfs assembly, process isolation (unshare)
├── state_manager.py        # State management — ~/.docksmith/ directory, manifest CRUD, layer storage
├── setup_base_image.py     # One-time script to download and import Alpine base image
├── extract.py              # Utility script (not part of runtime)
│
├── sample_app/             # Sample application for demo
│   ├── Docksmithfile       # Build instructions (uses all 6 instructions)
│   ├── main.sh             # Shell script (CMD target)
│   └── main.py             # Python script (alternative, not used by CMD)
│
└── Files/                  # Specification documents and planning files
```

### State Directory

All persistent state lives in `~/.docksmith/`:

```
~/.docksmith/
├── images/                 # One JSON manifest per image (e.g., myapp_latest.json)
├── layers/                 # Content-addressed tar files (e.g., sha256_<hash>.tar)
└── cache/                  # Cache index (index.json — maps cache keys to layer digests)
```

---

## How It Works

### Build Flow

1. The CLI parses arguments and calls the build engine.
2. The build engine reads the `Docksmithfile` line by line.
3. For each instruction:
   - **FROM**: Loads the base image's layers and config.
   - **WORKDIR / ENV / CMD**: Updates image config metadata only (no layer produced).
   - **COPY / RUN**: Computes a cache key. On cache hit, reuses the stored layer. On cache miss, executes the instruction, captures the filesystem delta as a tar, stores it content-addressed, and updates the cache index.
4. The final manifest (with computed digest) is written to `~/.docksmith/images/`.

### Container Runtime Flow

1. All layer tars are extracted in order into a temporary directory (later layers overwrite earlier ones).
2. The process is isolated into that root using `unshare` (Linux namespaces + pivot root).
3. Environment variables and working directory are applied.
4. The command executes inside the isolated filesystem.
5. The CLI waits for the process to exit, then cleans up the temporary directory.

### Process Isolation

DockSmith uses the Linux `unshare` utility with the following namespace flags:

| Flag | Namespace | Purpose |
|---|---|---|
| `-m` | Mount | Isolates mount points |
| `-u` | UTS | Isolates hostname |
| `-p` | PID | Isolates process IDs |
| `-f` | Fork | Required with `-p` for PID namespace |
| `-i` | IPC | Isolates inter-process communication |
| `-n` | Network | Blocks all network access |
| `-r` | User | Maps current user to root inside container |
| `-R` | Root | Pivots root filesystem to the assembled rootfs |

---

## Troubleshooting

### `unshare: unshare failed: Operation not permitted`

You need root privileges for namespace creation:

```bash
sudo python3 docksmith.py run myapp:latest
```

Or, if on a system with user namespaces enabled:

```bash
# Check if user namespaces are enabled
cat /proc/sys/kernel/unprivileged_userns_clone
# 1 = enabled, 0 = disabled

# Enable if needed (requires root)
sudo sysctl -w kernel.unprivileged_userns_clone=1
```

### `Error: Base image alpine:latest not found in local store`

Run the base image import script first:

```bash
python3 setup_base_image.py
```

### `Error: 'unshare' utility not found on this Linux system`

Install `util-linux`:

```bash
sudo apt install util-linux    # Debian/Ubuntu
sudo dnf install util-linux    # Fedora/RHEL
sudo pacman -S util-linux      # Arch
```

### `[WARNING] Not on Linux. Strict process isolation is disabled.`

You are running on Windows or macOS directly. DockSmith requires Linux for isolation. Use WSL2 or a Linux VM.

### Build cache not hitting when expected

Ensure your builds are deterministic:
- Tar entries are sorted and timestamps are zeroed (handled automatically by `create_deterministic_tar()`).
- If you modify any source file, `COPY` and all subsequent steps will be cache misses (this is correct — cascade invalidation).
- If a layer file was manually deleted from `~/.docksmith/layers/`, that step and all below it will be cache misses.

### `Permission denied` when writing to `~/.docksmith/`

Ensure the directory is owned by your user:

```bash
sudo chown -R $(whoami):$(whoami) ~/.docksmith
```

### Cleaning up everything

To start completely fresh:

```bash
rm -rf ~/.docksmith
python3 setup_base_image.py
```
