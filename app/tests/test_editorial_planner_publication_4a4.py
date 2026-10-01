"""Phase 4A.4 — offline publication. 0 provider. Isolated fixture paths only."""

from __future__ import annotations

import json

import pytest

from app.editorial_planning.constants import PUBLICATION_AUTHORIZED
from app.editorial_planning.fixtures import (
    covering_transport,
    empty_section_transport,
    missing_idea_transport,
    tiny_source_map,
    unknown_idea_transport,
)
from app.editorial_planning.pipeline import materialize_plan
from app.editorial_planning.prompt import prompt_bundle
from app.editorial_planning.schema import schema_identity
from app.editorial_planning.writer import editorial_plan_path, render_editorial_plan
from app.editorial_planner_publication_4a4.constants import (
    BYTE_IDENTITY_EXACT,
    EDITORIAL_PLAN_PUBLICATION_AUTHORIZED,
    EXPECTED_CANDIDATE_SHA256,
    EXPECTED_SOURCE_MAP_SHA256,
    PHASE,
    PUBLICATION_MODE_CONFLICT,
    PUBLICATION_MODE_IDENTICAL,
    PUBLICATION_MODE_NEW,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    RELATION_QUALITY_TECHNICAL_DEBT,
)
from app.editorial_planner_publication_4a4.offline import (
    assert_analyzer_untouched,
    assert_no_book_generator,
    assert_offline_package,
    package_imports_network_clients,
    package_invokes_provider,
)
from app.editorial_planner_publication_4a4.publish import (
    atomic_replace,
    publish_exact_bytes,
    write_raw_bytes_atomic,
)
from app.editorial_planner_publication_4a4.runner import build_bundle
from app.source_analysis.writer import partial_path, source_map_path, write_source_map


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _ids():
    prompt = prompt_bundle()
    schema = schema_identity()
    return prompt["prompt_sha256"], schema["raw_schema_sha256"]


def _materialize(source_map, transport):
    prompt_sha, schema_sha = _ids()
    return materialize_plan(
        transport,
        source_map,
        source_map_sha256="fixture-source",
        source_map_bytes=32,
        prompt_sha256=prompt_sha,
        response_schema_sha256=schema_sha,
        source_map_path_value="analysis/source_map.json",
    )


def _write_fixture(tmp_path, *, project="demo_4a4", transport_factory=covering_transport):
    source_map = tiny_source_map(project_name=project, primary_language="en")
    transport = transport_factory(source_map)
    plan, validation, _sha = _materialize(source_map, transport)
    raw = render_editorial_plan(plan.to_dict()).encode("utf-8")
    candidate = tmp_path / "editorial_plan_candidate.json"
    candidate.write_bytes(raw)
    sm_path = source_map_path(project, sortie_dir=tmp_path)
    sm_path.parent.mkdir(parents=True, exist_ok=True)
    write_source_map(sm_path, source_map.to_dict())
    return {
        "project": project,
        "candidate": candidate,
        "candidate_bytes": raw,
        "source_map": source_map,
        "source_map_path": sm_path,
        "plan": plan,
        "validation": validation,
    }


def _publish(tmp_path, fixture, **overrides):
    kwargs = {
        "project_name": fixture["project"],
        "sortie_dir": tmp_path,
        "candidate_path": fixture["candidate"],
        "source_map_file": fixture["source_map_path"],
        "pastoral_contract": False,
        "expected_canonical_language": "en",
        "tests": "unit 4A.4",
    }
    kwargs.update(overrides)
    return build_bundle(**kwargs)


class TestFrozenContracts:
    def test_offline_and_historical_publication_flag(self):
        assert_offline_package()
        assert_analyzer_untouched()
        assert_no_book_generator()
        assert PUBLICATION_AUTHORIZED is False
        assert EDITORIAL_PLAN_PUBLICATION_AUTHORIZED is True
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert PHASE == "4A.4"
        assert RELATION_QUALITY_TECHNICAL_DEBT == "YES"
        assert EXPECTED_CANDIDATE_SHA256.startswith("01cfb86a")
        assert EXPECTED_SOURCE_MAP_SHA256.startswith("df32f594")


