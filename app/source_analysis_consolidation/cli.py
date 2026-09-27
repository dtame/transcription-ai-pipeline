"""
CLI offline 3B.7.4.

Usage :
    python -m app.source_analysis_consolidation.cli <projet>

Aucun --real-call. Aucun engine.generate() vers un provider réel.
"""

from __future__ import annotations

import sys

from app.source_analysis_consolidation.constants import MODE, PHASE
from app.source_analysis_consolidation.runner import run_consolidation_pipeline


def _usage() -> None:
    print("Usage  : python -m app.source_analysis_consolidation.cli <projet>")
    print("Mode   : OFFLINE_CONSOLIDATION_FAKE_AI. Aucun --real-call. 0 appel réseau réel.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0
    if "--real-call" in argv:
        print("[ERREUR] --real-call est interdit. Cette phase est OFFLINE_CONSOLIDATION_FAKE_AI.")
        return 2
    project_name = argv[0]
    flags = set(argv[1:])
    if flags:
        print(f"[ERREUR] option(s) inconnue(s) : {sorted(flags)}")
        _usage()
        return 2

    print(f"[consolidation] projet={project_name}")
    print(f"[consolidation] phase={PHASE} mode={MODE}")
    print("[consolidation] FakeAI only — aucun Anthropic, aucun Attempt #3")

    result = run_consolidation_pipeline(project_name)
    print(f"[consolidation] outcome={result.outcome}")
    print(f"[consolidation] artifact_sha={result.artifact_sha256}")
    print(f"[consolidation] deterministic={result.deterministic}")
    print(
        f"[consolidation] state={result.project_state_status} "
        f"error={result.project_state_error}"
    )
    print(f"[consolidation] protected_unchanged={result.protected_unchanged}")
    print("[consolidation] STOP — revue humaine. Phase 3B INCOMPLETE.")
    return 0 if result.outcome in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    sys.exit(main())
