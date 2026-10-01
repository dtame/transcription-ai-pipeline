"""Offline semantic-gate context budget. No provider call."""

from __future__ import annotations

import math
from statistics import median
from typing import Any, Mapping, Sequence

from app.ai.capabilities import resolve_capabilities
from app.ai.estimation import estimate_tokens
from app.ai.settings import resolve_stage_settings
from app.book_generation.budget import estimate_manuscript_output
from app.book_generation.evidence import evidence_metrics
from app.book_semantic_gate_4b23.constants import (
    CONSERVATIVE_MAX_OUTPUT_TOKENS,
    DEFAULT_MAX_OUTPUT_TOKENS,
    SEMANTIC_GATE_MODEL,
    SEMANTIC_GATE_PROVIDER,
    SEMANTIC_GATE_STAGE,
    TARGET_CHAPTER_ID,
)
from app.book_semantic_gate_4b23.evidence import (
    build_gate_input,
    render_gate_input_json,
)
from app.book_semantic_gate_4b23.payload import payload_audit

_PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC = 1.9365384615384615
_PROVIDER_CHARS_PER_TOKEN_MID = 2.5


def _provider_tokens(chars: int, chars_per_token: float) -> int:
    return int(math.ceil(max(0, chars) / chars_per_token))


def estimated_generated_chars(idea_count: int, section_count: int) -> dict[str, int]:
    manuscript = estimate_manuscript_output(idea_count, section_count)
    mid_chars = int(manuscript["estimated_mid_words"] * 6)
    high_chars = int(manuscript["estimated_high_words"] * 6)
    return {
        "mid_chars": mid_chars,
        "high_chars": high_chars,
        "expected_output_tokens": manuscript["expected_output_tokens"],
    }


def measure_chapter_budget(
    *,
    evidence: Mapping[str, Any],
    candidate: Mapping[str, Any] | None,
    language: str,
    chapter_id: str,
    idea_count: int,
    section_count: int,
) -> dict[str, Any]:
    if candidate is None:
        generated = estimated_generated_chars(idea_count, section_count)
        section_rows = list(evidence.get("sections") or [{"id": "SEC"}])
        per_section = max(80, generated["mid_chars"] // max(1, len(section_rows)))
        proxy = {
            "chapter_id": chapter_id,
            "title": (evidence.get("chapter") or {}).get("t") or "",
            "sections": [
                {
                    "section_id": str(section.get("id") or ""),
                    "title": str(section.get("t") or ""),
                    "paragraphs": [
                        {
                            "text": "X" * per_section,
                            "kind": "substantive",
                            "provider_handle": f"p{index + 1}",
                            "evidence_handles": [],
                        }
                    ],
                }
                for index, section in enumerate(section_rows)
            ],
        }
        gate_input = build_gate_input(
            candidate=proxy, evidence=evidence, language=language
        )
        candidate_source = "estimated_generated_text"
    else:
        gate_input = build_gate_input(
            candidate=candidate, evidence=evidence, language=language
        )
        generated = {
            "mid_chars": sum(
                len(str(para.get("t") or ""))
                for section in (gate_input.get("candidate") or {}).get("sections")
                or []
                for para in section.get("paras") or []
            ),
            "high_chars": 0,
            "expected_output_tokens": 0,
        }
        candidate_source = "historical_or_supplied_candidate"
    audit = payload_audit(gate_input)
    request_chars = audit["system_prompt_chars"] + audit["user_prompt_chars"]
    local = int((audit["local_input_token_estimate"] or {}).get("tokens") or 0)
    mid = max(local, _provider_tokens(request_chars, _PROVIDER_CHARS_PER_TOKEN_MID))
    pessimistic = _provider_tokens(
        request_chars, _PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC
    )
    paragraph_count = sum(
        len(section.get("paras") or [])
        for section in (gate_input.get("candidate") or {}).get("sections") or []
    )
    claim_units = max(paragraph_count, idea_count, 1)
    expected_output = max(800, claim_units * 180)
    conservative_output = max(1500, claim_units * 320)
    recommended = min(
        CONSERVATIVE_MAX_OUTPUT_TOKENS,
        max(DEFAULT_MAX_OUTPUT_TOKENS, conservative_output),
    )
    caps = resolve_capabilities(SEMANTIC_GATE_PROVIDER, SEMANTIC_GATE_MODEL)
    stage = resolve_stage_settings(SEMANTIC_GATE_STAGE)
    usable = int(caps.context_window * stage.context_safety_ratio) - recommended
    metrics = evidence_metrics(dict(evidence))
    return {
        "chapter_id": chapter_id,
        "candidate_source": candidate_source,
        "evidence": metrics,
        "generated_chars": generated,
        "request": {
            "system_chars": audit["system_prompt_chars"],
            "user_chars": audit["user_prompt_chars"],
            "payload_sha256": audit["payload_sha256"],
            "local_token_estimate": local,
            "provider_adjusted_mid": mid,
            "provider_adjusted_pessimistic": pessimistic,
        },
        "output": {
            "paragraph_count": paragraph_count,
            "expected_output_tokens": expected_output,
            "conservative_output_tokens": conservative_output,
            "recommended_max_output": recommended,
        },
        "usable_input_tokens": usable,
        "context_window": caps.context_window,
        "context_utilization_pessimistic": (
            round(pessimistic / usable, 6) if usable else 1.0
        ),
        "context_safe": pessimistic < usable and mid < usable,
        "thinking_present": audit["thinking_present"],
        "temperature_present": audit["temperature_present"],
        "http_sent": False,
        "gate_input_chars": len(render_gate_input_json(gate_input)),
    }


def distribution(values: Sequence[int | float]) -> dict[str, float]:
    if not values:
        return {"min": 0, "median": 0, "max": 0}
    ordered = sorted(float(item) for item in values)
    return {
        "min": ordered[0],
        "median": float(median(ordered)),
        "max": ordered[-1],
    }


def select_extrema(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_id = {str(row.get("chapter_id")): row for row in rows}
    ordered = sorted(
        rows,
        key=lambda row: int((row.get("request") or {}).get("provider_adjusted_pessimistic") or 0),
    )
    smallest = ordered[0] if ordered else {}
    largest = ordered[-1] if ordered else {}
    mid_index = len(ordered) // 2
    median_row = ordered[mid_index] if ordered else {}
    return {
        "ch016": by_id.get(TARGET_CHAPTER_ID) or {},
        "smallest": smallest,
        "median": median_row,
        "largest": largest,
    }


__all__ = [
    "distribution",
    "estimated_generated_chars",
    "measure_chapter_budget",
    "select_extrema",
]
