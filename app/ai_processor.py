"""
Orchestration du traitement IA des chunks de transcription.

Ce module ne connaît pas le moteur IA utilisé.
Il délègue le traitement à get_ai_engine() qui retourne
le moteur configuré dans app/config.py (AI_PROVIDER).

Pipeline :
    1. Charger project_state.json
    2. Pour chaque chunk à l'état "pending_ai" (ou "pending" pour compat) :
       a. Lire le texte brut depuis sortie/<projet>/chunks/
       b. Appeler engine.process(text)
       c. Écrire le Markdown dans sortie/<projet>/processed/
       d. Mettre à jour project_state.json (status → "done", chemin, timestamp)
    3. Les chunks déjà "done" sont ignorés (reprise après interruption)
    4. Les chunks "skipped_empty" sont ignorés (pas de contenu réel)
    5. Les erreurs sont enregistrées sans interrompre les autres chunks
       Un fichier d'erreur détaillé est écrit dans sortie/<projet>/errors/

Règle d'envoi à l'IA :
    Un chunk est traité si et seulement si :
    - needs_ai_processing = True  (chunk créé, modifié, ou processed absent)
    - OU le fichier processed/chunk_XXX.md est absent
    - OU force_ai_processing = True (retraitement manuel)
"""

import re
import traceback
from datetime import datetime

from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state
from app.ai_engine import get_ai_engine
from app.chunk_service import is_real_transcript_content


_METADATA_HEADER_PATTERNS = re.compile(
    r"^#\s*(Projet|Chunk|Généré le)\s*:",
    re.IGNORECASE | re.MULTILINE,
)


def _strip_chunk_metadata_header(text: str) -> str:
    """
    Supprime les lignes d'en-tête de métadonnées d'un chunk avant traitement IA.

    Retire les lignes du type :
        # Projet : nom_du_projet
        # Chunk : 001/008
        # Généré le : 2024-...

    ainsi que les lignes vides initiales après suppression.
    """
    lines = text.splitlines()
    cleaned: list[str] = []
    header_done = False

    for line in lines:
        stripped = line.strip()
        if not header_done:
            if _METADATA_HEADER_PATTERNS.match(stripped):
                continue
            if not stripped:
                continue
            header_done = True
        cleaned.append(line)

    return "\n".join(cleaned).strip()


def _write_chunk_error(
    errors_dir,
    chunk_name: str,
    exc: Exception,
    tb: str,
    prompt_excerpt: str | None = None,
) -> None:
    """
    Écrit un fichier d'erreur détaillé dans sortie/<projet>/errors/.

    Args:
        errors_dir:    Path vers le dossier errors/ du projet.
        chunk_name:    Nom du chunk concerné (ex. chunk_045.txt).
        exc:           Exception levée pendant le traitement.
        tb:            Traceback complet en chaîne.
        prompt_excerpt: Extrait du prompt si disponible.
    """
    errors_dir.mkdir(parents=True, exist_ok=True)
    error_filename = chunk_name.replace(".txt", ".error.txt")
    error_path = errors_dir / error_filename

    lines = [
        f"Chunk      : {chunk_name}",
        f"Date       : {datetime.now().isoformat(timespec='seconds')}",
        f"Erreur     : {type(exc).__name__}: {exc}",
        "",
        "=== Traceback ===",
        tb,
    ]

    if prompt_excerpt:
        lines += [
            "",
            "=== Extrait du prompt (500 premiers caractères) ===",
            prompt_excerpt[:500],
        ]

    error_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[ai_processor] Fichier d'erreur écrit : {error_path}")


