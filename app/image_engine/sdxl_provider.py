"""
Provider SDXL local — Stable Diffusion XL 1.0 via Hugging Face Diffusers.

Ce provider est optionnel : si les dépendances ne sont pas installées,
l'application ne plante pas — une RuntimeError claire est levée uniquement
au moment d'une tentative de génération.

Dépendances requises (non incluses dans requirements.txt par défaut) :
    pip install diffusers transformers accelerate safetensors torch Pillow

Premier lancement :
    Le modèle (~6 Go) est téléchargé automatiquement dans
    ~/.cache/huggingface/ et mis en cache pour les appels suivants.

Détection automatique :
    - GPU NVIDIA disponible → torch.float16, CUDA
    - Pas de GPU → torch.float32, CPU (lent mais fonctionnel)
"""

from __future__ import annotations

import gc
from pathlib import Path
from typing import TYPE_CHECKING

from app.image_engine.image_provider_base import ImageProviderBase
from app.image_engine.image_config import (
    SDXL_MODEL_ID,
    SDXL_VARIANT,
    IMAGE_WIDTH,
    IMAGE_HEIGHT,
    IMAGE_STEPS,
    IMAGE_GUIDANCE_SCALE,
    IMAGE_NEGATIVE_PROMPT_DEFAULT,
    SDXL_FORCE_CPU,
    SDXL_CPU_OFFLOAD,
)

if TYPE_CHECKING:
    pass


