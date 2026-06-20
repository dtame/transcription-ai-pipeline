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
from app.project_metadata import load_project_metadata, yaml_file_hash


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
# Construction du document_publication.md
# ---------------------------------------------------------------------------

def _extract_toc(markdown: str) -> list[tuple[int, str]]:
    """Extrait les titres pour la table des matières."""
    toc: list[tuple[int, str]] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            toc.append((3, stripped[4:].strip()))
        elif stripped.startswith("## "):
            toc.append((2, stripped[3:].strip()))
        elif stripped.startswith("# "):
            toc.append((1, stripped[2:].strip()))
    return toc


def _build_toc_markdown(toc: list[tuple[int, str]]) -> str:
    lines = ["# Table des matières", ""]
    for level, title in toc:
        indent = "  " * (level - 1)
        lines.append(f"{indent}- {title}")
    lines.append("")
    return "\n".join(lines)


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


def build_publication_markdown(project_name: str) -> Path | None:
    """
    Construit final/document_publication.md.

    Structure :
      - Page de titre (si include_cover)
      - Table des matières (si include_toc)
      - Contenu de document_final.md

    Ne reconstruit pas si les sources n'ont pas changé.
    """
    final_dir = SORTIE_DIR / project_name / "final"
    final_md = final_dir / "document_final.md"
    pub_md = final_dir / "document_publication.md"

    if not final_md.exists():
        print(
            f"[publication] document_final.md introuvable pour : {project_name}"
        )
        return None

    state = load_project_state(project_name)
    current_sig = _compute_source_signature(project_name, final_md)

    if not _should_rebuild_publication_md(state, pub_md, current_sig):
        print(f"[publication] document_publication.md déjà à jour : {pub_md}")
        return pub_md

    final_content = final_md.read_text(encoding="utf-8")
    settings = resolve_publication_settings(project_name, final_content)

    parts: list[str] = []

    # ---- Page de titre ----
    if settings.get("include_cover", True):
        parts.append(f"# {settings['title']}")
        parts.append("")

        if settings.get("subtitle"):
            parts.append(f"## {settings['subtitle']}")
            parts.append("")

        if settings.get("author"):
            parts.append(f"Auteur : {settings['author']}  ")
        if settings.get("organization"):
            parts.append(f"Organisation : {settings['organization']}  ")
        parts.append(f"Date : {settings['_generated_date']}  ")
        parts.append("")
        parts.append("---")
        parts.append("")

    # ---- Table des matières ----
    if settings.get("include_toc", True):
        toc = _extract_toc(final_content)
        if toc:
            parts.append(_build_toc_markdown(toc))
            parts.append("---")
            parts.append("")

    # ---- Contenu principal ----
    parts.append(final_content)

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
        "updated_at": generated_at,
    }

    save_project_state(project_name, state)

    print(f"[publication] document_publication.md généré : {pub_md}")
    return pub_md
