"""Phase 4B.2.26 report."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_full_generation_preparation_4b226.constants import CANONICAL_PYTHON


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    cost = dict(bundle.get("remaining_chapters_budget_forecast") or {})
    inventory = dict(bundle.get("remaining_chapters_inventory") or {})
    accepted = dict(bundle.get("accepted_chapters_inventory") or {})
    tests = dict(bundle.get("empty_paragraph_normalization_tests") or {})
    inventory_lines = [
        "| Chapter | Title | SEC | IDEA | SRC | Input tok | Central | Preflight max | Tariff |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    costs = {row["chapter_id"]: row for row in cost.get("per_chapter") or []}
    for row in inventory.get("chapters") or []:
        item = costs.get(row.get("chapter_id")) or {}
        inventory_lines.append(
            "| {id} | {title} | {sec} | {ideas} | {src} | {tokens} | {central} | {maximum} | {tariff} |".format(
                id=row.get("chapter_id", ""),
                title=row.get("working_title", ""),
                sec=row.get("section_count", ""),
                ideas=row.get("idea_count", ""),
                src=row.get("src_count", ""),
                tokens=item.get("estimated_input_tokens", ""),
                central=item.get("central_estimate_usd", ""),
                maximum=item.get("preflight_max_cost_usd", ""),
                tariff=item.get("tariff_knowledge_status", ""),
            )
        )
    accepted_lines = [
        "| Chapter | Status | JSON SHA-256 | Markdown SHA-256 |",
        "|---|---|---|---|",
    ]
    for row in accepted.get("chapters") or []:
        accepted_lines.append(
            "| {id} | {status} | `{json}` | `{md}` |".format(
                id=row.get("chapter_id", ""),
                status=row.get("status", ""),
                json=row.get("json_sha256", ""),
                md=row.get("markdown_sha256", ""),
            )
        )
    lines = [
        "**PHASE 4B.2.26 — FULL GENERATION PREPARATION**",
        "",
        f"RESULT = {header.get('result')}",
        "PROVIDER CALLS = 0",
        "ANTHROPIC HTTP = 0",
        "OPENAI HTTP = 0",
        f"CH003 HUMAN ACCEPTANCE = {header.get('ch003_human_acceptance')}",
        f"CH004 HUMAN ACCEPTANCE = {header.get('ch004_human_acceptance')}",
        f"ACCEPTED CHAPTERS = {header.get('accepted_chapters')}",
        f"REMAINING CHAPTERS = {header.get('remaining_chapters')}",
        f"EMPTY PARAGRAPH NORMALIZER = {header.get('empty_paragraph_normalizer')}",
        f"NORMALIZER TESTS PASSED / FAILED = {header.get('normalizer_tests')}",
        f"PRODUCTION VALIDATOR = {header.get('production_validator')}",
        f"FULL BATCH OFFLINE SIMULATION = {header.get('full_batch_offline_simulation')}",
        f"RESUME SAFETY = {header.get('resume_safety')}",
        f"CALL LOCK SAFETY = {header.get('call_lock_safety')}",
        f"GLOBAL ESTIMATED COST = {header.get('global_estimated_cost')} USD",
        f"GLOBAL PREFLIGHT MAX COST = {header.get('global_preflight_max_cost')} USD",
        f"RECOMMENDED AUTHORIZATION CAP = {header.get('recommended_authorization_cap')} USD",
        f"UNKNOWN COST COMPONENTS = {header.get('unknown_cost_components')}",
        f"CANONICAL HASHES PRE/POST = {header.get('canonical_hashes_pre_post_status')}",
        f"SIX ACCEPTED CHAPTERS IMMUTABLE = {header.get('six_accepted_chapters_immutable')}",
        f"PRODUCTION CACHE = {header.get('production_cache')}",
        "NEW CHAPTERS GENERATED = 0",
        "SEMANTIC CERTIFICATION = NOT PERFORMED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_SINGLE_13_CHAPTER_AUTHORIZATION = {header.get('ready_for_single_13_chapter_authorization')}",
        f"NEXT ACTION = {header.get('next_action')}",
        "",
        "## Why this result",
        "",
        str(header.get("notes") or ""),
        "",
        "## Canonical identity",
        "",
        f"Canonical Python = {CANONICAL_PYTHON}",
        f"Canonical hashes = {header.get('canonical_hashes_pre_post')}",
        "SourceMap, EditorialPlan, and the cleaned transcript were hashed before and after.",
        "They were not modified.",
        "",
        "## Accepted chapters",
        "",
        *accepted_lines,
        "",
        "CH003 EX005 remains documented as undetermined_handle_absent_is_not_omission.",
        "CH004 REF011, REF012, REF013 and the always / never formulations remain documented.",
        "Those observations do not trigger an automatic rewrite.",
        "",
        "## Remaining-chapter inventory",
        "",
        f"13 chapters remain after excluding the six accepted chapters.",
        f"Total remaining sections = {inventory.get('total_remaining_sections')}.",
        f"Total remaining planned IDEA units = {inventory.get('total_remaining_ideas')}.",
        "A section or idea in the plan is not treated as covered.",
        "",
        *inventory_lines,
        "",
        "## Empty-paragraph normalizer",
        "",
        "The deterministic strip runs after the raw provider response is saved and",
        "before the existing production validator. The validator is unchanged and",
        "remains the structural authority. Accepted chapters are not rewritten.",
        f"Normalizer tests = {tests.get('passed')} passed / {tests.get('failed')} failed.",
        "",
        "## Cost distinctions",
        "",
        "Historical observed cost of the remaining 13 chapters is UNKNOWN and is not zero.",
        "Central estimate is the token-based expected cost.",
        "Preflight maximum is the calculable theoretical maximum.",
        "Recommended cap is that maximum plus a documented 15 percent margin.",
        "Authorized spend for this phase is 0 USD.",
        "",
        "## Code and tests",
        "",
        f"Code modified = {header.get('code_modified')}",
        f"Tests executed = {header.get('tests_executed')}",
        "",
        "## Stop",
        "",
        "STOP. Do not call Anthropic. Do not call OpenAI.",
        "Do not generate CH005–CH019. Do not reuse a historical remaining budget.",
        "Do not request chapter-by-chapter authorization.",
        "Wait for the explicit single 13-chapter authorization and its global cap.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
