import hashlib
import re
from pathlib import Path

def sanitize_name(name: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "audio"

def file_hash(file_path: Path) -> str:
    hasher = hashlib.md5()

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)

    return hasher.hexdigest()

def unique_path(directory: Path, stem: str, suffix: str) -> Path:
    path = directory / f"{stem}{suffix}"
    counter = 2

    while path.exists():
        path = directory / f"{stem}_{counter}{suffix}"
        counter += 1

    return path
