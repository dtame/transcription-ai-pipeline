"""Écrit les artefacts A.21 isolés. N'écrase pas A.13–A.20. 0 provider réel."""

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
from app.source_analysis_v3_a19_forensics.constants import REPORT_NAME as A20_REPORT
from app.source_analysis_v3_hardened_win001.constants import (
    AUTHORIZATION_SCOPE,
    COMPARISON_ARTIFACT,
    EXECUTION_ARTIFACT,
    HANDLE_ARTIFACT,
    PHASE,
    PREFLIGHT_ARTIFACT,
    PROJECT_NAME,
    PROTECTED_HISTORICAL,
    REPORT_NAME,
    SRC_ARTIFACT,
    WINDOW_ID,
)
from app.source_analysis_v3_hardened_win001.facts import protected_a21_historical_hashes
from app.source_analysis_v3_hardened_win001.runner import run_hardened_v3_win001
from app.source_analysis_v3_hardened_win001.window import load_candidate_win001
from app.source_analysis_v3_real_win001.constants import REPORT_NAME as A19_CANARY_REPORT

REAL_PROJECT = Path(r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation")


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_artifacts_without_touching_historical(tmp_path):
    before = protected_a21_historical_hashes()
    a19 = audit_dir(PROJECT_NAME) / A19_CANARY_REPORT
    a20 = audit_dir(PROJECT_NAME) / A20_REPORT
    before_a19 = sha256_of_file(a19) if a19.is_file() else None
    before_a20 = sha256_of_file(a20) if a20.is_file() else None

    dry = run_hardened_v3_win001(
        PROJECT_NAME,
        dry_run=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        window_id=WINDOW_ID,
        artifact_sortie_dir=tmp_path,
        write_artifacts=True,
        tests="offline A.21",
    )
    assert dry.accepted is True
    assert dry.anthropic_post_attempts == 0
    assert (tmp_path / PROJECT_NAME / "audit" / PREFLIGHT_ARTIFACT).is_file()

    bundle = load_candidate_win001()
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
                request_id="fake-a21-audit",
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )
    executed = run_hardened_v3_win001(
        PROJECT_NAME,
        dry_run=False,
        execute_real=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        window_id=WINDOW_ID,
        engine=engine,
        allow_real_provider=False,
        artifact_sortie_dir=tmp_path,
        write_artifacts=True,
        tests="offline A.21",
    )
    assert executed.engine_generate_attempts == 1
    assert executed.anthropic_post_attempts == 0
    audit = tmp_path / PROJECT_NAME / "audit"
    assert (audit / EXECUTION_ARTIFACT).is_file()
    assert (audit / HANDLE_ARTIFACT).is_file()
    assert (audit / SRC_ARTIFACT).is_file()
    assert (audit / COMPARISON_ARTIFACT).is_file()
    assert (audit / REPORT_NAME).is_file()
    report_text = (audit / REPORT_NAME).read_text(encoding="utf-8")
    assert "# PHASE 3B.7.7A.21 — REAL V3 SMALL WIN001 HARDENED RETRY" in report_text
    assert "PROMPT = window-analysis-1.3.1" in report_text
    assert "TRANSPORT = semantic-transport-v3" in report_text
    assert "WIN002 AUTHORIZED = NO" in report_text
    assert "SOURCE MAP = NOT PUBLISHED" in report_text
    assert "PRODUCTION DEFAULT = window-planner-v2.0" in report_text
    assert executed.preflight["phase"] == PHASE
    assert not (tmp_path / PROJECT_NAME / "analysis" / "source_map.json").exists()
    assert not (tmp_path / PROJECT_NAME / "analysis" / "windows" / "WIN001").exists()
    assert not (
        tmp_path / PROJECT_NAME / "audit" / "canary" / "v3_real_win001" / "v3_cache"
    ).exists()

    after = protected_a21_historical_hashes()
    assert after == before
    if before_a19 is not None:
        assert sha256_of_file(a19) == before_a19
    if before_a20 is not None:
        assert sha256_of_file(a20) == before_a20
    assert REAL_PROJECT.joinpath("analysis", "source_map.json").exists() is False
    for rel in PROTECTED_HISTORICAL:
        real = REAL_PROJECT / rel
        if real.is_file():
            assert sha256_of_file(real) == before.get(rel, sha256_of_file(real))


