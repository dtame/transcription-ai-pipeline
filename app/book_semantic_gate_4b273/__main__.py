"""
CLI Phase 4B.2.7.3 one real Terra P3 negative canary.

Default: --dry-run (0 remote invocations).
Real: --authorization-scope BOOK_SEMANTIC_GATE_4B273_ONE_REAL_TERRA_P3_NEGATIVE_CANARY_ONLY --execute-real
"""

from __future__ import annotations

import json
import sys

from app.book_semantic_gate_4b273.constants import AUTHORIZATION_SCOPE, PHASE
from app.book_semantic_gate_4b273.guard import BookSemanticGate273Error
from app.book_semantic_gate_4b273.runner import run_canary


def _usage() -> None:
    print(
        "Usage : python -m app.book_semantic_gate_4b273 "
        "--authorization-scope "
        f"{AUTHORIZATION_SCOPE} --dry-run"
    )
    print(
        "Réel  : python -m app.book_semantic_gate_4b273 "
        "--authorization-scope "
        f"{AUTHORIZATION_SCOPE} --execute-real"
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0

    flags = argv
    scope = None
    dry_run = "--dry-run" in flags or "--execute-real" not in flags
    execute_real = "--execute-real" in flags
    index = 0
    while index < len(flags):
        token = flags[index]
        if token == "--authorization-scope":
            if index + 1 >= len(flags):
                print("[ERREUR] --authorization-scope exige une valeur.")
                return 2
            scope = flags[index + 1]
            index += 2
            continue
        if token in {"--dry-run", "--execute-real"}:
            index += 1
            continue
        print(f"[ERREUR] option inconnue : {token}")
        _usage()
        return 2

    if execute_real and "--dry-run" in flags:
        print("[ERREUR] --dry-run et --execute-real sont mutuellement exclusifs.")
        return 2

    print(f"[book_semantic_gate_4b273] phase={PHASE}")
    print(f"[book_semantic_gate_4b273] scope={scope}")
    print(
        f"[book_semantic_gate_4b273] dry_run={dry_run} execute_real={execute_real}"
    )
    print(f"[book_semantic_gate_4b273] python={sys.executable}")

    try:
        result = run_canary(
            dry_run=dry_run,
            execute_real=execute_real,
            authorization_scope=scope,
            allow_real_provider=bool(execute_real),
            persist_usage=bool(execute_real),
            write_artifacts=True,
        )
    except BookSemanticGate273Error as exc:
        print(f"[book_semantic_gate_4b273] rejected={exc}")
        print("[book_semantic_gate_4b273] STOP — revue humaine.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(f"[book_semantic_gate_4b273] accepted={result.accepted} mode={result.mode}")
    print(f"[book_semantic_gate_4b273] result={header.get('result')}")
    if result.error:
        print(f"[book_semantic_gate_4b273] error={result.error}")
    print(f"[book_semantic_gate_4b273] execution_attempts={result.execution_attempts}")
    print(f"[book_semantic_gate_4b273] remote_invocations={result.remote_invocations}")
    print(f"[book_semantic_gate_4b273] http_requests={result.http_requests}")
    print(f"[book_semantic_gate_4b273] provider_responses={result.provider_responses}")
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "authorized_remote_invocations": 1,
                "execution_attempts": header.get("execution_attempts"),
                "remote_invocations": header.get("remote_invocations"),
                "http_requests": header.get("http_requests"),
                "provider_responses": header.get("provider_responses"),
                "request_sha256": header.get("request_sha256"),
                "case_handle": header.get("case_handle"),
                "benchmark_id": header.get("benchmark_id"),
                "label_leakage": header.get("label_leakage"),
                "terra_global_verdict": header.get("terra_global_verdict"),
                "disputed_causal_clause_verdict": header.get(
                    "disputed_causal_clause_verdict"
                ),
                "book_json": "NOT PUBLISHED",
                "production_cache": "UNCHANGED",
                "ready_for_new_remote_terra_call": "NO",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("[book_semantic_gate_4b273] STOP — revue humaine.")
    if result.mode == "REJECTED":
        return 2
    if header.get("result") == "BLOCKED_PRECALL":
        return 2
    if execute_real:
        return 0 if header.get("result") in {"PASS", "PARTIAL"} else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
