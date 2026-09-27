import hashlib
import json
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


_NATURAL_CHUNKS = re.compile(r"(\d+)")


def natural_sort_key(value: str) -> tuple:
    """
    Clé de tri naturel : les suites de chiffres sont comparées numériquement.

        audio 1, audio 2, audio 10        (et non audio 1, audio 10, audio 2)
        01-introduction, 02-session, 03-conclusion

    La comparaison textuelle est insensible à la casse ; la chaîne d'origine est
    ajoutée en fin de clé pour garantir un ordre total déterministe lorsque deux
    noms ne diffèrent que par la casse.

    Utilisée par le contrat Transcript V2 (ordre canonique des sources audio).
    Le tri lexicographique de app.project_manager reste inchangé (voir rapport
    Phase 1 § dette restante).
    """
    key: list[tuple[int, int, str]] = []

    for chunk in _NATURAL_CHUNKS.split(str(value)):
        if chunk.isdigit():
            key.append((1, int(chunk), ""))
        elif chunk:
            key.append((0, 0, chunk.casefold()))

    key.append((2, 0, str(value)))

    return tuple(key)


def content_hash(text: str, encoding: str = "utf-8") -> str:
    """Calcule le hash SHA256 d'un contenu texte."""
    return hashlib.sha256(text.encode(encoding)).hexdigest()


def write_text_atomic(path: Path, content: str, encoding: str = "utf-8") -> Path:
    """
    Écrit un fichier texte de façon atomique.

    Le contenu est d'abord écrit dans «<nom>.partial», qui ne remplace la cible
    que lorsqu'il est complet (Path.replace est atomique, y compris sur Windows).

    Conséquences garanties :
    - un crash ne laisse jamais un fichier final tronqué ;
    - un fichier final valide déjà présent survit à un échec d'écriture ;
    - aucun fichier temporaire ne subsiste après un échec.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".partial")

    try:
        temp_path.write_text(content, encoding=encoding)
        temp_path.replace(path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise

    return path


def write_json_atomic(path: Path, data, indent: int = 2) -> Path:
    """
    Sérialise `data` en JSON UTF-8 lisible et l'écrit de façon atomique.

    ensure_ascii=False : les accents français restent lisibles (« fidélité » et
    non « fid\\u00e9lit\\u00e9 »), la sortie reste facilement diffable.
    """
    content = json.dumps(data, ensure_ascii=False, indent=indent) + "\n"
    return write_text_atomic(path, content)


def read_json(path: Path):
    """Relit un fichier JSON UTF-8."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


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
