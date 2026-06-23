"""
Service d'édition des métadonnées projet — TranscriptionAI.

Gère le chargement, la sauvegarde et la validation de
depot/<projet>/project.yaml depuis l'interface Streamlit.

Responsabilités :
  - Charger les métadonnées éditables avec valeurs par défaut
  - Créer project.yaml si absent
  - Sauvegarder en préservant les champs inconnus
  - Valider les valeurs avant sauvegarde
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

from app.paths import DEPOT_DIR
from app.project_metadata import (
    VALID_DOCUMENT_TYPES,
    VALID_TEMPLATES,
    VALID_THEMES,
    VALID_PAGE_SIZES,
    VALID_PUBLICATION_FORMATS,
    VALID_COVER_GENERATION_MODES,
    VALID_COVER_STYLES,
)

# Version applicative (best-effort)
try:
    from app import config as _cfg
    _APP_VERSION = getattr(_cfg, "VERSION", "1.0")
except Exception:
    _APP_VERSION = "1.0"

# ─────────────────────────────────────────────────────────────────────────────
# Listes d'options pour l'interface
# ─────────────────────────────────────────────────────────────────────────────

LANGUAGE_OPTIONS = ["fr", "en"]

DOCTYPE_OPTIONS = [
    "auto", "article", "livret", "petit_livre", "livre",
    "rapport", "formation", "conference", "enseignement", "reunion",
]

TEMPLATE_OPTIONS = [
    "auto", "standard", "conference", "formation", "enseignement",
    "livre", "rapport", "reunion", "spirituel", "professionnel",
]

THEME_OPTIONS = [
    "auto", "sobre_classique", "moderne_epure", "naturel_chaleureux",
    "spirituel_inspirant", "elegant_professionnel",
]

PAGESIZE_OPTIONS = ["auto", "letter", "a4", "digest", "six_by_nine"]

PUBFORMAT_OPTIONS = ["auto", "digital", "print", "booklet", "book"]

COVERMODE_OPTIONS = ["auto", "image", "typography"]

COVERSTYLE_OPTIONS = [
    "editorial_realistic", "spiritual", "professional", "modern", "natural",
]

# ─────────────────────────────────────────────────────────────────────────────
# Valeurs par défaut
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_METADATA: dict = {
    "title": "",
    "subtitle": "",
    "author": "",
    "organization": "",
    "language": "fr",
    "date": "",
    "version": "1.0",

    "document_type": "auto",
    "template": "auto",
    "theme": "auto",
    "page_size": "auto",
    "publication_format": "auto",

    "description": "",
    "keywords": [],
    "category": "",
    "audience": "",
    "copyright": "",
    "license": "",
    "isbn": "",
    "publisher": "",
    "location": "",

    "generated_by": "PublishForge",
    "generated_version": _APP_VERSION,

    "include_cover": True,
    "include_toc": True,
    "include_page_numbers": True,
    "include_headers": True,
    "include_footers": True,
    "include_date": True,
    "include_author": True,
    "include_organization": True,

    "cover_image": "auto",
    "cover_image_source": "auto",
    "cover_generation_mode": "auto",
    "cover_style": "editorial_realistic",
}

# Sections YAML avec commentaires — ordre canonique
_YAML_SECTIONS = [
    (
        "# Identité du document",
        ["title", "subtitle", "author", "organization", "language", "date", "version"],
    ),
    (
        "# Type et format de publication",
        ["document_type", "template", "theme", "page_size", "publication_format"],
    ),
    (
        "# Métadonnées éditoriales",
        [
            "description", "keywords", "category", "audience",
            "copyright", "license", "isbn", "publisher", "location",
        ],
    ),
    (
        "# Génération automatique",
        ["generated_by", "generated_version"],
    ),
    (
        "# Éléments inclus dans la publication",
        [
            "include_cover", "include_toc", "include_page_numbers",
            "include_headers", "include_footers", "include_date",
            "include_author", "include_organization",
        ],
    ),
    (
        "# Couverture",
        ["cover_image", "cover_image_source", "cover_generation_mode", "cover_style"],
    ),
]

_KNOWN_FIELDS: set[str] = {
    field
    for _, fields in _YAML_SECTIONS
    for field in fields
}


# ─────────────────────────────────────────────────────────────────────────────
# API publique
# ─────────────────────────────────────────────────────────────────────────────

def _find_project_source_dir(project_name: str) -> Path | None:
    """
    Résout le vrai dossier source d'un projet dans depot/.

    Essaie d'abord le chemin direct (depot/<project_name>/), puis cherche
    un sous-dossier de depot/ dont le nom *sanitisé* correspond à project_name.
    Cela gère les cas où le dossier contient des espaces ou des caractères
    spéciaux (ex. "pastoral retreat" → project_name "pastoral_retreat").

    Retourne le chemin absolu du dossier source, ou None si introuvable.
    """
    from app.file_utils import sanitize_name

    direct = DEPOT_DIR / project_name
    if direct.is_dir():
        return direct

    if DEPOT_DIR.exists():
        for d in DEPOT_DIR.iterdir():
            if d.is_dir() and sanitize_name(d.name) == project_name:
                return d
    return None


def get_yaml_path(project_name: str) -> Path:
    """
    Retourne le chemin vers project.yaml en résolvant le vrai dossier source.

    Si le dossier source est trouvé (même avec un nom contenant des espaces),
    retourne <source_dir>/project.yaml. Sinon, retourne le chemin canonique
    depot/<project_name>/project.yaml (dossier peut-être inexistant).
    """
    source_dir = _find_project_source_dir(project_name)
    if source_dir is not None:
        return source_dir / "project.yaml"
    return DEPOT_DIR / project_name / "project.yaml"


def _validate_project_name(project_name: str) -> None:
    """
    Vérifie que project_name est un identifiant technique simple et sûr.

    Lève ValueError si le nom contient des caractères interdits susceptibles
    de créer des chemins non désirés (traversée de répertoire, chemin absolu…).
    """
    if not project_name or not project_name.strip():
        raise ValueError("Le nom du projet ne peut pas être vide.")
    name = project_name.strip()
    _FORBIDDEN_TOKENS = ("/", "\\", ":", "..")
    for token in _FORBIDDEN_TOKENS:
        if token in name:
            raise ValueError(
                f"Nom de projet invalide : '{name}'. "
                f"Le jeton '{token}' est interdit dans un identifiant de projet."
            )
    if Path(name).is_absolute():
        raise ValueError(
            f"Nom de projet invalide : '{name}'. "
            f"Les chemins absolus sont interdits comme identifiant de projet."
        )


def ensure_project_yaml(project_name: str) -> Path:
    """
    Crée project.yaml avec les valeurs par défaut s'il n'existe pas.

    Le dossier source depot/<project_name> doit déjà exister (il peut avoir
    un nom contenant des espaces ou caractères spéciaux — la résolution est
    faite par _find_project_source_dir).
    Lève FileNotFoundError si aucun dossier source n'est trouvé.

    Retourne le chemin vers le fichier (existant ou nouvellement créé).
    """
    _validate_project_name(project_name)
    project_dir = _find_project_source_dir(project_name)

    if project_dir is None:
        raise FileNotFoundError(
            f"Le dossier projet '{project_name}' n'existe pas dans depot/. "
            f"Créez d'abord le dossier avec les fichiers audio avant d'initialiser project.yaml."
        )

    yaml_path = project_dir / "project.yaml"
    if yaml_path.exists():
        return yaml_path

    defaults = dict(DEFAULT_METADATA)
    defaults["title"] = project_name.replace("_", " ").title()
    defaults["date"] = datetime.now().strftime("%Y-%m-%d")

    _write_yaml(yaml_path, defaults)
    return yaml_path


def load_editable_metadata(project_name: str) -> dict:
    """
    Charge les métadonnées éditables depuis project.yaml.

    Retourne un dictionnaire complet (valeurs par défaut pour les champs
    manquants). Ne lève jamais d'exception.
    """
    yaml_path = get_yaml_path(project_name)
    raw: dict = {}

    if yaml_path.exists():
        try:
            raw = _load_yaml(yaml_path)
        except Exception as exc:
            print(f"[metadata_editor] Erreur lecture project.yaml : {exc}")

    result = dict(DEFAULT_METADATA)
    # Titre par défaut = nom humanisé
    if not result["title"]:
        result["title"] = project_name.replace("_", " ").title()
    result["date"] = datetime.now().strftime("%Y-%m-%d")

    for key, default in DEFAULT_METADATA.items():
        if key not in raw or raw[key] is None:
            continue
        raw_val = raw[key]
        if isinstance(default, bool):
            result[key] = _parse_bool(raw_val)
        elif isinstance(default, list):
            result[key] = _parse_list(raw_val)
        else:
            result[key] = str(raw_val).strip()

    return result


def save_editable_metadata(project_name: str, metadata: dict) -> Path:
    """
    Sauvegarde les métadonnées dans <source_dir>/project.yaml.

    Le dossier source est résolu via _find_project_source_dir : il peut avoir
    un nom différent du project_name sanitisé (ex. "pastoral retreat" pour
    le project_name "pastoral_retreat").
    Lève FileNotFoundError si aucun dossier source n'est trouvé, afin d'éviter
    toute création de dossier non désirée.

    Préserve les champs inconnus déjà présents dans le fichier.
    Retourne le chemin du fichier sauvegardé.
    """
    _validate_project_name(project_name)

    project_dir = _find_project_source_dir(project_name)
    if project_dir is None:
        raise FileNotFoundError(
            f"Le dossier projet '{project_name}' n'existe pas dans depot/. "
            f"Sauvegarde annulée — aucun dossier ne sera créé automatiquement."
        )

    yaml_path = project_dir / "project.yaml"

    # Charger l'existant pour préserver les champs inconnus
    existing: dict = {}
    if yaml_path.exists():
        try:
            existing = _load_yaml(yaml_path)
        except Exception:
            pass

    # Fusionner : les champs connus sont mis à jour, les inconnus conservés
    merged = {**existing, **metadata}
    _write_yaml(yaml_path, merged)
    return yaml_path


def validate_metadata(metadata: dict) -> tuple[bool, list[str]]:
    """
    Valide les métadonnées avant sauvegarde.

    Retourne (ok, liste_d_erreurs). Si ok=False, ne pas sauvegarder.
    """
    errors: list[str] = []

    title = str(metadata.get("title", "")).strip()
    if not title:
        errors.append("Le titre ne peut pas être vide.")

    language = str(metadata.get("language", "fr")).strip().lower()
    if language not in ("fr", "en"):
        errors.append(
            f"Langue invalide : « {language} ». Valeurs acceptées : fr, en."
        )

    version = str(metadata.get("version", "")).strip()
    if not version:
        errors.append("La version ne peut pas être vide.")

    doc_type = str(metadata.get("document_type", "auto")).strip().lower()
    if doc_type not in VALID_DOCUMENT_TYPES:
        errors.append(
            f"Type de document invalide : « {doc_type} ». "
            f"Valeurs : {', '.join(sorted(VALID_DOCUMENT_TYPES))}."
        )

    template = str(metadata.get("template", "auto")).strip().lower()
    if template not in VALID_TEMPLATES:
        errors.append(
            f"Gabarit invalide : « {template} ». "
            f"Valeurs : {', '.join(sorted(VALID_TEMPLATES))}."
        )

    theme = str(metadata.get("theme", "auto")).strip().lower()
    if theme not in VALID_THEMES:
        errors.append(
            f"Thème invalide : « {theme} ». "
            f"Valeurs : {', '.join(sorted(VALID_THEMES))}."
        )

    page_size = str(metadata.get("page_size", "auto")).strip().lower()
    if page_size not in VALID_PAGE_SIZES:
        errors.append(
            f"Taille de page invalide : « {page_size} ». "
            f"Valeurs : {', '.join(sorted(VALID_PAGE_SIZES))}."
        )

    cover_mode = str(metadata.get("cover_generation_mode", "auto")).strip().lower()
    if cover_mode not in VALID_COVER_GENERATION_MODES:
        errors.append(
            f"Mode couverture invalide : « {cover_mode} ». "
            f"Valeurs : {', '.join(sorted(VALID_COVER_GENERATION_MODES))}."
        )

    cover_style_raw = str(metadata.get("cover_style", "editorial_realistic")).strip().lower()
    valid_styles_extended = VALID_COVER_STYLES | {"auto"}
    if cover_style_raw not in valid_styles_extended:
        errors.append(
            f"Style de couverture invalide : « {cover_style_raw} ». "
            f"Valeurs : {', '.join(sorted(valid_styles_extended))}."
        )

    return len(errors) == 0, errors


def keywords_to_string(keywords) -> str:
    """Convertit une liste de mots-clés en chaîne séparée par des virgules."""
    if isinstance(keywords, list):
        return ", ".join(str(k) for k in keywords if k)
    if isinstance(keywords, str):
        return keywords
    return ""


def string_to_keywords(text: str) -> list[str]:
    """Convertit une chaîne séparée par des virgules en liste de mots-clés."""
    if not text or not text.strip():
        return []
    return [k.strip() for k in text.split(",") if k.strip()]


def option_index(options: list, value: str) -> int:
    """Retourne l'index d'une valeur dans une liste d'options (0 si absent)."""
    try:
        return options.index(str(value).strip().lower())
    except ValueError:
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────────

