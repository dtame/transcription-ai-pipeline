"""
Phase 3B.4.4 — contrat lexical canonique.

Aucun réseau. Aucun engine.generate() vers un fournisseur réel.
"""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from app.ai.contracts import AIRequest
from app.ai.estimation import estimate_tokens
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.cleanup_application.writer import audit_path, clean_json_path
from app.source_analysis.cache import (
    SignatureInputs,
    build_signature,
    is_cache_valid,
    prompt_fingerprint,
)
from app.source_analysis.canonical_vocabulary import (
    CURRENT_PROMPT_VERSION,
    EXACT_IDENTIFIER_EXAMPLES,
    GENERATION_C_ANTHROPIC_SHA256_3B43,
    GENERATION_C_RAW_SHA256_3B43,
    OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS,
    PREVIOUS_PROMPT_SHA256,
    PREVIOUS_PROMPT_VERSION,
    PREVIOUS_SIGNATURE,
    VOCABULARY_CATEGORY_ORDER,
    all_controlled_values,
    build_canonical_vocabulary_contract,
    build_record_field_contract,
    canonical_allowed_vocabulary,
    controlled_value_count,
    extract_prompt_controlled_vocabularies,
    intent_audience_kinds_are_free_text,
    prompt_controlled_vocabulary,
    prompt_decoder_parity,
    record_field_contract,
    vocabulary_fallbacks,
    vocabulary_sources,
)
from app.source_analysis.errors import SourceMapValidationError
from app.source_analysis.models import (
    CONFIDENCE_LEVELS,
    EXAMPLE_KINDS,
    IDEA_KINDS,
    IMPORTANCE_LEVELS,
    REFERENCE_COMPLETENESS,
    REFERENCE_KINDS,
    RELATION_KINDS,
    REPETITION_CHARACTERS,
    SEVERITY_LEVELS,
    SOURCE_MAP_SCHEMA_VERSION,
    UNCERTAINTY_KINDS,
    AnalysisProvenance,
)
from app.source_analysis.preflight import GenerateGuard, run_source_analyzer_preflight
from app.source_analysis.prompt import (
    SOURCE_ANALYZER_PROMPT_VERSION,
    build_system_prompt,
    build_user_prompt,
)
from app.source_analysis.protected import snapshot_protected
from app.source_analysis.schema import schema_fingerprint
from app.source_analysis.schema_complexity import analyze_schema_complexity
from app.source_analysis.semantic_transport_decoder import (
    decode_source_map,
    decode_to_canonical_raw,
)
from app.source_analysis.transcript_input import (
    TranscriptInputMode,
    load_transcript_input,
    transcript_data_file,
)
from app.source_analysis.ultra_compact_schema import (
    ALLOWED_RECORD_KINDS,
    VOICE_FIELDS,
    build_ultra_compact_response_schema,
    ultra_compact_schema_fingerprint,
)
from app.source_analysis.validator import ensure_valid_source_map, validate_source_map
from app.source_analysis.vocabulary_audit import (
    AUDIT_ARTIFACT_NAME,
    VOCABULARY_PROMPT_SERVER_COMPLIANCE,
    extra_protected_snapshot,
    build_vocabulary_contract_audit,
    write_vocabulary_contract_audit,
)
from app.source_analysis.vocabulary_fixtures import (
    build_golden_full_vocabulary_transport,
    build_observed_3b43_invalid_transport,
    build_remaining_confidence_transport,
    exercised_controlled_values,
    inject_invalid_token,
    load_historical_3b43_transport,
)
from app.source_analysis.writer import transcripts_dir
from app.tests.source_analysis_fixtures import (  # noqa: F401
    analysis_env,
    fake_engine,
)

_PROVENANCE = AnalysisProvenance(
    prompt_version=SOURCE_ANALYZER_PROMPT_VERSION,
    schema_version=SOURCE_MAP_SCHEMA_VERSION,
    provider="fake",
    model="fake-model",
    strategy="global",
    signature="sig-vocab",
)

