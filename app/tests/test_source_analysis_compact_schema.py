"""
Phase 3B.4 — DTO compact Anthropic, reconstruction, métriques, préflight.

Aucun réseau, aucun engine.generate() vers un fournisseur réel.
"""

from __future__ import annotations

import json

import pytest

from app.ai.contracts import AIRequest
from app.ai.errors import AIStructuredOutputError
from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.structured import parse_structured_output
from app.source_analysis.analyzer import analyze_source
from app.source_analysis.cache import SignatureInputs, build_signature
from app.source_analysis.compact_audit import (
    AUDIT_ARTIFACT_NAME,
    SERVER_ACCEPTANCE,
    build_compact_schema_audit,
    write_compact_schema_audit,
)
from app.source_analysis.compact_reconstructor import (
    looks_like_canonical_raw,
    reconstruct_source_map,
    reconstruct_to_canonical_raw,
    to_compact_provider_payload,
)
from app.source_analysis.compact_schema import (
    COMPACT_ID_FIELDS_ABSENT,
    COMPACT_REQUIRED_FIELDS,
    FIELD_CLASSIFICATION,
    SEMANTIC_DIMENSIONS_PRESERVED,
    build_compact_response_schema,
    compact_schema_fingerprint,
)
from app.source_analysis.ultra_compact_schema import (
    build_ultra_compact_response_schema,
)
from app.source_analysis.errors import (
    SourceMapEditorialLeakError,
    SourceMapValidationError,
)
from app.source_analysis.models import (
    AnalysisProvenance,
    SOURCE_MAP_SCHEMA_VERSION,
    forbidden_editorial_fields,
)
from app.source_analysis.preflight import GenerateGuard, run_source_analyzer_preflight
from app.source_analysis.prompt import (
    FORBIDDEN_STRUCTURE_BLOCK,
    SOURCE_ANALYZER_PROMPT_VERSION,
    STRUCTURAL_VOCABULARY,
    build_system_prompt,
    build_user_prompt,
)
from app.source_analysis.schema import build_response_schema, schema_fingerprint
from app.source_analysis.schema_complexity import analyze_schema_complexity
from app.source_analysis.transcript_input import (
    TranscriptInputMode,
    load_transcript_input,
    transcript_data_file,
)
from app.source_analysis.validator import (
    ensure_valid_source_map,
    validate_source_map,
)
from app.tests.source_analysis_fixtures import (  # noqa: F401
    analysis_env,
    fake_analysis_payload,
    fake_compact_analysis_payload,
    fake_engine,
)

_PROVENANCE = AnalysisProvenance(
    prompt_version=SOURCE_ANALYZER_PROMPT_VERSION,
    schema_version=SOURCE_MAP_SCHEMA_VERSION,
    provider="fake",
    model="fake-model",
    strategy="global",
    signature="sig-compact",
)


def _transcript(env):
    return load_transcript_input(
        transcript_data_file(env.transcripts_dir),
        project_name=env.project_name,
    )


def _empty_voice():
    return {
        "tone": [],
        "register": "",
        "sentence_style": "",
        "rhetorical_patterns": [],
        "use_of_questions": "",
        "use_of_repetition": "",
        "use_of_examples": "",
        "direct_address": "",
        "teaching_style": "",
        "distinctive_traits": [],
    }


def _header(**overrides):
    base = {
        "main_theme": "Le rôle de la foi dans la manière de traverser les épreuves",
        "author_intent": {
            "summary": "Enseigner ce que la foi change dans l'épreuve.",
            "confidence": "high",
            "kinds": ["enseigner"],
        },
        "target_audience": {
            "summary": "Audience croyante intéressée par la foi.",
            "confidence": "medium",
            "kinds": [],
        },
    }
    base.update(overrides)
    return base