def _load_yaml(yaml_path: Path) -> dict:
    """Charge un fichier YAML. Utilise PyYAML si disponible."""
    if _HAS_YAML:
        content = yaml_path.read_text(encoding="utf-8")
        return yaml.safe_load(content) or {}
    return _parse_yaml_minimal(yaml_path)


def _write_yaml(path: Path, data: dict) -> None:
    """
    Écrit un fichier YAML lisible avec sections commentées.

    Les champs connus sont écrits dans un ordre canonique avec des
    commentaires de section. Les champs inconnus sont ajoutés à la fin.
    """
    lines: list[str] = []

    for comment, fields in _YAML_SECTIONS:
        lines.append(comment)
        for field in fields:
            if field in data:
                lines.append(_yaml_line(field, data[field]))
        lines.append("")

    unknown = {k: v for k, v in data.items() if k not in _KNOWN_FIELDS}
    if unknown:
        lines.append("# Champs personnalisés")
        for k, v in unknown.items():
            lines.append(_yaml_line(k, v))
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def _yaml_line(key: str, value) -> str:
    """Sérialise une paire clé/valeur YAML sur une ou plusieurs lignes."""
    if isinstance(value, bool):
        return f"{key}: {str(value).lower()}"
    if isinstance(value, list):
        if not value:
            return f"{key}: []"
        items = "\n".join(f"  - {_yaml_scalar(item)}" for item in value)
        return f"{key}:\n{items}"
    if value is None or value == "":
        return f'{key}: ""'
    return f"{key}: {_yaml_scalar(str(value))}"


def _yaml_scalar(value: str) -> str:
    """Ajoute des guillemets si la valeur contient des caractères spéciaux."""
    needs_quote = any(c in str(value) for c in ':#{}[]|>&*!,`"\'\\')
    if needs_quote:
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return str(value)


def _parse_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "yes", "oui", "1")
    return bool(val)


def _parse_list(val) -> list:
    if isinstance(val, list):
        return [str(item) for item in val if item is not None]
    if isinstance(val, str) and val.strip():
        return [v.strip() for v in val.split(",") if v.strip()]
    return []


def _parse_yaml_minimal(yaml_path: Path) -> dict:
    """Parseur YAML minimal (fallback sans PyYAML)."""
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
        elif value.startswith('"') and value.endswith('"'):
            data[key] = value[1:-1]
        else:
            data[key] = value
    return data
