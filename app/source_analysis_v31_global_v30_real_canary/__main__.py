"""
CLI 3B.7.7A.46 — one real Anthropic global consolidation 3.0 canary.

Défaut : --dry-run (0 POST).
Réel : --authorization-scope GLOBAL_CONSOLIDATION_3_0_REAL_CANARY_EXACT_REQUEST_ONLY --execute-real
"""

from __future__ import annotations

import json
import sys

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v31_global_v30_real_canary.constants import (
    AUTHORIZATION_SCOPE,
    MODE,
    PHASE,
    PROJECT_NAME,
)
from app.source_analysis_v31_global_v30_real_canary.guard import GlobalRealCanaryError
from app.source_analysis_v31_global_v30_real_canary.post_tests import (
    run_broader_slices,
    run_focused_suite,
    write_a46_baseline,
    write_a46_post_delta,
)
from app.source_analysis_v31_global_v30_real_canary.runner import (
    run_global_v30_real_canary,
)
from app.source_analysis_v31_global_v30_real_canary.writer import write_canary_artifacts


def _usage() -> None:
    print(
        "Usage : python -m app.source_analysis_v31_global_v30_real_canary "
        "<projet> --authorization-scope "
        "GLOBAL_CONSOLIDATION_3_0_REAL_CANARY_EXACT_REQUEST_ONLY --dry-run"
    )
    print(
        "Réel  : ... --authorization-scope "
        "GLOBAL_CONSOLIDATION_3_0_REAL_CANARY_EXACT_REQUEST_ONLY --execute-real"
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

    print(f"[a46_global_v30_real_canary] projet={project_name}")
    print(f"[a46_global_v30_real_canary] phase={PHASE} mode={MODE}")
    print(f"[a46_global_v30_real_canary] scope={scope}")
    print(f"[a46_global_v30_real_canary] dry_run={dry_run} execute_real={execute_real}")
    print("[a46_global_v30_real_canary] authorized_calls=1 retries=0")

    tests_label = "not run"
    new_failures = "0"
    if execute_real and not skip_suite:
        audit = audit_dir(project_name)
        print(
            "[a46_global_v30_real_canary] running pre-call focused A.45/A.46 slices "
            "(not the full historical suite)"
        )
        focused = run_focused_suite(junit_path=audit / "a46_pre_focused.xml")
        write_a46_baseline(project_name, focused=focused)
        tests_label = f"pre-call focused: {focused.get('summary')}"
        print(f"[a46_global_v30_real_canary] baseline={tests_label}")
        if int(focused.get("failed") or 0) or int(focused.get("errors") or 0):
            print("[a46_global_v30_real_canary] BLOCKED_PRECALL — focused tests failed")
            dummy = run_global_v30_real_canary(
                project_name,
                dry_run=True,
                execute_real=False,
                authorization_scope=scope or AUTHORIZATION_SCOPE,
                write_artifacts=False,
            )
            dummy.mode = "BLOCKED_PRECALL"
            dummy.blocked_precall = True
            dummy.error = f"focused tests failed: {tests_label}"
            write_canary_artifacts(
                project_name,
                dummy,
                tests=tests_label,
                extra_header={"new_failures": "baseline", "test_scope": focused.get("scope")},
            )
            print("[a46_global_v30_real_canary] STOP — revue humaine. Phase 3B INCOMPLETE.")
            return 2

    try:
        result = run_global_v30_real_canary(
            project_name,
            dry_run=dry_run,
            execute_real=execute_real,
            authorization_scope=scope,
            allow_real_provider=bool(execute_real),
            write_artifacts=False,
        )
    except GlobalRealCanaryError as exc:
        print(f"[a46_global_v30_real_canary] rejected={exc}")
        print("[a46_global_v30_real_canary] STOP — revue humaine. Phase 3B INCOMPLETE.")
        return 2

    focused = None
    broader = None
    if execute_real and not result.blocked_precall and not skip_suite:
        audit = audit_dir(project_name)
        print(
            "[a46_global_v30_real_canary] running post-call focused + broader "
            "global-consolidation slices (not full historical suite)"
        )
        focused = run_focused_suite(junit_path=audit / "a46_post_focused.xml")
        broader = run_broader_slices(junit_path=audit / "a46_post_broader.xml")
        delta_path = write_a46_post_delta(
            project_name, post=broader, focused=focused
        )
        tests_label = (
            f"post focused={focused.get('summary')}; "
            f"broader slices={broader.get('summary')}; "
            "NOT full historical suite"
        )
        delta = json.loads(delta_path.read_text(encoding="utf-8"))
        new_failures = str(delta.get("new_failure_count") or 0)
        if int(broader.get("failed") or 0) or int(focused.get("failed") or 0):
            if result.execution:
                result.execution["result"] = "FAIL"
                result.execution["publication_eligible"] = "NO"
                result.execution["ready_for_source_map_publication_review"] = "NO"

    write_canary_artifacts(
        project_name,
        result,
        tests=tests_label,
        extra_header={"new_failures": new_failures},
    )

    print(f"[a46_global_v30_real_canary] accepted={result.accepted} mode={result.mode}")
    if result.error:
        print(f"[a46_global_v30_real_canary] error={result.error}")
    print(f"[a46_global_v30_real_canary] generate_attempts={result.engine_generate_attempts}")
    print(f"[a46_global_v30_real_canary] anthropic_posts={result.anthropic_post_attempts}")
    if result.dry_run and not execute_real:
        safe = {
            "request_identity": result.dry_run.get("request_identity"),
            "normalized_input_hash": result.dry_run.get("normalized_input_hash"),
            "request_identity_match": result.dry_run.get("request_identity_match"),
            "schema_hash": result.dry_run.get("schema_hash"),
            "estimated_input": result.dry_run.get("estimated_input"),
            "hard_output": result.dry_run.get("hard_output"),
            "provider_calls": 0,
        }
        print(json.dumps(safe, ensure_ascii=False, indent=2))
    if execute_real:
        print(f"[a46_global_v30_real_canary] result={(result.execution or {}).get('result')}")
        print(
            "[a46_global_v30_real_canary] publication_eligible="
            f"{(result.execution or {}).get('publication_eligible')}"
        )
        print(
            "[a46_global_v30_real_canary] candidate="
            f"{(result.execution or {}).get('candidate_source_map')}"
        )
    print("[a46_global_v30_real_canary] PRODUCTION SOURCE MAP = NOT PUBLISHED")
    print("[a46_global_v30_real_canary] STOP — revue humaine. Phase 3B INCOMPLETE.")
    if result.blocked_precall or not result.accepted:
        return 2
    if execute_real:
        verdict = (result.execution or {}).get("result")
        return 0 if verdict in {"PASS", "PARTIAL"} else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
