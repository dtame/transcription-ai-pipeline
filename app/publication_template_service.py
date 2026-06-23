"""
Service de gabarits de publication professionnels.

Responsabilités :
- Analyser document_final.md (mots, titres, sections)
- Déterminer document_type, page_size, template, theme, font_style si auto
- Construire document_publication.md (couverture + TOC + contenu)
- Gérer la reconstruction intelligente via signatures
"""

from pathlib import Path
from datetime import datetime
import hashlib
import re

from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state
from app.project_metadata import (
    load_project_metadata,
    yaml_file_hash,
    metadata_signature as compute_metadata_signature,
)
from app.publication_cleaner import is_publishable_heading, clean_publication_markdown


# ---------------------------------------------------------------------------
# Tables de résolution automatique
# ---------------------------------------------------------------------------

_DOC_TYPE_PAGE_SIZE: dict[str, str] = {
    "article": "letter",
    "livret": "letter",
    "rapport": "letter",
    "formation": "letter",
    "conference": "letter",
    "reunion": "letter",
    "enseignement": "letter",
    "petit_livre": "six_by_nine",
    "livre": "six_by_nine",
}

_DOC_TYPE_TEMPLATE: dict[str, str] = {
    "enseignement": "spirituel",
    "conference": "conference",
    "formation": "formation",
    "rapport": "rapport",
    "reunion": "reunion",
    "livre": "livre",
    "petit_livre": "livre",
}

_TEMPLATE_THEME: dict[str, str] = {
    "spirituel": "spirituel_inspirant",
    "conference": "moderne_epure",
    "formation": "sobre_classique",
    "rapport": "elegant_professionnel",
    "reunion": "sobre_classique",
    "livre": "sobre_classique",
    "standard": "moderne_epure",
    "professionnel": "elegant_professionnel",
}

_THEME_FONT_STYLE: dict[str, str] = {
    "spirituel_inspirant": "elegant",
    "moderne_epure": "modern",
    "sobre_classique": "classic",
    "elegant_professionnel": "modern",
    "naturel_chaleureux": "readable",
}

# Couleurs par thème : primary, secondary, accent
THEME_COLORS: dict[str, dict[str, str]] = {
    "sobre_classique": {
        "primary": "#1a1a1a",
        "secondary": "#f5f0e8",
        "accent": "#666666",
    },
    "moderne_epure": {
        "primary": "#2c3e50",
        "secondary": "#ffffff",
        "accent": "#7f8c8d",
    },
    "naturel_chaleureux": {
        "primary": "#4a7c59",
        "secondary": "#f5f0e3",
        "accent": "#8b6914",
    },
    "spirituel_inspirant": {
        "primary": "#1a3a5c",
        "secondary": "#fdf6e3",
        "accent": "#c9a227",
    },
    "elegant_professionnel": {
        "primary": "#2d2d2d",
        "secondary": "#f0ebe3",
        "accent": "#8a8a8a",
    },
}


# ---------------------------------------------------------------------------
# Analyse du document
# ---------------------------------------------------------------------------

def analyze_document(markdown: str) -> dict:
    """Compte mots, titres et sections dans un document Markdown."""
    words = len(markdown.split())
    h1_count = len(re.findall(r"^# ", markdown, re.MULTILINE))
    h2_count = len(re.findall(r"^## ", markdown, re.MULTILINE))
    h3_count = len(re.findall(r"^### ", markdown, re.MULTILINE))
    return {
        "word_count": words,
        "h1_count": h1_count,
        "h2_count": h2_count,
        "h3_count": h3_count,
        "total_headings": h1_count + h2_count + h3_count,
    }


def _auto_document_type(analysis: dict) -> str:
    words = analysis["word_count"]
    if words < 3_000:
        return "article"
    if words < 12_000:
        return "livret"
    if words < 40_000:
        return "petit_livre"
    return "livre"


# ---------------------------------------------------------------------------
# Résolution des paramètres de publication
# ---------------------------------------------------------------------------

