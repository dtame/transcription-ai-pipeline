"""Phase 4B.2.19 report."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_editorial_acceptance_4b219.constants import CANONICAL_PYTHON, CHAPTER_ID


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    idea = dict(bundle.get("idea_content_mapping_review") or {})
    coverage = dict(bundle.get("source_coverage_review") or {})
    scale = dict(bundle.get("scale_up_options") or {})
    prompt = dict(bundle.get("generator_prompt_readiness") or {})
    mapping_lines = [
        "| IDEA | Status | Paragraphs | SRC overlap used as proof |",
        "|---|---|---|---|",
    ]
    for row in idea.get("mappings") or []:
        mapping_lines.append(
            "| {idea_id} | {status} | {paragraphs} | NO |".format(
                idea_id=row.get("idea_id", ""),
                status=row.get("status", ""),
                paragraphs=", ".join(row.get("proposed_paragraphs") or []),
            )
        )
    coverage_lines = [
        "| Unit | Presence | Substantial omission | Separate human decision |",
        "|---|---|---|---|",
    ]
    for row in coverage.get("flagged_units") or []:
        coverage_lines.append(
            "| {id} | {presence} | {substantial} | {human} |".format(
                id=row.get("id", ""),
                presence=row.get("presence", ""),
                substantial="YES" if row.get("substantial") else "NO",
                human="YES" if row.get("separate_human_decision") else "NO",
            )
        )
    lines = [
        "**PHASE 4B.2.19 — CH012 EDITORIAL ACCEPTANCE & SEMANTIC VALIDATION READINESS**",
        "",
        f"RESULT = {header.get('result')}",
        "PROVIDER CALLS = 0",
        "ANTHROPIC HTTP = 0",
        "OPENAI HTTP = 0",
        f"CANONICAL PYTHON = {header.get('canonical_python') or CANONICAL_PYTHON}",
        f"CANONICAL HASHES = {header.get('canonical_hashes_pre_post')}",
        f"ACCEPTED CHAPTER = {header.get('accepted_chapter') or CHAPTER_ID}",
        f"HUMAN EDITORIAL ACCEPTANCE = {header.get('human_editorial_acceptance')}",
        f"P000001 ACCEPTED = {header.get('p000001_accepted')}",
        f"ACCEPTED MD SHA-256 = {header.get('accepted_md_sha256')}",
        f"ACCEPTED JSON SHA-256 = {header.get('accepted_json_sha256')}",
        f"MARKDOWN / JSON CONSISTENCY = {header.get('markdown_json_consistency')}",
        f"SECTIONS = {header.get('sections')}",
        f"PARAGRAPHS = {header.get('paragraphs')}",
        f"IDEA MAPPINGS CONTENT_SUPPORTED = {header.get('idea_mappings_content_supported')}",
        f"IDEA MAPPINGS PARTIALLY_SUPPORTED = {header.get('idea_mappings_partially_supported')}",
        f"IDEA MAPPINGS NOT_SUPPORTED = {header.get('idea_mappings_not_supported')}",
        f"IDEA MAPPINGS UNDETERMINED = {header.get('idea_mappings_undetermined')}",
        f"SOURCE COVERAGE STATUS = {header.get('source_coverage_status')}",
        "SEMANTIC CERTIFICATION = NOT PERFORMED",
        "SEMANTIC GATE PROMOTED = NO",
        f"GENERATOR PROMPT READY = {header.get('generator_prompt_ready')}",
        f"ESTIMATED NEXT PHASE COST = {header.get('estimated_next_phase_cost')}",
        f"RECOMMENDED NEXT OPTION = {header.get('recommended_next_option')}",
        f"READY_FOR_CONTROLLED_SCALE_UP = {header.get('ready_for_controlled_scale_up')}",
        "READY_FOR_FULL_REAL_BOOK_GENERATION = NO",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"NEXT ACTION = {header.get('next_action')}",
        "",
        "## Why this result",
        "",
        str(header.get("notes") or ""),
        "",
        "## Human editorial acceptance",
        "",
        "The user explicitly approved the corrected CH012 chapter, including "
        "reading quality, the four-section organization, faithful restatement, "
        "authorial narrative voice, the 4B.2.18 corrections, and the current "
        "P000001 wording without further change.",
        "",
        "This record is an editorial acceptance. It is not a digital signature, "
        "not a legal or cryptographic user approval, not a semantic certificate, "
        "and not proof of exhaustive source coverage. Publication is not granted.",
        "",
        "## Accepted pair freeze",
        "",
        f"Markdown SHA-256 = {header.get('accepted_md_sha256')}",
        f"JSON SHA-256 = {header.get('accepted_json_sha256')}",
        "Historical 4B.2.17 artifacts and the provider lock were not moved or overwritten.",
        f"Markdown/JSON consistency = {header.get('markdown_json_consistency')}.",
        "",
        "## IDEA content mappings",
        "",
        "SRC overlap was recorded and was never used as sufficient proof.",
        "An idea may split across paragraphs. A paragraph may support more than one idea.",
        "The accepted `paras[].e` fields were not written.",
        "",
        *mapping_lines,
        "",
        "## Source coverage of previously flagged units",
        "",
        *coverage_lines,
        "",
        "The 4B.2.16 heuristic is not semantic proof. No substantial omission "
        "requires rewriting the accepted chapter. EX030's neighboring "
        "'losing strength' detail remains a possible minor omission for a "
        "separate human decision if that detail is judged essential.",
        "",
        "## Semantic validation readiness",
        "",
        "Fourteen actual paragraphs. Strategy A, one request per paragraph, "
        "remains a later option only. Estimated Terra analog cost uses the "
        "h01 figure and is a hypothesis. Reasoning-token billing and "
        "long-context pricing stay UNKNOWN. The historical Semantic Gate "
        "was not promoted and was not called.",
        "",
        "## Generator prompt 1.1",
        "",
        f"Version = {prompt.get('version')}.",
        f"Ready as reference candidate = {prompt.get('ready_as_reference_candidate')}.",
        "Ready for production = NO. Automatically promoted = NO.",
        "The prompt contains strict fidelity, controlled thematic reorganization, "
        "authorial voice, prudent attribution, preservation of nuances, examples, "
        "and references, IDEA-handle traceability, and a validator-compatible "
        "output contract. It remains unregistered, inactive, and unused in a "
        "real call.",
        "",
        "## Scale-up recommendation",
        "",
        f"Recommended option = {scale.get('recommended_option')}.",
        "OPTION A is not justified: no substantial unresolved CH012 risk requires a provider call.",
        "OPTION B is not required: voice and restatement are already accepted; "
        "1.1 handle robustness can be controlled by a first remaining-chapter hard stop.",
        "OPTION C is preferred: prepare controlled generation of the remaining 18 "
        "chapters, chapter by chapter, without executing any of them now.",
        "",
        "READY_FOR_CONTROLLED_SCALE_UP remains NO because preparation is not "
        "execution. No remaining-chapter authorization exists. Prompt 1.1 is "
        "inactive. Semantic certification has not been performed. book.json "
        "is unpublished.",
        "",
        "## Historical results left in place",
        "",
        "4B.2.12 remains PASS. 4B.2.13 remains PASS. 4B.2.14 remains PASS.",
        "4B.2.15 remains PARTIAL. 4B.2.16 remains PASS. 4B.2.17 remains PARTIAL.",
        "4B.2.18 remains PASS.",
        "h01, h02, and h11 remain PARTIAL.",
        "",
        "## Stop",
        "",
        "STOP. No Sonnet call. No Terra call. No CH012 regeneration.",
        "No correction of the accepted chapter. No global activation.",
        "No book.json. No DOCX/PDF. Wait for the human decision on the next step.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
