"""
Invocation manuelle de la Phase 3A.1.2B — classification par lots FR <-> EN.

Usage : python -m app.semantic_batch.cli <nom_du_projet>
Exemple : python -m app.semantic_batch.cli pastoral_retreat_v2_validation

Comme app/semantic_canary/cli.py, ce module n'est branché nulle part
automatiquement. CE SCRIPT PEUT EFFECTUER PLUSIEURS APPELS RÉSEAU RÉELS vers
Anthropic (un par lot non déjà en cache — §22) : il ne doit être lancé
qu'après que la suite de tests complète soit verte (§35-36) et que le plan
de lots ait été inspecté (§17).
"""

from __future__ import annotations

import sys

from app.semantic_batch.errors import SemanticBatchError
from app.semantic_batch.planner import build_batch_plan, validate_batch_plan
from app.semantic_batch.runner import (
    load_and_validate_sources,
    run_semantic_batch_classification,
)
from app.semantic_batch.selection import select_needed_blocks, validate_needed_population


def _usage() -> None:
    print("Usage  : python -m app.semantic_batch.cli <nom_du_projet>")
    print("Exemple: python -m app.semantic_batch.cli pastoral_retreat_v2_validation")


def _print_plan_control(project_name: str) -> int:
    """§17 : imprime le plan de lots AVANT tout appel réseau. Retourne 0 si valide."""
    try:
        sources = load_and_validate_sources(project_name)
        selected = select_needed_blocks(sources["blocks"])
        expected = int(
            (sources["stats"].get("semantic_review_distribution") or {}).get("NEEDED", 0)
        )
        validate_needed_population(selected, expected_count=expected)
        plan = build_batch_plan(selected)
        validate_batch_plan(plan, selected)
    except SemanticBatchError as exc:
        print(f"[ERREUR] Plan invalide — STOP AVANT RÉSEAU : {exc}")
        return 1

    print(
        f"[semantic_batch] {len(selected)} bloc(s) NEEDED, "
        f"{len(plan)} lot(s) planifié(s) :"
    )
    for item in plan:
        print(
            f"  {item.batch_id} : {item.block_count} bloc(s), "
            f"~{item.estimated_input_tokens} tokens estimés"
        )

    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0

    project_name = argv[0]

    control_status = _print_plan_control(project_name)
    if control_status != 0:
        return control_status

    try:
        result = run_semantic_batch_classification(project_name)
    except SemanticBatchError as exc:
        print(f"[ERREUR] {type(exc).__name__} — STOP AVANT RÉSEAU : {exc}")
        return 1

    print(
        f"[semantic_batch] appels réels = {result.real_call_count}, "
        f"cache hits = {result.cache_hit_count}"
    )

    if not result.success:
        print(f"[semantic_batch] ÉCHEC au lot {result.stopped_at_batch} : {result.error}")
        return 1

    print(f"[semantic_batch] artefact publié : {result.artifact_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
