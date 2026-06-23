"""
Service de mise en page des couvertures (PublishForge — étape 24).

Responsabilités :
  - calculer les dimensions d'affichage de la couverture (PDF en points, DOCX en pouces)
  - fournir les dimensions standard en pixels par format de page
  - normaliser les couvertures extrêmement grandes (via Pillow, optionnel)
  - préparer les futures évolutions imprimeur
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import inch

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_PAGE_SIZES_PT: dict[str, tuple] = {
    "letter":      letter,
    "a4":          A4,
    "six_by_nine": (6.0 * inch, 9.0 * inch),
    "digest":      (5.5 * inch, 8.5 * inch),
}

_STANDARD_COVER_PIXELS: dict[str, tuple[int, int]] = {
    "letter":      (2550, 3300),
    "a4":          (2480, 3508),
    "digest":      (1650, 2550),
    "six_by_nine": (1800, 2700),
}

DEFAULT_COVER_DPI = 300


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def get_cover_display_size(page_size_name: str) -> dict:
    """
    Retourne les dimensions d'affichage de la couverture en points ReportLab
    pour un format de page donné.

    Retour :
        {"width_pt": float, "height_pt": float}

    Formats supportés : letter, a4, digest, six_by_nine.
    Tout format inconnu retourne les dimensions A4.
    """
    pagesize = _PAGE_SIZES_PT.get(page_size_name, A4)
    return {
        "width_pt":  pagesize[0],
        "height_pt": pagesize[1],
    }


def get_standard_cover_pixels(page_size_name: str) -> tuple[int, int]:
    """
    Retourne les dimensions standard de la couverture en pixels à 300 DPI.

    Exemples :
        letter      → (2550, 3300)
        a4          → (2480, 3508)
        digest      → (1650, 2550)
        six_by_nine → (1800, 2700)

    Tout format inconnu retourne les dimensions A4.
    """
    return _STANDARD_COVER_PIXELS.get(page_size_name, _STANDARD_COVER_PIXELS["a4"])


def normalize_cover_if_needed(
    cover_path: Path,
    page_size_name: str = "a4",
    max_pixels: int = 5000,
) -> Path:
    """
    Redimensionne la couverture si elle est extrêmement grande.

    - Si Pillow n'est pas disponible, retourne cover_path inchangé.
    - Si l'image est en dessous de max_pixels sur ses deux axes, retourne cover_path inchangé.
    - Sinon, redimensionne aux dimensions standard et sauvegarde en cover_normalized.jpg.

    Ne touche jamais cover.jpg original.

    Retourne le chemin de l'image (originale ou normalisée).
    """
    try:
        from PIL import Image
    except ImportError:
        return cover_path

    try:
        with Image.open(cover_path) as img:
            w, h = img.size
            if w <= max_pixels and h <= max_pixels:
                return cover_path

            target_w, target_h = get_standard_cover_pixels(page_size_name)
            img_resized = img.resize((target_w, target_h), Image.LANCZOS)
            out_path = cover_path.parent / "cover_normalized.jpg"
            img_resized.save(out_path, "JPEG", quality=92)
            print(
                f"[cover_layout] image normalisée : {w}×{h} → {target_w}×{target_h}"
            )
            return out_path

    except Exception as exc:
        print(f"[cover_layout] normalisation ignorée : {exc}")
        return cover_path
