"""Phase 4B.2.16 report."""

from __future__ import annotations

from typing import Any, Mapping


def render_report(header: Mapping[str, Any]) -> str:
    obstacles = header.get("obstacles") or []
    obstacle_lines = "\n".join(f"{index}. {item}" for index, item in enumerate(obstacles, start=1))
    lines = [
        "**PHASE 4B.2.16 — FAITHFUL THEMATIC REORGANIZATION & SEMANTIC ALIGNMENT**",
        "",
        f"RESULT = {header.get('result')}",
        "PROVIDER CALLS = 0",
        "OPENAI HTTP = 0",
        "ANTHROPIC HTTP = 0",
        f"CANONICAL PYTHON = {header.get('canonical_python')}",
        f"CANONICAL HASHES PRE/POST = {header.get('canonical_hashes')}",
        f"EDITORIAL POLICY = {header.get('editorial_policy')}",
        f"FAITHFUL GENERATOR PROMPT = {header.get('faithful_prompt')}",
        "HISTORICAL GENERATOR PROMPT MODIFIED = NO",
        "HISTORICAL SEMANTIC CONTRACT MODIFIED = NO",
        f"THEMATIC REORGANIZATION RULES = {header.get('thematic_rules')}",
        f"SOURCE COVERAGE = {header.get('source_coverage')}",
        f"SEMANTIC GATE ALIGNMENT = {header.get('semantic_alignment')}",
        f"HUMAN RESOLUTION = {header.get('human_resolution')}",
        f"PILOT CHAPTER = {header.get('pilot_chapter')}",
        f"PILOT CHAPTER SECTIONS = {header.get('pilot_sections')}",
        f"PILOT CHAPTER IDEAS = {header.get('pilot_ideas')}",
        f"PILOT CHAPTER COST = {header.get('pilot_cost')}",
        f"PHASE 5 COST = {header.get('phase5_cost')}",
        f"OFFLINE TESTS PASSED / FAILED = {header.get('tests_passed')} / {header.get('tests_failed')}",
        f"NEW REGRESSIONS = {header.get('new_regressions')}",
        "PRODUCTION PIPELINE MODIFIED = NO",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_ONE_REAL_PILOT_CHAPTER = {header.get('ready_for_one_real_pilot_chapter')}",
        "READY_FOR_FULL_REAL_BOOK_GENERATION = NO",
        "NEXT ACTION = HUMAN REVIEW",
        "",
        "## Principle",
        "",
        "The book restores the original teaching in an organized, coherent, and readable form.",
        "Thematic reorganization is authorized. New arguments, examples, causalities, implications, guarantees, and conclusions are not.",
        "Fidelity also requires keeping important ideas, reasonings, examples, and nuances.",
        "",
        "## Responsibility split",
        "",
        "The Editorial Planner keeps thematic organization, idea assignment, and chapter and section structure.",
        "The Book Generator keeps faithful wording, readability, and preservation of reasonings, examples, and nuances.",
        "Those planner responsibilities are not moved into the generator.",
        "",
        "## Historical results",
        "",
        "4B.2.12 remains PASS. 4B.2.13 remains PASS. 4B.2.14 remains PASS.",
        "4B.2.15 remains PARTIAL. 4B.2.11 remains PARTIAL.",
        "h01, h02, and h11 remain PARTIAL. The h11 human label remains UNSUPPORTED.",
        "None of these results is requalified.",
        "",
        "## Pilot obstacles",
        "",
        obstacle_lines or "None.",
        "",
        "## Notes",
        "",
        str(header.get("notes") or ""),
        "",
        "STOP. No Terra call. No Sonnet call. No CH016 generation. No real chapter generation.",
        "No generation of the 19 chapters. No Semantic Gate promotion. No production-bridge activation.",
        "No production-cache write. No book.json. No Phase 5. No Word or PDF.",
        "Wait for human review before the first real pilot chapter.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
