"""
Moteurs de génération de couverture — TranscriptionAI.

Architecture extensible :
  BaseCoverEngine               → interface commune
  FakeCoverEngine               → simulation pour tests (aucune dépendance)
  ImageGenerationCoverEngine    → délègue à un provider externe
    providers actuels :
      "openai"  → OpenAI Images (DALL-E 3)
      "fake"    → alias FakeCoverEngine

Règle fondamentale :
  Toute couverture générée doit ressembler à une couverture de livre
  réellement publiée, jamais à une image Midjourney ou Stable Diffusion.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


# ---------------------------------------------------------------------------
# Prompt système global
# ---------------------------------------------------------------------------

COVER_SYSTEM_PROMPT = (
    "Professional editorial book cover photography. "
    "Natural lighting. "
    "Realistic composition. "
    "Authentic textures. "
    "Professional publishing quality. "
    "Minimalist and elegant. "
    "Suitable for commercial printing. "
    "Looks like a real published book cover. "
    "Avoid AI-looking imagery. "
    "Avoid fantasy. "
    "Avoid surrealism. "
    "Avoid CGI rendering. "
    "Avoid artificial perfection. "
    "No text. "
    "No logos. "
    "No watermark. "
    "No visible AI artifacts."
)


# ---------------------------------------------------------------------------
# Interface commune
# ---------------------------------------------------------------------------

class BaseCoverEngine(ABC):
    """Interface commune pour tous les moteurs de couverture."""

    @abstractmethod
    def generate(self, prompt: str, output_path: Path) -> Path:
        """
        Génère une couverture à partir d'un prompt.

        Args:
            prompt:      Description visuelle du contenu de la couverture.
            output_path: Chemin de sortie pour l'image (JPEG).

        Returns:
            Chemin de l'image générée.
        """
        ...

    @property
    def provider_name(self) -> str:
        return "base"


# ---------------------------------------------------------------------------
# FakeCoverEngine — simulation sans dépendance externe
# ---------------------------------------------------------------------------

class FakeCoverEngine(BaseCoverEngine):
    """
    Moteur de simulation / fallback.

    Génère une vraie couverture typographique propre (si les métadonnées
    du projet sont disponibles via settings), ou une couverture de test
    minimaliste si aucun contexte n'est fourni.

    Ne produit JAMAIS un simple placeholder "COUVERTURE" en production.
    """

    def __init__(self, settings: dict | None = None):
        self._settings = settings or {}

    @property
    def provider_name(self) -> str:
        return "fake"

    def generate(self, prompt: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self._settings:
            # Couverture typographique propre avec les métadonnées du projet
            try:
                from app.cover_generation_service import _generate_typography_pillow
                from app.publication_template_service import THEME_COLORS

                settings = dict(self._settings)
                if "theme_colors" not in settings:
                    theme = settings.get("theme", "spirituel_inspirant")
                    settings["theme_colors"] = THEME_COLORS.get(
                        theme, THEME_COLORS["moderne_epure"]
                    )
                _generate_typography_pillow(output_path, settings)
                return output_path
            except Exception:
                pass

        # Fallback : couverture typographique minimale mais propre
        _write_typographic_fallback_jpeg(output_path, self._settings)
        return output_path


def _write_placeholder_jpeg(path: Path) -> None:
    """
    Alias interne conservé pour compatibilité.
    Délègue vers _write_typographic_fallback_jpeg.
    """
    _write_typographic_fallback_jpeg(path, {})


def _write_typographic_fallback_jpeg(path: Path, settings: dict) -> None:
    """
    Génère une couverture de test/fallback typographique 600×900 px.

    Utilise Pillow si disponible pour une couverture propre avec titre.
    Fallback → 1×1 px JPEG valide (aucune dépendance).

    Ne produit JAMAIS "COUVERTURE placeholder".
    """
    title    = settings.get("title", "")
    subtitle = settings.get("subtitle", "")
    author   = settings.get("author", "")
    org      = settings.get("organization", "")

    try:
        from PIL import Image, ImageDraw

        W, H = 600, 900
        # Fond blanc cassé élégant
        bg     = (250, 248, 243)
        dark   = (26, 26, 26)
        accent = (100, 100, 100)

        img  = Image.new("RGB", (W, H), color=bg)
        draw = ImageDraw.Draw(img)

        # Bande haute
        draw.rectangle([0, 0, W, int(H * 0.12)], fill=dark)
        # Bande basse
        draw.rectangle([0, H - int(H * 0.08), W, H], fill=dark)
        # Ligne décorative
        draw.rectangle([0, int(H * 0.12), W, int(H * 0.12) + 2], fill=accent)

        # Titre
        cy = int(H * 0.38)
        if title:
            _draw_wrapped_text(draw, title, W, cy, dark, max_chars=26, line_h=42)
        else:
            _draw_centered_text(draw, "Document", W // 2, cy, dark)

        # Sous-titre
        if subtitle:
            _draw_wrapped_text(draw, subtitle, W, cy + 100, accent, max_chars=36, line_h=28)

        # Séparateur
        sep_y = int(H * 0.63)
        draw.line([(W // 2 - 50, sep_y), (W // 2 + 50, sep_y)], fill=accent, width=1)

        # Auteur
        if author:
            _draw_centered_text(draw, author, W // 2, sep_y + 30, dark)
        if org:
            _draw_centered_text(draw, org, W // 2, sep_y + 58, accent)

        img.save(str(path), "JPEG", quality=92)

    except ImportError:
        path.write_bytes(_MINIMAL_JPEG_GREY)


def _draw_wrapped_text(
    draw, text: str, page_w: int, y: int, fill: tuple,
    max_chars: int = 26, line_h: int = 40,
) -> None:
    """Dessine du texte centré sur plusieurs lignes."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for w in words:
        candidate = f"{current} {w}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)

    for i, line in enumerate(lines[:4]):
        _draw_centered_text(draw, line, page_w // 2, y + i * line_h, fill)


def _draw_centered_text(
    draw, text: str, cx: int, cy: int, fill: tuple
) -> None:
    """Dessine un texte centré sans dépendance à ImageFont."""
    try:
        draw.text((cx, cy), text, fill=fill, anchor="mm")
    except TypeError:
        # Versions anciennes de Pillow sans anchor
        w = len(text) * 7
        draw.text((cx - w // 2, cy - 8), text, fill=fill)


# JPEG 1×1 px gris clair — aucune dépendance requise
_MINIMAL_JPEG_GREY = bytes([
    0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
    0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
    0x00, 0x10, 0x0B, 0x0C, 0x0E, 0x0C, 0x0A, 0x10, 0x0E, 0x0D, 0x0E, 0x12,
    0x11, 0x10, 0x13, 0x18, 0x28, 0x1A, 0x18, 0x16, 0x16, 0x18, 0x31, 0x23,
    0x25, 0x1D, 0x28, 0x3A, 0x33, 0x3D, 0x3C, 0x39, 0x33, 0x38, 0x37, 0x40,
    0x48, 0x5C, 0x4E, 0x40, 0x44, 0x57, 0x45, 0x37, 0x38, 0x50, 0x6D, 0x51,
    0x57, 0x5F, 0x62, 0x67, 0x68, 0x67, 0x3E, 0x4D, 0x71, 0x79, 0x70, 0x64,
    0x78, 0x5C, 0x65, 0x67, 0x63, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
    0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
    0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
    0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
    0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
    0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
    0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
    0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
    0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
    0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
    0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
    0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
    0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
    0x8A, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3, 0xA4,
    0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7,
    0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA,
    0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2, 0xE3,
    0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5,
    0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00,
    0x00, 0x3F, 0x00, 0xFB, 0xD3, 0xFF, 0xD9,
])


# ---------------------------------------------------------------------------
# ImageGenerationCoverEngine — génération par API externe
# ---------------------------------------------------------------------------

class ImageGenerationCoverEngine(BaseCoverEngine):
    """
    Moteur de génération d'images via API externe.

    Providers supportés :
      "openai"  → DALL-E 3 (nécessite OPENAI_API_KEY dans config.py)
      "fake"    → FakeCoverEngine (simulation)

    Architecture extensible : ajouter de nouveaux providers dans generate().
    """

    SUPPORTED_PROVIDERS = frozenset({"openai", "fake"})

    def __init__(self, provider: str = "fake"):
        provider = provider.lower()
        if provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Provider de couverture inconnu : {provider!r}. "
                f"Valeurs supportées : {sorted(self.SUPPORTED_PROVIDERS)}"
            )
        self._provider = provider

    @property
    def provider_name(self) -> str:
        return self._provider

    def generate(self, prompt: str, output_path: Path) -> Path:
        if self._provider == "openai":
            return self._generate_openai(prompt, output_path)
        return FakeCoverEngine().generate(prompt, output_path)

    def _generate_openai(self, prompt: str, output_path: Path) -> Path:
        """Génère via OpenAI Images API (DALL-E 3)."""
        try:
            import openai
            import urllib.request
            from app import config

            api_key = getattr(config, "OPENAI_API_KEY", "")
            if not api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY non configuré dans app/config.py."
                )

            client = openai.OpenAI(api_key=api_key)
            full_prompt = f"{COVER_SYSTEM_PROMPT}\n\n{prompt}"

            response = client.images.generate(
                model="dall-e-3",
                prompt=full_prompt,
                size="1024x1792",
                quality="hd",
                n=1,
                response_format="url",
            )
            image_url = response.data[0].url

            output_path.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(image_url, str(output_path))
            return output_path

        except Exception as exc:
            raise RuntimeError(
                f"Génération de couverture OpenAI échouée : {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_cover_engine(provider: str | None = None) -> BaseCoverEngine:
    """
    Retourne le moteur correspondant au provider.
    Si provider est None, utilise COVER_PROVIDER depuis app/config.py.

    Providers supportés :
      "fake"        → couverture typographique (aucune dépendance)
      "openai"      → DALL-E 3 (nécessite OPENAI_API_KEY)
      "sdxl_local"  → Stable Diffusion XL local (nécessite diffusers + torch)
    """
    from app import config

    _provider = (provider or getattr(config, "COVER_PROVIDER", "fake")).lower()

    if _provider == "fake":
        return FakeCoverEngine()
    if _provider in ImageGenerationCoverEngine.SUPPORTED_PROVIDERS:
        return ImageGenerationCoverEngine(provider=_provider)
    if _provider == "sdxl_local":
        return _SdxlCoverEngineAdapter()

    # Fallback sécurisé
    print(f"[cover_engine] Provider inconnu '{_provider}', utilisation de 'fake'.")
    return FakeCoverEngine()


class _SdxlCoverEngineAdapter(BaseCoverEngine):
    """
    Adaptateur qui connecte BaseCoverEngine à SdxlLocalProvider
    (app.image_engine.sdxl_provider).

    Permet d'utiliser COVER_PROVIDER = "sdxl_local" dans app/config.py
    pour générer les couvertures avec SDXL sans modifier le pipeline existant.
    """

    @property
    def provider_name(self) -> str:
        return "sdxl_local"

    def generate(self, prompt: str, output_path: Path) -> Path:
        try:
            from app.image_engine.sdxl_provider import SdxlLocalProvider
        except ImportError as exc:
            raise RuntimeError(
                "Le moteur SDXL local n'est pas installé ou n'est pas disponible.\n"
                "Commande : pip install diffusers transformers accelerate safetensors torch"
            ) from exc

        from app.image_engine.image_config import IMAGE_NEGATIVE_PROMPT_DEFAULT

        provider = SdxlLocalProvider()
        return provider.generate_image(
            prompt=prompt,
            output_path=output_path,
            negative_prompt=IMAGE_NEGATIVE_PROMPT_DEFAULT,
        )
