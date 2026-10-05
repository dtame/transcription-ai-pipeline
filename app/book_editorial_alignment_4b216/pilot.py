"""
Pilot-chapter selection and budget.

Selection is deterministic and excludes CH001 and CH016.
No chapter is generated.
"""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping

from app.book_editorial_alignment_4b216.constants import (
    COST_UNKNOWN,
    ELIGIBLE_IDEA_HIGH,
    ELIGIBLE_IDEA_LOW,
    ELIGIBLE_SECTION_HIGH,
    ELIGIBLE_SECTION_LOW,
    EXCLUDED_PILOT_CHAPTERS,
    H01_ANALOG_COST_USD,
    MODEST_EVIDENCE_CHARS,
    PHASE,
    PREFERRED_IDEA_HIGH,
    PREFERRED_IDEA_LOW,
    PRICING_EFFECTIVE_DATE,
    SEMANTIC_GATE_MODEL,
    SEMANTIC_GATE_PROVIDER,
    SONNET_INPUT_COST_PER_1M,
    SONNET_MODEL,
    SONNET_OUTPUT_COST_PER_1M,
    SONNET_PROVIDER,
)
from app.book_editorial_alignment_4b216.paths import repo_root


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _analog_cost() -> Decimal:
    raw = str(H01_ANALOG_COST_USD).split()[0]
    return Decimal(raw)


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _row_from_chapter(chapter: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "chapter_id": chapter["chapter_id"],
        "working_title": chapter["working_title"],
        "section_count": chapter["section_count"],
        "section_ids": [item["section_id"] for item in chapter["sections"]],
        "idea_count": chapter["idea_count"],
        "audio_sources": chapter["audio_sources"],
        "cross_recording": chapter["cross_recording"],
        "evidence_chars": chapter["evidence_chars"],
        "hydrated_src_chars": chapter["hydrated_src_chars"],
        "src_ref_count": chapter["src_ref_count"],
        "example_count": chapter["example_count"],
        "reference_count": chapter["reference_count"],
        "uncertainty_count": chapter["uncertainty_count"],
        "detached_example_count": len(chapter["detached_examples"]),
        "separated_uncertainty_count": len(chapter["separated_uncertainties"]),
        "reference_tension_count": len(chapter["reference_tensions"]),
    }


def _eligible(row: Mapping[str, Any]) -> tuple[bool, list[str]]:
    reasons = []
    if row["chapter_id"] in EXCLUDED_PILOT_CHAPTERS:
        reasons.append("excluded_by_phase_rule")
    if not (ELIGIBLE_IDEA_LOW <= int(row["idea_count"]) <= ELIGIBLE_IDEA_HIGH):
        reasons.append("idea_count_outside_8_to_16")
    if not (ELIGIBLE_SECTION_LOW <= int(row["section_count"]) <= ELIGIBLE_SECTION_HIGH):
        reasons.append("section_count_outside_3_to_5")
    if int(row["detached_example_count"]) > 0:
        reasons.append("detached_example_would_confound_a_first_pilot")
    if int(row["src_ref_count"]) < 20:
        reasons.append("src_evidence_thin")
    if not row["audio_sources"]:
        reasons.append("no_recording_sources")
    return not reasons, reasons


def _score(row: Mapping[str, Any]) -> tuple[int, list[str]]:
    score = 0
    reasons = []
    if row["cross_recording"]:
        score += 40
        reasons.append("cross_recording_regrouping_is_observable")
    if int(row["separated_uncertainty_count"]) > 0:
        score += 25
        reasons.append("reservation_separation_risk_is_identifiable")
    if int(row["reference_tension_count"]) > 0:
        score += 15
        reasons.append("reference_association_risk_is_identifiable")
    if int(row["example_count"]) > 0:
        score += 8
        reasons.append("examples_are_present_for_coverage")
    if PREFERRED_IDEA_LOW <= int(row["idea_count"]) <= PREFERRED_IDEA_HIGH:
        score += 12
        reasons.append("idea_count_is_in_the_preferred_band")
    if int(row["evidence_chars"]) <= MODEST_EVIDENCE_CHARS:
        score += 8
        reasons.append("evidence_bundle_is_modest")
    return score, reasons


