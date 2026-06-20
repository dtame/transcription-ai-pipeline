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
    Moteur de simulation pour les tests.
    Génère une image JPEG minimaliste de placeholder.
    Utilise Pillow si disponible, sinon un JPEG minimal raw.
    """

    @property
    def provider_name(self) -> str:
        return "fake"

    def generate(self, prompt: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _write_placeholder_jpeg(output_path)
        return output_path


def _write_placeholder_jpeg(path: Path) -> None:
    """
    Génère un JPEG de placeholder 600×900 px.
    Pillow → image lisible avec texte.
    Fallback → 1×1 px JPEG valide (aucune dépendance).
    """
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (600, 900), color=(245, 245, 245))
        draw = ImageDraw.Draw(img)
        draw.rectangle([20, 20, 579, 879], outline=(200, 200, 200), width=2)
        draw.rectangle([40, 40, 559, 860], outline=(220, 220, 220), width=1)
        cx = 300
        draw.line([(cx - 60, 400), (cx + 60, 400)], fill=(180, 180, 180), width=1)
        _draw_centered_text(draw, "COUVERTURE", cx, 430, (140, 140, 140))
        _draw_centered_text(draw, "placeholder", cx, 460, (180, 180, 180))
        img.save(str(path), "JPEG", quality=85)
    except ImportError:
        path.write_bytes(_MINIMAL_JPEG_GREY)


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
    """
    from app import config

    _provider = (provider or getattr(config, "COVER_PROVIDER", "fake")).lower()

    if _provider == "fake":
        return FakeCoverEngine()
    if _provider in ImageGenerationCoverEngine.SUPPORTED_PROVIDERS:
        return ImageGenerationCoverEngine(provider=_provider)

    # Fallback sécurisé
    print(f"[cover_engine] Provider inconnu '{_provider}', utilisation de 'fake'.")
    return FakeCoverEngine()
