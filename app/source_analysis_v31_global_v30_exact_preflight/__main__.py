"""Entrée offline 3B.7.7A.45. 0 provider."""

from __future__ import annotations

from app.source_analysis_v31_global_v30_exact_preflight.constants import PHASE, PROJECT_NAME
from app.source_analysis_v31_global_v30_exact_preflight.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_v30_exact_preflight.runner import build_bundle
from app.source_analysis_v31_global_v30_exact_preflight.writer import write_audit_bundle


def main() -> None:
    assert_offline_package()
    assert_analyzer_not_wired()
    bundle = build_bundle(project_name=PROJECT_NAME, tests="offline A.45")
    written = write_audit_bundle(PROJECT_NAME, bundle)
    header = bundle["header"]
    print(f"[a45] phase={PHASE} result={header.get('result')}")
    print(f"[a45] provider_calls=0 a44_request={header.get('a44_request')}")
    print(f"[a45] request_hash={header.get('exact_request_hash')}")
    print(f"[a45] hard_output={header.get('hard_planning_output')}")
    print(
        "[a45] ready="
        f"{header.get('ready_for_one_real_global_consolidation_canary')}"
    )
    print(f"[a45] report={written['report']}")
    print("[a45] STOP — revue humaine. Phase 3B INCOMPLETE. No provider call.")


if __name__ == "__main__":
    main()
