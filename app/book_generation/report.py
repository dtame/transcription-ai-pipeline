"""Markdown report for Phase 4B.1."""

from __future__ import annotations

from typing import Any, Mapping


def _line(label: str, value: Any) -> str:
    return f"{label} = {value}"


def render_report(bundle: Mapping[str, Any], *, tests: str = "offline Phase 4B.1") -> str:
    header = dict(bundle.get("header") or {})
    schema = dict(bundle.get("schema_identity") or {})
    fake = dict(bundle.get("fakeai") or {})
    cost = dict(bundle.get("cost_estimate") or {})
    thinking = dict(bundle.get("thinking") or {})
    dist = dict(header.get("chapter_size_distribution") or {})
    preflight = dict(bundle.get("preflight") or {})
    lines = [
        "# PHASE 4B.1 — BOOK GENERATOR ARCHITECTURE + OFFLINE FOUNDATION",
        "",
        "## Result",
        "",
        str(header.get("result") or "FAIL"),
        "",
        _line("REAL PROVIDER CALLS", header.get("real_provider_calls", 0)),
        "",
        _line("SOURCE MAP SHA256", header.get("source_map_sha256")),
        "",
        _line("EDITORIAL PLAN SHA256", header.get("editorial_plan_sha256")),
        "",
        _line("EDITORIAL PLAN STATUS", header.get("editorial_plan_status")),
        "",
        _line("CANONICAL LANGUAGE", header.get("canonical_language")),
        "",
        _line("PRODUCTION MODEL", header.get("production_model")),
        "",
        _line("BOOK GENERATOR PROMPT", header.get("book_generator_prompt")),
        "",
        _line("BOOK GENERATION TRANSPORT", header.get("book_generation_transport")),
        "",
        _line(
            "SCHEMA RAW / ADAPTED",
            f"{schema.get('raw_schema_bytes')} / {schema.get('adapted_schema_bytes')}",
        ),
        "",
        _line("SCHEMA SHA256", header.get("schema_sha256")),
        "",
        _line("GENERATION UNIT", header.get("generation_unit")),
        "",
        _line("FALLBACK UNIT", header.get("fallback_unit")),
        "",
        _line("EVIDENCE STRATEGY", header.get("evidence_strategy")),
        "",
        _line("TRANSCRIPT HYDRATION", header.get("transcript_hydration")),
        "",
        _line("TRANSCRIPT ARTIFACT", header.get("transcript_artifact")),
        "",
        _line("CHAPTERS", header.get("chapters")),
        "",
        _line("SECTIONS", header.get("sections")),
        "",
        _line("IDEAS", header.get("ideas")),
        "",
        _line(
            "CHAPTER SIZE DISTRIBUTION",
            (
                f"sections {dist.get('sections')}; "
                f"ideas {dist.get('ideas')}; "
                f"evidence_chars {dist.get('evidence_chars')}"
            ),
        ),
        "",
        _line("OUTLIER CHAPTERS", header.get("outlier_chapters")),
        "",
        _line("SMALLEST REQUEST", header.get("smallest_request")),
        "",
        _line("MEDIAN REQUEST", header.get("median_request")),
        "",
        _line("LARGEST REQUEST", header.get("largest_request")),
        "",
        _line("CONTEXT SAFETY", header.get("context_safety")),
        "",
        _line("RECOMMENDED MAX_OUTPUT", header.get("recommended_max_output")),
        "",
        _line("THINKING POLICY", header.get("thinking_policy")),
        "",
        _line("EXPECTED BOOK LENGTH RANGE", header.get("expected_book_length_range")),
        "",
        _line("ESTIMATED PRODUCTION CALLS", header.get("estimated_production_calls")),
        "",
        _line("ESTIMATED PRODUCTION COST", header.get("estimated_production_cost")),
        "",
        _line("PARAGRAPH TRACEABILITY", header.get("paragraph_traceability")),
        "",
        _line("IDEA ACCOUNTABILITY", header.get("idea_accountability")),
        "",
        _line("SECTION ACCOUNTABILITY", header.get("section_accountability")),
        "",
        _line("CACHE / RESUME", header.get("cache_resume")),
        "",
        _line("FAKEAI TESTS", header.get("fakeai_tests")),
        "",
        _line("TOTAL TESTS", tests),
        "",
        _line("NEW FAILURES", header.get("new_failures")),
        "",
        "book.json = NOT PUBLISHED",
        "",
        _line(
            "READY_FOR_BOOK_GENERATOR_GRAMMAR_CANARY",
            header.get("ready_for_book_generator_grammar_canary"),
        ),
        "",
        "READY_FOR_REAL_BOOK_GENERATION = NO",
        "",
        "NEXT ACTION = HUMAN REVIEW",
        "",
        "## Notes",
        "",
        f"Working title remains {header.get('working_title')!r} (not final-approved).",
        "",
        f"Thinking capabilities known={thinking.get('capabilities_known')}; "
        f"Book Generator thinking validated="
        f"{thinking.get('book_generator_thinking_validated')}.",
        "",
        f"Cost status={cost.get('status')}; "
        f"preflight chapters={sorted(preflight)}.",
        "",
        f"FakeAI cases ok={fake.get('status')}.",
        "",
    ]
    return "\n".join(lines)
