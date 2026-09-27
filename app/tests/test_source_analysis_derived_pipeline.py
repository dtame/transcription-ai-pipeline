"""
Phase 3A.2C — Source Analyzer sur un transcript DERIVED à SRC creux.

Prompt, fenêtres, normalizer, validateur, couverture, signature, préflight.
Aucun engine.generate(), aucun réseau.
"""

from __future__ import annotations

import pytest

from app.ai.capabilities import resolve_capabilities
from app.source_analysis.cache import SignatureInputs, build_signature
from app.source_analysis.context_strategy import plan_context, plan_windows
from app.source_analysis.models import AnalysisProvenance, STRATEGY_GLOBAL
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.preflight import (
    GenerateGuard,
    run_source_analyzer_preflight,
)
from app.source_analysis.prompt import build_system_prompt, build_user_prompt
from app.source_analysis.compact_schema import build_compact_response_schema
from app.source_analysis.schema import build_response_schema
from app.source_analysis.ultra_compact_schema import build_ultra_compact_response_schema
from app.source_analysis.transcript_input import (
    TranscriptInputMode,
    load_transcript_input,
)
from app.source_analysis.validator import validate_source_map
from app.tests.source_analysis_fixtures import (
    analysis_env,  # noqa: F401
    drop_segments,
    fake_analysis_payload,
    write_cleanup_provenance,
    write_transcript,
)
from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)

_PROVENANCE = AnalysisProvenance(
    prompt_version="1.0",
    schema_version="1.0",
    provider="fake",
    model="fake-model",
    strategy="global",
    signature="sig",
)

SPARSE_KEEP = ("SRC000001", "SRC000003", "SRC000007")
SPARSE_DROP = ("SRC000002", "SRC000004", "SRC000005", "SRC000006", "SRC000008")


def _sparse_env(env):
    original = env.document
    removed = [segment for segment in original.segments if segment.id in SPARSE_DROP]
    clean = drop_segments(original, set(SPARSE_DROP))
    clean_path = write_transcript(env.transcripts_dir / "clean", clean)
    provenance_path = env.sortie / env.project_name / "audit" / "cleanup_application.json"
    write_cleanup_provenance(
        provenance_path,
        original_path=env.transcript_path,
        clean_path=clean_path,
        original=original,
        clean=clean,
        removed=removed,
    )
    transcript = load_transcript_input(
        clean_path,
        project_name=env.project_name,
        mode=TranscriptInputMode.DERIVED,
        provenance_path=provenance_path,
    )
    return transcript, clean_path, provenance_path


class TestCleanInputLoads:
    def test_clean_input_loads(self, analysis_env):
        transcript, _, _ = _sparse_env(analysis_env)

        assert transcript.segment_count == 3
        assert transcript.src_ids() == SPARSE_KEEP
        assert transcript.duration_seconds == analysis_env.document.stats.duration_seconds


class TestPromptKeepsRealSrcIds:
    def test_prompt_keeps_original_src_ids(self, analysis_env):
        transcript, _, _ = _sparse_env(analysis_env)
        prompt = build_user_prompt(transcript)

        assert "[SRC000001 |" in prompt
        assert "[SRC000003 |" in prompt
        assert "[SRC000007 |" in prompt
        assert "SRC000002" not in prompt
        assert "LOCAL_SRC" not in prompt
        assert "SRC000001" in prompt


class TestContextPlanWithGaps:
    def test_global_context_plan_works(self, analysis_env):
        transcript, _, _ = _sparse_env(analysis_env)
        plan = plan_context(
            transcript,
            resolve_capabilities("fake", "fake-model"),
            system_prompt=build_system_prompt(transcript.primary_language),
            user_prompt=build_user_prompt(transcript),
        )

        assert plan.strategy == STRATEGY_GLOBAL
        assert plan.windows == ()

    def test_window_context_plan_uses_present_src_list(self, analysis_env):
        transcript, _, _ = _sparse_env(analysis_env)
        windows = plan_windows(
            transcript,
            estimated_tokens=1_000,
            budget_tokens=50,
            overlap_segments=0,
        )

        seen = [segment.src_id for window in windows for segment in window.segments]
        assert seen == list(SPARSE_KEEP)
        assert windows[0].first_src == "SRC000001"
        assert windows[-1].last_src == "SRC000007"


