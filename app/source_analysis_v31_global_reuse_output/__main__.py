"""Entrée offline 3B.7.7A.43. 0 provider."""

from __future__ import annotations

from app.source_analysis_v31_global_reuse_output.constants import PHASE, PROJECT_NAME
from app.source_analysis_v31_global_reuse_output.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_reuse_output.runner import build_bundle
from app.source_analysis_v31_global_reuse_output.writer import write_audit_bundle


def main() -> None:
    assert_offline_package()
    assert_analyzer_not_wired()
    bundle = build_bundle(project_name=PROJECT_NAME, tests="offline A.43")
    written = write_audit_bundle(PROJECT_NAME, bundle)
    header = bundle["header"]
    print(f"[a43] phase={PHASE} result={header.get('result')}")
    print(f"[a43] provider_calls=0 request={header.get('a42_request')}")
    print(f"[a43] readiness={header.get('readiness')}")
    print(f"[a43] report={written['report']}")
    print("[a43] STOP — revue humaine. Phase 3B INCOMPLETE.")


if __name__ == "__main__":
    main()