def select_pilot(risk_map: Mapping[str, Any]) -> dict[str, Any]:
    ranked = []
    for chapter in risk_map["chapters"]:
        row = _row_from_chapter(chapter)
        eligible, blocked = _eligible(row)
        score, reasons = _score(row) if eligible else (0, [])
        ranked.append(
            {
                **row,
                "eligible": eligible,
                "ineligible_reasons": blocked,
                "score": score,
                "score_reasons": reasons,
            }
        )
    eligible_rows = [row for row in ranked if row["eligible"]]
    eligible_rows.sort(
        key=lambda row: (
            -int(row["score"]),
            int(row["idea_count"]),
            int(row["evidence_chars"]),
            str(row["chapter_id"]),
        )
    )
    selected_id = eligible_rows[0]["chapter_id"] if eligible_rows else ""
    selected_chapter = next(
        (
            chapter
            for chapter in risk_map["chapters"]
            if chapter["chapter_id"] == selected_id
        ),
        None,
    )
    return {
        "phase": PHASE,
        "selection_executed": bool(selected_id),
        "generation_executed": False,
        "excluded_without_scoring": list(EXCLUDED_PILOT_CHAPTERS),
        "candidates": ranked,
        "eligible_ranking": [row["chapter_id"] for row in eligible_rows],
        "selected_chapter_id": selected_id,
        "selected": _selected_document(selected_chapter) if selected_chapter else {},
        "secrets_included": False,
    }


def _selected_document(chapter: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "phase": PHASE,
        "chapter_id": chapter["chapter_id"],
        "working_title": chapter["working_title"],
        "purpose": chapter["purpose"],
        "language": "en",
        "sections": [
            {
                "section_id": section["section_id"],
                "working_title": section["working_title"],
                "idea_ids": section["idea_ids"],
                "example_ids": section["example_ids"],
                "reference_ids": section["reference_ids"],
                "uncertainty_ids": section["uncertainty_ids"],
                "audio_sources": section["audio_sources"],
                "transcript_index_span": section["transcript_index_span"],
                "cross_recording": section["cross_recording"],
            }
            for section in chapter["sections"]
        ],
        "section_count": chapter["section_count"],
        "idea_count": chapter["idea_count"],
        "idea_ids": chapter["idea_ids"],
        "reference_ids": sorted(
            {
                reference_id
                for section in chapter["sections"]
                for reference_id in section["reference_ids"]
            }
        ),
        "example_ids": sorted(
            {
                example_id
                for section in chapter["sections"]
                for example_id in section["example_ids"]
            }
        ),
        "uncertainty_ids": sorted(
            {
                uncertainty_id
                for section in chapter["sections"]
                for uncertainty_id in section["uncertainty_ids"]
            }
        ),
        "audio_sources": chapter["audio_sources"],
        "src_ref_count": chapter["src_ref_count"],
        "evidence_chars": chapter["evidence_chars"],
        "hydrated_src_chars": chapter["hydrated_src_chars"],
        "risks": chapter["risks"],
        "detached_examples": chapter["detached_examples"],
        "separated_uncertainties": chapter["separated_uncertainties"],
        "reference_tensions": chapter["reference_tensions"],
        "why_selected": (
            "The chapter is neither CH001 nor CH016. It has a manageable "
            "idea count, four defined sections, hydrated SRC evidence, a "
            "modest bundle, and identifiable risks: material from two "
            "recordings is already grouped, at least one reservation does "
            "not share SRC with its section ideas, and at least one "
            "reference does not share SRC with its section ideas."
        ),
        "generation_executed": False,
        "stop_conditions": [
            "Human review of phase 4B.2.16 has not been recorded.",
            "The requested chapter id is not the selected pilot.",
            "A second chapter, CH016, or the full book is requested.",
            "Canonical SourceMap, EditorialPlan, or transcript hash changes.",
            "Any provider retry or fallback is requested.",
            "Projected generator or Semantic Gate spend exceeds the high band of this estimate.",
            "Phase 5, Word, or PDF is requested.",
            "book.json publication or production-cache acceptance is requested.",
            "The faithful prompt or coverage control is treated as already activated.",
        ],
        "ready_to_generate": False,
        "secrets_included": False,
    }


