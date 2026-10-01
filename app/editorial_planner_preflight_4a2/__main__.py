"""
CLI Phase 4A.2 Editorial Planner exact production preflight.

Offline only. Never --execute-real. 0 provider calls.
"""

from __future__ import annotations

import json
import sys

from app.editorial_planner_preflight_4a2.constants import AUTHORIZATION_SCOPE, PHASE
from app.editorial_planner_preflight_4a2.guard import PlannerPreflightError
from app.editorial_planner_preflight_4a2.runner import run_preflight


def _usage() -> None:
    print(
        "Usage : python -m app.editorial_planner_preflight_4a2 "
        "--authorization-scope "
        "EDITORIAL_PLANNER_4A2_OFFLINE_PRODUCTION_PREFLIGHT_ONLY --dry-run"
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0
    if "--execute-real" in argv:
        print("[ERREUR] Phase 4A.2 interdit --execute-real. 0 appels provider.")
        return 2
    scope = None
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--authorization-scope":
            if index + 1 >= len(argv):
                print("[ERREUR] --authorization-scope exige une valeur.")
                return 2
            scope = argv[index + 1]
            index += 2
            continue
        if token == "--dry-run":
            index += 1
            continue
        print(f"[ERREUR] option inconnue : {token}")
        _usage()
        return 2
    if scope != AUTHORIZATION_SCOPE:
        print(
            f"[ERREUR] authorization scope must be {AUTHORIZATION_SCOPE!r}, "
            f"received {scope!r}."
        )
        return 2

    print(f"[editorial_planner_preflight_4a2] phase={PHASE}")
    print(f"[editorial_planner_preflight_4a2] scope={scope}")
    print("[editorial_planner_preflight_4a2] dry_run=True execute_real=False")
    try:
        bundle = run_preflight(write_artifacts=True)
    except PlannerPreflightError as exc:
        print(f"[editorial_planner_preflight_4a2] rejected={exc}")
        print("[editorial_planner_preflight_4a2] STOP — revue humaine.")
        return 2
    header = bundle.get("header") or {}
    print(f"[editorial_planner_preflight_4a2] result={header.get('result')}")
    print(
        "[editorial_planner_preflight_4a2] "
        f"ready={header.get('ready_for_one_real_editorial_planner_canary')}"
    )
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "real_provider_calls": header.get("real_provider_calls"),
                "selected_max_output": header.get("selected_production_max_output"),
                "output_budget_decision": header.get("output_budget_decision"),
                "request_sha256": header.get("exact_request_sha256"),
                "ready": header.get("ready_for_one_real_editorial_planner_canary"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("[editorial_planner_preflight_4a2] STOP — revue humaine.")
    return 0 if header.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
