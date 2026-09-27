"""
Cover Renderer — Moteur de rendu typographique professionnel pour PublishForge.

Produit des couvertures PDF (ReportLab) et PNG (Pillow) de qualité éditoriale.
Aucune image externe, aucune API, fonctionne entièrement hors ligne.

Architecture :
    FontRegistry    — chargement et cache des polices TTF
    TextureEngine   — génération programmatique des textures de fond (PNG)
    CoverRenderer   — rendu PDF + PNG à partir du contexte de composition
"""

from __future__ import annotations

import os
import re
import math
from pathlib import Path
from typing import Optional

from app.cover_theme import (
    CoverTheme, ColorPalette, TypographySpec,
    CompositionModel, FontFamily, OrnamentType, TextureType,
)
from app.cover_layout import CoverGrid, Zone, ZoneBounds
from app.cover_composition import CompositionContext


# ─────────────────────────────────────────────────────────────────────────────
# Chemins de recherche de polices
# ─────────────────────────────────────────────────────────────────────────────

_FONT_DIRS: list[Path] = [
    Path(__file__).parent.parent / "fonts",
    Path("C:/Windows/Fonts"),
    Path("/usr/share/fonts/truetype"),
    Path("/usr/local/share/fonts"),
    Path(os.path.expanduser("~/.fonts")),
]

