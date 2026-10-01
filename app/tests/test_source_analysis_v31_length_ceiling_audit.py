"""Écrit les artefacts A.29. N'écrase pas A.19–A.28. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_local_v2.granularity import (
    TEXT_HARD_LIMITS,
    V11_MINIMAL_TEXT_HARD_LIMITS,
)
from app.source_analysis_v31_length_ceiling.constants import (
    BOUNDARY_ARTIFACT,
    COUNTERFACTUAL_ARTIFACT,
    DECISION_ARTIFACT,
    DISTRIBUTION_ARTIFACT,
    FORENSICS_ARTIFACT,
    OPTIONS_ARTIFACT,
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REPORT_NAME,
    WIN003_RETRY_AUTHORIZED,
)
from app.source_analysis_v31_length_ceiling.evidence import (
    protected_a29_historical_hashes,
    win003_raw_path,
)
from app.source_analysis_v31_length_ceiling.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_length_ceiling.runner import build_bundle
from app.source_analysis_v31_length_ceiling.writer import write_audit_bundle
from app.source_analysis_v31_remaining_windows.constants import REPORT_NAME as A28_REPORT


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_without_touching_history():
    assert_offline_package()
    assert_analyzer_not_wired()
    a28 = audit_dir(PROJECT_NAME) / A28_REPORT
    raw = win003_raw_path(PROJECT_NAME)
    before_report = sha256_of_file(a28) if a28.is_file() else None
    before_raw = sha256_of_file(raw)
    before_protected = protected_a29_historical_hashes()
    before_limits = dict(TEXT_HARD_LIMITS)
    before_historical = dict(V11_MINIMAL_TEXT_HARD_LIMITS)

    bundle = build_bundle(tests="offline A.29")
    written = write_audit_bundle(PROJECT_NAME, bundle, tests="offline A.29")

    assert written["boundary"].name == BOUNDARY_ARTIFACT
    assert written["distribution"].name == DISTRIBUTION_ARTIFACT
    assert written["forensics"].name == FORENSICS_ARTIFACT
    assert written["options"].name == OPTIONS_ARTIFACT
    assert written["counterfactual"].name == COUNTERFACTUAL_ARTIFACT
    assert written["decision"].name == DECISION_ARTIFACT
    assert written["report"].name == REPORT_NAME

    report_text = written["report"].read_text(encoding="utf-8")
    assert report_text.startswith(
        "# PHASE 3B.7.7A.29 — WIN003 VALUE-LENGTH CEILING FORENSICS"
    )
    assert "REAL PROVIDER CALLS =" in report_text
    assert "\n0\n" in report_text
    assert "REAL WINDOW CALLS =" in report_text
    assert "A.28 STATUS =" in report_text
    assert "FAIL unchanged" in report_text
    assert "READY WINDOWS =" in report_text
    assert "3 / 7" in report_text
    assert "PROVIDER SCHEMA ENFORCES 200 =" in report_text
    assert "NO" in report_text
    assert "CANONICAL MODEL REQUIRES 200 =" in report_text
    assert "COUNTERFACTUAL 225 =" in report_text
    assert "SELECTED POLICY =" in report_text
    assert "USE_KIND_SPECIFIC_LIMITS" in report_text
    assert "PROMPT CHANGE REQUIRED =" in report_text
    assert "TRANSPORT VERSION CHANGE REQUIRED =" in report_text
    assert "SCHEMA IDENTITY CHANGES =" in report_text
    assert "A.18 GRAMMAR PROOF STILL APPLIES =" in report_text
    assert "YES" in report_text
    assert "WIN003 FUTURE ACTION =" in report_text
    assert "NO_RETRY_REQUIRED_SAVED_RESPONSE_CAN_BE_REVALIDATED" in report_text
    assert "SOURCE MAP =" in report_text
    assert "NOT PUBLISHED" in report_text
    assert "PHASE 3B =" in report_text
    assert "INCOMPLETE" in report_text
    assert "NEXT ACTION =" in report_text
    assert "HUMAN REVIEW" in report_text
    assert "theme 212 chars" in report_text
    assert "IDEA 209 chars" in report_text
    assert "EXAMPLE 213 chars" in report_text

    header = bundle["header"]
    assert header["phase"] == PHASE
    assert header["result"] == "PASS"
    assert header["real_provider_calls"] == REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert WIN003_RETRY_AUTHORIZED is False
    assert bundle["replay"]["reproduced"] is True
    assert bundle["counterfactual"]["counterfactual_225"] == "PASS"
    assert bundle["counterfactual"]["counterfactual_250"] == "PASS"
    assert bundle["counterfactual"]["counterfactual_300"] == "PASS"
    assert bundle["decision"]["win003_not_ready"] is True
    assert bundle["options"]["repair_policy"]["implemented"] is False
    assert TEXT_HARD_LIMITS == before_limits
    assert V11_MINIMAL_TEXT_HARD_LIMITS == before_historical
    assert not source_map_path(PROJECT_NAME).is_file()

    after_report = sha256_of_file(a28) if a28.is_file() else None
    after_raw = sha256_of_file(raw)
    after_protected = protected_a29_historical_hashes()
    assert after_report == before_report
    assert after_raw == before_raw
    assert after_protected == before_protected


def test_tmp_write_does_not_create_source_map(tmp_path: Path):
    bundle = build_bundle(PROJECT_NAME, tests="tmp A.29")
    written = write_audit_bundle(
        PROJECT_NAME,
        bundle,
        sortie_dir=tmp_path,
        tests="tmp A.29",
    )
    assert written["report"].is_file()
    assert not (tmp_path / PROJECT_NAME / "source_map.json").exists()
    assert V11_MINIMAL_TEXT_HARD_LIMITS["theme"] == 200
