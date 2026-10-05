"""
CLI Phase 4B.2.5.1 — offline OpenAI Terra API compatibility hardening.

Terra execution is rejected. No --execute-real.
"""

from __future__ import annotations

import json
import sys

from app.book_semantic_gate_4b251.constants import AUTHORIZATION_SCOPE, PHASE
from app.book_semantic_gate_4b251.guard import BookSemanticGate251Error
from app.book_semantic_gate_4b251.runner import run_phase


def _usage() -> None:
    print(
        "Usage : python -m app.book_semantic_gate_4b251 "
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
            print("[book_semantic_gate_4b251] Terra execution is not authorized.")
            print("[book_semantic_gate_4b251] STOP — revue humaine.")
            return 2
        if token == "--dry-run":
            index += 1
            continue
        print(f"[ERREUR] option inconnue : {token}")
        _usage()
        return 2

    print(f"[book_semantic_gate_4b251] phase={PHASE}")
    print(f"[book_semantic_gate_4b251] scope={scope}")
    print("[book_semantic_gate_4b251] offline=True terra_authorized=False")

    try:
        result = run_phase(
            authorization_scope=scope,
            write_artifacts=True,
            run_tests=True,
        )
    except BookSemanticGate251Error as exc:
        print(f"[book_semantic_gate_4b251] rejected={exc}")
        print("[book_semantic_gate_4b251] STOP — revue humaine.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(f"[book_semantic_gate_4b251] accepted={result.accepted} mode={result.mode}")
    print(f"[book_semantic_gate_4b251] result={header.get('result')}")
    if result.error:
        print(f"[book_semantic_gate_4b251] error={result.error}")
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "provider_calls": 0,
                "openai_http": 0,
                "anthropic_http": 0,
                "historical_request_sha256": header.get("historical_request_sha256"),
                "corrected_request_sha256": header.get("corrected_request_sha256"),
                "ready_for_one_new_explicitly_authorized_terra_canary": header.get(
                    "ready_for_one_new_explicitly_authorized_terra_canary"
                ),
                "book_json": "NOT PUBLISHED",
                "production_cache": "UNCHANGED",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("[book_semantic_gate_4b251] STOP — revue humaine.")
    if result.mode == "REJECTED":
        return 2
    return 0 if header.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