def compact_fixture(name: str) -> dict:
    """Fixtures A–J du protocole 3B.4."""
    voice = {
        "tone": ["didactique"],
        "register": "oral accessible",
        "sentence_style": "phrases courtes",
        "rhetorical_patterns": ["opposition"],
        "use_of_questions": "rares",
        "use_of_repetition": "formules centrales",
        "use_of_examples": "anecdotes",
        "direct_address": "vous",
        "teaching_style": "affirmation puis illustration",
        "distinctive_traits": ["images concrètes"],
    }

    simple = {
        "source_analysis": _header(),
        "topics": [
            {
                "label": "Foi dans l'épreuve",
                "summary": "Ce que la foi modifie dans une épreuve.",
                "source_refs": ["SRC000001"],
            }
        ],
        "ideas": [
            {
                "summary": "La foi change la manière de traverser l'épreuve.",
                "kind": "claim",
                "importance": "central",
                "topic_indexes": [0],
                "source_refs": ["SRC000001"],
            }
        ],
        "relations": [],
        "examples": [],
        "references": [],
        "uncertainties": [],
        "repetitions": [],
        "author_voice_profile": dict(voice),
    }

    if name == "A":
        return simple

    if name == "B":
        payload = json.loads(json.dumps(simple))
        payload["topics"].append(
            {
                "label": "Confiance révélée",
                "summary": "L'épreuve révèle une confiance déjà là.",
                "source_refs": ["SRC000004"],
            }
        )
        payload["ideas"][0]["topic_indexes"] = [0, 1]
        payload["ideas"][0]["source_refs"] = ["SRC000001", "SRC000004"]
        return payload

    if name == "C":
        payload = json.loads(json.dumps(simple))
        payload["ideas"].append(
            {
                "summary": "L'épreuve révèle la solidité d'une confiance.",
                "kind": "explanation",
                "importance": "supporting",
                "topic_indexes": [0],
                "source_refs": ["SRC000004"],
            }
        )
        return payload

    if name == "D":
        payload = compact_fixture("C")
        payload["relations"] = [{"from": 1, "to": 0, "relation": "supports"}]
        return payload

    if name == "E":
        payload = compact_fixture("C")
        payload["examples"] = [
            {
                "kind": "anecdote",
                "summary": "Un homme qui priait encore chaque matin.",
                "idea_indexes": [0, 1],
                "source_refs": ["SRC000003"],
            }
        ]
        return payload

    if name == "F":
        payload = compact_fixture("A")
        payload["references"] = [
            {
                "kind": "biblical",
                "raw_reference": "Paul dit quelque part",
                "normalized_reference": "",
                "completeness": "vague",
                "source_refs": ["SRC000002"],
            }
        ]
        return payload

    if name == "G":
        payload = compact_fixture("F")
        payload["uncertainties"] = [
            {
                "kind": "incomplete_reference",
                "description": "La référence paulinienne n'est pas située.",
                "severity": "medium",
                "source_refs": ["SRC000002"],
            }
        ]
        return payload

    if name == "H":
        payload = compact_fixture("C")
        payload["repetitions"] = [
            {
                "character": "development",
                "description": "Affirmation puis développement, pas un doublon.",
                "idea_indexes": [0, 1],
                "source_refs": ["SRC000002", "SRC000005"],
            }
        ]
        return payload

    if name == "I":
        payload = compact_fixture("A")
        payload["author_voice_profile"] = {
            "tone": ["didactique", "encourageant", "pastoral"],
            "register": "langue parlée accessible, sans jargon",
            "sentence_style": "phrases courtes, rythme oral, reprises",
            "rhetorical_patterns": [
                "reprise d'une formule pour insister",
                "opposition entre supprimer et traverser",
                "adresse directe à l'auditoire",
            ],
            "use_of_questions": "peu de questions, surtout des affirmations",
            "use_of_repetition": "reprise volontaire des formules centrales",
            "use_of_examples": "une anecdote vécue par idée principale",
            "direct_address": "s'adresse directement à l'auditoire au vous",
            "teaching_style": "affirmation puis illustration puis application",
            "distinctive_traits": [
                "images concrètes du quotidien",
                "vocabulaire de la marche et de la traversée",
            ],
        }
        return payload

    if name == "J":
        payload = compact_fixture("A")
        payload["topics"][0]["source_refs"] = ["SRC000001", "SRC000007"]
        payload["ideas"][0]["source_refs"] = ["SRC000001", "SRC000007"]
        return payload

    raise KeyError(name)


