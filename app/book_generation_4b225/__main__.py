"""
CLI Phase 4B.2.25 — CH001/CH002 acceptance and CH003–CH004 resume.

Default: --dry-run (0 provider calls).
Real: --authorization-scope BOOK_GENERATION_BATCH01_RESUME_CH003_CH004_ONE_SHOT_ONLY --execute-real
"""

from __future__ import annotations

import json
import sys

from app.book_generation_4b225.constants import AUTHORIZATION_SCOPE, PHASE
from app.book_generation_4b225.guard import BookGeneration4225Error
from app.book_generation_4b225.runner import run_phase


def _usage() -> None:
    print(
        "Usage : python -m app.book_generation_4b225 "
        "--authorization-scope "
        f"{AUTHORIZATION_SCOPE} --dry-run"
    )
    print(
        "Réel  : python -m app.book_generation_4b225 "
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

    print(f"[book_generation_4b225] phase={PHASE}")
    print(f"[book_generation_4b225] scope={scope}")
    print(f"[book_generation_4b225] dry_run={dry_run} execute_real={execute_real}")
    print(f"[book_generation_4b225] python={sys.executable}")

    try:
        result = run_phase(
            authorization_scope=scope,
            dry_run=dry_run,
            execute_real=execute_real,
            allow_real_provider=bool(execute_real),
            persist_usage=bool(execute_real),
            write_artifacts=True,
        )
    except BookGeneration4225Error as exc:
        print(f"[book_generation_4b225] rejected={exc}")
        print("[book_generation_4b225] STOP - human review.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(f"[book_generation_4b225] accepted={result.accepted} mode={result.mode}")
    print(f"[book_generation_4b225] result={header.get('result')}")
    if result.error:
        print(f"[book_generation_4b225] error={result.error}")
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "provider_calls": header.get("provider_calls"),
                "anthropic_http": header.get("anthropic_http"),
                "openai_http": 0,
                "model": header.get("model"),
                "chapters_generated": header.get("chapters_generated"),
                "prompt": header.get("prompt"),
                "preflight_max_cost": header.get("preflight_max_cost"),
                "actual_total_cost": header.get("actual_total_cost"),
                "ch001_human_acceptance": header.get("ch001_human_acceptance"),
                "ch002_human_acceptance": header.get("ch002_human_acceptance"),
                "stop_reason": header.get("stop_reason"),
                "book_json": "NOT PUBLISHED",
                "production_cache": "UNCHANGED",
                "ready_for_human_review": header.get("ready_for_human_review"),
                "ready_for_batch02": "NO",
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    print("[book_generation_4b225] STOP - human review. Do not launch BATCH-02.")
    if result.mode == "REJECTED":
        return 2
    if execute_real:
        return 0 if header.get("result") in {"PASS", "PARTIAL"} else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
