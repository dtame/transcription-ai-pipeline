"""
CLI offline 3B.7.1.

Usage :
    python -m app.source_analysis_hybrid.cli <projet>

Aucun --real-call. Aucun engine.generate(). Aucun réseau.
"""

from __future__ import annotations

import sys
from app.source_analysis_hybrid.constants import MODE, PHASE
from app.source_analysis_hybrid.runner import run_window_planner_implementation


def _usage() -> None:
    print("Usage  : python -m app.source_analysis_hybrid.cli <projet>")
    print("Mode   : OFFLINE_IMPLEMENTATION. Aucun --real-call. 0 appel réseau.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0
    if "--real-call" in argv:
        print("[ERREUR] --real-call est interdit. Cette phase est OFFLINE.")
        return 2
    project_name = argv[0]
    flags = set(argv[1:])
    if flags:
        print(f"[ERREUR] option(s) inconnue(s) : {sorted(flags)}")
        _usage()
        return 2

    print(f"[window_planner_v2] projet={project_name}")
    print(f"[window_planner_v2] phase={PHASE} mode={MODE}")
    print("[window_planner_v2] aucun engine.generate(), aucun réseau, aucun Attempt #3")

    result = run_window_planner_implementation(project_name)
    print(f"[window_planner_v2] outcome={result.outcome}")
    print(f"[window_planner_v2] plan_sha={result.plan_sha256}")
    print(f"[window_planner_v2] artifact_sha={result.artifact_sha256}")
    print(f"[window_planner_v2] deterministic={result.deterministic}")
    print(
        f"[window_planner_v2] state={result.project_state_status} "
        f"error={result.project_state_error}"
    )
    print(f"[window_planner_v2] protected_unchanged={result.protected_unchanged}")
    print("[window_planner_v2] STOP — revue humaine. Phase 3B INCOMPLETE.")
    return 0 if result.outcome in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    sys.exit(main())
