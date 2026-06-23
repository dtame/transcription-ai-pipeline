"""
image_engine — Moteur de génération d'images locales (PublishForge).

Ce module est indépendant du pipeline texte (Ollama / Faster-Whisper).
Il fournit une architecture extensible pour la génération d'images via
différents providers.

Providers disponibles :
  sdxl_local  → Stable Diffusion XL (local, Hugging Face Diffusers)
  fake        → simulation sans dépendance (pour les tests)

Usage rapide :
    from app.image_engine.image_service import generate_project_cover_image
    output = generate_project_cover_image("mon_projet", title="Mon Titre")
"""

__all__ = ["generate_project_cover_image"]


def __getattr__(name: str):
    if name == "generate_project_cover_image":
        from app.image_engine.image_service import generate_project_cover_image
        return generate_project_cover_image
    raise AttributeError(f"module 'app.image_engine' has no attribute {name!r}")