def process_project_chunks(project) -> None:
    """
    Traite les chunks IA pending d'un projet.

    Génère des fichiers Markdown dans sortie/<projet>/processed/
    et met à jour project_state.json à chaque chunk traité.

    En cas d'erreur sur un chunk :
    - le chunk est marqué "failed" dans project_state.json
    - un fichier d'erreur est écrit dans sortie/<projet>/errors/
    - les autres chunks continuent d'être traités

    Args:
        project: objet projet avec attribut .name (str ou Path)
    """
    project_output_dir = SORTIE_DIR / project.name
    chunks_dir = project_output_dir / "chunks"
    processed_dir = project_output_dir / "processed"
    errors_dir = project_output_dir / "errors"

    processed_dir.mkdir(parents=True, exist_ok=True)

    state = load_project_state(project.name)
    chunks_state = state.get("chunks", {})

    if not chunks_state:
        print(f"Aucun chunk enregistré pour le projet : {project.name}")
        return

    engine = get_ai_engine()
    print(f"Moteur IA actif : {engine.__class__.__name__}")

    for chunk_name, chunk in chunks_state.items():
        status   = chunk.get("status", "pending_ai")
        needs_ai = chunk.get("needs_ai_processing", True)

        chunk_path  = chunks_dir / chunk_name
        output_name = chunk_name.replace(".txt", ".md")
        output_path = processed_dir / output_name

        # ── Cas 0 : chunk sans contenu réel (en-tête seul) ───────────────
        if status == "skipped_empty":
            print(
                f"[ai_processing] {chunk_name} ignoré : "
                "aucun contenu réel (skipped_empty)"
            )
            continue

        # ── Cas 1 : chunk déjà traité et non modifié ──────────────────────
        # "done" + processed présent + pas de retraitement requis → ignorer
        if status == "done":
            if not needs_ai and output_path.exists():
                print(f"[ai_processor] {chunk_name} inchangé → ignoré")
                continue
            if output_path.exists():
                print(f"[ai_processor] {chunk_name} déjà traité → ignoré")
                continue
            # processed/ absent même si status=="done" → retraiter

        # ── Cas 2 : chunk inchangé avec processed/ existant ───────────────
        # Couvre aussi les anciens states avec status="pending" ou "pending_ai"
        # mais où le fichier processed existe déjà
        if not needs_ai and output_path.exists():
            if status not in ("done",):
                chunk["status"] = "done"
                chunk.pop("needs_ai_processing", None)
                save_project_state(project.name, state)
            print(f"[ai_processor] {chunk_name} inchangé, processed existant → ignoré")
            continue

        if not chunk_path.exists():
            print(f"[ai_processor] {chunk_name} introuvable sur disque")
            chunk["status"] = "failed"
            chunk["error"] = "chunk file not found"
            save_project_state(project.name, state)
            continue

        print(f"[ai_processor] Traitement IA : {chunk_name}")

        prompt_excerpt: str | None = None

        try:
            text = chunk_path.read_text(encoding="utf-8")
            text = _strip_chunk_metadata_header(text)

            # ── Garde : ne pas envoyer un chunk vide à l'IA ───────────────
            if not is_real_transcript_content(text):
                print(
                    f"[ai_processing] {chunk_name} ignoré : "
                    "aucun contenu réel détecté — chunk marqué skipped_empty"
                )
                chunk["status"] = "skipped_empty"
                chunk.pop("error", None)
                save_project_state(project.name, state)
                continue

            prompt = engine.build_prompt(text, project_name=project.name)
            prompt_excerpt = prompt[:500]

            result = engine.send_prompt(prompt)

            output_path.write_text(result, encoding="utf-8")

            chunk["status"] = "done"
            chunk["processed_file"] = str(output_path)
            chunk["processed_at"] = datetime.now().isoformat(timespec="seconds")
            chunk.pop("error", None)

            save_project_state(project.name, state)

            print(f"[ai_processing] {chunk_name} traité")

        except Exception as e:
            tb = traceback.format_exc()

            chunk["status"] = "failed"
            chunk["error"] = str(e)
            save_project_state(project.name, state)

            _write_chunk_error(errors_dir, chunk_name, e, tb, prompt_excerpt)
            print(f"Erreur traitement chunk {chunk_name} : {e}")


def process_single_chunk(project_name: str, chunk_name: str) -> bool:
    """
    Retraite un seul chunk d'un projet, quel que soit son statut actuel.

    Utile pour rejouer un chunk spécifique sans relancer tout le pipeline.

    Args:
        project_name: nom du projet (sous-dossier de sortie/)
        chunk_name:   nom du fichier chunk (ex. "chunk_045.txt")

    Returns:
        True si le traitement a réussi, False sinon.
    """
    project_output_dir = SORTIE_DIR / project_name
    chunks_dir = project_output_dir / "chunks"
    processed_dir = project_output_dir / "processed"
    errors_dir = project_output_dir / "errors"

    processed_dir.mkdir(parents=True, exist_ok=True)

    state = load_project_state(project_name)
    chunks_state = state.get("chunks", {})

    if chunk_name not in chunks_state:
        print(
            f"[reprocess] Chunk '{chunk_name}' absent de project_state.json "
            f"pour le projet '{project_name}'.\n"
            f"Chunks disponibles : {list(chunks_state.keys())}"
        )
        return False

    chunk_path = chunks_dir / chunk_name
    if not chunk_path.exists():
        print(f"[reprocess] Fichier chunk introuvable : {chunk_path}")
        return False

    output_name = chunk_name.replace(".txt", ".md")
    output_path = processed_dir / output_name

    engine = get_ai_engine()
    print(f"[reprocess] Moteur IA actif : {engine.__class__.__name__}")
    print(f"[reprocess] Retraitement du chunk : {chunk_name}")

    prompt_excerpt: str | None = None

    try:
        text = chunk_path.read_text(encoding="utf-8")
        text = _strip_chunk_metadata_header(text)

        # ── Garde : ne pas envoyer un chunk vide à l'IA ───────────────────
        if not is_real_transcript_content(text):
            print(
                f"[ai_processing] {chunk_name} ignoré : "
                "aucun contenu réel détecté — chunk marqué skipped_empty"
            )
            chunk = chunks_state[chunk_name]
            chunk["status"] = "skipped_empty"
            chunk.pop("error", None)
            save_project_state(project_name, state)
            return False

        prompt = engine.build_prompt(text, project_name=project_name)
        prompt_excerpt = prompt[:500]

        result = engine.send_prompt(prompt)

        output_path.write_text(result, encoding="utf-8")

        chunk = chunks_state[chunk_name]
        chunk["status"] = "done"
        chunk["processed_file"] = str(output_path)
        chunk["processed_at"] = datetime.now().isoformat(timespec="seconds")
        chunk.pop("error", None)

        save_project_state(project_name, state)

        print(f"[reprocess] Chunk retraité avec succès : {output_path}")
        return True

    except Exception as e:
        tb = traceback.format_exc()

        chunk = chunks_state[chunk_name]
        chunk["status"] = "failed"
        chunk["error"] = str(e)
        save_project_state(project_name, state)

        _write_chunk_error(errors_dir, chunk_name, e, tb, prompt_excerpt)
        print(f"[reprocess] Erreur lors du retraitement de {chunk_name} : {e}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Retraite un chunk spécifique d'un projet TranscriptionAI."
    )
    parser.add_argument("project_name", help="Nom du projet (ex: pastoral_retreat)")
    parser.add_argument(
        "--chunk",
        required=True,
        help="Nom du fichier chunk à retraiter (ex: chunk_045.txt)",
    )

    args = parser.parse_args()
    success = process_single_chunk(args.project_name, args.chunk)
    raise SystemExit(0 if success else 1)
