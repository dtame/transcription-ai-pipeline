"""
Cover Image Engine — Moteur d'image de couverture optionnel pour PublishForge.

Gère les sources d'images de couverture pour la publication sans aucune
dépendance obligatoire. Le système fonctionne entièrement sans ce module.

Modes supportés :
    NONE                      Aucune image (couverture textuelle de secours)
    LOCAL_FILE                Image déposée manuellement par l'utilisateur
    STABLE_DIFFUSION_WEBUI    Génération via SD WebUI / Forge / Fooocus (placeholder)
    COMFYUI                   Génération via ComfyUI (placeholder)

Chemins :
    Image cible  : sortie/<project_name>/publication/cover/cover_image.png
    Prompt       : sortie/<project_name>/publication/cover/cover_prompt.txt
    Source LOCAL : sortie/<project_name>/publication/cover/source/
                   → déposer cover.jpg / cover.jpeg / cover.png
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from app.logger import log_event
from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state
from app.publication_metadata import get_publication_metadata


# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────

COVER_IMAGE_MODES: tuple[str, ...] = (
    "NONE",
    "LOCAL_FILE",
    "STABLE_DIFFUSION_WEBUI",
    "COMFYUI",
)

_COVER_IMAGE_FILENAME = "cover_image.png"
_COVER_PROMPT_FILENAME = "cover_prompt.txt"
_SOURCE_SUBDIR = "source"
_STATE_KEY = "cover_image"


# ─────────────────────────────────────────────────────────────────────────────
# Chemins
# ─────────────────────────────────────────────────────────────────────────────

def _cover_dir(project_name: str) -> Path:
    return SORTIE_DIR / project_name / "publication" / "cover"


def cover_image_path(project_name: str) -> Path:
    """Retourne le chemin cible de l'image de couverture."""
    return _cover_dir(project_name) / _COVER_IMAGE_FILENAME


def cover_prompt_path(project_name: str) -> Path:
    """Retourne le chemin du fichier prompt de couverture."""
    return _cover_dir(project_name) / _COVER_PROMPT_FILENAME


def source_dir(project_name: str) -> Path:
    """Retourne le dossier source LOCAL_FILE."""
    return _cover_dir(project_name) / _SOURCE_SUBDIR


def _ensure_dirs(project_name: str) -> None:
    _cover_dir(project_name).mkdir(parents=True, exist_ok=True)
    source_dir(project_name).mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Mode
# ─────────────────────────────────────────────────────────────────────────────

def get_cover_image_mode(project_name: str) -> str:
    """
    Retourne le mode d'image de couverture configuré pour le projet.

    Modes supportés : NONE, LOCAL_FILE, STABLE_DIFFUSION_WEBUI, COMFYUI
    Retourne "NONE" si absent ou inconnu.
    """
    state = load_project_state(project_name)
    mode = state.get(_STATE_KEY, {}).get("mode", "NONE")
    if mode not in COVER_IMAGE_MODES:
        mode = "NONE"
    return mode


