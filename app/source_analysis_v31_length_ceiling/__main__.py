"""Entrée offline 3B.7.7A.29. 0 provider."""

from __future__ import annotations

from app.source_analysis_v31_length_ceiling.constants import PHASE, PROJECT_NAME
from app.source_analysis_v31_length_ceiling.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_length_ceiling.runner import build_bundle
from app.source_analysis_v31_length_ceiling.writer import write_audit_bundle


def main() -> None:
    assert_offline_package()
    assert_analyzer_not_wired()
    bundle = build_bundle(project_name=PROJECT_NAME, tests="offline A.29")
    written = write_audit_bundle(PROJECT_NAME, bundle)
    header = bundle["header"]
    print(f"[a29_length] phase={PHASE} result={header.get('result')}")
    print(f"[a29_length] provider_calls={header.get('real_provider_calls')}")
    print(f"[a29_length] report={written['report']}")
    print("[a29_length] STOP — revue humaine. Phase 3B INCOMPLETE.")


if __name__ == "__main__":
    main()
