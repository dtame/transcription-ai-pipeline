"""
CLI 3B.7.7A.38 — first real global consolidation canary.

Défaut : --dry-run (0 POST).
Réel : --authorization-scope REAL_GLOBAL_CONSOLIDATION_CANARY_ALL_7_READY_WINDOWS_ONLY --execute-real
"""

from __future__ import annotations

import json
import sys

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v31_global_real_consolidation.constants import (
    AUTHORIZATION_SCOPE,
    MODE,
    PHASE,
    PROJECT_NAME,
)
from app.source_analysis_v31_global_real_consolidation.guard import (
    GlobalRealConsolidationError,
)
from app.source_analysis_v31_global_real_consolidation.post_tests import (
    run_focused_suite,
    run_full_suite,
    write_a38_baseline,
    write_a38_post_delta,
)
from app.source_analysis_v31_global_real_consolidation.runner import (
    run_real_global_consolidation,
)
from app.source_analysis_v31_global_real_consolidation.writer import (
    write_consolidation_artifacts,
)


def _usage() -> None:
    print(
        "Usage : python -m app.source_analysis_v31_global_real_consolidation "
        "<projet> --authorization-scope "
        "REAL_GLOBAL_CONSOLIDATION_CANARY_ALL_7_READY_WINDOWS_ONLY --dry-run"
    )
    print(
        "Réel  : ... --authorization-scope "
        "REAL_GLOBAL_CONSOLIDATION_CANARY_ALL_7_READY_WINDOWS_ONLY --execute-real"
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

    print(f"[a38_real_global_consolidation] projet={project_name}")
    print(f"[a38_real_global_consolidation] phase={PHASE} mode={MODE}")
    print(f"[a38_real_global_consolidation] scope={scope}")
    print(f"[a38_real_global_consolidation] dry_run={dry_run} execute_real={execute_real}")
    print("[a38_real_global_consolidation] authorized_calls=1 actual=0 successful=0 failed=0 retries=0")

    tests_label = "not run"
    new_failures = "0"
    if execute_real and not skip_suite:
        audit = audit_dir(project_name)
        print("[a38_real_global_consolidation] running pre-call full suite")
        baseline = run_full_suite(junit_path=audit / "a38_pre_full.xml")
        write_a38_baseline(project_name, full=baseline)
        tests_label = baseline.get("summary") or tests_label
        print(f"[a38_real_global_consolidation] baseline={tests_label}")
        if int(baseline.get("failed") or 0) or int(baseline.get("errors") or 0):
            print("[a38_real_global_consolidation] BLOCKED_PRECALL — baseline failed")
            dummy = run_real_global_consolidation(
                project_name,
                dry_run=True,
                execute_real=False,
                authorization_scope=scope or AUTHORIZATION_SCOPE,
                write_artifacts=False,
            )
            dummy.mode = "BLOCKED_PRECALL"
            dummy.blocked_precall = True
            dummy.error = f"baseline tests failed: {tests_label}"
            write_consolidation_artifacts(
                project_name,
                dummy,
                tests=tests_label,
                extra_header={"new_failures": "baseline"},
            )
            print("[a38_real_global_consolidation] STOP — revue humaine. Phase 3B INCOMPLETE.")
            return 2

    try:
        result = run_real_global_consolidation(
            project_name,
            dry_run=dry_run,
            execute_real=execute_real,
            authorization_scope=scope,
            allow_real_provider=bool(execute_real),
            write_artifacts=False,
        )
    except GlobalRealConsolidationError as exc:
        print(f"[a38_real_global_consolidation] rejected={exc}")
        print("[a38_real_global_consolidation] STOP — revue humaine. Phase 3B INCOMPLETE.")
        return 2

    focused = None
    post = None
    if execute_real and not result.blocked_precall and not skip_suite:
        audit = audit_dir(project_name)
        print("[a38_real_global_consolidation] running focused + full suite")
        focused = run_focused_suite(junit_path=audit / "a38_post_focused.xml")
        post = run_full_suite(junit_path=audit / "a38_post_full.xml")
        delta_path = write_a38_post_delta(project_name, post=post, focused=focused)
        tests_label = post.get("summary") or tests_label
        delta = json.loads(delta_path.read_text(encoding="utf-8"))
        new_failures = str(delta.get("new_failure_count") or 0)
        if int(post.get("failed") or 0):
            if result.execution:
                result.execution["result"] = "FAIL"

    write_consolidation_artifacts(
        project_name,
        result,
        tests=tests_label,
        extra_header={"new_failures": new_failures},
    )

    print(f"[a38_real_global_consolidation] accepted={result.accepted} mode={result.mode}")
    if result.error:
        print(f"[a38_real_global_consolidation] error={result.error}")
    print(f"[a38_real_global_consolidation] generate_attempts={result.engine_generate_attempts}")
    print(f"[a38_real_global_consolidation] anthropic_posts={result.anthropic_post_attempts}")
    if result.dry_run and not execute_real:
        safe = {
            "request_identity": result.dry_run.get("request_identity"),
            "schema_hash": result.dry_run.get("schema_hash"),
            "prompt_hash": result.dry_run.get("prompt_hash"),
            "input_hash": result.dry_run.get("input_hash"),
            "schema_identity": result.dry_run.get("schema_identity"),
            "prompt_version": result.dry_run.get("prompt_version"),
            "transport": result.dry_run.get("transport"),
            "provider_calls": 0,
            "ready_windows": result.dry_run.get("ready_windows"),
        }
        print(json.dumps(safe, ensure_ascii=False, indent=2))
    if execute_real:
        print(f"[a38_real_global_consolidation] result={(result.execution or {}).get('result')}")
        print(
            "[a38_real_global_consolidation] candidate="
            f"{(result.execution or {}).get('candidate_source_map')}"
        )
    print("[a38_real_global_consolidation] PRODUCTION SOURCE MAP = NOT PUBLISHED")
    print("[a38_real_global_consolidation] STOP — revue humaine. Phase 3B INCOMPLETE.")
    if result.blocked_precall or not result.accepted:
        return 2
    if execute_real:
        verdict = (result.execution or {}).get("result")
        return 0 if verdict in {"PASS", "PARTIAL"} else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
