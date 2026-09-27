"""
Phase 3B.4.2 — transport sémantique ultra-compact.

Aucun réseau, aucun engine.generate() vers un fournisseur réel.
"""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from app.ai.contracts import AIRequest
from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.source_analysis.analyzer import analyze_source
from app.source_analysis.cache import SignatureInputs, build_signature
from app.source_analysis.compact_reconstructor import reconstruct_source_map
from app.source_analysis.compact_schema import (
    build_compact_response_schema,
    compact_schema_fingerprint,
)
from app.source_analysis.errors import (
    SourceMapEditorialLeakError,
    SourceMapValidationError,
)
from app.source_analysis.models import AnalysisProvenance, SOURCE_MAP_SCHEMA_VERSION
from app.source_analysis.preflight import GenerateGuard, run_source_analyzer_preflight
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION, build_user_prompt
from app.source_analysis.schema import build_response_schema, schema_fingerprint
from app.source_analysis.schema_complexity import analyze_schema_complexity
from app.source_analysis.semantic_equivalence import (
    compare_semantic_source_maps,
    source_maps_semantically_equal,
)
from app.source_analysis.semantic_transport_decoder import (
    decode_source_map,
    decode_to_canonical_raw,
)
from app.source_analysis.transcript_input import (
    TranscriptInputMode,
    load_transcript_input,
    transcript_data_file,
)
from app.source_analysis.ultra_compact_audit import (
    AUDIT_ARTIFACT_NAME,
    SERVER_ACCEPTANCE,
    build_ultra_compact_schema_audit,
    write_ultra_compact_schema_audit,
)
from app.source_analysis.ultra_compact_schema import (
    ALLOWED_RECORD_KINDS,
    KIND_EXAMPLE,
    KIND_IDEA,
    KIND_RELATION,
    KIND_REPETITION,
    KIND_TOPIC,
    SEMANTIC_TRANSPORT_VERSION,
    ULTRA_INSTANCE_MAX_DEPTH,
    ULTRA_RECORD_FIELDS,
    ULTRA_ROOT_FIELDS,
    build_ultra_compact_response_schema,
    looks_like_ultra_transport,
    to_ultra_transport_payload,
    ultra_compact_schema_fingerprint,
)
from app.source_analysis.validator import (
    ensure_valid_source_map,
    validate_source_map,
)
from app.source_analysis_schema_canary.architecture import count_recursive_refs
from app.tests.source_analysis_fixtures import (  # noqa: F401
    analysis_env,
    fake_compact_analysis_payload,
    fake_engine,
    fake_ultra_analysis_payload,
)
from app.tests.test_source_analysis_compact_schema import compact_fixture
from app.tests.test_source_analysis_derived_pipeline import _sparse_env

_PROVENANCE = AnalysisProvenance(
    prompt_version=SOURCE_ANALYZER_PROMPT_VERSION,
    schema_version=SOURCE_MAP_SCHEMA_VERSION,
    provider="fake",
    model="fake-model",
    strategy="global",
    signature="sig-ultra",
)


def _transcript(env):
    return load_transcript_input(
        transcript_data_file(env.transcripts_dir),
        project_name=env.project_name,
    )


def _record(kind, value, source_refs=None, links=None, metadata=None):
    return {
        "k": kind,
        "v": value,
        "s": list(source_refs or []),
        "l": list(links or []),
        "m": list(metadata or []),
    }