def resolve_publication_settings(project_name: str, markdown: str) -> dict:
    """
    Fusionne les métadonnées projet avec la détection automatique.

    Retourne un dictionnaire de paramètres entièrement résolus
    (aucune valeur 'auto' restante).
    """
    meta = load_project_metadata(project_name)
    analysis = analyze_document(markdown)

    settings = dict(meta)
    settings["analysis"] = analysis

    # document_type
    if settings["document_type"] == "auto":
        settings["document_type"] = _auto_document_type(analysis)
    doc_type = settings["document_type"]

    # page_size (la valeur yaml prime si non-auto)
    if settings["page_size"] == "auto":
        settings["page_size"] = _DOC_TYPE_PAGE_SIZE.get(doc_type, "letter")

    # template
    if settings["template"] == "auto":
        settings["template"] = _DOC_TYPE_TEMPLATE.get(doc_type, "standard")
    template = settings["template"]

    # theme
    if settings["theme"] == "auto":
        settings["theme"] = _TEMPLATE_THEME.get(template, "moderne_epure")
    theme = settings["theme"]

    # font_style
    if settings["font_style"] == "auto":
        settings["font_style"] = _THEME_FONT_STYLE.get(theme, "readable")

    # couleurs du thème
    settings["theme_colors"] = THEME_COLORS.get(
        theme, THEME_COLORS["moderne_epure"]
    )

    return settings


# ---------------------------------------------------------------------------
# Extraction de titres et table des matières
# ---------------------------------------------------------------------------

def extract_headings(markdown: str, publishable_only: bool = True) -> list[dict]:
    """
    Extrait les titres H1/H2/H3 d'un document Markdown.

    Args:
        markdown:         Contenu Markdown à analyser.
        publishable_only: Si True (défaut), filtre les titres techniques
                          non publiables (chunk_XXX, Projet :, Généré le :, etc.)

    Retourne une liste de dicts avec les clés :
      - level (int) : 1, 2 ou 3
      - title (str) : texte du titre sans le préfixe #
    """
    headings: list[dict] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            title = stripped[4:].strip()
            level = 3
        elif stripped.startswith("## "):
            title = stripped[3:].strip()
            level = 2
        elif stripped.startswith("# "):
            title = stripped[2:].strip()
            level = 1
        else:
            continue

        if publishable_only and not is_publishable_heading(title):
            continue

        headings.append({"level": level, "title": title})
    return headings


