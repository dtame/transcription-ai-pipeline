"""
Invocation manuelle de la Phase 3A.2A — simulation des politiques de
nettoyage linguistique.

Usage : python -m app.cleanup_policy.cli <nom_du_projet>
Exemple : python -m app.cleanup_policy.cli pastoral_retreat_v2_validation

ZÉRO appel réseau (§3, §43) : ce script ne fait qu'agréger des artefacts
déjà présents sur disque. Il n'écrit qu'un seul nouveau fichier :
sortie/<projet>/audit/cleanup_policy_simulation.json — les cinq sources
protégées ne sont jamais ouvertes en écriture.
"""

from __future__ import annotations

import sys

from app.cleanup_policy.constants import (
    POLICY_IDS,
    REAL_PROJECT_EXPECTED_NO_ENGLISH_CONTEXT,
    REAL_PROJECT_EXPECTED_PHASE_3A1_RESOLVED,
    REAL_PROJECT_EXPECTED_SEMANTIC_BATCH,
    REAL_PROJECT_EXPECTED_TOTAL,
    REAL_PROJECT_NAME,
)
from app.cleanup_policy.errors import CleanupPolicyError
from app.cleanup_policy.runner import run_cleanup_policy_simulation


def _usage() -> None:
    print("Usage  : python -m app.cleanup_policy.cli <nom_du_projet>")
    print("Exemple: python -m app.cleanup_policy.cli pastoral_retreat_v2_validation")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0

    project_name = argv[0]

    expected_kwargs: dict = {}
    if project_name == REAL_PROJECT_NAME:
        expected_kwargs = {
            "expected_total": REAL_PROJECT_EXPECTED_TOTAL,
            "expected_semantic_batch": REAL_PROJECT_EXPECTED_SEMANTIC_BATCH,
            "expected_phase_3a1_resolved": REAL_PROJECT_EXPECTED_PHASE_3A1_RESOLVED,
            "expected_no_english_context": REAL_PROJECT_EXPECTED_NO_ENGLISH_CONTEXT,
        }

    try:
        result = run_cleanup_policy_simulation(project_name, **expected_kwargs)
    except CleanupPolicyError as exc:
        print(f"[ERREUR] {type(exc).__name__} — STOP : {exc}")
        return 1

    totals = result.artifact["statistics"]["global_totals"]
    population = result.artifact["population"]

    print(f"[cleanup_policy] population totale = {population['total']}")
    print(
        f"[cleanup_policy]   SEMANTIC_BATCH={population['semantic_batch']} "
        f"PHASE_3A1_RESOLVED={population['phase_3a1_resolved']} "
        f"NO_ENGLISH_CONTEXT={population['no_english_context']}"
    )

    for policy_id in POLICY_IDS:
        stats = totals[policy_id]
        print(
            f"[cleanup_policy] {policy_id} : "
            f"AUTO_REMOVE={stats['auto_remove_blocks']} "
            f"HUMAN_REVIEW={stats['human_review_blocks']} "
            f"KEEP={stats['keep_blocks']} "
            f"(SRC retirés={stats['auto_remove_fr_src_count']}, "
            f"mots retirés={stats['auto_remove_words']})"
        )

    safe_consensus = result.artifact["statistics"]["safe_consensus_candidate"]
    print(f"[cleanup_policy] SAFE_CONSENSUS_CANDIDATE = {safe_consensus['count']}")

    print(f"[cleanup_policy] artefact publié : {result.artifact_path}")
    print("[cleanup_policy] STOP — aucune suppression réelle, en attente de revue humaine.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