def golden_rich_ultra() -> dict:
    """Fixture riche : 2 topics, 4 ideas, relations, example, ref, unc, rep, voice."""
    return {
        "theme": "Le rôle de la foi dans la manière de traverser les épreuves",
        "intent": "Enseigner ce que la foi change dans l'épreuve.",
        "ic": "high",
        "aud": "Audience croyante intéressée par la foi.",
        "ac": "medium",
        "records": [
            _record("INTENT_KIND", "enseigner"),
            _record("AUDIENCE_KIND", "croyants"),
            _record("TOPIC", "Foi dans l'épreuve", ["SRC000001"], [], ["Ce que la foi modifie."]),
            _record(
                "TOPIC",
                "Confiance révélée",
                ["SRC000003"],
                [],
                ["L'épreuve révèle une confiance déjà là."],
            ),
            _record("IDEA", "La foi change la traversée.", ["SRC000001"], [2], ["claim", "central"]),
            _record(
                "IDEA",
                "L'épreuve révèle la confiance.",
                ["SRC000003"],
                [2, 3],
                ["explanation", "supporting"],
            ),
            _record(
                "IDEA",
                "Avancer malgré tout.",
                ["SRC000007"],
                [3],
                ["instruction", "supporting"],
            ),
            _record(
                "IDEA",
                "Que reste-t-il debout ?",
                ["SRC000001"],
                [2],
                ["question", "minor"],
            ),
            _record("RELATION", "supports", [], [5, 4], []),
            _record("RELATION", "develops", [], [6, 5], []),
            _record(
                "EXAMPLE",
                "Un homme qui priait encore chaque matin.",
                ["SRC000003"],
                [4],
                ["anecdote"],
            ),
            _record(
                "REFERENCE",
                "Paul dit quelque part",
                ["SRC000001"],
                [],
                ["biblical", "vague", ""],
            ),
            _record(
                "UNCERTAINTY",
                "La référence paulinienne n'est pas située.",
                ["SRC000001"],
                [],
                ["incomplete_reference", "medium"],
            ),
            _record(
                "REPETITION",
                "Affirmation puis développement.",
                ["SRC000001", "SRC000003"],
                [4, 5],
                ["development"],
            ),
            _record("VOICE", "didactique", [], [], ["tone"]),
            _record("VOICE", "oral accessible", [], [], ["register"]),
            _record("VOICE", "phrases courtes", [], [], ["sentence_style"]),
            _record("VOICE", "opposition", [], [], ["rhetorical_patterns"]),
            _record("VOICE", "rares", [], [], ["use_of_questions"]),
            _record("VOICE", "formules centrales", [], [], ["use_of_repetition"]),
            _record("VOICE", "anecdotes", [], [], ["use_of_examples"]),
            _record("VOICE", "vous", [], [], ["direct_address"]),
            _record("VOICE", "affirmation puis illustration", [], [], ["teaching_style"]),
            _record("VOICE", "images concrètes", [], [], ["distinctive_traits"]),
        ],
    }


class TestSchemaGenerationAndMetrics:
    def test_schema_generation_deterministic(self):
        assert build_ultra_compact_response_schema() == build_ultra_compact_response_schema()
        assert ultra_compact_schema_fingerprint() == ultra_compact_schema_fingerprint()

    def test_schema_metrics_deterministic(self):
        schema = build_ultra_compact_response_schema()
        assert analyze_schema_complexity(schema) == analyze_schema_complexity(schema)

    def test_generation_abc_comparison(self):
        audit = build_ultra_compact_schema_audit()
        a = audit["generation_a"]["metrics"]
        b = audit["generation_b"]["metrics"]
        c = audit["generation_c"]["metrics"]
        assert a["serialized_json_bytes"] == 10492
        assert b["serialized_json_bytes"] == 4398
        assert c["serialized_json_bytes"] < 900
        assert c["object_nodes"] == 2
        assert c["enum_count"] == 0
        assert c["constraints"] == 0
        assert c["optional_properties"] == 0
        assert c["distinct_object_shapes"] == 2
        assert c["arrays_of_objects"] == 1
        assert c["nested_arrays"] == 0
        assert c["ref_count"] == 0
        assert c["union_count"] == 0
        assert audit["reductions"]["b_to_c"]["serialized_json_bytes"] > 70
        assert audit["reductions"]["a_to_c"]["serialized_json_bytes"] > 90

    def test_ultra_root_and_record_shape(self):
        schema = build_ultra_compact_response_schema()
        assert schema["required"] == list(ULTRA_ROOT_FIELDS)
        assert set(schema["properties"]) == set(ULTRA_ROOT_FIELDS)
        record = schema["properties"]["records"]["items"]
        assert record["required"] == list(ULTRA_RECORD_FIELDS)
        assert set(record["properties"]) == set(ULTRA_RECORD_FIELDS)

    def test_zero_provider_enums_and_low_nesting(self):
        schema = build_ultra_compact_response_schema()
        metrics = analyze_schema_complexity(schema)
        assert metrics["enum_count"] == 0
        assert metrics["total_enum_values"] == 0
        assert ULTRA_INSTANCE_MAX_DEPTH == 3
        assert looks_like_ultra_transport({"theme": "", "records": []})

    def test_semantic_kinds_listed(self):
        assert ALLOWED_RECORD_KINDS == (
            "TOPIC",
            "IDEA",
            "RELATION",
            "EXAMPLE",
            "REFERENCE",
            "UNCERTAINTY",
            "REPETITION",
            "VOICE",
            "INTENT_KIND",
            "AUDIENCE_KIND",
        )