# Fichiers TTF par variante, par ordre de préférence
_FONT_FILES: dict[str, list[str]] = {
    "serif_bold": [
        "EBGaramond-Bold.ttf", "EBGaramond12-Bold.ttf",
        "CormorantGaramond-Bold.ttf", "CormorantGaramond-SemiBold.ttf",
        "georgiab.ttf", "Georgia Bold.ttf",
        "timesbd.ttf", "Times New Roman Bold.ttf",
    ],
    "serif_regular": [
        "EBGaramond-Regular.ttf", "EBGaramond12-Regular.ttf",
        "CormorantGaramond-Regular.ttf",
        "georgia.ttf", "Georgia.ttf",
        "times.ttf", "Times New Roman.ttf",
    ],
    "serif_italic": [
        "EBGaramond-Italic.ttf", "EBGaramond12-Italic.ttf",
        "CormorantGaramond-Italic.ttf",
        "georgiai.ttf", "Georgia Italic.ttf",
        "timesi.ttf", "Times New Roman Italic.ttf",
    ],
    "sans_bold": [
        "Montserrat-Bold.ttf", "Montserrat-ExtraBold.ttf",
        "SourceSansPro-Bold.ttf", "SourceSans3-Bold.ttf",
        "Lato-Bold.ttf",
        "segoeuib.ttf", "SegoeUI-Bold.ttf",
        "arialbd.ttf", "Arial Bold.ttf",
    ],
    "sans_regular": [
        "Montserrat-Regular.ttf",
        "SourceSansPro-Regular.ttf", "SourceSans3-Regular.ttf",
        "Lato-Regular.ttf",
        "segoeui.ttf", "SegoeUI.ttf",
        "arial.ttf", "Arial.ttf",
    ],
    "sans_italic": [
        "Montserrat-Italic.ttf",
        "SourceSansPro-Italic.ttf",
        "Lato-Italic.ttf",
        "segoeuii.ttf",
        "ariali.ttf",
    ],
    "sans_light": [
        "Montserrat-Light.ttf",
        "SourceSansPro-Light.ttf",
        "Lato-Light.ttf",
        "segoeuisl.ttf",
        "arial.ttf",
    ],
    "modern_bold": [
        "Manrope-Bold.ttf", "Manrope-ExtraBold.ttf",
        "Inter-Bold.ttf", "Inter-ExtraBold.ttf",
        "Calibri Bold.ttf", "calibrib.ttf",
        "segoeuib.ttf",
        "arialbd.ttf",
    ],
    "modern_regular": [
        "Manrope-Regular.ttf",
        "Inter-Regular.ttf",
        "calibri.ttf", "Calibri.ttf",
        "segoeui.ttf",
        "arial.ttf",
    ],
    "modern_light": [
        "Manrope-Light.ttf",
        "Inter-Light.ttf",
        "Calibri Light.ttf", "calibril.ttf",
        "segoeuisl.ttf",
        "arial.ttf",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Registre de polices
# ─────────────────────────────────────────────────────────────────────────────

class FontRegistry:
    """Cache et enregistrement centralisé des polices TTF pour ReportLab et Pillow."""

    _rl_registered: dict[str, str] = {}   # variant_key → rl_font_name
    _ttf_paths:     dict[str, Path] = {}  # variant_key → ttf_path

    @classmethod
    def _find_ttf(cls, filenames: list[str]) -> Path | None:
        for d in _FONT_DIRS:
            if not d.exists():
                continue
            for fn in filenames:
                p = d / fn
                if p.exists():
                    return p
        return None

    @classmethod
    def _variant_key(cls, family: FontFamily, weight: str, italic: bool) -> str:
        fam = family.value.split("_")[0]  # "serif", "sans", "modern"
        if weight == "light":
            w = "light"
        elif weight == "bold":
            w = "bold"
        else:
            w = "regular"
        return f"{fam}_{w}{'_italic' if italic and w == 'regular' else ''}"

    @classmethod
    def _register_rl(cls, rl_name: str, ttf_path: Path) -> bool:
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            pdfmetrics.registerFont(TTFont(rl_name, str(ttf_path)))
            return True
        except Exception:
            return False

    @classmethod
    def get_rl_font(
        cls,
        family: FontFamily,
        weight: str,
        italic: bool = False,
    ) -> str:
        """
        Retourne le nom de police ReportLab à utiliser.
        Enregistre la police TTF si disponible ; sinon utilise un built-in.
        """
        vk = cls._variant_key(family, weight, italic)

        if vk in cls._rl_registered:
            return cls._rl_registered[vk]

        fam   = family.value.split("_")[0]
        w     = "light" if weight == "light" else ("bold" if weight == "bold" else "regular")
        fkey  = f"{fam}_{w}" + ("_italic" if italic and w == "regular" else "")
        files = _FONT_FILES.get(fkey, _FONT_FILES.get(f"{fam}_regular", []))
        ttf   = cls._find_ttf(files)

        if ttf:
            safe  = re.sub(r"[^A-Za-z0-9_-]", "_", ttf.stem)
            rl_nm = f"PF_{safe}"
            if cls._register_rl(rl_nm, ttf):
                cls._rl_registered[vk] = rl_nm
                cls._ttf_paths[vk]     = ttf
                return rl_nm

        # Fallback polices built-in ReportLab
        fallback = _builtin_fallback(family, weight, italic)
        cls._rl_registered[vk] = fallback
        return fallback

    @classmethod
    def get_pil_font(
        cls,
        family: FontFamily,
        weight: str,
        size:   int,
        italic: bool = False,
    ):
        """Retourne une ImageFont Pillow pour la famille/poids/taille demandés."""
        try:
            from PIL import ImageFont
        except ImportError:
            return None

        vk  = cls._variant_key(family, weight, italic)
        ttf = cls._ttf_paths.get(vk)

        if not ttf:
            # Déclenche la résolution lazy
            cls.get_rl_font(family, weight, italic)
            ttf = cls._ttf_paths.get(vk)

        if ttf:
            try:
                return ImageFont.truetype(str(ttf), size)
            except (OSError, IOError):
                pass

        # Fallback polices système
        for fname in ["segoeui.ttf", "arial.ttf", "Arial.ttf", "DejaVuSans.ttf"]:
            fallback_ttf = FontRegistry._find_ttf([fname])
            if fallback_ttf:
                try:
                    return ImageFont.truetype(str(fallback_ttf), size)
                except (OSError, IOError):
                    pass

        try:
            return ImageFont.load_default(size=min(size, 40))  # Pillow ≥ 10
        except TypeError:
            return ImageFont.load_default()


def _builtin_fallback(family: FontFamily, weight: str, italic: bool) -> str:
    """Polices built-in ReportLab selon la famille demandée."""
    if family == FontFamily.SERIF_PREMIUM:
        if weight == "bold" and italic:
            return "Times-BoldItalic"
        if weight == "bold":
            return "Times-Bold"
        if italic:
            return "Times-Italic"
        return "Times-Roman"
    if weight == "bold" and italic:
        return "Helvetica-BoldOblique"
    if weight == "bold":
        return "Helvetica-Bold"
    if italic:
        return "Helvetica-Oblique"
    return "Helvetica"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers couleurs
# ─────────────────────────────────────────────────────────────────────────────

def _f(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """Convertit RGB 0-255 → 0.0-1.0 pour ReportLab."""
    return rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0


# ─────────────────────────────────────────────────────────────────────────────
# Moteur de textures PNG (Pillow)
# ─────────────────────────────────────────────────────────────────────────────

def _make_noise_tile(size: int, base: tuple[int, int, int], amplitude: int) -> "PIL.Image.Image":
    """Génère une tuile de bruit de couleur (sans numpy)."""
    from PIL import Image
    raw = bytearray(os.urandom(size * size))
    rgb = bytearray(size * size * 3)
    r0, g0, b0 = base
    for i, byte in enumerate(raw):
        d = int(byte) - 128
        d = int(d * amplitude / 128)
        rgb[i * 3]     = max(0, min(255, r0 + d))
        rgb[i * 3 + 1] = max(0, min(255, g0 + d))
        rgb[i * 3 + 2] = max(0, min(255, b0 + d))
    return Image.frombytes("RGB", (size, size), bytes(rgb))


def _tile(tile: "PIL.Image.Image", width: int, height: int) -> "PIL.Image.Image":
    """Tile une image sur toute la surface."""
    from PIL import Image
    tw, th = tile.size
    out = Image.new("RGB", (width, height))
    for y in range(0, height, th):
        for x in range(0, width, tw):
            out.paste(tile, (x, y))
    return out


def generate_texture(
    width:   int,
    height:  int,
    texture: TextureType,
    base:    tuple[int, int, int],
) -> "PIL.Image.Image":
    """Génère un fond texturé pour la couverture PNG."""
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        return None  # type: ignore

    img = Image.new("RGB", (width, height), base)

    if texture == TextureType.SOLID:
        return img

    if texture == TextureType.PAPER:
        tile = _make_noise_tile(128, base, 8)
        img  = _tile(tile, width, height)
        return img.filter(ImageFilter.GaussianBlur(radius=0.4))

    if texture == TextureType.GRAIN:
        tile = _make_noise_tile(96, base, 20)
        return _tile(tile, width, height)

    if texture == TextureType.LINEN:
        draw = ImageDraw.Draw(img)
        r0, g0, b0 = base
        dark  = (max(0, r0 - 14), max(0, g0 - 14), max(0, b0 - 14))
        light = (min(255, r0 + 9), min(255, g0 + 9), min(255, b0 + 9))
        for y in range(0, height, 4):
            draw.line([(0, y), (width, y)], fill=dark,  width=1)
        for x in range(0, width, 6):
            draw.line([(x, 0), (x, height)], fill=light, width=1)
        return img.filter(ImageFilter.GaussianBlur(radius=0.3))

    if texture == TextureType.PARCHMENT:
        # Bruit chaud
        r0, g0, b0 = base
        warm_base = (min(255, r0 + 4), g0, max(0, b0 - 4))
        tile = _make_noise_tile(128, warm_base, 10)
        img  = _tile(tile, width, height)
        img  = img.filter(ImageFilter.GaussianBlur(radius=0.6))
        # Vignette douce
        vignette = Image.new("L", (width, height), 0)
        vd = ImageDraw.Draw(vignette)
        steps = 60
        for i in range(steps):
            alpha = int(40 * (1.0 - i / steps))
            vd.rectangle([i * 2, i * 2, width - i * 2, height - i * 2], outline=alpha)
        vig_blur = vignette.filter(ImageFilter.GaussianBlur(radius=width // 5))
        # Appliquer : assombrit légèrement les bords
        from PIL import ImageChops
        dark_layer = Image.new("RGB", (width, height), (0, 0, 0))
        img = Image.composite(dark_layer, img, vig_blur)
        return img

    if texture == TextureType.MODERN_DARK:
        tile = _make_noise_tile(128, base, 5)
        img  = _tile(tile, width, height)
        return img.filter(ImageFilter.GaussianBlur(radius=1.2))

    return img


# ─────────────────────────────────────────────────────────────────────────────
# Rendu PDF — fonctions de dessin
# ─────────────────────────────────────────────────────────────────────────────

def _pdf_y(page_h: float, grid_y: float) -> float:
    """Convertit Y grille (haut=0) → Y ReportLab (bas=0)."""
    return page_h - grid_y


def _draw_text_block_pdf(
    c,
    lines:        list[str],
    font_name:    str,
    font_size:    float,
    leading:      float,
    color:        tuple[int, int, int],
    zone:         ZoneBounds,
    page_h:       float,
    align:        str = "center",  # "center" | "left"
    caps:         bool = False,
) -> float:
    """
    Dessine un bloc de texte multi-lignes dans une zone.
    Retourne le Y grille de la dernière ligne + leading (pour chaînage).
    """
    if not lines:
        return zone.top

    if caps:
        lines = [l.upper() for l in lines]

    n          = len(lines)
    line_h     = font_size * leading
    block_h    = n * line_h - (line_h - font_size)
    # Centre le bloc verticalement dans la zone
    y_start    = zone.top + (zone.height - block_h) / 2.0

    r, g, b = _f(color)
    c.setFillColorRGB(r, g, b)
    c.setFont(font_name, font_size)

    for i, line in enumerate(lines):
        grid_y  = y_start + i * line_h + font_size * 0.72  # approx cap height
        rl_y    = _pdf_y(page_h, grid_y)
        if align == "center":
            c.drawCentredString(zone.center_x, rl_y, line)
        else:
            c.drawString(zone.left, rl_y, line)

    return y_start + block_h


def _draw_single_line_pdf(
    c,
    text:      str,
    font_name: str,
    font_size: float,
    color:     tuple[int, int, int],
    grid_y:    float,
    zone:      ZoneBounds,
    page_h:    float,
    align:     str = "center",
    caps:      bool = False,
) -> None:
    """Dessine une ligne de texte à une position Y grille donnée."""
    if not text:
        return
    if caps:
        text = text.upper()
    rl_y = _pdf_y(page_h, grid_y)
    r, g, b = _f(color)
    c.setFillColorRGB(r, g, b)
    c.setFont(font_name, font_size)
    if align == "center":
        c.drawCentredString(zone.center_x, rl_y, text)
    else:
        c.drawString(zone.left, rl_y, text)


def _draw_horizontal_rule_pdf(
    c,
    cx:         float,
    grid_y:     float,
    page_h:     float,
    width:      float,
    color:      tuple[int, int, int],
    thickness:  float = 0.75,
) -> None:
    r, g, b = _f(color)
    c.setStrokeColorRGB(r, g, b)
    c.setLineWidth(thickness)
    rl_y = _pdf_y(page_h, grid_y)
    c.line(cx - width / 2, rl_y, cx + width / 2, rl_y)


def _draw_ornament_pdf(
    c,
    theme:  CoverTheme,
    grid:   CoverGrid,
    page_h: float,
) -> None:
    """Dessine l'ornement dans la zone ORNAMENT selon le type du thème."""
    zone    = grid.zone(Zone.ORNAMENT)
    palette = theme.palette
    cx      = zone.center_x
    cy_grid = zone.center_y
    cy_rl   = _pdf_y(page_h, cy_grid)
    avail_w = zone.width

    if theme.ornament == OrnamentType.THIN_LINE:
        _draw_horizontal_rule_pdf(c, cx, cy_grid, page_h, avail_w * 0.55,
                                  palette.accent, thickness=0.75)

    elif theme.ornament == OrnamentType.DOUBLE_LINE:
        gap = 5.0
        _draw_horizontal_rule_pdf(c, cx, cy_grid - gap / 2, page_h, avail_w * 0.50,
                                  palette.accent, thickness=0.75)
        _draw_horizontal_rule_pdf(c, cx, cy_grid + gap / 2, page_h, avail_w * 0.50,
                                  palette.accent, thickness=0.40)

    elif theme.ornament == OrnamentType.GEOMETRIC:
        # Ligne avec cercle central et points terminaux
        rw = avail_w * 0.42
        r, g, b = _f(palette.accent)
        c.setStrokeColorRGB(r, g, b)
        c.setFillColorRGB(r, g, b)
        c.setLineWidth(1.0)
        c.line(cx - rw, cy_rl, cx - 9, cy_rl)
        c.line(cx + 9, cy_rl, cx + rw, cy_rl)
        c.circle(cx, cy_rl, 4, fill=1, stroke=0)
        c.circle(cx - rw, cy_rl, 2.5, fill=1, stroke=0)
        c.circle(cx + rw, cy_rl, 2.5, fill=1, stroke=0)

    elif theme.ornament == OrnamentType.CORNER_FRAME:
        # Traité séparément (pleine page) via _draw_corner_frame_pdf
        pass


def _draw_corner_frame_pdf(
    c,
    theme:  CoverTheme,
    grid:   CoverGrid,
    page_h: float,
) -> None:
    """Dessine un encadrement de coins élégant sur toute la page."""
    if theme.ornament != OrnamentType.CORNER_FRAME:
        return
    m   = grid.margin_h * 0.65
    pw  = grid.page_w
    ph  = grid.page_h
    seg = pw * 0.09

    r, g, b = _f(theme.palette.accent)
    c.setStrokeColorRGB(r, g, b)
    c.setLineWidth(0.80)

    # Coin sup-gauche
    rl_top = _pdf_y(ph, m)
    c.line(m, rl_top, m + seg, rl_top)
    c.line(m, rl_top, m, rl_top - seg)

    # Coin sup-droit
    c.line(pw - m - seg, rl_top, pw - m, rl_top)
    c.line(pw - m, rl_top, pw - m, rl_top - seg)

    # Coin inf-gauche
    rl_bot = _pdf_y(ph, ph - m)
    c.line(m, rl_bot, m + seg, rl_bot)
    c.line(m, rl_bot, m, rl_bot + seg)

    # Coin inf-droit
    c.line(pw - m - seg, rl_bot, pw - m, rl_bot)
    c.line(pw - m, rl_bot, pw - m, rl_bot + seg)


def _draw_background_pdf(
    c,
    page_w: float,
    page_h: float,
    color:  tuple[int, int, int],
    texture: TextureType,
) -> None:
    """Dessine le fond de la couverture."""
    r, g, b = _f(color)
    c.setFillColorRGB(r, g, b)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # Pour MODERN_DARK : légère variation luminosité au centre
    if texture == TextureType.MODERN_DARK:
        r0, g0, b0 = color
        for i in range(12):
            shade = i * 0.006
            ri = min(1.0, r0 / 255 + shade)
            gi = min(1.0, g0 / 255 + shade)
            bi = min(1.0, b0 / 255 + shade)
            c.setFillColorRGB(ri, gi, bi)
            band_h = page_h * 0.08
            cy     = page_h * 0.35
            c.ellipse(
                page_w * 0.1 - i * page_w * 0.05,
                cy - band_h * (i + 1),
                page_w * 0.9 + i * page_w * 0.05,
                cy + band_h * (i + 1),
                fill=1, stroke=0,
            )
        # Redessiner fond plein pour que la texture reste subtile
        c.setFillColorRGB(r, g, b)
        c.setFillAlpha(0.55)
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
        c.setFillAlpha(1.0)


def _draw_top_band_pdf(
    c,
    page_w:    float,
    page_h:    float,
    height:    float,
    color:     tuple[int, int, int],
    text:      str    = "",
    text_color: tuple[int, int, int] = (255, 255, 255),
    font_name: str    = "Helvetica-Bold",
    font_size: float  = 11.0,
) -> None:
    """Dessine une bande pleine en haut de la page (ex : catégorie formation)."""
    r, g, b = _f(color)
    c.setFillColorRGB(r, g, b)
    c.rect(0, page_h - height, page_w, height, fill=1, stroke=0)
    if text:
        tr, tg, tb = _f(text_color)
        c.setFillColorRGB(tr, tg, tb)
        c.setFont(font_name, font_size)
        c.drawCentredString(page_w / 2, page_h - height / 2 - font_size * 0.35, text.upper())


def _draw_bottom_band_pdf(
    c,
    page_w:    float,
    page_h:    float,
    height:    float,
    color:     tuple[int, int, int],
    text:      str    = "",
    text_color: tuple[int, int, int] = (255, 255, 255),
    font_name: str    = "Helvetica",
    font_size: float  = 10.0,
) -> None:
    """Dessine une bande pleine en bas de la page."""
    r, g, b = _f(color)
    c.setFillColorRGB(r, g, b)
    c.rect(0, 0, page_w, height, fill=1, stroke=0)
    if text:
        tr, tg, tb = _f(text_color)
        c.setFillColorRGB(tr, tg, tb)
        c.setFont(font_name, font_size)
        c.drawCentredString(page_w / 2, height / 2 - font_size * 0.35, text.upper())


def _draw_left_accent_bar_pdf(
    c,
    page_h: float,
    color:  tuple[int, int, int],
    width:  float = 4.0,
) -> None:
    """Dessine une barre verticale d'accent sur le bord gauche (MODERN_BOOK)."""
    r, g, b = _f(color)
    c.setFillColorRGB(r, g, b)
    c.rect(0, 0, width, page_h, fill=1, stroke=0)


def _draw_thin_accent_line_pdf(
    c,
    page_w:  float,
    page_h:  float,
    y_ratio: float,
    color:   tuple[int, int, int],
    height:  float = 2.0,
) -> None:
    """Dessine un filet pleine largeur à une position relative."""
    r, g, b = _f(color)
    c.setFillColorRGB(r, g, b)
    rl_y = _pdf_y(page_h, page_h * y_ratio)
    c.rect(0, rl_y, page_w, height, fill=1, stroke=0)


def _draw_consulting_header_pdf(
    c,
    page_w:  float,
    page_h:  float,
    palette: ColorPalette,
) -> None:
    """Élément géométrique coin sup-droit pour CONSULTING_REPORT."""
    r, g, b = _f(palette.accent)
    c.setStrokeColorRGB(r, g, b)
    c.setLineWidth(1.0)
    size = page_w * 0.22
    x0   = page_w - size
    y0   = page_h  # rl Y = 0 pour grid_y = page_h
    # Mais en ReportLab, le coin sup-droit est (page_w, page_h)
    # On dessine depuis le coin sup-droit
    c.line(page_w, page_h, page_w - size, page_h)          # ligne horizontale
    c.line(page_w, page_h, page_w, page_h - size * 0.7)    # ligne verticale
    c.setLineWidth(0.5)
    c.line(page_w - size * 0.3, page_h, page_w, page_h - size * 0.5)  # diagonale


# ─────────────────────────────────────────────────────────────────────────────
# Rendu PNG — fonctions de dessin Pillow
# ─────────────────────────────────────────────────────────────────────────────

def _pil_center_text(draw, text, font, zone_x, zone_w, y, color):
    """Centre le texte horizontalement dans une zone."""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw   = bbox[2] - bbox[0]
    except AttributeError:
        tw = len(text) * font.size // 2  # fallback old Pillow
    x = zone_x + (zone_w - tw) // 2
    draw.text((x, y), text, fill=color, font=font)


def _pil_draw_text_block(draw, lines, font, color, zone, align="center"):
    """Dessine un bloc de texte centré (vertical) dans une zone."""
    if not lines:
        return 0

    try:
        sample_bbox = draw.textbbox((0, 0), lines[0], font=font)
        line_h = int((sample_bbox[3] - sample_bbox[1]) * 1.35)
    except AttributeError:
        line_h = int(getattr(font, "size", 20) * 1.35)

    total_h = len(lines) * line_h
    y_start = int(zone.top + (zone.height - total_h) / 2)

    for i, line in enumerate(lines):
        y = y_start + i * line_h
        if align == "center":
            _pil_center_text(draw, line, font, zone.left, zone.width, y, color)
        else:
            draw.text((int(zone.left), y), line, fill=color, font=font)

    return y_start + total_h


def _pil_draw_rule(draw, cx, y, width, color, thickness=3):
    """Dessine un filet horizontal centré."""
    x0 = int(cx - width / 2)
    x1 = int(cx + width / 2)
    draw.line([(x0, y), (x1, y)], fill=color, width=thickness)


def _pil_draw_ornament(draw, theme, grid, scale=1.0):
    """Dessine l'ornement dans la zone ORNAMENT (Pillow)."""
    zone = grid.zone(Zone.ORNAMENT)
    cx   = int(zone.center_x)
    cy   = int(zone.center_y)
    rw   = int(zone.width * 0.46)
    col  = theme.palette.accent

    if theme.ornament == OrnamentType.THIN_LINE:
        _pil_draw_rule(draw, cx, cy, zone.width * 0.55, col, int(2 * scale))

    elif theme.ornament == OrnamentType.DOUBLE_LINE:
        gap = int(5 * scale)
        _pil_draw_rule(draw, cx, cy - gap, zone.width * 0.50, col, int(2 * scale))
        _pil_draw_rule(draw, cx, cy + gap, zone.width * 0.50, col, int(1 * scale))

    elif theme.ornament == OrnamentType.GEOMETRIC:
        th = max(2, int(2 * scale))
        draw.line([(cx - rw, cy), (cx - int(10 * scale), cy)], fill=col, width=th)
        draw.line([(cx + int(10 * scale), cy), (cx + rw, cy)], fill=col, width=th)
        r = int(5 * scale)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
        r2 = int(3 * scale)
        draw.ellipse([cx - rw - r2, cy - r2, cx - rw + r2, cy + r2], fill=col)
        draw.ellipse([cx + rw - r2, cy - r2, cx + rw + r2, cy + r2], fill=col)

    elif theme.ornament == OrnamentType.CORNER_FRAME:
        m   = int(grid.margin_h * 0.65)
        pw  = int(grid.page_w)
        ph  = int(grid.page_h)
        seg = int(pw * 0.09)
        th  = max(1, int(1.5 * scale))
        col = theme.palette.accent
        # Coins
        draw.line([(m, m), (m + seg, m)], fill=col, width=th)
        draw.line([(m, m), (m, m + seg)], fill=col, width=th)
        draw.line([(pw - m - seg, m), (pw - m, m)], fill=col, width=th)
        draw.line([(pw - m, m), (pw - m, m + seg)], fill=col, width=th)
        draw.line([(m, ph - m), (m + seg, ph - m)], fill=col, width=th)
        draw.line([(m, ph - m - seg), (m, ph - m)], fill=col, width=th)
        draw.line([(pw - m - seg, ph - m), (pw - m, ph - m)], fill=col, width=th)
        draw.line([(pw - m, ph - m - seg), (pw - m, ph - m)], fill=col, width=th)


# ─────────────────────────────────────────────────────────────────────────────
# Labels multilingues
# ─────────────────────────────────────────────────────────────────────────────

_LABELS: dict[str, dict] = {
    "fr": {
        "author":  "Auteur",
        "org":     "Organisation",
        "date":    "",
        "mode_names": {
            "BOOK":              "Livre",
            "BOOKLET":           "Livret",
            "SERMON":            "Prédication",
            "TRAINING":          "Formation",
            "CONSULTING_REPORT": "Rapport conseil",
            "CORPORATE_REPORT":  "Rapport d'entreprise",
            "PODCAST":           "Podcast",
        },
    },
    "en": {
        "author":  "Author",
        "org":     "Organization",
        "date":    "",
        "mode_names": {
            "BOOK":              "Book",
            "BOOKLET":           "Booklet",
            "SERMON":            "Sermon",
            "TRAINING":          "Training",
            "CONSULTING_REPORT": "Consulting Report",
            "CORPORATE_REPORT":  "Corporate Report",
            "PODCAST":           "Podcast",
        },
    },
}


def _get_labels(lang: str) -> dict:
    return _LABELS.get(lang.lower()[:2], _LABELS["fr"])


def _mode_label(pub_mode: str, labels: dict) -> str:
    return labels["mode_names"].get(pub_mode, "")


# ─────────────────────────────────────────────────────────────────────────────
# Rendu PDF principal
# ─────────────────────────────────────────────────────────────────────────────

def render_pdf(
    output_path: Path,
    ctx:         CompositionContext,
    theme:       CoverTheme,
    grid:        CoverGrid,
    page_size:   tuple[float, float],  # (width_pt, height_pt)
) -> None:
    """
    Génère la couverture au format PDF.

    Args:
        output_path: Chemin de sortie du fichier PDF.
        ctx:         Contexte de composition (textes, lignes calculées).
        theme:       Thème visuel (palette, typo, ornements).
        grid:        Grille de composition (zones positionnées).
        page_size:   Dimensions de la page en points (largeur, hauteur).
    """
    from reportlab.pdfgen import canvas as rl_canvas

    page_w, page_h = page_size
    palette  = theme.palette
    comp     = theme.composition
    labels   = _get_labels(ctx.doc_lang)
    align    = "left" if grid.left_align else "center"

    # Résolution des polices
    fn_title_bold  = FontRegistry.get_rl_font(theme.font_family, "bold")
    fn_title_reg   = FontRegistry.get_rl_font(theme.font_family, "regular")
    fn_subtitle    = FontRegistry.get_rl_font(theme.font_family, "regular", italic=True)
    fn_meta        = FontRegistry.get_rl_font(theme.font_family, "regular")
    fn_light       = FontRegistry.get_rl_font(theme.font_family, "light")

    # Tailles adaptées à la résolution
    ts = theme.main_title
    ss = theme.subtitle
    aus = theme.author
    ms  = theme.metadata
    cs  = theme.collection

    title_size    = ts.size_pt * ctx.title_scale
    subtitle_size = ss.size_pt * ctx.subtitle_scale
    author_size   = aus.size_pt
    meta_size     = ms.size_pt
    coll_size     = cs.size_pt

    c = rl_canvas.Canvas(str(output_path), pagesize=(page_w, page_h))
    c.setTitle(ctx.title or "Cover")
    c.setAuthor(ctx.author or "PublishForge")

    # ── Fond ────────────────────────────────────────────────────────────────
    _draw_background_pdf(c, page_w, page_h, palette.background, theme.texture)

    # ── Éléments spécifiques à la composition ──────────────────────────────

    if comp == CompositionModel.CLASSIC_BOOK:
        # Filet accent supérieur
        _draw_thin_accent_line_pdf(c, page_w, page_h, 0.003, palette.accent, height=3.0)
        # Filet accent inférieur
        _draw_thin_accent_line_pdf(c, page_w, page_h, 0.992, palette.accent, height=4.0)

    elif comp == CompositionModel.MODERN_BOOK:
        # Barre verticale gauche
        _draw_left_accent_bar_pdf(c, page_h, palette.accent, width=4.5)

    elif comp == CompositionModel.TRAINING_MANUAL:
        # Bande top avec label de catégorie
        mode_label = _mode_label(ctx.pub_mode, labels)
        fn_coll = FontRegistry.get_rl_font(theme.font_family, "bold")
        _draw_top_band_pdf(
            c, page_w, page_h,
            height=page_h * 0.09,
            color=palette.accent,
            text=mode_label or "Formation",
            text_color=(255, 255, 255),
            font_name=fn_coll,
            font_size=coll_size * 1.1,
        )
        # Bande bas avec organisation
        _draw_bottom_band_pdf(
            c, page_w, page_h,
            height=page_h * 0.075,
            color=palette.accent,
            text=ctx.organization or "",
            text_color=(255, 255, 255),
            font_name=fn_meta,
            font_size=meta_size,
        )

    elif comp == CompositionModel.MEDIA_STYLE:
        # Bande rouge en haut
        _draw_top_band_pdf(
            c, page_w, page_h,
            height=page_h * 0.055,
            color=palette.accent,
        )

    elif comp == CompositionModel.CONSULTING_REPORT:
        # Élément géométrique coin supérieur droit
        _draw_consulting_header_pdf(c, page_w, page_h, palette)
        # Filet gold fin en haut
        _draw_thin_accent_line_pdf(c, page_w, page_h, 0.09, palette.accent, height=0.75)
        # Filet gold fin en bas
        _draw_thin_accent_line_pdf(c, page_w, page_h, 0.91, palette.accent, height=0.75)

    elif comp == CompositionModel.SPIRITUAL_BOOK:
        # Encadrement de coins
        _draw_corner_frame_pdf(c, theme, grid, page_h)

    # ── Titre ────────────────────────────────────────────────────────────────
    title_zone = grid.zone(Zone.MAIN_TITLE)
    _draw_text_block_pdf(
        c, ctx.title_lines,
        fn_title_bold, title_size,
        ts.leading,
        palette.primary,
        title_zone, page_h, align,
    )

    # ── Sous-titre ────────────────────────────────────────────────────────────
    if ctx.subtitle_lines:
        sub_zone = grid.zone(Zone.SUBTITLE)
        sub_fn   = fn_subtitle if ss.italic else fn_title_reg
        _draw_text_block_pdf(
            c, ctx.subtitle_lines,
            sub_fn, subtitle_size,
            ss.leading,
            palette.secondary,
            sub_zone, page_h, align,
        )

    # ── Ornement ────────────────────────────────────────────────────────────
    _draw_ornament_pdf(c, theme, grid, page_h)

    # ── Auteur ────────────────────────────────────────────────────────────────
    if ctx.author:
        author_zone = grid.zone(Zone.AUTHOR)
        author_text = ctx.author.upper() if aus.caps else ctx.author
        grid_y_author = author_zone.top + author_zone.height * 0.55 + author_size * 0.35
        _draw_single_line_pdf(
            c, author_text,
            fn_title_reg, author_size,
            palette.secondary,
            grid_y_author, author_zone, page_h, align,
        )

    # ── Organisation ─────────────────────────────────────────────────────────
    if ctx.organization and comp not in (
        CompositionModel.TRAINING_MANUAL,
    ):
        org_zone  = grid.zone(Zone.ORGANIZATION)
        grid_y_org = org_zone.top + org_zone.height * 0.55 + meta_size * 0.35
        _draw_single_line_pdf(
            c, ctx.organization,
            fn_meta, meta_size,
            palette.muted,
            grid_y_org, org_zone, page_h, align,
        )

    # ── Informations secondaires ──────────────────────────────────────────────
    if comp not in (CompositionModel.TRAINING_MANUAL,):
        sec_zone  = grid.zone(Zone.SECONDARY_INFO)
        sec_lines = []
        mode_name = _mode_label(ctx.pub_mode, labels)
        if mode_name:
            sec_lines.append(mode_name)
        if ctx.pub_date:
            sec_lines.append(ctx.pub_date)

        if sec_lines:
            line_spacing = meta_size * ms.leading
            total_h = len(sec_lines) * line_spacing
            y_start = sec_zone.top + (sec_zone.height - total_h) / 2
            for i, line in enumerate(sec_lines):
                grid_y = y_start + i * line_spacing + meta_size * 0.72
                _draw_single_line_pdf(
                    c, line, fn_meta, meta_size,
                    palette.muted,
                    grid_y, sec_zone, page_h, align,
                )

    c.save()


# ─────────────────────────────────────────────────────────────────────────────
# Rendu PNG principal
# ─────────────────────────────────────────────────────────────────────────────

def render_png(
    output_path: Path,
    ctx:         CompositionContext,
    theme:       CoverTheme,
    grid:        CoverGrid,
    width:       int = 1240,
    height:      int = 1754,
) -> bool:
    """
    Génère la couverture au format PNG.

    Returns:
        True si la génération a réussi, False si Pillow n'est pas disponible.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False

    try:
        palette  = theme.palette
        comp     = theme.composition
        labels   = _get_labels(ctx.doc_lang)
        align    = "left" if grid.left_align else "center"
        scale    = width / 595.27  # rapport px/pt (A4 = 595.27 pt)

        # Tailles adaptées à la résolution PNG
        title_sz    = max(int(theme.main_title.size_pt    * ctx.title_scale    * scale), 20)
        subtitle_sz = max(int(theme.subtitle.size_pt      * ctx.subtitle_scale * scale), 14)
        author_sz   = max(int(theme.author.size_pt                             * scale), 12)
        meta_sz     = max(int(theme.metadata.size_pt                           * scale), 10)
        coll_sz     = max(int(theme.collection.size_pt                         * scale), 10)

        # Fond texturé
        img = generate_texture(width, height, theme.texture, palette.background)
        if img is None:
            img = Image.new("RGB", (width, height), palette.background)
        draw = ImageDraw.Draw(img)

        # Polices
        ff = theme.font_family
        font_title    = FontRegistry.get_pil_font(ff, "bold",    title_sz)
        font_subtitle = FontRegistry.get_pil_font(ff, "regular", subtitle_sz, italic=True)
        font_author   = FontRegistry.get_pil_font(ff, "regular", author_sz)
        font_meta     = FontRegistry.get_pil_font(ff, "regular", meta_sz)
        font_coll     = FontRegistry.get_pil_font(ff, "bold",    coll_sz)

        # ── Éléments structurels ─────────────────────────────────────────────

        if comp == CompositionModel.CLASSIC_BOOK:
            # Filets accent haut / bas
            draw.rectangle([(0, 0), (width, max(3, int(4 * scale)))],
                           fill=palette.accent)
            draw.rectangle([(0, height - max(4, int(5 * scale))), (width, height)],
                           fill=palette.accent)

        elif comp == CompositionModel.MODERN_BOOK:
            bar_w = max(4, int(5 * scale))
            draw.rectangle([(0, 0), (bar_w, height)], fill=palette.accent)

        elif comp == CompositionModel.TRAINING_MANUAL:
            band_h = int(height * 0.09)
            draw.rectangle([(0, 0), (width, band_h)], fill=palette.accent)
            mode_name = _mode_label(ctx.pub_mode, labels)
            if mode_name and font_coll:
                _pil_center_text(draw, mode_name.upper(), font_coll,
                                 0, width, int(band_h / 2 - coll_sz * 0.5),
                                 (255, 255, 255))
            bot_band_h = int(height * 0.075)
            draw.rectangle([(0, height - bot_band_h), (width, height)], fill=palette.accent)
            if ctx.organization and font_meta:
                _pil_center_text(draw, ctx.organization, font_meta,
                                 0, width, int(height - bot_band_h + (bot_band_h - meta_sz) // 2),
                                 (255, 255, 255))

        elif comp == CompositionModel.MEDIA_STYLE:
            band_h = int(height * 0.055)
            draw.rectangle([(0, 0), (width, band_h)], fill=palette.accent)

        elif comp == CompositionModel.CONSULTING_REPORT:
            # Filets fins haut et bas
            th = max(1, int(scale))
            y_top = int(height * 0.09)
            y_bot = int(height * 0.91)
            draw.line([(0, y_top), (width, y_top)], fill=palette.accent, width=th)
            draw.line([(0, y_bot), (width, y_bot)], fill=palette.accent, width=th)
            # Élément géométrique coin sup-droit
            size = int(width * 0.22)
            th2  = max(1, int(1.5 * scale))
            draw.line([(width - size, 0), (width, 0)], fill=palette.accent, width=th2)
            draw.line([(width, 0), (width, int(size * 0.7))], fill=palette.accent, width=th2)

        elif comp == CompositionModel.SPIRITUAL_BOOK:
            _pil_draw_ornament(draw, theme, grid, scale)

        # ── Titre ─────────────────────────────────────────────────────────────
        title_zone = grid.zone(Zone.MAIN_TITLE)
        if ctx.title_lines and font_title:
            font_t = FontRegistry.get_pil_font(ff, "bold", title_sz)
            _pil_draw_text_block(draw, ctx.title_lines, font_t,
                                 palette.primary, title_zone, align)

        # ── Sous-titre ─────────────────────────────────────────────────────────
        if ctx.subtitle_lines and font_subtitle:
            _pil_draw_text_block(draw, ctx.subtitle_lines, font_subtitle,
                                 palette.secondary, grid.zone(Zone.SUBTITLE), align)

        # ── Ornement ─────────────────────────────────────────────────────────
        if comp != CompositionModel.SPIRITUAL_BOOK:
            _pil_draw_ornament(draw, theme, grid, scale)

        # ── Auteur ────────────────────────────────────────────────────────────
        if ctx.author and font_author:
            author_zone  = grid.zone(Zone.AUTHOR)
            author_text  = ctx.author.upper() if theme.author.caps else ctx.author
            grid_y_a     = int(author_zone.top + author_zone.height * 0.5)
            if align == "center":
                _pil_center_text(draw, author_text, font_author,
                                 int(author_zone.left), int(author_zone.width),
                                 grid_y_a, palette.secondary)
            else:
                draw.text((int(author_zone.left), grid_y_a), author_text,
                          fill=palette.secondary, font=font_author)

        # ── Organisation ─────────────────────────────────────────────────────
        if ctx.organization and font_meta and comp not in (CompositionModel.TRAINING_MANUAL,):
            org_zone  = grid.zone(Zone.ORGANIZATION)
            grid_y_o  = int(org_zone.top + org_zone.height * 0.5)
            if align == "center":
                _pil_center_text(draw, ctx.organization, font_meta,
                                 int(org_zone.left), int(org_zone.width),
                                 grid_y_o, palette.muted)
            else:
                draw.text((int(org_zone.left), grid_y_o), ctx.organization,
                          fill=palette.muted, font=font_meta)

        # ── Informations secondaires ──────────────────────────────────────────
        if font_meta and comp not in (CompositionModel.TRAINING_MANUAL,):
            sec_zone  = grid.zone(Zone.SECONDARY_INFO)
            sec_lines: list[str] = []
            mode_name = _mode_label(ctx.pub_mode, labels)
            if mode_name:
                sec_lines.append(mode_name)
            if ctx.pub_date:
                sec_lines.append(ctx.pub_date)
            if sec_lines:
                _pil_draw_text_block(draw, sec_lines, font_meta,
                                     palette.muted, sec_zone, align)

        img.save(str(output_path), "PNG", dpi=(150, 150))
        return True

    except Exception as exc:
        print(f"[cover_renderer] Erreur PNG : {exc}")
        return False
