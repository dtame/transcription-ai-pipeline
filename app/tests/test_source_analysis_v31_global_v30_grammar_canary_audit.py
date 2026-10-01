"""Écrit les artefacts A.44. N'écrase pas A.34–A.43. 0 provider."""

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
    AUTHORIZATION_SCOPE,
    CANONICAL_ARTIFACT,
    DERIVED_SRC_ARTIFACT,
    ESTIMATOR_ARTIFACT,
    FIXTURE_ARTIFACT,
    MEMBERSHIP_ARTIFACT,
    PHASE,
    READINESS_ARTIFACT,
    REPORT_NAME,
    REQUEST_ARTIFACT,
    REUSE_SYNTHESIS_ARTIFACT,
    USAGE_ARTIFACT,
    VALIDATOR_ARTIFACT,
)
from app.source_analysis_v31_global_v30_grammar_canary.runner import (
    run_global_v30_grammar_canary,
)
from app.source_analysis_v31_global_v30_grammar_canary.writer import write_canary_artifacts


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
        "a40": _hash_if_exists(real / A40_REPORT),
        "a41": _hash_if_exists(real / A41_REPORT),
        "a42": _hash_if_exists(real / A42_REPORT),
        "a43": _hash_if_exists(real / A43_REPORT),
    }

    result = run_global_v30_grammar_canary(
        "fixture",
        dry_run=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        sortie_dir=tmp_path,
    )
    written = write_canary_artifacts(
        "fixture", result, sortie_dir=tmp_path, tests="offline A.44 unit"
    )

    expected = {
        "fixture": FIXTURE_ARTIFACT,
        "request": REQUEST_ARTIFACT,
        "reuse_synthesis": REUSE_SYNTHESIS_ARTIFACT,
        "membership": MEMBERSHIP_ARTIFACT,
        "derived_src": DERIVED_SRC_ARTIFACT,
        "validator": VALIDATOR_ARTIFACT,
        "canonical": CANONICAL_ARTIFACT,
        "estimator": ESTIMATOR_ARTIFACT,
        "usage": USAGE_ARTIFACT,
        "readiness": READINESS_ARTIFACT,
    }
    for key, name in expected.items():
        assert written[key].is_file()
        assert written[key].name == name
    assert written["report"].name == REPORT_NAME
    report = written["report"].read_text(encoding="utf-8")
    assert (
        "# PHASE 3B.7.7A.44 — GLOBAL CONSOLIDATION V3.0 REUSE GRAMMAR CANARY"
        in report
    )
    assert "PROMPT =" in report
    assert "global-consolidation-3.0" in report
    assert "READY_FOR_REAL_GLOBAL_CONSOLIDATION_PREFLIGHT =" in report
    assert "READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY =" in report
    assert "SAFE_FOR_GRAMMAR_CANARY_BUDGET" in report
    assert "12302" in report
    assert not source_map_path("fixture", sortie_dir=tmp_path).is_file()

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
    }
    assert after == before
    assert PHASE == "3B.7.7A.44"
