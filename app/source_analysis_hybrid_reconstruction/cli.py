"""
CLI offline 3B.7.5.

Usage :
    python -m app.source_analysis_hybrid_reconstruction.cli <projet>

Aucun --real-call. Aucun engine.generate() vers un provider réel.
"""

from __future__ import annotations

import sys

from app.source_analysis_hybrid_reconstruction.constants import MODE, PHASE
from app.source_analysis_hybrid_reconstruction.runner import (
    run_hybrid_reconstruction_pipeline,
)


def _usage() -> None:
    print(
        "Usage  : python -m app.source_analysis_hybrid_reconstruction.cli <projet>"
    )
    print(
        "Mode   : OFFLINE_HYBRID_END_TO_END_FAKE_AI. "
        "Aucun --real-call. 0 appel réseau réel."
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0
    if "--real-call" in argv:
        print(
            "[ERREUR] --real-call est interdit. "
            "Cette phase est OFFLINE_HYBRID_END_TO_END_FAKE_AI."
        )
        return 2
    project_name = argv[0]
    flags = set(argv[1:])
    if flags:
        print(f"[ERREUR] option(s) inconnue(s) : {sorted(flags)}")
        _usage()
        return 2

    print(f"[hybrid-reconstruction] projet={project_name}")
    print(f"[hybrid-reconstruction] phase={PHASE} mode={MODE}")
    print("[hybrid-reconstruction] FakeAI only — aucun Anthropic, aucun WIN réel")

    result = run_hybrid_reconstruction_pipeline(project_name)
    print(f"[hybrid-reconstruction] outcome={result.outcome}")
    print(f"[hybrid-reconstruction] artifact_sha={result.artifact_sha256}")
    print(f"[hybrid-reconstruction] deterministic={result.deterministic}")
    print(
        f"[hybrid-reconstruction] state={result.project_state_status} "
        f"error={result.project_state_error}"
    )
    print(f"[hybrid-reconstruction] protected_unchanged={result.protected_unchanged}")
    print("[hybrid-reconstruction] STOP — revue humaine. Phase 3B INCOMPLETE.")
    return 0 if result.outcome in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    sys.exit(main())