INVALID_MATRIX = (
    ("record.kind", "idea"),
    ("record.kind", "CHAPTER"),
    ("idea.kind", "assertion"),
    ("idea.kind", "Claim"),
    ("idea.kind", "claims"),
    ("idea.importance", "crucial"),
    ("idea.importance", "Central"),
    ("relation.type", "contradicts"),
    ("relation.type", "supports-with"),
    ("example.kind", "story"),
    ("reference.kind", "bible"),
    ("reference.completeness", "incomplete"),
    ("uncertainty.kind", "transcription_artifact"),
    ("uncertainty.kind", "Ambiguous_transcription"),
    ("uncertainty.kind", "ambiguous-transcription"),
    ("uncertainty.kind", "transcription ambigue"),
    ("uncertainty.kind", "pensée_interrompue"),
    ("uncertainty.kind", "unknown_kind"),
    ("uncertainty.severity", "critical"),
    ("repetition.character", "rhetorical_device"),
    ("voice.field", "mood"),
    ("voice.field", "Tone"),
    ("confidence", "High"),
    ("confidence", "très_élevé"),
)


def _transcript(env):
    return load_transcript_input(
        transcript_data_file(env.transcripts_dir),
        project_name=env.project_name,
    )


def _src_ids(env) -> list[str]:
    return list(_transcript(env).src_ids())


class TestVocabularyInventory:
    def test_category_order_is_explicit(self):
        assert VOCABULARY_CATEGORY_ORDER == (
            "record.kind",
            "idea.kind",
            "idea.importance",
            "relation.type",
            "example.kind",
            "reference.kind",
            "reference.completeness",
            "uncertainty.kind",
            "uncertainty.severity",
            "repetition.character",
            "voice.field",
            "confidence",
        )

    def test_sources_of_truth_are_canonical_modules(self):
        sources = vocabulary_sources()
        assert sources["record.kind"].endswith("ALLOWED_RECORD_KINDS")
        assert sources["idea.kind"].endswith("IDEA_KINDS")
        assert sources["uncertainty.kind"].endswith("UNCERTAINTY_KINDS")
        assert sources["voice.field"].endswith("VOICE_FIELDS")

    def test_record_kinds_from_code(self):
        assert prompt_controlled_vocabulary()["record.kind"] == ALLOWED_RECORD_KINDS

    def test_idea_kinds_from_code(self):
        assert prompt_controlled_vocabulary()["idea.kind"] == IDEA_KINDS

    def test_importance_from_code(self):
        assert prompt_controlled_vocabulary()["idea.importance"] == IMPORTANCE_LEVELS

    def test_relation_types_from_code(self):
        assert prompt_controlled_vocabulary()["relation.type"] == RELATION_KINDS

    def test_uncertainty_kinds_from_code(self):
        assert prompt_controlled_vocabulary()["uncertainty.kind"] == UNCERTAINTY_KINDS
        assert "ambiguous_transcription" in UNCERTAINTY_KINDS
        assert "incomplete_reference" in UNCERTAINTY_KINDS
        assert "interrupted_thought" in UNCERTAINTY_KINDS

    def test_intent_and_audience_are_free_text(self):
        assert intent_audience_kinds_are_free_text() is True
        advertised = prompt_controlled_vocabulary()
        assert "intent.kind" not in advertised
        assert "audience.kind" not in advertised

    def test_repetition_and_voice_and_other_metadata(self):
        advertised = prompt_controlled_vocabulary()
        assert advertised["repetition.character"] == REPETITION_CHARACTERS
        assert advertised["voice.field"] == VOICE_FIELDS
        assert advertised["example.kind"] == EXAMPLE_KINDS
        assert advertised["reference.kind"] == REFERENCE_KINDS
        assert advertised["reference.completeness"] == REFERENCE_COMPLETENESS
        assert advertised["uncertainty.severity"] == SEVERITY_LEVELS
        assert advertised["confidence"] == CONFIDENCE_LEVELS


