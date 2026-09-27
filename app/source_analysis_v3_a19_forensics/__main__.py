"""Entrée offline 3B.7.7A.20. 0 provider."""

from __future__ import annotations

from app.source_analysis_v3_a19_forensics.constants import PHASE, PROJECT_NAME
from app.source_analysis_v3_a19_forensics.runner import build_bundle
from app.source_analysis_v3_a19_forensics.writer import write_audit_bundle


def main() -> None:
    bundle = build_bundle(project_name=PROJECT_NAME, tests="offline A.20")
    written = write_audit_bundle(PROJECT_NAME, bundle)
    header = bundle["header"]
    print(f"[a20_forensics] phase={PHASE} result={header.get('result')}")
    print(f"[a20_forensics] provider_calls={header.get('real_provider_calls')}")
    print(f"[a20_forensics] report={written['report']}")
    print("[a20_forensics] STOP — revue humaine. Phase 3B INCOMPLETE.")


if __name__ == "__main__":
    main()
