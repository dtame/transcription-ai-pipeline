"""
CLI canary WIN001.

Défaut : --dry-run.
Exécution réelle : --window WIN001 --execute-real.

Usage dry-run :
    python -m app.source_analysis_hybrid_readiness.canary_cli <projet> --window WIN001 --dry-run

Usage réel (NE PAS lancer en 3B.7.6) :
    python -m app.source_analysis_hybrid_readiness.canary_cli <projet> --window WIN001 --execute-real
"""

from __future__ import annotations

import sys

from app.source_analysis_hybrid_readiness.canary import run_win001_canary
from app.source_analysis_hybrid_readiness.constants import (
    AUTHORIZATION_SCOPE_BOUNDED_WIN001_ONLY,
    AUTHORIZATION_SCOPE_REMAINING_WINDOWS,
    AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY,
    AUTHORIZATION_SCOPE_WIN001_ONLY,
    MODE,
    PHASE,
)


def _usage() -> None:
    print(
        "Usage  : python -m app.source_analysis_hybrid_readiness.canary_cli "
        "<projet> --window WIN001 --dry-run"
    )
    print("Défaut : --dry-run (0 appel réseau).")
    print("Réel   : --window WIN001 --execute-real (autorisation humaine requise).")
    print(
        "Borné  : --authorization-scope BOUNDED_WIN001_ONLY "
        "--prompt-version window-analysis-1.1"
    )
    print(
        "Small  : --authorization-scope SMALL_V21_WIN001_ONLY "
        "--planner-version window-planner-v2.1-small "
        "--prompt-version window-analysis-1.1"
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0

    project_name = argv[0]
    flags = argv[1:]
    window_id = None
    scope = AUTHORIZATION_SCOPE_WIN001_ONLY
    prompt_version = None
    planner_version = None
    dry_run = "--dry-run" in flags or "--execute-real" not in flags
    execute_real = "--execute-real" in flags
    consumed: list[str] = []
    index = 0
    while index < len(flags):
        token = flags[index]
        if token == "--window":
            if index + 1 >= len(flags):
                print("[ERREUR] --window exige une valeur.")
                return 2
            window_id = flags[index + 1]
            consumed.extend([token, flags[index + 1]])
            index += 2
            continue
        if token == "--authorization-scope":
            if index + 1 >= len(flags):
                print("[ERREUR] --authorization-scope exige une valeur.")
                return 2
            scope = flags[index + 1]
            consumed.extend([token, flags[index + 1]])
            index += 2
            continue
        if token == "--prompt-version":
            if index + 1 >= len(flags):
                print("[ERREUR] --prompt-version exige une valeur.")
                return 2
            prompt_version = flags[index + 1]
            consumed.extend([token, flags[index + 1]])
            index += 2
            continue
        if token == "--planner-version":
            if index + 1 >= len(flags):
                print("[ERREUR] --planner-version exige une valeur.")
                return 2
            planner_version = flags[index + 1]
            consumed.extend([token, flags[index + 1]])
            index += 2
            continue
        if token in {"--dry-run", "--execute-real"}:
            consumed.append(token)
            index += 1
            continue
        print(f"[ERREUR] option inconnue : {token}")
        _usage()
        return 2

    if scope not in {
        AUTHORIZATION_SCOPE_WIN001_ONLY,
        AUTHORIZATION_SCOPE_BOUNDED_WIN001_ONLY,
        AUTHORIZATION_SCOPE_REMAINING_WINDOWS,
        AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY,
    }:
        print(f"[ERREUR] authorization_scope inconnu : {scope}")
        return 2
    if execute_real and "--dry-run" in flags:
        print("[ERREUR] --dry-run et --execute-real sont mutuellement exclusifs.")
        return 2

    print(f"[win001_canary] projet={project_name}")
    print(f"[win001_canary] phase={PHASE} mode={MODE}")
    print(f"[win001_canary] window={window_id} scope={scope}")
    print(f"[win001_canary] prompt_version={prompt_version}")
    print(f"[win001_canary] planner_version={planner_version}")
    print(f"[win001_canary] dry_run={dry_run} execute_real={execute_real}")

    result = run_win001_canary(
        project_name,
        window_id=window_id,
        dry_run=dry_run,
        execute_real=execute_real,
        authorization_scope=scope,
        prompt_version=prompt_version,
        planner_version=planner_version,
        allow_real_provider=bool(execute_real),
    )
    print(f"[win001_canary] accepted={result.accepted} mode={result.mode}")
    if result.error:
        print(f"[win001_canary] error={result.error}")
    print(f"[win001_canary] provider_calls={result.provider_calls}")
    print("[win001_canary] STOP — revue humaine. Phase 3B INCOMPLETE.")
    if not result.accepted:
        return 2
    if execute_real:
        return 0 if result.execution.get("failed_windows", 0) == 0 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
