"""
Phase 3B — garde-fou et portes pré-appel du Source Analyzer DERIVED.

Aucun test de ce fichier ne touche au réseau : `no_ai_network` interdit
tout POST, et le moteur est toujours FakeAIEngine. 0 appel Anthropic.
"""

from __future__ import annotations

import json

import pytest

from app.ai.providers.fake import FakeReply
from app.source_analysis.errors import (
    ExistingSourceMapConflictError,
    MaxRealCallsExceededError,
    SourceMapTruncatedError,
)
from app.source_analysis.guard import RealCallGuard
from app.source_analysis.real_run import (
    GuardedEngine,
    run_derived_source_analysis,
)
from app.source_analysis.transcript_input import TranscriptInputMode, load_transcript_input
from app.source_analysis.ultra_compact_schema import to_ultra_transport_payload
from app.tests.source_analysis_fixtures import (
    analysis_env,  # noqa: F401
    drop_segments,
    fake_analysis_payload,
    fake_engine,
    write_cleanup_provenance,
    write_transcript,
)

# On retire seulement les trois hésitations terminales : le clean reste
# substantiel (>= 30 mots) tout en ayant des trous SRC.
SPARSE_KEEP = ("SRC000001", "SRC000002", "SRC000003", "SRC000004", "SRC000005")
SPARSE_DROP = ("SRC000006", "SRC000007", "SRC000008")


def _derived_payload() -> dict:
    return fake_analysis_payload()


def _routed_fake_engine(**kwargs):
    """Fake dont provider/modèle collent au routage source_analysis."""
    engine = fake_engine(model="claude-sonnet-5", **kwargs)
    engine.provider_name = "anthropic"
    return engine


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
    return clean_path, provenance_path


class TestRealCallGuard:
    def test_premier_appel_passe(self):
        guard = RealCallGuard(max_calls=1)
        engine = fake_engine()
        from app.ai.contracts import AIRequest

        response = guard.guarded_generate(engine, AIRequest(prompt="x"))
        assert guard.call_count == 1
        assert response.text

    def test_second_appel_leve(self):
        guard = RealCallGuard(max_calls=1)
        engine = fake_engine()
        from app.ai.contracts import AIRequest

        guard.guarded_generate(engine, AIRequest(prompt="x"))
        with pytest.raises(MaxRealCallsExceededError):
            guard.guarded_generate(engine, AIRequest(prompt="x"))
        assert guard.call_count == 1

    def test_compteur_incremente_avant_echec(self):
        guard = RealCallGuard(max_calls=1)

        class Boom:
            def generate(self, request):
                raise RuntimeError("transport")

        with pytest.raises(RuntimeError):
            guard.guarded_generate(Boom(), object())
        assert guard.call_count == 1
        with pytest.raises(MaxRealCallsExceededError):
            guard.guarded_generate(Boom(), object())


class TestGuardedEngine:
    def test_refuse_un_second_generate(self, no_ai_network):
        inner = fake_engine(payload=_derived_payload())
        guarded = GuardedEngine(inner, RealCallGuard(max_calls=1))
        from app.ai.contracts import AIRequest

        guarded.generate(AIRequest(prompt="x"))
        with pytest.raises(MaxRealCallsExceededError):
            guarded.generate(AIRequest(prompt="x"))
        assert guarded.generate_calls == 1
        assert inner.call_count == 1


class TestExistingSourceMapNotOverwritten:
    def test_source_map_existant_non_cache_stop_sans_appel(
        self, analysis_env, no_ai_network
    ):
        _sparse_env(analysis_env)
        map_path = analysis_env.source_map_path
        map_path.parent.mkdir(parents=True, exist_ok=True)
        marker = '{"analysis": {"signature": "not-the-clean-signature"}, "keep": true}\n'
        map_path.write_text(marker, encoding="utf-8")
        before = map_path.read_bytes()

        engine = fake_engine(payload=_derived_payload())
        result = run_derived_source_analysis(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
            engine=engine,
            require_protected=False,
            write_report=False,
        )

        assert result.stop_reason == "EXISTING_SOURCE_MAP"
        assert result.real_call_count == 0
        assert engine.call_count == 0
        assert map_path.read_bytes() == before
        assert isinstance(
            result.error_type, str
        ) and result.error_type == ExistingSourceMapConflictError.__name__


