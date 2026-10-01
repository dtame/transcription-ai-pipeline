"""Markdown report Phase 4A.3.1."""

from __future__ import annotations

from typing import Any, Mapping


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    identity = dict(bundle.get("identity") or {})
    language = dict(bundle.get("language") or {})
    policy = dict(bundle.get("policy") or {})
    title = dict(bundle.get("title") or {})
    assignments = dict(bundle.get("assignments") or {})
    chapters = dict(bundle.get("chapters") or {})
    sections = dict(bundle.get("sections") or {})
    calibration = dict(bundle.get("calibration") or {})
    flagged = list(assignments.get("flagged") or [])
    lines = [
        "# PHASE 4A.3.1 — REAL EDITORIAL PLAN SEMANTIC FORENSICS",
        "",
        "## Result",
        "",
        str(header.get("result") or "FAIL"),
        "",
        f"REAL PROVIDER CALLS = {header.get('real_provider_calls', 0)}",
        "",
        f"A.3 HISTORICAL STATUS = {header.get('a3_historical_status')}",
        "",
        f"A.3 TECHNICAL CONTRACT = {header.get('a3_technical_contract')}",
        "",
        f"A.3 RAW RESPONSE UNCHANGED = {header.get('a3_raw_response_unchanged')}",
        "",
        f"A.3 CANDIDATE UNCHANGED = {header.get('a3_candidate_unchanged')}",
        "",
        f"SOURCE MAP UNCHANGED = {header.get('source_map_unchanged')}",
        "",
        f"SOURCE PRIMARY LANGUAGE = {header.get('source_primary_language')}",
        "",
        f"EDITORIAL PLAN LANGUAGE = {header.get('editorial_plan_language')}",
        "",
        f"EXPLICIT PRE-A3 LANGUAGE CONTRACT = {header.get('explicit_pre_a3_language_contract')}",
        "",
        f"LANGUAGE CONTRACT RESULT = {header.get('language_contract_result')}",
        "",
        f"RECOMMENDED GENERIC LANGUAGE POLICY = {header.get('recommended_generic_language_policy')}",
        "",
        f"BOOK_LANGUAGE_REQUIRES_HUMAN_DECISION = {header.get('book_language_requires_human_decision')}",
        "",
        f"WORKING TITLE = {header.get('working_title')}",
        "",
        f"TITLE STATUS = {header.get('title_status')}",
        "",
        "FINAL_TITLE_APPROVED = NO",
        "",
        f"IDEAS REVIEWED = {header.get('ideas_reviewed')}",
        "",
        f"STRONG_FIT = {header.get('strong_fit')}",
        "",
        f"ACCEPTABLE_FIT = {header.get('acceptable_fit')}",
        "",
        f"QUESTIONABLE_FIT = {header.get('questionable_fit')}",
        "",
        f"LIKELY_SHOULD_DEFER = {header.get('likely_should_defer')}",
        "",
        f"LIKELY_SHOULD_EXCLUDE = {header.get('likely_should_exclude')}",
        "",
        f"286/286 ASSIGNMENT RESULT = {header.get('assignment_result')}",
        "",
        f"CHAPTER ARCHITECTURE = {header.get('chapter_architecture')}",
        "",
        f"SECTION ARCHITECTURE = {header.get('section_architecture')}",
        "",
        f"INVENTION BOUNDARY = {header.get('invention_boundary')}",
        "",
        f"UNCERTAINTY PRESERVATION = {header.get('uncertainty_preservation')}",
        "",
        f"A.3 ACTUAL INPUT = {header.get('a3_actual_input')}",
        "",
        f"A.3 ACTUAL OUTPUT = {header.get('a3_actual_output')}",
        "",
        f"A.3 THINKING = {header.get('a3_thinking')}",
        "",
        f"A.3 COST = {header.get('a3_cost')}",
        "",
        f"A.3.1 COST = {header.get('a31_cost')}",
        "",
        f"MAX_OUTPUT = {header.get('max_output')}",
        "",
        f"OUTPUT UTILIZATION = {header.get('output_utilization')}",
        "",
        f"TRANSPORT CHANGE REQUIRED = {header.get('transport_change_required')}",
        "",
        f"SCHEMA CHANGE REQUIRED = {header.get('schema_change_required')}",
        "",
        f"FUTURE PROMPT CHANGE REQUIRED = {header.get('future_prompt_change_required')}",
        "",
        f"NEW GRAMMAR CANARY REQUIRED = {header.get('new_grammar_canary_required')}",
        "",
        f"NEW PROVIDER CALL REQUIRED TO VALIDATE CURRENT CANDIDATE = {header.get('new_provider_call_required_to_validate_current_candidate')}",
        "",
        f"SEMANTIC REVIEW = {header.get('semantic_review')}",
        "",
        f"PUBLICATION_ELIGIBLE = {header.get('publication_eligible')}",
        "",
        "editorial_plan.json = NOT PUBLISHED",
        "",
        f"READY_FOR_CONTROLLED_EDITORIAL_PLAN_PUBLICATION = {header.get('ready_for_controlled_editorial_plan_publication')}",
        "",
        "BOOK GENERATOR = NOT STARTED",
        "",
        f"NEXT ACTION = {header.get('next_action')}",
        "",
        "## Notes",
        "",
        "A.3.1 is an offline forensic phase. Historical A.3 remains PARTIAL. "
        "Zero provider calls. Candidate, raw response, and SourceMap were not modified. "
        "editorial_plan.json was not published. Book Generator was not started.",
        "",
        "Phase execution PASS is not candidate acceptance. Semantic review remains "
        "REVIEW_REQUIRED because book/editorial language still requires an explicit "
        "human decision. The French plan is not an explicit contract violation: "
        "editorial-planner-1.0 had no output-language rule.",
        "",
        f"Candidate SHA-256 = {identity.get('candidate_sha256')}",
        "",
        f"SourceMap SHA-256 = {identity.get('source_map_sha256')}",
        "",
        f"Source primary language = {language.get('source_primary_language')}",
        "",
        f"Editorial plan language = {language.get('editorial_plan_language')}",
        "",
        f"Language contract result = {language.get('language_contract_result')}",
        "",
        f"Recommended policy = {policy.get('recommended_generic_language_policy')}",
        "",
        f"Successor prompt if a future call needs a language instruction = {header.get('successor_prompt')}",
        "",
        "Do not mutate editorial-planner-1.0 in place. A language instruction is "
        "prompt semantics, not transport grammar; no new grammar canary is required "
        "for that instruction alone.",
        "",
        f"Working title status = {title.get('status')}. FINAL_TITLE_APPROVED = NO.",
        "",
        f"Assignment result = {assignments.get('assignment_result')}. "
        "100% ASSIGNED is permitted. DEFERRED/EXCLUDED are not required to occur.",
        "",
        f"Chapter architecture = {chapters.get('status')}. "
        f"Section architecture = {sections.get('status')}. "
        "French titles were not treated as structural defects.",
        "",
        f"A.3 input {calibration.get('a3_input_tokens')} vs A.2 local "
        f"{calibration.get('a2_local_input_estimate')} / provider-adjusted "
        f"{calibration.get('a2_provider_adjusted_pessimistic')} / planning "
        f"{calibration.get('a2_planning_input_estimate')}. "
        f"Output {calibration.get('a3_output_tokens')} is above expected "
        f"{calibration.get('a2_expected_output')} and below conservative "
        f"{calibration.get('a2_conservative_output')}. "
        f"Thinking {calibration.get('a3_thinking')} vs A.1 synthetic "
        f"{calibration.get('a1_thinking')}.",
        "",
        "## Human decision required",
        "",
        str(policy.get("human_decision_required") or ""),
        "",
        "## Questionable assignments",
        "",
    ]
    if not flagged:
        lines.append("None.")
        lines.append("")
    else:
        for item in flagged:
            lines.append(
                f"- {item.get('idea_id')} [{item.get('assigned_ch')}/{item.get('assigned_sec')}] "
                f"{item.get('fit')}: {item.get('source_supported_description')}"
            )
            lines.append(f"  Reason: {item.get('reason')}")
            lines.append("")
    lines.extend(
        [
            "WAIT FOR HUMAN REVIEW.",
            "",
        ]
    )
    return "\n".join(lines)
