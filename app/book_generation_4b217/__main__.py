"""
CLI Phase 4B.2.17 — CH012 faithful real pilot generation.

Default: --dry-run (0 provider calls).
Real: --authorization-scope BOOK_GENERATION_4B217_CH012_FAITHFUL_REAL_PILOT_GENERATION_ONLY --execute-real
"""

from __future__ import annotations

import json
import sys

from app.book_generation_4b217.constants import AUTHORIZATION_SCOPE, PHASE
from app.book_generation_4b217.guard import BookGeneration4217Error
from app.book_generation_4b217.runner import run_phase


def _usage() -> None:
    print(
        "Usage : python -m app.book_generation_4b217 "
        "--authorization-scope "
        f"{AUTHORIZATION_SCOPE} --dry-run"
    )
    print(
        "Réel  : python -m app.book_generation_4b217 "
        "--authorization-scope "
        f"{AUTHORIZATION_SCOPE} --execute-real"
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0

    scope = None
    dry_run = "--dry-run" in argv or "--execute-real" not in argv
    execute_real = "--execute-real" in argv
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
        if token in {"--dry-run", "--execute-real"}:
            index += 1
            continue
        print(f"[ERREUR] option inconnue : {token}")
        _usage()
        return 2

    if execute_real and "--dry-run" in argv:
        print("[ERREUR] --dry-run et --execute-real sont mutuellement exclusifs.")
        return 2

    print(f"[book_generation_4b217] phase={PHASE}")
    print(f"[book_generation_4b217] scope={scope}")
    print(f"[book_generation_4b217] dry_run={dry_run} execute_real={execute_real}")
    print(f"[book_generation_4b217] python={sys.executable}")

    try:
        result = run_phase(
            authorization_scope=scope,
            dry_run=dry_run,
            execute_real=execute_real,
            allow_real_provider=bool(execute_real),
            persist_usage=bool(execute_real),
            write_artifacts=True,
        )
    except BookGeneration4217Error as exc:
        print(f"[book_generation_4b217] rejected={exc}")
        print("[book_generation_4b217] STOP - human review.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(f"[book_generation_4b217] accepted={result.accepted} mode={result.mode}")
    print(f"[book_generation_4b217] result={header.get('result')}")
    if result.error:
        print(f"[book_generation_4b217] error={result.error}")
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "provider_calls": header.get("provider_calls"),
                "anthropic_http": header.get("anthropic_http"),
                "openai_http": 0,
                "model": header.get("model"),
                "chapter": "CH012",
                "precall_maximum_cost": header.get("precall_maximum_cost"),
                "real_cost": header.get("real_cost"),
                "stop_reason": header.get("stop_reason"),
                "book_json": "NOT PUBLISHED",
                "production_cache": "UNCHANGED",
                "ready_for_human_chapter_review": header.get(
                    "ready_for_human_chapter_review"
                ),
                "ready_for_terra_validation": "NO",
                "ready_for_full_book_generation": "NO",
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    print("[book_generation_4b217] STOP - human review.")
    if result.mode == "REJECTED":
        return 2
    if execute_real:
        return 0 if header.get("result") in {"PASS", "PARTIAL"} else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
