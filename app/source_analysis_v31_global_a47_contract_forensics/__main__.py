"""Entrée offline 3B.7.7A.47. 0 provider."""

from __future__ import annotations

from app.source_analysis_v31_global_a47_contract_forensics.constants import PHASE, PROJECT_NAME
from app.source_analysis_v31_global_a47_contract_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_a47_contract_forensics.runner import build_bundle
from app.source_analysis_v31_global_a47_contract_forensics.writer import write_audit_bundle


def main() -> None:
    assert_offline_package()
    assert_analyzer_not_wired()
    bundle = build_bundle(project_name=PROJECT_NAME, tests="offline A.47")
    written = write_audit_bundle(PROJECT_NAME, bundle)
    header = bundle["header"]
    print(f"[a47] phase={PHASE} result={header.get('result')}")
    print("[a47] provider_calls=0")
    print(f"[a47] a46_status={header.get('a46_historical_status')}")
    print(f"[a47] counterfactual={header.get('a46_unchanged_raw_response_counterfactual')}")
    print(f"[a47] selected_intent_limit={header.get('selected_intent_limit')}")
    print(f"[a47] report={written['report']}")
    print("[a47] STOP — revue humaine. Phase 3B INCOMPLETE. No provider call.")


if __name__ == "__main__":
    main()
