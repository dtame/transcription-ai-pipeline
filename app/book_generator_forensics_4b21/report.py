"""Markdown report for Phase 4B.2.1."""

from __future__ import annotations

from typing import Any, Mapping


def _line(label: str, value: Any) -> str:
    return f"{label} = {value}"


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    tests = dict(bundle.get("tests") or {})
    empty = dict(bundle.get("empty_paragraph") or {})
    connective = dict(bundle.get("connective_claim") or {})
    illustration = dict(bundle.get("invented_illustration") or {})
    future = dict(bundle.get("future_request") or {})
    cost = dict(bundle.get("future_cost") or {})
    architecture = dict(bundle.get("semantic_architecture") or {})
    identities = dict(bundle.get("identities") or {})
    replay = dict(bundle.get("replay") or {})
    lines = [
        "# PHASE 4B.2.1 — BOOK GENERATOR CANARY FORENSICS + HARDENING",
        "",
        "## Result",
        "",
        str(header.get("result") or "FAIL"),
        "",
        _line("REAL PROVIDER CALLS", header.get("real_provider_calls", 0)),
        "",
        _line("4B.2 HISTORICAL STATUS", header.get("historical_4b2_status")),
        "",
        _line("SOURCE MAP UNCHANGED", header.get("source_map_unchanged")),
        "",
        _line("EDITORIAL PLAN UNCHANGED", header.get("editorial_plan_unchanged")),
        "",
        _line("CLEAN TRANSCRIPT UNCHANGED", header.get("clean_transcript_unchanged")),
        "",
        _line("4B.2 RAW RESPONSE UNCHANGED", header.get("raw_response_unchanged")),
        "",
        _line("4B.2 CANDIDATE UNCHANGED", header.get("candidate_unchanged")),
        "",
        _line("EMPTY PARAGRAPH HANDLE", header.get("empty_paragraph_handle")),
        "",
        _line("EMPTY PARAGRAPH ROOT CAUSE", header.get("empty_paragraph_root_cause")),
        "",
        _line("VALIDATOR CORRECT", header.get("validator_correct")),
        "",
        _line("CONNECTIVE CLAIM HANDLE", header.get("connective_claim_handle")),
        "",
        _line(
            "CONNECTIVE CLAIM CLASSIFICATION",
            header.get("connective_claim_classification"),
        ),
        "",
        _line("CONNECTIVE CLAIM SUPPORTED", header.get("connective_claim_supported")),
        "",
        _line("INVENTED ILLUSTRATION HANDLE", header.get("invented_illustration_handle")),
        "",
        _line("ILLUSTRATION CLASSIFICATION", header.get("illustration_classification")),
        "",
        _line(
            "ILLUSTRATION SOURCE-SUPPORTED",
            header.get("illustration_source_supported"),
        ),
        "",
        _line("HYDRATION DEFECT", header.get("hydration_defect")),
        "",
        _line("GENERATION GRANULARITY DEFECT", header.get("generation_granularity_defect")),
        "",
        _line("OUTPUT BUDGET DEFECT", header.get("output_budget_defect")),
        "",
        _line(
            "THINKING CONFIGURATION DEFECT",
            header.get("thinking_configuration_defect"),
        ),
        "",
        _line("SELECTED HARDENING", header.get("selected_hardening")),
        "",
        _line("SUCCESSOR PROMPT", header.get("successor_prompt")),
        "",
        _line("TRANSPORT", header.get("transport")),
        "",
        _line("SCHEMA CHANGED", header.get("schema_changed")),
        "",
        _line("SCHEMA LIMITATION", header.get("schema_limitation")),
        "",
        _line("LOCAL VALIDATOR CHANGED", header.get("local_validator_changed")),
        "",
        _line("NEW GRAMMAR CANARY REQUIRED", header.get("new_grammar_canary_required")),
        "",
        _line("SEMANTIC VALIDATION STRATEGY", header.get("semantic_validation_strategy")),
        "",
        _line("FUTURE CH016 REQUEST SHA256", header.get("future_ch016_request_sha256")),
        "",
        _line("FUTURE REQUEST DETERMINISM", header.get("future_request_determinism")),
        "",
        _line("FUTURE MODEL", header.get("future_model")),
        "",
        _line("FUTURE THINKING", header.get("future_thinking")),
        "",
        _line("FUTURE MAX_OUTPUT", header.get("future_max_output")),
        "",
        _line("FUTURE HYDRATION", header.get("future_hydration")),
        "",
        _line("FUTURE ESTIMATED COST", header.get("future_estimated_cost")),
        "",
        _line(
            "FAKEAI TESTS",
            "PASS" if tests.get("new_failures") == 0 else "FAIL",
        ),
        "",
        _line(
            "TOTAL TESTS",
            tests.get("passed") or tests.get("summary") or tests.get("skipped"),
        ),
        "",
        _line("NEW FAILURES", tests.get("new_failures")),
        "",
        _line("book.json", header.get("book_json")),
        "",
        _line(
            "READY_FOR_ONE_HARDENED_CH016_CANARY",
            header.get("ready_for_one_hardened_ch016_canary"),
        ),
        "",
        _line("READY_FOR_PRODUCTION_PREFLIGHT", header.get("ready_for_production_preflight")),
        "",
        _line(
            "READY_FOR_FULL_REAL_BOOK_GENERATION",
            header.get("ready_for_full_real_book_generation"),
        ),
        "",
        _line("NEXT ACTION", header.get("next_action")),
        "",
        "## Notes",
        "",
        "Zero provider calls. Historical 4B.2 remains FAIL permanently.",
        "",
        (
            "Clean transcript: "
            f"{identities.get('clean_transcript', {}).get('path')} "
            f"SHA-256={identities.get('clean_transcript', {}).get('sha256')}"
        ),
        "",
        (
            "Historical candidate file SHA-256="
            f"{identities.get('candidate_file_sha256')}; "
            "canonical SHA-256="
            f"{identities.get('candidate_canonical_sha256')}."
        ),
        "",
        (
            f"Empty paragraph {empty.get('provider_handle')} raw text case="
            f"{empty.get('empty_text_case')}; evidence case="
            f"{empty.get('empty_evidence_case')}. Schema accepted empty `t` "
            "because Anthropic structured output cannot express minLength. "
            "Local validator correctly rejected it. VALIDATOR_DEFECT=NO."
        ),
        "",
        (
            f"Connective closer {connective.get('provider_handle')} classified "
            f"{connective.get('classification')}. The new proposition is not "
            "supported by supplied IDEA/EX/REF/UNC/SRC evidence. Provider "
            "self-label kind=con is not trusted."
        ),
        "",
        (
            f"Invented illustration in {illustration.get('provider_handle')} "
            f"classified {illustration.get('classification')}. Funeral-verse "
            "scenario is absent from canonical CH016 evidence. This is not "
            "an invented Bible reference."
        ),
        "",
        (
            "Historical raw response replayed through the strengthened "
            f"validator: {replay.get('status')}. Empty paragraph still FAIL. "
            "No silent drop / retroactive PASS."
        ),
        "",
        (
            f"Successor prompt {header.get('successor_prompt')} is a narrow "
            "hardening of frozen book-generator-1.0. Transport and schema "
            "bytes are unchanged. NEW_GRAMMAR_CANARY_REQUIRED=NO."
        ),
        "",
        (
            "Semantic validation strategy is HYBRID: BookGenerationValidator "
            "for deterministic checks; human review for the next single "
            "hardened CH016 canary; future independent OpenAI gpt-5.6-terra "
            "chapter-level semantic gate before cache accept. Phase 5 is not "
            "started. Estimated Terra 19-chapter gate cost is architecture "
            f"only ({(cost.get('future_terra_chapter_semantic_gate') or {}).get('estimated_cost_usd_19_chapters')})."
        ),
        "",
        (
            "Future CH016 request uses the production builder, language=en, "
            f"model=claude-sonnet-5, thinking=disabled, max_output=16384, "
            f"hydration unchanged. SHA-256={future.get('request_sha256')}. "
            f"Determinism={future.get('determinism')}. Differs from historical "
            f"4B.2 request. Cache signature changes with prompt 1.0.1."
        ),
        "",
        "book.json is not published. Do not send the future request. Wait for human review.",
        "",
    ]
    return "\n".join(lines)
