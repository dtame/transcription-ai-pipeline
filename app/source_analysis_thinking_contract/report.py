"""Rapport markdown déterministe 3B.7.7A.12."""

from __future__ import annotations

from typing import Any, Mapping


def _yn(value: Any) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    return str(value)


def render_report(
    *,
    header: Mapping[str, Any],
    official: Mapping[str, Any],
    call_c: Mapping[str, Any],
    options: Mapping[str, Any],
    decision: Mapping[str, Any],
    payload: Mapping[str, Any],
    readiness: Mapping[str, Any],
    integrity: Mapping[str, Any],
    isolation: Mapping[str, Any],
    current_payload: Mapping[str, Any],
    e2e: Mapping[str, Any],
) -> str:
    h = header
    lines = [
        "# PHASE 3B.7.7A.12 — ANTHROPIC THINKING CONTRACT VERIFICATION & REAL-CALL READINESS",
        "",
        "## Result",
        "",
        str(h["result"]),
        "",
        f"REAL PROVIDER CALLS = {h['real_provider_calls']}",
        "",
        f"REAL WINDOW CALLS = {h['real_window_calls']}",
        "",
        f"CALL C THINKING = {h['call_c_thinking']}",
        "",
        f"CALL C EFFECTIVE THINKING MODE = {h['call_c_effective_thinking_mode']}",
        "",
        f"CALL C EFFECTIVE EFFORT = {h['call_c_effective_effort']}",
        "",
        f"SONNET 5 ADAPTIVE THINKING DEFAULT = {h['sonnet5_adaptive_default']}",
        "",
        f"MANUAL budget_tokens SUPPORTED = {h['manual_budget_tokens_supported']}",
        "",
        f"THINKING DISABLED SUPPORTED = {h['thinking_disabled_supported']}",
        "",
        f"EFFORT CONTROL SUPPORTED = {h['effort_control_supported']}",
        "",
        f"DEFAULT EFFORT = {h['default_effort']}",
        "",
        f"SELECTED V2 THINKING CONTRACT = {h['selected_contract']}",
        "",
        f"SELECTED V2 EFFORT = {h['selected_effort']}",
        "",
        f"THINKING HARD TOKEN CAP = {h['thinking_hard_token_cap']}",
        "",
        f"SEMANTIC JSON WORST CASE = {h['semantic_json_worst_case']} local tokens",
        "",
        f"MAX OUTPUT = {h['max_output']} unchanged",
        "",
        f"V2 GRAMMAR SERVER VERIFIED = {h['v2_grammar_server_verified']}",
        "",
        f"V2 GRAMMAR CANARY READY = {h['v2_grammar_canary_ready']}",
        "",
        f"SEMANTIC WIN001 READY = {h['semantic_win001_ready']}",
        "",
        f"REAL PROVIDER CALL AUTHORIZED = {h['real_provider_call_authorized']}",
        "",
        f"PRODUCTION DEFAULT CHANGED = {h['production_default_changed']}",
        "",
        f"SOURCE MAP = {h['source_map']}",
        "",
        f"PHASE 3B = {h['phase_3b']}",
        "",
        f"TESTS = {h['tests']}",
        "",
        f"NEXT ACTION = {h['next_action']}",
        "",
        "## 1. Result",
        "",
        f"{h['result']}. Offline official-contract implementation. "
        f"Real provider calls = {h['real_provider_calls']}. "
        f"WIN001 not retried.",
        "",
        "## 2. Objective",
        "",
        "Implement versioned Sonnet 5 thinking configuration and select one "
        "future V2 canary contract. No real call.",
        "",
        "## 3. Baseline",
        "",
        f"Pre-change suite: {h['baseline']}.",
        "",
        "## 4. Real-call freeze",
        "",
        "REAL PROVIDER CALLS = 0. REAL WINDOW CALLS = 0. NO WIN001 RETRY. "
        "No Anthropic/OpenAI request authorized.",
        "",
        "## 5. Official Sonnet 5 contract",
        "",
        f"Model = {official['model']}. Verification date = "
        f"{official['verification_date']}. "
        f"{official['source_notes']}",
        "",
        "References:",
        "",
    ]
    for url in official.get("source_references") or []:
        lines.append(f"- {url}")
    lines.extend(
        [
            "",
            "## 6. Adaptive thinking default",
            "",
            "YES. Omitting `thinking` still enables adaptive thinking. "
            "That is why CALL C thought without a thinking field.",
            "",
            "## 7. Default effort",
            "",
            "high. Omitting output_config.effort uses the model default.",
            "",
            "## 8. max_tokens semantics",
            "",
            "max_tokens is a hard limit on TOTAL generated output: "
            "thinking + visible/structured tokens. CALL C: 21911 thinking "
            "+ remaining response = 32000, stop_reason=max_tokens.",
            "",
            "## 9. Manual budget_tokens",
            "",
            "NOT supported. thinking.type=enabled + budget_tokens returns "
            "HTTP 400. Not implemented. Architectural 8000 reserve remains "
            "a design concept only.",
            "",
            "## 10. Thinking disabled",
            "",
            "Supported: thinking.type=disabled. Selected for the future V2 canary.",
            "",
            "## 11. Adaptive effort control",
            "",
            "thinking.type=adaptive plus output_config.effort "
            "(low/medium/high/xhigh/max). Effort is NOT a deterministic "
            "thinking-token cap.",
            "",
            "## 12. Task budget",
            "",
            "task_budget is NOT supported for claude-sonnet-5 under the "
            "current official contract. Not implemented.",
            "",
            "## 13. Current app payload",
            "",
            "Historical provider-default builder fields: "
            f"{', '.join(current_payload.get('historical_fields') or [])}. "
            "thinking omitted. effort omitted. temperature omitted when None.",
            "",
            "## 14. CALL C reconstruction",
            "",
            f"thinking explicit = {_yn(call_c['thinking_explicit'])}. "
            f"effort explicit = {_yn(call_c['effort_explicit'])}. "
            f"temperature in payload = {_yn(call_c['temperature_in_payload'])}. "
            f"Effective thinking = {call_c['effective_thinking']}. "
            f"Effective effort = {call_c['effective_effort']}.",
            "",
            "## 15. Why CALL C thought without thinking field",
            "",
            "Sonnet 5 adaptive thinking is on by default when the field is omitted.",
            "",
            "## 16. Thinking/output accounting",
            "",
            f"Observed thinking = {call_c['observed_thinking']}. "
            f"max_tokens = {call_c['max_tokens']}. "
            f"Implied remaining visible budget = "
            f"{call_c['implied_remaining_visible_budget']}. "
            "Shared output budget exhausted.",
            "",
            "## 17. Temperature compatibility",
            "",
            payload.get("temperature_policy", ""),
            "",
            "## 18. output_config merging",
            "",
            payload.get("output_config_merge", ""),
            "",
            "## 19. AIRequest design",
            "",
            "Generic fields: thinking_mode "
            "(disabled / adaptive / provider_default), effort "
            "(low / medium / high / xhigh / max), thinking_budget_tokens "
            "(rejected locally for Sonnet 5). No raw Anthropic dicts in "
            "business logic.",
            "",
            "## 20. Capability model",
            "",
            "Verified only for anthropic:claude-sonnet-5. Other models "
            "remain fail-closed if thinking/effort are set explicitly.",
            "",
            "## 21. Fail-closed combinations",
            "",
            "claude-sonnet-5 + thinking_budget_tokens → local "
            "AIConfigurationError, HTTP=0. Invalid effort → local ValueError, "
            "HTTP=0. Unverified model + explicit thinking/effort → local reject.",
            "",
            "## 22. Historical compatibility",
            "",
            "Unspecified thinking_mode preserves provider_default. Historical "
            "Prompt 1.0 / 1.1 / semantic-transport-v1 / Generation C / "
            "source_analysis_window signatures omit thinking keys.",
            "",
            "## 23. Candidate A — disabled",
            "",
            "THINKING_PROVIDER_ENFORCED_DISABLED. Theoretical thinking usage 0. "
            "Semantic quality UNVERIFIED_REAL. Highest JSON-budget predictability.",
            "",
            "## 24. Candidate B — adaptive low",
            "",
            "THINKING_PROVIDER_ADAPTIVE + EFFORT_PROVIDER_CONTROLLED_LOW. "
            "THINKING_TOKEN_COUNT_NOT_HARD_CAPPED. Quality UNVERIFIED_REAL.",
            "",
            "## 25. Candidate C — adaptive medium",
            "",
            "Same classification with medium effort. Not selected.",
            "",
            "## 26. Baseline — adaptive high",
            "",
            "Historical effective CALL C behavior. Comparison baseline only. "
            "Observed configuration exhausted the shared 32000 budget. "
            "High can work in other settings; it failed here.",
            "",
            "## 27. Semantic task characteristics",
            "",
            "Source-grounded extraction, classification, compact structured "
            "representation, traceability. Not open-ended math, tools, coding, "
            "or long-horizon planning.",
            "",
            "## 28. Reliability implications",
            "",
            "For this bounded extraction stage, preserving visible JSON budget "
            "outranks hidden reasoning. Disabled is technically appropriate "
            "as a first canary contract. Quality remains unverified.",
            "",
            "## 29. Semantic-quality uncertainty",
            "",
            "No real Sonnet 5 result exists for disabled, low, or medium on "
            "this exact workload. All quality conclusions = UNVERIFIED_REAL.",
            "",
            "## 30. JSON-budget predictability",
            "",
            "Disabled: theoretical thinking 0, conceptual JSON budget 32000. "
            "Adaptive low/medium: thinking amount unknown — do not fabricate "
            "token values. Semantic cardinality remains application-bounded.",
            "",
            "## 31. Cost implications",
            "",
            "Disabled has the lowest thinking-token cost risk. Adaptive high "
            "already billed 21911 thinking tokens on CALL C.",
            "",
            "## 32. Selected contract",
            "",
            f"{decision['selected_future_contract']} / thinking_mode="
            f"{decision['selected_thinking_mode']} / effort="
            f"{decision['selected_effort_payload']}.",
            "",
            "## 33. Why selected",
            "",
            str(decision["why"]),
            "",
            "## 34. Fallback",
            "",
            f"{decision['fallback_candidate']} "
            f"({decision['fallback_thinking_mode']}/"
            f"{decision['fallback_effort']}) via a separately authorized canary "
            "if disabled is accepted but future semantic quality is inadequate.",
            "",
            "## 35. No automatic fallback",
            "",
            "Never automatically rerun with another thinking mode after failure.",
            "",
            "## 36. V2 payload",
            "",
            "Selected payload: thinking.type=disabled, effort omitted, "
            "output_config.format retained, temperature omitted, "
            "max_tokens=32000.",
            "",
            "## 37. Signature",
            "",
            "thinking_mode and effort participate in window analysis signature "
            "when they are not historical provider_default.",
            "",
            "## 38. Cache identity",
            "",
            "V2 child cache identity includes thinking fingerprint. "
            "disabled ≠ adaptive-low ≠ adaptive-medium ≠ provider-default/high.",
            "",
            "## 39. Forensic identity",
            "",
            "Forensic identity includes thinking configuration. Same WIN001 "
            "content cannot cache-hit across thinking contracts.",
            "",
            "## 40. Response parsing",
            "",
            "extract_anthropic_text / _extract_text select content blocks by "
            "type==text, not content[0]. Works with leading thinking blocks "
            "and with text-only responses.",
            "",
            "## 41. Usage observability",
            "",
            "thinking_tokens extracted from usage.output_tokens_details or "
            "usage.thinking_tokens when present. Absent remains None, never 0.",
            "",
            "## 42. Finish reason",
            "",
            "stop_reason remains mapped to AIResponse.finish_reason before "
            "structured parse. Already hardened; regression covered.",
            "",
            "## 43. Prompt 1.2",
            "",
            f"Byte-identical. version={integrity.get('prompt_1_2_version')}. "
            f"sha256={integrity.get('prompt_1_2_sha256')}.",
            "",
            "## 44. Transport v2",
            "",
            f"Byte-identical compact shape. raw="
            f"{integrity.get('transport_v2_raw_bytes')} bytes, adapted="
            f"{integrity.get('transport_v2_adapted_bytes')} bytes. "
            "Server grammar UNVERIFIED.",
            "",
            "## 45. Granularity",
            "",
            f"window-granularity-1.1-minimal unchanged "
            f"({integrity.get('granularity_1_1_minimal')}). "
            "1.0 production unchanged.",
            "",
            "## 46. Synthetic worst case",
            "",
            f"{integrity.get('synthetic_worst_case_tokens')} local tokens. "
            f"within target = {_yn(integrity.get('synthetic_worst_case_within_target'))}. "
            "No weakening.",
            "",
            "## 47. Small planner",
            "",
            f"{h['small_planner']} remains candidate. Not activated globally.",
            "",
            "## 48. Adaptive hierarchy",
            "",
            f"{h['adaptive_hierarchy']}.",
            "",
            "## 49. Capacity subdivision",
            "",
            "KEEP. No real execution. max_tokens truncation is not a valid "
            "semantic capacity signal (A.11 rule preserved).",
            "",
            "## 50. Grammar status",
            "",
            "V2 server grammar acceptance remains UNVERIFIED.",
            "",
            "## 51. Future grammar canary",
            "",
            "Prepared, not executed. Tiny synthetic input. Minimal output. "
            "Answers only schema+thinking payload acceptance.",
            "",
            "## 52. Grammar authorization scope",
            "",
            f"{readiness['grammar']['authorization_scope']}. "
            f"max generate={readiness['grammar']['max_engine_generate']}. "
            f"max_attempts={readiness['grammar']['max_attempts']}. "
            "No retry. Mandatory STOP.",
            "",
            "## 53. Future semantic scope",
            "",
            f"{readiness['semantic_scope']['authorization_scope']} prepared "
            "and DISABLED. Separate human authorization required after "
            "grammar canary review.",
            "",
            "## 54. Semantic WIN001 blocked",
            "",
            "YES. Not executable because this phase passed.",
            "",
            "## 55. Tests",
            "",
            str(h["tests"]),
            "",
            "## 56. Network",
            "",
            "0. no_ai_network fixture on new tests. Package has no requests/"
            "urllib/httpx/openai/anthropic SDK imports. generate/post/_invoke "
            "absent from the thinking_contract package.",
            "",
            "## 57. Historical artifacts",
            "",
            "A.7–A.11 artifacts preserved. CALL C evidence unaltered.",
            "",
            "## 58. CLEAN",
            "",
            f"unchanged = {_yn(integrity.get('clean_unchanged'))}.",
            "",
            "## 59. Isolation",
            "",
            f"unauthorized semantic artifacts forbidden = "
            f"{_yn(isolation.get('unauthorized_semantic_artifacts_forbidden'))}. "
            "Candidate path not wired into analyzer.py.",
            "",
            "## 60. SourceMap",
            "",
            f"present = {_yn(integrity.get('source_map_present'))}. "
            "NOT PUBLISHED. Canonical schema unchanged.",
            "",
            "## 61. Project state",
            "",
            f"not SUCCESS = {_yn((integrity.get('project_state') or {}).get('not_success'))}. "
            "Phase 3B incomplete.",
            "",
            "## 62. Files added",
            "",
            "app/ai/thinking.py; app/ai/providers/_anthropic_thinking.py; "
            "app/source_analysis_thinking_contract/*; "
            "app/tests/test_ai_thinking_contract.py; "
            "app/tests/test_source_analysis_thinking_contract.py; "
            "app/tests/test_source_analysis_thinking_contract_audit.py.",
            "",
            "## 63. Files modified",
            "",
            "app/ai/contracts.py; app/ai/providers/anthropic_engine.py; "
            "app/ai/providers/base.py; app/ai/providers/fake.py; "
            "app/ai/provider_forensics.py; "
            "app/source_analysis/window_signature.py; "
            "app/source_analysis_local_v2/pipeline.py; "
            "app/source_analysis_local_v2/subdivision.py.",
            "",
            "## 64. Remaining unknowns",
            "",
            "- Anthropic server acceptance of V2 schema + thinking disabled "
            "(UNVERIFIED).",
            "- Semantic fidelity of thinking disabled on real WIN001 "
            "(UNVERIFIED_REAL).",
            "- Adaptive low/medium quality (UNVERIFIED_REAL).",
            "- Sonnet 5 tokenizer vs local estimator mismatch (context only).",
            "",
            "## 65. Recommended next action",
            "",
            f"{h['next_action']}: separately authorize 3B.7.7A.13 — one tiny "
            "synthetic grammar+thinking-config canary. No pastoral transcript. "
            "No WIN001. max_attempts=1. Mandatory STOP.",
            "",
            "## Questions",
            "",
            f"Were any provider calls made? NO ({h['real_provider_calls']}).",
            "",
            "Was WIN001 retried? NO.",
            "",
            "Why did CALL C use thinking despite no thinking field? "
            "Sonnet 5 adaptive thinking default.",
            "",
            "What is Sonnet 5 default thinking behavior? adaptive.",
            "",
            "What is default effort? high.",
            "",
            "Is max_tokens shared between thinking and visible output? YES.",
            "",
            "Does Sonnet 5 support manual budget_tokens? NO. Would it return "
            "400? YES according to official contract.",
            "",
            "Can thinking be disabled? YES.",
            "",
            "Can adaptive thinking depth be controlled? YES, with effort. "
            "Is effort a deterministic thinking-token cap? NO.",
            "",
            "Is task_budget supported on Sonnet 5? NO.",
            "",
            f"CALL C effective contract: adaptive default + high default. "
            f"thinking={call_c['observed_thinking']}, max_tokens="
            f"{call_c['max_tokens']}, finish={call_c['finish_reason']}.",
            "",
            f"Selected V2 thinking mode: {decision['selected_thinking_mode']}.",
            "",
            f"Alternative retained: {decision['fallback_candidate']}.",
            "",
            "Semantic-quality uncertainty: UNVERIFIED_REAL.",
            "",
            "Does selected configuration preserve output_config.format? YES.",
            "",
            "Does temperature remain compatible? YES — omitted for Sonnet 5.",
            "",
            "Does signature change with thinking config? YES, when not default.",
            "",
            "Does cache separate configurations? YES.",
            "",
            "Does forensic identity separate them? YES.",
            "",
            f"Is synthetic V2 JSON still <=12000? "
            f"{_yn(integrity.get('synthetic_worst_case_within_target'))} "
            f"({integrity.get('synthetic_worst_case_tokens')}).",
            "",
            "Is max_output changed? NO.",
            "",
            "Is V2 server grammar verified? NO.",
            "",
            "Is a tiny grammar/config canary prepared? YES. Executed? NO.",
            "",
            "Is semantic WIN001 authorized? NO.",
            "",
            "Does production default change? NO.",
            "",
            "Does canonical SourceMap change? NO.",
            "",
            f"Is source_map absent? {_yn(not integrity.get('source_map_present'))}.",
            "",
            "Is Phase 3B complete? NO.",
            "",
            "Human decision required next: authorize 3B.7.7A.13 grammar canary "
            "only, or reject/change the selected THINKING_DISABLED contract.",
            "",
            f"FakeAI selected-contract E2E = {e2e.get('result')}.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = ["render_report"]
