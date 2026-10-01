"""Entrée offline 3B.7.7A.49. 0 provider. Publication du candidat A.48."""

from __future__ import annotations

from app.source_analysis_v31_global_a49_source_map_publication.constants import (
    PHASE,
    PROJECT_NAME,
)
from app.source_analysis_v31_global_a49_source_map_publication.offline import (
    assert_analyzer_not_wired,
    assert_no_phase4_artifacts,
    assert_offline_package,
)
from app.source_analysis_v31_global_a49_source_map_publication.runner import build_bundle
from app.source_analysis_v31_global_a49_source_map_publication.writer import (
    write_audit_bundle,
)


def main() -> None:
    assert_offline_package()
    assert_analyzer_not_wired()
    assert_no_phase4_artifacts()
    bundle = build_bundle(project_name=PROJECT_NAME, tests="offline A.49")
    written = write_audit_bundle(PROJECT_NAME, bundle)
    header = bundle["header"]
    print(f"[a49] phase={PHASE} result={header.get('result')}")
    print("[a49] provider_calls=0")
    print(f"[a49] a48_status={header.get('a48_status')}")
    print(f"[a49] publication_eligible={header.get('publication_eligible')}")
    print(f"[a49] publication_mode={header.get('publication_mode')}")
    print(f"[a49] source_map={header.get('source_map')}")
    print(f"[a49] phase_3b={header.get('phase_3b')}")
    print(f"[a49] report={written['report']}")
    print(
        "[a49] STOP — revue humaine. No provider call. "
        "No Editorial Planner. No Phase 4."
    )


if __name__ == "__main__":
    main()
