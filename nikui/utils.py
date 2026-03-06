import os
import fnmatch

def is_excluded(filepath, config):
    if not filepath: return False
    norm_path = os.path.normpath(filepath)
    parts = norm_path.split(os.sep)
    for d in config.get("exclusions", {}).get("directories", []):
        if d in parts: return True
    for p in config.get("exclusions", {}).get("patterns", []):
        if fnmatch.fnmatch(norm_path, p) or fnmatch.fnmatch(os.path.basename(norm_path), p): return True
    return False