class TestCacheHitNoCall:
    def test_cache_valide_ne_rappelle_pas(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        first = _routed_fake_engine(payload=_derived_payload())
        first_result = run_derived_source_analysis(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
            engine=first,
            require_protected=False,
            write_report=False,
        )
        assert first_result.outcome == "PASS"
        assert first.call_count == 1
        published = analysis_env.source_map_path.read_bytes()

        second = _routed_fake_engine(payload=_derived_payload())
        result = run_derived_source_analysis(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
            engine=second,
            require_protected=False,
            write_report=False,
        )

        assert result.cache_hit is True
        assert result.real_call_count == 0
        assert second.call_count == 0
        assert analysis_env.source_map_path.read_bytes() == published
        assert result.source_map_validation == "PASS"


class TestMissingCredentialStops:
    def test_credential_absente_zero_appel(self, analysis_env, no_ai_network, monkeypatch):
        _sparse_env(analysis_env)
        monkeypatch.setattr(
            "app.source_analysis.real_run.anthropic_credential_available",
            lambda: False,
        )
        engine = fake_engine(payload=_derived_payload())
        result = run_derived_source_analysis(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
            engine=engine,
            require_protected=False,
            require_credential=True,
            write_report=False,
        )

        assert result.stop_reason == "PRE_CALL_FAILURE"
        assert result.real_call_count == 0
        assert engine.call_count == 0
        assert analysis_env.source_map_path.exists() is False


class TestTruncationNotPublished:
    def test_max_tokens_ne_publie_pas(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        engine = _routed_fake_engine(
            script=[
                FakeReply(
                    text=json.dumps(
                        to_ultra_transport_payload(_derived_payload()),
                        ensure_ascii=False,
                    ),
                    input_tokens=100,
                    output_tokens=50,
                    finish_reason="max_tokens",
                    request_id="req_trunc",
                )
            ]
        )
        result = run_derived_source_analysis(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
            engine=engine,
            require_protected=False,
            write_report=False,
        )

        assert result.real_call_count == 1
        assert result.error_type == SourceMapTruncatedError.__name__
        assert analysis_env.source_map_path.exists() is False
        assert not analysis_env.partial_path.exists()


class TestHappyPathFake:
    def test_derived_publie_un_source_map_valide(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        engine = _routed_fake_engine(payload=_derived_payload(), input_tokens=200, output_tokens=40)
        result = run_derived_source_analysis(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
            engine=engine,
            require_protected=False,
            write_report=True,
        )

        assert result.outcome == "PASS"
        assert result.real_call_count == 1
        assert result.cache_hit is False
        assert result.signatures_differ is True
        assert result.real_src_ids_preserved is True
        assert result.removed_src_absent_from_prompt is True
        assert result.any_removed_referenced is False
        assert result.all_refs_in_clean is True
        assert result.source_map_exists is True
        assert result.partial_leftovers is False
        assert result.idea_count >= 1
        payload = analysis_env.source_map()
        assert payload["transcript_id"] == "TR001"
        report = (
            analysis_env.sortie
            / analysis_env.project_name
            / "audit"
            / "PHASE_3B_REAL_SOURCE_ANALYZER_CLEAN_REPORT.md"
        )
        assert report.exists()


class TestPromptKeepsGaps:
    def test_src_survivants_dans_le_prompt(self, analysis_env, no_ai_network):
        clean_path, provenance_path = _sparse_env(analysis_env)
        transcript = load_transcript_input(
            clean_path,
            project_name=analysis_env.project_name,
            mode=TranscriptInputMode.DERIVED,
            provenance_path=provenance_path,
        )
        from app.source_analysis.prompt import build_user_prompt

        prompt = build_user_prompt(transcript)
        assert "SRC000001" in prompt
        assert "SRC000005" in prompt
        assert "SRC000006" not in prompt
        assert "SRC000007" not in prompt
        assert "SRC000008" not in prompt
