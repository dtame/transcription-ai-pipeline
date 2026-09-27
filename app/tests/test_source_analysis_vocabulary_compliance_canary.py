"""
Phase 3B.4.5 — canary de conformité lexicale Prompt 1.3.

Aucun test de ce fichier n'ouvre de connexion : `no_ai_network` interdit
tout POST. Le moteur réel n'est jamais construit.
"""

from __future__ import annotations

import inspect
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
from app.source_analysis.canonical_vocabulary import (
    CURRENT_PROMPT_VERSION,
    OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS,
    VOCABULARY_BLOCK_BEGIN,
    build_canonical_vocabulary_contract,
    prompt_decoder_parity,
)
from app.source_analysis.compact_schema import build_compact_response_schema
from app.source_analysis.errors import MaxRealCallsExceededError
from app.source_analysis.guard import RealCallGuard
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.real_run import GuardedEngine
from app.source_analysis.schema import build_response_schema, schema_fingerprint
from app.source_analysis.transcript_input import (
    TranscriptInputMode,
    load_transcript_input,
)
from app.source_analysis.ultra_compact_schema import (
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
from app.source_analysis_ultra_compact_canary.prompt import CANARY_EXCERPT_NOTICE
from app.source_analysis_vocabulary_compliance_canary import constants as canary_constants
from app.source_analysis_vocabulary_compliance_canary.constants import (
    CANARY_MAX_OUTPUT_TOKENS,
    EXPECTED_MODEL,
    EXPECTED_PROMPT_VERSION,
    EXPECTED_PROVIDER,
    HISTORICAL_SRC_IDS,
    MAX_ATTEMPTS,
    MAX_REAL_CALLS,
    TRANSPORT_VERSION,
)
from app.source_analysis_vocabulary_compliance_canary.decoder_integrity import (
    decoder_has_repair,
    decoder_is_fail_closed,
    verify_decoder_integrity,
)
from app.source_analysis_vocabulary_compliance_canary.observe import (
    observe_controlled_tokens,
    vocabulary_compliance_status,
)
from app.source_analysis_vocabulary_compliance_canary.preflight import (
    verify_prompt_version,
    verify_vocabulary_contract_included,
    verify_vocabulary_parity,
)
from app.source_analysis_vocabulary_compliance_canary.runner import (
    run_vocabulary_compliance_canary,
)
from app.source_analysis_vocabulary_compliance_canary.selection import (
    historical_window_available,
    select_historical_canary_segments,
)
from app.source_analysis_vocabulary_compliance_canary.writer import (
    canary_sourcemap_path,
    input_path,
    production_source_map_path,
)
from app.source_analysis.vocabulary_fixtures import (
    build_golden_full_vocabulary_transport,
    build_observed_3b43_invalid_transport,
)
from app.tests.source_analysis_fixtures import (  # noqa: F401
    analysis_env,
    fake_engine,
    fake_ultra_analysis_payload,
    write_cleanup_provenance,
    write_transcript,
    build_transcript_document,
)

_HISTORICAL_TEXT = "he didn't say if you want to see the father"


def _historical_ids_from_document(document) -> tuple[str, ...]:
    return tuple(segment.id for segment in document.segments[:10])


def _isolated_env(env, monkeypatch, texts=None):
    body = texts or ((_HISTORICAL_TEXT,) * 10)
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
    monkeypatch.setattr(
        canary_constants,
        "HISTORICAL_SRC_IDS",
        _historical_ids_from_document(original),
    )
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


class TestPromptAndParity:
    def test_prompt_13_selected(self):
        assert CURRENT_PROMPT_VERSION == "1.3"
        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"
        assert EXPECTED_PROMPT_VERSION == "1.3"
        assert verify_prompt_version() == "1.3"

    def test_vocabulary_contract_included_in_system_prompt(self):
        from app.source_analysis.prompt import build_system_prompt

        system = build_system_prompt("en")
        assert verify_vocabulary_contract_included(system) is True
        assert VOCABULARY_BLOCK_BEGIN in system
        assert build_canonical_vocabulary_contract() in system
        assert "JETONS DE PROTOCOLE" in system
        assert "n'invente aucun synonyme" in system
        assert "ne le traduis pas" in system
        assert "ne le paraphrase pas" in system
        assert "ne remplace pas les underscores" in system

    def test_parity_exact(self):
        from app.source_analysis.prompt import build_system_prompt

        parity = verify_vocabulary_parity(build_system_prompt("en"))
        assert parity["missing_from_prompt"] == []
        assert parity["extra_in_prompt"] == []
        contract = prompt_decoder_parity()
        for row in contract.values():
            assert row["missing_from_prompt"] == []
            assert row["extra_in_prompt"] == []


class TestGenerationCUnchanged:
    def test_generation_c_unchanged_and_zero_enums(self):
        arch = verify_generation_c_architecture()
        report = audit_generation_c_complexity()
        audit = audit_local_anthropic_generation_c()
        c = report["generation_c"]["metrics"]
        ac = report["anthropic_generation_c"]["metrics"]
        assert arch["generation_c_selected"] is True
        assert arch["generation_a_selected"] is False
        assert arch["generation_b_selected"] is False
        assert c["serialized_json_bytes"] == 559
        assert ac["serialized_json_bytes"] == 621
        assert c["object_nodes"] == 2
        assert c["arrays_of_objects"] == 1
        assert c["total_properties"] == 11
        assert c["constraints"] == 0
        assert c["enum_count"] == 0
        assert report["sha_match_3b42"] is True
        assert audit["provider_enums"] == 0
        assert audit["compatibility"] == "PASS"
        adapted = prepare_anthropic_json_schema(production_generation_c_schema())
        assert all(not value for value in audit_unsupported_features(adapted).values())
        assert not payload_contains_ab_schema(adapted)


class TestDecoderIntegrity:
    def test_decoder_fail_closed_no_alias_repair(self):
        report = verify_decoder_integrity()
        assert report["fail_closed"] is True
        assert report["aliases"] is False
        assert report["synonym_map"] is False
        assert report["fuzzy_repair"] is False
        assert decoder_is_fail_closed() is True
        assert decoder_has_repair() is False
        source = inspect.getsource(
            __import__(
                "app.source_analysis.semantic_transport_decoder",
                fromlist=["decode_to_canonical_raw"],
            )
        )
        assert "alias_map" not in source
        assert "synonym_map" not in source
        assert "fuzzy" not in source


class TestObservation:
    def test_observes_canonical_and_invalid_without_repair(self):
        golden = build_golden_full_vocabulary_transport(["SRC000001", "SRC000002"])
        observed = observe_controlled_tokens(golden)
        assert observed
        assert all(item["canonical"] is True for item in observed)
        assert vocabulary_compliance_status(observed) == "PASS"

        invalid = build_observed_3b43_invalid_transport("SRC000001")
        seen = observe_controlled_tokens(invalid)
        kinds = [item["value"] for item in seen if item["vocabulary"] == "uncertainty.kind"]
        assert list(OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS) == kinds
        assert all(item["canonical"] is False for item in seen if item["vocabulary"] == "uncertainty.kind")
        assert vocabulary_compliance_status(seen) == "FAIL"

    def test_intent_audience_v_are_not_enums(self):
        payload = {
            "theme": "t",
            "intent": "i",
            "ic": "high",
            "aud": "a",
            "ac": "low",
            "records": [
                {"k": "INTENT_KIND", "v": "enseigner", "s": [], "l": [], "m": []},
                {"k": "AUDIENCE_KIND", "v": "croyants", "s": [], "l": [], "m": []},
            ],
        }
        observed = observe_controlled_tokens(payload)
        values = [item["value"] for item in observed]
        assert "enseigner" not in values
        assert "croyants" not in values
        assert {"INTENT_KIND", "AUDIENCE_KIND"} <= set(values)


class TestHistoricalSelection:
    def test_missing_historical_window_stops(self, analysis_env, no_ai_network):
        original = build_transcript_document(
            project_name=analysis_env.project_name,
            texts=(_HISTORICAL_TEXT,) * 10,
            language="en",
            transcript_id="TR001",
        )
        original_path = write_transcript(analysis_env.transcripts_dir, original)
        clean_path = write_transcript(analysis_env.transcripts_dir / "clean", original)
        write_cleanup_provenance(
            analysis_env.sortie / analysis_env.project_name / "audit" / "cleanup_application.json",
            original_path=original_path,
            clean_path=clean_path,
            original=original,
            clean=original,
            removed=[],
        )
        result = run_vocabulary_compliance_canary(
            analysis_env.project_name,
            dry_run=True,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
        )
        assert result.outcome == "FAIL"
        assert result.actual_real_calls == 0
        assert result.network["anthropic"] == 0
        assert result.classification == "PRE_CALL_HISTORICAL_INPUT_UNAVAILABLE"
        assert result.would_call_ai is False

    def test_exact_historical_ids_when_patched(self, analysis_env, monkeypatch):
        _isolated_env(analysis_env, monkeypatch)
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
        first = select_historical_canary_segments(transcript.segments)
        second = select_historical_canary_segments(transcript.segments)
        assert first.source_ids == second.source_ids == canary_constants.HISTORICAL_SRC_IDS
        assert first.word_count == 100
        assert historical_window_available(transcript.segments) is True


class TestDryRunAndGuards:
    def test_dry_run_prompt_13_generation_c_no_network(
        self, analysis_env, monkeypatch, no_ai_network
    ):
        _isolated_env(analysis_env, monkeypatch)
        result = run_vocabulary_compliance_canary(
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
        assert result.network["openai"] == 0
        assert result.provider == EXPECTED_PROVIDER
        assert result.model == EXPECTED_MODEL
        assert result.prompt_version == "1.3"
        assert result.vocabulary_parity == "PASS"
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
        assert payload["prompt_version"] == "1.3"
        assert payload["raw_generation_c_sha256"] == ultra_compact_schema_fingerprint()
        assert "timestamp" not in payload
        assert payload["transcript_id"] == "TR001"

    def test_http_failure_counts_as_one_call(
        self, analysis_env, monkeypatch, no_ai_network
    ):
        _isolated_env(analysis_env, monkeypatch)
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
        result = run_vocabulary_compliance_canary(
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
        assert result.classification == "SERVER_GRAMMAR_REGRESSION"
        assert result.outcome == "FAIL"
        assert engine.call_count == 1

    def test_retry_disabled_and_max_attempts_one(
        self, analysis_env, monkeypatch, no_ai_network
    ):
        _isolated_env(analysis_env, monkeypatch)
        engine = fake_engine(script=[AITransientError("timeout")], model="claude-sonnet-5")
        engine.provider_name = "anthropic"
        result = run_vocabulary_compliance_canary(
            analysis_env.project_name,
            dry_run=False,
            engine=engine,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
        )
        assert result.max_attempts == MAX_ATTEMPTS == 1
        assert getattr(engine, "_retry_policy").max_attempts == 1
        assert engine.call_count == 1
        assert result.actual_real_calls == 1
        assert result.retry_disabled is True
        assert result.fallback_disabled is True

    def test_guarded_engine_refuses_second_generate(self, no_ai_network):
        inner = fake_engine(payload=fake_ultra_analysis_payload())
        guarded = GuardedEngine(inner, RealCallGuard(max_calls=MAX_REAL_CALLS))
        guarded.generate(AIRequest(prompt="x"))
        with pytest.raises(MaxRealCallsExceededError):
            guarded.generate(AIRequest(prompt="x"))
        assert guarded.generate_calls == 1


class TestLocalPipelineAndNoProductionWrites:
    def test_canonical_pipeline_and_no_production_writer(
        self, analysis_env, monkeypatch, no_ai_network
    ):
        called = []

        def _forbidden_write(*args, **kwargs):
            called.append(True)
            raise AssertionError("write_source_map production ne doit pas être appelé")

        monkeypatch.setattr(
            "app.source_analysis.writer.write_source_map", _forbidden_write
        )
        _isolated_env(analysis_env, monkeypatch)
        dry = run_vocabulary_compliance_canary(
            analysis_env.project_name,
            dry_run=True,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
            write_artifacts=False,
        )
        engine = _routed_fake(dry.selected_source_ids)
        result = run_vocabulary_compliance_canary(
            analysis_env.project_name,
            dry_run=False,
            engine=engine,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
        )
        assert result.transport_parse == "PASS"
        assert result.decoder == "PASS"
        assert result.reconstruction == "PASS"
        assert result.normalization == "PASS"
        assert result.canonical_validation == "PASS"
        assert result.source_refs_in_canary == "PASS"
        assert result.link_validation == "PASS"
        assert result.editorial_leakage == "PASS"
        assert result.vocabulary_compliance == "PASS"
        assert result.invalid_tokens == []
        assert result.vocabulary_prompt_compliance == "VERIFIED"
        assert result.outcome == "PASS"
        assert result.production_source_map_created is False
        assert result.writer_production_called is False
        assert result.global_source_analysis_success is False
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

    def test_invalid_token_is_partial_not_repaired(
        self, analysis_env, monkeypatch, no_ai_network
    ):
        _isolated_env(analysis_env, monkeypatch)
        dry = run_vocabulary_compliance_canary(
            analysis_env.project_name,
            dry_run=True,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
            write_artifacts=False,
        )
        payload = build_observed_3b43_invalid_transport(dry.selected_source_ids[0])
        engine = fake_engine(payload=payload, model="claude-sonnet-5")
        engine.provider_name = "anthropic"
        result = run_vocabulary_compliance_canary(
            analysis_env.project_name,
            dry_run=False,
            engine=engine,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
        )
        assert result.actual_real_calls == 1
        assert result.vocabulary_compliance == "FAIL"
        assert result.decoder == "FAIL"
        assert result.outcome == "PARTIAL"
        assert result.reused_3b43_invalid_tokens == list(
            OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS
        )
        assert result.vocabulary_prompt_compliance == "FAILED"
        assert engine.call_count == 1


class TestPromptIsExcerptNotMiniSchema:
    def test_canary_prompt_keeps_generation_c(self, analysis_env, monkeypatch):
        from app.source_analysis_ultra_compact_canary.prompt import (
            build_canary_user_prompt,
        )

        _isolated_env(analysis_env, monkeypatch)
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
        selected = select_historical_canary_segments(transcript.segments)
        user = build_canary_user_prompt(transcript, selected.segments)
        assert "small source-analysis corpus" in user
        assert CANARY_EXCERPT_NOTICE.splitlines()[0] in user
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


PROJECT = "pastoral_retreat_v2_validation"
_REAL_CLEAN = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation\transcripts\clean\transcript_data.json"
)


@pytest.mark.skipif(not _REAL_CLEAN.exists(), reason=f"corpus réel {PROJECT} absent")
class TestRealCorpusSelection:
    def test_real_clean_is_exact_3b43_window(self):
        from app.cleanup_application.writer import audit_path, clean_json_path
        from app.source_analysis.writer import transcripts_dir

        transcript = load_transcript_input(
            clean_json_path(PROJECT),
            project_name=PROJECT,
            mode=TranscriptInputMode.DERIVED,
            provenance_path=audit_path(PROJECT),
            original_transcript_path=transcripts_dir(PROJECT) / "transcript_data.json",
        )
        first = select_historical_canary_segments(transcript.segments)
        second = select_historical_canary_segments(transcript.segments)
        assert first.source_ids == second.source_ids == HISTORICAL_SRC_IDS
        assert first.segment_count == 10
        assert first.word_count == 100
        assert first.texts_unchanged({s.src_id: s.text for s in transcript.segments})
        assert all(segment.text == _HISTORICAL_TEXT for segment in first.segments)
        historical = Path(
            r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation\audit"
            r"\source_analysis_ultra_compact_canary_input.json"
        )
        if historical.is_file():
            payload = json.loads(historical.read_text(encoding="utf-8"))
            assert list(first.source_ids) == payload["selected_source_ids"]
            assert [
                {"source_id": segment.src_id, "text": segment.text}
                for segment in first.segments
            ] == payload["selected_sources"]