class TestDecoderHappyPath:
    def test_golden_rich_fixture(self, analysis_env):
        transcript, _, _ = _sparse_env(analysis_env)
        source_map = decode_source_map(
            golden_rich_ultra(), transcript, provenance=_PROVENANCE
        )
        ensure_valid_source_map(source_map, transcript)
        assert source_map.source_analysis.main_theme.startswith("Le rôle de la foi")
        assert source_map.source_analysis.author_intent.kinds == ("enseigner",)
        assert source_map.source_analysis.target_audience.kinds == ("croyants",)
        assert [topic.topic_id for topic in source_map.topics] == ["TOP001", "TOP002"]
        assert [idea.idea_id for idea in source_map.ideas] == [
            "IDEA001",
            "IDEA002",
            "IDEA003",
            "IDEA004",
        ]
        assert {idea.kind for idea in source_map.ideas} >= {
            "claim",
            "explanation",
            "instruction",
            "question",
        }
        assert {idea.importance for idea in source_map.ideas} >= {
            "central",
            "supporting",
            "minor",
        }
        assert source_map.examples[0].example_id == "EX001"
        assert source_map.references[0].reference_id == "REF001"
        assert source_map.uncertainties[0].uncertainty_id == "UNC001"
        assert source_map.repetitions[0].repetition_id == "REP001"
        assert source_map.author_voice_profile.tone == ("didactique",)
        assert source_map.stats.idea_count == 4
        assert source_map.stats.source_segment_count == 3

    def test_semantic_equivalence_3b4_vs_3b42(self, analysis_env):
        transcript = _transcript(analysis_env)
        compact = fake_compact_analysis_payload()
        ultra = to_ultra_transport_payload(compact)
        left = reconstruct_source_map(compact, transcript, provenance=_PROVENANCE)
        right = decode_source_map(ultra, transcript, provenance=_PROVENANCE)
        assert source_maps_semantically_equal(left, right)
        assert compare_semantic_source_maps(left, right) == []

    def test_empty_collections_not_invented(self, analysis_env):
        compact = compact_fixture("A")
        ultra = to_ultra_transport_payload(compact)
        source_map = decode_source_map(ultra, _transcript(analysis_env), provenance=_PROVENANCE)
        assert source_map.examples == ()
        assert source_map.references == ()
        assert source_map.uncertainties == ()
        assert source_map.repetitions == ()

    def test_canonical_ids_and_ordering(self, analysis_env):
        compact = compact_fixture("C")
        compact["ideas"] = list(reversed(compact["ideas"]))
        source_map = decode_source_map(
            to_ultra_transport_payload(compact),
            _transcript(analysis_env),
            provenance=_PROVENANCE,
        )
        assert source_map.ideas[0].source_refs[0] == "SRC000001"
        assert source_map.ideas[0].idea_id == "IDEA001"

    def test_relations_reconstructed(self, analysis_env):
        source_map = decode_source_map(
            to_ultra_transport_payload(compact_fixture("D")),
            _transcript(analysis_env),
            provenance=_PROVENANCE,
        )
        assert source_map.ideas[1].relations[0].to_idea == "IDEA001"
        assert source_map.ideas[1].relations[0].relation == "supports"


