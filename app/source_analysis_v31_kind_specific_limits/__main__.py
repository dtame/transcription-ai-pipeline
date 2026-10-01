"""Entrée offline 3B.7.7A.30. 0 provider."""

from __future__ import annotations

from app.source_analysis_v31_kind_specific_limits.constants import PHASE, PROJECT_NAME
from app.source_analysis_v31_kind_specific_limits.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_kind_specific_limits.runner import build_bundle
from app.source_analysis_v31_kind_specific_limits.writer import write_audit_bundle


def main() -> None:
    assert_offline_package()
    assert_analyzer_not_wired()
    bundle = build_bundle(project_name=PROJECT_NAME, tests="offline A.30")
    written = write_audit_bundle(PROJECT_NAME, bundle)
    header = bundle["header"]
    print(f"[a30_limits] phase={PHASE} result={header.get('result')}")
    print(f"[a30_limits] provider_calls={header.get('real_provider_calls')}")
    print(f"[a30_limits] ready={header.get('ready_after')}")
    print(f"[a30_limits] report={written['report']}")
    print("[a30_limits] STOP — revue humaine. Phase 3B INCOMPLETE.")


if __name__ == "__main__":
    main()
