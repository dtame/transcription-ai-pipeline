"""Écrit les artefacts A.24 isolés. N'écrase pas A.13–A.23. 0 provider réel."""

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
from app.source_analysis_v3_a22_forensics.constants import (
    A22_SIGNATURE,
    REPORT_NAME as A23_REPORT,
)
from app.source_analysis_v3_hardened_win004.constants import (
    AUTHORIZATION_SCOPE,
    COMPARISON_ARTIFACT,
    EXECUTION_ARTIFACT,
    EXPECTED_ANALYSIS_SIGNATURE,
    HANDLE_ARTIFACT,
    METADATA_ARTIFACT,
    PHASE,
    PREFLIGHT_ARTIFACT,
    PROJECT_NAME,
    PROTECTED_HISTORICAL,
    REPORT_NAME,
    SRC_ARTIFACT,
    WINDOW_ID,
)
from app.source_analysis_v3_hardened_win004.facts import protected_a24_historical_hashes
from app.source_analysis_v3_hardened_win004.runner import run_hardened_v3_win004
from app.source_analysis_v3_hardened_win004.window import load_candidate_win004
from app.source_analysis_v3_second_window.constants import REPORT_NAME as A22_REPORT

REAL_PROJECT = Path(r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation")


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_artifacts_without_touching_historical(tmp_path):
    before = protected_a24_historical_hashes()
    a22 = audit_dir(PROJECT_NAME) / A22_REPORT
    a23 = audit_dir(PROJECT_NAME) / A23_REPORT
    before_a22 = sha256_of_file(a22) if a22.is_file() else None
    before_a23 = sha256_of_file(a23) if a23.is_file() else None

    dry = run_hardened_v3_win004(
        PROJECT_NAME,
        dry_run=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        window_id=WINDOW_ID,
        artifact_sortie_dir=tmp_path,
        write_artifacts=True,
        tests="offline A.24",
    )
    assert dry.accepted is True
    assert dry.anthropic_post_attempts == 0
    assert (tmp_path / PROJECT_NAME / "audit" / PREFLIGHT_ARTIFACT).is_file()

    bundle = load_candidate_win004()
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
                request_id="fake-a24-audit",
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )
    executed = run_hardened_v3_win004(
        PROJECT_NAME,
        dry_run=False,
        execute_real=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        window_id=WINDOW_ID,
        engine=engine,
        allow_real_provider=False,
        artifact_sortie_dir=tmp_path,
        write_artifacts=True,
        tests="offline A.24",
    )
    assert executed.engine_generate_attempts == 1
    assert executed.anthropic_post_attempts == 0
    audit = tmp_path / PROJECT_NAME / "audit"
    assert (audit / EXECUTION_ARTIFACT).is_file()
    assert (audit / HANDLE_ARTIFACT).is_file()
    assert (audit / SRC_ARTIFACT).is_file()
    assert (audit / METADATA_ARTIFACT).is_file()
    assert (audit / COMPARISON_ARTIFACT).is_file()
    assert (audit / REPORT_NAME).is_file()
    report_text = (audit / REPORT_NAME).read_text(encoding="utf-8")
    assert "# PHASE 3B.7.7A.24 — REAL WIN004 HARDENED TYPE-CONTRACT RETRY" in report_text
    assert "PROMPT = window-analysis-1.3.2" in report_text
    assert "TRANSPORT = semantic-transport-v3" in report_text
    assert "AUTHORIZED TARGET = WIN004" in report_text
    assert "OTHER WINDOWS AUTHORIZED = NO" in report_text
    assert "SOURCE MAP = NOT PUBLISHED" in report_text
    assert "PRODUCTION DEFAULT = window-planner-v2.0" in report_text
    assert "IDEA KIND \"example\" =" in report_text
    assert executed.preflight["phase"] == PHASE
    assert not (tmp_path / PROJECT_NAME / "analysis" / "source_map.json").exists()
    assert not (tmp_path / PROJECT_NAME / "analysis" / "windows" / "WIN004").exists()

    after = protected_a24_historical_hashes()
    assert after == before
    if before_a22 is not None:
        assert sha256_of_file(a22) == before_a22
    if before_a23 is not None:
        assert sha256_of_file(a23) == before_a23
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
    assert "source_analysis_v3_hardened_win004" not in text
    main = Path(r"C:\TranscriptionAI\main.py")
    if main.is_file():
        assert "source_analysis_v3_hardened_win004" not in main.read_text(encoding="utf-8")


def test_candidate_isolation_uses_a24_signature_only(tmp_path):
    bundle = load_candidate_win004()
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
    executed = run_hardened_v3_win004(
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
        assert "v3_hardened_win004" in storage.get("cache", "")
        assert A22_SIGNATURE not in (storage.get("cache") or "")
        assert EXPECTED_ANALYSIS_SIGNATURE in (storage.get("cache") or "")
    assert not (
        tmp_path
        / PROJECT_NAME
        / "audit"
        / "canary"
        / "v3_second_window"
        / "a22_real_v3_second_window.lock"
    ).exists()


def test_historical_a22_a23_remain_immutable():
    a22 = REAL_PROJECT / "audit" / A22_REPORT
    a23 = REAL_PROJECT / "audit" / A23_REPORT
    assert a22.is_file()
    assert a23.is_file()
    a22_text = a22.read_text(encoding="utf-8")
    a23_text = a23.read_text(encoding="utf-8")
    assert "FAIL" in a22_text
    assert "PROMPT = window-analysis-1.3.1" in a22_text
    assert "window-analysis-1.3.2" in a23_text
    assert not REAL_PROJECT.joinpath("analysis", "source_map.json").exists()
