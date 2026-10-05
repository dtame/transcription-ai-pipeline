"""
CLI Phase 4B.2.30 — Word print profile preparation.

Terra and Sonnet execution are rejected. The book DOCX and PDF are not generated.
book.json is not modified.
"""

from __future__ import annotations

import json
import sys

from app.word_print_profile_4b230.constants import AUTHORIZATION_SCOPE, PHASE
from app.word_print_profile_4b230.guard import WordPrintProfile4230Error
from app.word_print_profile_4b230.runner import run_phase


def _usage() -> None:
    print(
        "Usage : python -m app.word_print_profile_4b230 "
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
            print("[word_print_profile_4b230] Provider execution is not authorized.")
            print("[word_print_profile_4b230] STOP - wait for Phase 4B.2.31.")
            return 2
        if token == "--dry-run":
            index += 1
            continue
        print(f"[ERREUR] unknown option: {token}")
        _usage()
        return 2

    print(f"[word_print_profile_4b230] phase={PHASE}")
    print(
        "[word_print_profile_4b230] offline=True terra_authorized=False "
        "docx_authorized=False pdf_authorized=False"
    )
    try:
        result = run_phase(
            authorization_scope=scope,
            write_artifacts=True,
            run_tests=True,
        )
    except WordPrintProfile4230Error as exc:
        print(f"[word_print_profile_4b230] rejected={exc}")
        print("[word_print_profile_4b230] STOP - wait for Phase 4B.2.31.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "real_provider_calls": 0,
                "book_status": header.get("book_status"),
                "book_version": header.get("book_version"),
                "profile": header.get("profile"),
                "word_renderer": header.get("word_renderer"),
                "word_finalizer": header.get("word_finalizer"),
                "docx": "NOT GENERATED",
                "pdf": "NOT GENERATED",
                "ready_for_docx_pdf_generation": header.get(
                    "ready_for_docx_pdf_generation"
                ),
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    print("[word_print_profile_4b230] STOP - wait for Phase 4B.2.31.")
    if result.mode == "REJECTED":
        return 2
    return 0 if header.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
