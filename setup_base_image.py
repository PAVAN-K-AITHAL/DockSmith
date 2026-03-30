import urllib.request
import os
import tarfile
import json
from state_manager import store_layer, write_manifest

URL = "https://dl-cdn.alpinelinux.org/alpine/v3.18/releases/x86_64/alpine-minirootfs-3.18.4-x86_64.tar.gz"

print(f"Downloading {URL}...")
tar_gz_path, _ = urllib.request.urlretrieve(URL, "alpine.tar.gz")
print("Downloaded. Storing layer...")

with open(tar_gz_path, "rb") as f:
    tar_bytes = f.read()
    
# Store the layer
layer_digest, size = store_layer(tar_bytes)

manifest = {
    "name": "alpine",
    "tag": "latest",
    "digest": "",
    "created": "2023-11-20T00:00:00Z",
    "config": {
        "Env": ["PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"],
        "Cmd": ["/bin/sh"],
        "WorkingDir": "/"
    },
    "layers": [
        {"digest": layer_digest, "size": size, "createdBy": "Imported alpine mini-rootfs"}
    ]
}

write_manifest("alpine:latest", manifest)

print("Alpine imported as alpine:latest")
os.remove(tar_gz_path)
