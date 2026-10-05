"""
CLI Phase 4B.2.24 — CH002 offline recovery and CH001 editorial-review prep.

Terra and Sonnet execution are rejected. No chapter is generated.
"""

from __future__ import annotations

import json
import sys

from app.book_ch002_offline_recovery_4b224.constants import AUTHORIZATION_SCOPE, PHASE
from app.book_ch002_offline_recovery_4b224.guard import BookCh002OfflineRecovery4224Error
from app.book_ch002_offline_recovery_4b224.runner import run_phase


def _usage() -> None:
    print(
        "Usage : python -m app.book_ch002_offline_recovery_4b224 "
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
            print("[book_ch002_offline_recovery_4b224] Provider execution is not authorized.")
            print("[book_ch002_offline_recovery_4b224] STOP - human decision.")
            return 2
        if token == "--dry-run":
            index += 1
            continue
        print(f"[ERREUR] unknown option: {token}")
        _usage()
        return 2

    print(f"[book_ch002_offline_recovery_4b224] phase={PHASE}")
    print(
        "[book_ch002_offline_recovery_4b224] offline=True terra_authorized=False "
        "sonnet_authorized=False authorized_spend=0"
    )
    try:
        result = run_phase(authorization_scope=scope, write_artifacts=True, run_tests=True)
    except BookCh002OfflineRecovery4224Error as exc:
        print(f"[book_ch002_offline_recovery_4b224] rejected={exc}")
        print("[book_ch002_offline_recovery_4b224] STOP - human decision.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "real_provider_calls": 0,
                "openai_http_requests": 0,
                "anthropic_http_requests": 0,
                "ch001_status": header.get("ch001_status"),
                "ch002_recovery": header.get("ch002_recovery"),
                "ch002_recovered_contract": header.get("ch002_recovered_contract"),
                "ready_for_ch001_human_review": header.get("ready_for_ch001_human_review"),
                "ready_for_ch002_human_review": header.get("ready_for_ch002_human_review"),
                "ready_for_ch003_ch004_authorization": header.get(
                    "ready_for_ch003_ch004_authorization"
                ),
                "book_json": "NOT PUBLISHED",
                "production_cache": "UNCHANGED",
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    print("[book_ch002_offline_recovery_4b224] STOP - human review. Do not generate.")
    if result.mode == "REJECTED":
        return 2
    return 0 if header.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
