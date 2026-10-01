"""
CLI A.28 remaining five real local-lite windows.

Défaut : --dry-run (0 POST).
Réel : --authorization-scope SMALL_V21_V31_LOCAL_LITE_REMAINING_FIVE_ONLY --execute-real
"""

from __future__ import annotations

import json
import sys

from app.source_analysis_v31_remaining_windows.constants import (
    AUTHORIZATION_SCOPE,
    MODE,
    PHASE,
    PROJECT_NAME,
)
from app.source_analysis_v31_remaining_windows.guard import RemainingWindowsError
from app.source_analysis_v31_remaining_windows.runner import run_remaining_windows


def _usage() -> None:
    print(
        "Usage : python -m app.source_analysis_v31_remaining_windows "
        "<projet> --authorization-scope SMALL_V21_V31_LOCAL_LITE_REMAINING_FIVE_ONLY "
        "--dry-run"
    )
    print(
        "Réel  : ... --authorization-scope SMALL_V21_V31_LOCAL_LITE_REMAINING_FIVE_ONLY "
        "--execute-real"
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0

    project_name = argv[0] if not argv[0].startswith("--") else PROJECT_NAME
    flags = argv[1:] if not argv[0].startswith("--") else argv
    scope = None
    window_id = None
    dry_run = "--dry-run" in flags or "--execute-real" not in flags
    execute_real = "--execute-real" in flags
    tests = None
    max_windows = None
    index = 0
    while index < len(flags):
        token = flags[index]
        if token == "--authorization-scope":
            if index + 1 >= len(flags):
                print("[ERREUR] --authorization-scope exige une valeur.")
                return 2
            scope = flags[index + 1]
            index += 2
            continue
        if token == "--window":
            if index + 1 >= len(flags):
                print("[ERREUR] --window exige une valeur.")
                return 2
            window_id = flags[index + 1]
            index += 2
            continue
        if token == "--tests":
            if index + 1 >= len(flags):
                print("[ERREUR] --tests exige une valeur.")
                return 2
            tests = flags[index + 1]
            index += 2
            continue
        if token == "--max-windows":
            if index + 1 >= len(flags):
                print("[ERREUR] --max-windows exige une valeur.")
                return 2
            max_windows = int(flags[index + 1])
            index += 2
            continue
        if token in {"--dry-run", "--execute-real"}:
            index += 1
            continue
        print(f"[ERREUR] option inconnue : {token}")
        _usage()
        return 2

    if execute_real and "--dry-run" in flags:
        print("[ERREUR] --dry-run et --execute-real sont mutuellement exclusifs.")
        return 2
    if execute_real and window_id is not None:
        print("[ERREUR] --window is forbidden with --execute-real; order is fixed.")
        return 2

    print(f"[a28_remaining] projet={project_name}")
    print(f"[a28_remaining] phase={PHASE} mode={MODE}")
    print(f"[a28_remaining] scope={scope or AUTHORIZATION_SCOPE} window={window_id}")
    print(f"[a28_remaining] dry_run={dry_run} execute_real={execute_real}")

    try:
        result = run_remaining_windows(
            project_name,
            dry_run=dry_run,
            execute_real=execute_real,
            authorization_scope=scope,
            window_id=window_id,
            allow_real_provider=bool(execute_real),
            write_artifacts=True,
            tests=tests,
            max_windows=max_windows,
        )
    except RemainingWindowsError as exc:
        print(f"[a28_remaining] rejected={exc}")
        print("[a28_remaining] STOP — revue humaine. Phase 3B INCOMPLETE.")
        return 2

    print(f"[a28_remaining] accepted={result.accepted} mode={result.mode}")
    print(f"[a28_remaining] phase_result={result.phase_result}")
    if result.error:
        print(f"[a28_remaining] error={result.error}")
    print(f"[a28_remaining] generate_attempts={result.engine_generate_attempts}")
    print(f"[a28_remaining] anthropic_posts={result.anthropic_post_attempts}")
    print(f"[a28_remaining] stopped_at={result.stopped_at}")
    print(f"[a28_remaining] ready_after={result.ready_after_count} / 7")
    if dry_run and not execute_real:
        safe = {
            "windows": {
                window_id: {
                    "analysis_signature": row.get("analysis_signature"),
                    "local_input_estimate": row.get("local_input_estimate"),
                    "src_range": row.get("src_range"),
                    "cache": (row.get("cache") or {}).get("status"),
                }
                for window_id, row in (result.preflight.get("windows") or {}).items()
            },
            "schema_hash": (result.preflight.get("schema_metrics") or {}).get("raw_hash"),
            "provider_calls": 0,
        }
        print(json.dumps(safe, ensure_ascii=True, indent=2))
    print("[a28_remaining] STOP — revue humaine. Phase 3B INCOMPLETE.")
    if result.blocked_precall or not result.accepted:
        return 2
    if execute_real:
        return 0 if result.phase_result == "PASS" else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