class TestDecoderNegative:
    def test_unknown_kind_fails(self):
        payload = golden_rich_ultra()
        payload["records"][2]["k"] = "CHAPTER"
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(payload)
        assert any("kind inconnu" in error for error in excinfo.value.errors)

    def test_empty_required_value_fails(self):
        payload = golden_rich_ultra()
        payload["theme"] = ""
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(payload)
        assert any("theme vide" in error for error in excinfo.value.errors)

    def test_malformed_kind_fails(self):
        payload = golden_rich_ultra()
        payload["records"][2]["k"] = "topic"
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(payload)
        assert any("kind inconnu" in error for error in excinfo.value.errors)

    def test_negative_link_fails(self):
        payload = golden_rich_ultra()
        for record in payload["records"]:
            if record["k"] == KIND_IDEA:
                record["l"] = [-1]
                break
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(payload)
        assert any("hors plage" in error for error in excinfo.value.errors)

    def test_out_of_range_link_fails(self):
        payload = golden_rich_ultra()
        for record in payload["records"]:
            if record["k"] == KIND_IDEA:
                record["l"] = [999]
                break
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(payload)
        assert any("hors plage" in error for error in excinfo.value.errors)

    def test_self_link_fails(self):
        payload = golden_rich_ultra()
        for record in payload["records"]:
            if record["k"] == KIND_RELATION:
                idea_index = next(
                    i for i, item in enumerate(payload["records"]) if item["k"] == KIND_IDEA
                )
                record["l"] = [idea_index, idea_index]
                break
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(payload)
        assert any("auto-lien" in error for error in excinfo.value.errors)

    def test_example_linking_topic_fails(self):
        payload = golden_rich_ultra()
        topic_index = next(
            i for i, item in enumerate(payload["records"]) if item["k"] == KIND_TOPIC
        )
        for record in payload["records"]:
            if record["k"] == KIND_EXAMPLE:
                record["l"] = [topic_index]
                break
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(payload)
        assert any("EXAMPLE ne peut lier que IDEA" in error for error in excinfo.value.errors)

    def test_relation_missing_endpoints_fails(self):
        payload = golden_rich_ultra()
        for record in payload["records"]:
            if record["k"] == KIND_RELATION:
                record["l"] = [4]
                break
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(payload)
        assert any("l=[from, to]" in error for error in excinfo.value.errors)

    def test_repetition_linking_invalid_record_fails(self):
        payload = golden_rich_ultra()
        topic_index = next(
            i for i, item in enumerate(payload["records"]) if item["k"] == KIND_TOPIC
        )
        for record in payload["records"]:
            if record["k"] == KIND_REPETITION:
                record["l"] = [topic_index, topic_index + 1]
                break
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(payload)
        assert any("REPETITION ne peut lier que IDEA" in error for error in excinfo.value.errors)

    def test_sparse_src_pass_and_invalid_fail(self, analysis_env):
        transcript, _, _ = _sparse_env(analysis_env)
        allowed = set(transcript.src_ids())
        payload = golden_rich_ultra()
        decode_to_canonical_raw(payload, allowed_source_refs=allowed)
        bad = deepcopy(payload)
        bad["records"][2]["s"] = ["SRC000002"]
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(bad, allowed_source_refs=allowed)
        assert any("SRC000002" in error for error in excinfo.value.errors)
        worse = deepcopy(payload)
        worse["records"][2]["s"] = ["SRC999999"]
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(worse, allowed_source_refs=allowed)
        assert any("SRC999999" in error for error in excinfo.value.errors)

    def test_local_enum_validation(self):
        payload = golden_rich_ultra()
        for record in payload["records"]:
            if record["k"] == KIND_IDEA:
                record["m"] = ["brillante", "central"]
                break
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(payload)
        assert any("idea kind invalide" in error for error in excinfo.value.errors)

    def test_invalid_importance(self):
        payload = golden_rich_ultra()
        for record in payload["records"]:
            if record["k"] == KIND_IDEA:
                record["m"] = ["claim", "crucial"]
                break
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(payload)
        assert any("importance invalide" in error for error in excinfo.value.errors)

    def test_invalid_relation_type(self):
        payload = golden_rich_ultra()
        for record in payload["records"]:
            if record["k"] == KIND_RELATION:
                record["v"] = "contradicts"
                break
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(payload)
        assert any("relation type invalide" in error for error in excinfo.value.errors)

    def test_invalid_intent_kind(self):
        payload = golden_rich_ultra()
        payload["records"][0]["v"] = ""
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(payload)
        assert any("INTENT_KIND vide" in error for error in excinfo.value.errors)

    def test_invalid_audience_kind(self):
        payload = golden_rich_ultra()
        payload["records"][1]["v"] = ""
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(payload)
        assert any("AUDIENCE_KIND vide" in error for error in excinfo.value.errors)

    def test_confidence_boundaries(self, analysis_env):
        for value in ("high", "medium", "low"):
            payload = to_ultra_transport_payload(compact_fixture("A"))
            payload["ic"] = value
            decode_source_map(payload, _transcript(analysis_env), provenance=_PROVENANCE)

    def test_confidence_below_and_above_and_wrong_type(self):
        payload = golden_rich_ultra()
        payload["ic"] = "0.1"
        with pytest.raises(SourceMapValidationError):
            decode_to_canonical_raw(payload)
        payload = golden_rich_ultra()
        payload["ac"] = "absolute"
        with pytest.raises(SourceMapValidationError):
            decode_to_canonical_raw(payload)
        payload = golden_rich_ultra()
        payload["ic"] = 0.9
        with pytest.raises(SourceMapValidationError) as excinfo:
            decode_to_canonical_raw(payload)
        assert any("chaîne de confiance" in error for error in excinfo.value.errors)

    def test_completeness_unchanged(self, analysis_env):
        payload = to_ultra_transport_payload(compact_fixture("A"))
        payload["records"] = [
            record for record in payload["records"] if record["k"] != KIND_IDEA
        ]
        source_map = decode_source_map(
            payload, _transcript(analysis_env), provenance=_PROVENANCE
        )
        with pytest.raises(SourceMapValidationError) as excinfo:
            ensure_valid_source_map(source_map, _transcript(analysis_env))
        assert any("aucune idée" in error for error in excinfo.value.errors)

    def test_editorial_leakage_unchanged(self):
        payload = golden_rich_ultra()
        payload["chapters"] = []
        with pytest.raises(SourceMapEditorialLeakError) as excinfo:
            decode_to_canonical_raw(payload)
        assert "chapters" in excinfo.value.fields
        payload = golden_rich_ultra()
        payload["book_title"] = "Un livre"
        with pytest.raises(SourceMapEditorialLeakError):
            decode_to_canonical_raw(payload)
        payload = golden_rich_ultra()
        payload["editorial_plan"] = {}
        with pytest.raises(SourceMapEditorialLeakError):
            decode_to_canonical_raw(payload)


