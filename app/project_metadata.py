"""
Lecture et validation des métadonnées projet depuis depot/<project>/project.yaml.

Si le fichier n'existe pas, toutes les valeurs sont auto ou par défaut.
"""

from pathlib import Path
from datetime import datetime
import hashlib

from app.paths import DEPOT_DIR

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


VALID_DOCUMENT_TYPES = {
    "auto", "article", "livret", "petit_livre", "livre",
    "rapport", "formation", "conference", "enseignement", "reunion",
}

VALID_PUBLICATION_FORMATS = {"auto", "digital", "print", "booklet", "book"}

VALID_PAGE_SIZES = {"auto", "letter", "a4", "digest", "six_by_nine"}

VALID_TEMPLATES = {
    "auto", "standard", "conference", "formation", "enseignement",
    "livre", "rapport", "reunion", "spirituel", "professionnel",
}

VALID_THEMES = {
    "auto",
    "sobre_classique",
    "moderne_epure",
    "naturel_chaleureux",
    "spirituel_inspirant",
    "elegant_professionnel",
}

VALID_FONT_STYLES = {"auto", "classic", "modern", "elegant", "readable"}

VALID_COVER_IMAGE_SOURCES = {"user", "generated", "free_stock", "none"}

DEFAULTS: dict = {
    "title": "",
    "subtitle": "",
    "author": "",
    "organization": "TranscriptionAI",
    "language": "fr",
    "document_type": "auto",
    "publication_format": "auto",
    "template": "auto",
    "page_size": "auto",
    "cover_image": "auto",
    "cover_image_source": "none",
    "print_ready": True,
    "theme": "auto",
    "font_style": "auto",
    "include_cover": True,
    "include_toc": True,
    "include_page_numbers": True,
    "include_headers": True,
    "include_footers": True,
}


def get_yaml_path(project_name: str) -> Path:
    return DEPOT_DIR / project_name / "project.yaml"


def yaml_file_hash(project_name: str) -> str:
    """MD5 du project.yaml, ou chaîne vide s'il n'existe pas."""
    yaml_path = get_yaml_path(project_name)
    if not yaml_path.exists():
        return ""
    hasher = hashlib.md5()
    with yaml_path.open("rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _parse_yaml_file(yaml_path: Path) -> dict:
    if _HAS_YAML:
        return yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}

    # Fallback : parseur minimal key: value
    data: dict = {}
    for line in yaml_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.lower() in ("true", "yes", "oui"):
            data[key] = True
        elif value.lower() in ("false", "no", "non"):
            data[key] = False
        else:
            data[key] = value
    return data


def _validate_enum(raw: dict, key: str, valid_set: set, default: str) -> str:
    value = str(raw.get(key, default)).strip().lower()
    return value if value in valid_set else default


def load_project_metadata(project_name: str) -> dict:
    """
    Charge les métadonnées depuis depot/<project>/project.yaml.

    Retourne un dictionnaire complet avec valeurs par défaut pour
    tous les champs manquants ou invalides.
    """
    yaml_path = get_yaml_path(project_name)
    raw: dict = {}

    if yaml_path.exists():
        try:
            raw = _parse_yaml_file(yaml_path)
        except Exception as exc:
            print(f"[metadata] Erreur lecture project.yaml : {exc}")

    meta = dict(DEFAULTS)

    # Champs texte libres
    for key in ("title", "subtitle", "author", "organization", "language"):
        if key in raw and raw[key]:
            meta[key] = str(raw[key]).strip()

    # Titre par défaut = nom du projet humanisé
    if not meta["title"]:
        meta["title"] = project_name.replace("_", " ").title()

    # Champs enum validés
    meta["document_type"] = _validate_enum(
        raw, "document_type", VALID_DOCUMENT_TYPES, "auto"
    )
    meta["publication_format"] = _validate_enum(
        raw, "publication_format", VALID_PUBLICATION_FORMATS, "auto"
    )
    meta["template"] = _validate_enum(raw, "template", VALID_TEMPLATES, "auto")
    meta["page_size"] = _validate_enum(raw, "page_size", VALID_PAGE_SIZES, "auto")
    meta["theme"] = _validate_enum(raw, "theme", VALID_THEMES, "auto")
    meta["font_style"] = _validate_enum(
        raw, "font_style", VALID_FONT_STYLES, "auto"
    )
    meta["cover_image_source"] = _validate_enum(
        raw, "cover_image_source", VALID_COVER_IMAGE_SOURCES, "none"
    )

    # cover_image : chemin relatif ou auto/none
    cover_raw = raw.get("cover_image", "auto")
    meta["cover_image"] = str(cover_raw).strip() if isinstance(cover_raw, str) else "auto"

    # Champs booléens
    for key in (
        "print_ready",
        "include_cover",
        "include_toc",
        "include_page_numbers",
        "include_headers",
        "include_footers",
    ):
        if key in raw:
            val = raw[key]
            if isinstance(val, bool):
                meta[key] = val
            elif isinstance(val, str):
                meta[key] = val.lower() in ("true", "yes", "oui", "1")

    # Métadonnées internes
    meta["_yaml_exists"] = yaml_path.exists()
    meta["_yaml_path"] = str(yaml_path)
    meta["_generated_date"] = datetime.now().strftime("%Y-%m-%d")

    return meta
