"""
Orchestration du traitement IA des chunks de transcription.

Ce module ne connaît pas le moteur IA utilisé.
Il délègue le traitement à get_ai_engine() qui retourne
le moteur configuré dans app/config.py (AI_PROVIDER).

Pipeline :
    1. Charger project_state.json
    2. Pour chaque chunk à l'état "pending" :
       a. Lire le texte brut depuis sortie/<projet>/chunks/
       b. Appeler engine.process(text)
       c. Écrire le Markdown dans sortie/<projet>/processed/
       d. Mettre à jour project_state.json (status, chemin, timestamp)
    3. Les chunks déjà "done" sont ignorés (reprise après interruption)
    4. Les erreurs sont enregistrées sans interrompre les autres chunks
"""

from datetime import datetime

from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state
from app.ai_engine import get_ai_engine


def process_project_chunks(project) -> None:
    """
    Traite les chunks IA pending d'un projet.

    Génère des fichiers Markdown dans sortie/<projet>/processed/
    et met à jour project_state.json à chaque chunk traité.

    Args:
        project: objet projet avec attribut .name (str ou Path)
    """
    project_output_dir = SORTIE_DIR / project.name
    chunks_dir = project_output_dir / "chunks"
    processed_dir = project_output_dir / "processed"

    processed_dir.mkdir(parents=True, exist_ok=True)

    state = load_project_state(project.name)
    chunks_state = state.get("chunks", {})

    if not chunks_state:
        print(f"Aucun chunk enregistré pour le projet : {project.name}")
        return

    engine = get_ai_engine()
    print(f"Moteur IA actif : {engine.__class__.__name__}")

    for chunk_name, chunk in chunks_state.items():
        status = chunk.get("status", "pending")

        if status == "done":
            print(f"Chunk déjà traité, ignoré : {chunk_name}")
            continue

        chunk_path = chunks_dir / chunk_name
        output_name = chunk_name.replace(".txt", ".md")
        output_path = processed_dir / output_name

        if not chunk_path.exists():
            print(f"Chunk introuvable : {chunk_path}")
            chunk["status"] = "failed"
            chunk["error"] = "chunk file not found"
            save_project_state(project.name, state)
            continue

        print(f"Traitement IA du chunk : {chunk_name}")

        try:
            text = chunk_path.read_text(encoding="utf-8")
            result = engine.process(text, project_name=project.name)

            output_path.write_text(result, encoding="utf-8")

            chunk["status"] = "done"
            chunk["processed_file"] = str(output_path)
            chunk["processed_at"] = datetime.now().isoformat(timespec="seconds")

            save_project_state(project.name, state)

            print(f"Chunk traité : {output_path}")

        except Exception as e:
            chunk["status"] = "failed"
            chunk["error"] = str(e)
            save_project_state(project.name, state)

            print(f"Erreur traitement chunk {chunk_name} : {e}")
