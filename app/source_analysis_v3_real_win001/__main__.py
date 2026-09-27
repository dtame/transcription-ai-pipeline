"""
CLI A.19 real V3 small WIN001 symbolic-handle canary.

Défaut : --dry-run (0 POST).
Réel : --authorization-scope SMALL_V21_V3_SYMBOLIC_WIN001_ONLY --window WIN001 --execute-real
"""

from __future__ import annotations

import json
import sys

from app.source_analysis_v3_real_win001.constants import (
    AUTHORIZATION_SCOPE,
    MODE,
    PHASE,
    PROJECT_NAME,
    WINDOW_ID,
)
from app.source_analysis_v3_real_win001.guard import RealV3Win001Error
from app.source_analysis_v3_real_win001.runner import run_real_v3_win001


def _usage() -> None:
    print(
        "Usage : python -m app.source_analysis_v3_real_win001 "
        "<projet> --authorization-scope SMALL_V21_V3_SYMBOLIC_WIN001_ONLY "
        "--window WIN001 --dry-run"
    )
    print(
        "Réel  : ... --authorization-scope SMALL_V21_V3_SYMBOLIC_WIN001_ONLY "
        "--window WIN001 --execute-real"
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0

    project_name = argv[0] if not argv[0].startswith("--") else PROJECT_NAME
    flags = argv[1:] if not argv[0].startswith("--") else argv
    scope = None
    window_id = WINDOW_ID
    dry_run = "--dry-run" in flags or "--execute-real" not in flags
    execute_real = "--execute-real" in flags
    tests = None
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
        if token in {"--dry-run", "--execute-real"}:
            index += 1
            continue
        print(f"[ERREUR] option inconnue : {token}")
        _usage()
        return 2

    if execute_real and "--dry-run" in flags:
        print("[ERREUR] --dry-run et --execute-real sont mutuellement exclusifs.")
        return 2

    print(f"[a19_real_v3_win001] projet={project_name}")
    print(f"[a19_real_v3_win001] phase={PHASE} mode={MODE}")
    print(f"[a19_real_v3_win001] scope={scope} window={window_id}")
    print(f"[a19_real_v3_win001] dry_run={dry_run} execute_real={execute_real}")

    try:
        result = run_real_v3_win001(
            project_name,
            dry_run=dry_run,
            execute_real=execute_real,
            authorization_scope=scope,
            window_id=window_id,
            allow_real_provider=bool(execute_real),
            write_artifacts=True,
            tests=tests,
        )
    except RealV3Win001Error as exc:
        print(f"[a19_real_v3_win001] rejected={exc}")
        print("[a19_real_v3_win001] STOP — revue humaine. Phase 3B INCOMPLETE.")
        return 2

    print(f"[a19_real_v3_win001] accepted={result.accepted} mode={result.mode}")
    if result.error:
        print(f"[a19_real_v3_win001] error={result.error}")
    print(f"[a19_real_v3_win001] generate_attempts={result.engine_generate_attempts}")
    print(f"[a19_real_v3_win001] anthropic_posts={result.anthropic_post_attempts}")
    if dry_run and not execute_real:
        safe = {
            "analysis_signature": result.preflight.get("analysis_signature"),
            "local_input_estimate": result.preflight.get("local_input_estimate"),
            "window": result.preflight.get("window"),
            "schema_hash": (result.preflight.get("schema_metrics") or {}).get("raw_hash"),
            "dry_run_twice": result.preflight.get("dry_run_twice"),
            "provider_calls": 0,
        }
        print(json.dumps(safe, ensure_ascii=False, indent=2))
    print("[a19_real_v3_win001] STOP — revue humaine. Phase 3B INCOMPLETE.")
    if result.blocked_precall or not result.accepted:
        return 2
    if execute_real:
        verdict = (result.execution or {}).get("result")
        return 0 if verdict == "PASS" else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
