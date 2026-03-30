import os
import json
import hashlib
from state_manager import get_docksmith_dir, get_layer_path

def get_cache_index_path():
    return os.path.join(get_docksmith_dir(), "cache", "index.json")

def load_cache():
    path = get_cache_index_path()
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_cache(cache):
    path = get_cache_index_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

def compute_cache_key(prev_digest, instruction_text, workdir, env_state, copy_sources=None):
    # env_state: dict of accumulated ENV pairs
    sorted_env = dict(sorted(env_state.items()))
    env_str = json.dumps(sorted_env) if sorted_env else ""
    workdir_str = workdir if workdir else ""
    
    components = [
        prev_digest,
        instruction_text.strip(),
        workdir_str,
        env_str
    ]
    
    if copy_sources:
        # copy_sources is a dict of path -> absolute_path
        sorted_paths = sorted(copy_sources.keys())
        combined_hash = ""
        for p in sorted_paths:
            abs_p = copy_sources[p]
            if os.path.isfile(abs_p):
                with open(abs_p, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                    combined_hash += file_hash
        components.append(combined_hash)
        
    raw_key = "|".join(components)
    return "sha256:" + hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

def check_cache(cache_key):
    cache = load_cache()
    if cache_key in cache:
        digest = cache[cache_key]
        layer_path = get_layer_path(digest)
        if os.path.exists(layer_path):
            return digest
    return None

def update_cache(cache_key, layer_digest):
    cache = load_cache()
    cache[cache_key] = layer_digest
    save_cache(cache)
