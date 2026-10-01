"""Écrit les artefacts A.38. N'écrase pas A.34–A.37. 0 provider."""

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
from app.source_analysis_v31_global_preflight.constants import REPORT_NAME as A34_REPORT
from app.source_analysis_v31_global_v11_grammar_canary.constants import (
    REPORT_NAME as A37_REPORT,
)
from app.source_analysis_v31_global_real_consolidation.constants import (
    AUTHORIZATION_SCOPE,
    CANONICAL_ARTIFACT,
    CANDIDATE_SOURCE_MAP_NAME,
    COVERAGE_ARTIFACT,
    DISPOSITION_ARTIFACT,
    DROP_ARTIFACT,
    MERGE_ARTIFACT,
    OTHER_ARTIFACT,
    PREFLIGHT_ARTIFACT,
    RAW_INVENTORY_ARTIFACT,
    READINESS_ARTIFACT,
    RELATION_ARTIFACT,
    REPORT_NAME,
    REQUEST_ARTIFACT,
    SEMANTIC_ARTIFACT,
    USAGE_ARTIFACT,
)
from app.source_analysis_v31_global_real_consolidation.fake_transport import (
    mechanical_keep_transport,
)
from app.source_analysis_v31_global_real_consolidation.input_contract import (
    load_normalized_bundle,
)
from app.source_analysis_v31_global_real_consolidation.paths import canary_root
from app.source_analysis_v31_global_real_consolidation.runner import (
    run_real_global_consolidation,
)
from app.source_analysis_v31_global_real_consolidation.writer import (
    write_consolidation_artifacts,
)
from app.tests.test_source_analysis_v31_global_real_consolidation import _fake_engine


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _hash_if_exists(path: Path) -> str | None:
    return sha256_of_file(path) if path.is_file() else None


def test_write_audit_artifacts_without_touching_history(tmp_path):
    a34 = audit_dir("pastoral_retreat_v2_validation") / A34_REPORT
    a35 = audit_dir("pastoral_retreat_v2_validation") / A35_REPORT
    a36 = audit_dir("pastoral_retreat_v2_validation") / A36_REPORT
    a37 = audit_dir("pastoral_retreat_v2_validation") / A37_REPORT
    before = {
        "a34": _hash_if_exists(a34),
        "a35": _hash_if_exists(a35),
        "a36": _hash_if_exists(a36),
        "a37": _hash_if_exists(a37),
        "source_map": source_map_path("pastoral_retreat_v2_validation").is_file(),
    }

    result = run_real_global_consolidation(
        "pastoral_retreat_v2_validation",
        dry_run=True,
        authorization_scope=AUTHORIZATION_SCOPE,
    )
    written = write_consolidation_artifacts(
        "fixture", result, sortie_dir=tmp_path, tests="offline A.38 unit"
    )

    expected = {
        "preflight": PREFLIGHT_ARTIFACT,
        "request": REQUEST_ARTIFACT,
        "raw_inventory": RAW_INVENTORY_ARTIFACT,
        "dispositions": DISPOSITION_ARTIFACT,
        "drops": DROP_ARTIFACT,
        "others": OTHER_ARTIFACT,
        "merges": MERGE_ARTIFACT,
        "relations": RELATION_ARTIFACT,
        "semantic": SEMANTIC_ARTIFACT,
        "coverage": COVERAGE_ARTIFACT,
        "canonical": CANONICAL_ARTIFACT,
        "usage": USAGE_ARTIFACT,
        "readiness": READINESS_ARTIFACT,
        "report": REPORT_NAME,
    }
    for key, name in expected.items():
        assert written[key].name == name
        assert written[key].is_file()
    assert CANDIDATE_SOURCE_MAP_NAME not in {path.name for path in written.values()}
    assert not (tmp_path / "fixture" / "analysis" / "source_map.json").is_file()
    assert canary_root("fixture", sortie_dir=tmp_path).is_dir()

    after = {
        "a34": _hash_if_exists(a34),
        "a35": _hash_if_exists(a35),
        "a36": _hash_if_exists(a36),
        "a37": _hash_if_exists(a37),
        "source_map": source_map_path("pastoral_retreat_v2_validation").is_file(),
    }
    assert after == before


def test_candidate_isolated_when_created():
    bundle = load_normalized_bundle("pastoral_retreat_v2_validation")
    transport = mechanical_keep_transport(bundle["normalized"])
    result = run_real_global_consolidation(
        "pastoral_retreat_v2_validation",
        dry_run=False,
        execute_real=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        engine=_fake_engine(transport),
    )
    assert (result.execution or {}).get("source_map_published") is False
    assert not source_map_path("pastoral_retreat_v2_validation").is_file()
