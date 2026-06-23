"""
Constructeurs de prompts pour la génération d'images (image_engine).

Règle fondamentale :
  Aucun prompt ne demande à SDXL d'écrire du texte dans l'image.
  Titres, auteur, sous-titres et textes de couverture sont ajoutés
  ultérieurement avec ReportLab ou python-docx.

Style par défaut :
  Réalisme photographique éditorial, lumière naturelle, composition élégante,
  qualité d'impression professionnelle.
"""

from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────────────
# Style de base commun à toutes les images
# ──────────────────────────────────────────────────────────────────────────────

_BASE_STYLE = (
    "realistic editorial photography, natural light, elegant composition, "
    "professional book cover quality, credible real-world scene, "
    "subtle symbolism, clean background, premium publishing style, "
    "print-ready, no text, no logo, no watermark, no letters, no words"
)

# Styles thématiques prédéfinis
_THEME_STYLES: dict[str, str] = {
    "spiritual": (
        "soft diffused light, peaceful atmosphere, contemplative mood, "
        "warm golden tones, serene natural setting, depth of field"
    ),
    "professional": (
        "clean corporate aesthetic, neutral background, sharp focus, "
        "professional business photography, minimalist composition"
    ),
    "modern": (
        "contemporary design, geometric elements, clean lines, "
        "minimalist aesthetic, bold contrasts, architectural photography"
    ),
    "natural": (
        "nature photography, outdoor setting, natural textures, "
        "organic forms, environmental light, landscape photography"
    ),
    "educational": (
        "academic setting, learning environment, focused composition, "
        "warm institutional tones, professional educational photography"
    ),
    "editorial_realistic": (
        "high-end editorial photography, published book cover aesthetic, "
        "balanced composition, authentic textures, commercial printing quality"
    ),
}


# ──────────────────────────────────────────────────────────────────────────────
# Couverture avant
# ──────────────────────────────────────────────────────────────────────────────

def build_cover_prompt(
    title: str,
    subtitle: str | None = None,
    content_type: str | None = None,
    audience: str | None = None,
    theme_summary: str | None = None,
    style: str | None = None,
) -> str:
    """
    Construit un prompt pour la couverture avant d'un livre ou livret.

    Le prompt ne contient jamais de texte (titre, auteur, etc.) —
    ceux-ci sont ajoutés lors de la mise en page finale.

    Args:
        title:        Titre du document (utilisé pour déduire le thème visuel).
        subtitle:     Sous-titre optionnel (enrichit le contexte).
        content_type: Type de document (ex. "livre", "formation", "retraite").
        audience:     Public cible (ex. "professionnels", "étudiants").
        theme_summary: Résumé thématique court (quelques mots clés).
        style:        Clé de style (voir _THEME_STYLES). Si None, détection auto.

    Returns:
        Prompt textuel prêt à envoyer au provider SDXL.
    """
    parts: list[str] = []

    # ── Contexte visuel principal ──────────────────────────────────────────
    subject = _infer_visual_subject(
        title=title,
        subtitle=subtitle,
        content_type=content_type,
        theme_summary=theme_summary,
    )
    parts.append(subject)

    # ── Contexte public / usage ────────────────────────────────────────────
    if audience:
        parts.append(f"intended for {audience}")

    # ── Style visuel ──────────────────────────────────────────────────────
    resolved_style = style or _auto_detect_style(content_type, theme_summary)
    theme_style = _THEME_STYLES.get(resolved_style, _THEME_STYLES["editorial_realistic"])
    parts.append(theme_style)

    # ── Style de base ─────────────────────────────────────────────────────
    parts.append(_BASE_STYLE)

    return ", ".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# Illustration de chapitre
# ──────────────────────────────────────────────────────────────────────────────

def build_chapter_illustration_prompt(
    chapter_title: str,
    chapter_summary: str | None = None,
) -> str:
    """
    Construit un prompt pour une illustration de chapitre.

    Args:
        chapter_title:   Titre du chapitre.
        chapter_summary: Résumé ou idée principale du chapitre (optionnel).

    Returns:
        Prompt textuel pour le provider SDXL.
    """
    parts: list[str] = []

    subject = _infer_visual_subject(
        title=chapter_title,
        theme_summary=chapter_summary,
    )
    parts.append(subject)

    parts.append(
        "chapter illustration, editorial photography, "
        "documentary style, natural lighting, full-page spread"
    )
    parts.append(_BASE_STYLE)

    return ", ".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# Visuel de formation / présentation
