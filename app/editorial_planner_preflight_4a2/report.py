"""Rapport markdown Phase 4A.2."""

from __future__ import annotations

from typing import Any, Mapping


def _v(header: Mapping[str, Any], key: str, default: str = "...") -> Any:
    value = header.get(key)
    if value is None or value == "":
        return default
    return value


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    lines = [
        "# PHASE 4A.2 — EDITORIAL PLANNER EXACT PRODUCTION PREFLIGHT",
        "",
        "## Result",
        "",
        str(_v(header, "result", "FAIL")),
        "",
        f"REAL PROVIDER CALLS = {_v(header, 'real_provider_calls', 0)}",
        "",
        f"PHASE 4A = {_v(header, 'phase_4a', 'PASS')}",
        "",
        f"PHASE 4A.1 = {_v(header, 'phase_4a1', 'PASS')}",
        "",
        f"SOURCE MAP SHA256 = {_v(header, 'source_map_sha256')}",
        "",
        f"SOURCE MAP BYTES = {_v(header, 'source_map_bytes')}",
        "",
        f"SOURCE MAP INVENTORY = {_v(header, 'source_map_inventory')}",
        "",
        f"PROMPT = {_v(header, 'prompt')}",
        "",
        f"TRANSPORT = {_v(header, 'transport')}",
        "",
        f"SCHEMA RAW / ADAPTED = {_v(header, 'schema_raw_adapted')}",
        "",
        f"SCHEMA HASH = {_v(header, 'schema_hash')}",
        "",
        f"MODEL = {_v(header, 'model')}",
        "",
        f"THINKING MODE = {_v(header, 'thinking_mode')}",
        "",
        f"OPUS DEFAULT THINKING PREVIOUSLY OBSERVED = {_v(header, 'opus_default_thinking_previously_observed')}",
        "",
        f"EXACT REQUEST SHA256 = {_v(header, 'exact_request_sha256')}",
        "",
        f"EXACT REQUEST CHARS = {_v(header, 'exact_request_chars')}",
        "",
        f"EXACT REQUEST BYTES = {_v(header, 'exact_request_bytes')}",
        "",
        f"REQUEST DETERMINISM = {_v(header, 'request_determinism')}",
        "",
        f"LOCAL INPUT TOKEN ESTIMATE = {_v(header, 'local_input_token_estimate')}",
        "",
        f"PROVIDER-ADJUSTED INPUT ESTIMATE = {_v(header, 'provider_adjusted_input_estimate')}",
        "",
        f"PHASE 4A PROVIDER-ADJUSTED ESTIMATE = {_v(header, 'phase_4a_provider_adjusted_estimate')}",
        "",
        f"INPUT ESTIMATE DELTA = {_v(header, 'input_estimate_delta')}",
        "",
        f"EXPECTED OUTPUT = {_v(header, 'expected_output')}",
        "",
        f"CONSERVATIVE OUTPUT = {_v(header, 'conservative_output')}",
        "",
        f"HARD OUTPUT = {_v(header, 'hard_output')}",
        "",
        f"OLD PROPOSED MAX_OUTPUT = {_v(header, 'old_proposed_max_output')}",
        "",
        f"SELECTED PRODUCTION MAX_OUTPUT = {_v(header, 'selected_production_max_output')}",
        "",
        f"HARD OUTPUT UTILIZATION = {_v(header, 'hard_output_utilization')}",
        "",
        f"THINKING HEADROOM = {_v(header, 'thinking_headroom')}",
        "",
        f"OUTPUT BUDGET DECISION = {_v(header, 'output_budget_decision')}",
        "",
        f"TRANSPORT CHANGE REQUIRED = {_v(header, 'transport_change_required')}",
        "",
        f"PROMPT CHANGE REQUIRED = {_v(header, 'prompt_change_required')}",
        "",
        f"NEW GRAMMAR CANARY REQUIRED = {_v(header, 'new_grammar_canary_required')}",
        "",
        f"USABLE CONTEXT BUDGET = {_v(header, 'usable_context_budget')}",
        "",
        f"INPUT HEADROOM = {_v(header, 'input_headroom')}",
        "",
        f"LONG CONTEXT PRICING STATUS = {_v(header, 'long_context_pricing_status')}",
        "",
        f"EXPECTED COST = {_v(header, 'expected_cost')}",
        "",
        f"CONSERVATIVE COST = {_v(header, 'conservative_cost')}",
        "",
        f"HARD COST = {_v(header, 'hard_cost')}",
        "",
        f"RECOMMENDED CONNECT TIMEOUT = {_v(header, 'recommended_connect_timeout')}",
        "",
        f"RECOMMENDED READ TIMEOUT = {_v(header, 'recommended_read_timeout')}",
        "",
        f"FUTURE REAL CALL COUNT = {_v(header, 'future_real_call_count')}",
        "",
        f"FUTURE RETRIES = {_v(header, 'future_retries')}",
        "",
        f"IDEA INPUT COVERAGE = {_v(header, 'idea_input_coverage')}",
        "",
        f"UNKNOWN INPUT REFS = {_v(header, 'unknown_input_refs')}",
        "",
        f"SOURCE MAP MUTATED = {_v(header, 'source_map_mutated')}",
        "",
        f"CACHE SIGNATURE = {_v(header, 'cache_signature')}",
        "",
        f"FAKEAI FULL-SCALE STRESS = {_v(header, 'fakeai_full_scale_stress')}",
        "",
        f"TESTS = {_v(header, 'tests')}",
        "",
        f"NEW FAILURES = {_v(header, 'new_failures')}",
        "",
        "editorial_plan.json = NOT PUBLISHED",
        "",
        f"READY_FOR_ONE_REAL_EDITORIAL_PLANNER_CANARY = {_v(header, 'ready_for_one_real_editorial_planner_canary')}",
        "",
        "READY_FOR_EDITORIAL_PLAN_PUBLICATION = NO",
        "",
        "BOOK GENERATOR = NOT STARTED",
        "",
        "NEXT ACTION = HUMAN REVIEW",
        "",
    ]
    error = header.get("error") or bundle.get("error")
    if error:
        lines.extend(["## Block / error", "", str(error), ""])
    output = dict(bundle.get("output_budget") or {})
    selection = dict(output.get("selection") or {})
    if selection:
        lines.extend(
            [
                "## Output budget decision notes",
                "",
                f"- Decision: {selection.get('decision')}",
                f"- Hard visible tokens: {selection.get('hard_visible_tokens')}",
                f"- Thinking headroom: {selection.get('thinking_headroom_tokens')}",
                f"- Hard + thinking: {selection.get('hard_plus_thinking')}",
                f"- Utilization target: {selection.get('utilization_target')} ({selection.get('utilization_target_source')})",
                f"- Selected max_output: {selection.get('selected')}",
                f"- Do not blindly select 32768: {selection.get('do_not_blindly_select_32768')}",
                "",
            ]
        )
    assumptions = dict(output.get("assumptions") or {})
    if assumptions:
        lines.extend(["## Structural scenario assumptions", ""])
        for name, body in assumptions.items():
            lines.append(f"### {name}")
            lines.append("")
            if isinstance(body, dict):
                for key, value in body.items():
                    lines.append(f"- {key}: {value}")
            lines.append("")
    thinking = dict(bundle.get("thinking") or {})
    interaction = dict(thinking.get("max_tokens_interaction") or {})
    if interaction:
        lines.extend(
            [
                "## Thinking / max_tokens",
                "",
                f"- Opus 5 capabilities known: {interaction.get('repository_opus5_thinking_capabilities_known')}",
                f"- Whether max_tokens includes thinking: {interaction.get('whether_max_tokens_includes_thinking')}",
                f"- Conservative treatment: {interaction.get('conservative_treatment')}",
                "",
            ]
        )
    lines.extend(
        [
            "## Historical A.1 (not repeated)",
            "",
            "- provider = Anthropic",
            "- model = claude-opus-5",
            "- request id = req_011CfYKsDYnSjXnFggrn6Z2D",
            "- input tokens = 4826",
            "- output tokens = 2058",
            "- thinking tokens = 158",
            "- cost = 0.0755800 USD",
            "- elapsed = 89922 ms",
            "- finish = end_turn",
            "",
            "STOP. Wait for human review. Do not call Anthropic. Do not publish editorial_plan.json. Do not start Book Generator.",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = ["render_report"]
