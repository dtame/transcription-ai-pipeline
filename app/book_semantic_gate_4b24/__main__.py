"""
CLI Phase 4B.2.4 one real Terra semantic-gate benchmark canary.

Default: --dry-run (0 POST).
Real: --authorization-scope BOOK_SEMANTIC_GATE_4B24_ONE_REAL_TERRA_HISTORICAL_BENCHMARK_CANARY_ONLY --execute-real
"""

from __future__ import annotations

import json
import sys

from app.book_semantic_gate_4b24.constants import AUTHORIZATION_SCOPE, PHASE
from app.book_semantic_gate_4b24.guard import BookSemanticGateCanaryError
from app.book_semantic_gate_4b24.runner import run_canary


def _usage() -> None:
    print(
        "Usage : python -m app.book_semantic_gate_4b24 "
        "--authorization-scope "
        f"{AUTHORIZATION_SCOPE} --dry-run"
    )
    print(
        "Réel  : python -m app.book_semantic_gate_4b24 "
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

    print(f"[book_semantic_gate_4b24] phase={PHASE}")
    print(f"[book_semantic_gate_4b24] scope={scope}")
    print(
        f"[book_semantic_gate_4b24] dry_run={dry_run} execute_real={execute_real}"
    )

    try:
        result = run_canary(
            dry_run=dry_run,
            execute_real=execute_real,
            authorization_scope=scope,
            allow_real_provider=bool(execute_real),
            persist_usage=bool(execute_real),
            write_artifacts=True,
        )
    except BookSemanticGateCanaryError as exc:
        print(f"[book_semantic_gate_4b24] rejected={exc}")
        print("[book_semantic_gate_4b24] STOP — revue humaine.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(f"[book_semantic_gate_4b24] accepted={result.accepted} mode={result.mode}")
    print(f"[book_semantic_gate_4b24] result={header.get('result')}")
    if result.error:
        print(f"[book_semantic_gate_4b24] error={result.error}")
    print(f"[book_semantic_gate_4b24] generate={result.engine_generate_attempts}")
    print(f"[book_semantic_gate_4b24] posts={result.openai_post_attempts}")
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "actual_terra_calls": header.get("actual_terra_calls"),
                "request_sha256": header.get("request_sha256"),
                "label_leakage": header.get("label_leakage"),
                "positive_accepted": header.get("positive_accepted"),
                "negative_blocked": header.get("negative_blocked"),
                "book_json": "NOT PUBLISHED",
                "production_cache": "NOT ACCEPTED",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("[book_semantic_gate_4b24] STOP — revue humaine.")
    if result.mode == "REJECTED":
        return 2
    if header.get("result") == "BLOCKED_PRECALL":
        return 2
    if execute_real:
        return 0 if header.get("result") in {"PASS", "PARTIAL"} else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
