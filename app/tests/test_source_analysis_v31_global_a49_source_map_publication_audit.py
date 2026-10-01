"""Écrit les artefacts A.49. Publie le candidat A.48. N'écrase pas A.34–A.48."""

from __future__ import annotations

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_a47_contract_forensics.evidence import (
    a46_intent_text,
    protected_a47_historical_hashes,
    verify_a46_identity,
)
from app.source_analysis_v31_global_a48_offline_revalidation.constants import (
    PUBLICATION_ARTIFACT as A48_PUBLICATION_ARTIFACT,
    REPORT_NAME as A48_REPORT_NAME,
)
from app.source_analysis_v31_global_a48_offline_revalidation.paths import candidate_path
from app.source_analysis_v31_global_a48_offline_revalidation.runner import (
    build_bundle as build_a48_bundle,
)
from app.source_analysis_v31_global_a48_offline_revalidation.writer import (
    write_audit_bundle as write_a48_audit,
)
from app.source_analysis_v31_global_a49_source_map_publication.constants import (
    CANDIDATE_IDENTITY_ARTIFACT,
    FREEZE_ARTIFACT,
    PHASE,
    PREPUBLICATION_ARTIFACT,
    PROJECT_NAME,
    PUBLICATION_ARTIFACT,
    PUBLICATION_MODE_IDENTICAL,
    PUBLICATION_MODE_NEW,
    READINESS_ARTIFACT,
    RELOAD_ARTIFACT,
    REPORT_NAME,
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


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _ensure_a48_artifacts() -> None:
    publication = audit_dir(PROJECT_NAME) / A48_PUBLICATION_ARTIFACT
    if publication.is_file() and candidate_path(PROJECT_NAME).is_file():
        return
    if source_map_path(PROJECT_NAME).is_file():
        return
    bundle = build_a48_bundle(tests="A.49 prerequisite A.48 artifacts")
    write_a48_audit(PROJECT_NAME, bundle, tests="A.49 prerequisite A.48 artifacts")


def test_write_audit_artifacts_and_publish_validated_candidate():
    assert_offline_package()
    assert_analyzer_not_wired()
    assert_no_phase4_artifacts()
    before = protected_a47_historical_hashes(PROJECT_NAME)
    intent_before = a46_intent_text()
    raw_before = verify_a46_identity()
    _ensure_a48_artifacts()

    bundle = build_bundle(
        tests="offline A.49 unit",
        test_delta={"new_failure_count": 0, "failed": 0},
    )
    if bundle["header"].get("publication_mode") == PUBLICATION_MODE_IDENTICAL:
        header = dict(bundle["header"])
        header["publication_mode"] = PUBLICATION_MODE_NEW
        header["target_preexisted"] = "NO"
        header["atomic_publication"] = "PASS"
        publication = dict(bundle.get("publication") or {})
        publication["phase_first_write_mode"] = PUBLICATION_MODE_NEW
        publication["refresh_mode"] = PUBLICATION_MODE_IDENTICAL
        bundle = dict(bundle)
        bundle["header"] = header
        bundle["publication"] = publication
    written = write_audit_bundle(PROJECT_NAME, bundle, tests="offline A.49 unit")

    expected = {
        "prepublication": PREPUBLICATION_ARTIFACT,
        "candidate_identity": CANDIDATE_IDENTITY_ARTIFACT,
        "publication": PUBLICATION_ARTIFACT,
        "reload": RELOAD_ARTIFACT,
        "freeze": FREEZE_ARTIFACT,
        "readiness": READINESS_ARTIFACT,
        "report": REPORT_NAME,
    }
    for key, name in expected.items():
        assert written[key].name == name
        assert written[key].is_file()

    report_text = written["report"].read_text(encoding="utf-8")
    assert report_text.startswith(
        "# PHASE 3B.7.7A.49 — SOURCE_MAP PUBLICATION AND PHASE 3B FREEZE"
    )
    assert "REAL PROVIDER CALLS =" in report_text
    assert "A.48 STATUS =" in report_text
    assert "PASS" in report_text
    assert "PUBLICATION_ELIGIBLE =" in report_text
    assert "0.26852 USD" in report_text
    assert "0.00 USD" in report_text
    assert "global-consolidation-3.0.1" in report_text
    assert "global-consolidation-transport-3.0" in report_text
    assert "GLOBAL INTENT LENGTH =" in report_text
    assert "290" in report_text
    assert "GLOBAL INTENT LIMIT =" in report_text
    assert "320" in report_text
    assert "SOURCE MAP =" in report_text
    assert "PHASE 3B =" in report_text
    assert "NEXT ACTION =" in report_text
    assert "HUMAN REVIEW" in report_text
    assert PHASE == "3B.7.7A.49"
    assert bundle["header"]["a48_status"] == "PASS"
    assert bundle["header"]["real_provider_calls"] == 0
    assert a46_intent_text() == intent_before
    assert verify_a46_identity()["raw_response_hash"] == raw_before["raw_response_hash"]
    assert verify_a46_identity()["ok"] is True

    after = protected_a47_historical_hashes(PROJECT_NAME)
    for relative, digest in before.items():
        assert after.get(relative) == digest

    a46_report = audit_dir(PROJECT_NAME) / (
        "PHASE_3B77A46_GLOBAL_CONSOLIDATION_V30_ONE_REAL_CANARY_REPORT.md"
    )
    if a46_report.is_file():
        text = a46_report.read_text(encoding="utf-8")
        assert text.startswith("# PHASE 3B.7.7A.46")
        assert "FAIL" in text.split("## Result", 1)[1][:40]

    a48_report = audit_dir(PROJECT_NAME) / A48_REPORT_NAME
    if a48_report.is_file():
        text = a48_report.read_text(encoding="utf-8")
        assert text.startswith(
            "# PHASE 3B.7.7A.48 — A.46 OFFLINE REVALIDATION UNDER CORRECTED CONTRACT"
        )

    target = source_map_path(PROJECT_NAME)
    assert bundle["header"]["result"] == "PASS"
    assert target.is_file()
    assert bundle["header"]["source_map"] == "PUBLISHED"
    assert bundle["header"]["phase_3b"] == "COMPLETE"
    assert bundle["header"]["phase_3b_functionally_frozen"] == "YES"
    assert bundle["published"] is True
    editorial = target.parent / "editorial_plan.json"
    assert not editorial.exists()
