"""
Service principal de génération d'images (image_engine).

Point d'entrée unique pour toutes les générations d'images du projet.
Orchestre : sélection du provider → construction du prompt →
            génération → sauvegarde → métadonnées JSON.

Ce service est totalement indépendant du pipeline texte (Ollama / Whisper).

Structure de sortie :
  sortie/<project_name>/images/
    cover_front/
      cover_front.png
      cover_front.metadata.json
    cover_back/
    chapters/
    sections/
    training/
    rejected/

Test :
    python -m app.image_engine.image_service
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.image_engine.image_config import (
    IMAGE_GUIDANCE_SCALE,
    IMAGE_HEIGHT,
    IMAGE_NEGATIVE_PROMPT_DEFAULT,
    IMAGE_OUTPUT_SUBDIRS,
    IMAGE_PROVIDER,
    IMAGE_STEPS,
    IMAGE_WIDTH,
    SDXL_MODEL_ID,
)
from app.image_engine.image_prompt_builder import (
    build_back_cover_prompt,
    build_chapter_illustration_prompt,
    build_cover_prompt,
    build_training_visual_prompt,
)
from app.image_engine.image_provider_base import FakeImageProvider, ImageProviderBase
from app.paths import SORTIE_DIR


# ──────────────────────────────────────────────────────────────────────────────
# Factory provider
# ──────────────────────────────────────────────────────────────────────────────

def get_image_provider(provider: str | None = None) -> ImageProviderBase:
    """
    Retourne le provider d'images selon la configuration.

    Args:
        provider: Identifiant du provider. Si None, utilise IMAGE_PROVIDER.

    Returns:
        Instance d'ImageProviderBase prête à l'emploi.

    Raises:
        ValueError: si le provider est inconnu.
    """
    _provider = (provider or IMAGE_PROVIDER).strip().lower()

    if _provider == "sdxl_local":
        from app.image_engine.sdxl_provider import SdxlLocalProvider
        return SdxlLocalProvider()

    if _provider == "fake":
        return FakeImageProvider()

    raise ValueError(
        f"Provider d'images inconnu : '{_provider}'. "
        "Valeurs acceptées : 'sdxl_local', 'fake'."
    )


# ──────────────────────────────────────────────────────────────────────────────
# Initialisation dossiers de sortie
# ──────────────────────────────────────────────────────────────────────────────

def ensure_image_output_dirs(project_name: str) -> Path:
    """
    Crée les sous-dossiers d'images pour le projet si absents.

    Args:
        project_name: Nom du projet (identique au dossier dans sortie/).

    Returns:
        Chemin racine sortie/<project_name>/images/
    """
    base = SORTIE_DIR / project_name / "images"
    for subdir in IMAGE_OUTPUT_SUBDIRS:
        (base / subdir).mkdir(parents=True, exist_ok=True)
    return base


# ──────────────────────────────────────────────────────────────────────────────
# Génération couverture avant
# ──────────────────────────────────────────────────────────────────────────────

def generate_project_cover_image(
    project_name: str,
    title: str,
    subtitle: str | None = None,
    content_type: str | None = None,
    audience: str | None = None,
    theme_summary: str | None = None,
    seed: int | None = None,
    provider: str | None = None,
) -> Path:
    """
    Génère l'image de couverture avant du projet avec SDXL.

    Le texte (titre, auteur, sous-titre) N'EST PAS inclus dans l'image —
    il sera ajouté lors de la mise en page finale (ReportLab / python-docx).

    Args:
        project_name:  Nom du projet (dossier dans sortie/).
        title:         Titre du document.
        subtitle:      Sous-titre optionnel.
        content_type:  Type de document (ex. "livre", "formation").
        audience:      Public cible (ex. "professionnels chrétiens").
        theme_summary: Résumé visuel thématique (quelques mots clés).
        seed:          Graine aléatoire pour la reproductibilité.
        provider:      Override du provider (None = valeur de image_config.py).

    Returns:
        Chemin de l'image PNG générée.

    Raises:
        RuntimeError: si la génération échoue.
    """
    images_dir = ensure_image_output_dirs(project_name)
    output_dir = images_dir / "cover_front"
    output_path = output_dir / "cover_front.png"
    metadata_path = output_dir / "cover_front.metadata.json"

    prompt = build_cover_prompt(
        title=title,
        subtitle=subtitle,
        content_type=content_type,
        audience=audience,
        theme_summary=theme_summary,
    )
    negative_prompt = IMAGE_NEGATIVE_PROMPT_DEFAULT

    image_provider = get_image_provider(provider)

    print(f"[image_service] Provider : {image_provider.provider_name}")
    print(f"[image_service] Prompt   : {prompt[:120]}…")

    generated_path = image_provider.generate_image(
        prompt=prompt,
        output_path=output_path,
        negative_prompt=negative_prompt,
        width=IMAGE_WIDTH,
        height=IMAGE_HEIGHT,
        seed=seed,
    )

    _save_metadata(
        metadata_path=metadata_path,
        provider=image_provider.provider_name,
        model_id=image_provider.model_id,
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=IMAGE_WIDTH,
        height=IMAGE_HEIGHT,
        steps=IMAGE_STEPS,
        guidance_scale=IMAGE_GUIDANCE_SCALE,
        seed=seed,
        output_path=generated_path,
    )

    return generated_path


# ──────────────────────────────────────────────────────────────────────────────
# Génération quatrième de couverture
# ──────────────────────────────────────────────────────────────────────────────

def generate_project_back_cover_image(
    project_name: str,
    title: str,
    theme_summary: str | None = None,
    seed: int | None = None,
    provider: str | None = None,
) -> Path:
    """
    Génère l'image de quatrième de couverture.

    Returns:
        Chemin de l'image PNG générée.
    """
    images_dir = ensure_image_output_dirs(project_name)
    output_path = images_dir / "cover_back" / "cover_back.png"
    metadata_path = images_dir / "cover_back" / "cover_back.metadata.json"

    prompt = build_back_cover_prompt(title=title, theme_summary=theme_summary)
    negative_prompt = IMAGE_NEGATIVE_PROMPT_DEFAULT

    image_provider = get_image_provider(provider)

    generated_path = image_provider.generate_image(
        prompt=prompt,
        output_path=output_path,
        negative_prompt=negative_prompt,
        width=IMAGE_WIDTH,
        height=IMAGE_HEIGHT,
        seed=seed,
    )

    _save_metadata(
        metadata_path=metadata_path,
        provider=image_provider.provider_name,
        model_id=image_provider.model_id,
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=IMAGE_WIDTH,
        height=IMAGE_HEIGHT,
        steps=IMAGE_STEPS,
        guidance_scale=IMAGE_GUIDANCE_SCALE,
        seed=seed,
        output_path=generated_path,
    )

    return generated_path


# ──────────────────────────────────────────────────────────────────────────────
# Génération illustration de chapitre
# ──────────────────────────────────────────────────────────────────────────────

def generate_chapter_illustration(
    project_name: str,
    chapter_slug: str,
    chapter_title: str,
    chapter_summary: str | None = None,
    seed: int | None = None,
    provider: str | None = None,
) -> Path:
    """
    Génère une illustration pour un chapitre.

    Args:
        chapter_slug: Identifiant court du chapitre (ex. "ch01_introduction").

    Returns:
        Chemin de l'image PNG générée.
    """
    images_dir = ensure_image_output_dirs(project_name)
    output_path = images_dir / "chapters" / f"{chapter_slug}.png"
    metadata_path = images_dir / "chapters" / f"{chapter_slug}.metadata.json"

    prompt = build_chapter_illustration_prompt(
        chapter_title=chapter_title,
        chapter_summary=chapter_summary,
    )
    negative_prompt = IMAGE_NEGATIVE_PROMPT_DEFAULT

    image_provider = get_image_provider(provider)

    generated_path = image_provider.generate_image(
        prompt=prompt,
        output_path=output_path,
        negative_prompt=negative_prompt,
        width=IMAGE_WIDTH,
        height=IMAGE_HEIGHT,
        seed=seed,
    )

    _save_metadata(
        metadata_path=metadata_path,
        provider=image_provider.provider_name,
        model_id=image_provider.model_id,
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=IMAGE_WIDTH,
        height=IMAGE_HEIGHT,
        steps=IMAGE_STEPS,
        guidance_scale=IMAGE_GUIDANCE_SCALE,
        seed=seed,
        output_path=generated_path,
    )

    return generated_path


# ──────────────────────────────────────────────────────────────────────────────
# Génération visuel de formation
# ──────────────────────────────────────────────────────────────────────────────

def generate_training_visual(
    project_name: str,
    visual_slug: str,
    topic: str,
    audience: str | None = None,
    seed: int | None = None,
    provider: str | None = None,
) -> Path:
    """
    Génère un visuel pour une formation ou présentation.

    Args:
        visual_slug: Identifiant court du visuel (ex. "intro_slide").

    Returns:
        Chemin de l'image PNG générée.
    """
    images_dir = ensure_image_output_dirs(project_name)
    output_path = images_dir / "training" / f"{visual_slug}.png"
    metadata_path = images_dir / "training" / f"{visual_slug}.metadata.json"

    prompt = build_training_visual_prompt(topic=topic, audience=audience)
    negative_prompt = IMAGE_NEGATIVE_PROMPT_DEFAULT

    image_provider = get_image_provider(provider)

    generated_path = image_provider.generate_image(
        prompt=prompt,
        output_path=output_path,
        negative_prompt=negative_prompt,
        width=IMAGE_WIDTH,
        height=IMAGE_HEIGHT,
        seed=seed,
    )

    _save_metadata(
        metadata_path=metadata_path,
        provider=image_provider.provider_name,
        model_id=image_provider.model_id,
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=IMAGE_WIDTH,
        height=IMAGE_HEIGHT,
        steps=IMAGE_STEPS,
        guidance_scale=IMAGE_GUIDANCE_SCALE,
        seed=seed,
        output_path=generated_path,
    )

    return generated_path


# ──────────────────────────────────────────────────────────────────────────────
# Sauvegarde des métadonnées
# ──────────────────────────────────────────────────────────────────────────────

def _save_metadata(
    metadata_path: Path,
    provider: str,
    model_id: str,
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    steps: int,
    guidance_scale: float,
    seed: int | None,
    output_path: Path,
) -> None:
    """Sauvegarde les métadonnées de génération en JSON."""
    data = {
        "provider": provider,
        "model_id": model_id,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "steps": steps,
        "guidance_scale": guidance_scale,
        "seed": seed,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "output_path": str(output_path),
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────────
# Point d'entrée test : python -m app.image_engine.image_service
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Test de génération d'image de couverture avec image_engine."
    )
    parser.add_argument(
        "--project", "-p",
        default="test_image_engine",
        help="Nom du projet (dossier de sortie). Défaut : test_image_engine",
    )
    parser.add_argument(
        "--title", "-t",
        default="Retraite Pastorale",
        help="Titre du document.",
    )
    parser.add_argument(
        "--subtitle", "-s",
        default="Approfondissement spirituel et communautaire",
        help="Sous-titre (optionnel).",
    )
    parser.add_argument(
        "--content-type", "-c",
        default="retraite",
        help="Type de contenu (ex. livre, formation, retraite).",
    )
    parser.add_argument(
        "--audience", "-a",
        default=None,
        help="Public cible (optionnel).",
    )
    parser.add_argument(
        "--theme", "-m",
        default="peaceful retreat in nature, contemplation, community gathering",
        help="Résumé thématique visuel.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Graine aléatoire pour la reproductibilité. Défaut : 42",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help=(
            "Provider à utiliser (sdxl_local | fake). "
            "Si non spécifié, utilise IMAGE_PROVIDER de image_config.py."
        ),
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  image_engine — Test de génération de couverture")
    print("=" * 60)
    print(f"  Projet       : {args.project}")
    print(f"  Titre        : {args.title}")
    print(f"  Sous-titre   : {args.subtitle}")
    print(f"  Type         : {args.content_type}")
    print(f"  Thème        : {args.theme}")
    print(f"  Seed         : {args.seed}")
    print(f"  Provider     : {args.provider or IMAGE_PROVIDER} (config)")
    print("=" * 60)

    try:
        output = generate_project_cover_image(
            project_name=args.project,
            title=args.title,
            subtitle=args.subtitle,
            content_type=args.content_type,
            audience=args.audience,
            theme_summary=args.theme,
            seed=args.seed,
            provider=args.provider,
        )

        print()
        print("  Génération réussie !")
        print(f"  Image    : {output}")
        metadata = output.parent / (output.stem + ".metadata.json")
        if metadata.exists():
            print(f"  Metadata : {metadata}")
        print()

    except RuntimeError as exc:
        print(f"\n  ERREUR : {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n  Génération interrompue.", file=sys.stderr)
        sys.exit(1)
