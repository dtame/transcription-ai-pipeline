"""Phase 4A.2 — artefacts d'audit persistés. 0 réseau."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.editorial_planner_preflight_4a2.constants import (
    ADAPTED_SCHEMA_SHA256,
    AUDIT_CACHE,
    AUDIT_COST,
    AUDIT_COVERAGE,
    AUDIT_GATES,
    AUDIT_INPUT_BUDGET,
    AUDIT_OUTPUT_BUDGET,
    AUDIT_READINESS,
    AUDIT_REQUEST_IDENTITY,
    AUDIT_SOURCE_IDENTITY,
    AUDIT_THINKING,
    EXPECTED_SOURCE_MAP_SHA256,
    REPORT_NAME,
)
from app.editorial_planner_preflight_4a2.paths import (
    preflight_audit_dir,
    production_editorial_plan_path,
    report_path,
    repo_root,
)
from app.editorial_planning.constants import PUBLICATION_AUTHORIZED


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _require_artifacts() -> Path:
    directory = preflight_audit_dir(root=repo_root())
    if not (directory / AUDIT_REQUEST_IDENTITY).is_file():
        pytest.skip("Phase 4A.2 artifacts not persisted yet")
    return directory


class TestPersistedPreflightArtifacts:
    def test_required_audits_exist(self):
        directory = _require_artifacts()
        for name in (
            AUDIT_SOURCE_IDENTITY,
            AUDIT_REQUEST_IDENTITY,
            AUDIT_INPUT_BUDGET,
            AUDIT_OUTPUT_BUDGET,
            AUDIT_THINKING,
            AUDIT_COST,
            AUDIT_CACHE,
            AUDIT_COVERAGE,
            AUDIT_GATES,
            AUDIT_READINESS,
            "index.json",
        ):
            assert (directory / name).is_file(), name
        assert report_path(root=repo_root()).is_file()
        assert report_path(root=repo_root()).name == REPORT_NAME

    def test_production_plan_not_published(self):
        assert PUBLICATION_AUTHORIZED is False
        assert not production_editorial_plan_path().is_file()

    def test_identities_and_zero_provider(self):
        directory = _require_artifacts()
        source = json.loads(
            (directory / AUDIT_SOURCE_IDENTITY).read_text(encoding="utf-8")
        )
        request = json.loads(
            (directory / AUDIT_REQUEST_IDENTITY).read_text(encoding="utf-8")
        )
        coverage = json.loads((directory / AUDIT_COVERAGE).read_text(encoding="utf-8"))
        readiness = json.loads(
            (directory / AUDIT_READINESS).read_text(encoding="utf-8")
        )
        thinking = json.loads((directory / AUDIT_THINKING).read_text(encoding="utf-8"))
        assert source["sha256"] == EXPECTED_SOURCE_MAP_SHA256
        assert source["source_map_not_modified"] is True
        assert request["request_determinism"] is True
        assert request["secrets_included"] is False
        assert request["engine_generate_called"] is False
        assert "x-api-key" not in json.dumps(request)
        assert coverage["idea_count"] == 286
        assert coverage["unknown_input_refs"] == 0
        assert thinking["thinking_mode"] == "provider_default"
        assert thinking["do_not_switch_to_thinking_disabled"] is True
        assert readiness["READY_FOR_EDITORIAL_PLAN_PUBLICATION"] is False
        schema_live = json.loads(
            (directory / AUDIT_SOURCE_IDENTITY).read_text(encoding="utf-8")
        )
        _ = schema_live
        output = json.loads((directory / AUDIT_OUTPUT_BUDGET).read_text(encoding="utf-8"))
        assert output["selection"]["do_not_blindly_select_32768"] is True
        _ = ADAPTED_SCHEMA_SHA256
