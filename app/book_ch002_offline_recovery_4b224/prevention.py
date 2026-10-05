"""Isolated empty-paragraph prevention analysis. Production pipeline stays closed."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_ch002_offline_recovery_4b224.constants import (
    EMPTY_PARAGRAPH_ID,
    PHASE,
    TARGET_CHAPTER_ID,
    VALIDATOR_VERSION,
)
from app.book_generation.constants import (
    BOOK_GENERATOR_PROMPT_VERSION,
    BOOK_GENERATOR_VALIDATOR_VERSION,
)


def analyze_prevention(
    forensic: Mapping[str, Any],
    *,
    original_validation_status: str,
    recovered_validation_status: str | None,
) -> dict[str, Any]:
    introduction = dict(forensic.get("introduction") or {})
    return {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "empty_paragraph_id": EMPTY_PARAGRAPH_ID,
        "where_introduced": {
            "model_emitted_empty_connective": introduction.get("introduced_by_model"),
            "parser_invented_paragraph": introduction.get("introduced_by_parsing"),
            "normalizer_invented_paragraph": introduction.get(
                "introduced_by_normalization"
            ),
            "renderer_invented_paragraph": introduction.get("introduced_by_rendering"),
            "contract_defect": introduction.get("contract_defect"),
            "validation_defect": introduction.get("validation_defect"),
            "evidence": introduction.get("rationale"),
        },
        "current_controls": {
            "prompt_forbids_empty_paragraphs": True,
            "historical_prompt": BOOK_GENERATOR_PROMPT_VERSION,
            "validator_version": VALIDATOR_VERSION,
            "validator_module_version": BOOK_GENERATOR_VALIDATOR_VERSION,
            "validator_fails_on_empty_text": original_validation_status == "FAIL",
            "empty_paragraph_never_dropped_by_production_validator": True,
            "markdown_renderer_omits_empty_text": introduction.get(
                "markdown_omits_empty_paragraph"
            ),
            "production_pipeline_modified_this_phase": False,
        },
        "recommended_future_rule": {
            "name": "strip_strictly_empty_unprovenanced_paragraphs",
            "authorized_in_this_phase": False,
            "proposal_only": True,
            "applies_only_when": [
                "text is empty or whitespace-only",
                "no IDEA handle",
                "no SRC handle",
                "no EX handle",
                "no REF handle",
                "no UNC handle",
                "no other provenance fields",
                "paragraph is not referenced by another structure",
            ],
            "never": [
                "delete a paragraph that contains text",
                "delete a paragraph that carries an IDEA",
                "delete a paragraph that carries provenance",
                "delete a section",
                "renumber remaining paragraphs silently",
                "modify the raw provider response",
                "hide a substantial error",
            ],
            "after_strip": [
                "re-run the existing structural validator, not a weakened copy",
                "keep the original response immutable",
                "label the result OFFLINE_DERIVED_ARTIFACT / NOT_PROVIDER_ORIGINAL",
                "require human review before acceptance",
            ],
            "batch_effect": (
                "Had this deterministic strip existed as an authorized "
                "post-receipt repair, CH002 would not have stopped BATCH-01 "
                "for a provenance-less empty connective. The 4B.2.23 lock "
                "would still be consumed. This phase only proposes the rule."
            ),
        },
        "recovered_validation_status": recovered_validation_status,
        "do_not_weaken_validator_to_obtain_pass": True,
        "secrets_included": False,
    }


def render_prevention_markdown(analysis: Mapping[str, Any]) -> str:
    where = dict(analysis.get("where_introduced") or {})
    rule = dict(analysis.get("recommended_future_rule") or {})
    current = dict(analysis.get("current_controls") or {})
    never = "\n".join(f"- {item}" for item in rule.get("never") or [])
    applies = "\n".join(f"- {item}" for item in rule.get("applies_only_when") or [])
    after = "\n".join(f"- {item}" for item in rule.get("after_strip") or [])
    return "\n".join(
        [
            "# Empty-paragraph prevention analysis — Phase 4B.2.24",
            "",
            "This note is a proposal. The production generation pipeline was not modified.",
            "",
            "## Where the empty paragraph was introduced",
            "",
            f"- Model emitted empty connective: {where.get('model_emitted_empty_connective')}",
            f"- Parser invented the paragraph: {where.get('parser_invented_paragraph')}",
            f"- Normalizer invented the paragraph: {where.get('normalizer_invented_paragraph')}",
            f"- Renderer invented the paragraph: {where.get('renderer_invented_paragraph')}",
            f"- Contract defect: {where.get('contract_defect')}",
            f"- Validation defect: {where.get('validation_defect')}",
            "",
            str(where.get("evidence") or ""),
            "",
            "The defect is attributed to the model because the raw parsed Anthropic "
            "JSON already contains `p8` with `t: \"\"` and `e: []`. Parsing, "
            "materialization, and paragraph-id assignment preserved that object. "
            "The markdown renderer omitted it, which hid the failure from the "
            "readable file but did not invent it. The existing validator correctly "
            f"failed (`{current.get('validator_version')}`).",
            "",
            "## Recommended future rule",
            "",
            f"Name: `{rule.get('name')}`.",
            "",
            "Authorized in this phase: no. Proposal only.",
            "",
            "Apply only when all of the following are true:",
            "",
            applies,
            "",
            "Never:",
            "",
            never,
            "",
            "After a future authorized strip:",
            "",
            after,
            "",
            str(rule.get("batch_effect") or ""),
            "",
            "Do not weaken the validator to obtain PASS.",
            "",
        ]
    )


__all__ = ["analyze_prevention", "render_prevention_markdown"]
