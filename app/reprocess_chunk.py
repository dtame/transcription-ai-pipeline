"""
Outil de retraitement d'un chunk individuel.

Permet de relancer le traitement IA d'un seul chunk sans relancer
tout le pipeline du projet.

Usage :
    python -m app.reprocess_chunk <project_name> --chunk <chunk_name>

Exemples :
    python -m app.reprocess_chunk pastoral_retreat --chunk chunk_045.txt
    python -m app.reprocess_chunk pastoral_retreat --chunk chunk_045.txt --reset-failed
    python -m app.reprocess_chunk pastoral_retreat --list-failed

Options :
    --chunk <nom>       Retraiter un chunk spécifique (ex: chunk_045.txt)
    --list-failed       Lister les chunks en échec pour ce projet
    --reset-failed      Retraiter TOUS les chunks en échec du projet
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai_processor import process_single_chunk
from app.project_state import load_project_state


def list_failed_chunks(project_name: str) -> list[str]:
    """Retourne la liste des chunks en échec pour un projet."""
    state = load_project_state(project_name)
    return [
        name
        for name, info in state.get("chunks", {}).items()
        if info.get("status") == "failed"
    ]


def reset_all_failed(project_name: str) -> dict:
    """
    Retraite tous les chunks en échec d'un projet.

    Returns:
        Dictionnaire {chunk_name: True/False} avec le résultat par chunk.
    """
    failed = list_failed_chunks(project_name)

    if not failed:
        print(f"[reprocess] Aucun chunk en échec pour le projet '{project_name}'.")
        return {}

    print(f"[reprocess] {len(failed)} chunk(s) en échec à retraiter : {failed}")

    results = {}
    for chunk_name in failed:
        results[chunk_name] = process_single_chunk(project_name, chunk_name)

    success_count = sum(1 for v in results.values() if v)
    fail_count = len(results) - success_count

    print(f"\n[reprocess] Résultat : {success_count} réussi(s), {fail_count} échoué(s)")
    return results


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Retraite un ou plusieurs chunks d'un projet TranscriptionAI "
            "sans relancer tout le pipeline."
        )
    )
    parser.add_argument(
        "project_name",
        help="Nom du projet (ex: pastoral_retreat)",
    )
    parser.add_argument(
        "--chunk",
        help="Nom du chunk à retraiter (ex: chunk_045.txt)",
        default=None,
    )
    parser.add_argument(
        "--list-failed",
        action="store_true",
        help="Lister les chunks en échec pour ce projet",
    )
    parser.add_argument(
        "--reset-failed",
        action="store_true",
        help="Retraiter tous les chunks en échec du projet",
    )

    args = parser.parse_args()

    if args.list_failed:
        failed = list_failed_chunks(args.project_name)
        if failed:
            print(f"Chunks en échec pour '{args.project_name}' ({len(failed)}) :")
            for name in failed:
                state = load_project_state(args.project_name)
                error = state["chunks"][name].get("error", "inconnu")
                print(f"  - {name}  →  {error}")
        else:
            print(f"Aucun chunk en échec pour '{args.project_name}'.")
        sys.exit(0)

    if args.reset_failed:
        results = reset_all_failed(args.project_name)
        all_ok = all(results.values()) if results else True
        sys.exit(0 if all_ok else 1)

    if args.chunk:
        success = process_single_chunk(args.project_name, args.chunk)
        sys.exit(0 if success else 1)

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
