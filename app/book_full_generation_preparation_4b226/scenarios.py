"""Offline regression scenarios. No HTTP. No generation."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.book_ch002_offline_recovery_4b224.chapter_io import (
    idea_handles,
    load_json,
    paragraph_ids,
)
from app.book_full_generation_preparation_4b226.constants import (
    ACCEPTED_CHAPTER_IDS,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    CH002_REMOVED_EMPTY_PARAGRAPH,
    PHASE,
    REMAINING_CHAPTER_IDS,
)
from app.book_full_generation_preparation_4b226.guard import assert_offline_only
from app.book_full_generation_preparation_4b226.hashes import snapshot
from app.book_full_generation_preparation_4b226.inventory import chapter_spec_from_plan
from app.book_full_generation_preparation_4b226.normalize import (
    inspect_paragraph,
    normalize_empty_paragraphs,
    normalize_empty_paragraphs_idempotent,
    removal_is_admissible,
)
from app.book_full_generation_preparation_4b226.paths import (
    accepted_chapter_json_path,
    ch001_approved_json_path,
    ch002_approved_json_path,
    ch002_original_json_path,
    ch002_original_raw_path,
    ch003_approved_json_path,
    ch004_approved_json_path,
    ch018_json_path,
    production_book_path,
)
from app.book_full_generation_preparation_4b226.pipeline import normalize_then_validate
from app.book_scale_up_preparation_4b220.context import build_chapter_source_context
from app.book_scale_up_preparation_4b220.corpus import load_canonical_corpus


def _para(paragraph_id: str, text: str = "", **extra: Any) -> dict[str, Any]:
    payload = {
        "paragraph_id": paragraph_id,
        "text": text,
        "kind": "con" if not str(text).strip() else "sub",
        "evidence_handles": extra.pop("evidence_handles", []),
        "source_refs": extra.pop("source_refs", []),
        "idea_refs": extra.pop("idea_refs", []),
        "example_refs": extra.pop("example_refs", []),
        "reference_refs": extra.pop("reference_refs", []),
        "uncertainty_refs": extra.pop("uncertainty_refs", []),
    }
    payload.update(extra)
    return payload


def _chapter(paragraphs: list[dict[str, Any]], chapter_id: str = "CH099") -> dict[str, Any]:
    return {
        "chapter_id": chapter_id,
        "title": "Fixture",
        "sections": [
            {
                "section_id": "SEC001",
                "title": "Section",
                "paragraphs": paragraphs,
                "idea_refs": [],
                "source_refs": [],
            }
        ],
        "idea_refs": [],
        "source_refs": [],
        "provider_raw_sha256": "raw-immutable-fixture",
    }


def _kept(result: dict[str, Any], paragraph_id: str) -> bool:
    return paragraph_id in result["derived_paragraph_ids"]


def _removed(result: dict[str, Any], paragraph_id: str) -> bool:
    return paragraph_id in result["removed_paragraph_ids"]


def evaluate_normalizer_tests() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    def _row(name: str, ok: bool, detail: str) -> None:
        rows.append({"name": name, "ok": ok, "detail": detail})

    raw = {"parsed": {"untouched": True}, "text": "RAW"}
    nonempty = _para("P000001", "A teaching that must stay.")
    empty = _para("P000099", "")

    r1 = normalize_empty_paragraphs(
        _chapter([nonempty, empty]), raw_response=raw, protect_accepted=False
    )
    _row(
        "empty_without_provenance_removed",
        _removed(r1, "P000099") and _kept(r1, "P000001"),
        "strict empty unprovenanced paragraph deleted",
    )

    r2 = normalize_empty_paragraphs(
        _chapter([nonempty, _para("P000098", "   \n\t")]),
        protect_accepted=False,
    )
    _row(
        "whitespace_without_provenance_removed",
        _removed(r2, "P000098") and _kept(r2, "P000001"),
        "whitespace-only unprovenanced paragraph deleted",
    )

    with_idea = _para("P000097", "", evidence_handles=["IDEA001"], idea_refs=["IDEA001"])
    r3 = normalize_empty_paragraphs(_chapter([nonempty, with_idea]), protect_accepted=False)
    _row(
        "empty_with_idea_kept",
        _kept(r3, "P000097") and not _removed(r3, "P000097"),
        "empty paragraph with IDEA conserved",
    )

    with_src = _para("P000096", "", evidence_handles=["SRC000001"], source_refs=["SRC000001"])
    r4 = normalize_empty_paragraphs(_chapter([nonempty, with_src]), protect_accepted=False)
    _row("empty_with_src_kept", _kept(r4, "P000096"), "empty paragraph with SRC conserved")

    with_ex = _para("P000095", "", evidence_handles=["EX001"], example_refs=["EX001"])
    r5 = normalize_empty_paragraphs(_chapter([nonempty, with_ex]), protect_accepted=False)
    _row("empty_with_ex_kept", _kept(r5, "P000095"), "empty paragraph with EX conserved")

    with_ref = _para("P000094", "", evidence_handles=["REF001"], reference_refs=["REF001"])
    r6 = normalize_empty_paragraphs(_chapter([nonempty, with_ref]), protect_accepted=False)
    _row("empty_with_ref_kept", _kept(r6, "P000094"), "empty paragraph with REF conserved")

    with_unc = _para("P000093", "", evidence_handles=["UNC001"], uncertainty_refs=["UNC001"])
    r7 = normalize_empty_paragraphs(_chapter([nonempty, with_unc]), protect_accepted=False)
    _row("empty_with_unc_kept", _kept(r7, "P000093"), "empty paragraph with UNC conserved")

    with_attr = _para("P000092", "", attribution="speaker")
    r8 = normalize_empty_paragraphs(_chapter([nonempty, with_attr]), protect_accepted=False)
    _row(
        "empty_with_attribution_kept",
        _kept(r8, "P000092"),
        "empty paragraph with attribution conserved",
    )

    with_unknown = _para("P000091", "", editorial_note="keep-by-default")
    r9 = normalize_empty_paragraphs(_chapter([nonempty, with_unknown]), protect_accepted=False)
    _row(
        "empty_with_unknown_metadata_kept",
        _kept(r9, "P000091"),
        "empty paragraph with unknown metadata conserved by default",
    )

    referenced = _para("P000090", "")
    pointer = _para("P000002", "See P000090 for the missing connective.")
    r10 = normalize_empty_paragraphs(
        _chapter([referenced, pointer]), protect_accepted=False
    )
    _row(
        "referenced_paragraph_kept",
        _kept(r10, "P000090"),
        "empty paragraph referenced elsewhere conserved",
    )

    with_cite = _para("P000089", "", citation="John 11:25")
    r11 = normalize_empty_paragraphs(_chapter([nonempty, with_cite]), protect_accepted=False)
    _row("empty_with_citation_kept", _kept(r11, "P000089"), "empty paragraph with citation conserved")

    e1 = _para("P000088", "")
    e2 = _para("P000087", "")
    keep = _para("P000003", "Keep this teaching.")
    r12 = normalize_empty_paragraphs(_chapter([e1, keep, e2]), protect_accepted=False)
    _row(
        "multiple_independent_empties_removed",
        _removed(r12, "P000088") and _removed(r12, "P000087") and _kept(r12, "P000003"),
        "independent empty paragraphs removed without touching others",
    )

    _row(
        "non_empty_paragraphs_unchanged",
        r12["derived"]["sections"][0]["paragraphs"][0]["text"] == "Keep this teaching."
        and r12["other_paragraphs_modified"] is False,
        "non-empty paragraphs were not rewritten",
    )
    _row(
        "identifiers_not_renumbered",
        r12["ids_renumbered"] is False and r12["derived_paragraph_ids"] == ["P000003"],
        "remaining identifiers were not renumbered",
    )

    r15 = normalize_empty_paragraphs_idempotent(r12["derived"], protect_accepted=False)
    _row(
        "idempotent",
        r15.get("idempotent") is True and r15["changed"] is False,
        "second pass removes nothing",
    )
    _row(
        "raw_response_unchanged",
        r1["raw_response_unchanged"] is True and r1["raw_response"] == raw,
        "raw provider payload was not mutated",
    )

    original_ch002 = load_json(ch002_original_json_path())
    recovered_ch002 = load_json(ch002_approved_json_path())
    raw_ch002 = load_json(ch002_original_raw_path())
    hist = normalize_empty_paragraphs(
        original_ch002, raw_response=raw_ch002, protect_accepted=False
    )
    hist_ids = set(hist["derived_paragraph_ids"])
    recovered_ids = set(paragraph_ids(recovered_ch002))
    _row(
        "ch002_historical_equivalent_to_4b224",
        CH002_REMOVED_EMPTY_PARAGRAPH in hist["removed_paragraph_ids"]
        and hist_ids == recovered_ids
        and hist["idea_coverage_unchanged"] is True
        and hist["ids_renumbered"] is False,
        "historical CH002 derived result matches 4B.2.24 recovery identifiers",
    )

    corpus = load_canonical_corpus()
    spec002 = chapter_spec_from_plan("CH002", corpus=corpus)
    built002 = build_chapter_source_context("CH002", corpus=corpus)
    pipeline002 = normalize_then_validate(
        original_ch002,
        plan=corpus.plan,
        source_map=corpus.source_map,
        editorial_chapter=next(
            item for item in corpus.plan.chapters if item.chapter_id == "CH002"
        ),
        spec=spec002,
        allowed_handles=list(built002.get("allowed_handles") or []),
        language=corpus.language,
        raw_response=raw_ch002,
        finish_reason="end_turn",
        protect_accepted=False,
    )
    _row(
        "structural_validation_after_normalization",
        pipeline002["validator_executed_after_normalization"] is True
        and pipeline002["production_validator_modified"] is False
        and pipeline002["validator_pass"] is True,
        "existing validator ran after normalization and passed recovered CH002",
    )

    broken = deepcopy(original_ch002)
    for section in broken.get("sections") or []:
        for paragraph in section.get("paragraphs") or []:
            if paragraph.get("paragraph_id") == "P000001":
                handles = list(paragraph.get("evidence_handles") or [])
                handles.append("IDEA999")
                paragraph["evidence_handles"] = handles
                paragraph["idea_refs"] = list(paragraph.get("idea_refs") or []) + ["IDEA999"]
    pipeline_fail = normalize_then_validate(
        broken,
        plan=corpus.plan,
        source_map=corpus.source_map,
        editorial_chapter=next(
            item for item in corpus.plan.chapters if item.chapter_id == "CH002"
        ),
        spec=spec002,
        allowed_handles=list(built002.get("allowed_handles") or []),
        language=corpus.language,
        raw_response=raw_ch002,
        finish_reason="end_turn",
        protect_accepted=False,
    )
    _row(
        "validator_failure_rejects_candidate",
        pipeline_fail["candidate_status"] == "REJECTED"
        and pipeline_fail["validator_pass"] is False,
        "validator failure rejects the derived candidate",
    )
    _row(
        "idea_coverage_unchanged",
        hist["idea_coverage_unchanged"] is True
        and sorted(set(idea_handles(hist["derived"])))
        == sorted(set(idea_handles(recovered_ch002))),
        "IDEA coverage is unchanged by empty-paragraph removal",
    )

    accepted_paths = {
        "CH001": ch001_approved_json_path(),
        "CH003": ch003_approved_json_path(),
        "CH004": ch004_approved_json_path(),
        "CH012": accepted_chapter_json_path(),
        "CH018": ch018_json_path(),
        "CH002": ch002_approved_json_path(),
    }
    for chapter_id, path in accepted_paths.items():
        payload = load_json(path)
        before_ids = paragraph_ids(payload)
        result = normalize_empty_paragraphs(payload, protect_accepted=True)
        _row(
            f"{chapter_id.lower()}_unchanged",
            result["changed"] is False
            and result["removed_paragraph_ids"] == []
            and paragraph_ids(result["derived"]) == before_ids
            and result.get("accepted_chapter_protected") is True,
            f"{chapter_id} accepted artifact was not rewritten",
        )

    snap = snapshot()
    _row(
        "canonical_sources_unchanged",
        snap["canonical_match_expected"] is True,
        "canonical SourceMap / EditorialPlan / transcript hashes match",
    )
    _row(
        "no_http_calls",
        AUTHORIZED_ANTHROPIC_CALLS == 0 and AUTHORIZED_OPENAI_CALLS == 0,
        "no HTTP authorization exists in this phase",
    )
    _row(
        "no_generation_calls",
        production_book_path().is_file() is False,
        "no chapter generation and no book.json",
    )

    inspection = inspect_paragraph(with_idea)
    admissible, reasons = removal_is_admissible(inspection)
    _row(
        "empty_with_idea_not_admissible",
        admissible is False and any("IDEA" in item for item in reasons),
        "admissibility refuses empty IDEA paragraphs",
    )

    passed = sum(1 for row in rows if row["ok"])
    failed = sum(1 for row in rows if not row["ok"])
    return {
        "phase": PHASE,
        "passed": passed,
        "failed": failed,
        "rows": rows,
        "secrets_included": False,
    }


def evaluate_offline_scenarios(
    *,
    inventory: dict[str, Any] | None = None,
    cost: dict[str, Any] | None = None,
    simulation: dict[str, Any] | None = None,
    resume: dict[str, Any] | None = None,
    root=None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    def _row(name: str, ok: bool, detail: str) -> None:
        rows.append({"name": name, "ok": ok, "detail": detail})

    assert_offline_only()
    snap = snapshot(root=root)
    remaining = list((inventory or {}).get("remaining_chapter_ids") or [])
    _row("offline_only", True, "provider calls remain unauthorized")
    _row(
        "remaining_order",
        remaining == list(REMAINING_CHAPTER_IDS),
        "remaining 13 follow the required order",
    )
    _row(
        "accepted_excluded",
        not any(item in remaining for item in ACCEPTED_CHAPTER_IDS),
        "accepted six are absent from the remaining queue",
    )
    _row("canonical_match", bool(snap.get("canonical_match_expected")), "canonical hashes match")
    _row("six_immutable", bool(snap.get("six_accepted_immutable")), "six accepted hashes match")
    _row("book_json_absent", production_book_path().is_file() is False, "book.json unpublished")
    if cost:
        _row(
            "unknown_not_zero",
            cost.get("unknown_replaced_by_zero") is False
            and all(
                row.get("historical_observed_cost_usd") == "UNKNOWN"
                for row in cost.get("per_chapter") or []
            ),
            "UNKNOWN remaining observed costs are not replaced by zero",
        )
        _row(
            "central_not_cap",
            all(row.get("central_is_not_a_safety_cap") for row in cost.get("per_chapter") or []),
            "central estimate is not the safety cap",
        )
    if simulation:
        _row(
            "simulation_pass",
            simulation.get("status") == "PASS" and simulation.get("chapters_generated") == 0,
            "offline simulation generated no chapters",
        )
    if resume:
        _row(
            "resume_safety",
            resume.get("status") == "PASS" and resume.get("uncertain_ch006_blocks_replay"),
            "resume refuses uncertain replay",
        )
    passed = sum(1 for row in rows if row["ok"])
    failed = sum(1 for row in rows if not row["ok"])
    return {
        "phase": PHASE,
        "passed": passed,
        "failed": failed,
        "rows": rows,
        "secrets_included": False,
    }


def dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, indent=2)


__all__ = ["evaluate_normalizer_tests", "evaluate_offline_scenarios"]
