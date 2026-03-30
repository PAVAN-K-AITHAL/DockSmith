# Docksmith Implementation Plan

Docksmith is a simplified Docker-like build and runtime system built from scratch, as requested in the project requirements. It features:
- A CLI binary with no background daemon.
- A Build Engine supporting exactly six instructions: `FROM`, `COPY`, `RUN`, `WORKDIR`, `ENV`, and `CMD`.
- A deterministic build cache with a cascade invalidation mechanism.
- Process isolation restricting access to the host ecosystem.

## User Review Required

> [!WARNING]
> **Operating System Restraints (Crucial)**
> The project specifications explicitly state: **"Requires Linux... JUST USE A LINUX VM. WSL has its own quirks."** Furthermore, it has a core requirement for *Strict Process Isolation*, stating that we must "Implement isolation directly using OS primitives."
> Your current operating system is **Windows**. Native Windows does not support Linux primitives like `chroot` or `unshare` (namespaces) which are necessary for container process isolation.
> 
> **My Proposal:** I will write the complete codebase for Docksmith, assuming a Linux environment. You will then need to run or test the resulting code in a Linux VM (like Ubuntu).

> [!IMPORTANT]
> **Language Choice**
> I propose writing Docksmith in **Python**, as it has excellent standard libraries for interacting with the filesystem (`os`, `shutil`, `tarfile`), calculating hashes (`hashlib`), and creating CLIs (`argparse`). `os.chroot` and `os.unshare` are available in Python on Linux for isolation. Alternatively, we could use Go, which is the industry standard for container runtimes. 
> *Are you okay with using Python, or do you have a specific language preference (e.g., Go)?*

---

## Proposed Changes

### Core Architecture

We will organize the code cleanly to align with the proposed Team Work Breakdown. The codebase will be created in `c:/Users/PAVAN K AITHAL/OneDrive/Desktop/Docksmith/`.

#### [NEW] [docksmith.py](file:///c:/Users/PAVAN%20K%20AITHAL/OneDrive/Desktop/Docksmith/docksmith.py)
This will serve as the main CLI entry point. It will handle argument parsing for the four required commands: `build`, `images`, `rmi`, and `run`.

#### [NEW] [state_manager.py](file:///c:/Users/PAVAN%20K%20AITHAL/OneDrive/Desktop/Docksmith/state_manager.py)
Responsible for setting up and managing the `~/.docksmith/` directory structure:
- `images/`: JSON manifests
- `layers/`: Content-addressed tar files
- `cache/`: Index mapping cache keys to layer digests

It will also handle logic for `docksmith images` and `docksmith rmi`.

#### [NEW] [build_engine.py](file:///c:/Users/PAVAN%20K%20AITHAL/OneDrive/Desktop/Docksmith/build_engine.py)
Parses the `Docksmithfile` and manages the state of a build. Executes instructions (`FROM`, `COPY`, `RUN`, `WORKDIR`, `ENV`, `CMD`), logs output, and creates the final image manifest JSON.

#### [NEW] [cache_engine.py](file:///c:/Users/PAVAN%20K%20AITHAL/OneDrive/Desktop/Docksmith/cache_engine.py)
Computes cache keys using `hashlib.sha256` according to the strict specification (previous digest, instruction text, WORKDIR, ENV, source files). Manages the `[CACHE HIT]` / `[CACHE MISS]` outputs and cascade logic. Ensures deterministic tarball creation (sorted entries, zeroed timestamps).

#### [NEW] [runtime.py](file:///c:/Users/PAVAN%20K%20AITHAL/OneDrive/Desktop/Docksmith/runtime.py)
The core OS process isolation mechanism used by both `docksmith run` and the `RUN` build instruction.
Will use `os.chroot` and Linux namespaces (via `unshare` or similar syscalls/wrappers tool) to trap the process.
Extracts tar layers in order to assemble a root filesystem temporarily before executing the command.

#### [NEW] [sample_app/Docksmithfile](file:///c:/Users/PAVAN%20K%20AITHAL/OneDrive/Desktop/Docksmith/sample_app/Docksmithfile)
The required demonstrative app, which uses a pre-downloaded minimal image and implements all six instructions.

---

## Open Questions

1. **Language Choice:** Python or Go? Python is readily available, but please confirm.
2. **Testing Environment:** Are you currently able to move the final code into a Linux VM for testing, or do you want me to attempt a WSL-friendly mechanism for now (even though the specs discourage it)?
3. **Base Image:** For the sample app, do you already have a `rootfs.tar` (e.g., an alpine minirootfs) that you'd like to use as the base image to test the offline functionality?

## Verification Plan

### Automated Tests
* We will create a local mock test suite to verify the cache key generation and parser logic, as those can run on Windows without namespaces.

### Manual Verification (Requires Linux VM)
*   **Command 1:** `python docksmith.py build -t myapp:latest .` -> Verify caching logs (Misses).
*   **Command 2:** `python docksmith.py build -t myapp:latest .` -> Verify caching logs (Hits).
*   **Command 3:** Verify `images` command lists the new image.
*   **Command 4:** `python docksmith.py run myapp:latest` -> Inspect console output.
*   **Command 5:** `python docksmith.py run -e KEY=val myapp:latest` -> Verify env injections.
*   **Demonstrate Isolation:** Attempt to write to a host directory during `run`. Ensure it strictly fails.
