"""
CLI Phase 4B.2.29 — provisional print-review book.json constitution.

Terra and Sonnet execution are rejected. Chapters are not regenerated.
DOCX and PDF are not generated.
"""

from __future__ import annotations

import json
import sys

from app.book_print_review_canonical_4b229.constants import AUTHORIZATION_SCOPE, PHASE
from app.book_print_review_canonical_4b229.guard import (
    BookPrintReviewCanonical4229Error,
)
from app.book_print_review_canonical_4b229.runner import run_phase


def _usage() -> None:
    print(
        "Usage : python -m app.book_print_review_canonical_4b229 "
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
            print("[book_print_review_canonical_4b229] Provider execution is not authorized.")
            print("[book_print_review_canonical_4b229] STOP - wait for the next phase.")
            return 2
        if token == "--dry-run":
            index += 1
            continue
        print(f"[ERREUR] unknown option: {token}")
        _usage()
        return 2

    print(f"[book_print_review_canonical_4b229] phase={PHASE}")
    print(
        "[book_print_review_canonical_4b229] offline=True terra_authorized=False "
        "sonnet_authorized=False"
    )
    try:
        result = run_phase(
            authorization_scope=scope,
            write_artifacts=True,
            run_tests=True,
            publish=True,
        )
    except BookPrintReviewCanonical4229Error as exc:
        print(f"[book_print_review_canonical_4b229] rejected={exc}")
        print("[book_print_review_canonical_4b229] STOP - wait for the next phase.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "real_provider_calls": 0,
                "openai_http_requests": 0,
                "anthropic_http_requests": 0,
                "book_status": header.get("book_status"),
                "book_version": header.get("book_version"),
                "book_canonical_path": header.get("book_canonical_path"),
                "chapters": header.get("chapters"),
                "sections": header.get("sections"),
                "idea_coverage": header.get("idea_coverage"),
                "docx": "NOT GENERATED",
                "pdf": "NOT GENERATED",
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    print("[book_print_review_canonical_4b229] STOP - wait for visual direction.")
    if result.mode == "REJECTED":
        return 2
    return 0 if header.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
