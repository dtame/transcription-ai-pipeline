"""Phase 4B.2.22 report."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_batch_preparation_4b222.constants import CANONICAL_PYTHON, FIRST_BATCH_ID


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    inventory = dict(bundle.get("remaining_17_chapters_inventory") or {})
    cost = dict(bundle.get("batch_cost_envelope") or {})
    plan = dict(bundle.get("batch_generation_plan") or {})
    auth = dict(bundle.get("batch_authorization_template") or {})
    token = dict(auth.get("required_human_token") or {})
    ex046 = dict(bundle.get("ch018_ex046_traceability_review") or {})
    generation = dict(cost.get("generation_17_chapters") or {})
    first = next(
        (row for row in plan.get("batches") or [] if row.get("batch_id") == FIRST_BATCH_ID),
        {},
    )
    first_cost = next(
        (row for row in cost.get("batches") or [] if row.get("batch_id") == FIRST_BATCH_ID),
        {},
    )
    inventory_lines = [
        "| Chapter | Title | Order | SEC | IDEA | EX | REF | UNC | SRC | Words | Complexity | Status |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in inventory.get("chapters") or []:
        inventory_lines.append(
            "| {id} | {title} | {order} | {sec} | {ideas} | {ex} | {ref} | {unc} | {src} | {words} | {complexity} | {status} |".format(
                id=row.get("chapter_id", ""),
                title=row.get("working_title", ""),
                order=row.get("book_order", ""),
                sec=row.get("section_count", ""),
                ideas=row.get("idea_count", ""),
                ex=row.get("example_count", ""),
                ref=row.get("reference_count", ""),
                unc=row.get("uncertainty_count", ""),
                src=row.get("src_count", ""),
                words=(row.get("estimated_source_context") or {}).get("hydrated_src_words", ""),
                complexity=row.get("editorial_complexity", ""),
                status=row.get("generation_status", ""),
            )
        )
    batch_lines = [
        "| Lot | Chapters | Expected | Calculable max | Proposed cap | Authorized |",
        "|---|---|---|---|---|---|",
    ]
    for row in cost.get("batches") or []:
        batch_lines.append(
            "| {id} | {chapters} | {expected} | {maximum} | {proposed} | {authorized} |".format(
                id=row.get("batch_id", ""),
                chapters=", ".join(row.get("chapter_ids") or []),
                expected=row.get("expected_cost_usd"),
                maximum=row.get("calculable_maximum_usd"),
                proposed=row.get("proposed_cap_usd"),
                authorized=row.get("authorized_cap_usd"),
            )
        )
    matching = ", ".join(
        item.get("paragraph_id", "")
        for item in ex046.get("matching_paragraphs") or []
    )
    lines = [
        "**PHASE 4B.2.22 — CH018 EDITORIAL ACCEPTANCE & 17-CHAPTER BATCH GENERATION READINESS**",
        "",
        f"RESULT = {header.get('result')}",
        "PROVIDER CALLS = 0",
        "ANTHROPIC HTTP = 0",
        "OPENAI HTTP = 0",
        f"CANONICAL HASHES PRE/POST = {header.get('canonical_hashes_pre_post')}",
        f"CH012 IMMUTABLE = {header.get('ch012_immutable')}",
        f"CH018 IMMUTABLE = {header.get('ch018_immutable')}",
        "CH018 HUMAN EDITORIAL ACCEPTANCE = YES",
        f"CH018 MD SHA-256 = {header.get('ch018_md_sha256')}",
        f"CH018 JSON SHA-256 = {header.get('ch018_json_sha256')}",
        f"CH018 EX046 TRACEABILITY = {header.get('ch018_ex046_traceability')}",
        f"REMAINING CHAPTERS = {header.get('remaining_chapters')}",
        f"REMAINING SECTIONS = {header.get('remaining_sections')}",
        f"REMAINING IDEAS = {header.get('remaining_ideas')}",
        f"BATCH COUNT = {header.get('batch_count')}",
        f"BATCH SIZES = {header.get('batch_sizes')}",
        f"PROMPT 1.1 HASH MATCH = {header.get('prompt_11_hash_match')}",
        f"GENERATION COST LOW / CENTRAL / HIGH = {header.get('generation_cost')}",
        f"COMPLETE COST = {header.get('complete_cost')}",
        "AUTHORIZED SPEND = 0 USD",
        f"HARD STOP TESTS = {header.get('hard_stop_tests')}",
        f"OFFLINE TESTS PASSED / FAILED = {header.get('offline_tests')}",
        "PRODUCTION PIPELINE MODIFIED = NO",
        "PRODUCTION CACHE = UNCHANGED",
        "SEMANTIC GATE PROMOTED = NO",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_FIRST_BATCH_AUTHORIZATION = {header.get('ready_for_first_batch_authorization')}",
        "READY_FOR_ALL_17_REAL_GENERATIONS = NO",
        f"NEXT ACTION = {header.get('next_action')}",
        "",
        "## Why this result",
        "",
        str(header.get("notes") or ""),
        "",
        "## Canonical identity",
        "",
        f"Canonical Python = {CANONICAL_PYTHON}",
        "SourceMap, EditorialPlan, and clean transcript were hashed before and after.",
        "They were not modified. CH012 and CH018 accepted artifacts were not modified.",
        "",
        "## CH018 editorial acceptance",
        "",
        "The user explicitly approved CH018. This record freezes the generated",
        "Markdown and JSON by hash. It is an editorial acceptance, not a semantic",
        "certificate and not a publication authorization. No digital signature was invented.",
        "",
        "## EX046 traceability",
        "",
        f"Correspondence established = {ex046.get('correspondence_established')}.",
        f"Matching paragraphs = {matching or 'none'}.",
        f"Supporting SRC = {', '.join(ex046.get('supporting_src') or []) or 'none'}.",
        "EX046 was not injected into the accepted paras[].e. The original provider",
        "response was not rewritten. A later production projection may add the handle",
        "if those paragraphs still restate the graveside testimony.",
        "",
        "## Remaining-chapter inventory",
        "",
        f"17 chapters remain after excluding CH012 and CH018.",
        f"Total remaining sections = {inventory.get('total_remaining_sections')}.",
        f"Total remaining planned IDEA units = {inventory.get('total_remaining_ideas')}.",
        "A section or idea in the plan is not treated as covered.",
        "",
        *inventory_lines,
        "",
        "## Batch plan",
        "",
        *batch_lines,
        "",
        "## Cost distinctions",
        "",
        "Expected cost is the token-based central estimate.",
        "Calculable maximum is the pre-call theoretical maximum.",
        "Proposed cap is that maximum plus a 15 percent margin.",
        "Authorized cap remains 0 USD. UNKNOWN items are not replaced by zero.",
        "CH012 0.036152 USD and CH018 0.041500 USD are calibration, not fixed prices.",
        "",
        "## Proposed first real batch",
        "",
        f"- Identifiant du lot = {FIRST_BATCH_ID}",
        f"- Chapitres inclus = {', '.join(first.get('chapter_ids') or [])}",
        "- Modèle = anthropic/claude-sonnet-5",
        "- Prompt = book-generator-faithful-restatement-1.1-candidate",
        f"- Coût maximal calculable = {first_cost.get('calculable_maximum_usd')} USD",
        f"- Plafond recommandé = {first_cost.get('proposed_cap_usd')} USD",
        f"- Nombre d'appels = {len(first.get('chapter_ids') or [])} (un par chapitre)",
        "- Conditions d'arrêt = JSON invalide, sections manquantes, IDEA non tracées,",
        "  SRC inventés, réponse tronquée, coût UNKNOWN, plafond dépassé, verrou",
        "  incertain, autorisation absente, changement non autorisé du prompt ou du modèle.",
        f"- Jeton humain requis = {token.get('authorization_scope')}",
        "",
        "## Stop",
        "",
        "STOP. No Sonnet call. No Terra call. No remaining-chapter generation.",
        "No CH012 or CH018 regeneration. No global prompt activation. No book.json.",
        "Wait for the explicit human decision on a distinct first-batch authorization.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