class TestPublicationMechanics:
    def test_valid_candidate_publishes_exact_bytes(self, tmp_path):
        fixture = _write_fixture(tmp_path)
        bundle = _publish(tmp_path, fixture)
        target = editorial_plan_path(fixture["project"], sortie_dir=tmp_path)
        assert target.is_file()
        assert target.read_bytes() == fixture["candidate_bytes"]
        assert bundle["header"]["publication_mode"] == PUBLICATION_MODE_NEW
        assert bundle["header"]["byte_identity"] == BYTE_IDENTITY_EXACT
        assert bundle["header"]["reload"] == "PASS"
        assert bundle["header"]["validator"] == "PASS"
        assert not partial_path(target).exists()

    def test_idempotent_second_publish_does_not_rewrite(self, tmp_path):
        fixture = _write_fixture(tmp_path, project="demo_4a4_idem")
        first = _publish(tmp_path, fixture)
        target = editorial_plan_path(fixture["project"], sortie_dir=tmp_path)
        mtime = target.stat().st_mtime_ns
        second = _publish(tmp_path, fixture)
        assert target.read_bytes() == fixture["candidate_bytes"]
        assert first["header"]["publication_mode"] == PUBLICATION_MODE_NEW
        assert second["header"]["publication_mode"] == PUBLICATION_MODE_IDENTICAL
        assert second["publication"]["atomic_publication"] == "SKIPPED_IDENTICAL"
        assert target.stat().st_mtime_ns == mtime

    def test_conflict_blocks_overwrite(self, tmp_path):
        fixture = _write_fixture(tmp_path, project="demo_4a4_conflict")
        target = editorial_plan_path(fixture["project"], sortie_dir=tmp_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        original = b'{"schema_version": "other"}\n'
        target.write_bytes(original)
        bundle = _publish(tmp_path, fixture)
        assert bundle["header"]["publication_mode"] == PUBLICATION_MODE_CONFLICT
        assert bundle["header"]["result"] == "BLOCKED_CONFLICT"
        assert target.read_bytes() == original
        assert bundle["header"]["editorial_plan_json"] == "NOT PUBLISHED"

    def test_wrong_candidate_hash_blocks(self, tmp_path):
        fixture = _write_fixture(tmp_path, project="demo_4a4_hash")
        bundle = _publish(
            tmp_path,
            fixture,
            expected_candidate_sha256="0" * 64,
        )
        target = editorial_plan_path(fixture["project"], sortie_dir=tmp_path)
        assert not target.is_file()
        assert bundle["header"]["result"] == "BLOCKED"
        assert bundle["gate"]["authorized"] is False
        assert bundle["header"]["candidate_identity"] == "MISMATCH"

    def test_wrong_source_map_hash_blocks(self, tmp_path):
        fixture = _write_fixture(tmp_path, project="demo_4a4_sm")
        bundle = _publish(
            tmp_path,
            fixture,
            expected_source_map_sha256="0" * 64,
        )
        target = editorial_plan_path(fixture["project"], sortie_dir=tmp_path)
        assert not target.is_file()
        assert bundle["header"]["result"] == "BLOCKED"
        assert bundle["gate"]["blocked_reason"] == "SOURCE_MAP_IDENTITY"

    def test_invalid_candidate_does_not_publish(self, tmp_path):
        project = "demo_4a4_invalid"
        source_map = tiny_source_map(project_name=project, primary_language="en")
        sm_path = source_map_path(project, sortie_dir=tmp_path)
        sm_path.parent.mkdir(parents=True, exist_ok=True)
        write_source_map(sm_path, source_map.to_dict())
        candidate = tmp_path / "bad_candidate.json"
        candidate.write_bytes(b'{"chapters": [{"title": "One"}]}\n')
        bundle = build_bundle(
            project,
            sortie_dir=tmp_path,
            candidate_path=candidate,
            source_map_file=sm_path,
            pastoral_contract=False,
            expected_canonical_language="en",
        )
        target = editorial_plan_path(project, sortie_dir=tmp_path)
        assert not target.is_file()
        assert bundle["header"]["result"] == "BLOCKED"

    def test_language_mismatch_does_not_publish(self, tmp_path):
        fixture = _write_fixture(tmp_path, project="demo_4a4_lang")
        bundle = _publish(
            tmp_path,
            fixture,
            expected_canonical_language="fr",
        )
        target = editorial_plan_path(fixture["project"], sortie_dir=tmp_path)
        assert not target.is_file()
        assert bundle["header"]["result"] == "BLOCKED"
        assert bundle["gate"]["blocked_reason"] == "LANGUAGE"

    def test_missing_idea_does_not_publish(self, tmp_path):
        fixture = _write_fixture(
            tmp_path,
            project="demo_4a4_missing",
            transport_factory=missing_idea_transport,
        )
        bundle = _publish(tmp_path, fixture)
        target = editorial_plan_path(fixture["project"], sortie_dir=tmp_path)
        assert not target.is_file()
        assert bundle["header"]["result"] == "BLOCKED"
        assert bundle["gate"]["blocked_reason"] in {"VALIDATOR", "COVERAGE"}

    def test_duplicate_disposition_does_not_publish(self, tmp_path):
        fixture = _write_fixture(tmp_path, project="demo_4a4_dup")
        payload = json.loads(fixture["candidate_bytes"].decode("utf-8"))
        row = dict(payload["idea_coverage"][0])
        payload["idea_coverage"].append(row)
        raw = render_editorial_plan(payload).encode("utf-8")
        fixture["candidate"].write_bytes(raw)
        fixture["candidate_bytes"] = raw
        bundle = _publish(tmp_path, fixture)
        target = editorial_plan_path(fixture["project"], sortie_dir=tmp_path)
        assert not target.is_file()
        assert bundle["header"]["result"] == "BLOCKED"
        assert bundle["gate"]["blocked_reason"] in {"VALIDATOR", "COVERAGE"}

    def test_unknown_reference_does_not_publish(self, tmp_path):
        fixture = _write_fixture(
            tmp_path,
            project="demo_4a4_unknown",
            transport_factory=unknown_idea_transport,
        )
        bundle = _publish(tmp_path, fixture)
        target = editorial_plan_path(fixture["project"], sortie_dir=tmp_path)
        assert not target.is_file()
        assert bundle["header"]["result"] == "BLOCKED"
        assert bundle["gate"]["blocked_reason"] in {"VALIDATOR", "UNKNOWN_REF"}

    def test_validator_failure_does_not_publish(self, tmp_path):
        fixture = _write_fixture(
            tmp_path,
            project="demo_4a4_empty",
            transport_factory=empty_section_transport,
        )
        bundle = _publish(tmp_path, fixture)
        target = editorial_plan_path(fixture["project"], sortie_dir=tmp_path)
        assert not target.is_file()
        assert bundle["header"]["result"] == "BLOCKED"
        assert bundle["gate"]["blocked_reason"] == "VALIDATOR"

    def test_atomicity_failure_leaves_no_production_file(self, tmp_path, monkeypatch):
        target = tmp_path / "analysis" / "editorial_plan.json"
        payload = b'{"schema_version": "1.0"}\n'

        def _boom(partial, dest):
            raise OSError("replace failed")

        monkeypatch.setattr(
            "app.editorial_planner_publication_4a4.publish.atomic_replace",
            _boom,
        )
        with pytest.raises(OSError):
            write_raw_bytes_atomic(target, payload)
        assert not target.exists()
        assert not partial_path(target).exists()

    def test_network_package_is_offline(self):
        assert_offline_package()
        assert package_imports_network_clients() == []
        assert package_invokes_provider() == []


class TestDirectPublishHelper:
    def test_inspect_conflict_without_runner(self, tmp_path):
        target = tmp_path / "editorial_plan.json"
        candidate = b'{"a": 1}\n'
        target.write_bytes(b'{"a": 2}\n')
        result = publish_exact_bytes(target, candidate, authorized=True)
        assert result["mode"] == PUBLICATION_MODE_CONFLICT
        assert target.read_bytes() == b'{"a": 2}\n'
        assert atomic_replace is not None
