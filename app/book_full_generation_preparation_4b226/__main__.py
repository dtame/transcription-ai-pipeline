"""
CLI Phase 4B.2.26 — CH003/CH004 acceptance and full-generation readiness.

Terra and Sonnet execution are rejected. Remaining chapters are not generated.
"""

from __future__ import annotations

import json
import sys

from app.book_full_generation_preparation_4b226.constants import AUTHORIZATION_SCOPE, PHASE
from app.book_full_generation_preparation_4b226.guard import (
    BookFullGenerationPreparation4226Error,
)
from app.book_full_generation_preparation_4b226.runner import run_phase


def _usage() -> None:
    print(
        "Usage : python -m app.book_full_generation_preparation_4b226 "
        "--authorization-scope "
        f"{AUTHORIZATION_SCOPE}"
    )
    print("This phase is OFFLINE ONLY. --execute-real is rejected.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0

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
        if token in {"--execute-real", "--allow-real-provider"}:
            print("[book_full_generation_preparation_4b226] Provider execution is not authorized.")
            print("[book_full_generation_preparation_4b226] STOP - human decision.")
            return 2
        if token == "--dry-run":
            index += 1
            continue
        print(f"[ERREUR] unknown option: {token}")
        _usage()
        return 2

    print(f"[book_full_generation_preparation_4b226] phase={PHASE}")
    print(
        "[book_full_generation_preparation_4b226] offline=True terra_authorized=False "
        "sonnet_authorized=False"
    )
    try:
        result = run_phase(authorization_scope=scope, write_artifacts=True, run_tests=True)
    except BookFullGenerationPreparation4226Error as exc:
        print(f"[book_full_generation_preparation_4b226] rejected={exc}")
        print("[book_full_generation_preparation_4b226] STOP - human decision.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "real_provider_calls": 0,
                "openai_http_requests": 0,
                "anthropic_http_requests": 0,
                "ch003_human_acceptance": header.get("ch003_human_acceptance"),
                "ch004_human_acceptance": header.get("ch004_human_acceptance"),
                "remaining_chapters": header.get("remaining_chapters"),
                "ready_for_single_13_chapter_authorization": header.get(
                    "ready_for_single_13_chapter_authorization"
                ),
                "book_json": "NOT PUBLISHED",
                "production_cache": "UNCHANGED",
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    print("[book_full_generation_preparation_4b226] STOP - human decision.")
    if result.mode == "REJECTED":
        return 2
    return 0 if header.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
