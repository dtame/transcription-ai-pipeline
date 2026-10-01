"""
CLI Phase 4A.1 Editorial Planner tiny grammar + contract canary.

Défaut : --dry-run (0 POST).
Réel : --authorization-scope EDITORIAL_PLANNER_4A1_TINY_GRAMMAR_CONTRACT_CANARY_ONLY --execute-real
"""

from __future__ import annotations

import json
import sys

from app.editorial_planner_canary_4a1.constants import AUTHORIZATION_SCOPE, PHASE
from app.editorial_planner_canary_4a1.guard import PlannerCanaryError
from app.editorial_planner_canary_4a1.runner import run_canary


def _usage() -> None:
    print(
        "Usage : python -m app.editorial_planner_canary_4a1 "
        "--authorization-scope "
        "EDITORIAL_PLANNER_4A1_TINY_GRAMMAR_CONTRACT_CANARY_ONLY --dry-run"
    )
    print(
        "Réel  : python -m app.editorial_planner_canary_4a1 "
        "--authorization-scope "
        "EDITORIAL_PLANNER_4A1_TINY_GRAMMAR_CONTRACT_CANARY_ONLY --execute-real"
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0

    flags = argv
    scope = None
    dry_run = "--dry-run" in flags or "--execute-real" not in flags
    execute_real = "--execute-real" in flags
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
        if token in {"--dry-run", "--execute-real"}:
            index += 1
            continue
        print(f"[ERREUR] option inconnue : {token}")
        _usage()
        return 2

    if execute_real and "--dry-run" in flags:
        print("[ERREUR] --dry-run et --execute-real sont mutuellement exclusifs.")
        return 2

    print(f"[editorial_planner_canary_4a1] phase={PHASE}")
    print(f"[editorial_planner_canary_4a1] scope={scope}")
    print(
        f"[editorial_planner_canary_4a1] dry_run={dry_run} execute_real={execute_real}"
    )

    try:
        result = run_canary(
            dry_run=dry_run,
            execute_real=execute_real,
            authorization_scope=scope,
            allow_real_provider=bool(execute_real),
            write_artifacts=True,
        )
    except PlannerCanaryError as exc:
        print(f"[editorial_planner_canary_4a1] rejected={exc}")
        print("[editorial_planner_canary_4a1] STOP — revue humaine.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(f"[editorial_planner_canary_4a1] accepted={result.accepted} mode={result.mode}")
    print(f"[editorial_planner_canary_4a1] result={header.get('result')}")
    if result.error:
        print(f"[editorial_planner_canary_4a1] error={result.error}")
    print(f"[editorial_planner_canary_4a1] generate={result.engine_generate_attempts}")
    print(f"[editorial_planner_canary_4a1] posts={result.anthropic_post_attempts}")
    if not execute_real:
        safe = {
            "schema_identity": header.get("schema_identity"),
            "prompt": header.get("prompt"),
            "transport": header.get("transport"),
            "blocked_precall": header.get("result") == "BLOCKED_PRECALL",
            "provider_calls": 0,
        }
        print(json.dumps(safe, ensure_ascii=False, indent=2))
    print("[editorial_planner_canary_4a1] STOP — revue humaine.")
    print("READY_FOR_REAL_EDITORIAL_PLANNER_CALL = NO")
    if not result.accepted and execute_real:
        return 1
    if header.get("result") == "BLOCKED_PRECALL":
        return 2
    if execute_real:
        return 0 if header.get("result") == "PASS" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