class TestAnthropicAndFutureRequest:
    def test_anthropic_adapter_and_compatibility(self):
        adapted = prepare_anthropic_json_schema(build_ultra_compact_response_schema())
        findings = audit_unsupported_features(adapted)
        assert findings["additionalProperties_not_false"] == []
        assert findings["minLength"] == []
        assert findings["unsupported_minItems"] == []
        assert findings["minimum"] == []
        assert findings["maximum"] == []
        assert findings["maxItems"] == []
        assert findings["maxLength"] == []
        assert findings["external_ref"] == []
        assert all(not values for values in findings.values())
        assert count_recursive_refs(adapted) == 0
        metrics = analyze_schema_complexity(adapted)
        assert metrics["additional_properties_keywords"] == metrics["object_nodes"] == 2

    def test_future_airequest_uses_generation_c(self, analysis_env, no_ai_network):
        engine = fake_engine()
        analyze_source(analysis_env.project_name, engine=engine)
        sent = engine.last_request.response_schema
        assert sent == build_ultra_compact_response_schema()
        assert sent != build_compact_response_schema()
        assert sent != build_response_schema()

    def test_old_schemas_not_sent_in_payload(self):
        request = AIRequest(
            prompt="x",
            model="claude-sonnet-5",
            response_schema=build_ultra_compact_response_schema(),
        )
        payload = AnthropicEngine(model="claude-sonnet-5", api_key="test").build_payload(
            request, "claude-sonnet-5"
        )
        sent = payload["output_config"]["format"]["schema"]
        assert payload["output_config"]["format"]["type"] == "json_schema"
        assert sent == prepare_anthropic_json_schema(build_ultra_compact_response_schema())
        assert sent != prepare_anthropic_json_schema(build_compact_response_schema())
        assert sent != prepare_anthropic_json_schema(build_response_schema())

    def test_prompt_and_signature_changed(self, analysis_env):
        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"
        assert SEMANTIC_TRANSPORT_VERSION == "semantic-transport-v1"
        prompt = build_user_prompt(_transcript(analysis_env))
        assert "semantic-transport-v1" in prompt
        assert "TOPIC" in prompt
        shared = dict(
            transcript_sha256="a" * 64,
            transcript_id="TR001",
            prompt_sha256="b" * 64,
            schema_version="1.0",
            provider="anthropic",
            model="claude-sonnet-5",
            temperature=None,
            max_output_tokens=None,
            context_safety_ratio=0.70,
            output_language="fr",
        )
        old = build_signature(
            SignatureInputs(
                **shared,
                prompt_version="1.2",
                response_schema_sha256=ultra_compact_schema_fingerprint(),
            )
        )
        new = build_signature(
            SignatureInputs(
                **shared,
                prompt_version="1.3",
                response_schema_sha256=ultra_compact_schema_fingerprint(),
            )
        )
        assert old != new

    def test_offline_preflight_uses_c(self, analysis_env):
        result = run_source_analyzer_preflight(
            transcript_data_file(analysis_env.transcripts_dir),
            project_name=analysis_env.project_name,
        )
        assert result.request.response_schema == build_ultra_compact_response_schema()
        assert result.plan.strategy == "global"
        assert result.generate_calls == 0

    def test_engine_generate_and_network_zero(self, analysis_env, no_ai_network):
        guard = GenerateGuard()
        result = run_source_analyzer_preflight(
            transcript_data_file(analysis_env.transcripts_dir),
            project_name=analysis_env.project_name,
            engine=guard,
        )
        assert guard.calls == 0
        assert result.generate_calls == 0

    def test_diagnostic_deterministic(self, tmp_path):
        first = tmp_path / "a" / AUDIT_ARTIFACT_NAME
        second = tmp_path / "b" / AUDIT_ARTIFACT_NAME
        write_ultra_compact_schema_audit(first)
        write_ultra_compact_schema_audit(second)
        assert first.read_bytes() == second.read_bytes()
        payload = json.loads(first.read_text(encoding="utf-8"))
        assert payload["future_server_acceptance"] == SERVER_ACCEPTANCE
        assert payload["network_calls"] == 0
        assert "generated_at" not in payload

    def test_protected_artifacts_unchanged(self):
        from app.source_analysis.protected import snapshot_protected
        from app.source_analysis.ultra_compact_report import extra_protected_snapshot

        before = snapshot_protected("pastoral_retreat_v2_validation", require_all=False)
        extra_before = extra_protected_snapshot("pastoral_retreat_v2_validation")
        after = snapshot_protected("pastoral_retreat_v2_validation", require_all=False)
        extra_after = extra_protected_snapshot("pastoral_retreat_v2_validation")
        assert before.hashes == after.hashes
        assert extra_before == extra_after

    def test_canonical_validator_unchanged(self, analysis_env):
        source_map = decode_source_map(
            to_ultra_transport_payload(compact_fixture("D")),
            _transcript(analysis_env),
            provenance=_PROVENANCE,
        )
        assert validate_source_map(source_map, _transcript(analysis_env)) == []
