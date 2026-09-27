"""
CLI offline 3B.7.2.

Usage :
    python -m app.source_analysis_window_pipeline.cli <projet>

Aucun --real-call. Aucun engine.generate() vers un provider réel.
"""

from __future__ import annotations

import sys

from app.source_analysis_window_pipeline.constants import MODE, PHASE
from app.source_analysis_window_pipeline.runner import run_window_pipeline


def _usage() -> None:
    print("Usage  : python -m app.source_analysis_window_pipeline.cli <projet>")
    print("Mode   : OFFLINE_FAKE_AI. Aucun --real-call. 0 appel réseau réel.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0
    if "--real-call" in argv:
        print("[ERREUR] --real-call est interdit. Cette phase est OFFLINE_FAKE_AI.")
        return 2
    project_name = argv[0]
    flags = set(argv[1:])
    if flags:
        print(f"[ERREUR] option(s) inconnue(s) : {sorted(flags)}")
        _usage()
        return 2

    print(f"[window_pipeline] projet={project_name}")
    print(f"[window_pipeline] phase={PHASE} mode={MODE}")
    print("[window_pipeline] FakeAI only — aucun Anthropic, aucun Attempt #3")

    result = run_window_pipeline(project_name)
    print(f"[window_pipeline] outcome={result.outcome}")
    print(f"[window_pipeline] artifact_sha={result.artifact_sha256}")
    print(f"[window_pipeline] deterministic={result.deterministic}")
    print(
        f"[window_pipeline] state={result.project_state_status} "
        f"error={result.project_state_error}"
    )
    print(f"[window_pipeline] protected_unchanged={result.protected_unchanged}")
    print("[window_pipeline] STOP — revue humaine. Phase 3B INCOMPLETE.")
    return 0 if result.outcome in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    sys.exit(main())
