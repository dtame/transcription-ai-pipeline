"""CLI A.16 offline forensics. 0 provider."""

from __future__ import annotations

from app.source_analysis_v2_a15_forensics.constants import (
    MODE,
    PHASE,
    PROJECT_NAME,
)
from app.source_analysis_v2_a15_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v2_a15_forensics.runner import build_bundle
from app.source_analysis_v2_a15_forensics.writer import write_audit_bundle


def main() -> None:
    assert_offline_package()
    assert_analyzer_not_wired()
    print(f"[a16_forensics] projet={PROJECT_NAME}")
    print(f"[a16_forensics] phase={PHASE} mode={MODE}")
    bundle = build_bundle(tests="written by __main__; run full suite separately")
    written = write_audit_bundle(PROJECT_NAME, bundle)
    print(f"[a16_forensics] result={bundle['header']['result']}")
    print(f"[a16_forensics] invalid_links={bundle['forensics']['invalid_link_count']}")
    print(f"[a16_forensics] artifacts={list(written)}")
    print("[a16_forensics] STOP — revue humaine. Phase 3B INCOMPLETE.")


if __name__ == "__main__":
    main()