class TestPromptVocabularyGeneration:
    def test_deterministic_byte_identical(self):
        assert build_canonical_vocabulary_contract() == build_canonical_vocabulary_contract()
        assert build_record_field_contract() == build_record_field_contract()

    def test_no_python_set_order(self):
        first = extract_prompt_controlled_vocabularies(build_canonical_vocabulary_contract())
        second = extract_prompt_controlled_vocabularies(build_canonical_vocabulary_contract())
        assert list(first) == list(VOCABULARY_CATEGORY_ORDER)
        assert list(second) == list(VOCABULARY_CATEGORY_ORDER)
        for key in VOCABULARY_CATEGORY_ORDER:
            assert first[key] == second[key]
            assert first[key] == canonical_allowed_vocabulary()[key]

    def test_exact_token_rule_present(self):
        block = build_canonical_vocabulary_contract()
        assert "JETONS DE PROTOCOLE" in block
        assert "n'invente aucun synonyme" in block
        assert "ne le traduis pas" in block
        assert "ne le paraphrase pas" in block
        assert "ne remplace pas les underscores" in block

    def test_free_text_vs_controlled_distinction(self):
        block = build_canonical_vocabulary_contract()
        assert "TEXTE LIBRE" in block
        assert "INTENT_KIND.v" in block
        assert "theme" in block

    def test_fallback_documented_for_every_vocabulary(self):
        block = build_canonical_vocabulary_contract()
        for key, fallback in vocabulary_fallbacks().items():
            assert f"{key}:" in block
            assert fallback in block

    def test_observed_examples_point_to_canonical_tokens(self):
        block = build_canonical_vocabulary_contract()
        for wrong, valid in EXACT_IDENTIFIER_EXAMPLES:
            assert f'WRONG: "{wrong}"' in block
            assert f'VALID IDENTIFIER: "{valid}"' in block
            assert valid in UNCERTAINTY_KINDS
            assert wrong not in UNCERTAINTY_KINDS

    def test_system_prompt_contains_vocabulary_contract(self):
        prompt = build_system_prompt("en")
        advertised = extract_prompt_controlled_vocabularies(prompt)
        assert advertised == prompt_controlled_vocabulary()
        assert "ambiguous_transcription" in prompt
        assert "incomplete_reference" in prompt
        assert "interrupted_thought" in prompt

    def test_user_prompt_documents_record_fields(self, analysis_env):
        prompt = build_user_prompt(_transcript(analysis_env))
        for row in record_field_contract():
            assert row["kind"] in prompt
        assert "N'émets aucun identifiant métier" in prompt


class TestPromptDecoderParity:
    def test_overall_parity(self):
        assert prompt_controlled_vocabulary() == canonical_allowed_vocabulary()
        parity = prompt_decoder_parity()
        for key, row in parity.items():
            assert row["missing_from_prompt"] == [], key
            assert row["extra_in_prompt"] == [], key

    @pytest.mark.parametrize("key", list(VOCABULARY_CATEGORY_ORDER))
    def test_each_vocabulary_parity(self, key):
        row = prompt_decoder_parity()[key]
        assert row["prompt_values"] == row["decoder_values"]
        assert row["missing_from_prompt"] == []
        assert row["extra_in_prompt"] == []


class TestObserved3B43:
    def test_invalid_tokens_still_rejected(self, analysis_env):
        payload = build_observed_3b43_invalid_transport(_src_ids(analysis_env)[0])
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(
                payload,
                allowed_source_refs=set(_src_ids(analysis_env)),
            )
        joined = " ".join(excinfo.value.errors)
        for token in OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS:
            assert token in joined

    def test_no_synonym_repair(self, analysis_env):
        payload = build_observed_3b43_invalid_transport(_src_ids(analysis_env)[0])
        with pytest.raises(SourceMapValidationError):
            decode_to_canonical_raw(
                payload,
                allowed_source_refs=set(_src_ids(analysis_env)),
            )

    def test_canonical_counterparts_accepted(self, analysis_env):
        payload = build_observed_3b43_invalid_transport(_src_ids(analysis_env)[0])
        mapping = dict(EXACT_IDENTIFIER_EXAMPLES)
        for record in payload["records"]:
            if record["k"] == "UNCERTAINTY":
                record["m"][0] = mapping[record["m"][0]]
        raw = decode_to_canonical_raw(
            payload,
            allowed_source_refs=set(_src_ids(analysis_env)),
        )
        kinds = [item["kind"] for item in raw["uncertainties"]]
        assert kinds == [
            "ambiguous_transcription",
            "incomplete_reference",
            "interrupted_thought",
        ]

    def test_historical_3b43_transport_still_rejected(self):
        historical = load_historical_3b43_transport("pastoral_retreat_v2_validation")
        if historical is None:
            pytest.skip("artefact historique 3B.4.3 absent")
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(historical)
        joined = " ".join(excinfo.value.errors)
        for token in OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS:
            assert token in joined
        assert "transcription_artifact" in json.dumps(historical, ensure_ascii=False)