class TestNormalizerAndValidatorSparseRefs:
    def test_normalizer_accepts_sparse_source_refs(self, analysis_env):
        transcript, _, _ = _sparse_env(analysis_env)
        payload = fake_analysis_payload()
        payload["topics"][0]["source_refs"] = ["SRC000001", "SRC000007"]
        payload["ideas"][0]["source_refs"] = ["SRC000001"]
        payload["ideas"][1]["source_refs"] = ["SRC000007"]
        payload["examples"][0]["source_refs"] = ["SRC000003"]
        payload["repetitions"][0]["source_refs"] = ["SRC000001", "SRC000007"]

        source_map = normalize_source_map(
            payload, transcript, provenance=_PROVENANCE
        )

        assert source_map.topics[0].source_refs == ("SRC000001", "SRC000007")
        assert source_map.stats.source_segment_count == 3

    def test_validator_accepts_existing_sparse_refs(self, analysis_env):
        transcript, _, _ = _sparse_env(analysis_env)
        payload = fake_analysis_payload()
        payload["topics"][0]["source_refs"] = ["SRC000001", "SRC000007"]
        payload["ideas"][0]["source_refs"] = ["SRC000001"]
        payload["ideas"][1]["source_refs"] = ["SRC000007"]
        payload["examples"][0]["source_refs"] = ["SRC000003"]
        payload["repetitions"][0]["source_refs"] = ["SRC000001", "SRC000007"]

        source_map = normalize_source_map(
            payload, transcript, provenance=_PROVENANCE
        )
        assert validate_source_map(source_map, transcript) == []

    def test_validator_rejects_missing_sparse_ref(self, analysis_env):
        transcript, _, _ = _sparse_env(analysis_env)
        payload = fake_analysis_payload()
        payload["topics"][0]["source_refs"] = ["SRC000001", "SRC000007"]
        payload["ideas"][0]["source_refs"] = ["SRC000001"]
        payload["ideas"][1]["source_refs"] = ["SRC000007"]
        payload["examples"][0]["source_refs"] = ["SRC000003"]
        payload["repetitions"][0]["source_refs"] = ["SRC000001", "SRC000007"]

        source_map = normalize_source_map(
            payload, transcript, provenance=_PROVENANCE
        )

        import dataclasses

        broken = dataclasses.replace(
            source_map,
            ideas=(
                dataclasses.replace(
                    source_map.ideas[0], source_refs=("SRC000002",)
                ),
                source_map.ideas[1],
            ),
        )
        errors = validate_source_map(broken, transcript)
        assert any("SRC000002" in error and "n'existe pas" in error for error in errors)

    def test_coverage_denominator_uses_present_clean_src(self, analysis_env):
        transcript, _, _ = _sparse_env(analysis_env)
        payload = fake_analysis_payload()
        payload["topics"][0]["source_refs"] = ["SRC000001", "SRC000007"]
        payload["ideas"][0]["source_refs"] = ["SRC000001"]
        payload["ideas"][1]["source_refs"] = ["SRC000007"]
        payload["examples"][0]["source_refs"] = ["SRC000003"]
        payload["repetitions"][0]["source_refs"] = ["SRC000001", "SRC000007"]

        source_map = normalize_source_map(
            payload, transcript, provenance=_PROVENANCE
        )

        assert source_map.stats.source_segment_count == 3
        assert source_map.stats.referenced_source_segments == 3
        assert source_map.stats.source_coverage_ratio == 1.0


