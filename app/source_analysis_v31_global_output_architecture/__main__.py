"""Entrée offline 3B.7.7A.39. 0 provider."""

from __future__ import annotations

from app.source_analysis_v31_global_output_architecture.constants import PHASE, PROJECT_NAME
from app.source_analysis_v31_global_output_architecture.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_output_architecture.runner import build_bundle
from app.source_analysis_v31_global_output_architecture.writer import write_audit_bundle


def main() -> None:
    assert_offline_package()
    assert_analyzer_not_wired()
    bundle = build_bundle(project_name=PROJECT_NAME, tests="offline A.39")
    written = write_audit_bundle(PROJECT_NAME, bundle)
    header = bundle["header"]
    print(f"[a39] phase={PHASE} result={header.get('result')}")
    print(f"[a39] provider_calls=0 request={header.get('a38_request')}")
    print(f"[a39] readiness={header.get('readiness')}")
    print(f"[a39] report={written['report']}")
    print("[a39] STOP — revue humaine. Phase 3B INCOMPLETE.")


if __name__ == "__main__":
    main()