class TestSchemaMetricsDeterministic:
    def test_schema_metrics_deterministic(self):
        schema = build_compact_response_schema()
        assert analyze_schema_complexity(schema) == analyze_schema_complexity(schema)

    def test_old_schema_metrics(self):
        metrics = analyze_schema_complexity(build_response_schema())
        assert metrics["serialized_json_bytes"] > 0
        assert metrics["object_nodes"] >= 8
        assert metrics["optional_properties"] > 0

    def test_compact_schema_metrics(self):
        metrics = analyze_schema_complexity(build_compact_response_schema())
        assert metrics["optional_properties"] == 0
        assert metrics["id_pattern_like_structures"] == 0

    def test_anthropic_adapted_metrics(self):
        adapted = prepare_anthropic_json_schema(build_compact_response_schema())
        metrics = analyze_schema_complexity(adapted)
        assert metrics["additional_properties_keywords"] == metrics["object_nodes"]


class TestSemanticFieldClassification:
    def test_semantic_field_classification(self):
        classes = {row["classification"] for row in FIELD_CLASSIFICATION}
        assert classes == {
            "MODEL_SEMANTIC_REQUIRED",
            "MODEL_SEMANTIC_COMPACTABLE",
            "DETERMINISTIC_RECONSTRUCTABLE",
            "METADATA_LOCAL",
            "DERIVED_STATS",
        }

    def test_compact_required_fields(self):
        assert build_compact_response_schema()["required"] == list(
            COMPACT_REQUIRED_FIELDS
        )

    def test_canonical_metadata_local(self):
        local = [
            row["field"]
            for row in FIELD_CLASSIFICATION
            if row["classification"] == "METADATA_LOCAL"
        ]
        assert "analysis.signature" in local
        assert "transcript_id" in local

    def test_canonical_stats_derived(self):
        derived = [
            row["field"]
            for row in FIELD_CLASSIFICATION
            if row["classification"] == "DERIVED_STATS"
        ]
        assert derived == ["stats.*"]

    def test_canonical_ids_derived(self):
        derived = [
            row["field"]
            for row in FIELD_CLASSIFICATION
            if row["classification"] == "DETERMINISTIC_RECONSTRUCTABLE"
        ]
        assert "topics[].topic_id" in derived
        assert "ideas[].idea_id" in derived


class TestReconstructionCollections:
    def test_topic_reconstruction(self, analysis_env):
        source_map = reconstruct_source_map(
            compact_fixture("A"), _transcript(analysis_env), provenance=_PROVENANCE
        )
        assert source_map.topics[0].topic_id == "TOP001"
        assert source_map.topics[0].label == "Foi dans l'épreuve"

    def test_idea_reconstruction(self, analysis_env):
        source_map = reconstruct_source_map(
            compact_fixture("C"), _transcript(analysis_env), provenance=_PROVENANCE
        )
        assert [idea.idea_id for idea in source_map.ideas] == ["IDEA001", "IDEA002"]

    def test_example_reconstruction(self, analysis_env):
        source_map = reconstruct_source_map(
            compact_fixture("E"), _transcript(analysis_env), provenance=_PROVENANCE
        )
        assert source_map.examples[0].example_id == "EX001"
        assert source_map.examples[0].supports_idea_refs == ("IDEA001", "IDEA002")

    def test_reference_reconstruction(self, analysis_env):
        source_map = reconstruct_source_map(
            compact_fixture("F"), _transcript(analysis_env), provenance=_PROVENANCE
        )
        assert source_map.references[0].reference_id == "REF001"
        assert source_map.references[0].raw_reference == "Paul dit quelque part"

    def test_uncertainty_reconstruction(self, analysis_env):
        source_map = reconstruct_source_map(
            compact_fixture("G"), _transcript(analysis_env), provenance=_PROVENANCE
        )
        assert source_map.uncertainties[0].uncertainty_id == "UNC001"

    def test_repetition_reconstruction(self, analysis_env):
        source_map = reconstruct_source_map(
            compact_fixture("H"), _transcript(analysis_env), provenance=_PROVENANCE
        )
        assert source_map.repetitions[0].repetition_id == "REP001"
        assert source_map.repetitions[0].idea_refs == ("IDEA001", "IDEA002")

    def test_voice_profile_reconstruction(self, analysis_env):
        source_map = reconstruct_source_map(
            compact_fixture("I"), _transcript(analysis_env), provenance=_PROVENANCE
        )
        assert "pastoral" in source_map.author_voice_profile.tone
        assert source_map.author_voice_profile.teaching_style.startswith("affirmation")

    def test_author_intent_reconstruction(self, analysis_env):
        source_map = reconstruct_source_map(
            compact_fixture("A"), _transcript(analysis_env), provenance=_PROVENANCE
        )
        assert source_map.source_analysis.author_intent.confidence == "high"
        assert source_map.source_analysis.author_intent.kinds == ("enseigner",)

    def test_audience_reconstruction(self, analysis_env):
        source_map = reconstruct_source_map(
            compact_fixture("A"), _transcript(analysis_env), provenance=_PROVENANCE
        )
        assert source_map.source_analysis.target_audience.confidence == "medium"

    def test_idea_relation_reconstruction(self, analysis_env):
        source_map = reconstruct_source_map(
            compact_fixture("D"), _transcript(analysis_env), provenance=_PROVENANCE
        )
        assert source_map.ideas[1].relations[0].to_idea == "IDEA001"
        assert source_map.ideas[1].relations[0].relation == "supports"


