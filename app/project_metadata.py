"""
Lecture et validation des métadonnées projet depuis depot/<project>/project.yaml.

Si le fichier n'existe pas, toutes les valeurs sont auto ou par défaut.
"""

from pathlib import Path
from datetime import datetime
import hashlib
import json

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

VALID_COVER_GENERATION_MODES = {"auto", "image", "typography", "none"}

VALID_COVER_STYLES = {
    "auto",
    "editorial_realistic",
    "spiritual",
    "professional",
    "modern",
    "natural",
}

DEFAULTS: dict = {
    # Identité du document
    "title": "",
    "subtitle": "",
    "author": "",
    "organization": "TranscriptionAI",
    "language": "fr",
    "date": "",           # date utilisateur ou date du jour
    "version": "1.0",

    # Type et format
    "document_type": "auto",
    "publication_format": "auto",
    "template": "auto",
    "page_size": "auto",
    "cover_image": "auto",
    "cover_image_source": "none",
    "cover_generation_mode": "auto",
    "cover_style": "auto",
    "print_ready": True,
    "theme": "auto",
    "font_style": "auto",

    # Métadonnées éditoriales
    "description": "",
    "keywords": "",
    "category": "",
    "audience": "",
    "copyright": "",
    "license": "",
    "isbn": "",
    "publisher": "",
    "location": "",

    # Éléments de publication
    "include_cover": True,
    "include_toc": True,
    "include_page_numbers": True,
    "include_headers": True,
    "include_footers": True,
    "include_date": True,
    "include_author": True,
    "include_organization": True,
}

# Champs texte libres de base
_TEXT_FIELDS_BASE = (
    "title", "subtitle", "author", "organization", "language", "version",
)

# Champs texte libres éditoriaux
_TEXT_FIELDS_EDITORIAL = (
    "description", "keywords", "category", "audience",
    "copyright", "license", "isbn", "publisher", "location",
)

# Champs booléens
_BOOL_FIELDS = (
    "print_ready",
    "include_cover",
    "include_toc",
    "include_page_numbers",
    "include_headers",
    "include_footers",
    "include_date",
    "include_author",
    "include_organization",
)

# Champs inclus dans la signature de métadonnées
_SIGNATURE_FIELDS = (
    "title", "subtitle", "author", "organization", "language",
    "date", "version", "description", "keywords", "category",
    "audience", "copyright", "license", "isbn", "publisher", "location",
    "include_cover", "include_toc", "include_page_numbers",
    "include_headers", "include_footers", "include_date",
    "include_author", "include_organization",
)


def get_yaml_path(project_name: str) -> Path:
    """
    Retourne le chemin vers project.yaml en résolvant le vrai dossier source.

    Cherche d'abord le dossier direct depot/<project_name>/, puis un dossier
    dont le nom sanitisé correspond (ex. "pastoral retreat" → "pastoral_retreat").
    Si aucun dossier n'est trouvé, retourne le chemin canonique (peut être inexistant).
    """
    try:
        from app.file_utils import sanitize_name
        direct = DEPOT_DIR / project_name
        if direct.is_dir():
            return direct / "project.yaml"
        if DEPOT_DIR.exists():
            for d in DEPOT_DIR.iterdir():
                if d.is_dir() and sanitize_name(d.name) == project_name:
                    return d / "project.yaml"
    except Exception:
        pass
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


def metadata_signature(meta: dict) -> str:
    """MD5 des champs de métadonnées clés (titre, auteur, etc.)."""
    fields = {k: meta.get(k, "") for k in _SIGNATURE_FIELDS}
    return hashlib.md5(
        json.dumps(fields, sort_keys=True, default=str).encode()
    ).hexdigest()


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


def _parse_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "yes", "oui", "1")
    return bool(val)


def load_project_metadata(project_name: str) -> dict:
    """
    Charge les métadonnées depuis depot/<project>/project.yaml.

    Retourne un dictionnaire complet avec valeurs par défaut pour
    tous les champs manquants ou invalides. Ne plante jamais même
    si project.yaml est absent ou malformé.
    """
    yaml_path = get_yaml_path(project_name)
    raw: dict = {}

    if yaml_path.exists():
        try:
            raw = _parse_yaml_file(yaml_path)
        except Exception as exc:
            print(f"[metadata] Erreur lecture project.yaml : {exc}")

    meta = dict(DEFAULTS)

    # Champs texte de base
    for key in _TEXT_FIELDS_BASE:
        if key in raw and raw[key] is not None:
            meta[key] = str(raw[key]).strip()

    # Titre par défaut = nom du projet humanisé
    if not meta["title"]:
        meta["title"] = project_name.replace("_", " ").title()

    # Date : valeur yaml ou date du jour
    if "date" in raw and raw["date"]:
        meta["date"] = str(raw["date"]).strip()
    else:
        meta["date"] = datetime.now().strftime("%Y-%m-%d")

    # Champs texte éditoriaux
    for key in _TEXT_FIELDS_EDITORIAL:
        if key in raw and raw[key] is not None:
            meta[key] = str(raw[key]).strip()

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
    meta["cover_generation_mode"] = _validate_enum(
        raw, "cover_generation_mode", VALID_COVER_GENERATION_MODES, "auto"
    )
    meta["cover_style"] = _validate_enum(
        raw, "cover_style", VALID_COVER_STYLES, "auto"
    )
    # Résoudre cover_style "auto" → valeur par défaut de config
    if meta["cover_style"] == "auto":
        try:
            from app import config as _cfg
            meta["cover_style"] = getattr(_cfg, "COVER_STYLE", "editorial_realistic")
        except ImportError:
            meta["cover_style"] = "editorial_realistic"

    # cover_image : chemin relatif ou auto/none
    cover_raw = raw.get("cover_image", "auto")
    meta["cover_image"] = str(cover_raw).strip() if isinstance(cover_raw, str) else "auto"

    # Champs booléens
    for key in _BOOL_FIELDS:
        if key in raw:
            meta[key] = _parse_bool(raw[key])

    # Métadonnées internes
    meta["_yaml_exists"] = yaml_path.exists()
    meta["_yaml_path"] = str(yaml_path)
    meta["_generated_date"] = datetime.now().strftime("%Y-%m-%d")

    return meta
