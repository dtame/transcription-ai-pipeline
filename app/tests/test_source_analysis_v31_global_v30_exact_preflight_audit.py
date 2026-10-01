"""Écrit les artefacts A.45. N'écrase pas A.34–A.44. 0 provider."""

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
    REPORT_NAME as A43_REPORT,
)
from app.source_analysis_v31_global_v11_grammar_canary.constants import (
    REPORT_NAME as A37_REPORT,
)
from app.source_analysis_v31_global_v20_grammar_canary.constants import (
    REPORT_NAME as A40_REPORT,
)
from app.source_analysis_v31_global_v201_contract_canary.constants import (
    REPORT_NAME as A42_REPORT,
)
from app.source_analysis_v31_global_v30_grammar_canary.constants import (
    REPORT_NAME as A44_REPORT,
)
from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    CONTRACT_ARTIFACT,
    COST_ARTIFACT,
    FAKEAI_ARTIFACT,
    FUTURE_GUARD_ARTIFACT,
    INPUT_BUDGET_ARTIFACT,
    INVENTORY_ARTIFACT,
    NORMALIZED_INPUT_ARTIFACT,
    OUTPUT_BUDGET_ARTIFACT,
    OUTPUT_COMPONENTS_ARTIFACT,
    PHASE,
    PROJECT_NAME,
    PUBLICATION_ARTIFACT,
    READINESS_ARTIFACT,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REPORT_NAME,
    REQUEST_ARTIFACT,
    REQUEST_IDENTITY_ARTIFACT,
    SEMANTIC_PLAN_ARTIFACT,
    WINDOW_MANIFEST_ARTIFACT,
)
from app.source_analysis_v31_global_v30_exact_preflight.evidence import (
    protected_a45_historical_hashes,
)
from app.source_analysis_v31_global_v30_exact_preflight.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_v30_exact_preflight.payload import secrets_present
from app.source_analysis_v31_global_v30_exact_preflight.runner import build_bundle
from app.source_analysis_v31_global_v30_exact_preflight.writer import write_audit_bundle


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
        "a43": _hash_if_exists(real / A43_REPORT),
        "a44": _hash_if_exists(real / A44_REPORT),
    }
    before_protected = protected_a45_historical_hashes()

    bundle = build_bundle(tests="offline A.45 unit")
    written = write_audit_bundle(PROJECT_NAME, bundle, tests="offline A.45 unit")

    expected = {
        "inventory": INVENTORY_ARTIFACT,
        "window_manifest": WINDOW_MANIFEST_ARTIFACT,
        "normalized_input": NORMALIZED_INPUT_ARTIFACT,
        "request": REQUEST_ARTIFACT,
        "request_identity": REQUEST_IDENTITY_ARTIFACT,
        "input_budget": INPUT_BUDGET_ARTIFACT,
        "output_budget": OUTPUT_BUDGET_ARTIFACT,
        "output_components": OUTPUT_COMPONENTS_ARTIFACT,
        "cost": COST_ARTIFACT,
        "contract": CONTRACT_ARTIFACT,
        "publication": PUBLICATION_ARTIFACT,
        "future_guard": FUTURE_GUARD_ARTIFACT,
        "fakeai": FAKEAI_ARTIFACT,
        "semantic_plan": SEMANTIC_PLAN_ARTIFACT,
        "readiness": READINESS_ARTIFACT,
        "report": REPORT_NAME,
    }
    for key, name in expected.items():
        assert written[key].name == name
        assert written[key].is_file()

    request = written["request"].read_text(encoding="utf-8")
    assert secrets_present(request) == []
    assert "sk-ant-" not in request
    assert "x-api-key" not in request.lower()

    report_text = written["report"].read_text(encoding="utf-8")
    assert report_text.startswith(
        "# PHASE 3B.7.7A.45 — GLOBAL CONSOLIDATION V3.0 EXACT PRODUCTION PREFLIGHT"
    )
    assert "REAL PROVIDER CALLS =" in report_text
    assert "A.44 STATUS =" in report_text
    assert "PASS unchanged" in report_text
    assert "req_011CfY6EGQtoB2iSvDaHNCwx" in report_text
    assert "global-consolidation-3.0" in report_text
    assert "global-consolidation-transport-3.0" in report_text
    assert "1583 / 1831" in report_text
    assert "822397b642b0e1724e29686962caab32bff63effe18f05bff26b404bad9b2a90" in report_text
    assert "claude-sonnet-5" in report_text
    assert "READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY =" in report_text
    assert "SOURCE MAP =" in report_text
    assert "NOT PUBLISHED" in report_text
    assert "PHASE 3B =" in report_text
    assert "INCOMPLETE" in report_text
    assert bundle["header"]["result"] in {"PASS", "PARTIAL"}
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert PHASE == "3B.7.7A.45"
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
        "a43": _hash_if_exists(real / A43_REPORT),
        "a44": _hash_if_exists(real / A44_REPORT),
    }
    assert after == before
    assert protected_a45_historical_hashes() == before_protected


def test_analyzer_not_wired_to_a45():
    analyzer = Path("app/source_analysis/analyzer.py")
    main = Path("main.py")
    marker = "source_analysis_v31_global_v30_exact_preflight"
    assert marker not in analyzer.read_text(encoding="utf-8")
    if main.is_file():
        assert marker not in main.read_text(encoding="utf-8")
