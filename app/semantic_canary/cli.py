"""
Invocation manuelle de la Phase 3A.1.2A — canary sémantique FR <-> EN.

Usage : python -m app.semantic_canary.cli <nom_du_projet>
Exemple : python -m app.semantic_canary.cli pastoral_retreat_v2_validation

Comme app/language_blocks/cli.py et app/language_cleanup/cli.py, ce module
n'est branché nulle part automatiquement. CE SCRIPT EFFECTUE UN APPEL RÉSEAU
RÉEL vers Anthropic s'il atteint cette étape (§33) : il ne doit être lancé
qu'après que la suite de tests complète soit verte (§31) et que la
sélection ait été inspectée (§14).
"""

from __future__ import annotations

import json
import sys

from app.semantic_canary.errors import SemanticCanaryError
from app.semantic_canary.runner import load_and_validate_sources, run_semantic_canary
from app.semantic_canary.selection import select_canary_blocks, validate_selection


def _usage() -> None:
    print("Usage  : python -m app.semantic_canary.cli <nom_du_projet>")
    print("Exemple: python -m app.semantic_canary.cli pastoral_retreat_v2_validation")


def _print_selection_control(project_name: str) -> int:
    """
    §14 : imprime la liste des 20 block_id sélectionnés AVANT tout appel
    réseau, et valide localement la sélection. Retourne 0 si valide.
    """
    try:
        sources = load_and_validate_sources(project_name)
        selected = select_canary_blocks(sources["blocks"])
        validate_selection(selected)
    except SemanticCanaryError as exc:
        print(f"[ERREUR] Sélection invalide — STOP AVANT RÉSEAU : {exc}")
        return 1

    print(f"[semantic_canary] {len(selected)} bloc(s) sélectionné(s) :")
    for block in selected:
        print(json.dumps(block.control_summary(), ensure_ascii=False, sort_keys=True))

    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0

    project_name = argv[0]

    control_status = _print_selection_control(project_name)
    if control_status != 0:
        return control_status

    try:
        result = run_semantic_canary(project_name)
    except SemanticCanaryError as exc:
        print(f"[ERREUR] {type(exc).__name__} — STOP AVANT RÉSEAU : {exc}")
        return 1

    print(f"[semantic_canary] appels réels effectués = {result.real_call_count}")

    if not result.success:
        print(f"[semantic_canary] ÉCHEC : {result.error.to_dict() if result.error else 'inconnu'}")
        if result.cost_record is not None:
            print(f"[semantic_canary] usage préservé : {result.cost_record.to_dict()}")
        return 1

    print(f"[semantic_canary] artefact publié : {result.artifact_path}")
    print(
        "[semantic_canary] usage : "
        f"input={result.response.input_tokens} "
        f"output={result.response.output_tokens} "
        f"latency_ms={result.response.latency_ms}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