def test_network_isolation_and_production_untouched():
    assert not source_map_path(PROJECT_NAME).is_file()
    assert REAL_PROJECT.joinpath("analysis", "source_map.json").exists() is False
    analyzer = Path(r"C:\TranscriptionAI\app\source_analysis\analyzer.py")
    text = analyzer.read_text(encoding="utf-8")
    assert "source_analysis_v3_hardened_win001" not in text
    main = Path(r"C:\TranscriptionAI\main.py")
    if main.is_file():
        assert "source_analysis_v3_hardened_win001" not in main.read_text(encoding="utf-8")


def test_candidate_isolation_uses_a21_signature_only(tmp_path):
    bundle = load_candidate_win001()
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
    executed = run_hardened_v3_win001(
        PROJECT_NAME,
        dry_run=False,
        execute_real=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        window_id=WINDOW_ID,
        engine=engine,
        allow_real_provider=False,
        artifact_sortie_dir=tmp_path,
        write_artifacts=True,
    )
    storage = (executed.execution or {}).get("candidate_storage") or {}
    if storage:
        assert "v3_hardened_win001" in storage.get("cache", "")
        assert "e2b5019216624fac4b32dd5bd0b90e1a0cde860c805982dde0820a5ef47f3c1d" not in (
            storage.get("cache") or ""
        )
    assert not (
        tmp_path
        / PROJECT_NAME
        / "audit"
        / "canary"
        / "v3_real_win001"
        / "a19_real_v3_win001.lock"
    ).exists()


def test_real_a21_artifacts_if_present_stay_isolated():
    execution = REAL_PROJECT / "audit" / EXECUTION_ARTIFACT
    if not execution.is_file():
        pytest.skip("A.21 real execution artifact not present")
    payload = json.loads(execution.read_text(encoding="utf-8"))
    exe = payload.get("execution") or {}
    assert payload.get("anthropic_post_attempts") == 1
    assert exe.get("authorized_target") == "WIN001"
    assert exe.get("win002_authorized") is False
    assert exe.get("source_map") == "NOT PUBLISHED"
    assert exe.get("prompt_version") == "window-analysis-1.3.1"
    assert exe.get("a19_src_typo_class") == "ELIMINATED"
    assert not REAL_PROJECT.joinpath("analysis", "source_map.json").exists()
    assert not REAL_PROJECT.joinpath("analysis", "windows", "WIN001").exists()
    lock = (
        REAL_PROJECT
        / "audit"
        / "canary"
        / "v3_hardened_win001"
        / "a21_real_v3_hardened_win001.lock"
    )
    assert lock.is_file()
    a19_lock = (
        REAL_PROJECT / "audit" / "canary" / "v3_real_win001" / "a19_real_v3_win001.lock"
    )
    assert a19_lock.is_file()
    report = (REAL_PROJECT / "audit" / REPORT_NAME).read_text(encoding="utf-8")
    assert "REAL PROVIDER CALLS = 1" in report
    assert "PROMPT = window-analysis-1.3.1" in report
    assert "WIN002 AUTHORIZED = NO" in report
    assert "SOURCE MAP = NOT PUBLISHED" in report
    a19_report = REAL_PROJECT / "audit" / A19_CANARY_REPORT
    if a19_report.is_file():
        a19_text = a19_report.read_text(encoding="utf-8")
        assert "REAL V3 SMALL WIN001 SYMBOLIC-HANDLE CANARY" in a19_text
        assert "FAIL" in a19_text
