"""
Cover Theme — Thèmes visuels professionnels pour PublishForge.

Définit les palettes de couleurs, familles typographiques, textures,
ornements et thèmes complets prêts à l'emploi.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────

class TextureType(str, Enum):
    SOLID       = "solid"
    PAPER       = "paper"
    GRAIN       = "grain"
    LINEN       = "linen"
    PARCHMENT   = "parchment"
    MODERN_DARK = "modern_dark"


class OrnamentType(str, Enum):
    NONE         = "none"
    THIN_LINE    = "thin_line"
    DOUBLE_LINE  = "double_line"
    CORNER_FRAME = "corner_frame"
    GEOMETRIC    = "geometric"


class FontFamily(str, Enum):
    SERIF_PREMIUM = "serif_premium"
    SANS_PREMIUM  = "sans_premium"
    MODERN        = "modern"


class CompositionModel(str, Enum):
    CLASSIC_BOOK      = "classic_book"
    MODERN_BOOK       = "modern_book"
    SPIRITUAL_BOOK    = "spiritual_book"
    TRAINING_MANUAL   = "training_manual"
    CONSULTING_REPORT = "consulting_report"
    MEDIA_STYLE       = "media_style"


# ─────────────────────────────────────────────────────────────────────────────
# Structures de données
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ColorPalette:
    """Palette de couleurs complète pour une couverture."""
    name:       str
    background: tuple[int, int, int]   # Fond principal
    primary:    tuple[int, int, int]   # Titre principal
    secondary:  tuple[int, int, int]   # Sous-titre
    accent:     tuple[int, int, int]   # Éléments décoratifs / filets
    muted:      tuple[int, int, int]   # Métadonnées discrètes
    surface:    tuple[int, int, int]   # Fond secondaire (bandes, blocs)


@dataclass
class TypographySpec:
    """Spécifications typographiques pour un niveau hiérarchique."""
    size_pt:  float         # Taille de base en points (PDF)
    weight:   str           # "regular" | "bold" | "light"
    italic:   bool  = False
    caps:     bool  = False  # Convertir en majuscules
    leading:  float = 1.30   # Interligne (× size_pt)
    tracking: float = 0.0    # Espacement lettres (em, 0 = normal)


@dataclass
class CoverTheme:
    """Thème visuel complet pour une couverture typographique."""
    name:          str
    composition:   CompositionModel
    palette:       ColorPalette
    font_family:   FontFamily
    texture:       TextureType
    ornament:      OrnamentType
    display_title: TypographySpec   # Très grand titre (impact)
    main_title:    TypographySpec   # Titre principal
    subtitle:      TypographySpec   # Complément du titre
    author:        TypographySpec   # Nom d'auteur
    metadata:      TypographySpec   # Informations secondaires
    collection:    TypographySpec   # Collection / type (très discret)
    margin_ratio:  float = 0.10     # Marge latérale relative à la largeur


# ─────────────────────────────────────────────────────────────────────────────
# Palettes professionnelles
# ─────────────────────────────────────────────────────────────────────────────

PALETTE_CLASSIC_PREMIUM = ColorPalette(
    name       = "classic_premium",
    background = (0x14, 0x14, 0x1E),   # Noir profond bleuté
    primary    = (0xF2, 0xE4, 0xC4),   # Crème chaude
    secondary  = (0xD4, 0xAF, 0x37),   # Or
    accent     = (0xD4, 0xAF, 0x37),   # Or
    muted      = (0x9A, 0x8A, 0x6A),   # Or discret
    surface    = (0x1C, 0x1C, 0x2A),   # Fond secondaire
)

PALETTE_SPIRITUAL = ColorPalette(
    name       = "spiritual",
    background = (0xFB, 0xF6, 0xEB),   # Ivoire chaud
    primary    = (0x2D, 0x1A, 0x00),   # Brun profond
    secondary  = (0x6B, 0x3A, 0x10),   # Brun doré
    accent     = (0xB8, 0x86, 0x0B),   # Or doux
    muted      = (0x88, 0x66, 0x44),   # Brun clair
    surface    = (0xF0, 0xE8, 0xD4),   # Parchemin
)

PALETTE_MODERN = ColorPalette(
    name       = "modern",
    background = (0xFF, 0xFF, 0xFF),   # Blanc pur
    primary    = (0x0A, 0x0A, 0x0A),   # Quasi-noir
    secondary  = (0x3A, 0x3A, 0x3A),   # Anthracite
    accent     = (0x00, 0x56, 0xE0),   # Bleu vif
    muted      = (0x6A, 0x6A, 0x6A),   # Gris moyen
    surface    = (0xF2, 0xF2, 0xF2),   # Gris clair
)

PALETTE_CORPORATE = ColorPalette(
    name       = "corporate",
    background = (0x0A, 0x18, 0x2C),   # Bleu nuit profond
    primary    = (0xFF, 0xFF, 0xFF),   # Blanc
    secondary  = (0xE8, 0xD8, 0x9A),   # Or pâle
    accent     = (0xC8, 0x9E, 0x1C),   # Or
    muted      = (0x80, 0x9C, 0xB8),   # Bleu gris
    surface    = (0x10, 0x22, 0x3C),   # Bleu nuit + clair
)

PALETTE_MEDIA = ColorPalette(
    name       = "media",
    background = (0x08, 0x08, 0x08),   # Noir
    primary    = (0xFF, 0xFF, 0xFF),   # Blanc
    secondary  = (0xCC, 0xCC, 0xCC),   # Gris clair
    accent     = (0xE8, 0x20, 0x20),   # Rouge vif
    muted      = (0x88, 0x88, 0x88),   # Gris
    surface    = (0x18, 0x18, 0x18),   # Noir + clair
)

PALETTE_TRAINING = ColorPalette(
    name       = "training",
    background = (0xF8, 0xF9, 0xFF),   # Blanc bleuté
    primary    = (0x0B, 0x21, 0x58),   # Bleu marine
    secondary  = (0x1C, 0x3E, 0xAA),   # Bleu moyen
    accent     = (0x1C, 0x3E, 0xAA),   # Bleu
    muted      = (0x44, 0x55, 0x88),   # Bleu gris
    surface    = (0xD8, 0xE4, 0xFF),   # Bleu très clair
)


# ─────────────────────────────────────────────────────────────────────────────
# Thèmes complets prêts à l'emploi
# ─────────────────────────────────────────────────────────────────────────────

THEME_CLASSIC_BOOK = CoverTheme(
    name          = "classic_book",
    composition   = CompositionModel.CLASSIC_BOOK,
    palette       = PALETTE_CLASSIC_PREMIUM,
    font_family   = FontFamily.SERIF_PREMIUM,
    texture       = TextureType.SOLID,
    ornament      = OrnamentType.DOUBLE_LINE,
    display_title = TypographySpec(size_pt=48, weight="bold",    leading=1.15),
    main_title    = TypographySpec(size_pt=42, weight="bold",    leading=1.18),
    subtitle      = TypographySpec(size_pt=20, weight="regular", italic=True, leading=1.35),
    author        = TypographySpec(size_pt=15, weight="regular", caps=True, tracking=0.18, leading=1.0),
    metadata      = TypographySpec(size_pt=11, weight="regular", leading=1.60),
    collection    = TypographySpec(size_pt=10, weight="light",   caps=True, tracking=0.22, leading=1.0),
    margin_ratio  = 0.12,
)

THEME_MODERN_BOOK = CoverTheme(
    name          = "modern_book",
    composition   = CompositionModel.MODERN_BOOK,
    palette       = PALETTE_MODERN,
    font_family   = FontFamily.SANS_PREMIUM,
    texture       = TextureType.SOLID,
    ornament      = OrnamentType.THIN_LINE,
    display_title = TypographySpec(size_pt=54, weight="bold",    leading=1.04),
    main_title    = TypographySpec(size_pt=46, weight="bold",    leading=1.06),
    subtitle      = TypographySpec(size_pt=20, weight="light",   leading=1.40),
    author        = TypographySpec(size_pt=14, weight="regular", tracking=0.08, leading=1.0),
    metadata      = TypographySpec(size_pt=11, weight="regular", leading=1.50),
    collection    = TypographySpec(size_pt=10, weight="light",   caps=True, tracking=0.14, leading=1.0),
    margin_ratio  = 0.09,
)

THEME_SPIRITUAL_BOOK = CoverTheme(
    name          = "spiritual_book",
    composition   = CompositionModel.SPIRITUAL_BOOK,
    palette       = PALETTE_SPIRITUAL,
    font_family   = FontFamily.SERIF_PREMIUM,
    texture       = TextureType.PARCHMENT,
    ornament      = OrnamentType.CORNER_FRAME,
    display_title = TypographySpec(size_pt=44, weight="bold",    leading=1.22),
    main_title    = TypographySpec(size_pt=38, weight="bold",    leading=1.25),
    subtitle      = TypographySpec(size_pt=18, weight="regular", italic=True, leading=1.40),
    author        = TypographySpec(size_pt=14, weight="regular", tracking=0.10, leading=1.0),
    metadata      = TypographySpec(size_pt=11, weight="regular", leading=1.60),
    collection    = TypographySpec(size_pt=10, weight="light",   italic=True, leading=1.0),
    margin_ratio  = 0.14,
)

THEME_TRAINING_MANUAL = CoverTheme(
    name          = "training_manual",
    composition   = CompositionModel.TRAINING_MANUAL,
    palette       = PALETTE_TRAINING,
    font_family   = FontFamily.SANS_PREMIUM,
    texture       = TextureType.SOLID,
    ornament      = OrnamentType.GEOMETRIC,
    display_title = TypographySpec(size_pt=40, weight="bold",    leading=1.15),
    main_title    = TypographySpec(size_pt=35, weight="bold",    leading=1.18),
    subtitle      = TypographySpec(size_pt=18, weight="regular", leading=1.36),
    author        = TypographySpec(size_pt=13, weight="regular", leading=1.0),
    metadata      = TypographySpec(size_pt=11, weight="regular", leading=1.50),
    collection    = TypographySpec(size_pt=11, weight="bold",    caps=True, tracking=0.10, leading=1.0),
    margin_ratio  = 0.10,
)

THEME_CONSULTING_REPORT = CoverTheme(
    name          = "consulting_report",
    composition   = CompositionModel.CONSULTING_REPORT,
    palette       = PALETTE_CORPORATE,
    font_family   = FontFamily.MODERN,
    texture       = TextureType.MODERN_DARK,
    ornament      = OrnamentType.THIN_LINE,
    display_title = TypographySpec(size_pt=42, weight="bold",    leading=1.10),
    main_title    = TypographySpec(size_pt=36, weight="bold",    leading=1.14),
    subtitle      = TypographySpec(size_pt=18, weight="light",   leading=1.42),
    author        = TypographySpec(size_pt=13, weight="regular", leading=1.0),
    metadata      = TypographySpec(size_pt=11, weight="regular", leading=1.50),
    collection    = TypographySpec(size_pt=10, weight="regular", caps=True, tracking=0.16, leading=1.0),
    margin_ratio  = 0.11,
)

THEME_MEDIA_STYLE = CoverTheme(
    name          = "media_style",
    composition   = CompositionModel.MEDIA_STYLE,
    palette       = PALETTE_MEDIA,
    font_family   = FontFamily.SANS_PREMIUM,
    texture       = TextureType.GRAIN,
    ornament      = OrnamentType.THIN_LINE,
    display_title = TypographySpec(size_pt=58, weight="bold",    leading=0.98),
    main_title    = TypographySpec(size_pt=50, weight="bold",    leading=1.02),
    subtitle      = TypographySpec(size_pt=20, weight="regular", leading=1.32),
    author        = TypographySpec(size_pt=14, weight="regular", caps=True, tracking=0.12, leading=1.0),
    metadata      = TypographySpec(size_pt=11, weight="regular", leading=1.50),
    collection    = TypographySpec(size_pt=10, weight="light",   caps=True, tracking=0.20, leading=1.0),
    margin_ratio  = 0.09,
)


# ─────────────────────────────────────────────────────────────────────────────
# Tables de correspondance style → thème
# ─────────────────────────────────────────────────────────────────────────────

_STYLE_TO_THEME: dict[str, CoverTheme] = {
    "classic":            THEME_CLASSIC_BOOK,
    "classic_book":       THEME_CLASSIC_BOOK,
    "compact":            THEME_MODERN_BOOK,
    "modern":             THEME_MODERN_BOOK,
    "modern_book":        THEME_MODERN_BOOK,
    "sermon":             THEME_SPIRITUAL_BOOK,
    "spiritual":          THEME_SPIRITUAL_BOOK,
    "spiritual_book":     THEME_SPIRITUAL_BOOK,
    "training":           THEME_TRAINING_MANUAL,
    "training_manual":    THEME_TRAINING_MANUAL,
    "professional":       THEME_CONSULTING_REPORT,
    "corporate":          THEME_CONSULTING_REPORT,
    "consulting":         THEME_CONSULTING_REPORT,
    "consulting_report":  THEME_CONSULTING_REPORT,
    "media":              THEME_MEDIA_STYLE,
    "media_style":        THEME_MEDIA_STYLE,
}

_MODE_TO_THEME: dict[str, CoverTheme] = {
    "BOOK":              THEME_CLASSIC_BOOK,
    "BOOKLET":           THEME_CLASSIC_BOOK,
    "SERMON":            THEME_SPIRITUAL_BOOK,
    "TRAINING":          THEME_TRAINING_MANUAL,
    "CONSULTING_REPORT": THEME_CONSULTING_REPORT,
    "CORPORATE_REPORT":  THEME_CONSULTING_REPORT,
    "PODCAST":           THEME_MEDIA_STYLE,
}


def get_theme(
    cover_style: str | None = None,
    publication_mode: str | None = None,
) -> CoverTheme:
    """
    Retourne le thème de couverture adapté au style ou au mode de publication.

    Priorité : cover_style > publication_mode > défaut (CLASSIC_BOOK).
    """
    if cover_style:
        key = cover_style.lower().strip()
        if key in _STYLE_TO_THEME:
            return _STYLE_TO_THEME[key]
    if publication_mode:
        key = publication_mode.upper().strip()
        if key in _MODE_TO_THEME:
            return _MODE_TO_THEME[key]
    return THEME_CLASSIC_BOOK
