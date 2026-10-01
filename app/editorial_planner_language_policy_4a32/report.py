"""Markdown report for Phase 4A.3.2."""

from __future__ import annotations

from typing import Any, Mapping


def _v(header: Mapping[str, Any], key: str, default: str = "...") -> Any:
    value = header.get(key)
    if value is None or value == "":
        return default
    return value


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    return "\n".join(
        [
            "# PHASE 4A.3.2 — CANONICAL DOCUMENT LANGUAGE POLICY + PLANNER PREFLIGHT",
            "",
            "## Result",
            "",
            str(_v(header, "result", "FAIL")),
            "",
            f"REAL PROVIDER CALLS = {_v(header, 'real_provider_calls', 0)}",
            "",
            f"A.3 HISTORICAL STATUS = {_v(header, 'a3_historical_status')}",
            "",
            f"A.3.1 = {_v(header, 'a31_status')}",
            "",
            f"CANONICAL LANGUAGE SOURCE = {_v(header, 'canonical_language_source')}",
            "",
            f"CANONICAL DOCUMENT LANGUAGE = {_v(header, 'canonical_document_language')}",
            "",
            f"LANGUAGE POLICY = {_v(header, 'language_policy')}",
            "",
            f"TRANSLATION DURING SOURCE GENERATION = {_v(header, 'translation_during_source_generation')}",
            "",
            f"TRANSLATION AFTER COMPLETED SOURCE DOCUMENT = {_v(header, 'translation_after_source_document')}",
            "",
            f"HISTORICAL PROMPT = {_v(header, 'historical_prompt')}",
            "",
            f"NEW PROMPT = {_v(header, 'new_prompt')}",
            "",
            f"HISTORICAL PROMPT MUTATED = {_v(header, 'historical_prompt_mutated')}",
            "",
            f"TRANSPORT = {_v(header, 'transport')}",
            "",
            f"SCHEMA RAW / ADAPTED = {_v(header, 'schema_raw_adapted')}",
            "",
            f"SCHEMA HASH = {_v(header, 'schema_hash')}",
            "",
            f"SCHEMA CHANGED = {_v(header, 'schema_changed')}",
            "",
            f"NEW GRAMMAR CANARY REQUIRED = {_v(header, 'new_grammar_canary_required')}",
            "",
            f"PROVIDER = {_v(header, 'provider')}",
            "",
            f"MODEL = {_v(header, 'model')}",
            "",
            f"THINKING = {_v(header, 'thinking')}",
            "",
            f"MAX_OUTPUT = {_v(header, 'max_output')}",
            "",
            f"HISTORICAL A.3 REQUEST SHA256 = {_v(header, 'historical_a3_request_sha256')}",
            "",
            f"NEW EXACT REQUEST SHA256 = {_v(header, 'new_exact_request_sha256')}",
            "",
            f"REQUEST CHANGED = {_v(header, 'request_changed')}",
            "",
            f"REQUEST DETERMINISM = {_v(header, 'request_determinism')}",
            "",
            f"IDEA INPUT COVERAGE = {_v(header, 'idea_input_coverage')}",
            "",
            f"UNKNOWN REFS = {_v(header, 'unknown_refs')}",
            "",
            f"INPUT ESTIMATE = {_v(header, 'input_estimate')}",
            "",
            f"OUTPUT EXPECTED / CONSERVATIVE / HARD = {_v(header, 'output_expected_conservative_hard')}",
            "",
            f"CONTEXT SAFETY = {_v(header, 'context_safety')}",
            "",
            f"ESTIMATED COST = {_v(header, 'estimated_cost')}",
            "",
            f"LANGUAGE VALIDATION POLICY = {_v(header, 'language_validation_policy')}",
            "",
            f"A.3 FRENCH CANDIDATE = {_v(header, 'a3_french_candidate')}",
            "",
            f"NEW PROVIDER CALLS REQUIRED = {_v(header, 'new_provider_calls_required')}",
            "",
            f"READY_FOR_ONE_REAL_ENGLISH_EDITORIAL_PLANNER_CANARY = {_v(header, 'ready_for_one_real_english_editorial_planner_canary')}",
            "",
            f"READY_FOR_EDITORIAL_PLAN_PUBLICATION = {_v(header, 'ready_for_editorial_plan_publication')}",
            "",
            f"BOOK GENERATOR = {_v(header, 'book_generator')}",
            "",
            f"NEXT ACTION = {_v(header, 'next_action')}",
            "",
            "## Notes",
            "",
            "This phase is offline. The 1.0.1 request was built and hashed but not sent.",
            "The historical A.3 French candidate remains audit-only and unpublished.",
            "Future translation is a separate stage after a completed source-language book.",
            "",
        ]
    )


__all__ = ["render_report"]
