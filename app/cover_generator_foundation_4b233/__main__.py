"""
CLI Phase 4B.2.33 — cover generator foundation.

Terra, OpenAI, Anthropic, and image generation are rejected.
book.json and the interior files are not modified.
"""

from __future__ import annotations

import json
import sys

from app.cover_generator_foundation_4b233.constants import AUTHORIZATION_SCOPE, PHASE
from app.cover_generator_foundation_4b233.guard import CoverGeneratorFoundation4233Error
from app.cover_generator_foundation_4b233.runner import run_phase


def _usage() -> None:
    print(
        "Usage : python -m app.cover_generator_foundation_4b233 "
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
            print("[cover_generator_foundation_4b233] Provider execution is not authorized.")
            print("[cover_generator_foundation_4b233] STOP.")
            return 2
        if token == "--dry-run":
            index += 1
            continue
        print(f"[ERREUR] unknown option: {token}")
        _usage()
        return 2

    print(f"[cover_generator_foundation_4b233] phase={PHASE}")
    print(
        "[cover_generator_foundation_4b233] offline=True image_generation=False "
        "docx=False pdf=False"
    )
    try:
        result = run_phase(authorization_scope=scope, write_artifacts=True, run_tests=True)
    except CoverGeneratorFoundation4233Error as exc:
        print(f"[cover_generator_foundation_4b233] rejected={exc}")
        print("[cover_generator_foundation_4b233] STOP.")
        return 2

    header = (result.bundle or {}).get("header") or {}
    print(
        json.dumps(
            {
                "result": header.get("result"),
                "provider_calls": 0,
                "recommended_free_model": header.get("recommended_free_model"),
                "ready_for_next_phase": header.get("ready_for_next_phase"),
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    print("[cover_generator_foundation_4b233] STOP.")
    if result.mode == "REJECTED":
        return 2
    return 0 if header.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
