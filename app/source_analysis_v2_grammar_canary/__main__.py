"""
CLI canary V2 grammar + thinking-config.

Défaut : --dry-run (0 POST).
Réel : --authorization-scope V2_GRAMMAR_CONFIG_CANARY_ONLY --execute-real
"""

from __future__ import annotations

import json
import sys

from app.source_analysis_v2_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    MODE,
    PHASE,
    PROJECT_NAME,
)
from app.source_analysis_v2_grammar_canary.guard import GrammarCanaryError
from app.source_analysis_v2_grammar_canary.runner import run_grammar_thinking_canary


def _usage() -> None:
    print(
        "Usage : python -m app.source_analysis_v2_grammar_canary "
        "<projet> --authorization-scope V2_GRAMMAR_CONFIG_CANARY_ONLY --dry-run"
    )
    print("Réel  : ... --authorization-scope V2_GRAMMAR_CONFIG_CANARY_ONLY --execute-real")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0

    project_name = argv[0] if not argv[0].startswith("--") else PROJECT_NAME
    flags = argv[1:] if not argv[0].startswith("--") else argv
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

    print(f"[v2_grammar_canary] projet={project_name}")
    print(f"[v2_grammar_canary] phase={PHASE} mode={MODE}")
    print(f"[v2_grammar_canary] scope={scope}")
    print(f"[v2_grammar_canary] dry_run={dry_run} execute_real={execute_real}")

    try:
        result = run_grammar_thinking_canary(
            project_name,
            dry_run=dry_run,
            execute_real=execute_real,
            authorization_scope=scope,
            allow_real_provider=bool(execute_real),
            write_artifacts=bool(execute_real),
        )
    except GrammarCanaryError as exc:
        print(f"[v2_grammar_canary] rejected={exc}")
        print("[v2_grammar_canary] STOP — revue humaine. Phase 3B INCOMPLETE.")
        return 2

    print(f"[v2_grammar_canary] accepted={result.accepted} mode={result.mode}")
    if result.error:
        print(f"[v2_grammar_canary] error={result.error}")
    print(f"[v2_grammar_canary] generate_attempts={result.engine_generate_attempts}")
    print(f"[v2_grammar_canary] anthropic_posts={result.anthropic_post_attempts}")
    if result.dry_run and not execute_real:
        safe = {
            "request_identity": result.dry_run.get("request_identity"),
            "schema_hash": result.dry_run.get("schema_hash"),
            "synthetic_fixture_hash": result.dry_run.get("synthetic_fixture_hash"),
            "payload_audit": result.payload_audit,
            "provider_calls": 0,
        }
        print(json.dumps(safe, ensure_ascii=False, indent=2))
    print("[v2_grammar_canary] STOP — revue humaine. Phase 3B INCOMPLETE.")
    if not result.accepted:
        return 2
    if execute_real:
        verdict = (result.execution or {}).get("result")
        return 0 if verdict == "PASS" else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
