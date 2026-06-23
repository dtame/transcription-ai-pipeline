"""
Service d'harmonisation éditoriale globale — Étape 18.

Traite document_final.md avec un prompt dédié et génère
sortie/<projet>/harmonized/document_harmonized.md.

Ce service est totalement optionnel (GLOBAL_EDITOR_ENABLED = False par défaut).
Il ne modifie jamais document_final.md.

Modes disponibles :
    light      -> harmonisation légère : titres, structure, ponctuation, transitions
    medium     -> fusion légère de répétitions, amélioration de la fluidité
    aggressive -> réécriture globale (réservé aux livres longs)

Reprise après interruption :
    Ne retraite pas si document_final.md n'a pas changé, si le mode
    n'a pas changé, et si document_harmonized.md existe déjà.
"""

import hashlib
from datetime import datetime
from pathlib import Path

from app.config import GLOBAL_EDITOR_ENABLED, GLOBAL_EDITOR_MODE
from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state
from app.ai_engine import get_ai_engine
from app.prompt_manager import PROMPT_TEMPLATES
from app.prompt_utils import render_prompt


_VALID_MODES = ("light", "medium", "aggressive")


def _file_signature(path: Path) -> str:
    """Calcule la signature MD5 d'un fichier."""
    hasher = hashlib.md5()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            hasher.update(block)
    return hasher.hexdigest()


def get_harmonized_path(project_name: str) -> Path:
    """Retourne le chemin attendu de document_harmonized.md."""
    return SORTIE_DIR / project_name / "harmonized" / "document_harmonized.md"


def _get_final_path(project_name: str) -> Path:
    return SORTIE_DIR / project_name / "final" / "document_final.md"


def _should_rebuild(
    state: dict,
    harmonized_path: Path,
    final_sig: str,
    mode: str,
) -> bool:
    """Détermine si l'harmonisation doit être reconstruite."""
    if not harmonized_path.exists():
        return True

    harm_state = state.get("harmonization", {})
    if not harm_state.get("generated"):
        return True
    if harm_state.get("source_signature") != final_sig:
        return True
    if harm_state.get("mode") != mode:
        return True

    return False


def _process_full_document(text: str, mode: str) -> str:
    """
    Traite le document complet avec le prompt d'harmonisation adapté au mode.

    Utilise engine.send_prompt() pour contourner le système de prompts par chunks
    et injecter directement le prompt d'harmonisation global.
    """
    task_name = f"global_harmonization_{mode}"
    template = PROMPT_TEMPLATES.get(task_name)
    if template is None:
        raise ValueError(
            f"Prompt d'harmonisation introuvable : '{task_name}'. "
            f"Modes disponibles : {_VALID_MODES}"
        )

    prompt = render_prompt(template, {"TEXT": text})
    engine = get_ai_engine()
    print(f"[harmonisation] Moteur IA actif : {engine.__class__.__name__}")
    return engine.send_prompt(prompt)


def harmonize_document(project_name: str) -> Path | None:
    """
    Harmonise document_final.md et génère document_harmonized.md.

    Retourne le chemin vers document_harmonized.md si généré, None sinon.

    Règles de reprise :
        - Ne retraite pas si document_final.md n'a pas changé.
        - Ne retraite pas si le mode n'a pas changé.
        - Ne retraite pas si document_harmonized.md existe déjà.

    Ne modifie jamais document_final.md.

    Args:
        project_name: nom du projet (sous-dossier de sortie/)

    Returns:
        Path vers document_harmonized.md si généré, None si étape ignorée ou échouée.
    """
    if not GLOBAL_EDITOR_ENABLED:
        print("[harmonisation] Étape désactivée (GLOBAL_EDITOR_ENABLED = False).")
        return None

    mode = GLOBAL_EDITOR_MODE.strip().lower()

    if mode == "off":
        print("[harmonisation] Mode 'off' — étape ignorée.")
        return None

    if mode not in _VALID_MODES:
        print(
            f"[harmonisation] Mode inconnu : '{mode}'. "
            f"Modes valides : {_VALID_MODES}. Étape ignorée."
        )
        return None

    final_path = _get_final_path(project_name)
    if not final_path.exists():
        print(f"[harmonisation] document_final.md introuvable : {final_path}")
        return None

    harmonized_path = get_harmonized_path(project_name)
    final_sig = _file_signature(final_path)
    state = load_project_state(project_name)

    if not _should_rebuild(state, harmonized_path, final_sig, mode):
        print(
            f"[harmonisation] document_harmonized.md déjà à jour : {harmonized_path}"
        )
        return harmonized_path

    print(f"[harmonisation] Harmonisation en cours (mode : {mode})...")

    try:
        text = final_path.read_text(encoding="utf-8")
        result = _process_full_document(text, mode)

        harmonized_path.parent.mkdir(parents=True, exist_ok=True)
        harmonized_path.write_text(result, encoding="utf-8")

        generated_at = datetime.now().isoformat(timespec="seconds")

        state["harmonization"] = {
            "enabled": True,
            "mode": mode,
            "generated": True,
            "path": str(harmonized_path),
            "source_signature": final_sig,
            "updated_at": generated_at,
        }

        save_project_state(project_name, state)
        print(f"[harmonisation] document_harmonized.md généré : {harmonized_path}")
        return harmonized_path

    except Exception as e:
        print(f"[harmonisation] Erreur lors de l'harmonisation : {e}")

        state["harmonization"] = {
            "enabled": True,
            "mode": mode,
            "generated": False,
            "path": None,
            "source_signature": final_sig,
            "error": str(e),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

        save_project_state(project_name, state)
        return None
