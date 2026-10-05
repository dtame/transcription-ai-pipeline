"""
CLI Phase 4B.2.32 — interchapter blank page removal.

Terra, OpenAI, Anthropic, and Sonnet execution are rejected.
book.json is not modified. print-review-v1 is not overwritten.
"""

from __future__ import annotations

import json
import sys

from app.book_print_review_pagination_fix_4b232.constants import AUTHORIZATION_SCOPE, PHASE
from app.book_print_review_pagination_fix_4b232.guard import BookPrintReviewPaginationFix4232Error
from app.book_print_review_pagination_fix_4b232.runner import run_phase


def _usage() -> None:
    print(
        "Usage : python -m app.book_print_review_pagination_fix_4b232 "
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
            print("[book_print_review_pagination_fix_4b232] Provider execution is not authorized.")
            print("[book_print_review_pagination_fix_4b232] STOP.")
            return 2
        if token == "--dry-run":
            index += 1
            continue
        print(f"[ERREUR] unknown option: {token}")
        _usage()
        return 2

    print(f"[book_print_review_pagination_fix_4b232] phase={PHASE}")
    print(
        "[book_print_review_pagination_fix_4b232] offline=True terra_authorized=False "
        "docx_authorized=True pdf_authorized=True v1_readonly=True"
    )
    try:
        result = run_phase(
            authorization_scope=scope,
            write_artifacts=True,
            run_tests=True,
            finalize=True,
            probe_word=True,
        )
    except BookPrintReviewPaginationFix4232Error as exc:
        print(f"[book_print_review_pagination_fix_4b232] rejected={exc}")
        print("[book_print_review_pagination_fix_4b232] STOP.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "real_provider_calls": 0,
                "source_version": header.get("source_version"),
                "output_version": header.get("output_version"),
                "docx": header.get("docx_path"),
                "pdf": header.get("pdf_path"),
                "ready_for_print_review": header.get("ready_for_print_review"),
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    print("[book_print_review_pagination_fix_4b232] STOP.")
    if result.mode == "REJECTED":
        return 2
    return 0 if header.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
