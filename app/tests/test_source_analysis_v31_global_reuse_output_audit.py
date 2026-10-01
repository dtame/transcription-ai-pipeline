"""Écrit les artefacts A.43. N'écrase pas A.34–A.42. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_canary_forensics.constants import (
    REPORT_NAME as A36_REPORT,
)
from app.source_analysis_v31_global_drop_domain.constants import (
    REPORT_NAME as A41_REPORT,
)
from app.source_analysis_v31_global_grammar_canary.constants import (
    REPORT_NAME as A35_REPORT,
)
from app.source_analysis_v31_global_output_architecture.constants import (
    REPORT_NAME as A39_REPORT,
)
from app.source_analysis_v31_global_preflight.constants import REPORT_NAME as A34_REPORT
from app.source_analysis_v31_global_real_consolidation.constants import (
    REPORT_NAME as A38_REPORT,
)
from app.source_analysis_v31_global_reuse_output.constants import (
    BREAKDOWN_ARTIFACT,
    BUDGET_ARTIFACT,
    CONTRACT_ARTIFACT,
    COST_ARTIFACT,
    OPTIONS_ARTIFACT,
    PHASE,
    PROJECT_NAME,
    QUALITY_ARTIFACT,
    READINESS_ARTIFACT,
    READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REPORT_NAME,
    REUSE_ANALYSIS_ARTIFACT,
    SCHEMA_ARTIFACT,
    SELECTED_ARTIFACT,
    STRESS_ARTIFACT,
)
from app.source_analysis_v31_global_reuse_output.evidence import (
    protected_a43_historical_hashes,
)
from app.source_analysis_v31_global_reuse_output.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_reuse_output.runner import build_bundle
from app.source_analysis_v31_global_reuse_output.writer import write_audit_bundle
from app.source_analysis_v31_global_v11_grammar_canary.constants import (
    REPORT_NAME as A37_REPORT,
)
from app.source_analysis_v31_global_v20_grammar_canary.constants import (
    REPORT_NAME as A40_REPORT,
)
from app.source_analysis_v31_global_v201_contract_canary.constants import (
    REPORT_NAME as A42_REPORT,
)
from app.semantic_canary.integrity import sha256_of_file


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _hash_if_exists(path: Path) -> str | None:
    return sha256_of_file(path) if path.is_file() else None


def test_write_audit_artifacts_without_touching_history():
    assert_offline_package()
    assert_analyzer_not_wired()
    real = audit_dir(PROJECT_NAME)
    before = {
        "a34": _hash_if_exists(real / A34_REPORT),
        "a35": _hash_if_exists(real / A35_REPORT),
        "a36": _hash_if_exists(real / A36_REPORT),
        "a37": _hash_if_exists(real / A37_REPORT),
        "a38": _hash_if_exists(real / A38_REPORT),
        "a39": _hash_if_exists(real / A39_REPORT),
        "a40": _hash_if_exists(real / A40_REPORT),
        "a41": _hash_if_exists(real / A41_REPORT),
        "a42": _hash_if_exists(real / A42_REPORT),
    }
    before_protected = protected_a43_historical_hashes()

    bundle = build_bundle(tests="offline A.43 unit")
    written = write_audit_bundle(PROJECT_NAME, bundle, tests="offline A.43 unit")

    expected = {
        "reuse_analysis": REUSE_ANALYSIS_ARTIFACT,
        "quality": QUALITY_ARTIFACT,
        "breakdown": BREAKDOWN_ARTIFACT,
        "options": OPTIONS_ARTIFACT,
        "selected": SELECTED_ARTIFACT,
        "contract": CONTRACT_ARTIFACT,
        "budget": BUDGET_ARTIFACT,
        "stress": STRESS_ARTIFACT,
        "schema": SCHEMA_ARTIFACT,
        "cost": COST_ARTIFACT,
        "readiness": READINESS_ARTIFACT,
        "report": REPORT_NAME,
    }
    for key, name in expected.items():
        assert written[key].name == name
        assert written[key].is_file()

    report_text = written["report"].read_text(encoding="utf-8")
    assert report_text.startswith(
        "# PHASE 3B.7.7A.43 — GLOBAL CONSOLIDATION REUSE OUTPUT-BUDGET REDESIGN"
    )
    assert "REAL PROVIDER CALLS =" in report_text
    assert "A.42 STATUS =" in report_text
    assert "PASS unchanged" in report_text
    assert "req_011CfXza6D59WbhBZVCLPEej" in report_text
    assert "global-consolidation-transport-2.0" in report_text
    assert "global-consolidation-2.0.1" in report_text
    assert "global-consolidation-3.0" in report_text
    assert "global-consolidation-transport-3.0" in report_text
    assert "HARD_SINGLE_MEMBER_REUSE_SYNTHESIZE_MERGES_ONLY" in report_text
    assert "READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY =" in report_text
    assert "SOURCE MAP =" in report_text
    assert "NOT PUBLISHED" in report_text
    assert "PHASE 3B =" in report_text
    assert "INCOMPLETE" in report_text
    assert bundle["header"]["result"] in {"PASS", "PARTIAL"}
    assert READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY == "NO"
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert PHASE == "3B.7.7A.43"
    assert not source_map_path(PROJECT_NAME).is_file()

    after = {
        "a34": _hash_if_exists(real / A34_REPORT),
        "a35": _hash_if_exists(real / A35_REPORT),
        "a36": _hash_if_exists(real / A36_REPORT),
        "a37": _hash_if_exists(real / A37_REPORT),
        "a38": _hash_if_exists(real / A38_REPORT),
        "a39": _hash_if_exists(real / A39_REPORT),
        "a40": _hash_if_exists(real / A40_REPORT),
        "a41": _hash_if_exists(real / A41_REPORT),
        "a42": _hash_if_exists(real / A42_REPORT),
    }
    assert after == before
    assert protected_a43_historical_hashes() == before_protected


def test_analyzer_not_wired_to_a43():
    analyzer = Path("app/source_analysis/analyzer.py")
    main = Path("main.py")
    marker = "source_analysis_v31_global_reuse_output"
    assert marker not in analyzer.read_text(encoding="utf-8")
    if main.is_file():
        assert marker not in main.read_text(encoding="utf-8")
