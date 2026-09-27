"""
Invocation de l'essai #2 du Source Analyzer global CLEAN.

Usage :
    python -m app.source_analysis_global_clean_attempt2.cli <projet> --dry-run
    python -m app.source_analysis_global_clean_attempt2.cli <projet> --real-call

`--dry-run` (défaut) s'arrête avant tout appel réseau.
`--real-call` effectue AU PLUS un appel Anthropic. Pas de retry, pas de fallback,
pas d'essai #3.
"""

from __future__ import annotations

import sys

from app.source_analysis_global_clean.errors import GlobalCleanError
from app.source_analysis_global_clean_attempt2.runner import (
    format_pre_call_snapshot,
    run_global_clean_attempt2,
)


def _usage() -> None:
    print(
        "Usage  : python -m app.source_analysis_global_clean_attempt2.cli "
        "<projet> --dry-run"
    )
    print(
        "         python -m app.source_analysis_global_clean_attempt2.cli "
        "<projet> --real-call"
    )
    print("Défaut : --dry-run (0 appel réseau).")
    print("GLOBAL_ATTEMPT_NUMBER = 2. Timeouts process-scoped 30 / 7200.")


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

    print("[attempt2] GLOBAL_ATTEMPT_NUMBER = 2")
    print(f"[attempt2] projet={project_name}")
    print(f"[attempt2] mode={'DRY_RUN' if dry_run else 'REAL_CALL'}")
    print("[attempt2] provider=anthropic model=claude-sonnet-5")
    print("[attempt2] connect=30 read=7200 source=stage_env (process-scoped)")
    print("[attempt2] max_real_calls=1 max_attempts=1 retry=false fallback=none")
    print("[attempt2] third_timeout_escalation=PROHIBITED")
    print("[attempt2] prompt=1.3 transport=semantic-transport-v1 Generation C")
    print("[attempt2] aucun .env réel modifié")

    try:
        result = run_global_clean_attempt2(project_name, dry_run=dry_run)
    except GlobalCleanError as exc:
        print(f"[ERREUR] {type(exc).__name__} - STOP : {exc}")
        return 1

    print("[attempt2] --- PRE-CALL SNAPSHOT ---")
    print(format_pre_call_snapshot(result), end="")
    print("[attempt2] --- END SNAPSHOT ---")
    print(f"[attempt2] outcome={result.outcome}")
    print(
        f"[attempt2] pipeline={result.pipeline_result} "
        f"generation={result.provider_generation} "
        f"published={result.source_map_published}"
    )
    print(
        f"[attempt2] segments={result.segment_count} "
        f"words={result.word_count} "
        f"est_tokens={result.estimated_tokens}"
    )
    print(
        f"[attempt2] connect={result.effective_connect_timeout_seconds} "
        f"({result.connect_source}) "
        f"read={result.effective_read_timeout_seconds} "
        f"({result.read_source})"
    )
    print(
        f"[attempt2] would_call_ai={result.would_call_ai} "
        f"actual_real_calls={result.actual_real_calls}"
    )
    if result.error_type:
        print(
            f"[attempt2] error={result.error_type} "
            f"timeout_kind={result.timeout_kind}"
        )
    print(
        f"[attempt2] source_map={result.source_map_published} "
        f"protected_unchanged={result.protected_unchanged}"
    )
    print(f"[attempt2] next_action={result.next_action or 'n/a'}")
    print("[attempt2] STOP - revue humaine. Aucune Phase 4. Aucun essai #3.")
    return 0 if result.outcome in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    sys.exit(main())