class TestSourceRefsAndIndexes:
    def test_sparse_source_refs(self, analysis_env):
        from app.tests.source_analysis_fixtures import drop_segments, write_transcript
        from app.tests.test_source_analysis_derived_pipeline import _sparse_env

        transcript, _, _ = _sparse_env(analysis_env)
        payload = compact_fixture("J")
        source_map = reconstruct_source_map(
            payload, transcript, provenance=_PROVENANCE
        )
        assert source_map.topics[0].source_refs == ("SRC000001", "SRC000007")

    def test_missing_source_ref_rejected(self, analysis_env):
        payload = compact_fixture("A")
        payload["ideas"][0]["source_refs"] = ["SRC000002"]
        from app.tests.test_source_analysis_derived_pipeline import _sparse_env

        transcript, _, _ = _sparse_env(analysis_env)
        payload["topics"][0]["source_refs"] = ["SRC000001"]
        with pytest.raises(SourceMapValidationError) as excinfo:
            reconstruct_source_map(payload, transcript, provenance=_PROVENANCE)
        assert any("SRC000002" in error for error in excinfo.value.errors)

    def test_invalid_indexes_rejected(self, analysis_env):
        payload = compact_fixture("A")
        payload["ideas"][0]["topic_indexes"] = [4]
        with pytest.raises(SourceMapValidationError) as excinfo:
            reconstruct_to_canonical_raw(payload)
        assert any("hors plage" in error for error in excinfo.value.errors)

    def test_invalid_idea_index_rejected(self, analysis_env):
        payload = compact_fixture("A")
        payload["relations"] = [{"from": 0, "to": 9, "relation": "supports"}]
        with pytest.raises(SourceMapValidationError) as excinfo:
            reconstruct_to_canonical_raw(payload)
        assert any("hors plage" in error for error in excinfo.value.errors)

    def test_canonical_id_assignment(self, analysis_env):
        source_map = reconstruct_source_map(
            compact_fixture("E"), _transcript(analysis_env), provenance=_PROVENANCE
        )
        assert source_map.declared_ids()["topics"] == ("TOP001",)
        assert source_map.declared_ids()["ideas"] == ("IDEA001", "IDEA002")
        assert source_map.declared_ids()["examples"] == ("EX001",)

    def test_canonical_ordering(self, analysis_env):
        payload = compact_fixture("C")
        payload["ideas"] = list(reversed(payload["ideas"]))
        source_map = reconstruct_source_map(
            payload, _transcript(analysis_env), provenance=_PROVENANCE
        )
        assert source_map.ideas[0].source_refs[0] == "SRC000001"
        assert source_map.ideas[0].idea_id == "IDEA001"


