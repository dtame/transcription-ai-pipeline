"""Phase 4A.1 — replay hors ligne depuis la réponse persistée. 0 réseau."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.editorial_planner_canary_4a1.constants import (
    AUDIT_CONTRACT,
    AUDIT_RAW_RESPONSE,
    AUDIT_READINESS,
    PHASE_4A_ADAPTED_SCHEMA_SHA256,
    PROJECT_NAME,
)
from app.editorial_planner_canary_4a1.fixture import build_synthetic_source_map
from app.editorial_planner_canary_4a1.paths import (
    canary_audit_dir,
    production_editorial_plan_path,
    report_path,
    repo_root,
)
from app.editorial_planner_canary_4a1.validate import interpret_canary_response
from app.editorial_planning.constants import PUBLICATION_AUTHORIZED
from app.file_utils import content_hash


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _audit_dir() -> Path:
    return canary_audit_dir(root=repo_root())


def _require_real_artifacts() -> Path:
    directory = _audit_dir()
    raw_path = directory / AUDIT_RAW_RESPONSE
    if not raw_path.is_file():
        pytest.skip("Phase 4A.1 raw response not persisted yet")
    return directory


class TestPersistedCanaryArtifacts:
    def test_required_audits_exist(self):
        directory = _require_real_artifacts()
        for name in (
            "editorial_planner_4a1_precall_identity.json",
            "editorial_planner_4a1_synthetic_fixture.json",
            "editorial_planner_4a1_request_payload.json",
            AUDIT_RAW_RESPONSE,
            "editorial_planner_4a1_response_identity.json",
            "editorial_planner_4a1_opus_thinking_observation.json",
            AUDIT_CONTRACT,
            "editorial_planner_4a1_semantic_review.json",
            "editorial_planner_4a1_production_budget_status.json",
            AUDIT_READINESS,
            "canary_real_call.lock",
        ):
            assert (directory / name).is_file(), name
        assert report_path(root=repo_root()).is_file()

    def test_production_plan_not_published(self):
        assert PUBLICATION_AUTHORIZED is False
        assert not production_editorial_plan_path().is_file()

    def test_offline_replay_is_deterministic(self):
        directory = _require_real_artifacts()
        raw = json.loads((directory / AUDIT_RAW_RESPONSE).read_text(encoding="utf-8"))
        parsed = raw.get("parsed")
        assert isinstance(parsed, dict)
        source_map = build_synthetic_source_map()
        encoded = json.dumps(source_map.to_dict(), ensure_ascii=False, sort_keys=True)
        digest = content_hash(encoded)
        first = interpret_canary_response(
            parsed,
            source_map=source_map,
            source_map_sha256=digest,
            source_map_bytes=len(encoded.encode("utf-8")),
            raw_text=raw.get("text"),
        )
        second = interpret_canary_response(
            parsed,
            source_map=source_map,
            source_map_sha256=digest,
            source_map_bytes=len(encoded.encode("utf-8")),
            raw_text=raw.get("text"),
        )
        assert first["structured_parse"] == "PASS"
        assert first["transport_decoder"] == "PASS"
        assert first["canonical_reconstruction"] == "PASS"
        assert first["deterministic_replay"] == "PASS"
        assert first["plan_sha256"] == second["plan_sha256"]
        persisted = json.loads((directory / AUDIT_CONTRACT).read_text(encoding="utf-8"))
        assert first["plan_sha256"] == persisted["plan_sha256"]
        assert first["idea_coverage"]["coverage_complete"] is True
        assert first["idea_coverage"]["silent_omissions"] == 0

    def test_readiness_blocks_real_production_call(self):
        directory = _require_real_artifacts()
        readiness = json.loads((directory / AUDIT_READINESS).read_text(encoding="utf-8"))
        assert readiness["READY_FOR_REAL_EDITORIAL_PLANNER_CALL"] is False
        thinking = json.loads(
            (directory / "editorial_planner_4a1_opus_thinking_observation.json").read_text(
                encoding="utf-8"
            )
        )
        assert thinking["request_configuration"]["sonnet5_thinking_disabled_copied"] is False
        precall = json.loads(
            (directory / "editorial_planner_4a1_precall_identity.json").read_text(
                encoding="utf-8"
            )
        )
        assert (
            precall["schema"]["live"]["adapted_schema_sha256"]
            == PHASE_4A_ADAPTED_SCHEMA_SHA256
        )
        request = json.loads(
            (directory / "editorial_planner_4a1_request_payload.json").read_text(
                encoding="utf-8"
            )
        )
        blob = json.dumps(request).lower()
        assert "pastoral_retreat" not in blob
        assert PROJECT_NAME in json.dumps(request)
        assert "sk-ant-" not in blob
        assert "x-api-key" not in blob
