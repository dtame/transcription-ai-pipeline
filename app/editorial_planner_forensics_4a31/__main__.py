"""
CLI Phase 4A.3.1 Editorial Planner semantic forensics.

Offline only. 0 provider calls. Does not publish editorial_plan.json.
"""

from __future__ import annotations

import json
import sys

from app.editorial_planner_forensics_4a31.constants import PHASE, REAL_PROVIDER_CALLS
from app.editorial_planner_forensics_4a31.guard import PlannerForensicsError
from app.editorial_planner_forensics_4a31.runner import run_forensics


def _usage() -> None:
    print("Usage : python -m app.editorial_planner_forensics_4a31")
    print("Offline forensic review of the saved A.3 candidate. 0 provider calls.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("-h", "--help"):
        _usage()
        return 0
    if argv:
        print(f"[ERREUR] option inconnue : {argv[0]}")
        _usage()
        return 2

    print(f"[editorial_planner_forensics_4a31] phase={PHASE}")
    print(f"[editorial_planner_forensics_4a31] real_provider_calls={REAL_PROVIDER_CALLS}")
    try:
        result = run_forensics(write_artifacts=True)
    except PlannerForensicsError as exc:
        print(f"[editorial_planner_forensics_4a31] rejected={exc}")
        print("[editorial_planner_forensics_4a31] STOP — revue humaine.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(
        f"[editorial_planner_forensics_4a31] accepted={result.accepted} "
        f"calls={result.provider_calls}"
    )
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "real_provider_calls": header.get("real_provider_calls"),
                "semantic_review": header.get("semantic_review"),
                "publication_eligible": header.get("publication_eligible"),
                "book_language_requires_human_decision": header.get(
                    "book_language_requires_human_decision"
                ),
                "editorial_plan_json": "NOT PUBLISHED",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("[editorial_planner_forensics_4a31] STOP — revue humaine.")
    if not result.accepted:
        return 1
    return 0 if header.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
