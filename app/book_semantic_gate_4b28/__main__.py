"""
CLI Phase 4B.2.8 — Comparative forensics and architecture design.

Terra execution is rejected. No --execute-real.
"""

from __future__ import annotations

import json
import sys

from app.book_semantic_gate_4b28.constants import AUTHORIZATION_SCOPE, PHASE
from app.book_semantic_gate_4b28.guard import BookSemanticGate28Error
from app.book_semantic_gate_4b28.runner import run_phase


def _usage() -> None:
    print(
        "Usage : python -m app.book_semantic_gate_4b28 "
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
            print("[book_semantic_gate_4b28] Terra execution is not authorized.")
            print("[book_semantic_gate_4b28] STOP — revue humaine.")
            return 2
        if token == "--dry-run":
            index += 1
            continue
        print(f"[ERREUR] option inconnue : {token}")
        _usage()
        return 2

    print(f"[book_semantic_gate_4b28] phase={PHASE}")
    print(f"[book_semantic_gate_4b28] scope={scope}")
    print("[book_semantic_gate_4b28] offline=True terra_authorized=False")

    try:
        result = run_phase(
            authorization_scope=scope,
            write_artifacts=True,
            run_tests=True,
        )
    except BookSemanticGate28Error as exc:
        print(f"[book_semantic_gate_4b28] rejected={exc}")
        print("[book_semantic_gate_4b28] STOP — revue humaine.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(f"[book_semantic_gate_4b28] accepted={result.accepted} mode={result.mode}")
    print(f"[book_semantic_gate_4b28] result={header.get('result')}")
    if result.error:
        print(f"[book_semantic_gate_4b28] error={result.error}")
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "real_provider_calls": 0,
                "openai_http_requests": 0,
                "anthropic_http_requests": 0,
                "historical_h01": "PARTIAL",
                "historical_h02": "PARTIAL",
                "historical_h11": "PARTIAL",
                "contract_proposal": header.get("contract_20_proposal"),
                "target_architecture": header.get("proposed_target_architecture"),
                "book_json": "NOT PUBLISHED",
                "production_cache": "UNCHANGED",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("[book_semantic_gate_4b28] STOP — revue humaine.")
    if result.mode == "REJECTED":
        return 2
    return 0 if header.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