def save_cover_image_mode(project_name: str, mode: str) -> None:
    """Sauvegarde le mode d'image de couverture dans project_state.json."""
    if mode not in COVER_IMAGE_MODES:
        raise ValueError(
            f"Mode inconnu : {mode!r}. "
            f"Modes valides : {COVER_IMAGE_MODES}"
        )
    state = load_project_state(project_name)
    state.setdefault(_STATE_KEY, {})["mode"] = mode
    save_project_state(project_name, state)

    print(f"[cover_image_engine] Mode image : {mode}")
    log_event({
        "step":    "cover_image_engine",
        "project": project_name,
        "action":  "mode_saved",
        "mode":    mode,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────────────────────

def build_cover_prompt(project_name: str) -> str:
    """
    Construit un prompt descriptif pour la génération d'image de couverture.

    Utilise les métadonnées de publication :
        title, subtitle, publication_mode, document_language

    Sauvegarde le prompt dans :
        sortie/<project_name>/publication/cover/cover_prompt.txt

    Retourne le prompt sous forme de chaîne.
    Le prompt n'est pas encore envoyé à un moteur image — il est généré
    pour être prêt lors d'une future intégration (SD, SDXL, Flux, ComfyUI…).
    """
    metadata = get_publication_metadata(project_name)

    title    = (metadata.get("title") or "").strip()
    subtitle = (metadata.get("subtitle") or "").strip()
    pub_mode = (metadata.get("publication_mode") or "BOOK").strip().upper()
    lang     = (metadata.get("document_language") or "en").strip().lower()

    _MODE_THEMES: dict[str, str] = {
        "BOOK":              "Spiritual growth, faith, wisdom",
        "BOOKLET":           "Knowledge, learning, clarity",
        "SERMON":            "Spiritual teaching, sacred, community",
        "TRAINING":          "Professional development, education, growth",
        "CONSULTING_REPORT": "Business, strategy, corporate professionalism",
        "CORPORATE_REPORT":  "Corporate design, enterprise, authority",
        "PODCAST":           "Audio, media, conversation, modern",
    }
    theme = _MODE_THEMES.get(pub_mode, "Professional, clean design")

    lines: list[str] = ["Professional book cover.", ""]

    if title:
        lines += ["Title:", title, ""]
    if subtitle:
        lines += ["Subtitle:", subtitle, ""]

    lines += [
        "Theme:",
        theme,
        "",
        "Clean design.",
        "High quality.",
        "Book cover.",
    ]

    if lang == "fr":
        lines += ["", "Style : couverture de livre professionnelle."]

    prompt = "\n".join(lines)

    _ensure_dirs(project_name)
    prompt_path = cover_prompt_path(project_name)
    prompt_path.write_text(prompt, encoding="utf-8")

    print(f"[cover_image_engine] Prompt couverture généré : {prompt_path}")
    log_event({
        "step":    "cover_image_engine",
        "project": project_name,
        "action":  "prompt_generated",
        "path":    str(prompt_path),
    })

    return prompt


# ─────────────────────────────────────────────────────────────────────────────
# Implémentations par mode
# ─────────────────────────────────────────────────────────────────────────────

def _generate_local_file(project_name: str) -> Path | None:
    """
    MODE LOCAL_FILE — détecte une image dans source/ et la copie vers cover_image.png.

    Formats acceptés : cover.jpg, cover.jpeg, cover.png
    """
    src_dir = source_dir(project_name)
    target  = cover_image_path(project_name)

    candidates = [
        src_dir / "cover.png",
        src_dir / "cover.jpg",
        src_dir / "cover.jpeg",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.stat().st_size > 0:
            print(f"[cover_image_engine] Image couverture trouvée : {candidate}")
            log_event({
                "step":    "cover_image_engine",
                "project": project_name,
                "action":  "source_found",
                "source":  str(candidate),
            })

            shutil.copy2(str(candidate), str(target))

            print(f"[cover_image_engine] Image couverture copiée : {target}")
            log_event({
                "step":    "cover_image_engine",
                "project": project_name,
                "action":  "image_copied",
                "path":    str(target),
            })
            return target

    print(
        f"[cover_image_engine] Aucune image trouvée dans {src_dir} "
        f"(cover.png / cover.jpg / cover.jpeg attendus)"
    )
    return None


def _generate_stable_diffusion_webui(project_name: str) -> Path | None:
    """
    MODE STABLE_DIFFUSION_WEBUI — placeholder.

    Prêt pour une future intégration avec :
        - AUTOMATIC1111 Stable Diffusion WebUI
        - Forge
        - Fooocus
        - SDXL
        - Flux Schnell

    Pour implémenter :
        1. Lire cover_prompt.txt
        2. Appeler l'API REST du WebUI (http://127.0.0.1:7860/sdapi/v1/txt2img)
        3. Sauvegarder la réponse base64 vers cover_image.png
        4. Retourner le chemin
    """
    print(
        "[cover_image_engine] STABLE_DIFFUSION_WEBUI : "
        "génération non encore implémentée. "
        "Connectez votre instance Stable Diffusion WebUI / Forge / Fooocus."
    )
    log_event({
        "step":    "cover_image_engine",
        "project": project_name,
        "action":  "placeholder",
        "mode":    "STABLE_DIFFUSION_WEBUI",
    })
    return None


def _generate_comfyui(project_name: str) -> Path | None:
    """
    MODE COMFYUI — placeholder.

    Prêt pour une future intégration avec ComfyUI (API REST locale).

    Pour implémenter :
        1. Lire cover_prompt.txt
        2. Construire un workflow ComfyUI JSON
        3. Appeler http://127.0.0.1:8188/prompt
        4. Récupérer l'image générée et la sauvegarder vers cover_image.png
        5. Retourner le chemin
    """
    print(
        "[cover_image_engine] COMFYUI : "
        "génération non encore implémentée. "
        "Connectez votre instance ComfyUI locale."
    )
    log_event({
        "step":    "cover_image_engine",
        "project": project_name,
        "action":  "placeholder",
        "mode":    "COMFYUI",
    })
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée public
# ─────────────────────────────────────────────────────────────────────────────

def generate_cover_image(project_name: str) -> Path | None:
    """
    Génère (ou récupère) l'image de couverture selon le mode configuré.

    Modes :
        NONE                    → Retourne None, aucune image.
        LOCAL_FILE              → Copie depuis source/ vers cover_image.png.
        STABLE_DIFFUSION_WEBUI  → Placeholder (retourne None).
        COMFYUI                 → Placeholder (retourne None).

    Dans tous les cas :
        - Crée sortie/<project_name>/publication/cover/ et sous-dossier source/
        - Génère cover_prompt.txt (utile pour les futurs moteurs image)
        - Met à jour project_state.json["cover_image"]

    Retourne :
        Path vers cover_image.png si disponible, None sinon.
        Le pipeline de publication continue normalement sans image.
    """
    now  = datetime.now().isoformat(timespec="seconds")
    mode = get_cover_image_mode(project_name)

    print(f"[cover_image_engine] Mode image : {mode}")
    log_event({
        "step":    "cover_image_engine",
        "project": project_name,
        "action":  "start",
        "mode":    mode,
    })

    _ensure_dirs(project_name)

    # Génération du prompt dans tous les cas
    prompt_path_str: str | None = None
    try:
        build_cover_prompt(project_name)
        prompt_path_str = str(cover_prompt_path(project_name))
    except Exception as exc:
        print(
            f"[cover_image_engine] Avertissement — impossible de générer le prompt : {exc}"
        )

    result: Path | None = None
    error: str | None = None

    try:
        if mode == "NONE":
            result = None
        elif mode == "LOCAL_FILE":
            result = _generate_local_file(project_name)
        elif mode == "STABLE_DIFFUSION_WEBUI":
            result = _generate_stable_diffusion_webui(project_name)
        elif mode == "COMFYUI":
            result = _generate_comfyui(project_name)
        else:
            print(f"[cover_image_engine] Mode inconnu : {mode!r} — aucune image générée.")

    except Exception as exc:
        error = str(exc)
        print(f"[cover_image_engine] ERREUR : {error}")
        log_event({
            "step":    "cover_image_engine",
            "project": project_name,
            "action":  "error",
            "error":   error,
        })

    _save_cover_image_state(
        project_name,
        mode=mode,
        generated=result is not None,
        now=now,
        path=str(result) if result else None,
        prompt_path=prompt_path_str,
        error=error,
    )

    if result:
        print(f"[cover_image_engine] Image couverture disponible : {result}")
        log_event({
            "step":    "cover_image_engine",
            "project": project_name,
            "action":  "done",
            "path":    str(result),
        })
    else:
        print(
            f"[cover_image_engine] Aucune image de couverture générée "
            f"(mode={mode}) — couverture textuelle de secours active."
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Persistance
# ─────────────────────────────────────────────────────────────────────────────

def _save_cover_image_state(
    project_name: str,
    *,
    mode: str,
    generated: bool,
    now: str,
    path: str | None = None,
    prompt_path: str | None = None,
    error: str | None = None,
) -> None:
    state = load_project_state(project_name)
    state.setdefault(_STATE_KEY, {})

    if generated:
        entry: dict = {
            "mode":         mode,
            "generated":    True,
            "path":         path,
            "prompt_path":  prompt_path,
            "generated_at": now,
        }
    else:
        entry = {
            "mode":         mode,
            "generated":    False,
            "prompt_path":  prompt_path,
            "generated_at": now,
        }
        if error:
            entry["error"] = error

    state[_STATE_KEY] = entry
    save_project_state(project_name, state)
    print("[cover_image_engine] project_state.json mis à jour.")
