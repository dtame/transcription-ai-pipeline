"""
CLI offline de la politique 3B.5.2.

Usage :
    python -m app.source_analysis_long_run_policy.cli <projet>

Aucun --real-call. Aucun engine.generate(). Aucun réseau.
N'écrit pas le .env réel.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.source_analysis_long_run_policy.audit import (
    assert_offline_package,
    assert_source_map_absent,
    build_deterministic_policy,
    inspect_project_state,
)
from app.source_analysis_long_run_policy.constants import (
    MODE,
    PHASE,
    POLICY_ARTIFACT_NAME,
    REPORT_NAME,
    SELECTED_POLICY_STATUS,
)
from app.source_analysis_long_run_policy.integrity import (
    assert_protected_unchanged,
    snapshot_long_run_policy_protected,
)
from app.source_analysis_long_run_policy.report import render_report
from app.source_analysis_long_run_policy.writer import (
    assert_no_production_source_map,
    policy_path,
    report_path,
    write_bytes_atomic,
)


@dataclass
class LongRunPolicyResult:
    project_name: str
    outcome: str = "PASS"
    policy_sha256: str = ""
    policy_deterministic: bool = False
    protected_unchanged: bool = False
    source_map_present: bool = False
    project_state_status: str = ""
    project_state_error: str | None = None
    files_created: list[str] = field(default_factory=list)
    policy: dict[str, Any] = field(default_factory=dict)


def run_long_run_policy(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    write_artifacts: bool = True,
) -> LongRunPolicyResult:
    assert_offline_package()
    assert_source_map_absent(project_name, sortie_dir=sortie_dir)
    before = snapshot_long_run_policy_protected(
        project_name, sortie_dir=sortie_dir, require_all=False
    )
    state = inspect_project_state(project_name)
    payload, sha1, sha2 = build_deterministic_policy()
    result = LongRunPolicyResult(
        project_name=project_name,
        policy=payload,
        policy_sha256=sha1,
        policy_deterministic=sha1 == sha2,
        project_state_status=str(state.get("status") or ""),
        project_state_error=state.get("error"),
        source_map_present=False,
    )
    if write_artifacts:
        write_bytes_atomic(
            policy_path(project_name, sortie_dir=sortie_dir),
            payload,
        )
        result.files_created.append(POLICY_ARTIFACT_NAME)
        write_bytes_atomic(
            report_path(project_name, sortie_dir=sortie_dir),
            render_report(payload, sha256=sha1),
        )
        result.files_created.append(REPORT_NAME)
    after = snapshot_long_run_policy_protected(
        project_name, sortie_dir=sortie_dir, require_all=False
    )
    assert_protected_unchanged(before, after)
    assert_no_production_source_map(project_name, sortie_dir=sortie_dir)
    result.protected_unchanged = True
    if not result.policy_deterministic:
        result.outcome = "FAIL"
    if payload.get("selected_policy", {}).get("status") != SELECTED_POLICY_STATUS:
        result.outcome = "FAIL"
    if payload.get("execution", {}).get("execution_authorized"):
        result.outcome = "FAIL"
    if payload.get("execution", {}).get("provider_call_performed"):
        result.outcome = "FAIL"
    if payload.get("selected_policy", {}).get("third_global_timeout_escalation_allowed"):
        result.outcome = "FAIL"
    if state.get("status") == "SUCCESS" or state.get("status") == "completed":
        result.outcome = "FAIL"
    return result


def _usage() -> None:
    print("Usage  : python -m app.source_analysis_long_run_policy.cli <projet>")
    print("Mode   : OFFLINE_POLICY. Aucun --real-call. 0 appel réseau.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0
    if "--real-call" in argv:
        print("[ERREUR] --real-call est interdit. Cette politique est OFFLINE.")
        return 2
    project_name = argv[0]
    flags = set(argv[1:])
    if flags:
        print(f"[ERREUR] option(s) inconnue(s) : {sorted(flags)}")
        _usage()
        return 2

    print(f"[long_run_policy] projet={project_name}")
    print(f"[long_run_policy] phase={PHASE} mode={MODE}")
    print("[long_run_policy] aucun engine.generate(), aucun réseau")
    print(f"[long_run_policy] status={SELECTED_POLICY_STATUS}")
    print("[long_run_policy] execution_authorized=False")

    result = run_long_run_policy(project_name)
    print(f"[long_run_policy] outcome={result.outcome}")
    print(f"[long_run_policy] policy_sha={result.policy_sha256}")
    print(f"[long_run_policy] deterministic={result.policy_deterministic}")
    print(
        f"[long_run_policy] state={result.project_state_status} "
        f"error={result.project_state_error}"
    )
    print(f"[long_run_policy] protected_unchanged={result.protected_unchanged}")
    print("[long_run_policy] STOP — aucun nouvel appel Anthropic. Revue humaine.")
    return 0 if result.outcome == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
