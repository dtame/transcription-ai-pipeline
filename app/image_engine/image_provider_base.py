"""
Classe abstraite commune pour tous les providers de génération d'images.

Tout nouveau provider doit hériter de ImageProviderBase et implémenter
generate_image(). L'architecture est volontairement minimaliste pour
faciliter l'ajout de nouveaux providers (Stable Diffusion 3, ComfyUI,
Replicate, etc.) sans modifier le code existant.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class ImageProviderBase(ABC):
    """Interface commune pour tous les providers d'images."""

    @abstractmethod
    def generate_image(
        self,
        prompt: str,
        output_path: Path,
        negative_prompt: str | None = None,
        width: int | None = None,
        height: int | None = None,
        seed: int | None = None,
    ) -> Path:
        """
        Génère une image à partir d'un prompt et la sauvegarde sur disque.

        Args:
            prompt:          Description visuelle de l'image à générer.
            output_path:     Chemin de sortie (PNG recommandé).
            negative_prompt: Ce que l'image ne doit pas contenir.
                             Si None, utilise le prompt négatif par défaut du provider.
            width:           Largeur en pixels. Si None, utilise la valeur par défaut.
            height:          Hauteur en pixels. Si None, utilise la valeur par défaut.
            seed:            Graine aléatoire pour la reproductibilité.
                             Si None, génération non déterministe.

        Returns:
            Chemin absolu de l'image générée (identique à output_path).

        Raises:
            RuntimeError: si la génération échoue (dépendances manquantes,
                          VRAM insuffisante, modèle introuvable, etc.)
        """
        ...

    @property
    def provider_name(self) -> str:
        """Identifiant lisible du provider (ex. 'sdxl_local', 'fake')."""
        return "base"

    @property
    def model_id(self) -> str:
        """Identifiant du modèle utilisé (ex. 'stabilityai/stable-diffusion-xl-base-1.0')."""
        return "unknown"

    def is_available(self) -> bool:
        """
        Vérifie si le provider est disponible (dépendances installées, modèle accessible).

        Retourne False si les dépendances sont manquantes.
        Ne lève pas d'exception.
        """
        return True


class FakeImageProvider(ImageProviderBase):
    """
    Provider de simulation — aucune dépendance requise.

    Génère un PNG gris uni avec un pixel valide.
    Utile pour les tests unitaires et l'intégration CI.
    """

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_id(self) -> str:
        return "fake"

    def generate_image(
        self,
        prompt: str,
        output_path: Path,
        negative_prompt: str | None = None,
        width: int | None = None,
        height: int | None = None,
        seed: int | None = None,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        w = width or 64
        h = height or 64

        try:
            from PIL import Image

            img = Image.new("RGB", (w, h), color=(180, 180, 180))
            img.save(str(output_path), "PNG")
        except ImportError:
            # Fallback PNG minimal 1×1 px sans Pillow
            output_path.write_bytes(_MINIMAL_PNG_1X1)

        return output_path


# PNG 1×1 px gris — aucune dépendance requise
_MINIMAL_PNG_1X1 = bytes([
    0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # Signature PNG
    0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1
    0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,  # 8-bit RGB
    0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
    0x54, 0x08, 0xD7, 0x63, 0xB4, 0xB4, 0xB4, 0x00,
    0x00, 0x00, 0x60, 0x00, 0x01, 0x13, 0x0E, 0xF8,
    0xD5, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
    0x44, 0xAE, 0x42, 0x60, 0x82,
])
