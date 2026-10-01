"""Entrée offline 3B.7.7A.34. 0 provider."""

from __future__ import annotations

from app.source_analysis_v31_global_preflight.constants import PHASE, PROJECT_NAME
from app.source_analysis_v31_global_preflight.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_preflight.runner import build_bundle
from app.source_analysis_v31_global_preflight.writer import write_audit_bundle


def main() -> None:
    assert_offline_package()
    assert_analyzer_not_wired()
    bundle = build_bundle(project_name=PROJECT_NAME, tests="offline A.34")
    written = write_audit_bundle(PROJECT_NAME, bundle)
    header = bundle["header"]
    print(f"[a34_preflight] phase={PHASE} result={header.get('result')}")
    print(f"[a34_preflight] provider_calls={header.get('real_provider_calls')}")
    print(f"[a34_preflight] ready={header.get('ready_windows')}")
    print(f"[a34_preflight] freeze={header.get('local_extraction_functionally_frozen')}")
    print(f"[a34_preflight] readiness={header.get('readiness')}")
    print(f"[a34_preflight] report={written['report']}")
    print("[a34_preflight] STOP — revue humaine. Phase 3B INCOMPLETE.")


if __name__ == "__main__":
    main()
