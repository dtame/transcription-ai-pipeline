"""Entrée offline 3B.7.7A.36. 0 provider."""

from __future__ import annotations

from app.source_analysis_v31_global_canary_forensics.constants import PHASE, PROJECT_NAME
from app.source_analysis_v31_global_canary_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_canary_forensics.runner import build_bundle
from app.source_analysis_v31_global_canary_forensics.writer import write_audit_bundle


def main() -> None:
    assert_offline_package()
    assert_analyzer_not_wired()
    bundle = build_bundle(project_name=PROJECT_NAME, tests="offline A.36")
    written = write_audit_bundle(PROJECT_NAME, bundle)
    header = bundle["header"]
    print(f"[a36_forensics] phase={PHASE} result={header.get('result')}")
    print(f"[a36_forensics] provider_calls={header.get('real_provider_calls')}")
    print(f"[a36_forensics] a35={header.get('a35_status')} request={header.get('a35_request')}")
    print(f"[a36_forensics] readiness={header.get('readiness')}")
    print(f"[a36_forensics] report={written['report']}")
    print("[a36_forensics] STOP — revue humaine. Phase 3B INCOMPLETE.")


if __name__ == "__main__":
    main()
