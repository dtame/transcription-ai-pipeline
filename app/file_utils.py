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


def content_hash(text: str, encoding: str = "utf-8") -> str:
    """Calcule le hash SHA256 d'un contenu texte."""
    return hashlib.sha256(text.encode(encoding)).hexdigest()


def write_text_if_changed(path: Path, content: str, encoding: str = "utf-8") -> str:
    """
    Écrit le fichier seulement si le contenu est différent du fichier existant.

    Retourne :
        "created"   – le fichier n'existait pas
        "updated"   – le fichier existait mais le contenu diffère
        "unchanged" – le fichier existait et le contenu est identique
    """
    if not path.exists():
        path.write_text(content, encoding=encoding)
        return "created"

    existing = path.read_text(encoding=encoding)
    if existing == content:
        return "unchanged"

    path.write_text(content, encoding=encoding)
    return "updated"
