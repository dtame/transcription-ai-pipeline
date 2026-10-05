"""CLI Phase 4B.2.35 — print-ready front and back covers.

No OpenAI call. No Black Forest Labs call. The interior is not modified.
"""

from __future__ import annotations

import json
import sys

from app.cover_print_ready_4b235.constants import AUTHORIZATION_SCOPE, PHASE
from app.cover_print_ready_4b235.guard import ApprovedImageHashError, CoverPrintReady4235Error
from app.cover_print_ready_4b235.runner import run_phase


def _usage() -> None:
    print(
        "Usage : python -m app.cover_print_ready_4b235 "
        "--authorization-scope "
        f"{AUTHORIZATION_SCOPE}"
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
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
        print(f"[ERREUR] unknown option: {token}")
        _usage()
        return 2
    print(f"[cover_print_ready_4b235] phase={PHASE}")
    print("[cover_print_ready_4b235] ai_generation_calls=0 openai=0 black_forest_labs=0")
    try:
        result = run_phase(authorization_scope=scope, run_tests=True)
    except ApprovedImageHashError as exc:
        print(f"[cover_print_ready_4b235] {exc}")
        return 2
    except CoverPrintReady4235Error as exc:
        print(f"[cover_print_ready_4b235] rejected={exc}")
        return 2
    print(json.dumps({"result": result["result"], "ai_generation_calls": 0}, indent=2))
    print("[cover_print_ready_4b235] STOP. Wait for human inspection of the four cover files.")
    return 0 if result["result"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
