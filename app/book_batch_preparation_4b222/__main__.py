"""
CLI Phase 4B.2.22 — CH018 editorial acceptance and batch-generation readiness.

Terra and Sonnet execution are rejected. Remaining chapters are not generated.
"""

from __future__ import annotations

import json
import sys

from app.book_batch_preparation_4b222.constants import AUTHORIZATION_SCOPE, PHASE
from app.book_batch_preparation_4b222.guard import BookBatchPreparation4222Error
from app.book_batch_preparation_4b222.runner import run_phase


def _usage() -> None:
    print(
        "Usage : python -m app.book_batch_preparation_4b222 "
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
            print("[book_batch_preparation_4b222] Provider execution is not authorized.")
            print("[book_batch_preparation_4b222] STOP - human decision.")
            return 2
        if token == "--dry-run":
            index += 1
            continue
        print(f"[ERREUR] unknown option: {token}")
        _usage()
        return 2

    print(f"[book_batch_preparation_4b222] phase={PHASE}")
    print(
        "[book_batch_preparation_4b222] offline=True terra_authorized=False "
        "sonnet_authorized=False"
    )
    try:
        result = run_phase(authorization_scope=scope, write_artifacts=True, run_tests=True)
    except BookBatchPreparation4222Error as exc:
        print(f"[book_batch_preparation_4b222] rejected={exc}")
        print("[book_batch_preparation_4b222] STOP - human decision.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "real_provider_calls": 0,
                "openai_http_requests": 0,
                "anthropic_http_requests": 0,
                "ch018_accepted": True,
                "remaining_chapters": header.get("remaining_chapters"),
                "prompt_1_1_hash_match": header.get("prompt_11_hash_match"),
                "ready_for_first_batch_authorization": header.get(
                    "ready_for_first_batch_authorization"
                ),
                "ready_for_all_17_real_generations": "NO",
                "book_json": "NOT PUBLISHED",
                "production_cache": "UNCHANGED",
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    print("[book_batch_preparation_4b222] STOP - human decision.")
    if result.mode == "REJECTED":
        return 2
    return 0 if header.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