class SdxlLocalProvider(ImageProviderBase):
    """
    Génération d'images via Stable Diffusion XL 1.0 (local).

    Chargement lazy : le modèle n'est chargé qu'au premier appel
    à generate_image(). Le démarrage de l'application n'est pas impacté.
    """

    def __init__(self) -> None:
        self._pipeline = None
        self._device: str | None = None

    # ──────────────────────────────────────────────────────────────────────────
    # Propriétés
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def provider_name(self) -> str:
        return "sdxl_local"

    @property
    def model_id(self) -> str:
        return SDXL_MODEL_ID

    # ──────────────────────────────────────────────────────────────────────────
    # Disponibilité
    # ──────────────────────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Retourne True si diffusers et torch sont installés."""
        try:
            import diffusers  # noqa: F401
            import torch  # noqa: F401
            return True
        except ImportError:
            return False

    # ──────────────────────────────────────────────────────────────────────────
    # Chargement du modèle (lazy)
    # ──────────────────────────────────────────────────────────────────────────

    def _load_pipeline(self) -> None:
        """Charge le pipeline SDXL si ce n'est pas encore fait."""
        if self._pipeline is not None:
            return

        _check_dependencies()

        import torch
        from diffusers import StableDiffusionXLPipeline

        device, dtype = _detect_device_and_dtype()
        self._device = device

        print(
            f"[sdxl_local] Chargement du modèle {SDXL_MODEL_ID} "
            f"sur {device} ({dtype}) …"
        )

        try:
            load_kwargs: dict = {
                "torch_dtype": dtype,
                "use_safetensors": True,
            }

            # Variante fp16 disponible uniquement si CUDA
            if dtype == torch.float16 and SDXL_VARIANT:
                load_kwargs["variant"] = SDXL_VARIANT

            pipeline = StableDiffusionXLPipeline.from_pretrained(
                SDXL_MODEL_ID,
                **load_kwargs,
            )

            if SDXL_CPU_OFFLOAD and device == "cuda":
                pipeline.enable_model_cpu_offload()
            else:
                pipeline = pipeline.to(device)

            self._pipeline = pipeline
            print(f"[sdxl_local] Modèle chargé ({device}).")

        except Exception as exc:
            self._pipeline = None
            raise RuntimeError(
                f"Impossible de charger le modèle SDXL ({SDXL_MODEL_ID}) : {exc}\n"
                "Vérifiez votre connexion internet (premier téléchargement) "
                "ou l'espace disque disponible (~6 Go)."
            ) from exc

    def unload(self) -> None:
        """Libère le modèle de la mémoire (VRAM / RAM)."""
        if self._pipeline is not None:
            del self._pipeline
            self._pipeline = None
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
            print("[sdxl_local] Modèle déchargé.")

    # ──────────────────────────────────────────────────────────────────────────
    # Génération
    # ──────────────────────────────────────────────────────────────────────────

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
        Génère une image PNG avec SDXL et la sauvegarde sur disque.

        Args:
            prompt:          Prompt positif décrivant l'image.
            output_path:     Chemin de sortie (le dossier est créé si absent).
            negative_prompt: Prompt négatif. Utilise le défaut si None.
            width:           Largeur en pixels (défaut : IMAGE_WIDTH).
            height:          Hauteur en pixels (défaut : IMAGE_HEIGHT).
            seed:            Graine pour la reproductibilité (None = aléatoire).

        Returns:
            output_path après écriture.

        Raises:
            RuntimeError: dépendances manquantes, VRAM insuffisante, etc.
        """
        import torch

        self._load_pipeline()

        w = width or IMAGE_WIDTH
        h = height or IMAGE_HEIGHT
        neg = negative_prompt if negative_prompt is not None else IMAGE_NEGATIVE_PROMPT_DEFAULT

        generator = None
        if seed is not None:
            generator = torch.Generator(device=self._device).manual_seed(seed)

        print(
            f"[sdxl_local] Génération {w}×{h} — "
            f"{IMAGE_STEPS} étapes, CFG={IMAGE_GUIDANCE_SCALE} …"
        )

        try:
            result = self._pipeline(
                prompt=prompt,
                negative_prompt=neg,
                width=w,
                height=h,
                num_inference_steps=IMAGE_STEPS,
                guidance_scale=IMAGE_GUIDANCE_SCALE,
                generator=generator,
            )
        except RuntimeError as exc:
            error_str = str(exc).lower()
            if "out of memory" in error_str or "cuda out of memory" in error_str:
                self.unload()
                raise RuntimeError(
                    "Mémoire GPU insuffisante pour générer l'image avec SDXL. "
                    "Options :\n"
                    "  1. Réduire IMAGE_WIDTH / IMAGE_HEIGHT dans image_config.py\n"
                    "  2. Activer SDXL_CPU_OFFLOAD = True dans image_config.py\n"
                    "  3. Activer SDXL_FORCE_CPU = True pour passer en mode CPU\n"
                    f"Erreur originale : {exc}"
                ) from exc
            raise RuntimeError(
                f"Erreur lors de la génération SDXL : {exc}"
            ) from exc

        image = result.images[0]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(output_path), "PNG")

        print(f"[sdxl_local] Image sauvegardée → {output_path}")
        return output_path


# ──────────────────────────────────────────────────────────────────────────────
# Fonctions utilitaires internes
# ──────────────────────────────────────────────────────────────────────────────

def _check_dependencies() -> None:
    """
    Vérifie que les dépendances SDXL sont installées.

    Lève une RuntimeError claire avec les commandes d'installation si manquant.
    """
    missing = []
    for pkg in ("torch", "diffusers", "transformers", "accelerate"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        install_cmd = "pip install " + " ".join(missing)
        raise RuntimeError(
            "Le moteur SDXL local n'est pas installé ou n'est pas disponible.\n"
            f"Packages manquants : {', '.join(missing)}\n"
            f"Commande d'installation : {install_cmd}\n"
            "Commande complète recommandée :\n"
            "  pip install diffusers transformers accelerate safetensors torch Pillow"
        )


def _detect_device_and_dtype() -> tuple[str, object]:
    """
    Détecte le device optimal (CUDA > CPU) et le dtype associé.

    Returns:
        (device_str, torch_dtype)
        - ("cuda", torch.float16) si GPU NVIDIA disponible et non forcé CPU
        - ("cpu",  torch.float32) sinon
    """
    import torch

    if not SDXL_FORCE_CPU and torch.cuda.is_available():
        return "cuda", torch.float16

    return "cpu", torch.float32
