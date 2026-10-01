"""Phase 3B.7.7A.49 — FakeAI / offline publication. 0 réseau."""

from __future__ import annotations

import json

import pytest

from app.source_analysis.models import (
    SOURCE_MAP_SCHEMA_VERSION,
    AnalysisProvenance,
    AuthorVoiceProfile,
    Example,
    Idea,
    IntentStatement,
    Reference,
    Repetition,
    SourceAnalysisHeader,
    SourceMap,
    SourceMapStats,
    Topic,
    Uncertainty,
)
from app.source_analysis.writer import partial_path, source_map_path
from app.source_analysis_v31_global_a47_contract_forensics.evidence import (
    verify_a46_identity,
)
from app.source_analysis_v31_global_a49_source_map_publication.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_STATUS_PRESERVED,
    A39_STATUS_PRESERVED,
    A40_STATUS_PRESERVED,
    A41_STATUS_PRESERVED,
    A42_STATUS_PRESERVED,
    A43_STATUS_PRESERVED,
    A44_STATUS_PRESERVED,
    A45_REQUEST_HASH,
    A45_STATUS_PRESERVED,
    A46_COST_USD,
    A46_STATUS_PRESERVED,
    A47_STATUS_PRESERVED,
    A48_STATUS_PRESERVED,
    A49_COST_USD,
    BYTE_IDENTITY_EXACT,
    FUTURE_PROMPT,
    GLOBAL_INTENT_MAX_CHARS,
    HISTORICAL_PROMPT,
    HISTORICAL_REQUEST_HASH,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    PHASE,
    PROJECT_NAME,
    PUBLICATION_MODE_CONFLICT,
    PUBLICATION_MODE_IDENTICAL,
    PUBLICATION_MODE_NEW,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SOURCE_MAP_PUBLICATION_AUTHORIZED,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_a49_source_map_publication.offline import (
    assert_analyzer_not_wired,
    assert_no_phase4_artifacts,
    assert_offline_package,
    package_imports_network_clients,
    package_invokes_provider,
)
from app.source_analysis_v31_global_a49_source_map_publication.paths import (
    a48_candidate_path,
    production_source_map_path,
)
from app.source_analysis_v31_global_a49_source_map_publication.publish import (
    atomic_replace,
    publish_exact_bytes,
    write_raw_bytes_atomic,
)
from app.source_analysis_v31_global_a49_source_map_publication.runner import build_bundle


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _tiny_payload() -> dict:
    return SourceMap(
        transcript_id="TR001",
        project_name="demo",
        primary_language="fr",
        source_analysis=SourceAnalysisHeader(
            main_theme="Le rôle de la foi dans l'épreuve",
            author_intent=IntentStatement(
                summary="Enseigner", confidence="high", kinds=("enseigner",)
            ),
            target_audience=IntentStatement(
                summary="Audience croyante", confidence="medium"
            ),
        ),
        topics=(
            Topic(
                topic_id="TOP001",
                label="Foi",
                summary="Résumé",
                source_refs=("SRC000001",),
            ),
        ),
        ideas=(
            Idea(
                idea_id="IDEA001",
                summary="Une idée",
                kind="",
                importance="central",
                topic_refs=("TOP001",),
                source_refs=("SRC000001",),
            ),
        ),
        examples=(
            Example(
                example_id="EX001",
                kind="anecdote",
                summary="Une anecdote",
                supports_idea_refs=("IDEA001",),
                source_refs=("SRC000003",),
            ),
        ),
        references=(
            Reference(
                reference_id="REF001",
                kind="biblical",
                raw_reference="Paul dit quelque part",
                normalized_reference="",
                completeness="vague",
                source_refs=("SRC000004",),
            ),
        ),
        uncertainties=(
            Uncertainty(
                uncertainty_id="UNC001",
                kind="incomplete_reference",
                description="Référence non située",
                severity="medium",
                source_refs=("SRC000004",),
            ),
        ),
        repetitions=(
            Repetition(
                repetition_id="REP001",
                character="development",
                description="Reprise développée",
                idea_refs=("IDEA001",),
                source_refs=("SRC000002",),
            ),
        ),
        author_voice_profile=AuthorVoiceProfile(
            tone=("didactique",),
            register="langue parlée",
        ),
        stats=SourceMapStats(
            topic_count=1,
            idea_count=1,
            example_count=1,
            reference_count=1,
            uncertainty_count=1,
            repetition_count=1,
            source_segment_count=8,
            referenced_source_segments=4,
            source_coverage_ratio=0.5,
        ),
        analysis=AnalysisProvenance(
            prompt_version=HISTORICAL_PROMPT,
            schema_version=SOURCE_MAP_SCHEMA_VERSION,
            provider="anthropic",
            model="claude-sonnet-5",
            strategy=TRANSPORT_VERSION,
            signature="a49-fixture",
        ),
    ).to_dict()