class TestSignatureOriginalVsClean:
    def test_signature_differs_original_clean_same_transcript_id(self, analysis_env):
        original = load_transcript_input(
            analysis_env.transcript_path, project_name=analysis_env.project_name
        )
        clean, _, _ = _sparse_env(analysis_env)

        assert original.transcript_id == clean.transcript_id == "TR001"
        assert original.content_sha256 != clean.content_sha256

        common = dict(
            transcript_id="TR001",
            prompt_version="1.0",
            prompt_sha256="b" * 64,
            schema_version="1.0",
            response_schema_sha256="c" * 64,
            provider="anthropic",
            model="claude-sonnet-5",
            temperature=None,
            max_output_tokens=None,
            context_safety_ratio=0.70,
            output_language="fr",
        )
        original_sig = build_signature(
            SignatureInputs(transcript_sha256=original.content_sha256, **common)
        )
        clean_sig = build_signature(
            SignatureInputs(transcript_sha256=clean.content_sha256, **common)
        )
        assert original_sig != clean_sig

    def test_cache_does_not_collide(self, analysis_env):
        from app.source_analysis.cache import is_cache_valid

        original = load_transcript_input(
            analysis_env.transcript_path, project_name=analysis_env.project_name
        )
        clean, _, _ = _sparse_env(analysis_env)
        common = dict(
            transcript_id="TR001",
            prompt_version="1.0",
            prompt_sha256="b" * 64,
            schema_version="1.0",
            response_schema_sha256="c" * 64,
            provider="anthropic",
            model="claude-sonnet-5",
            temperature=None,
            max_output_tokens=None,
            context_safety_ratio=0.70,
            output_language="fr",
        )
        original_sig = build_signature(
            SignatureInputs(transcript_sha256=original.content_sha256, **common)
        )
        clean_sig = build_signature(
            SignatureInputs(transcript_sha256=clean.content_sha256, **common)
        )

        assert not is_cache_valid(
            signature=clean_sig,
            state_block={"status": "completed", "signature": original_sig},
            published_payload={"analysis": {"signature": original_sig}},
        )


class TestPreflightGuard:
    def test_preflight_never_calls_generate(self, analysis_env):
        transcript, clean_path, provenance_path = _sparse_env(analysis_env)
        guard = GenerateGuard()

        result = run_source_analyzer_preflight(
            clean_path,
            project_name=analysis_env.project_name,
            mode=TranscriptInputMode.DERIVED,
            provenance_path=provenance_path,
            engine=guard,
        )

        assert guard.calls == 0
        assert result.generate_calls == 0
        assert result.request.response_schema == build_ultra_compact_response_schema()
        assert result.request.response_schema != build_compact_response_schema()
        assert result.request.response_schema != build_response_schema()
        assert result.to_artifact()["source_analysis"]["would_call_ai"] is False

    def test_generate_guard_raises_if_called(self):
        guard = GenerateGuard()
        with pytest.raises(AssertionError, match="interdit"):
            guard.generate(object())
        assert guard.calls == 1

    def test_preflight_artifact_is_deterministic(self, analysis_env, tmp_path):
        _, clean_path, provenance_path = _sparse_env(analysis_env)
        first = tmp_path / "a" / "source_analyzer_clean_preflight.json"
        second = tmp_path / "b" / "source_analyzer_clean_preflight.json"

        run_source_analyzer_preflight(
            clean_path,
            project_name=analysis_env.project_name,
            mode=TranscriptInputMode.DERIVED,
            provenance_path=provenance_path,
            write_artifact_to=first,
        )
        run_source_analyzer_preflight(
            clean_path,
            project_name=analysis_env.project_name,
            mode=TranscriptInputMode.DERIVED,
            provenance_path=provenance_path,
            write_artifact_to=second,
        )

        assert first.read_bytes() == second.read_bytes()
        assert not first.with_name(first.name + ".partial").exists()

    def test_anthropic_schema_audit_stays_clean(self, analysis_env):
        _, clean_path, provenance_path = _sparse_env(analysis_env)
        result = run_source_analyzer_preflight(
            clean_path,
            project_name=analysis_env.project_name,
            mode=TranscriptInputMode.DERIVED,
            provenance_path=provenance_path,
        )

        findings = result.schema_audit
        assert findings["additionalProperties_not_false"] == []
        assert findings["minLength"] == []
        assert findings["unsupported_minItems"] == []
        assert findings["external_ref"] == []
        provider = prepare_anthropic_json_schema(build_ultra_compact_response_schema())
        assert audit_unsupported_features(provider) == findings
