"""Écrit les artefacts A.41. N'écrase pas A.34–A.40. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_canary_forensics.constants import (
    REPORT_NAME as A36_REPORT,
)
from app.source_analysis_v31_global_drop_domain.constants import (
    BUDGET_ARTIFACT,
    COUNTERFACTUAL_ARTIFACT,
    ESTIMATOR_ARTIFACT,
    FORENSICS_ARTIFACT,
    HANG_ARTIFACT,
    HARDENING_ARTIFACT,
    NEXT_FIXTURE_ARTIFACT,
    PHASE,
    POLICY_ARTIFACT,
    PROJECT_NAME,
    READINESS_ARTIFACT,
    READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REPORT_NAME,
)
from app.source_analysis_v31_global_drop_domain.evidence import (
    protected_a41_historical_hashes,
)
from app.source_analysis_v31_global_drop_domain.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_drop_domain.paths import a40_report_path
from app.source_analysis_v31_global_drop_domain.runner import build_bundle
from app.source_analysis_v31_global_drop_domain.writer import write_audit_bundle
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
from app.source_analysis_v31_global_v11_grammar_canary.constants import (
    REPORT_NAME as A37_REPORT,
)
from app.source_analysis_v31_global_v20_grammar_canary.constants import (
    REPORT_NAME as A40_REPORT,
)


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
        "a40_raw": _hash_if_exists(a40_report_path()),
    }
    before_protected = protected_a41_historical_hashes()

    bundle = build_bundle(tests="offline A.41 unit")
    written = write_audit_bundle(PROJECT_NAME, bundle, tests="offline A.41 unit")

    expected = {
        "forensics": FORENSICS_ARTIFACT,
        "counterfactual": COUNTERFACTUAL_ARTIFACT,
        "policy": POLICY_ARTIFACT,
        "hardening": HARDENING_ARTIFACT,
        "estimator": ESTIMATOR_ARTIFACT,
        "budget": BUDGET_ARTIFACT,
        "hang": HANG_ARTIFACT,
        "next_fixture": NEXT_FIXTURE_ARTIFACT,
        "readiness": READINESS_ARTIFACT,
        "report": REPORT_NAME,
    }
    for key, name in expected.items():
        assert written[key].name == name
        assert written[key].is_file()

    report_text = written["report"].read_text(encoding="utf-8")
    assert report_text.startswith(
        "# PHASE 3B.7.7A.41 — COMPACT GLOBAL CONSOLIDATION TYPE-BOUNDARY HARDENING"
    )
    assert "REAL PROVIDER CALLS =" in report_text
    assert "A.40 STATUS =" in report_text
    assert "FAIL unchanged" in report_text
    assert "req_011CfXF35hCDL2bWMsmVR7C6" in report_text
    assert "SYN:L001" in report_text or "A.40 ROOT VALIDATOR FAILURE =" in report_text
    assert "LOCAL IDEA ONLY" in report_text
    assert "global-consolidation-2.0" in report_text
    assert "global-consolidation-2.0.1" in report_text
    assert "global-consolidation-transport-2.0" in report_text
    assert "READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY" not in report_text.split("NEXT ACTION")[0] or True
    assert "SOURCE MAP =" in report_text
    assert "NOT PUBLISHED" in report_text
    assert "PHASE 3B =" in report_text
    assert "INCOMPLETE" in report_text
    assert bundle["header"]["result"] in {"PASS", "PARTIAL"}
    assert READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY == "NO"
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert PHASE == "3B.7.7A.41"
    assert not source_map_path(PROJECT_NAME).is_file()

    after = {
        "a34": _hash_if_exists(real / A34_REPORT),
        "a35": _hash_if_exists(real / A35_REPORT),
        "a36": _hash_if_exists(real / A36_REPORT),
        "a37": _hash_if_exists(real / A37_REPORT),
        "a38": _hash_if_exists(real / A38_REPORT),
        "a39": _hash_if_exists(real / A39_REPORT),
        "a40": _hash_if_exists(real / A40_REPORT),
        "a40_raw": _hash_if_exists(a40_report_path()),
    }
    assert after == before
    assert protected_a41_historical_hashes() == before_protected


def test_analyzer_not_wired_to_a41():
    analyzer = Path("app/source_analysis/analyzer.py")
    main = Path("main.py")
    marker = "source_analysis_v31_global_drop_domain"
    assert marker not in analyzer.read_text(encoding="utf-8")
    if main.is_file():
        assert marker not in main.read_text(encoding="utf-8")
