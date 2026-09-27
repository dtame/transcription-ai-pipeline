"""
Cover Layout — Système de grille éditoriale pour PublishForge.

Divise la couverture en 8 zones de composition dont toutes les positions
découlent de la grille. Aucun placement arbitraire.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.cover_theme import CompositionModel


# ─────────────────────────────────────────────────────────────────────────────
# Zones de composition
# ─────────────────────────────────────────────────────────────────────────────

class Zone(str, Enum):
    BREATHING_TOP    = "breathing_top"     # Zone 1 — respiration supérieure
    MAIN_TITLE       = "main_title"        # Zone 2 — titre principal
    SUBTITLE         = "subtitle"          # Zone 3 — sous-titre
    ORNAMENT         = "ornament"          # Zone 4 — élément décoratif
    AUTHOR           = "author"            # Zone 5 — auteur
    ORGANIZATION     = "organization"      # Zone 6 — organisation
    SECONDARY_INFO   = "secondary_info"    # Zone 7 — informations secondaires
    BREATHING_BOTTOM = "breathing_bottom"  # Zone 8 — respiration inférieure


@dataclass
class ZoneBounds:
    """Limites absolues d'une zone. Origine : coin supérieur gauche (Y vers le bas)."""
    top:    float
    bottom: float
    left:   float
    right:  float

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2.0

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2.0

    @property
    def text_top(self) -> float:
        """Position Y de début de texte (légère marge interne)."""
        return self.top + self.height * 0.08


@dataclass
class CoverGrid:
    """Grille complète avec toutes les zones positionnées."""
    page_w:      float
    page_h:      float
    margin_h:    float
    zones:       dict[Zone, ZoneBounds]
    left_align:  bool = False   # True pour les compositions alignées à gauche

    def zone(self, z: Zone) -> ZoneBounds:
        return self.zones[z]


# ─────────────────────────────────────────────────────────────────────────────
# Ratios de grille par modèle de composition
# Format : Zone → (y_top_ratio, y_bottom_ratio)   [0.0 = haut, 1.0 = bas]
# ─────────────────────────────────────────────────────────────────────────────