class TestCanonicalContractUnchanged:
    def test_canonical_validator_unchanged(self, analysis_env):
        source_map = reconstruct_source_map(
            compact_fixture("D"), _transcript(analysis_env), provenance=_PROVENANCE
        )
        assert validate_source_map(source_map, _transcript(analysis_env)) == []
        ensure_valid_source_map(source_map, _transcript(analysis_env))

    def test_completeness_unchanged(self, analysis_env):
        payload = compact_fixture("A")
        payload["ideas"] = []
        payload["relations"] = []
        source_map = reconstruct_source_map(
            payload, _transcript(analysis_env), provenance=_PROVENANCE
        )
        with pytest.raises(SourceMapValidationError) as excinfo:
            ensure_valid_source_map(source_map, _transcript(analysis_env))
        assert any("aucune idée" in error for error in excinfo.value.errors)

    def test_editorial_leakage_unchanged(self, analysis_env):
        payload = compact_fixture("A")
        payload["chapters"] = []
        with pytest.raises(SourceMapEditorialLeakError) as excinfo:
            reconstruct_to_canonical_raw(payload)
        assert "chapters" in excinfo.value.fields


class TestPromptCompactContract:
    def test_prompt_compact_contract(self, analysis_env):
        prompt = build_user_prompt(_transcript(analysis_env))
        assert "semantic-transport-v1" in prompt
        assert "records" in prompt
        assert "N'émets aucun identifiant métier" in prompt

    def test_prompt_fidelity_rules(self):
        prompt = build_system_prompt("fr")
        assert "ANALYSTE DE SOURCE" in prompt
        assert "Grande liberté d'analyse, liberté sémantique nulle." in prompt

    def test_prompt_forbidden_editorial_behavior(self, analysis_env):
        system = build_system_prompt("fr")
        user = build_user_prompt(_transcript(analysis_env))
        outside = system.replace(FORBIDDEN_STRUCTURE_BLOCK, "").lower()
        assert [word for word in STRUCTURAL_VOCABULARY if word in outside] == []
        assert [word for word in STRUCTURAL_VOCABULARY if word in user.lower()] == []

    def test_prompt_version_signature(self):
        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"

    def test_schema_sha_signature(self):
        old = schema_fingerprint(build_response_schema())
        new = compact_schema_fingerprint(build_compact_response_schema())
        assert old != new
        assert len(new) == 64

    def test_cache_invalidation(self):
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
        old_sig = build_signature(
            SignatureInputs(
                **shared,
                prompt_version="1.0",
                response_schema_sha256=schema_fingerprint(build_response_schema()),
            )
        )
        new_sig = build_signature(
            SignatureInputs(
                **shared,
                prompt_version="1.2",
                response_schema_sha256=compact_schema_fingerprint(),
            )
        )
        assert old_sig != new_sig


