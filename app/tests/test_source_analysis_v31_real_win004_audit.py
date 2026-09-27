"""Écrit les artefacts A.27 isolés. N'écrase pas A.13–A.26.1. 0 provider réel."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_local_v3.fixtures import v31_success_transport
from app.source_analysis_v3_a22_forensics.constants import (
    A22_SIGNATURE,
    REPORT_NAME as A23_REPORT,
)
from app.source_analysis_v3_hardened_win004.constants import REPORT_NAME as A24_REPORT
from app.source_analysis_v31_local_lite.constants import REPORT_NAME as A26_REPORT
from app.source_analysis_v31_real_win004.constants import (
    AUTHORIZATION_SCOPE,
    COMPARISON_ARTIFACT,
    EXECUTION_ARTIFACT,
    EXPECTED_ANALYSIS_SIGNATURE,
    HANDLE_ARTIFACT,
    LOCAL_LITE_ARTIFACT,
    PHASE,
    PREFLIGHT_ARTIFACT,
    PROJECT_NAME,
    REPORT_NAME,
    SRC_ARTIFACT,
    WINDOW_ID,
)
from app.source_analysis_v31_real_win004.facts import protected_a27_historical_hashes
from app.source_analysis_v31_real_win004.runner import run_local_lite_win004
from app.source_analysis_v31_real_win004.window import load_candidate_win004
from app.source_analysis_v3_second_window.constants import REPORT_NAME as A22_REPORT


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_artifacts_without_touching_historical(tmp_path):
    before = protected_a27_historical_hashes()
    a22 = audit_dir(PROJECT_NAME) / A22_REPORT
    a23 = audit_dir(PROJECT_NAME) / A23_REPORT
    a24 = audit_dir(PROJECT_NAME) / A24_REPORT
    a26 = audit_dir(PROJECT_NAME) / A26_REPORT
    before_a22 = sha256_of_file(a22) if a22.is_file() else None
    before_a23 = sha256_of_file(a23) if a23.is_file() else None
    before_a24 = sha256_of_file(a24) if a24.is_file() else None
    before_a26 = sha256_of_file(a26) if a26.is_file() else None

    dry = run_local_lite_win004(
        PROJECT_NAME,
        dry_run=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        window_id=WINDOW_ID,
        artifact_sortie_dir=tmp_path,
        write_artifacts=True,
        tests="offline A.27",
    )
    assert dry.accepted is True
    assert dry.anthropic_post_attempts == 0
    assert (tmp_path / PROJECT_NAME / "audit" / PREFLIGHT_ARTIFACT).is_file()

    bundle = load_candidate_win004()
    owned = bundle["window"].owned_src_refs[0]
    transport = v31_success_transport(owned_src=owned)
    engine = FakeAIEngine(
        script=[
            FakeReply(
                text=json.dumps(transport, ensure_ascii=False),
                parsed=transport,
                finish_reason="end_turn",
                input_tokens=1000,
                output_tokens=200,
                thinking_tokens=0,
                request_id="fake-a27-audit",
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )
    executed = run_local_lite_win004(
        PROJECT_NAME,
        dry_run=False,
        execute_real=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        window_id=WINDOW_ID,
        engine=engine,
        allow_real_provider=False,
        artifact_sortie_dir=tmp_path,
        write_artifacts=True,
        tests="offline A.27",
    )
    assert executed.engine_generate_attempts == 1
    assert executed.anthropic_post_attempts == 0
    audit = tmp_path / PROJECT_NAME / "audit"
    assert (audit / EXECUTION_ARTIFACT).is_file()
    assert (audit / REPORT_NAME).is_file()
    report = (audit / REPORT_NAME).read_text(encoding="utf-8")
    assert report.startswith("# PHASE 3B.7.7A.27 — REAL WIN004 LOCAL-LITE CANARY")
    assert "TRANSPORT = semantic-transport-v3.1-local-lite" in report
    assert "PROMPT = window-analysis-1.4.0" in report
    assert PHASE == "3B.7.7A.27"

    after = protected_a27_historical_hashes()
    for key, digest in before.items():
        assert after.get(key) == digest
    if before_a22:
        assert sha256_of_file(a22) == before_a22
    if before_a23:
        assert sha256_of_file(a23) == before_a23
    if before_a24:
        assert sha256_of_file(a24) == before_a24
    if before_a26:
        assert sha256_of_file(a26) == before_a26
    assert not source_map_path(PROJECT_NAME).is_file()
    assert A22_SIGNATURE != EXPECTED_ANALYSIS_SIGNATURE


def test_candidate_isolation_requires_full_pass(tmp_path):
    bundle = load_candidate_win004()
    owned = bundle["window"].owned_src_refs[0]
    transport = v31_success_transport(owned_src=owned)
    engine = FakeAIEngine(
        script=[
            FakeReply(
                text=json.dumps(transport, ensure_ascii=False),
                parsed=transport,
                finish_reason="end_turn",
                input_tokens=1000,
                output_tokens=200,
                thinking_tokens=0,
                request_id="fake-a27-cache",
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )
    result = run_local_lite_win004(
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
    cache = (
        tmp_path
        / PROJECT_NAME
        / "audit"
        / "canary"
        / "v31_local_lite_win004"
        / "v31_cache"
        / EXPECTED_ANALYSIS_SIGNATURE
        / WINDOW_ID
    )
    if result.execution.get("result") != "PASS":
        assert not cache.exists() or not any(cache.iterdir())
    assert not source_map_path(PROJECT_NAME, sortie_dir=tmp_path).is_file()
