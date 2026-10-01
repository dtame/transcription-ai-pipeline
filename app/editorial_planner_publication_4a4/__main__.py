"""Offline entry for Phase 4A.4. 0 provider. Publish the A.3.5 candidate."""

from __future__ import annotations

from app.editorial_planner_publication_4a4.constants import PHASE, PROJECT_NAME
from app.editorial_planner_publication_4a4.offline import (
    assert_analyzer_untouched,
    assert_no_book_generator,
    assert_offline_package,
)
from app.editorial_planner_publication_4a4.runner import build_bundle
from app.editorial_planner_publication_4a4.writer import write_audit_bundle


def main() -> None:
    assert_offline_package()
    assert_analyzer_untouched()
    assert_no_book_generator()
    bundle = build_bundle(project_name=PROJECT_NAME, tests="offline 4A.4")
    written = write_audit_bundle(bundle, tests="offline 4A.4")
    header = bundle["header"]
    print(f"[4a4] phase={PHASE} result={header.get('result')}")
    print("[4a4] provider_calls=0")
    print(f"[4a4] candidate_identity={header.get('candidate_identity')}")
    print(f"[4a4] publication_mode={header.get('publication_mode')}")
    print(f"[4a4] editorial_plan={header.get('editorial_plan_json')}")
    print(f"[4a4] phase_4={header.get('phase_4_status')}")
    print(f"[4a4] report={written['report']}")
    print(
        "[4a4] STOP — revue humaine. No provider call. "
        "Book Generator not started."
    )


if __name__ == "__main__":
    main()
