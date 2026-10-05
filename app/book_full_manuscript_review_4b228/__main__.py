"""
CLI Phase 4B.2.28 — full manuscript editorial consolidation.

Terra and Sonnet execution are rejected. Chapters are not regenerated.
"""

from __future__ import annotations

import json
import sys

from app.book_full_manuscript_review_4b228.constants import AUTHORIZATION_SCOPE, PHASE
from app.book_full_manuscript_review_4b228.guard import (
    BookFullManuscriptReview4228Error,
)
from app.book_full_manuscript_review_4b228.runner import run_phase


def _usage() -> None:
    print(
        "Usage : python -m app.book_full_manuscript_review_4b228 "
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
            print("[book_full_manuscript_review_4b228] Provider execution is not authorized.")
            print("[book_full_manuscript_review_4b228] STOP - human decision.")
            return 2
        if token == "--dry-run":
            index += 1
            continue
        print(f"[ERREUR] unknown option: {token}")
        _usage()
        return 2

    print(f"[book_full_manuscript_review_4b228] phase={PHASE}")
    print(
        "[book_full_manuscript_review_4b228] offline=True terra_authorized=False "
        "sonnet_authorized=False"
    )
    try:
        result = run_phase(authorization_scope=scope, write_artifacts=True, run_tests=True)
    except BookFullManuscriptReview4228Error as exc:
        print(f"[book_full_manuscript_review_4b228] rejected={exc}")
        print("[book_full_manuscript_review_4b228] STOP - human decision.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "real_provider_calls": 0,
                "openai_http_requests": 0,
                "anthropic_http_requests": 0,
                "chapters_assembled": header.get("chapters_assembled"),
                "sections_assembled": header.get("sections_assembled"),
                "idea_coverage": header.get("idea_coverage"),
                "ready_for_global_human_review": header.get(
                    "ready_for_global_human_review"
                ),
                "book_json": "NOT PUBLISHED",
                "docx": "NOT GENERATED",
                "pdf": "NOT GENERATED",
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    print("[book_full_manuscript_review_4b228] STOP - human decision.")
    if result.mode == "REJECTED":
        return 2
    return 0 if header.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
