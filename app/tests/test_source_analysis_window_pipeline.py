"""
Phase 3B.7.2 — Window analysis pipeline with FakeAI.

Aucun réseau. Aucun engine.generate() vers un fournisseur réel.
Aucun source_map de production. Aucun Attempt #3.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.errors import AIError, AITimeoutError
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.ai.settings import resolve_stage_settings
from app.source_analysis.canonical_vocabulary import (
    GENERATION_C_ANTHROPIC_SHA256_3B43,
    GENERATION_C_RAW_SHA256_3B43,
    build_canonical_vocabulary_contract,
)
from app.source_analysis.errors import (
    SourceMapEditorialLeakError,
    WindowAnalysisError,
    WindowResultValidationError,
    WindowSourceRefError,
    WindowTransportValidationError,
    WindowTransportWriteError,
)
from app.source_analysis.prompt import (
    SOURCE_ANALYZER_PROMPT_VERSION,
    STRUCTURAL_VOCABULARY,
)
from app.source_analysis.ultra_compact_schema import (
    SEMANTIC_TRANSPORT_VERSION,
    build_ultra_compact_response_schema,
)
from app.source_analysis.window_analyzer import (
    WindowAnalysisHooks,
    analyze_window,
    build_window_ai_request,
)
from app.source_analysis.window_fixtures import (
    context_only_transport,
    deleted_src_transport,
    editorial_leak_transport,
    invalid_idea_kind_transport,
    invalid_kind_transport,
    invalid_link_transport,
    invalid_relation_transport,
    invalid_severity_transport,
    invalid_src_transport,
    invalid_vocabulary_transport,
    make_transcript,
    minimal_transport,
    owned_plus_context_transport,
    rich_transport,
    window_for,
)
from app.source_analysis.window_models import (
    STAGE_WINDOW,
    TARGET_MODEL,
    TARGET_PROVIDER,
    WINDOW_MAX_OUTPUT_TOKENS,
    assert_safe_window_id,
    make_window_input,
)
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
    WINDOW_PROMPT_ROLE,
    build_window_system_prompt,
    build_window_system_prompt_v10,
    build_window_user_prompt,
    window_prompt_fingerprint,
)
from app.source_analysis.window_signature import (
    WindowSignatureInputs,
    build_window_analysis_signature,
)
from app.source_analysis.window_validator import ownership_policy
from app.source_analysis.window_writer import (
    leftover_partial,
    result_path,
    transport_path,
)
from app.source_analysis_hybrid.constants import HARD_MAX_INPUT_TOKENS, PLANNER_VERSION
from app.source_analysis_hybrid.offline import assert_analyzer_not_wired
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.source_analysis_window_pipeline.cli import main as pipeline_cli
from app.source_analysis_window_pipeline.offline import assert_analyzer_not_wired as assert_window_not_wired
from app.source_analysis_window_pipeline.runner import (
    run_real_preflight,
    run_window_pipeline,
)
from app.source_analysis.writer import source_map_path
from app.tests.source_analysis_fixtures import (  # noqa: F401
    analysis_env,
    drop_segments,
    write_cleanup_provenance,
    write_transcript,
)

REAL_PROJECT = "pastoral_retreat_v2_validation"
REAL_CLEAN = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation"
    r"\transcripts\clean\transcript_data.json"
)


def _engine(transport: dict) -> FakeAIEngine:
    return FakeAIEngine(
        script=[FakeReply(parsed=transport)],
        retry_policy=no_delay_policy(max_attempts=1),
    )


def _analyze(tmp_path, transport, transcript=None, window=None, **kwargs):
    transcript = transcript or make_transcript(
        ("Faith changes the crossing of a trial.", "Trust is revealed.")
    )
    window = window or window_for(transcript)
    root = tmp_path / "windows"
    result = analyze_window(
        window,
        transcript,
        _engine(transport),
        windows_root=root,
        **kwargs,
    )
    return result, root, window, transcript


class TestWindowPrompt:
    def test_version_stable(self):
        assert WINDOW_ANALYSIS_PROMPT_VERSION == "window-analysis-1.1"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V10 == "window-analysis-1.0"
        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"
        assert WINDOW_ANALYSIS_PROMPT_VERSION != SOURCE_ANALYZER_PROMPT_VERSION
        assert build_window_system_prompt_v10("en") == build_window_system_prompt(
            "en", version=WINDOW_ANALYSIS_PROMPT_VERSION_V10
        )
        assert "GRANULARITÉ SÉMANTIQUE" not in build_window_system_prompt_v10("en")
        assert "GRANULARITÉ SÉMANTIQUE" in build_window_system_prompt("en")

    def test_deterministic_output(self):
        system = build_window_system_prompt("en")
        assert system == build_window_system_prompt("en")
        transcript = make_transcript(("one", "two"))
        window = window_for(transcript)
        user = build_window_user_prompt(transcript, window)
        assert user == build_window_user_prompt(transcript, window)

    def test_owned_and_context_sections(self):
        transcript = make_transcript(("owned text", "context text"))
        window = window_for(
            transcript, owned=("SRC000001",), context=("SRC000002",)
        )
        user = build_window_user_prompt(transcript, window)
        assert "OWNED SOURCES" in user
        assert "CONTEXT-ONLY SOURCES" in user
        assert "SRC000001" in user
        assert "SRC000002" in user
        assert "owned text" in user
        assert "context text" in user

    def test_empty_context_section_present(self):
        transcript = make_transcript(("only owned",))
        user = build_window_user_prompt(transcript, window_for(transcript))
        assert "CONTEXT-ONLY SOURCES" in user
        assert "none" in user.lower()

    def test_forbidden_editorial_instructions(self):
        system = build_window_system_prompt("en")
        for term in STRUCTURAL_VOCABULARY:
            assert term in system
        assert "chapitre" in system
        assert "SOURCE WINDOW ANALYST" in system or WINDOW_PROMPT_ROLE in system
        assert "CANDIDAT" in system or "CANDIDATES" in system

    def test_canonical_vocabulary_included(self):
        system = build_window_system_prompt("en")
        assert build_canonical_vocabulary_contract() in system
        assert "incomplete_reference" in system
        start = system.find("CONTROLLED_VOCABULARY_BEGIN")
        end = system.find("CONTROLLED_VOCABULARY_END")
        block = system[start:end]
        assert "incomplete_reference" in block
        assert "transcription_artifact" not in block

    def test_no_global_truth_claim(self):
        system = build_window_system_prompt("en")
        user = build_window_user_prompt(
            make_transcript(("x",)),
            window_for(make_transcript(("x",))),
        )
        combined = system + user
        assert "décision globale" in combined.lower() or "CANDIDAT" in combined
        assert "pas la vérité" in combined.lower() or "NOT" in combined
        assert "consolidateur" in combined.lower() or "consolidator" in combined.lower()


class TestWindowRequest:
    def test_generation_c_schema_and_targets(self):
        transcript = make_transcript(("Faith remains.",))
        window = window_for(transcript)
        bundle = build_window_ai_request(window, transcript)
        assert bundle.request.response_schema == build_ultra_compact_response_schema()
        assert bundle.request.wants_structured_output is True
        assert bundle.request.stage == STAGE_WINDOW
        assert bundle.request.max_output_tokens == WINDOW_MAX_OUTPUT_TOKENS
        assert bundle.settings.provider == TARGET_PROVIDER
        assert bundle.settings.model == TARGET_MODEL
        assert bundle.request.metadata["output_language"] == "en"
        assert bundle.signature

    def test_max_output_not_128000(self):
        assert WINDOW_MAX_OUTPUT_TOKENS == 32000
        assert WINDOW_MAX_OUTPUT_TOKENS != 128000


class TestValidTransport:
    def test_minimal_persists_transport_and_result(self, tmp_path, no_ai_network):
        result, root, window, _ = _analyze(tmp_path, minimal_transport())
        assert result.window_id == window.window_id
        assert transport_path("fixture", window.window_id, root=root).is_file()
        assert result_path("fixture", window.window_id, root=root).is_file()
        assert result.records[0].record_id == "WIN001:R0001"
        assert leftover_partial(transport_path("fixture", window.window_id, root=root)) is None

    def test_rich_fixture(self, tmp_path, no_ai_network):
        result, _, _, _ = _analyze(tmp_path, rich_transport())
        assert result.stats.topic_count == 2
        assert result.stats.idea_count >= 2
        assert result.stats.example_count == 1
        assert result.stats.reference_count == 1
        assert result.stats.uncertainty_count == 1
        assert result.stats.repetition_count == 1
        assert result.stats.voice_count >= 1
        assert result.stats.intent_kind_count == 1
        assert result.stats.audience_kind_count == 1
        assert result.candidates.scope == "WINDOW_CANDIDATE_ONLY"
        assert result.to_dict()["canonical_sourcemap"] is False


class TestInvalidTransport:
    def test_invalid_kind(self, tmp_path, no_ai_network):
        self._expect_fail(tmp_path, invalid_kind_transport())

    def test_invalid_idea_kind(self, tmp_path, no_ai_network):
        self._expect_fail(tmp_path, invalid_idea_kind_transport())

    def test_invalid_relation(self, tmp_path, no_ai_network):
        self._expect_fail(tmp_path, invalid_relation_transport())

    def test_invalid_uncertainty_kind(self, tmp_path, no_ai_network):
        self._expect_fail(tmp_path, invalid_vocabulary_transport())

    def test_invalid_severity(self, tmp_path, no_ai_network):
        self._expect_fail(tmp_path, invalid_severity_transport())

    def test_invalid_link(self, tmp_path, no_ai_network):
        self._expect_fail(tmp_path, invalid_link_transport())

    def test_invalid_src(self, tmp_path, no_ai_network):
        self._expect_fail(tmp_path, invalid_src_transport())

    def test_context_only_substantive(self, tmp_path, no_ai_network):
        transcript = make_transcript(("owned", "context only"))
        window = window_for(
            transcript, owned=("SRC000001",), context=("SRC000002",)
        )
        self._expect_fail(
            tmp_path,
            context_only_transport(context_src="SRC000002"),
            transcript=transcript,
            window=window,
        )

    def test_owned_plus_context_allowed(self, tmp_path, no_ai_network):
        transcript = make_transcript(("owned faith", "boundary"))
        window = window_for(
            transcript, owned=("SRC000001",), context=("SRC000002",)
        )
        result, _, _, _ = _analyze(
            tmp_path,
            owned_plus_context_transport(
                owned_src="SRC000001", context_src="SRC000002"
            ),
            transcript=transcript,
            window=window,
        )
        refs = result.records[1].source_refs
        assert "SRC000001" in refs
        assert "SRC000002" in refs

    def test_deleted_gap_src(self, tmp_path, no_ai_network):
        transcript = make_transcript(
            ("keep", "also keep"),
            src_ids=("SRC000001", "SRC000005"),
        )
        window = window_for(transcript, owned=("SRC000001", "SRC000005"))
        self._expect_fail(
            tmp_path,
            deleted_src_transport(deleted_src="SRC000003", owned_src="SRC000001"),
            transcript=transcript,
            window=window,
        )

    def test_editorial_leakage(self, tmp_path, no_ai_network):
        self._expect_fail(tmp_path, editorial_leak_transport())

    def _expect_fail(self, tmp_path, transport, transcript=None, window=None):
        transcript = transcript or make_transcript(
            ("Faith changes the crossing of a trial.", "Trust is revealed.")
        )
        window = window or window_for(transcript)
        root = tmp_path / "windows"
        engine = _engine(transport)
        with pytest.raises(
            (
                WindowTransportValidationError,
                WindowSourceRefError,
                WindowResultValidationError,
                WindowAnalysisError,
                SourceMapEditorialLeakError,
            )
        ):
            analyze_window(window, transcript, engine, windows_root=root)
        assert engine.call_count == 1
        assert transport_path("fixture", window.window_id, root=root).is_file()
        assert not result_path("fixture", window.window_id, root=root).exists()


class TestPersistenceAndOrder:
    def test_transport_first_if_decoder_fails(self, tmp_path, no_ai_network):
        transcript = make_transcript(("one",))
        window = window_for(transcript)
        root = tmp_path / "windows"
        order: list[str] = []

        def after_generate(_response):
            order.append("generate")

        def after_transport(_path):
            order.append("transport")
            assert _path.is_file()

        def before_decode(_payload):
            order.append("decode")

        with pytest.raises((WindowTransportValidationError, WindowSourceRefError)):
            analyze_window(
                window,
                transcript,
                _engine(invalid_vocabulary_transport()),
                windows_root=root,
                hooks=WindowAnalysisHooks(
                    after_generate=after_generate,
                    after_transport_write=after_transport,
                    before_decode=before_decode,
                ),
            )
        assert order == ["generate", "transport", "decode"]
        assert transport_path("fixture", window.window_id, root=root).is_file()
        assert not result_path("fixture", window.window_id, root=root).exists()

    def test_write_failure_stops_before_decode(self, tmp_path, no_ai_network, monkeypatch):
        transcript = make_transcript(("one",))
        window = window_for(transcript)
        decoded = {"called": False}

        def boom(*_args, **_kwargs):
            raise WindowTransportWriteError("disk full")

        def decode_should_not_run(*_args, **_kwargs):
            decoded["called"] = True
            raise AssertionError("decoder must not run")

        monkeypatch.setattr(
            "app.source_analysis.window_analyzer.write_window_transport", boom
        )
        monkeypatch.setattr(
            "app.source_analysis.window_analyzer.decode_window_transport",
            decode_should_not_run,
        )
        with pytest.raises(WindowTransportWriteError):
            analyze_window(
                window,
                transcript,
                _engine(minimal_transport()),
                windows_root=tmp_path / "windows",
            )
        assert decoded["called"] is False
        assert not result_path(
            "fixture", window.window_id, root=tmp_path / "windows"
        ).exists()

    def test_result_only_after_validation(self, tmp_path, no_ai_network):
        wrote = {"result": False}

        def before_result(result):
            wrote["result"] = True
            assert result.window_analysis_signature

        _analyze(
            tmp_path,
            minimal_transport(),
            hooks=WindowAnalysisHooks(before_result_write=before_result),
        )
        assert wrote["result"] is True

    def test_aierror_before_response(self, tmp_path, no_ai_network):
        transcript = make_transcript(("one",))
        window = window_for(transcript)
        root = tmp_path / "windows"
        engine = FakeAIEngine(
            script=[AITimeoutError("offline timeout")],
            retry_policy=no_delay_policy(max_attempts=1),
        )
        with pytest.raises(AIError):
            analyze_window(window, transcript, engine, windows_root=root)
        assert engine.call_count == 1
        assert not transport_path("fixture", window.window_id, root=root).exists()
        assert not result_path("fixture", window.window_id, root=root).exists()

    def test_keyboard_interrupt(self, tmp_path, no_ai_network):
        transcript = make_transcript(("one",))
        window = window_for(transcript)
        root = tmp_path / "windows"
        engine = FakeAIEngine(
            script=[KeyboardInterrupt()],
            retry_policy=no_delay_policy(max_attempts=1),
        )
        with pytest.raises(KeyboardInterrupt):
            analyze_window(window, transcript, engine, windows_root=root)
        assert not result_path("fixture", window.window_id, root=root).exists()

    def test_engine_required(self, tmp_path):
        transcript = make_transcript(("one",))
        with pytest.raises(WindowAnalysisError, match="injecté"):
            analyze_window(
                window_for(transcript),
                transcript,
                None,
                windows_root=tmp_path / "windows",
            )

    def test_one_fake_call_on_success(self, tmp_path, no_ai_network):
        transcript = make_transcript(("one",))
        window = window_for(transcript)
        engine = _engine(minimal_transport())
        analyze_window(
            window, transcript, engine, windows_root=tmp_path / "windows"
        )
        assert engine.call_count == 1


class TestDeterminism:
    def test_byte_identical_artifacts(self, tmp_path, no_ai_network):
        transcript = make_transcript(("Faith changes the crossing.",))
        window = window_for(transcript)
        a = tmp_path / "a"
        b = tmp_path / "b"
        analyze_window(window, transcript, _engine(minimal_transport()), windows_root=a)
        analyze_window(window, transcript, _engine(minimal_transport()), windows_root=b)
        t_a = transport_path("fixture", "WIN001", root=a).read_bytes()
        t_b = transport_path("fixture", "WIN001", root=b).read_bytes()
        r_a = result_path("fixture", "WIN001", root=a).read_bytes()
        r_b = result_path("fixture", "WIN001", root=b).read_bytes()
        assert t_a == t_b
        assert r_a == r_b
        assert b"generated_at" not in r_a
        assert b"timestamp" not in r_a


class TestSignature:
    def _inputs(self, **overrides) -> WindowSignatureInputs:
        base = dict(
            window_input_hash="h1",
            window_id="WIN001",
            transcript_id="TR001",
            transcript_sha256="t" * 64,
            planner_version=PLANNER_VERSION,
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
            prompt_sha256="p" * 64,
            transport_version=SEMANTIC_TRANSPORT_VERSION,
            response_schema_sha256="s" * 64,
            provider="anthropic",
            model="claude-sonnet-5",
            temperature=None,
            max_output_tokens=32000,
            output_language="en",
            context_safety_ratio=0.7,
        )
        base.update(overrides)
        return WindowSignatureInputs(**base)

    def test_mutations_invalidate(self):
        original = build_window_analysis_signature(self._inputs())
        mutations = [
            {"window_input_hash": "other"},
            {"prompt_version": "window-analysis-1.0"},
            {"prompt_sha256": "q" * 64},
            {"response_schema_sha256": "z" * 64},
            {"provider": "openai"},
            {"model": "other-model"},
            {"temperature": 0.2},
            {"max_output_tokens": 16000},
            {"output_language": "fr"},
            {"transcript_sha256": "u" * 64},
        ]
        for change in mutations:
            assert build_window_analysis_signature(self._inputs(**change)) != original

    def test_latency_not_in_signature(self):
        payload = self._inputs().to_dict()
        assert "latency" not in json.dumps(payload)
        assert "request_id" not in payload

    def test_source_content_changes_prompt_sha(self):
        left = make_transcript(("alpha",))
        right = make_transcript(("beta",), content_sha256="b" * 64)
        w_left = window_for(left)
        w_right = window_for(right)
        sha_left = window_prompt_fingerprint(
            build_window_system_prompt("en"),
            build_window_user_prompt(left, w_left),
        )
        sha_right = window_prompt_fingerprint(
            build_window_system_prompt("en"),
            build_window_user_prompt(right, w_right),
        )
        assert sha_left != sha_right


class TestStageIsolation:
    def test_editorial_stages_unchanged(self):
        source = resolve_stage_settings("source_analysis")
        assert source.provider == "anthropic"
        assert source.model == "claude-sonnet-5"
        assert source.max_output_tokens is None
        assert source.connect_timeout_seconds is None
        assert source.read_timeout_seconds is None
        editorial = resolve_stage_settings("editorial_planning")
        assert editorial.provider == "anthropic"
        assert editorial.model == "claude-opus-5"
        assert editorial.max_output_tokens is None
        book = resolve_stage_settings("book_generation")
        assert book.provider == "anthropic"
        assert book.model == "claude-sonnet-5"
        validation = resolve_stage_settings("book_validation")
        assert validation.provider == "openai"
        assert validation.model == "gpt-5.6-terra"
        window = resolve_stage_settings(STAGE_WINDOW)
        assert window.provider == TARGET_PROVIDER
        assert window.model == TARGET_MODEL
        assert window.max_output_tokens == 32000
        assert window.connect_timeout_seconds == 30.0
        assert window.read_timeout_seconds == 1800.0
        assert window.read_timeout_seconds != 7200

    def test_timeout_not_7200(self):
        window = resolve_stage_settings(STAGE_WINDOW)
        assert window.read_timeout_seconds == 1800.0


class TestSecurity:
    def test_window_id_path_rejection(self):
        with pytest.raises(Exception):
            assert_safe_window_id("../etc")
        with pytest.raises(Exception):
            assert_safe_window_id("WIN001/../x")
        with pytest.raises(Exception):
            make_window_input(
                make_transcript(("x",)),
                owned_src_refs=("SRC000001",),
                window_id="WIN..1",
            )

    def test_provider_cannot_choose_window_id(self, tmp_path, no_ai_network):
        result, _, window, _ = _analyze(tmp_path, minimal_transport())
        assert result.window_id == window.window_id == "WIN001"
        assert all(record.record_id.startswith("WIN001:") for record in result.records)

    def test_no_secrets_in_result(self, tmp_path, no_ai_network):
        result, root, window, _ = _analyze(tmp_path, minimal_transport())
        text = result_path("fixture", window.window_id, root=root).read_text(
            encoding="utf-8"
        )
        assert "sk-" not in text
        assert "ANTHROPIC" not in text
        assert "api_key" not in text.lower()


class TestIntegrity:
    def test_prompt_1_3_unchanged(self):
        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"

    def test_generation_c_unchanged(self):
        hashes = generation_c_hashes()
        assert hashes["raw_sha256"] == GENERATION_C_RAW_SHA256_3B43
        assert hashes["anthropic_sha256"] == GENERATION_C_ANTHROPIC_SHA256_3B43
        assert hashes["raw_matches_historical"] is True
        assert hashes["anthropic_matches_historical"] is True

    def test_analyzer_not_wired(self):
        assert_analyzer_not_wired()
        assert_window_not_wired()

    def test_decoder_reused_not_forked(self):
        from app.source_analysis.window_validator import decode_window_transport
        from app.source_analysis.semantic_transport_decoder import decode_to_canonical_raw

        assert decode_window_transport.__doc__
        assert decode_to_canonical_raw is not None

    def test_ownership_policy(self):
        policy = ownership_policy()
        assert policy["context_only_substantive_forbidden"] is True
        assert policy["mixed_owned_context_allowed"] is True
        assert policy["deleted_src_membership_only"] is True


class TestEndToEndFake:
    def test_planner_to_analyzer(self, tmp_path, no_ai_network):
        transcript = make_transcript(
            ("Faith changes how a trial is crossed.", "Trust remains.")
        )
        plan = plan_windows_v2(
            transcript,
            overhead=0,
            remeasure=False,
        )
        window = plan.windows[0]
        engine = _engine(minimal_transport(owned_src=window.owned_src_refs[0]))
        result = analyze_window(
            window, transcript, engine, windows_root=tmp_path / "windows"
        )
        assert engine.call_count == 1
        assert result.window_id == window.window_id
        assert transport_path(
            "fixture", window.window_id, root=tmp_path / "windows"
        ).is_file()


class TestCli:
    def test_rejects_real_call(self):
        assert pipeline_cli(["demo", "--real-call"]) == 2


@pytest.mark.skipif(not REAL_CLEAN.is_file(), reason="real clean transcript absent")
class TestRealWin001Preflight:
    def test_preflight_stops_before_generate(self, no_ai_network):
        from app.source_analysis_execution_strategy.windows import load_clean_transcript

        transcript = load_clean_transcript(REAL_PROJECT)
        plan = plan_windows_v2(transcript)
        assert plan.window_count == 3
        window = plan.windows[0]
        assert window.window_id == "WIN001"
        assert window.owned_src_count == 2787
        assert window.context_src_count == 0
        bundle = build_window_ai_request(window, transcript)
        assert bundle.request.wants_structured_output
        assert bundle.token_estimate["total_tokens"] <= HARD_MAX_INPUT_TOKENS
        assert not source_map_path(REAL_PROJECT).exists()
        preflight = run_real_preflight(REAL_PROJECT)
        assert preflight["would_call_ai"] is True
        assert preflight["actual_real_provider_calls"] == 0
        assert preflight["engine_generate"] is False
        assert preflight["owned_src_count"] == 2787
        assert preflight["within_hard_max"] is True
        assert Path(
            r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation"
            r"\analysis\windows"
        ).exists() is False

    def test_runner_writes_audit_only(self, no_ai_network):
        result = run_window_pipeline(REAL_PROJECT)
        assert result.outcome in {"PASS", "PARTIAL"}
        assert result.deterministic is True
        assert result.protected_unchanged is True
        assert result.artifact["execution"]["anthropic_calls"] == 0
        assert result.artifact["execution"]["source_map_published"] is False
        assert not source_map_path(REAL_PROJECT).exists()
        assert result.project_state_status not in {"SUCCESS", "completed"}
        again = run_window_pipeline(REAL_PROJECT)
        assert again.artifact_sha256 == result.artifact_sha256
