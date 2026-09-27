"""
Cover Composition — Modèles de mise en page et équilibre visuel pour PublishForge.

Résout le modèle de composition, analyse le contenu textuel,
ajuste les tailles typographiques pour préserver l'équilibre visuel.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.cover_theme import CompositionModel


# ─────────────────────────────────────────────────────────────────────────────
# Contexte de composition
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CompositionContext:
    """Données de composition finales, prêtes pour le rendu."""
    composition:    CompositionModel
    title:          str
    subtitle:       str
    author:         str
    organization:   str
    pub_date:       str
    pub_mode:       str
    doc_lang:       str
    # Facteurs de mise à l'échelle calculés par l'équilibre visuel
    title_scale:    float       = 1.0
    subtitle_scale: float       = 1.0
    # Lignes de texte après retour à la ligne
    title_lines:    list[str]   = field(default_factory=list)
    subtitle_lines: list[str]   = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Résolution du modèle de composition
# ─────────────────────────────────────────────────────────────────────────────

_STYLE_TO_COMPOSITION: dict[str, CompositionModel] = {
    "classic":            CompositionModel.CLASSIC_BOOK,
    "classic_book":       CompositionModel.CLASSIC_BOOK,
    "compact":            CompositionModel.MODERN_BOOK,
    "modern":             CompositionModel.MODERN_BOOK,
    "modern_book":        CompositionModel.MODERN_BOOK,
    "sermon":             CompositionModel.SPIRITUAL_BOOK,
    "spiritual":          CompositionModel.SPIRITUAL_BOOK,
    "spiritual_book":     CompositionModel.SPIRITUAL_BOOK,
    "training":           CompositionModel.TRAINING_MANUAL,
    "training_manual":    CompositionModel.TRAINING_MANUAL,
    "professional":       CompositionModel.CONSULTING_REPORT,
    "corporate":          CompositionModel.CONSULTING_REPORT,
    "consulting":         CompositionModel.CONSULTING_REPORT,
    "consulting_report":  CompositionModel.CONSULTING_REPORT,
    "media":              CompositionModel.MEDIA_STYLE,
    "media_style":        CompositionModel.MEDIA_STYLE,
}

_MODE_TO_COMPOSITION: dict[str, CompositionModel] = {
    "BOOK":              CompositionModel.CLASSIC_BOOK,
    "BOOKLET":           CompositionModel.CLASSIC_BOOK,
    "SERMON":            CompositionModel.SPIRITUAL_BOOK,
    "TRAINING":          CompositionModel.TRAINING_MANUAL,
    "CONSULTING_REPORT": CompositionModel.CONSULTING_REPORT,
    "CORPORATE_REPORT":  CompositionModel.CONSULTING_REPORT,
    "PODCAST":           CompositionModel.MEDIA_STYLE,
}


def resolve_composition_model(
    publication_mode: str | None,
    cover_style:      str | None,
) -> CompositionModel:
    """
    Détermine le modèle de composition à utiliser.

    Priorité : cover_style > publication_mode > CLASSIC_BOOK.
    """
    if cover_style:
        key = cover_style.lower().strip()
        if key in _STYLE_TO_COMPOSITION:
            return _STYLE_TO_COMPOSITION[key]
    if publication_mode:
        key = publication_mode.upper().strip()
        if key in _MODE_TO_COMPOSITION:
            return _MODE_TO_COMPOSITION[key]
    return CompositionModel.CLASSIC_BOOK


# ─────────────────────────────────────────────────────────────────────────────
# Équilibre visuel
# ─────────────────────────────────────────────────────────────────────────────

# Ratio approximatif largeur caractère / taille de police (Helvetica/sans-serif)
_CHAR_WIDTH_RATIO = 0.52


def _wrap_words(words: list[str], chars_per_line: float) -> list[str]:
    """Retour à la ligne par estimation de largeur (en caractères)."""
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        if len(candidate) <= chars_per_line:
            current = candidate
        else:
            if current:
                lines.append(current)
            # Mot plus long que la ligne → tronquer
            current = word[:max(int(chars_per_line), 4)]
    if current:
        lines.append(current)
    return lines or [""]


class VisualBalance:
    """
    Analyse le contenu textuel et calcule les paramètres typographiques
    nécessaires pour maintenir l'équilibre visuel de la composition.

    Règles appliquées :
    - Le titre principal ne doit pas dépasser 3 lignes.
    - Le sous-titre ne doit pas dépasser 2 lignes.
    - La taille est réduite progressivement jusqu'à respecter ces contraintes.
    - La réduction maximale est de 55 % de la taille de base.
    """

    _MAX_TITLE_LINES    = 3
    _MAX_SUBTITLE_LINES = 2
    _REDUCTION_STEPS    = (1.00, 0.92, 0.84, 0.76, 0.68, 0.62, 0.56)

    @classmethod
    def _measure_string_width(cls, text: str, font_name: str, size_pt: float) -> float:
        """Mesure la largeur réelle d'un texte via ReportLab si disponible."""
        try:
            from reportlab.pdfbase.pdfmetrics import stringWidth
            return stringWidth(text, font_name, size_pt)
        except Exception:
            return len(text) * size_pt * _CHAR_WIDTH_RATIO

    @classmethod
    def wrap_text(
        cls,
        text:            str,
        font_name:       str,
        font_size_pt:    float,
        available_width: float,
    ) -> list[str]:
        """
        Coupe le texte en lignes pour tenir dans la largeur disponible.

        Utilise la mesure réelle de ReportLab si disponible,
        sinon l'estimation par caractères.
        """
        if not text.strip():
            return []

        words = text.split()
        if not words:
            return []

        try:
            from reportlab.pdfbase.pdfmetrics import stringWidth
            lines: list[str] = []
            current = ""
            for word in words:
                candidate = f"{current} {word}".strip() if current else word
                if stringWidth(candidate, font_name, font_size_pt) <= available_width:
                    current = candidate
                else:
                    if current:
                        lines.append(current)
                    # Mot seul trop long → toujours sur sa propre ligne
                    current = word
            if current:
                lines.append(current)
            return lines or [""]
        except Exception:
            chars_per_line = max(available_width / (font_size_pt * _CHAR_WIDTH_RATIO), 6.0)
            return _wrap_words(words, chars_per_line)

    @classmethod
    def compute_scale(
        cls,
        text:            str,
        font_name:       str,
        base_size_pt:    float,
        available_width: float,
        max_lines:       int,
    ) -> float:
        """
        Calcule le facteur de réduction nécessaire pour que le texte
        ne dépasse pas `max_lines` lignes dans la largeur disponible.

        Retourne un facteur entre 0.56 et 1.0.
        """
        if not text.strip():
            return 1.0

        for scale in cls._REDUCTION_STEPS:
            lines = cls.wrap_text(
                text,
                font_name,
                base_size_pt * scale,
                available_width,
            )
            if len(lines) <= max_lines:
                return scale

        return cls._REDUCTION_STEPS[-1]

    @classmethod
    def build_context(
        cls,
        metadata:         dict,
        composition:      CompositionModel,
        title_size_pt:    float,
        subtitle_size_pt: float,
        available_width:  float,
        font_name_title:  str = "Helvetica-Bold",
        font_name_sub:    str = "Helvetica-Oblique",
    ) -> CompositionContext:
        """
        Construit le contexte de composition complet avec équilibre visuel appliqué.

        Args:
            metadata:         Métadonnées du projet (title, subtitle, author, …).
            composition:      Modèle de composition choisi.
            title_size_pt:    Taille de base du titre en points.
            subtitle_size_pt: Taille de base du sous-titre en points.
            available_width:  Largeur disponible pour le texte en points (ou pixels).
            font_name_title:  Nom de police ReportLab pour la mesure du titre.
            font_name_sub:    Nom de police ReportLab pour la mesure du sous-titre.

        Returns:
            CompositionContext avec title_lines, subtitle_lines et facteurs de scale.
        """
        title    = (metadata.get("title")            or "").strip()
        subtitle = (metadata.get("subtitle")         or "").strip()
        author   = (metadata.get("author")           or "").strip()
        org      = (metadata.get("organization")     or "").strip()
        pub_date = (metadata.get("publication_date") or "").strip()
        pub_mode = (metadata.get("publication_mode") or "BOOK").strip().upper()
        doc_lang = (metadata.get("document_language") or "fr").strip().lower()

        title_scale = cls.compute_scale(
            title, font_name_title, title_size_pt,
            available_width, cls._MAX_TITLE_LINES,
        )
        subtitle_scale = cls.compute_scale(
            subtitle, font_name_sub, subtitle_size_pt,
            available_width, cls._MAX_SUBTITLE_LINES,
        )

        title_lines = cls.wrap_text(
            title, font_name_title,
            title_size_pt * title_scale,
            available_width,
        )
        subtitle_lines = cls.wrap_text(
            subtitle, font_name_sub,
            subtitle_size_pt * subtitle_scale,
            available_width,
        )

        return CompositionContext(
            composition    = composition,
            title          = title,
            subtitle       = subtitle,
            author         = author,
            organization   = org,
            pub_date       = pub_date,
            pub_mode       = pub_mode,
            doc_lang       = doc_lang,
            title_scale    = title_scale,
            subtitle_scale = subtitle_scale,
            title_lines    = title_lines,
            subtitle_lines = subtitle_lines,
        )
