"""
Phase 3B.4.3 — canary de grammaire Anthropic (Generation C / semantic-transport-v1).

Aucun test de ce fichier n'ouvre de connexion : `no_ai_network` interdit
tout POST. Le moteur réel n'est jamais construit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.contracts import AIRequest
from app.ai.errors import AIRequestError, AITransientError
from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.source_analysis.compact_schema import build_compact_response_schema
from app.source_analysis.errors import MaxRealCallsExceededError
from app.source_analysis.guard import RealCallGuard
from app.source_analysis.real_run import GuardedEngine
from app.source_analysis.schema import build_response_schema, schema_fingerprint
from app.source_analysis.transcript_input import (
    SourceSegment,
    TranscriptInputMode,
    load_transcript_input,
)
from app.source_analysis.ultra_compact_schema import (
    SEMANTIC_TRANSPORT_VERSION,
    build_ultra_compact_response_schema,
    ultra_compact_schema_fingerprint,
)
from app.source_analysis.writer import source_map_path
from app.source_analysis_ultra_compact_canary.architecture import (
    audit_generation_c_complexity,
    audit_local_anthropic_generation_c,
    payload_contains_ab_schema,
    production_generation_c_schema,
    verify_generation_c_architecture,
)
from app.source_analysis_ultra_compact_canary.classify import classify_server_error
from app.source_analysis_ultra_compact_canary.constants import (
    CANARY_MAX_OUTPUT_TOKENS,
    EXPECTED_MODEL,
    EXPECTED_PROVIDER,
    HISTORICAL_SRC_IDS,
    MAX_ATTEMPTS,
    MAX_REAL_CALLS,
    MAX_WORDS,
    TRANSPORT_VERSION,
)
from app.source_analysis_ultra_compact_canary.pipeline import run_local_pipeline
from app.source_analysis_ultra_compact_canary.prompt import (
    CANARY_EXCERPT_NOTICE,
    build_canary_user_prompt,
)
from app.source_analysis_ultra_compact_canary.runner import run_ultra_compact_canary
from app.source_analysis_ultra_compact_canary.selection import (
    historical_window_available,
    is_eligible_canary_segment,
    select_canary_segments,
)
from app.source_analysis_ultra_compact_canary.writer import (
    canary_sourcemap_path,
    input_path,
    production_source_map_path,
)
from app.tests.source_analysis_fixtures import (
    analysis_env,  # noqa: F401
    fake_engine,
    fake_ultra_analysis_payload,
    write_cleanup_provenance,
    write_transcript,
    build_transcript_document,
)

_EN = (
    "The faith of the people is not a slogan and it does not remove "
    "the trial they walk through. When they stand in the storm they "
    "learn what they really believe and they keep walking with the "
    "Lord who is with them in the middle of the trouble."
)


def _english_texts(count: int = 16) -> tuple[str, ...]:
    return tuple(f"{_EN} Passage {index}." for index in range(count))


def _segment(src_id: str, text: str, order: int = 1) -> SourceSegment:
    return SourceSegment(
        src_id=src_id,
        source_id="AUDIO001",
        start=float(order),
        end=float(order) + 1.0,
        text=text,
        source_order=order,
    )


def _canary_env(env, texts: tuple[str, ...] | None = None):
    """Transcript clean anglais dérivé, IDs réels, provenance DERIVED."""
    body = texts or (
        ("Euh.", "Amen.", "Le rôle de la foi dans l'épreuve est central pour nous aujourd'hui.")
        + _english_texts(16)
    )
    original = build_transcript_document(
        project_name=env.project_name,
        texts=body,
        language="en",
        transcript_id="TR001",
    )
    original_path = write_transcript(env.transcripts_dir, original)
    clean_path = write_transcript(env.transcripts_dir / "clean", original)
    provenance_path = env.sortie / env.project_name / "audit" / "cleanup_application.json"
    write_cleanup_provenance(
        provenance_path,
        original_path=original_path,
        clean_path=clean_path,
        original=original,
        clean=original,
        removed=[],
    )
    env.transcript_path = original_path
    env.document = original
    return clean_path, provenance_path, original


def _remap_ultra(src_ids: list[str]) -> dict:
    payload = fake_ultra_analysis_payload()
    chosen = list(src_ids[:3]) or list(src_ids)
    for record in payload.get("records") or []:
        if record.get("s"):
            record["s"] = list(chosen)
    return payload


def _routed_fake(src_ids: list[str], **kwargs):
    engine = fake_engine(payload=_remap_ultra(src_ids), model="claude-sonnet-5", **kwargs)
    engine.provider_name = "anthropic"
    return engine


class TestGenerationCArchitecture:
    def test_generation_c_selected_a_and_b_not_selected(self):
        arch = verify_generation_c_architecture()
        assert arch["generation_c_selected"] is True
        assert arch["generation_b_selected"] is False
        assert arch["generation_a_selected"] is False
        assert arch["future_analyzer_uses_c"] is True
        assert arch["decoder_fail_closed"] is True
        assert arch["canonical_sourcemap_changed"] is False
        assert arch["canonical_validator_changed"] is False
        assert arch["transport_version"] == "semantic-transport-v1"
        raw_c = production_generation_c_schema()
        assert raw_c == build_ultra_compact_response_schema()
        assert ultra_compact_schema_fingerprint(raw_c) != schema_fingerprint(
            build_response_schema()
        )
        assert ultra_compact_schema_fingerprint(raw_c) != schema_fingerprint(
            build_compact_response_schema()
        )

    def test_complexity_matches_3b42_and_not_regressed(self):
        report = audit_generation_c_complexity()
        c = report["generation_c"]["metrics"]
        ac = report["anthropic_generation_c"]["metrics"]
        assert c["object_nodes"] == 2
        assert c["arrays_of_objects"] == 1
        assert c["total_properties"] == 11
        assert c["constraints"] == 0
        assert c["enum_count"] == 0
        assert c["serialized_json_bytes"] == 559
        assert ac["serialized_json_bytes"] == 621
        assert report["sha_match_3b42"] is True
        assert report["regressed"] is False

    def test_local_anthropic_audit_clean(self):
        audit = audit_local_anthropic_generation_c()
        assert audit["compatibility"] == "PASS"
        assert audit["known_unsupported_constructs"] == 0
        assert audit["recursive_refs"] == 0
        assert audit["objects"] == 2
        assert audit["arrays_of_objects"] == 1
        assert audit["properties"] == 11
        assert audit["constraints"] == 0
        assert audit["provider_enums"] == 0
        adapted = prepare_anthropic_json_schema(build_ultra_compact_response_schema())
        features = audit_unsupported_features(adapted)
        assert all(not value for value in features.values())
        assert not payload_contains_ab_schema(adapted)


class TestSelection:
    def test_prefers_historical_window_when_present(self):
        historical_text = "he didn't say if you want to see the father"
        segments = tuple(
            _segment(src_id, historical_text, order=index)
            for index, src_id in enumerate(HISTORICAL_SRC_IDS, start=1)
        )
        first = select_canary_segments(segments)
        second = select_canary_segments(segments)
        assert first.source_ids == second.source_ids == HISTORICAL_SRC_IDS
        assert first.word_count == 100
        assert historical_window_available(segments) is True

    def test_fallback_deterministic_and_preserves_real_src_ids(self):
        segments = (
            _segment("SRC002700", "Euh."),
            _segment("SRC002701", "Amen."),
            _segment("SRC002719", _EN + " One."),
            _segment("SRC002721", _EN + " Two."),
            _segment("SRC002723", _EN + " Three."),
            _segment("SRC002725", _EN + " Four."),
            _segment("SRC002727", _EN + " Five."),
            _segment("SRC002729", _EN + " Six."),
            _segment("SRC002731", _EN + " Seven."),
            _segment("SRC002733", _EN + " Eight."),
            _segment("SRC002735", _EN + " Nine."),
            _segment("SRC002737", _EN + " Ten."),
            _segment("SRC002739", _EN + " Eleven."),
            _segment("SRC002741", _EN + " Twelve."),
        )
        first = select_canary_segments(segments)
        second = select_canary_segments(segments)
        assert first.source_ids == second.source_ids
        assert first.source_ids[0] == "SRC002719"
        assert "SRC000001" not in first.source_ids
        assert all(src.startswith("SRC002") for src in first.source_ids)
        assert first.texts_unchanged({s.src_id: s.text for s in segments})
        assert first.word_count <= MAX_WORDS
        assert first.segment_count >= 8
        assert first.word_count >= 100

    def test_rejects_french_unknown_and_fillers(self):
        assert is_eligible_canary_segment(_segment("SRC000010", "Euh.")) is False
        assert is_eligible_canary_segment(_segment("SRC000011", "Amen.")) is False
        assert (
            is_eligible_canary_segment(
                _segment(
                    "SRC000012",
                    "Le rôle de la foi dans l'épreuve est central pour nous aujourd'hui.",
                )
            )
            is False
        )
        assert is_eligible_canary_segment(_segment("SRC000013", _EN)) is True


class TestDryRunAndSchemaContract:
    def test_dry_run_uses_production_generation_c_no_network(
        self, analysis_env, no_ai_network
    ):
        _canary_env(analysis_env)
        result = run_ultra_compact_canary(
            analysis_env.project_name,
            dry_run=True,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
        )
        assert result.outcome == "PASS"
        assert result.would_call_ai is True
        assert result.actual_real_calls == 0
        assert result.network["anthropic"] == 0
        assert result.provider == EXPECTED_PROVIDER
        assert result.model == EXPECTED_MODEL
        assert result.output_format_type == "json_schema"
        assert result.uses_production_generation_c is True
        assert result.generation_a_absent_from_payload is True
        assert result.generation_b_absent_from_payload is True
        assert result.local_compatibility == "PASS"
        assert result.retry_disabled is True
        assert result.fallback_disabled is True
        assert result.max_real_calls == 1
        assert result.max_attempts == 1
        assert result.cache_isolated is True
        assert result.cache_used is False
        assert result.estimated_output_budget == CANARY_MAX_OUTPUT_TOKENS
        assert result.real_src_ids_preserved is True
        assert result.text_unchanged is True
        assert result.input_deterministic is True
        assert result.input_sha256_run1 == result.input_sha256_run2
        assert result.provenance_verified is True
        assert not production_source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()
        payload = json.loads(
            input_path(analysis_env.project_name, sortie_dir=analysis_env.sortie).read_text(
                encoding="utf-8"
            )
        )
        assert payload["transport_version"] == TRANSPORT_VERSION
        assert payload["raw_generation_c_sha256"] == ultra_compact_schema_fingerprint()
        assert "timestamp" not in payload
        assert payload["source_transcript_id"] == "TR001"

    def test_canary_prompt_is_excerpt_not_mini_schema(self, analysis_env):
        _canary_env(analysis_env)
        transcript = load_transcript_input(
            analysis_env.transcripts_dir / "clean" / "transcript_data.json",
            project_name=analysis_env.project_name,
            mode=TranscriptInputMode.DERIVED,
            provenance_path=analysis_env.sortie
            / analysis_env.project_name
            / "audit"
            / "cleanup_application.json",
            original_transcript_path=analysis_env.transcripts_dir / "transcript_data.json",
        )
        selected = select_canary_segments(transcript.segments)
        user = build_canary_user_prompt(transcript, selected.segments)
        assert "small source-analysis corpus" in user
        assert "semantic-transport-v1" in user
        assert CANARY_EXCERPT_NOTICE.splitlines()[0] in user
        for src_id in selected.source_ids:
            assert src_id in user
        generation_c = production_generation_c_schema()
        request = AIRequest(
            prompt=user,
            system_prompt="x",
            model=EXPECTED_MODEL,
            response_schema=generation_c,
        )
        payload = AnthropicEngine(model=EXPECTED_MODEL, api_key="t").build_payload(
            request, EXPECTED_MODEL
        )
        schema = payload["output_config"]["format"]["schema"]
        assert payload["output_config"]["format"]["type"] == "json_schema"
        assert schema_fingerprint(schema) == schema_fingerprint(
            prepare_anthropic_json_schema(generation_c)
        )
        assert schema_fingerprint(schema) != schema_fingerprint(
            prepare_anthropic_json_schema(build_response_schema())
        )
        assert schema_fingerprint(schema) != schema_fingerprint(
            prepare_anthropic_json_schema(build_compact_response_schema())
        )
        assert not payload_contains_ab_schema(schema)


class TestGuardRetryFallback:
    def test_http_failure_counts_as_one_call(self, analysis_env, no_ai_network):
        _canary_env(analysis_env)
        engine = fake_engine(
            script=[
                AIRequestError(
                    "Anthropic a répondu 400. Corps : "
                    '{"type":"invalid_request_error",'
                    '"message":"The compiled grammar is too large"}'
                )
            ],
            model="claude-sonnet-5",
        )
        engine.provider_name = "anthropic"
        result = run_ultra_compact_canary(
            analysis_env.project_name,
            dry_run=False,
            engine=engine,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
        )
        assert result.actual_real_calls == 1
        assert result.network["anthropic"] == 1
        assert result.network["openai"] == 0
        assert result.server_grammar_result == "REJECTED"
        assert result.server_grammar_acceptance == "REJECTED"
        assert result.classification == "SERVER_GRAMMAR_REJECTED"
        assert result.http_status == 400
        assert result.outcome == "FAIL"
        assert result.pipeline_result == "N/A"
        assert engine.call_count == 1

    def test_retry_disabled_on_injected_engine(self, analysis_env, no_ai_network):
        _canary_env(analysis_env)
        engine = fake_engine(
            script=[AITransientError("timeout")],
            model="claude-sonnet-5",
        )
        engine.provider_name = "anthropic"
        result = run_ultra_compact_canary(
            analysis_env.project_name,
            dry_run=False,
            engine=engine,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
        )
        assert result.max_attempts == 1
        assert getattr(engine, "_retry_policy").max_attempts == 1
        assert engine.call_count == 1
        assert result.actual_real_calls == 1
        assert result.network["openai"] == 0
        assert result.retry_disabled is True
        assert result.fallback_disabled is True

    def test_guard_increments_before_failure(self):
        guard = RealCallGuard(max_calls=1)

        class Boom:
            def generate(self, request):
                raise RuntimeError("transport")

        with pytest.raises(RuntimeError):
            guard.guarded_generate(Boom(), object())
        assert guard.call_count == 1
        with pytest.raises(MaxRealCallsExceededError):
            guard.guarded_generate(Boom(), object())

    def test_guarded_engine_refuses_second_generate(self, no_ai_network):
        inner = fake_engine(payload=fake_ultra_analysis_payload())
        guarded = GuardedEngine(inner, RealCallGuard(max_calls=1))
        guarded.generate(AIRequest(prompt="x"))
        with pytest.raises(MaxRealCallsExceededError):
            guarded.generate(AIRequest(prompt="x"))
        assert guarded.generate_calls == 1


class TestLocalPipelineAndNoProductionWrites:
    def test_source_refs_restricted_and_canonical_ids(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        called = []

        def _forbidden_write(*args, **kwargs):
            called.append(True)
            raise AssertionError("write_source_map production ne doit pas être appelé")

        monkeypatch.setattr(
            "app.source_analysis.writer.write_source_map", _forbidden_write
        )
        _canary_env(analysis_env)
        dry = run_ultra_compact_canary(
            analysis_env.project_name,
            dry_run=True,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
            write_artifacts=False,
        )
        engine = _routed_fake(dry.selected_source_ids)
        result = run_ultra_compact_canary(
            analysis_env.project_name,
            dry_run=False,
            engine=engine,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
        )
        assert result.request_accepted is True
        assert result.server_grammar_result == "ACCEPTED"
        assert result.server_grammar_acceptance == "VERIFIED"
        assert result.transport_parse == "PASS"
        assert result.decoder == "PASS"
        assert result.reconstruction == "PASS"
        assert result.normalization == "PASS"
        assert result.canonical_validation == "PASS"
        assert result.source_refs_in_canary == "PASS"
        assert result.link_validation == "PASS"
        assert result.editorial_leakage == "PASS"
        assert result.topic_ids == ["TOP001"]
        assert result.idea_ids[0] == "IDEA001"
        assert result.production_source_map_created is False
        assert result.writer_production_called is False
        assert not called
        assert not source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()
        canary_map = canary_sourcemap_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        )
        assert canary_map.is_file()
        body = json.loads(canary_map.read_text(encoding="utf-8"))
        assert body["canary"] is True
        assert body["not_production"] is True
        assert "CANARY" in body["corpus_note"]
        state = analysis_env.state()
        block = state.get("source_analysis") or {}
        assert block.get("status") != "completed"
        assert result.global_source_analysis_success is False
        assert result.cache_isolated is True
        assert result.cache_used is False

    def test_foreign_source_ref_is_rejected(self, analysis_env):
        _canary_env(analysis_env)
        transcript = load_transcript_input(
            analysis_env.transcripts_dir / "clean" / "transcript_data.json",
            project_name=analysis_env.project_name,
            mode=TranscriptInputMode.DERIVED,
            provenance_path=analysis_env.sortie
            / analysis_env.project_name
            / "audit"
            / "cleanup_application.json",
            original_transcript_path=analysis_env.transcripts_dir / "transcript_data.json",
        )
        selected = select_canary_segments(transcript.segments)
        payload = _remap_ultra(list(selected.source_ids))
        payload["records"][0]["s"] = ["SRC000123"]
        from app.source_analysis.models import AnalysisProvenance

        local = run_local_pipeline(
            payload,
            transcript,
            selected.segments,
            provenance=AnalysisProvenance(
                prompt_version="1.2",
                schema_version="1.0",
                provider="anthropic",
                model="claude-sonnet-5",
                strategy="global",
                signature="test",
            ),
        )
        assert local.decoder == "FAIL"
        assert local.source_refs_in_canary == "FAIL"
        assert any("SRC000123" in item for item in (local.errors or []))

    def test_other_http_400_is_not_grammar(self):
        classification, grammar, acceptance, status = classify_server_error(
            "Anthropic a répondu 400. Corps : {\"type\":\"invalid_request_error\","
            "\"message\":\"max_tokens is required\"}"
        )
        assert classification == "SERVER_REQUEST_REJECTED"
        assert grammar == "UNKNOWN"
        assert acceptance == "UNKNOWN"
        assert status == 400

    def test_other_schema_error_is_not_compiled_grammar(self):
        classification, grammar, acceptance, status = classify_server_error(
            "Anthropic a répondu 400. Corps : {\"type\":\"invalid_request_error\","
            "\"message\":\"invalid schema: unsupported keyword\"}"
        )
        assert classification == "SERVER_SCHEMA_REJECTED"
        assert grammar == "REJECTED"
        assert acceptance == "REJECTED"
        assert status == 400


class TestUsesCleanTranscript:
    def test_selection_reads_clean_not_original(self, analysis_env, no_ai_network):
        _canary_env(analysis_env)
        result = run_ultra_compact_canary(
            analysis_env.project_name,
            dry_run=True,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
        )
        clean = load_transcript_input(
            analysis_env.transcripts_dir / "clean" / "transcript_data.json",
            project_name=analysis_env.project_name,
            mode=TranscriptInputMode.DERIVED,
            provenance_path=analysis_env.sortie
            / analysis_env.project_name
            / "audit"
            / "cleanup_application.json",
            original_transcript_path=analysis_env.transcripts_dir / "transcript_data.json",
        )
        clean_ids = set(clean.src_ids())
        assert set(result.selected_source_ids) <= clean_ids
        by_id = {segment.src_id: segment.text for segment in clean.segments}
        for item in result.selected_texts:
            assert item["text"] == by_id[item["source_id"]]


PROJECT = "pastoral_retreat_v2_validation"
_REAL_CLEAN = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation\transcripts\clean\transcript_data.json"
)


@pytest.mark.skipif(not _REAL_CLEAN.exists(), reason=f"corpus réel {PROJECT} absent")
class TestRealCorpusSelection:
    def test_real_clean_reuses_3b41_window(self):
        from app.cleanup_application.writer import audit_path, clean_json_path
        from app.source_analysis.writer import transcripts_dir

        transcript = load_transcript_input(
            clean_json_path(PROJECT),
            project_name=PROJECT,
            mode=TranscriptInputMode.DERIVED,
            provenance_path=audit_path(PROJECT),
            original_transcript_path=transcripts_dir(PROJECT) / "transcript_data.json",
        )
        first = select_canary_segments(transcript.segments)
        second = select_canary_segments(transcript.segments)
        assert first.source_ids == second.source_ids
        assert set(first.source_ids) <= set(transcript.src_ids())
        assert first.texts_unchanged({s.src_id: s.text for s in transcript.segments})
        if historical_window_available(transcript.segments):
            assert first.source_ids == HISTORICAL_SRC_IDS
            assert first.segment_count == 10
            assert first.word_count == 100