class TestNegativeVariants:
    @pytest.mark.parametrize("vocab_key,invalid", INVALID_MATRIX)
    def test_invalid_variant_rejected(self, analysis_env, vocab_key, invalid):
        golden = build_golden_full_vocabulary_transport(_src_ids(analysis_env))
        payload = inject_invalid_token(golden, vocab_key=vocab_key, invalid_value=invalid)
        with pytest.raises(SourceMapValidationError):
            decode_to_canonical_raw(
                payload,
                allowed_source_refs=set(_src_ids(analysis_env)),
            )

    def test_unknown_record_kind_fails(self, analysis_env):
        payload = build_golden_full_vocabulary_transport(_src_ids(analysis_env))
        payload["records"][2]["k"] = "UNKNOWN_KIND"
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(payload)
        assert any("kind inconnu" in error for error in excinfo.value.errors)

    def test_unknown_metadata_token_fails(self, analysis_env):
        payload = build_golden_full_vocabulary_transport(_src_ids(analysis_env))
        for record in payload["records"]:
            if record["k"] == "IDEA":
                record["m"][0] = "not_a_kind"
                break
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(payload)
        assert any("idea kind invalide" in error for error in excinfo.value.errors)

    def test_case_sensitive_record_kind(self, analysis_env):
        payload = build_golden_full_vocabulary_transport(_src_ids(analysis_env))
        payload["records"][2]["k"] = "topic"
        with pytest.raises(SourceMapValidationError):
            decode_to_canonical_raw(payload)

    def test_underscore_required(self, analysis_env):
        payload = build_golden_full_vocabulary_transport(_src_ids(analysis_env))
        payload = inject_invalid_token(
            payload,
            vocab_key="uncertainty.kind",
            invalid_value="ambiguous transcription",
        )
        with pytest.raises(SourceMapValidationError):
            decode_to_canonical_raw(
                payload,
                allowed_source_refs=set(_src_ids(analysis_env)),
            )


class TestGoldenAndCoverage:
    def test_golden_decoder_normalizer_validator(self, analysis_env):
        transcript = _transcript(analysis_env)
        payload = build_golden_full_vocabulary_transport(list(transcript.src_ids()))
        raw = decode_to_canonical_raw(
            payload,
            allowed_source_refs=set(transcript.src_ids()),
        )
        assert raw["source_analysis"]["main_theme"]
        source_map = decode_source_map(
            payload,
            transcript,
            provenance=_PROVENANCE,
        )
        assert validate_source_map(source_map, transcript) == []
        ensure_valid_source_map(source_map, transcript)

    def test_remaining_confidence_fixture(self, analysis_env):
        transcript = _transcript(analysis_env)
        payload = build_remaining_confidence_transport(list(transcript.src_ids()))
        source_map = decode_source_map(
            payload,
            transcript,
            provenance=_PROVENANCE,
        )
        assert source_map.source_analysis.author_intent.confidence == "low"
        assert validate_source_map(source_map, transcript) == []

    def test_vocabulary_coverage_complete(self, analysis_env):
        srcs = _src_ids(analysis_env)
        golden = build_golden_full_vocabulary_transport(srcs)
        remaining = build_remaining_confidence_transport(srcs)
        tested = exercised_controlled_values(golden) | exercised_controlled_values(remaining)
        expected = set(all_controlled_values())
        assert expected <= tested
        assert controlled_value_count() == len(expected)
        percent = round(100.0 * len(expected & tested) / len(expected), 2)
        assert percent == 100.0


