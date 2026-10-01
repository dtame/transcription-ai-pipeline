"""Entrée offline 3B.7.7A.48. 0 provider."""

from __future__ import annotations

from app.source_analysis_v31_global_a48_offline_revalidation.constants import PHASE, PROJECT_NAME
from app.source_analysis_v31_global_a48_offline_revalidation.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_a48_offline_revalidation.runner import build_bundle
from app.source_analysis_v31_global_a48_offline_revalidation.writer import write_audit_bundle


def main() -> None:
    assert_offline_package()
    assert_analyzer_not_wired()
    bundle = build_bundle(project_name=PROJECT_NAME, tests="offline A.48")
    written = write_audit_bundle(PROJECT_NAME, bundle)
    header = bundle["header"]
    print(f"[a48] phase={PHASE} result={header.get('result')}")
    print("[a48] provider_calls=0")
    print(f"[a48] a46_status={header.get('a46_historical_status')}")
    print(f"[a48] publication_eligible={header.get('publication_eligible')}")
    print(f"[a48] source_map={header.get('source_map')}")
    print(f"[a48] report={written['report']}")
    print("[a48] STOP — revue humaine. Phase 3B INCOMPLETE. No provider call. No publication.")


if __name__ == "__main__":
    main()
