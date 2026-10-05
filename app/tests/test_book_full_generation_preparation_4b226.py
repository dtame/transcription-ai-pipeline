"""Phase 4B.2.26 — offline acceptance, normalizer, and 13-chapter readiness."""

from __future__ import annotations

from copy import deepcopy

import pytest

from app.book_ch002_offline_recovery_4b224.chapter_io import load_json, paragraph_ids
from app.book_full_generation_preparation_4b226.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    CH002_REMOVED_EMPTY_PARAGRAPH,
    CONSUMED_4B225_SCOPE,
    FAITHFUL_PROMPT_1_1_ACTIVATED,
    FUTURE_AUTHORIZATION_ACTIVATED,
    FUTURE_AUTHORIZATION_SCOPE,
    PUBLICATION_AUTHORIZED,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
    REMAINING_CHAPTER_IDS,
)
from app.book_full_generation_preparation_4b226.guard import (
    BookFullGenerationPreparation4226Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_full_generation_preparation_4b226.hashes import snapshot
from app.book_full_generation_preparation_4b226.lock import (
    SimulationLockStore,
    next_admissible_chapter,
)
from app.book_full_generation_preparation_4b226.normalize import (
    normalize_empty_paragraphs,
    normalize_empty_paragraphs_idempotent,
)
from app.book_full_generation_preparation_4b226.paths import (
    ch001_approved_json_path,
    ch002_approved_json_path,
    ch002_original_json_path,
    production_book_path,
)
from app.book_full_generation_preparation_4b226.runner import run_phase
from app.book_full_generation_preparation_4b226.scenarios import evaluate_normalizer_tests
from app.book_generation.constants import BOOK_GENERATOR_PROMPT_VERSION
from app.book_generation.prompt import FROZEN_PROMPT_SHA256, prompt_bundle as frozen_v10
from app.book_generation.prompt_select import resolve_prompt_module
from app.book_generation.prompt_v101 import prompt_bundle as frozen_v101
from app.book_generation_4b223.constants import FAITHFUL_PROMPT_1_1


def test_offline_authorizations_and_prompt_isolation():
    assert PUBLICATION_AUTHORIZED is False
    assert REAL_CHAPTER_GENERATION_AUTHORIZED is False
    assert AUTHORIZED_ANTHROPIC_CALLS == 0
    assert AUTHORIZED_OPENAI_CALLS == 0
    assert AUTHORIZED_SONNET_CALLS == 0
    assert AUTHORIZED_TERRA_CALLS == 0
    assert FAITHFUL_PROMPT_1_1_ACTIVATED is False
    assert FUTURE_AUTHORIZATION_ACTIVATED is False
    assert_offline_only()
    with pytest.raises(ValueError):
        resolve_prompt_module(FAITHFUL_PROMPT_1_1)
    assert frozen_v10()["prompt_sha256"] == FROZEN_PROMPT_SHA256
    assert frozen_v101()["version"] == BOOK_GENERATOR_PROMPT_VERSION == "book-generator-1.0.1"


def test_consumed_and_future_scopes_are_rejected():
    validate_authorization_scope(AUTHORIZATION_SCOPE)
    with pytest.raises(BookFullGenerationPreparation4226Error):
        validate_authorization_scope(CONSUMED_4B225_SCOPE)
    with pytest.raises(BookFullGenerationPreparation4226Error):
        validate_authorization_scope(FUTURE_AUTHORIZATION_SCOPE)
    with pytest.raises(BookFullGenerationPreparation4226Error):
        validate_authorization_scope("WRONG")


def test_canonical_and_accepted_hashes():
    snap = snapshot()
    assert snap["canonical_match_expected"] is True
    assert snap["six_accepted_immutable"] is True
    assert production_book_path().is_file() is False


def test_remaining_order_excludes_accepted():
    assert REMAINING_CHAPTER_IDS == (
        "CH005",
        "CH006",
        "CH007",
        "CH008",
        "CH009",
        "CH010",
        "CH011",
        "CH013",
        "CH014",
        "CH015",
        "CH016",
        "CH017",
        "CH019",
    )
    assert "CH001" not in REMAINING_CHAPTER_IDS
    assert "CH003" not in REMAINING_CHAPTER_IDS
    assert "CH012" not in REMAINING_CHAPTER_IDS


def test_normalizer_matrix_offline():
    report = evaluate_normalizer_tests()
    failed = [row["name"] for row in report["rows"] if not row["ok"]]
    assert report["failed"] == 0, failed


def test_ch002_historical_matches_recovered_ids():
    original = load_json(ch002_original_json_path())
    recovered = load_json(ch002_approved_json_path())
    result = normalize_empty_paragraphs(original, protect_accepted=False)
    assert CH002_REMOVED_EMPTY_PARAGRAPH in result["removed_paragraph_ids"]
    assert set(result["derived_paragraph_ids"]) == set(paragraph_ids(recovered))
    assert result["ids_renumbered"] is False
    second = normalize_empty_paragraphs_idempotent(result["derived"], protect_accepted=False)
    assert second["idempotent"] is True


def test_accepted_ch001_is_protected():
    payload = load_json(ch001_approved_json_path())
    before = deepcopy(payload)
    result = normalize_empty_paragraphs(payload, protect_accepted=True)
    assert result["changed"] is False
    assert result["accepted_chapter_protected"] is True
    assert paragraph_ids(result["derived"]) == paragraph_ids(before)


def test_uncertain_lock_is_never_replayed():
    store = SimulationLockStore()
    store.transition("CH005", state="RESPONSE_VALIDATED", note="already done")
    store.transition("CH006", state="UNCERTAIN", note="uncertain")
    nxt = next_admissible_chapter(
        chapter_ids=REMAINING_CHAPTER_IDS,
        store=store,
        accepted_ids=("CH001", "CH002", "CH003", "CH004", "CH012", "CH018"),
    )
    assert nxt["blocked"] is True
    assert "CH006_UNCERTAIN" in str(nxt.get("reason") or "")
    with pytest.raises(BookFullGenerationPreparation4226Error):
        store.transition("CH006", state="PREFLIGHT_VALIDATED", note="replay")


def test_phase_runner_offline_without_writing_when_requested(tmp_path):
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        write_artifacts=False,
        run_tests=False,
    )
    header = result.bundle["header"]
    assert header["provider_calls"] == 0
    assert header["anthropic_http"] == 0
    assert header["openai_http"] == 0
    assert header["ch003_human_acceptance"] == "RECORDED"
    assert header["ch004_human_acceptance"] == "RECORDED"
    assert header["production_validator"] == "UNCHANGED"
    assert result.bundle["full_batch_offline_simulation"]["chapters_generated"] == 0
