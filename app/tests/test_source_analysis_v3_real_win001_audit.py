"""Écrit les artefacts A.19 isolés. N'écrase pas A.13–A.18. 0 provider réel."""

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
from app.source_analysis_v2_real_win001.constants import REPORT_NAME as A15_REPORT
from app.source_analysis_v3_real_win001.constants import (
    AUTHORIZATION_SCOPE,
    COMPARISON_ARTIFACT,
    EXECUTION_ARTIFACT,
    HANDLE_ARTIFACT,
    PHASE,
    PREFLIGHT_ARTIFACT,
    PROJECT_NAME,
    PROTECTED_HISTORICAL,
    REPORT_NAME,
    REVIEW_ARTIFACT,
    WINDOW_ID,
)
from app.source_analysis_v3_real_win001.facts import protected_a19_historical_hashes
from app.source_analysis_v3_real_win001.runner import run_real_v3_win001
from app.source_analysis_v3_real_win001.window import load_candidate_win001
from app.source_analysis_v3_symbolic_grammar_canary.constants import (
    REPORT_NAME as A18_REPORT,
)
from app.source_analysis_v3_symbolic_handles.constants import REPORT_NAME as A17_REPORT

REAL_PROJECT = Path(r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation")


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_artifacts_without_touching_historical(tmp_path):
    before = protected_a19_historical_hashes()
    a15 = audit_dir(PROJECT_NAME) / A15_REPORT
    a17 = audit_dir(PROJECT_NAME) / A17_REPORT
    a18 = audit_dir(PROJECT_NAME) / A18_REPORT
    before_a15 = sha256_of_file(a15) if a15.is_file() else None
    before_a17 = sha256_of_file(a17) if a17.is_file() else None
    before_a18 = sha256_of_file(a18) if a18.is_file() else None

    dry = run_real_v3_win001(
        PROJECT_NAME,
        dry_run=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        window_id=WINDOW_ID,
        artifact_sortie_dir=tmp_path,
        write_artifacts=True,
        tests="offline A.19",
    )
    assert dry.accepted is True
    assert dry.anthropic_post_attempts == 0
    preflight_path = (
        tmp_path / PROJECT_NAME / "audit" / PREFLIGHT_ARTIFACT
    )
    assert preflight_path.is_file()

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
                request_id="fake-a19-audit",
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )
    executed = run_real_v3_win001(
        PROJECT_NAME,
        dry_run=False,
        execute_real=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        window_id=WINDOW_ID,
        engine=engine,
        allow_real_provider=False,
        artifact_sortie_dir=tmp_path,
        write_artifacts=True,
        tests="offline A.19",
    )
    assert executed.engine_generate_attempts == 1
    assert executed.anthropic_post_attempts == 0
    audit = tmp_path / PROJECT_NAME / "audit"
    assert (audit / EXECUTION_ARTIFACT).is_file()
    assert (audit / HANDLE_ARTIFACT).is_file()
    assert (audit / REPORT_NAME).is_file()
    report_text = (audit / REPORT_NAME).read_text(encoding="utf-8")
    assert "# PHASE 3B.7.7A.19 — REAL V3 SMALL WIN001 SYMBOLIC-HANDLE CANARY" in report_text
    assert "PROMPT = window-analysis-1.3" in report_text
    assert "TRANSPORT = semantic-transport-v3" in report_text
    assert "WIN002 AUTHORIZED = NO" in report_text
    assert "SOURCE MAP = NOT PUBLISHED" in report_text
    assert "PRODUCTION DEFAULT = window-planner-v2.0" in report_text
    assert executed.preflight["phase"] == PHASE
    assert not (tmp_path / PROJECT_NAME / "analysis" / "source_map.json").exists()
    assert not (tmp_path / PROJECT_NAME / "analysis" / "windows" / "WIN001").exists()
    assert not (tmp_path / PROJECT_NAME / "audit" / "canary" / "v2_cache").exists()

    after = protected_a19_historical_hashes()
    assert after == before
    if before_a15 is not None:
        assert sha256_of_file(a15) == before_a15
    if before_a17 is not None:
        assert sha256_of_file(a17) == before_a17
    if before_a18 is not None:
        assert sha256_of_file(a18) == before_a18
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
    assert "source_analysis_v3_real_win001" not in text
    main = Path(r"C:\TranscriptionAI\main.py")
    if main.is_file():
        assert "source_analysis_v3_real_win001" not in main.read_text(encoding="utf-8")


def test_real_a19_artifacts_if_present_stay_isolated():
    execution = REAL_PROJECT / "audit" / EXECUTION_ARTIFACT
    if not execution.is_file():
        pytest.skip("A.19 real execution artifact not present")
    payload = json.loads(execution.read_text(encoding="utf-8"))
    exe = payload.get("execution") or {}
    assert payload.get("anthropic_post_attempts") == 1
    assert exe.get("authorized_target") == "WIN001"
    assert exe.get("win002_authorized") is False
    assert exe.get("source_map") == "NOT PUBLISHED"
    assert exe.get("candidate_storage") in ({}, None)
    assert not REAL_PROJECT.joinpath("analysis", "source_map.json").exists()
    assert not REAL_PROJECT.joinpath("analysis", "windows", "WIN001").exists()
    assert not REAL_PROJECT.joinpath(
        "audit", "canary", "v3_real_win001", "v3_windows", "WIN001", "transport.json"
    ).exists()
    lock = REAL_PROJECT / "audit" / "canary" / "v3_real_win001" / "a19_real_v3_win001.lock"
    assert lock.is_file()
    report = (REAL_PROJECT / "audit" / REPORT_NAME).read_text(encoding="utf-8")
    assert "REAL PROVIDER CALLS = 1" in report
    assert "WIN002 AUTHORIZED = NO" in report
    assert "SOURCE MAP = NOT PUBLISHED" in report
