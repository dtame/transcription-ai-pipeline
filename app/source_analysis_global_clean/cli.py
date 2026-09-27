"""
Invocation manuelle du Source Analyzer global CLEAN — Phase 3B Final.

Usage :
    python -m app.source_analysis_global_clean.cli <projet> --dry-run
    python -m app.source_analysis_global_clean.cli <projet> --real-call

`--dry-run` (défaut) s'arrête avant tout appel réseau.
`--real-call` effectue AU PLUS un appel Anthropic. Pas de retry, pas de fallback.
"""

from __future__ import annotations

import sys

from app.source_analysis_global_clean.errors import GlobalCleanError
from app.source_analysis_global_clean.runner import run_global_clean_source_analysis


def _usage() -> None:
    print(
        "Usage  : python -m app.source_analysis_global_clean.cli "
        "<projet> --dry-run"
    )
    print(
        "         python -m app.source_analysis_global_clean.cli "
        "<projet> --real-call"
    )
    print("Défaut : --dry-run (0 appel réseau).")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0

    project_name = argv[0]
    flags = set(argv[1:])
    allowed = {"--dry-run", "--real-call"}
    unknown = flags - allowed
    if unknown:
        print(f"[ERREUR] option(s) inconnue(s) : {sorted(unknown)}")
        _usage()
        return 2

    if "--dry-run" in flags and "--real-call" in flags:
        print("[ERREUR] --dry-run et --real-call sont mutuellement exclusifs.")
        return 2

    dry_run = "--real-call" not in flags

    print(f"[global_clean] projet={project_name}")
    print(f"[global_clean] mode={'DRY_RUN' if dry_run else 'REAL_CALL'}")
    print("[global_clean] max_real_calls=1 max_attempts=1 provider=anthropic")
    print("[global_clean] prompt=1.3 transport=semantic-transport-v1 Generation C")
    print("[global_clean] aucun fallback, aucun retry, aucun second appel")

    try:
        result = run_global_clean_source_analysis(project_name, dry_run=dry_run)
    except GlobalCleanError as exc:
        print(f"[ERREUR] {type(exc).__name__} - STOP : {exc}")
        return 1

    print(f"[global_clean] outcome={result.outcome}")
    print(
        f"[global_clean] pipeline={result.pipeline_result} "
        f"generation={result.provider_generation} "
        f"published={result.source_map_published}"
    )
    print(
        f"[global_clean] segments={result.segment_count} "
        f"words={result.word_count} "
        f"est_tokens={result.estimated_tokens}"
    )
    print(
        f"[global_clean] would_call_ai={result.would_call_ai} "
        f"actual_real_calls={result.actual_real_calls}"
    )
    if result.error_type:
        print(f"[global_clean] error={result.error_type}")
    print(
        f"[global_clean] source_map={result.source_map_published} "
        f"protected_unchanged={result.protected_unchanged}"
    )
    print("[global_clean] STOP - revue humaine. Aucune Phase 4.")
    return 0 if result.outcome in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    sys.exit(main())
