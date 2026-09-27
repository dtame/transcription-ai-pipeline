"""
CLI offline 3B.7.6 — audit de readiness uniquement.

Usage :
    python -m app.source_analysis_hybrid_readiness.cli <projet>

Aucun --execute-real. Aucun engine.generate() vers un provider réel.
"""

from __future__ import annotations

import sys

from app.source_analysis_hybrid_readiness.constants import MODE, PHASE
from app.source_analysis_hybrid_readiness.runner import run_hybrid_readiness_audit


def _usage() -> None:
    print("Usage  : python -m app.source_analysis_hybrid_readiness.cli <projet>")
    print("Mode   : OFFLINE_PRODUCTION_READINESS. 0 appel réseau réel.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0
    forbidden = {"--real-call", "--execute-real", "--authorize-real-call"}
    if forbidden.intersection(argv):
        print("[ERREUR] exécution réelle interdite. Cette phase est OFFLINE.")
        return 2
    project_name = argv[0]
    flags = set(argv[1:])
    if flags:
        print(f"[ERREUR] option(s) inconnue(s) : {sorted(flags)}")
        _usage()
        return 2

    print(f"[hybrid_readiness] projet={project_name}")
    print(f"[hybrid_readiness] phase={PHASE} mode={MODE}")
    print("[hybrid_readiness] dry-run only — aucun Anthropic, aucun WIN001 réel")

    result = run_hybrid_readiness_audit(project_name)
    print(f"[hybrid_readiness] outcome={result.outcome}")
    print(f"[hybrid_readiness] readiness={result.readiness_status}")
    print(f"[hybrid_readiness] artifact_sha={result.artifact_sha256}")
    print(f"[hybrid_readiness] deterministic={result.deterministic}")
    print(
        f"[hybrid_readiness] state={result.project_state_status} "
        f"error={result.project_state_error}"
    )
    print(f"[hybrid_readiness] protected_unchanged={result.protected_unchanged}")
    print("[hybrid_readiness] STOP — revue humaine. Phase 3B INCOMPLETE.")
    return 0 if result.outcome in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    sys.exit(main())
