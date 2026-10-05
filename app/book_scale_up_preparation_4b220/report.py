"""Phase 4B.2.20 report."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_scale_up_preparation_4b220.constants import CANONICAL_PYTHON


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    inventory = dict(bundle.get("remaining_chapters_inventory") or {})
    selection = dict(bundle.get("first_chapter_selection") or {})
    prompt = dict(bundle.get("prompt_11_readiness") or {})
    contract = dict(bundle.get("generation_contract_matrix") or {})
    context = dict(bundle.get("first_chapter_source_context_manifest") or {})
    cost = dict(bundle.get("scale_up_cost_envelope") or {})
    auth = dict(bundle.get("future_authorization") or {})
    token = dict(auth.get("required_human_token") or {})
    first = dict(cost.get("first_chapter") or {})
    generation = dict(cost.get("generation_18_chapters") or {})
    validation = dict(cost.get("validation_cost") or {})
    matrix_lines = [
        "| Exigence | Prompt 1.1 | Contrat JSON | Validateur | Statut |",
        "|---|---|---|---|---|",
    ]
    for row in contract.get("rows") or []:
        matrix_lines.append(
            "| {req} | {prompt} | {field} | {control} | {status} |".format(
                req=row.get("requirement", ""),
                prompt="Oui" if row.get("prompt_1_1") else "Non",
                field=row.get("json_contract_field") or "contrôle éditorial",
                control=row.get("validator_control", ""),
                status=row.get("status", ""),
            )
        )
    reason_lines = [f"- {item}" for item in selection.get("reasons") or []]
    stop_lines = [f"- {item}" for item in selection.get("stop_conditions") or []]
    lines = [
        "**PHASE 4B.2.20 — CONTROLLED SCALE-UP PREPARATION & FIRST-CHAPTER READINESS**",
        "",
        f"RESULT = {header.get('result')}",
        "PROVIDER CALLS = 0",
        "ANTHROPIC HTTP = 0",
        "OPENAI HTTP = 0",
        f"CANONICAL HASHES PRE/POST = {header.get('canonical_hashes_pre_post')}",
        f"CH012 IMMUTABLE = {header.get('ch012_immutable')}",
        f"REMAINING CHAPTERS = {header.get('remaining_chapters')}",
        f"TOTAL REMAINING SECTIONS = {header.get('total_remaining_sections')}",
        f"TOTAL REMAINING IDEAS = {header.get('total_remaining_ideas')}",
        f"FIRST CHAPTER SELECTED = {header.get('first_chapter_selected')}",
        f"FIRST CHAPTER SECTIONS = {header.get('first_chapter_sections')}",
        f"FIRST CHAPTER IDEAS = {header.get('first_chapter_ideas')}",
        f"PROMPT 1.1 AVAILABLE = {header.get('prompt_11_available')}",
        f"PROMPT 1.1 ISOLATED = {header.get('prompt_11_isolated')}",
        f"GENERATION CONTRACT COMPATIBLE = {header.get('generation_contract_compatible')}",
        f"FIRST CHAPTER SOURCE CONTEXT READY = {header.get('first_chapter_source_context_ready')}",
        f"ESTIMATED FIRST CHAPTER COST = {header.get('estimated_first_chapter_cost')}",
        f"ESTIMATED 18-CHAPTER GENERATION COST = {header.get('estimated_18_chapter_cost')}",
        f"VALIDATION COST = {header.get('validation_cost')}",
        "AUTHORIZED SPEND = 0 USD",
        f"HARD STOP TESTS = {header.get('hard_stop_tests')}",
        f"OFFLINE TESTS PASSED / FAILED = {header.get('offline_tests')}",
        f"PRODUCTION PIPELINE MODIFIED = {header.get('production_pipeline_modified')}",
        "PRODUCTION CACHE = UNCHANGED",
        "SEMANTIC GATE PROMOTED = NO",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_FIRST_REAL_CHAPTER = {header.get('ready_for_first_real_chapter')}",
        "READY_FOR_18_CHAPTER_RUN = NO",
        f"NEXT ACTION = {header.get('next_action')}",
        "",
        "## Why this result",
        "",
        str(header.get("notes") or ""),
        "",
        "## Canonical identity",
        "",
        f"Canonical Python = {header.get('canonical_python') or CANONICAL_PYTHON}",
        "SourceMap, EditorialPlan, and clean transcript were hashed before and after.",
        "They were not modified. CH012 accepted artifacts and the 4B.2.17 lock were not modified.",
        "",
        "## Remaining-chapter inventory",
        "",
        f"{inventory.get('remaining_chapter_count')} chapters remain after excluding CH012.",
        f"Total remaining sections = {inventory.get('total_remaining_sections')}.",
        f"Total remaining planned IDEA units = {inventory.get('total_remaining_ideas')}.",
        "A section or idea in the plan is not treated as covered.",
        "",
        "## First chapter selection",
        "",
        f"Selected = {selection.get('selected_chapter_id')} — {selection.get('working_title')}.",
        f"Sections = {selection.get('section_count')}. IDEA units = {selection.get('idea_count')}.",
        "",
        *reason_lines,
        "",
        "Anticipated difficulties:",
        *[f"- {item}" for item in selection.get("anticipated_difficulties") or []],
        "",
        "Stop conditions:",
        *stop_lines,
        "",
        "## Prompt 1.1",
        "",
        f"Version = {prompt.get('version')}.",
        f"Available = {prompt.get('available')}. Isolated = {prompt.get('isolated')}.",
        "Registered in production prompt_select = "
        f"{prompt.get('registered_in_prompt_select')}.",
        "Activated = False. Ready for production = False. Automatically promoted = False.",
        "Handle mention is not treated as content restatement.",
        "paras[].e must not be completed after generation to satisfy a validator.",
        "",
        "## Generation contract",
        "",
        *matrix_lines,
        "",
        str(contract.get("historical_4b217_detection") or ""),
        "",
        "## First-chapter source context",
        "",
        f"Chapter = {context.get('chapter_id')}.",
        f"Missing sources = {context.get('missing_sources') or []}.",
        f"Hydrated SRC count = {(context.get('resolved_sources') or {}).get('hydrated_count')}.",
        f"Whole transcript injected = {context.get('whole_transcript_injected')}.",
        "A missing mandatory source blocks generation.",
        "",
        "## Cost envelope",
        "",
        f"First chapter expected = {first.get('expected_cost_usd')} USD.",
        f"First chapter calculable maximum = {first.get('calculable_maximum_usd')} USD.",
        f"18-chapter low / central / high = {generation.get('low_usd')} / "
        f"{generation.get('central_usd')} / {generation.get('high_calculable_maximum_usd')} USD.",
        f"Validation = {validation.get('semantic_gate_complete_cost')}; "
        "Terra analog is a hypothesis, not a complete cost.",
        "Authorized spend = 0 USD. Central estimates are not safety caps.",
        "UNKNOWN items are listed and are not replaced by zero.",
        "",
        "## Future human authorization if the first chapter is to be generated",
        "",
        "This phase does not request a provider. If the user later authorizes "
        "exactly one remaining chapter, the token must be limited to:",
        "",
        f"- Chapter `{token.get('chapter_id')}`.",
        f"- Model `{token.get('provider')}/{token.get('model')}`.",
        f"- Prompt `{token.get('prompt_version')}` via an isolated explicit option.",
        "- One remote call. Zero retries. Zero fallbacks.",
        "- A cost cap at or above the calculable theoretical maximum, not the central estimate.",
        "- Hard stop on missing/invented IDEA handles, invalid JSON, truncation, unknown cost, or cap breach.",
        "- Isolated audit output. No publication. No CH012 rewrite. No 18-chapter run.",
        "",
        "## Stop",
        "",
        "STOP. No Sonnet call. No Terra call. No remaining-chapter generation.",
        "No CH012 regeneration. No global prompt activation. No book.json. No DOCX/PDF.",
        "Wait for the explicit human decision on a distinct one-chapter authorization.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