def build_table_of_contents(headings: list[dict]) -> str:
    """
    Construit une table des matières Markdown à partir d'une liste de titres.

    Format :
      # Table des matières

      - Titre niveau 1
        - Titre niveau 2
          - Titre niveau 3
    """
    lines = ["# Table des matières", ""]
    for h in headings:
        indent = "  " * (h["level"] - 1)
        lines.append(f"{indent}- {h['title']}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Construction du document_publication.md
# ---------------------------------------------------------------------------

def _file_hash(path: Path) -> str:
    hasher = hashlib.md5()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _compute_source_signature(project_name: str, final_md_path: Path) -> dict:
    return {
        "final_md": _file_hash(final_md_path) if final_md_path.exists() else "",
        "yaml": yaml_file_hash(project_name),
    }


def _should_rebuild_publication_md(
    state: dict,
    pub_md_path: Path,
    current_sig: dict,
) -> bool:
    if not pub_md_path.exists():
        return True
    pub_state = state.get("publication", {}).get("markdown", {})
    if not pub_state.get("generated"):
        return True
    return pub_state.get("source_signature") != current_sig


def _build_cover_markdown(settings: dict) -> list[str]:
    """Construit les lignes Markdown de la page de couverture."""
    parts: list[str] = []

    parts.append(f"# {settings['title']}")
    parts.append("")

    if settings.get("subtitle"):
        parts.append(f"## {settings['subtitle']}")
        parts.append("")

    if settings.get("include_author", True) and settings.get("author"):
        parts.append(f"Auteur : {settings['author']}  ")

    if settings.get("include_organization", True) and settings.get("organization"):
        parts.append(f"Organisation : {settings['organization']}  ")

    if settings.get("include_date", True):
        date_display = settings.get("date") or settings.get("_generated_date", "")
        if date_display:
            parts.append(f"Date : {date_display}  ")

    if settings.get("version"):
        parts.append(f"Version : {settings['version']}  ")

    parts.append("")
    parts.append("---")
    parts.append("")

    return parts


def _get_content_source(project_name: str) -> tuple[Path, str]:
    """
    Retourne (chemin_source, label) en privilégiant par ordre :
      1. document_harmonized.md (si disponible)
      2. document_clean.md     (version nettoyée du final)
      3. document_final.md     (fallback)

    Labels : "harmonized" | "clean" | "final"
    """
    harmonized_md = SORTIE_DIR / project_name / "harmonized" / "document_harmonized.md"
    clean_md      = SORTIE_DIR / project_name / "final" / "document_clean.md"
    final_md      = SORTIE_DIR / project_name / "final" / "document_final.md"

    if harmonized_md.exists():
        return harmonized_md, "harmonized"
    if clean_md.exists():
        return clean_md, "clean"
    return final_md, "final"


def build_publication_markdown(project_name: str) -> Path | None:
    """
    Construit final/document_publication.md.

    Source de contenu (par ordre de priorité) :
      1. sortie/<projet>/harmonized/document_harmonized.md (si disponible)
      2. sortie/<projet>/final/document_final.md

    Structure du document :
      - Page de titre (si include_cover)
      - Table des matières (si include_toc)
      - Contenu de la source choisie

    Ne reconstruit pas si les sources n'ont pas changé.
    """
    final_dir = SORTIE_DIR / project_name / "final"
    final_md = final_dir / "document_final.md"
    pub_md = final_dir / "document_publication.md"

    if not final_md.exists():
        raise RuntimeError(
            f"[publication] document_final.md introuvable pour le projet '{project_name}'. "
            "Assurez-vous que l'étape final_document a réussi avant de relancer."
        )

    source_md, source_label = _get_content_source(project_name)

    source_labels = {
        "harmonized": "document_harmonized.md",
        "clean": "document_clean.md",
        "final": "document_final.md (fallback)",
    }
    print(f"[publication] Source : {source_labels.get(source_label, source_label)}")

    state = load_project_state(project_name)
    current_sig = _compute_source_signature(project_name, source_md)

    if not _should_rebuild_publication_md(state, pub_md, current_sig):
        print(f"[publication] document_publication.md déjà à jour : {pub_md}")
        return pub_md

    raw_content = source_md.read_text(encoding="utf-8")

    # Appliquer le nettoyage si la source est le document_final.md brut
    if source_label == "final":
        publication_content = clean_publication_markdown(raw_content)
    else:
        publication_content = raw_content

    settings = resolve_publication_settings(project_name, publication_content)

    parts: list[str] = []

    # ---- Page de titre ----
    if settings.get("include_cover", True):
        parts.extend(_build_cover_markdown(settings))

    # ---- Table des matières (titres publiables uniquement) ----
    headings: list[dict] = []
    if settings.get("include_toc", True):
        headings = extract_headings(publication_content, publishable_only=True)
        if headings:
            parts.append(build_table_of_contents(headings))
            parts.append("---")
            parts.append("")

    # ---- Contenu principal nettoyé ----
    parts.append(publication_content)

    pub_md.parent.mkdir(parents=True, exist_ok=True)
    pub_md.write_text("\n".join(parts), encoding="utf-8")

    generated_at = datetime.now().isoformat(timespec="seconds")

    settings_summary = {
        k: v
        for k, v in settings.items()
        if not k.startswith("_") and k not in ("analysis", "theme_colors")
    }

    if "publication" not in state:
        state["publication"] = {}

    state["publication"]["markdown"] = {
        "generated": True,
        "path": str(pub_md),
        "settings": settings_summary,
        "source_signature": current_sig,
        "content_source": source_label,
        "content_cleaned": source_label in ("clean", "harmonized"),
        "updated_at": generated_at,
    }

    state["publication"]["metadata_signature"] = compute_metadata_signature(settings)

    state["publication"]["toc"] = {
        "generated": settings.get("include_toc", True) and len(headings) > 0,
        "headings_count": len(headings),
        "updated_at": generated_at,
    }

    save_project_state(project_name, state)

    print(f"[publication] document_publication.md généré : {pub_md}")
    return pub_md
