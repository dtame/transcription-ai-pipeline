"""
CLI Phase 4A.3 Editorial Planner one real production canary.

Default: --dry-run (0 POST).
Real: --authorization-scope EDITORIAL_PLANNER_4A3_ONE_REAL_PRODUCTION_CANARY_ONLY --execute-real
"""

from __future__ import annotations

import json
import sys

from app.editorial_planner_canary_4a3.constants import AUTHORIZATION_SCOPE, PHASE
from app.editorial_planner_canary_4a3.guard import PlannerCanaryError
from app.editorial_planner_canary_4a3.runner import run_canary


def _usage() -> None:
    print(
        "Usage : python -m app.editorial_planner_canary_4a3 "
        "--authorization-scope "
        "EDITORIAL_PLANNER_4A3_ONE_REAL_PRODUCTION_CANARY_ONLY --dry-run"
    )
    print(
        "Réel  : python -m app.editorial_planner_canary_4a3 "
        "--authorization-scope "
        "EDITORIAL_PLANNER_4A3_ONE_REAL_PRODUCTION_CANARY_ONLY --execute-real"
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

    print(f"[editorial_planner_canary_4a3] phase={PHASE}")
    print(f"[editorial_planner_canary_4a3] scope={scope}")
    print(
        f"[editorial_planner_canary_4a3] dry_run={dry_run} execute_real={execute_real}"
    )

    try:
        result = run_canary(
            dry_run=dry_run,
            execute_real=execute_real,
            authorization_scope=scope,
            allow_real_provider=bool(execute_real),
            persist_usage=bool(execute_real),
            write_artifacts=True,
        )
    except PlannerCanaryError as exc:
        print(f"[editorial_planner_canary_4a3] rejected={exc}")
        print("[editorial_planner_canary_4a3] STOP — revue humaine.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(f"[editorial_planner_canary_4a3] accepted={result.accepted} mode={result.mode}")
    print(f"[editorial_planner_canary_4a3] result={header.get('result')}")
    if result.error:
        print(f"[editorial_planner_canary_4a3] error={result.error}")
    print(f"[editorial_planner_canary_4a3] generate={result.engine_generate_attempts}")
    print(f"[editorial_planner_canary_4a3] posts={result.anthropic_post_attempts}")
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "actual_provider_calls": header.get("actual_provider_calls"),
                "request_identity": header.get("request_identity"),
                "actual_request_sha256": header.get("actual_request_sha256"),
                "max_output": header.get("max_output"),
                "publication_eligible": header.get("publication_eligible"),
                "editorial_plan_json": "NOT PUBLISHED",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("[editorial_planner_canary_4a3] STOP — revue humaine.")
    if result.mode == "REJECTED":
        return 2
    if not result.accepted and execute_real:
        return 1
    if header.get("result") == "BLOCKED_PRECALL":
        return 2
    if execute_real:
        return 0 if header.get("result") in {"PASS", "PARTIAL"} else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
