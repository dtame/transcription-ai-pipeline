"""Entrée offline 3B.7.7A.32. 0 provider."""

from __future__ import annotations

from app.source_analysis_v31_src_typo_forensics.constants import PHASE, PROJECT_NAME
from app.source_analysis_v31_src_typo_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_src_typo_forensics.runner import build_bundle
from app.source_analysis_v31_src_typo_forensics.writer import write_audit_bundle


def main() -> None:
    assert_offline_package()
    assert_analyzer_not_wired()
    bundle = build_bundle(project_name=PROJECT_NAME, tests="offline A.32")
    written = write_audit_bundle(PROJECT_NAME, bundle)
    header = bundle["header"]
    print(f"[a32_src] phase={PHASE} result={header.get('result')}")
    print(f"[a32_src] provider_calls={header.get('real_provider_calls')}")
    print(f"[a32_src] win007=NOT READY ready=6/7")
    print(f"[a32_src] report={written['report']}")
    print("[a32_src] STOP — revue humaine. Phase 3B INCOMPLETE.")


if __name__ == "__main__":
    main()