class TestAIRequestUsesCompact:
    def test_airequest_uses_compact_schema(self, analysis_env, no_ai_network):
        engine = fake_engine()
        analyze_source(analysis_env.project_name, engine=engine)
        assert engine.last_request.response_schema == build_ultra_compact_response_schema()
        assert engine.last_request.response_schema != build_compact_response_schema()

    def test_anthropic_payload_uses_compact_schema(self, analysis_env):
        request = AIRequest(
            prompt="x",
            system_prompt="s",
            model="claude-sonnet-5",
            response_schema=build_ultra_compact_response_schema(),
        )
        payload = AnthropicEngine(model="claude-sonnet-5", api_key="test").build_payload(
            request, "claude-sonnet-5"
        )
        assert payload["output_config"]["format"]["type"] == "json_schema"
        assert payload["output_config"]["format"]["schema"] == (
            prepare_anthropic_json_schema(build_ultra_compact_response_schema())
        )

    def test_old_schema_not_sent(self, analysis_env):
        request = AIRequest(
            prompt="x",
            model="claude-sonnet-5",
            response_schema=build_ultra_compact_response_schema(),
        )
        payload = AnthropicEngine(model="claude-sonnet-5", api_key="test").build_payload(
            request, "claude-sonnet-5"
        )
        sent = payload["output_config"]["format"]["schema"]
        assert sent != prepare_anthropic_json_schema(build_response_schema())
        assert sent != prepare_anthropic_json_schema(build_compact_response_schema())

    def test_provider_adapter_compatibility(self):
        adapted = prepare_anthropic_json_schema(build_compact_response_schema())
        findings = audit_unsupported_features(adapted)
        assert findings["additionalProperties_not_false"] == []
        assert findings["minLength"] == []
        assert findings["unsupported_minItems"] == []
        assert findings["external_ref"] == []
        assert all(not values for values in findings.values())

    def test_additional_properties_false(self):
        adapted = prepare_anthropic_json_schema(build_compact_response_schema())
        findings = audit_unsupported_features(adapted)
        assert findings["additionalProperties_not_false"] == []

    def test_unsupported_constraints_zero(self):
        adapted = prepare_anthropic_json_schema(build_compact_response_schema())
        findings = audit_unsupported_features(adapted)
        assert findings["minLength"] == []
        assert findings["maxLength"] == []
        assert findings["minimum"] == []
        assert findings["maximum"] == []
        assert findings["multipleOf"] == []
        assert findings["maxItems"] == []
        assert findings["unsupported_minItems"] == []


class TestNoNetworkNoGenerate:
    def test_no_real_network(self, analysis_env, no_ai_network):
        analyze_source(analysis_env.project_name, engine=fake_engine())
        assert analysis_env.source_map_path.exists()

    def test_no_engine_generate(self, analysis_env):
        guard = GenerateGuard()
        result = run_source_analyzer_preflight(
            transcript_data_file(analysis_env.transcripts_dir),
            project_name=analysis_env.project_name,
            engine=guard,
        )
        assert guard.calls == 0
        assert result.generate_calls == 0
        assert result.plan.strategy == "global"

    def test_preflight_global(self, analysis_env):
        result = run_source_analyzer_preflight(
            transcript_data_file(analysis_env.transcripts_dir),
            project_name=analysis_env.project_name,
        )
        assert result.plan.strategy == "global"
        assert result.request.response_schema == build_ultra_compact_response_schema()
        assert result.request.response_schema != build_compact_response_schema()


class TestDiagnosticAndProtected:
    def test_diagnostic_artifact_deterministic(self, tmp_path):
        first = tmp_path / "a" / AUDIT_ARTIFACT_NAME
        second = tmp_path / "b" / AUDIT_ARTIFACT_NAME
        write_compact_schema_audit(first)
        write_compact_schema_audit(second)
        assert first.read_bytes() == second.read_bytes()
        payload = json.loads(first.read_text(encoding="utf-8"))
        assert payload["server_acceptance"] == SERVER_ACCEPTANCE
        assert "generated_at" not in payload

    def test_protected_artifacts_unchanged(self):
        from app.source_analysis.protected import snapshot_protected

        before = snapshot_protected(
            "pastoral_retreat_v2_validation", require_all=False
        )
        after = snapshot_protected(
            "pastoral_retreat_v2_validation", require_all=False
        )
        assert before.hashes == after.hashes