class TestGenerationCUnchanged:
    def test_raw_and_anthropic_sha_unchanged(self):
        raw = build_ultra_compact_response_schema()
        adapted = prepare_anthropic_json_schema(raw)
        assert ultra_compact_schema_fingerprint(raw) == GENERATION_C_RAW_SHA256_3B43
        assert schema_fingerprint(adapted) == GENERATION_C_ANTHROPIC_SHA256_3B43
        assert raw == build_ultra_compact_response_schema()
        assert adapted == prepare_anthropic_json_schema(build_ultra_compact_response_schema())

    def test_metrics_and_zero_enums(self):
        raw = build_ultra_compact_response_schema()
        adapted = prepare_anthropic_json_schema(raw)
        metrics = analyze_schema_complexity(raw)
        adapted_metrics = analyze_schema_complexity(adapted)
        assert metrics["serialized_json_bytes"] == 559
        assert adapted_metrics["serialized_json_bytes"] == 621
        assert metrics["object_nodes"] == 2
        assert metrics["arrays_of_objects"] == 1
        assert metrics["total_properties"] == 11
        assert metrics["constraints"] == 0
        assert metrics["enum_count"] == 0
        assert metrics["total_enum_values"] == 0
        assert adapted_metrics["enum_count"] == 0

    def test_no_enums_reintroduced(self):
        serialized = json.dumps(build_ultra_compact_response_schema())
        assert '"enum"' not in serialized


class TestPromptVersionSignatureCache:
    def test_prompt_version_changed(self):
        assert PREVIOUS_PROMPT_VERSION == "1.2"
        assert CURRENT_PROMPT_VERSION == "1.3"
        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"

    def test_prompt_sha_changed(self, analysis_env):
        transcript = _transcript(analysis_env)
        current = prompt_fingerprint(
            build_system_prompt(transcript.primary_language),
            build_user_prompt(transcript),
        )
        assert current != PREVIOUS_PROMPT_SHA256
        assert len(current) == 64

    def test_signature_changed_and_old_cache_cannot_collide(self, analysis_env):
        transcript = _transcript(analysis_env)
        current_prompt = prompt_fingerprint(
            build_system_prompt(transcript.primary_language),
            build_user_prompt(transcript),
        )
        shared = dict(
            transcript_sha256="a" * 64,
            transcript_id="TR001",
            schema_version="1.0",
            response_schema_sha256=ultra_compact_schema_fingerprint(),
            provider="anthropic",
            model="claude-sonnet-5",
            temperature=None,
            max_output_tokens=None,
            context_safety_ratio=0.70,
            output_language="en",
        )
        old = build_signature(
            SignatureInputs(
                **shared,
                prompt_version="1.2",
                prompt_sha256=PREVIOUS_PROMPT_SHA256,
            )
        )
        new = build_signature(
            SignatureInputs(
                **shared,
                prompt_version="1.3",
                prompt_sha256=current_prompt,
            )
        )
        assert old != new
        assert new != PREVIOUS_SIGNATURE
        assert is_cache_valid(
            signature=new,
            state_block={"status": "completed", "signature": old},
            published_payload={"analysis": {"signature": old}},
        ) is False


class TestFutureRequestAndPayload:
    def test_future_airequest_uses_generation_c_and_new_prompt(
        self, analysis_env, no_ai_network
    ):
        guard = GenerateGuard()
        result = run_source_analyzer_preflight(
            transcript_data_file(analysis_env.transcripts_dir),
            project_name=analysis_env.project_name,
            engine=guard,
        )
        assert guard.calls == 0
        assert result.generate_calls == 0
        assert result.request.response_schema == build_ultra_compact_response_schema()
        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"
        assert "CONTROLLED_VOCABULARY_BEGIN" in result.request.system_prompt
        assert result.plan.strategy == "global"

    def test_future_payload_still_json_schema_generation_c(self, analysis_env):
        request = AIRequest(
            prompt="x",
            system_prompt=build_system_prompt("en"),
            model="claude-sonnet-5",
            response_schema=build_ultra_compact_response_schema(),
        )
        payload = AnthropicEngine(model="claude-sonnet-5", api_key="test").build_payload(
            request, "claude-sonnet-5"
        )
        sent = payload["output_config"]["format"]["schema"]
        assert payload["output_config"]["format"]["type"] == "json_schema"
        assert sent == prepare_anthropic_json_schema(build_ultra_compact_response_schema())
        assert analyze_schema_complexity(sent)["enum_count"] == 0


