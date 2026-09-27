"""Écrit les artefacts A.22 isolés. N'écrase pas A.13–A.21. 0 provider réel."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_local_v3.fixtures import v3_success_transport
from app.source_analysis_v3_hardened_win001.constants import (
    EXPECTED_ANALYSIS_SIGNATURE as A21_SIGNATURE,
    REPORT_NAME as A21_REPORT,
)
from app.source_analysis_v3_second_window.constants import (
    AUTHORIZATION_SCOPE,
    COMPARISON_ARTIFACT,
    EXECUTION_ARTIFACT,
    HANDLE_ARTIFACT,
    PHASE,
    PREFERRED_WINDOW_ID,
    PREFLIGHT_ARTIFACT,
    PROJECT_NAME,
    PROTECTED_A21,
    PROTECTED_HISTORICAL,
    REPORT_NAME,
    REVIEW_ARTIFACT,
    SELECTION_ARTIFACT,
    SRC_ARTIFACT,
)
from app.source_analysis_v3_second_window.facts import protected_a22_historical_hashes
from app.source_analysis_v3_second_window.runner import run_second_window_canary
from app.source_analysis_v3_second_window.window import load_selected_window

REAL_PROJECT = Path(r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation")


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_artifacts_without_touching_historical(tmp_path):
    before = protected_a22_historical_hashes()
    a21 = audit_dir(PROJECT_NAME) / A21_REPORT
    before_a21 = sha256_of_file(a21) if a21.is_file() else None

    dry = run_second_window_canary(
        PROJECT_NAME,
        dry_run=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        window_id=PREFERRED_WINDOW_ID,
        artifact_sortie_dir=tmp_path,
        write_artifacts=True,
        tests="offline A.22",
    )
    assert dry.accepted is True
    assert dry.anthropic_post_attempts == 0
    assert (tmp_path / PROJECT_NAME / "audit" / PREFLIGHT_ARTIFACT).is_file()
    assert (tmp_path / PROJECT_NAME / "audit" / SELECTION_ARTIFACT).is_file()

    bundle = load_selected_window()
    owned = bundle["window"].owned_src_refs[0]
    transport = v3_success_transport(owned_src=owned)
    engine = FakeAIEngine(
        script=[
            FakeReply(
                text=json.dumps(transport, ensure_ascii=False),
                parsed=transport,
                finish_reason="end_turn",
                input_tokens=1000,
                output_tokens=200,
                thinking_tokens=0,
                request_id="fake-a22-audit",
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )
    executed = run_second_window_canary(
        PROJECT_NAME,
        dry_run=False,
        execute_real=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        window_id=PREFERRED_WINDOW_ID,
        engine=engine,
        allow_real_provider=False,
        artifact_sortie_dir=tmp_path,
        write_artifacts=True,
        tests="offline A.22",
    )
    assert executed.engine_generate_attempts == 1
    assert executed.anthropic_post_attempts == 0
    audit = tmp_path / PROJECT_NAME / "audit"
    assert (audit / EXECUTION_ARTIFACT).is_file()
    assert (audit / HANDLE_ARTIFACT).is_file()
    assert (audit / SRC_ARTIFACT).is_file()
    assert (audit / COMPARISON_ARTIFACT).is_file()
    assert (audit / REVIEW_ARTIFACT).is_file()
    assert (audit / REPORT_NAME).is_file()
    report_text = (audit / REPORT_NAME).read_text(encoding="utf-8")
    assert "# PHASE 3B.7.7A.22 — SECOND INDEPENDENT REAL-WINDOW CANARY" in report_text
    assert "PROMPT = window-analysis-1.3.1" in report_text
    assert "TRANSPORT = semantic-transport-v3" in report_text
    assert "OTHER WINDOWS AUTHORIZED = NO" in report_text
    assert "SOURCE MAP = NOT PUBLISHED" in report_text
    assert "PRODUCTION DEFAULT = window-planner-v2.0" in report_text
    assert "SELECTED TARGET = WIN004" in report_text
    assert executed.preflight["phase"] == PHASE
    assert not (tmp_path / PROJECT_NAME / "analysis" / "source_map.json").exists()
    assert not (tmp_path / PROJECT_NAME / "analysis" / "windows" / "WIN004").exists()
    assert not (
        tmp_path / PROJECT_NAME / "audit" / "canary" / "v3_hardened_win001" / "v3_cache"
    ).exists()

    after = protected_a22_historical_hashes()
    assert after == before
    if before_a21 is not None:
        assert sha256_of_file(a21) == before_a21
    assert REAL_PROJECT.joinpath("analysis", "source_map.json").exists() is False
    for rel in PROTECTED_HISTORICAL:
        real = REAL_PROJECT / rel
        if real.is_file():
            assert sha256_of_file(real) == before.get(rel, sha256_of_file(real))
    for rel in PROTECTED_A21:
        real = REAL_PROJECT / rel
        if real.is_file():
            assert sha256_of_file(real) == before.get(rel, sha256_of_file(real))


def test_network_isolation_and_production_untouched():
    assert not source_map_path(PROJECT_NAME).is_file()
    assert REAL_PROJECT.joinpath("analysis", "source_map.json").exists() is False
    analyzer = Path(r"C:\TranscriptionAI\app\source_analysis\analyzer.py")
    text = analyzer.read_text(encoding="utf-8")
    assert "source_analysis_v3_second_window" not in text
    main = Path(r"C:\TranscriptionAI\main.py")
    if main.is_file():
        assert "source_analysis_v3_second_window" not in main.read_text(encoding="utf-8")


def test_candidate_isolation_uses_a22_signature_only(tmp_path):
    bundle = load_selected_window()
    owned = bundle["window"].owned_src_refs[0]
    transport = v3_success_transport(owned_src=owned)
    engine = FakeAIEngine(
        script=[
            FakeReply(
                text=json.dumps(transport, ensure_ascii=False),
                parsed=transport,
                finish_reason="end_turn",
                thinking_tokens=0,
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )
    executed = run_second_window_canary(
        PROJECT_NAME,
        dry_run=False,
        execute_real=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        window_id=PREFERRED_WINDOW_ID,
        engine=engine,
        allow_real_provider=False,
        artifact_sortie_dir=tmp_path,
        write_artifacts=True,
    )
    storage = (executed.execution or {}).get("candidate_storage") or {}
    if storage:
        assert "v3_second_window" in storage.get("cache", "")
        assert A21_SIGNATURE not in (storage.get("cache") or "")
        assert "WIN001" not in (storage.get("cache") or "")
    assert not (
        tmp_path
        / PROJECT_NAME
        / "audit"
        / "canary"
        / "v3_hardened_win001"
        / "a21_real_v3_hardened_win001.lock"
    ).exists()


def test_real_a21_artifacts_if_present_stay_isolated():
    a21_execution = REAL_PROJECT / "audit" / "source_analysis_v3_hardened_win001_execution.json"
    if not a21_execution.is_file():
        pytest.skip("A.21 real execution artifact not present")
    payload = json.loads(a21_execution.read_text(encoding="utf-8"))
    exe = payload.get("execution") or {}
    assert payload.get("anthropic_post_attempts") == 1
    assert exe.get("authorized_target") == "WIN001"
    assert exe.get("result") == "PASS"
    assert not REAL_PROJECT.joinpath("analysis", "source_map.json").exists()
    lock = (
        REAL_PROJECT
        / "audit"
        / "canary"
        / "v3_hardened_win001"
        / "a21_real_v3_hardened_win001.lock"
    )
    assert lock.is_file()
    report = (REAL_PROJECT / "audit" / A21_REPORT).read_text(encoding="utf-8")
    assert "REAL PROVIDER CALLS = 1" in report
    assert "PROMPT = window-analysis-1.3.1" in report
    a22_lock = (
        REAL_PROJECT / "audit" / "canary" / "v3_second_window" / "a22_real_v3_second_window.lock"
    )
    if a22_lock.is_file():
        a22_execution = REAL_PROJECT / "audit" / EXECUTION_ARTIFACT
        assert a22_execution.is_file()
        a22_payload = json.loads(a22_execution.read_text(encoding="utf-8"))
        a22_exe = a22_payload.get("execution") or {}
        assert a22_payload.get("anthropic_post_attempts") == 1
        assert a22_exe.get("authorized_target") == PREFERRED_WINDOW_ID
        assert a22_exe.get("authorized_target") != "WIN001"
        assert a22_exe.get("real_windows_ready") == "1 / 7"
        assert not (
            REAL_PROJECT / "audit" / "canary" / "v3_second_window" / "v3_cache"
        ).exists()
        assert exe.get("result") == "PASS"