# ──────────────────────────────────────────────────────────────────────────────

def build_training_visual_prompt(
    topic: str,
    audience: str | None = None,
) -> str:
    """
    Construit un prompt pour un visuel de formation ou de présentation.

    Args:
        topic:    Sujet ou thème de la formation.
        audience: Public cible (optionnel).

    Returns:
        Prompt textuel pour le provider SDXL.
    """
    parts: list[str] = []

    parts.append(
        f"visual representation of the topic: {_sanitize_for_prompt(topic)}"
    )

    if audience:
        parts.append(f"for {_sanitize_for_prompt(audience)}")

    parts.append(_THEME_STYLES["educational"])
    parts.append(_BASE_STYLE)

    return ", ".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# Quatrième de couverture
# ──────────────────────────────────────────────────────────────────────────────

def build_back_cover_prompt(
    title: str,
    theme_summary: str | None = None,
    style: str | None = None,
) -> str:
    """
    Construit un prompt pour la quatrième de couverture.

    Généralement plus épurée que la couverture avant : fond neutre,
    composition ouverte pour accueillir le texte de quatrième.

    Args:
        title:        Titre du document.
        theme_summary: Résumé thématique.
        style:        Clé de style visuel.

    Returns:
        Prompt textuel pour le provider SDXL.
    """
    parts: list[str] = []

    subject = _infer_visual_subject(title=title, theme_summary=theme_summary)
    parts.append(f"subtle background for back cover, {subject}")

    parts.append(
        "soft focus, desaturated background, open composition, "
        "plenty of empty space for text overlay, blurred bokeh background"
    )

    resolved_style = style or "editorial_realistic"
    theme_style = _THEME_STYLES.get(resolved_style, _THEME_STYLES["editorial_realistic"])
    parts.append(theme_style)
    parts.append(_BASE_STYLE)

    return ", ".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# Fonctions internes
# ──────────────────────────────────────────────────────────────────────────────

def _infer_visual_subject(
    title: str,
    subtitle: str | None = None,
    content_type: str | None = None,
    theme_summary: str | None = None,
) -> str:
    """
    Construit la description du sujet visuel à partir des métadonnées textuelles.

    Ne produit jamais de demande de texte dans l'image.
    """
    context_parts: list[str] = []

    if theme_summary:
        context_parts.append(_sanitize_for_prompt(theme_summary))
    elif title:
        context_parts.append(
            f"scene inspired by the theme: {_sanitize_for_prompt(title)}"
        )

    if subtitle and not theme_summary:
        context_parts.append(_sanitize_for_prompt(subtitle))

    if content_type:
        type_map = {
            "livre": "book cover scene",
            "livret": "booklet cover scene",
            "formation": "professional training environment",
            "enseignement": "educational setting",
            "conference": "conference or seminar atmosphere",
            "retraite": "retreat, contemplative peaceful setting",
            "rapport": "professional report, clean workspace",
            "reunion": "meeting or gathering scene",
        }
        mapped = type_map.get(content_type.lower(), "professional publication scene")
        context_parts.append(mapped)

    return ", ".join(context_parts) if context_parts else "professional editorial scene"


def _auto_detect_style(
    content_type: str | None,
    theme_summary: str | None,
) -> str:
    """Détecte automatiquement le style visuel selon le type de document."""
    if not content_type:
        return "editorial_realistic"

    ct = content_type.lower()
    style_map = {
        "retraite": "spiritual",
        "spirituel": "spiritual",
        "formation": "educational",
        "enseignement": "educational",
        "rapport": "professional",
        "reunion": "professional",
        "conference": "professional",
        "livre": "editorial_realistic",
        "livret": "editorial_realistic",
    }
    return style_map.get(ct, "editorial_realistic")


def _sanitize_for_prompt(text: str) -> str:
    """
    Nettoie un texte pour inclusion dans un prompt SDXL.

    - Tronque à 120 caractères pour éviter les prompts trop longs.
    - Supprime les caractères spéciaux potentiellement problématiques.
    """
    cleaned = text.strip().replace('"', "'").replace("\n", " ")
    if len(cleaned) > 120:
        cleaned = cleaned[:117] + "..."
    return cleaned
