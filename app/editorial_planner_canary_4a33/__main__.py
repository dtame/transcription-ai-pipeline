"""
CLI Phase 4A.3.3 Editorial Planner one real English production canary.

Default: --dry-run (0 POST).
Real: --authorization-scope EDITORIAL_PLANNER_4A33_ONE_REAL_ENGLISH_PRODUCTION_CANARY_ONLY --execute-real
"""

from __future__ import annotations

import json
import sys

from app.editorial_planner_canary_4a33.constants import AUTHORIZATION_SCOPE, PHASE
from app.editorial_planner_canary_4a33.guard import PlannerCanaryError
from app.editorial_planner_canary_4a33.runner import run_canary


def _usage() -> None:
    print(
        "Usage : python -m app.editorial_planner_canary_4a33 "
        "--authorization-scope "
        f"{AUTHORIZATION_SCOPE} --dry-run"
    )
    print(
        "Réel  : python -m app.editorial_planner_canary_4a33 "
        "--authorization-scope "
        f"{AUTHORIZATION_SCOPE} --execute-real"
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

    print(f"[editorial_planner_canary_4a33] phase={PHASE}")
    print(f"[editorial_planner_canary_4a33] scope={scope}")
    print(
        f"[editorial_planner_canary_4a33] dry_run={dry_run} execute_real={execute_real}"
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
        print(f"[editorial_planner_canary_4a33] rejected={exc}")
        print("[editorial_planner_canary_4a33] STOP — revue humaine.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(f"[editorial_planner_canary_4a33] accepted={result.accepted} mode={result.mode}")
    print(f"[editorial_planner_canary_4a33] result={header.get('result')}")
    if result.error:
        print(f"[editorial_planner_canary_4a33] error={result.error}")
    print(f"[editorial_planner_canary_4a33] generate={result.engine_generate_attempts}")
    print(f"[editorial_planner_canary_4a33] posts={result.anthropic_post_attempts}")
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "actual_provider_calls": header.get("actual_provider_calls"),
                "request_identity": header.get("request_identity"),
                "actual_request_sha256": header.get("actual_request_sha256"),
                "canonical_document_language": header.get("canonical_document_language"),
                "editorial_language_result": header.get("editorial_language_result"),
                "publication_eligible": header.get("publication_eligible"),
                "editorial_plan_json": "NOT PUBLISHED",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("[editorial_planner_canary_4a33] STOP — revue humaine.")
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