def pilot_budget_estimate(
    selected: Mapping[str, Any] | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    base = root or repo_root()
    historical_gate = _load(
        base / "audit" / "book_generation_bridge_4b214" / "cost_estimates.json"
    )
    corpus = _load(base / "audit" / "book_generator_4b1" / "book_generator_4b1_real_corpus_budget.json")
    chapter_id = str((selected or {}).get("chapter_id") or "")
    historical_row = next(
        (
            row
            for row in corpus.get("chapters") or []
            if row.get("chapter_id") == chapter_id
        ),
        {},
    )
    section_count = int((selected or {}).get("section_count") or historical_row.get("section_count") or 0)
    input_tokens = historical_row.get("input_pessimistic")
    output_tokens = historical_row.get("expected_output")
    generator_status = "historical_4b1_estimate"
    if input_tokens is None or output_tokens is None:
        generator_central = None
        generator_low = None
        generator_high = None
    else:
        generator_central = (
            Decimal(input_tokens) / Decimal(1_000_000) * Decimal(str(SONNET_INPUT_COST_PER_1M))
        ) + (
            Decimal(output_tokens) / Decimal(1_000_000) * Decimal(str(SONNET_OUTPUT_COST_PER_1M))
        )
        generator_low = generator_central * Decimal("0.6")
        generator_high = generator_central * Decimal("2.0")
    per_call = _analog_cost()
    # 4B.2.14 assumption: 2 / 4 / 7 paragraphs per section. Not a measurement.
    requests_low = section_count * 2
    requests_central = section_count * 4
    requests_high = section_count * 7
    gate_low = per_call * Decimal(requests_low)
    gate_central = per_call * Decimal(requests_central)
    gate_high = per_call * Decimal(requests_high)
    partial_central = (
        None if generator_central is None else generator_central + gate_central
    )
    return {
        "phase": PHASE,
        "provider_calls": 0,
        "spent": False,
        "chapter_id": chapter_id,
        "pricing_effective_date": PRICING_EFFECTIVE_DATE,
        "tariffs_are_local_configuration_not_a_live_lookup": True,
        "historical_full_book_4b214": {
            "classification": "hypothesis_reused_not_remeasured",
            "source": "audit/book_generation_bridge_4b214/cost_estimates.json",
            "book_generator": historical_gate.get("book_generator"),
            "semantic_gate": historical_gate.get("semantic_gate"),
            "phase5": historical_gate.get("phase5"),
            "partial_sum_generator_plus_strategy_a_gate": historical_gate.get(
                "partial_sum_generator_plus_strategy_a_gate"
            ),
            "complete_total": COST_UNKNOWN,
            "unknown_not_treated_as_zero": True,
        },
        "pilot_book_generator": {
            "classification": "historical_estimate",
            "status": generator_status if generator_central is not None else COST_UNKNOWN,
            "source": "audit/book_generator_4b1/book_generator_4b1_real_corpus_budget.json",
            "provider": SONNET_PROVIDER,
            "model": SONNET_MODEL,
            "input_tokens_pessimistic": input_tokens,
            "expected_output_tokens": output_tokens,
            "output_tokens_are_a_formula_not_a_measurement": True,
            "observed_spend_usd": COST_UNKNOWN,
            "central_usd": None if generator_central is None else _money(generator_central),
            "low_usd": None if generator_low is None else _money(generator_low),
            "high_usd": None if generator_high is None else _money(generator_high),
            "band_factors": "0.6 and 2.0 reused from 4B.2.14; assumptions, not measured spend",
            "counted_as_zero": False,
        },
        "pilot_semantic_gate": {
            "classification": "hypothesis",
            "status": "hypothesis",
            "provider": SEMANTIC_GATE_PROVIDER,
            "model": SEMANTIC_GATE_MODEL,
            "granularity": "A_ONE_REQUEST_PER_PARAGRAPH",
            "per_call_usd_h01_analog": _money(per_call),
            "h01_analog_scope": "one historical paragraph call; not a generated book paragraph",
            "paragraphs_per_section_assumption": "2 / 4 / 7 reused from 4B.2.14",
            "assumption_not_measurement": True,
            "section_count": section_count,
            "requests_low": requests_low,
            "requests_central": requests_central,
            "requests_high": requests_high,
            "low_usd": _money(gate_low),
            "central_usd": _money(gate_central),
            "high_usd": _money(gate_high),
            "actual_paragraph_count": COST_UNKNOWN,
            "actual_paragraph_count_counted_as_zero": False,
            "reasoning_token_billing": COST_UNKNOWN,
            "long_context_pricing": COST_UNKNOWN,
            "counted_as_zero": False,
        },
        "possible_reprise": {
            "classification": "hypothesis",
            "status": COST_UNKNOWN,
            "whether_a_reprise_is_required": COST_UNKNOWN,
            "counted_as_zero": False,
            "modeled_sensitivity_only": {
                "one_extra_generator_call_at_central_usd": (
                    None if generator_central is None else _money(generator_central)
                ),
                "gate_central_plus_10_percent_usd": _money(gate_central * Decimal("1.10")),
                "gate_high_plus_50_percent_usd": _money(gate_high * Decimal("1.50")),
                "factors_are_assumptions": True,
            },
        },
        "phase5": {
            "classification": COST_UNKNOWN,
            "status": COST_UNKNOWN,
            "low_usd": None,
            "central_usd": None,
            "high_usd": None,
            "counted_as_zero": False,
            "reason": "The independent Book Validator is not implemented. No measured token use.",
        },
        "pilot_partial_generator_plus_gate_hypothesis": {
            "central_usd": None if partial_central is None else _money(partial_central),
            "complete_total_including_phase5": COST_UNKNOWN,
            "unknown_not_treated_as_zero": True,
        },
        "stop_if_high_band_exceeded": {
            "generator_high_usd": None if generator_high is None else _money(generator_high),
            "semantic_gate_high_usd": _money(gate_high),
            "does_not_authorize_spend": True,
            "phase5_not_included_so_ceiling_is_incomplete": True,
        },
        "secrets_included": False,
    }


__all__ = ["pilot_budget_estimate", "select_pilot"]
