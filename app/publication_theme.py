"""
Publication Theme Engine — Thèmes de publication pour PublishForge.

Fournit une configuration centralisée des paramètres visuels selon
le type de livrable cible.

Modes supportés :
    BOOK, BOOKLET, SERMON, TRAINING,
    CONSULTING_REPORT, CORPORATE_REPORT, PODCAST
"""

from __future__ import annotations

VALID_MODES: frozenset[str] = frozenset({
    "BOOK",
    "BOOKLET",
    "SERMON",
    "TRAINING",
    "CONSULTING_REPORT",
    "CORPORATE_REPORT",
    "PODCAST",
})

DEFAULT_MODE = "BOOK"


# ─────────────────────────────────────────────────────────────────────────────
# Définitions de thèmes (valeurs par mode, sans les labels de langue)
# ─────────────────────────────────────────────────────────────────────────────

_THEMES: dict[str, dict] = {
    "BOOK": {
        "page_size":            "LETTER",
        "top_margin":           72,
        "bottom_margin":        72,
        "left_margin":          72,
        "right_margin":         72,
        "title_font_size":      26,
        "heading1_font_size":   18,
        "heading2_font_size":   14,
        "body_font_size":       11,
        "body_line_spacing":    1.15,
        "cover_style":          "classic",
        "include_cover":        True,
        "include_title_page":   True,
        "include_toc":          True,
    },
    "BOOKLET": {
        "page_size":            "LETTER",
        "top_margin":           54,
        "bottom_margin":        54,
        "left_margin":          54,
        "right_margin":         54,
        "title_font_size":      22,
        "heading1_font_size":   16,
        "heading2_font_size":   13,
        "body_font_size":       10.5,
        "body_line_spacing":    1.15,
        "cover_style":          "compact",
        "include_cover":        True,
        "include_title_page":   False,
        "include_toc":          True,
    },
    "SERMON": {
        "page_size":            "LETTER",
        "top_margin":           72,
        "bottom_margin":        72,
        "left_margin":          72,
        "right_margin":         72,
        "title_font_size":      24,
        "heading1_font_size":   18,
        "heading2_font_size":   14,
        "body_font_size":       12,
        "body_line_spacing":    1.3,
        "cover_style":          "sermon",
        "include_cover":        True,
        "include_title_page":   True,
        "include_toc":          False,
    },
    "TRAINING": {
        "page_size":            "LETTER",
        "top_margin":           72,
        "bottom_margin":        72,
        "left_margin":          72,
        "right_margin":         72,
        "title_font_size":      24,
        "heading1_font_size":   17,
        "heading2_font_size":   14,
        "body_font_size":       11,
        "body_line_spacing":    1.2,
        "cover_style":          "training",
        "include_cover":        True,
        "include_title_page":   True,
        "include_toc":          True,
    },
    "CONSULTING_REPORT": {
        "page_size":            "LETTER",
        "top_margin":           72,
        "bottom_margin":        72,
        "left_margin":          90,
        "right_margin":         90,
        "title_font_size":      22,
        "heading1_font_size":   16,
        "heading2_font_size":   13,
        "body_font_size":       10.5,
        "body_line_spacing":    1.15,
        "cover_style":          "professional",
        "include_cover":        True,
        "include_title_page":   True,
        "include_toc":          True,
    },
    "CORPORATE_REPORT": {
        "page_size":            "LETTER",
        "top_margin":           72,
        "bottom_margin":        72,
        "left_margin":          90,
        "right_margin":         90,
        "title_font_size":      22,
        "heading1_font_size":   16,
        "heading2_font_size":   13,
        "body_font_size":       10.5,
        "body_line_spacing":    1.15,
        "cover_style":          "corporate",
        "include_cover":        True,
        "include_title_page":   True,
        "include_toc":          True,
    },
    "PODCAST": {
        "page_size":            "LETTER",
        "top_margin":           72,
        "bottom_margin":        72,
        "left_margin":          72,
        "right_margin":         72,
        "title_font_size":      24,
        "heading1_font_size":   17,
        "heading2_font_size":   14,
        "body_font_size":       11,
        "body_line_spacing":    1.2,
        "cover_style":          "media",
        "include_cover":        True,
        "include_title_page":   False,
        "include_toc":          False,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Labels par langue
# ─────────────────────────────────────────────────────────────────────────────

_LANG_LABELS: dict[str, dict[str, str]] = {
    "fr": {
        "toc_title":     "Table des matières",
        "chapter_label": "Chapitre",
    },
    "en": {
        "toc_title":     "Table of Contents",
        "chapter_label": "Chapter",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée public
# ─────────────────────────────────────────────────────────────────────────────

def get_publication_theme(
    publication_mode: str,
    document_language: str = "en",
) -> dict:
    """
    Retourne les paramètres visuels à appliquer au DOCX et au PDF
    selon le mode de publication.

    Args:
        publication_mode:  Mode parmi VALID_MODES. Fallback sur DEFAULT_MODE.
        document_language: Code langue ("fr" ou "en"). Fallback sur "en".

    Returns:
        Dictionnaire de configuration du thème incluant :
          mode, page_size, marges, tailles de police, espacements,
          cover_style, include_*, toc_title, chapter_label.
    """
    mode = (publication_mode or "").strip().upper()
    if mode not in VALID_MODES:
        mode = DEFAULT_MODE

    lang = (document_language or "").strip().lower()
    if lang not in _LANG_LABELS:
        lang = "en"

    theme: dict = {"mode": mode}
    theme.update(_THEMES[mode])
    theme.update(_LANG_LABELS[lang])

    return theme
