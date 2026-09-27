"""
Phase 3B Final — portes pré-appel et publication gardée du Source Analyzer.

Aucun test de ce fichier n'ouvre de connexion : `no_ai_network` interdit
tout POST. Le moteur réel n'est jamais construit.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

from app.ai.contracts import AIRequest
from app.ai.errors import AIRequestError, AITransientError
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.providers.fake import FakeReply
from app.source_analysis.errors import MaxRealCallsExceededError
from app.source_analysis.guard import RealCallGuard
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.real_run import GuardedEngine
from app.source_analysis.schema import schema_fingerprint
from app.source_analysis.ultra_compact_schema import ultra_compact_schema_fingerprint
from app.source_analysis.writer import source_map_path
from app.source_analysis_global_clean.constants import (
    CANARY_SIGNATURE_MARKS,
    EXPECTED_MODEL,
    EXPECTED_MODEL_MAX_OUTPUT,
    EXPECTED_PROMPT_VERSION,
    EXPECTED_PROVIDER,
    MAX_ATTEMPTS,
    MAX_REAL_CALLS,
    TRANSPORT_VERSION,
)
from app.source_analysis_global_clean.runner import run_global_clean_source_analysis
from app.source_analysis_global_clean.writer import (
    dry_run_path,
    production_source_map_path,
    transport_path,
)
from app.source_analysis_ultra_compact_canary.architecture import (
    production_generation_c_schema,
)
from app.source_analysis.vocabulary_fixtures import build_observed_3b43_invalid_transport
from app.tests.source_analysis_fixtures import (  # noqa: F401
    analysis_env,
    drop_segments,
    fake_engine,
    fake_ultra_analysis_payload,
    write_cleanup_provenance,
    write_transcript,
)

SPARSE_KEEP = ("SRC000001", "SRC000002", "SRC000003", "SRC000004", "SRC000005")
SPARSE_DROP = ("SRC000006", "SRC000007", "SRC000008")


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


class TestPromptGenerationCAndParity:
    def test_prompt_13_and_generation_c(self):
        assert SOURCE_ANALYZER_PROMPT_VERSION == EXPECTED_PROMPT_VERSION == "1.3"
        schema = production_generation_c_schema()
        assert ultra_compact_schema_fingerprint(schema)
        adapted = prepare_anthropic_json_schema(schema)
        payload = AnthropicEngine(model=EXPECTED_MODEL, api_key="t").build_payload(
            AIRequest(
                prompt="x",
                system_prompt="y",
                model=EXPECTED_MODEL,
                response_schema=schema,
            ),
            EXPECTED_MODEL,
        )
        assert payload["output_config"]["format"]["type"] == "json_schema"
        assert schema_fingerprint(payload["output_config"]["format"]["schema"]) == (
            schema_fingerprint(adapted)
        )


class TestDryRunGuards:
    def test_dry_run_selects_clean_derived_not_original(
        self, analysis_env, no_ai_network
    ):
        _sparse_env(analysis_env)
        result = run_global_clean_source_analysis(
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
        assert result.mode == "DERIVED"
        assert result.original_not_selected is True
        assert result.provenance_verified is True
        assert result.prompt_version == "1.3"
        assert result.vocabulary_parity == "PASS"
        assert result.missing_from_prompt == []
        assert result.extra_in_prompt == []
        assert result.uses_production_generation_c is True
        assert result.generation_a_absent_from_payload is True
        assert result.generation_b_absent_from_payload is True
        assert result.generation_c_unchanged is True
        assert result.output_format_type == "json_schema"
        assert result.strategy == "global"
        assert result.resolved_max_output == EXPECTED_MODEL_MAX_OUTPUT
        assert result.max_output_coherent is True
        assert result.max_real_calls == 1
        assert result.max_attempts == 1
        assert result.retry is False
        assert result.fallback is None
        assert result.dry_run_deterministic is True
        assert result.dry_run_sha256_run1 == result.dry_run_sha256_run2
        assert result.cache_isolated_from_canaries is True
        assert result.signature not in CANARY_SIGNATURE_MARKS
        assert result.source_map_published is False
        assert not production_source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()
        path = dry_run_path(analysis_env.project_name, sortie_dir=analysis_env.sortie)
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["would_call_ai"] is True
        assert payload["actual_real_calls"] == 0
        assert payload["prompt"] == "1.3"
        assert payload["transport"] == TRANSPORT_VERSION
        assert payload["derived_provenance"] == "PASS"
        assert "timestamp" not in payload
        assert result.decoder_integrity["fail_closed"] is True

    def test_existing_source_map_stops_without_call(
        self, analysis_env, no_ai_network
    ):
        _sparse_env(analysis_env)
        map_path = source_map_path(analysis_env.project_name)
        map_path.parent.mkdir(parents=True, exist_ok=True)
        before = b'{"keep": true}\n'
        map_path.write_bytes(before)
        engine = _routed_fake(list(SPARSE_KEEP))
        result = run_global_clean_source_analysis(
            analysis_env.project_name,
            dry_run=False,
            engine=engine,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
        )
        assert result.stop_reason == "EXISTING_SOURCE_MAP"
        assert result.actual_real_calls == 0
        assert engine.call_count == 0
        assert map_path.read_bytes() == before

    def test_missing_credential_zero_call(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        _sparse_env(analysis_env)
        monkeypatch.setattr(
            "app.source_analysis.real_run.anthropic_credential_available",
            lambda: False,
        )
        engine = _routed_fake(list(SPARSE_KEEP))
        result = run_global_clean_source_analysis(
            analysis_env.project_name,
            dry_run=False,
            engine=engine,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=True,
        )
        assert result.classification == "PRE_CALL_CREDENTIAL_MISSING"
        assert result.actual_real_calls == 0
        assert engine.call_count == 0
        assert not production_source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()


class TestCallGuardAndIsolation:
    def test_http_failure_counts_as_one_call(
        self, analysis_env, no_ai_network
    ):
        _sparse_env(analysis_env)
        engine = fake_engine(
            script=[AIRequestError("Anthropic a répondu 500. timeout")],
            model="claude-sonnet-5",
        )
        engine.provider_name = "anthropic"
        result = run_global_clean_source_analysis(
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
        assert engine.call_count == 1
        assert result.source_map_published is False

    def test_retry_false_max_attempts_one(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        engine = fake_engine(script=[AITransientError("timeout")], model="claude-sonnet-5")
        engine.provider_name = "anthropic"
        result = run_global_clean_source_analysis(
            analysis_env.project_name,
            dry_run=False,
            engine=engine,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
        )
        assert result.max_attempts == MAX_ATTEMPTS == 1
        assert getattr(engine, "_retry_policy").max_attempts == 1
        assert result.retry is False
        assert result.fallback is None
        assert result.actual_real_calls == 1

    def test_guarded_engine_refuses_second_generate(self, no_ai_network):
        inner = fake_engine(payload=fake_ultra_analysis_payload())
        guarded = GuardedEngine(inner, RealCallGuard(max_calls=MAX_REAL_CALLS))
        guarded.generate(AIRequest(prompt="x"))
        with pytest.raises(MaxRealCallsExceededError):
            guarded.generate(AIRequest(prompt="x"))
        assert guarded.generate_calls == 1

    def test_canary_source_map_is_not_production_cache(
        self, analysis_env, no_ai_network
    ):
        _sparse_env(analysis_env)
        canary = (
            analysis_env.sortie
            / analysis_env.project_name
            / "audit"
            / "source_analysis_vocabulary_compliance_canary_source_map.json"
        )
        canary.parent.mkdir(parents=True, exist_ok=True)
        canary.write_text(
            json.dumps({"canary": True, "not_production": True, "analysis": {"signature": "x"}}),
            encoding="utf-8",
        )
        result = run_global_clean_source_analysis(
            analysis_env.project_name,
            dry_run=True,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
        )
        assert result.cache_hit is False
        assert result.cache_status == "miss"
        assert result.signature not in CANARY_SIGNATURE_MARKS
        assert not production_source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()


class TestTransportPreservationAndPublication:
    def test_invalid_vocab_preserves_transport_no_publish(
        self, analysis_env, no_ai_network
    ):
        _sparse_env(analysis_env)
        payload = build_observed_3b43_invalid_transport("SRC000001")
        engine = fake_engine(payload=payload, model="claude-sonnet-5")
        engine.provider_name = "anthropic"
        result = run_global_clean_source_analysis(
            analysis_env.project_name,
            dry_run=False,
            engine=engine,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
        )
        assert result.actual_real_calls == 1
        assert result.vocabulary_compliance == "FAIL"
        assert result.source_map_published is False
        assert result.project_state_status == "failed"
        assert result.transport_preserved == "PASS"
        assert transport_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).is_file()
        assert not production_source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()
        assert engine.call_count == 1

    def test_truncation_preserves_transport_no_publish(
        self, analysis_env, no_ai_network
    ):
        _sparse_env(analysis_env)
        engine = fake_engine(
            script=[
                FakeReply(
                    text=json.dumps(fake_ultra_analysis_payload(), ensure_ascii=False),
                    input_tokens=100,
                    output_tokens=50,
                    finish_reason="max_tokens",
                    request_id="req_trunc",
                )
            ],
            model="claude-sonnet-5",
        )
        engine.provider_name = "anthropic"
        result = run_global_clean_source_analysis(
            analysis_env.project_name,
            dry_run=False,
            engine=engine,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
        )
        assert result.actual_real_calls == 1
        assert result.source_map_published is False
        assert result.stop_reason == "OUTPUT_TRUNCATED"
        assert result.transport_preserved == "PASS"
        assert not production_source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()

    def test_writer_gated_and_state_after_publication(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        calls = []
        real_write = __import__(
            "app.source_analysis.writer", fromlist=["write_source_map"]
        ).write_source_map

        def _tracked(path, payload):
            calls.append(True)
            return real_write(path, payload)

        monkeypatch.setattr("app.source_analysis.writer.write_source_map", _tracked)
        _sparse_env(analysis_env)
        engine = _routed_fake(list(SPARSE_KEEP))
        result = run_global_clean_source_analysis(
            analysis_env.project_name,
            dry_run=False,
            engine=engine,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
        )
        assert result.outcome == "PASS"
        assert result.pipeline_result == "PASS"
        assert result.source_map_published is True
        assert result.project_state_status == "completed"
        assert result.determinism == "PASS"
        assert result.determinism_sha_run1 == result.determinism_sha_run2
        assert result.transport_preserved == "PASS"
        assert result.invalid_tokens == []
        assert calls == [True]
        assert analysis_env.source_map_path.exists()
        leftover = analysis_env.partial_path
        assert leftover.exists() is False
        state = analysis_env.state()
        assert state["source_analysis"]["status"] == "completed"
        assert result.phase4_invoked is False

    def test_phase4_not_imported(self):
        import app.source_analysis_global_clean.runner as runner_module

        source = inspect.getsource(runner_module)
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        forbidden = {
            "app.editorial",
            "app.editorial_planning",
            "app.book_generation",
            "app.book_validation",
            "app.visual_design",
        }
        assert imported.isdisjoint(forbidden)
        for marker in ("create_editorial_plan", "run_editorial", "editorial_plan.json"):
            assert marker not in source
        assert "PHASE_3B_REAL_SOURCE_ANALYZER_CLEAN_REPORT.md" not in source