_GRID_RATIOS: dict[CompositionModel, dict[Zone, tuple[float, float]]] = {

    CompositionModel.CLASSIC_BOOK: {
        Zone.BREATHING_TOP:    (0.000, 0.050),
        Zone.MAIN_TITLE:       (0.050, 0.450),
        Zone.SUBTITLE:         (0.450, 0.555),
        Zone.ORNAMENT:         (0.555, 0.600),
        Zone.AUTHOR:           (0.600, 0.670),
        Zone.ORGANIZATION:     (0.670, 0.730),
        Zone.SECONDARY_INFO:   (0.730, 0.880),
        Zone.BREATHING_BOTTOM: (0.880, 1.000),
    },

    CompositionModel.MODERN_BOOK: {
        Zone.BREATHING_TOP:    (0.000, 0.055),
        Zone.MAIN_TITLE:       (0.055, 0.440),
        Zone.SUBTITLE:         (0.440, 0.535),
        Zone.ORNAMENT:         (0.535, 0.565),
        Zone.AUTHOR:           (0.565, 0.635),
        Zone.ORGANIZATION:     (0.635, 0.695),
        Zone.SECONDARY_INFO:   (0.695, 0.855),
        Zone.BREATHING_BOTTOM: (0.855, 1.000),
    },

    CompositionModel.SPIRITUAL_BOOK: {
        Zone.BREATHING_TOP:    (0.000, 0.075),
        Zone.MAIN_TITLE:       (0.075, 0.455),
        Zone.SUBTITLE:         (0.455, 0.565),
        Zone.ORNAMENT:         (0.565, 0.618),
        Zone.AUTHOR:           (0.618, 0.692),
        Zone.ORGANIZATION:     (0.692, 0.755),
        Zone.SECONDARY_INFO:   (0.755, 0.888),
        Zone.BREATHING_BOTTOM: (0.888, 1.000),
    },

    CompositionModel.TRAINING_MANUAL: {
        Zone.BREATHING_TOP:    (0.000, 0.000),  # Remplacé par bande haut
        Zone.MAIN_TITLE:       (0.090, 0.410),
        Zone.SUBTITLE:         (0.410, 0.510),
        Zone.ORNAMENT:         (0.510, 0.548),
        Zone.AUTHOR:           (0.548, 0.618),
        Zone.ORGANIZATION:     (0.618, 0.678),
        Zone.SECONDARY_INFO:   (0.678, 0.840),
        Zone.BREATHING_BOTTOM: (0.840, 1.000),  # Remplacé par bande bas
    },

    CompositionModel.CONSULTING_REPORT: {
        Zone.BREATHING_TOP:    (0.000, 0.090),
        Zone.MAIN_TITLE:       (0.090, 0.465),
        Zone.SUBTITLE:         (0.465, 0.570),
        Zone.ORNAMENT:         (0.570, 0.608),
        Zone.AUTHOR:           (0.608, 0.678),
        Zone.ORGANIZATION:     (0.678, 0.742),
        Zone.SECONDARY_INFO:   (0.742, 0.880),
        Zone.BREATHING_BOTTOM: (0.880, 1.000),
    },

    CompositionModel.MEDIA_STYLE: {
        Zone.BREATHING_TOP:    (0.000, 0.000),  # Remplacé par bande accent
        Zone.MAIN_TITLE:       (0.060, 0.470),
        Zone.SUBTITLE:         (0.470, 0.560),
        Zone.ORNAMENT:         (0.560, 0.592),
        Zone.AUTHOR:           (0.592, 0.662),
        Zone.ORGANIZATION:     (0.662, 0.722),
        Zone.SECONDARY_INFO:   (0.722, 0.860),
        Zone.BREATHING_BOTTOM: (0.860, 1.000),
    },
}

# Compositions avec alignement à gauche (titre, auteur, etc.)
_LEFT_ALIGNED: set[CompositionModel] = {
    CompositionModel.MODERN_BOOK,
    CompositionModel.CONSULTING_REPORT,
}


def build_grid(
    page_w:        float,
    page_h:        float,
    margin_ratio:  float,
    composition:   CompositionModel,
) -> CoverGrid:
    """
    Construit la grille de composition pour une page donnée.

    Coordonnées : origine coin supérieur gauche, Y vers le bas.
    Le renderer PDF (ReportLab) effectue la conversion en bas-gauche.

    Args:
        page_w:       Largeur de page en points (ou pixels).
        page_h:       Hauteur de page en points (ou pixels).
        margin_ratio: Rapport marge / largeur de page.
        composition:  Modèle de composition souhaité.

    Returns:
        CoverGrid avec toutes les zones calculées.
    """
    ratios   = _GRID_RATIOS.get(composition, _GRID_RATIOS[CompositionModel.CLASSIC_BOOK])
    margin_h = page_w * margin_ratio
    is_left  = composition in _LEFT_ALIGNED

    zones: dict[Zone, ZoneBounds] = {}

    for zone, (y_top_r, y_bot_r) in ratios.items():
        top    = page_h * y_top_r
        bottom = page_h * y_bot_r

        # Les zones structurelles s'étendent sur toute la largeur
        if zone in (Zone.BREATHING_TOP, Zone.BREATHING_BOTTOM, Zone.ORNAMENT):
            left  = 0.0
            right = page_w
        else:
            left  = margin_h
            right = page_w - margin_h

        zones[zone] = ZoneBounds(top=top, bottom=bottom, left=left, right=right)

    return CoverGrid(
        page_w     = page_w,
        page_h     = page_h,
        margin_h   = margin_h,
        zones      = zones,
        left_align = is_left,
    )
