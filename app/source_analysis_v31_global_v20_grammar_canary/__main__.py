"""
CLI canary 3B.7.7A.40 — tiny synthetic global consolidation transport-2.0 grammar canary.

Défaut : --dry-run (0 POST).
Réel : --authorization-scope GLOBAL_CONSOLIDATION_2_0_TINY_SYNTHETIC_GRAMMAR_CANARY_ONLY --execute-real
"""

from __future__ import annotations

import json
import sys

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v31_global_v20_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    MODE,
    PHASE,
    PROJECT_NAME,
)
from app.source_analysis_v31_global_v20_grammar_canary.guard import GlobalGrammarCanaryError
from app.source_analysis_v31_global_v20_grammar_canary.post_tests import (
    run_focused_suite,
    run_full_suite,
    write_a40_baseline,
    write_a40_post_delta,
)
from app.source_analysis_v31_global_v20_grammar_canary.runner import (
    run_global_v20_grammar_canary,
)
from app.source_analysis_v31_global_v20_grammar_canary.writer import write_canary_artifacts


def _usage() -> None:
    print(
        "Usage : python -m app.source_analysis_v31_global_v20_grammar_canary "
        "<projet> --authorization-scope "
        "GLOBAL_CONSOLIDATION_2_0_TINY_SYNTHETIC_GRAMMAR_CANARY_ONLY --dry-run"
    )
    print(
        "Réel  : ... --authorization-scope "
        "GLOBAL_CONSOLIDATION_2_0_TINY_SYNTHETIC_GRAMMAR_CANARY_ONLY --execute-real"
    )


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
    skip_suite = "--skip-suite" in flags
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
        if token in {"--dry-run", "--execute-real", "--skip-suite"}:
            index += 1
            continue
        print(f"[ERREUR] option inconnue : {token}")
        _usage()
        return 2

    if execute_real and "--dry-run" in flags:
        print("[ERREUR] --dry-run et --execute-real sont mutuellement exclusifs.")
        return 2

    print(f"[a40_global_v20_grammar_canary] projet={project_name}")
    print(f"[a40_global_v20_grammar_canary] phase={PHASE} mode={MODE}")
    print(f"[a40_global_v20_grammar_canary] scope={scope}")
    print(f"[a40_global_v20_grammar_canary] dry_run={dry_run} execute_real={execute_real}")

    tests_label = "not run"
    new_failures = "0"
    if execute_real and not skip_suite:
        audit = audit_dir(project_name)
        print("[a40_global_v20_grammar_canary] running pre-call full suite")
        baseline = run_full_suite(junit_path=audit / "a40_pre_full.xml")
        write_a40_baseline(project_name, full=baseline)
        tests_label = baseline.get("summary") or tests_label
        print(f"[a40_global_v20_grammar_canary] baseline={tests_label}")
        if int(baseline.get("failed") or 0) or int(baseline.get("errors") or 0):
            print("[a40_global_v20_grammar_canary] BLOCKED_PRECALL — baseline failed")
            dummy = run_global_v20_grammar_canary(
                project_name,
                dry_run=True,
                execute_real=False,
                authorization_scope=scope or AUTHORIZATION_SCOPE,
                write_artifacts=False,
            )
            dummy.mode = "BLOCKED_PRECALL"
            dummy.blocked_precall = True
            dummy.error = f"baseline tests failed: {tests_label}"
            write_canary_artifacts(
                project_name, dummy, tests=tests_label, extra_header={"new_failures": "baseline"}
            )
            print("[a40_global_v20_grammar_canary] STOP — revue humaine. Phase 3B INCOMPLETE.")
            return 2

    try:
        result = run_global_v20_grammar_canary(
            project_name,
            dry_run=dry_run,
            execute_real=execute_real,
            authorization_scope=scope,
            allow_real_provider=bool(execute_real),
            write_artifacts=False,
        )
    except GlobalGrammarCanaryError as exc:
        print(f"[a40_global_v20_grammar_canary] rejected={exc}")
        print("[a40_global_v20_grammar_canary] STOP — revue humaine. Phase 3B INCOMPLETE.")
        return 2

    focused = None
    post = None
    if execute_real and not result.blocked_precall and not skip_suite:
        audit = audit_dir(project_name)
        print("[a40_global_v20_grammar_canary] running focused + full suite")
        focused = run_focused_suite(junit_path=audit / "a40_post_focused.xml")
        post = run_full_suite(junit_path=audit / "a40_post_full.xml")
        delta_path = write_a40_post_delta(project_name, post=post, focused=focused)
        tests_label = post.get("summary") or tests_label
        delta = json.loads(delta_path.read_text(encoding="utf-8"))
        new_failures = str(delta.get("new_failure_count") or 0)
        if int(post.get("failed") or 0):
            if result.execution:
                result.execution["result"] = "FAIL"
                result.execution["ready_for_compact_global_real_call_preflight"] = "NO"

    write_canary_artifacts(
        project_name,
        result,
        tests=tests_label,
        extra_header={"new_failures": new_failures},
    )

    print(f"[a40_global_v20_grammar_canary] accepted={result.accepted} mode={result.mode}")
    if result.error:
        print(f"[a40_global_v20_grammar_canary] error={result.error}")
    print(f"[a40_global_v20_grammar_canary] generate_attempts={result.engine_generate_attempts}")
    print(f"[a40_global_v20_grammar_canary] anthropic_posts={result.anthropic_post_attempts}")
    if result.dry_run and not execute_real:
        safe = {
            "request_identity": result.dry_run.get("request_identity"),
            "schema_hash": result.dry_run.get("schema_hash"),
            "prompt_hash": result.dry_run.get("prompt_hash"),
            "synthetic_fixture_hash": result.dry_run.get("synthetic_fixture_hash"),
            "schema_identity": result.dry_run.get("schema_identity"),
            "prompt_version": result.dry_run.get("prompt_version"),
            "transport": result.dry_run.get("transport"),
            "provider_calls": 0,
        }
        print(json.dumps(safe, ensure_ascii=False, indent=2))
    if execute_real:
        print(f"[a40_global_v20_grammar_canary] result={(result.execution or {}).get('result')}")
        print(
            "[a40_global_v20_grammar_canary] ready_preflight="
            f"{(result.execution or {}).get('ready_for_compact_global_real_call_preflight')}"
        )
    print("[a40_global_v20_grammar_canary] STOP — revue humaine. Phase 3B INCOMPLETE.")
    if result.blocked_precall or not result.accepted:
        return 2
    if execute_real:
        verdict = (result.execution or {}).get("result")
        return 0 if verdict == "PASS" else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
