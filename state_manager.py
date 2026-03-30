import os
import json
import shutil
import hashlib

def get_docksmith_dir():
    home = os.path.expanduser("~")
    return os.path.join(home, ".docksmith")

def init_state():
    base = get_docksmith_dir()
    for d in ["images", "layers", "cache"]:
        path = os.path.join(base, d)
        if not os.path.exists(path):
            os.makedirs(path)

def get_image_path(name_tag):
    # Expects format name:tag
    # We replace : with _ to be filesystem friendly, though json allows : in filenames on Linux
    # Specs say "one JSON manifest per image", so myapp:latest might be myapp_latest.json
    safe_name = name_tag.replace(":", "_") + ".json"
    return os.path.join(get_docksmith_dir(), "images", safe_name)

def read_manifest(name_tag):
    path = get_image_path(name_tag)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_manifest(name_tag, manifest):
    # Calculate canonical manifest digest first
    temp_manifest = manifest.copy()
    temp_manifest["digest"] = ""
    # "compute the SHA-256 of that serialized bytes"
    canonical_bytes = json.dumps(temp_manifest, separators=(',', ':'), sort_keys=True).encode('utf-8')
    computed_digest = "sha256:" + hashlib.sha256(canonical_bytes).hexdigest()
    
    # Store the true digest
    manifest["digest"] = computed_digest
    path = get_image_path(name_tag)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

def list_images():
    images_dir = os.path.join(get_docksmith_dir(), "images")
    if not os.path.exists(images_dir):
        return []
    
    images = []
    for f in os.listdir(images_dir):
        if f.endswith(".json"):
            with open(os.path.join(images_dir, f), "r", encoding="utf-8") as fp:
                manifest = json.load(fp)
                images.append(manifest)
    return images

def delete_image_and_layers(name_tag):
    manifest = read_manifest(name_tag)
    if not manifest:
        return False
    
    # Remove layers
    for layer in manifest.get("layers", []):
        digest = layer.get("digest")
        if digest:
            layer_path = get_layer_path(digest)
            if os.path.exists(layer_path):
                os.remove(layer_path)
                
    # Remove manifest
    os.remove(get_image_path(name_tag))
    return True

def store_layer(tar_bytes):
    # "named by the SHA-256 digest of the tar's raw bytes"
    sha = hashlib.sha256(tar_bytes).hexdigest()
    digest = f"sha256:{sha}"
    layer_path = get_layer_path(digest)
    
    # Only write if it doesn't exist
    if not os.path.exists(layer_path):
        with open(layer_path, "wb") as f:
            f.write(tar_bytes)
            
    return digest, len(tar_bytes)

def get_layer_path(digest):
    # Digest format: "sha256:abcd..." -> convert to "sha256_abcd...tar" or similar to avoid colon
    safe_digest = digest.replace(":", "_") + ".tar"
    return os.path.join(get_docksmith_dir(), "layers", safe_digest)

# Run init automatically on import
init_state()