def _write_candidate(project: str, sortie, payload: dict) -> bytes:
    path = a48_candidate_path(project, sortie_dir=sortie)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return raw


class TestHistoricalFreeze:
    def test_history_and_offline_contract(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        assert_no_phase4_artifacts()
        assert A34_STATUS_PRESERVED == "PASS"
        assert A35_STATUS_PRESERVED == "FAIL"
        assert A36_STATUS_PRESERVED == "PASS"
        assert A37_STATUS_PRESERVED == "PASS"
        assert A38_STATUS_PRESERVED == "FAIL"
        assert A39_STATUS_PRESERVED == "PASS"
        assert A40_STATUS_PRESERVED == "FAIL"
        assert A41_STATUS_PRESERVED == "PASS"
        assert A42_STATUS_PRESERVED == "PASS"
        assert A43_STATUS_PRESERVED == "PASS"
        assert A44_STATUS_PRESERVED == "PASS"
        assert A45_STATUS_PRESERVED == "PASS"
        assert A46_STATUS_PRESERVED == "FAIL"
        assert A47_STATUS_PRESERVED == "PASS"
        assert A48_STATUS_PRESERVED == "PASS"
        assert PHASE == "3B.7.7A.49"
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert SOURCE_MAP_PUBLICATION_AUTHORIZED is True
        assert FUTURE_PROMPT == "global-consolidation-3.0.1"
        assert HISTORICAL_PROMPT == "global-consolidation-3.0"
        assert TRANSPORT_VERSION == "global-consolidation-transport-3.0"
        assert GLOBAL_INTENT_MAX_CHARS == 320
        assert LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN == "YES"
        assert RELATION_QUALITY_TECHNICAL_DEBT == "YES"
        assert A49_COST_USD == 0.0
        assert A46_COST_USD == 0.26852
        assert HISTORICAL_REQUEST_HASH == A45_REQUEST_HASH
        assert HISTORICAL_REQUEST_HASH.startswith("fbffc38c")
        identity = verify_a46_identity()
        assert identity["ok"] is True


class TestPublicationMechanics:
    def test_eligible_candidate_publishes_exact_bytes(self, tmp_path):
        project = "a49_pub"
        payload = _tiny_payload()
        raw = _write_candidate(project, tmp_path, payload)
        bundle = build_bundle(
            project,
            sortie_dir=tmp_path,
            tests="unit A.49 publish",
            pastoral_contract=False,
            publication_eligible_override="YES",
            update_state=False,
        )
        target = production_source_map_path(project, sortie_dir=tmp_path)
        assert target.is_file()
        assert target.read_bytes() == raw
        assert bundle["header"]["publication_mode"] == PUBLICATION_MODE_NEW
        assert bundle["header"]["byte_identity"] == BYTE_IDENTITY_EXACT
        assert bundle["reload"]["json_parse"] == "PASS"
        assert bundle["reload"]["model_load"] == "PASS"
        assert bundle["reload"]["structural_scan"] == "PASS"
        assert not partial_path(target).exists()

    def test_idempotent_second_publish_does_not_rewrite(self, tmp_path):
        project = "a49_idem"
        raw = _write_candidate(project, tmp_path, _tiny_payload())
        first = build_bundle(
            project,
            sortie_dir=tmp_path,
            pastoral_contract=False,
            publication_eligible_override="YES",
            update_state=False,
        )
        target = production_source_map_path(project, sortie_dir=tmp_path)
        mtime = target.stat().st_mtime_ns
        second = build_bundle(
            project,
            sortie_dir=tmp_path,
            pastoral_contract=False,
            publication_eligible_override="YES",
            update_state=False,
        )
        assert target.read_bytes() == raw
        assert first["header"]["publication_mode"] == PUBLICATION_MODE_NEW
        assert second["header"]["publication_mode"] == PUBLICATION_MODE_IDENTICAL
        assert second["publication"]["atomic_publication"] == "SKIPPED_IDENTICAL"
        assert target.stat().st_mtime_ns == mtime

    def test_conflict_blocks_overwrite(self, tmp_path):
        project = "a49_conflict"
        _write_candidate(project, tmp_path, _tiny_payload())
        target = production_source_map_path(project, sortie_dir=tmp_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        original = b'{"schema_version": "other"}\n'
        target.write_bytes(original)
        bundle = build_bundle(
            project,
            sortie_dir=tmp_path,
            pastoral_contract=False,
            publication_eligible_override="YES",
            update_state=False,
        )
        assert bundle["header"]["publication_mode"] == PUBLICATION_MODE_CONFLICT
        assert bundle["header"]["result"] == "BLOCKED"
        assert target.read_bytes() == original
        assert bundle["header"]["source_map"] == "NOT PUBLISHED"
        assert bundle["header"]["phase_3b"] == "INCOMPLETE"

    def test_ineligible_does_not_publish(self, tmp_path):
        project = "a49_ineligible"
        _write_candidate(project, tmp_path, _tiny_payload())
        bundle = build_bundle(
            project,
            sortie_dir=tmp_path,
            pastoral_contract=False,
            publication_eligible_override="NO",
            update_state=False,
        )
        target = production_source_map_path(project, sortie_dir=tmp_path)
        assert not target.is_file()
        assert bundle["header"]["result"] == "BLOCKED"
        assert bundle["header"]["publication_eligible"] == "NO"
        assert bundle["gate"]["authorized"] is False

    def test_invalid_candidate_does_not_publish(self, tmp_path):
        project = "a49_invalid"
        _write_candidate(project, tmp_path, {"chapters": [{"title": "One"}]})
        bundle = build_bundle(
            project,
            sortie_dir=tmp_path,
            pastoral_contract=False,
            publication_eligible_override="YES",
            update_state=False,
        )
        target = production_source_map_path(project, sortie_dir=tmp_path)
        assert not target.is_file()
        assert bundle["header"]["result"] == "BLOCKED"
        assert bundle["gate"]["gates"]["structural_scanner"] == "FAIL"

    def test_atomicity_failure_leaves_no_production_file(self, tmp_path, monkeypatch):
        target = tmp_path / "analysis" / "source_map.json"
        payload = json.dumps(_tiny_payload(), ensure_ascii=False, indent=2) + "\n"

        def _boom(partial, dest):
            raise OSError("replace failed")

        monkeypatch.setattr(
            "app.source_analysis_v31_global_a49_source_map_publication.publish.atomic_replace",
            _boom,
        )
        with pytest.raises(OSError):
            write_raw_bytes_atomic(target, payload.encode("utf-8"))
        assert not target.exists()
        assert not partial_path(target).exists()

    def test_network_package_is_offline(self):
        assert_offline_package()
        assert package_imports_network_clients() == []
        assert package_invokes_provider() == []


class TestDirectPublishHelper:
    def test_inspect_conflict_without_runner(self, tmp_path):
        target = tmp_path / "source_map.json"
        candidate = b'{"a": 1}\n'
        target.write_bytes(b'{"a": 2}\n')
        result = publish_exact_bytes(target, candidate, authorized=True)
        assert result["mode"] == PUBLICATION_MODE_CONFLICT
        assert target.read_bytes() == b'{"a": 2}\n'
        assert atomic_replace is not None
        assert source_map_path(PROJECT_NAME).name == "source_map.json"