class TestFailureModes:
    def test_missing_semantic_required_field(self):
        payload = compact_fixture("A")
        del payload["source_analysis"]["main_theme"]
        with pytest.raises(AIStructuredOutputError):
            parse_structured_output(
                json.dumps(payload), build_compact_response_schema()
            )

    def test_invalid_confidence(self):
        payload = compact_fixture("A")
        payload["source_analysis"]["author_intent"]["confidence"] = "peut-être"
        with pytest.raises(AIStructuredOutputError):
            parse_structured_output(
                json.dumps(payload), build_compact_response_schema()
            )

    def test_invalid_enum(self):
        payload = compact_fixture("A")
        payload["ideas"][0]["kind"] = "brillante"
        with pytest.raises(AIStructuredOutputError):
            parse_structured_output(
                json.dumps(payload), build_compact_response_schema()
            )

    def test_invalid_source_ref_pattern(self):
        payload = compact_fixture("A")
        payload["ideas"][0]["source_refs"] = ["SRC1"]
        with pytest.raises(AIStructuredOutputError):
            parse_structured_output(
                json.dumps(payload), build_compact_response_schema()
            )

    def test_unknown_provider_field(self):
        payload = compact_fixture("A")
        payload["invented_axis"] = "nope"
        with pytest.raises(SourceMapValidationError) as excinfo:
            reconstruct_to_canonical_raw(payload)
        assert any("invented_axis" in error for error in excinfo.value.errors)

    def test_canonical_validation_failure_propagated(self, analysis_env):
        payload = compact_fixture("A")
        payload["ideas"][0]["source_refs"] = ["SRC999999"]
        parsed = parse_structured_output(
            json.dumps(payload), build_compact_response_schema()
        )
        with pytest.raises(SourceMapValidationError):
            reconstruct_source_map(
                parsed, _transcript(analysis_env), provenance=_PROVENANCE
            )

    def test_empty_collections_allowed(self, analysis_env):
        payload = compact_fixture("A")
        source_map = reconstruct_source_map(
            payload, _transcript(analysis_env), provenance=_PROVENANCE
        )
        assert source_map.examples == ()
        assert source_map.references == ()
        assert source_map.uncertainties == ()
        assert source_map.repetitions == ()

    def test_provider_ids_not_required(self):
        schema = json.dumps(build_compact_response_schema())
        for field in COMPACT_ID_FIELDS_ABSENT:
            assert f'"{field}"' not in schema

    def test_golden_test(self, analysis_env):
        payload = fake_compact_analysis_payload()
        source_map = reconstruct_source_map(
            payload, _transcript(analysis_env), provenance=_PROVENANCE
        )
        ensure_valid_source_map(source_map, _transcript(analysis_env))
        assert source_map.source_analysis.main_theme == (
            "Le rôle de la foi dans la manière de traverser les épreuves"
        )
        assert [idea.idea_id for idea in source_map.ideas] == ["IDEA001", "IDEA002"]
        assert source_map.ideas[1].relations[0].to_idea == "IDEA001"
        assert source_map.examples[0].supports_idea_refs == ("IDEA001",)
        assert source_map.repetitions[0].idea_refs == ("IDEA001", "IDEA002")
        assert source_map.stats.idea_count == 2
        assert source_map.analysis.signature == "sig-compact"

    def test_fixtures_a_to_j_rebuild(self, analysis_env):
        transcript = _transcript(analysis_env)
        for name in "ABCDEFGHIJ":
            source_map = reconstruct_source_map(
                compact_fixture(name), transcript, provenance=_PROVENANCE
            )
            ensure_valid_source_map(source_map, transcript)
            assert forbidden_editorial_fields(source_map.to_dict()) == ()

    def test_looks_like_canonical_raw(self):
        assert looks_like_canonical_raw(fake_analysis_payload()) is True
        assert looks_like_canonical_raw(compact_fixture("A")) is False

    def test_round_trip_fixture_adapter(self, analysis_env):
        raw = fake_analysis_payload()
        compact = to_compact_provider_payload(raw)
        source_map = reconstruct_source_map(
            compact, _transcript(analysis_env), provenance=_PROVENANCE
        )
        ensure_valid_source_map(source_map, _transcript(analysis_env))
        assert source_map.stats.topic_count == 1


class TestObservabilityUnchanged:
    def test_structured_parse_failure_still_observable(
        self, analysis_env, no_ai_network
    ):
        engine = fake_engine("{ cassé", input_tokens=10, output_tokens=2)
        with pytest.raises(AIStructuredOutputError):
            analyze_source(analysis_env.project_name, engine=engine)
        records = analysis_env.state()["ai_usage"]["records"]
        assert records[0]["input_tokens"] == 10
        assert engine.call_count == 1
        assert not analysis_env.source_map_path.exists()

    def test_no_json_repair(self, analysis_env, no_ai_network):
        engine = fake_engine("{ cassé")
        with pytest.raises(AIStructuredOutputError):
            analyze_source(analysis_env.project_name, engine=engine)
        assert engine.call_count == 1
