"""Écrit les artefacts A.40. N'écrase pas A.34–A.39. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_canary_forensics.constants import (
    REPORT_NAME as A36_REPORT,
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
from app.source_analysis_v31_global_v11_grammar_canary.constants import (
    REPORT_NAME as A37_REPORT,
)
from app.source_analysis_v31_global_v20_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    CANONICAL_ARTIFACT,
    DERIVED_DISPOSITION_ARTIFACT,
    DERIVED_SRC_ARTIFACT,
    ESTIMATOR_ARTIFACT,
    FIXTURE_ARTIFACT,
    MEMBERSHIP_ARTIFACT,
    PHASE,
    READINESS_ARTIFACT,
    REPORT_NAME,
    REQUEST_ARTIFACT,
    USAGE_ARTIFACT,
    VALIDATOR_ARTIFACT,
)
from app.source_analysis_v31_global_v20_grammar_canary.runner import (
    run_global_v20_grammar_canary,
)
from app.source_analysis_v31_global_v20_grammar_canary.writer import write_canary_artifacts


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _hash_if_exists(path: Path) -> str | None:
    return sha256_of_file(path) if path.is_file() else None


def test_write_audit_artifacts_without_touching_history(tmp_path):
    real = audit_dir("pastoral_retreat_v2_validation")
    before = {
        "a34": _hash_if_exists(real / A34_REPORT),
        "a35": _hash_if_exists(real / A35_REPORT),
        "a36": _hash_if_exists(real / A36_REPORT),
        "a37": _hash_if_exists(real / A37_REPORT),
        "a38": _hash_if_exists(real / A38_REPORT),
        "a39": _hash_if_exists(real / A39_REPORT),
    }

    result = run_global_v20_grammar_canary(
        "fixture",
        dry_run=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        sortie_dir=tmp_path,
    )
    written = write_canary_artifacts(
        "fixture", result, sortie_dir=tmp_path, tests="offline A.40 unit"
    )

    expected = {
        "fixture": FIXTURE_ARTIFACT,
        "request": REQUEST_ARTIFACT,
        "membership": MEMBERSHIP_ARTIFACT,
        "derived_dispositions": DERIVED_DISPOSITION_ARTIFACT,
        "derived_src": DERIVED_SRC_ARTIFACT,
        "validator": VALIDATOR_ARTIFACT,
        "canonical": CANONICAL_ARTIFACT,
        "estimator": ESTIMATOR_ARTIFACT,
        "usage": USAGE_ARTIFACT,
        "readiness": READINESS_ARTIFACT,
        "report": REPORT_NAME,
    }
    for key, name in expected.items():
        assert written[key].name == name
        assert written[key].is_file()

    report_text = written["report"].read_text(encoding="utf-8")
    assert report_text.startswith(
        "# PHASE 3B.7.7A.40 — COMPACT GLOBAL CONSOLIDATION V2.0 GRAMMAR CANARY"
    )
    assert "AUTHORIZED PROVIDER CALLS =" in report_text
    assert "PASTORAL DATA SENT =" in report_text
    assert "REAL CONSOLIDATION EXECUTED =" in report_text
    assert "claude-sonnet-5" in report_text
    assert "global-consolidation-2.0" in report_text
    assert "global-consolidation-transport-2.0" in report_text
    assert "1588 / 1836" in report_text
    assert "READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY =" in report_text
    assert PHASE == "3B.7.7A.40"
    assert not source_map_path("fixture", sortie_dir=tmp_path).is_file()
    fixture_path = written["fixture"]
    assert fixture_path.parts[-3:] == (
        "canary",
        "global_consolidation_transport_v20",
        FIXTURE_ARTIFACT,
    )

    after = {
        "a34": _hash_if_exists(real / A34_REPORT),
        "a35": _hash_if_exists(real / A35_REPORT),
        "a36": _hash_if_exists(real / A36_REPORT),
        "a37": _hash_if_exists(real / A37_REPORT),
        "a38": _hash_if_exists(real / A38_REPORT),
        "a39": _hash_if_exists(real / A39_REPORT),
    }
    assert after == before


def test_analyzer_not_wired_to_a40():
    analyzer = Path("app/source_analysis/analyzer.py")
    main = Path("main.py")
    marker = "source_analysis_v31_global_v20_grammar_canary"
    assert marker not in analyzer.read_text(encoding="utf-8")
    if main.is_file():
        assert marker not in main.read_text(encoding="utf-8")
