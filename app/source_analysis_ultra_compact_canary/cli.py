"""
Invocation manuelle du canary de grammaire 3B.4.3.

Usage :
    python -m app.source_analysis_ultra_compact_canary.cli <projet> --dry-run
    python -m app.source_analysis_ultra_compact_canary.cli <projet> --real-call

`--dry-run` (défaut) s'arrête avant tout appel réseau.
`--real-call` effectue AU PLUS un appel Anthropic. Pas de retry, pas de fallback.
"""

from __future__ import annotations

import sys

from app.source_analysis_ultra_compact_canary.errors import UltraCompactCanaryError
from app.source_analysis_ultra_compact_canary.runner import run_ultra_compact_canary


def _usage() -> None:
    print("Usage  : python -m app.source_analysis_ultra_compact_canary.cli <projet> --dry-run")
    print("         python -m app.source_analysis_ultra_compact_canary.cli <projet> --real-call")
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

    print(f"[ultra_compact_canary] projet={project_name}")
    print(f"[ultra_compact_canary] mode={'DRY_RUN' if dry_run else 'REAL_CALL'}")
    print("[ultra_compact_canary] max_real_calls=1 max_attempts=1 provider=anthropic")
    print("[ultra_compact_canary] transport=semantic-transport-v1 Generation C")
    print("[ultra_compact_canary] aucun fallback, aucun retry, aucun second appel")

    try:
        result = run_ultra_compact_canary(project_name, dry_run=dry_run)
    except UltraCompactCanaryError as exc:
        print(f"[ERREUR] {type(exc).__name__} - STOP : {exc}")
        return 1

    print(f"[ultra_compact_canary] outcome={result.outcome}")
    print(
        f"[ultra_compact_canary] grammar={result.server_grammar_result} "
        f"acceptance={result.server_grammar_acceptance} "
        f"pipeline={result.pipeline_result}"
    )
    print(
        f"[ultra_compact_canary] segments={result.selected_segment_count} "
        f"words={result.selected_word_count} "
        f"est_tokens={result.estimated_input_tokens}"
    )
    print(
        f"[ultra_compact_canary] would_call_ai={result.would_call_ai} "
        f"actual_real_calls={result.actual_real_calls}"
    )
    if result.error_type:
        print(f"[ultra_compact_canary] error={result.error_type}")
    print(
        f"[ultra_compact_canary] production_source_map={result.production_source_map_created} "
        f"protected_unchanged={result.protected_unchanged}"
    )
    print("[ultra_compact_canary] STOP - revue humaine avant tout Source Analyzer global.")
    return 0 if result.outcome in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    sys.exit(main())