class TestCleanDerivedPreflight:
    def test_clean_derived_preflight_budget(self, no_ai_network):
        project = "pastoral_retreat_v2_validation"
        guard = GenerateGuard()
        result = run_source_analyzer_preflight(
            clean_json_path(project),
            project_name=project,
            mode=TranscriptInputMode.DERIVED,
            provenance_path=audit_path(project),
            original_transcript_path=transcripts_dir(project) / "transcript_data.json",
            engine=guard,
            write_artifact_to=None,
        )
        assert guard.calls == 0
        assert result.generate_calls == 0
        assert result.transcript.segment_count == 8298
        assert result.transcript.word_count == 38313
        assert result.transcript.duration_seconds == 19954.601
        assert result.plan.provider == "anthropic"
        assert result.plan.model == "claude-sonnet-5"
        assert result.plan.strategy == "global"
        assert result.request.response_schema == build_ultra_compact_response_schema()
        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"
        current = prompt_fingerprint(result.request.system_prompt, result.request.prompt)
        assert current != PREVIOUS_PROMPT_SHA256
        assert result.signature != PREVIOUS_SIGNATURE
        assert result.remaining_margin > 0

    def test_vocabulary_block_size_reported(self):
        block = build_canonical_vocabulary_contract()
        tokens = estimate_tokens(block, model="claude-sonnet-5").tokens
        assert len(block) > 0
        assert tokens > 0


class TestDiagnosticAndProtected:
    def test_diagnostic_deterministic(self, tmp_path):
        first = tmp_path / "a" / AUDIT_ARTIFACT_NAME
        second = tmp_path / "b" / AUDIT_ARTIFACT_NAME
        payload = build_vocabulary_contract_audit(
            golden_status="PASS",
            observed_rejected=True,
            generate_calls=0,
        )
        write_vocabulary_contract_audit(first, payload)
        write_vocabulary_contract_audit(second, payload)
        assert first.read_bytes() == second.read_bytes()
        loaded = json.loads(first.read_text(encoding="utf-8"))
        assert loaded["vocabulary_prompt_server_compliance"] == VOCABULARY_PROMPT_SERVER_COMPLIANCE
        assert loaded["network_calls"] == 0
        assert loaded["engine_generate"] == 0
        assert "generated_at" not in loaded
        assert loaded["generation_c"]["server_acceptance"] == "PREVIOUSLY_VERIFIED"
        assert loaded["parity"]["missing_from_prompt"] == []
        assert loaded["parity"]["extra_in_prompt"] == []

    def test_protected_artifacts_unchanged(self):
        before = snapshot_protected("pastoral_retreat_v2_validation", require_all=False)
        extra_before = extra_protected_snapshot("pastoral_retreat_v2_validation")
        after = snapshot_protected("pastoral_retreat_v2_validation", require_all=False)
        extra_after = extra_protected_snapshot("pastoral_retreat_v2_validation")
        assert before.hashes == after.hashes
        assert extra_before == extra_after

    def test_canonical_contract_not_weakened(self, analysis_env):
        transcript = _transcript(analysis_env)
        payload = build_golden_full_vocabulary_transport(list(transcript.src_ids()))
        source_map = decode_source_map(payload, transcript, provenance=_PROVENANCE)
        assert validate_source_map(source_map, transcript) == []
        bad = deepcopy(payload)
        for record in bad["records"]:
            if record["k"] == "UNCERTAINTY":
                record["m"][0] = "transcription_artifact"
                break
        with pytest.raises(SourceMapValidationError):
            decode_to_canonical_raw(bad, allowed_source_refs=set(transcript.src_ids()))
