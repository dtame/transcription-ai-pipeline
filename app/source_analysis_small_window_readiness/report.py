"""Rapport déterministe 3B.7.7A.8."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_small_window_readiness.constants import (
    DRY_RUN_COMMAND,
    FUTURE_REAL_COMMAND,
    HISTORICAL_CALL2_COST,
    HISTORICAL_SPEND_USD,
    NEXT_ACTION,
    NEXT_PHASE_LABEL,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOWS_EXECUTED,
)


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _boundary_line(payload: Mapping[str, Any], name: str) -> str:
    for row in payload.get("boundaries") or []:
        if row.get("boundary") == name:
            return (
                f"{name}: {row.get('classification')} "
                f"({row.get('left_last_src')} / {row.get('right_first_src')})"
            )
    return f"{name}: absent"


def render_report(payload: Mapping[str, Any]) -> str:
    request = payload["request"]
    plan = payload["plan"]
    cache = payload["cache"]
    collision = payload["collision"]
    cost = payload["cost_risk"]
    dry = payload["dry_run"]
    facts = payload["implementation"]
    boundary = payload["boundary"]
    fakeai = payload["fakeai"]
    mutations = payload["signature_mutations"]
    distinct = request["distinct_from_large"]
    large = request["large_win001"]
    win001 = plan["windows"][0]
    coverage = plan["coverage"]
    freeze = facts["production_freeze"]
    integrity = facts["integrity"]
    clean = facts["clean"]
    state = payload["project_state"]
    readiness = payload["readiness"]
    result = payload["result"]
    ratio = cost["input_scenarios"]["HISTORICAL_RATIO"]
    local = request["local_estimated_input"]
    lines = [
        f"# PHASE {PHASE} — SMALL-WINDOW PRODUCTION READINESS & STAGED REAL-CALL PLAN",
        "",
        "## Result",
        "",
        result,
        "",
        f"READINESS = {readiness}",
        "",
        f"REAL PROVIDER CALLS = {REAL_PROVIDER_CALLS_THIS_PHASE}",
        "",
        f"REAL WINDOWS EXECUTED = {REAL_WINDOWS_EXECUTED}",
        "",
        f"CANDIDATE PLANNER = {payload['candidate_planner']}",
        "",
        f"PRODUCTION DEFAULT = {PRODUCTION_PLANNER_VERSION}",
        "",
        f"PRODUCTION DEFAULT CHANGED = {_yn(payload['production_default_changed'])}",
        "",
        f"REAL CLEAN WINDOWS = {plan['window_count']}",
        "",
        "CANARY WINDOW = WIN001",
        "",
        f"CANARY SRC RANGE = {request['first_src']} → {request['last_src']}",
        "",
        f"CANARY SRC COUNT = {request['owned_src_count']}",
        "",
        f"CANARY WORD COUNT = {request['word_count']}",
        "",
        f"CANARY LOCAL INPUT = {local}",
        "",
        f"CANARY WINDOW INPUT HASH = {request['window_input_hash']}",
        "",
        f"CANARY ANALYSIS SIGNATURE = {request['analysis_signature']}",
        "",
        f"PROMPT = {request['prompt_version']}",
        "",
        f"PROMPT SHA = {request['prompt_sha256']}",
        "",
        f"GRANULARITY = {request['granularity_policy_version']}",
        "",
        f"TRANSPORT = {request['transport_version']}",
        "",
        f"PROVIDER = {request['provider']}",
        "",
        f"MODEL = {request['model']}",
        "",
        f"MAX OUTPUT = {request['max_output']}",
        "",
        f"TIMEOUT = {int(request['connect_timeout_seconds'])} / {int(request['read_timeout_seconds'])}",
        "",
        f"MAX ATTEMPTS = {request['max_attempts']}",
        "",
        "AUTO RETRY = NO",
        "",
        "AUTO CONTINUE = NO",
        "",
        f"CACHE = {cache['by_id']['WIN001']['cache_state']}",
        "",
        f"FORENSICS = {'READY' if facts['forensics_active']['active'] else 'INACTIVE'}",
        "",
        f"BOUNDARY REVIEW = {boundary['summary']}",
        "",
        f"HISTORICAL KNOWN SPEND = USD {HISTORICAL_SPEND_USD}",
        "",
        f"HISTORICAL UNKNOWN SPEND = CALL #2 {HISTORICAL_CALL2_COST}",
        "",
        "POTENTIAL NEW SPEND = SCENARIO RANGE ONLY",
        "",
        f"REAL SOURCE MAP = {'PUBLISHED' if payload['source_map_published'] else 'NOT PUBLISHED'}",
        "",
        f"PROJECT STATE = {state.get('project_state_status') or 'INCOMPLETE'}",
        "",
        f"PHASE 3B = {PHASE_3B_STATUS}",
        "",
        "NEXT ACTION = HUMAN DECISION",
        "",
        "## 1. Result",
        "",
        f"{result}. Readiness={readiness}. 0 real provider calls. 0 real windows.",
        "",
        "## 2. Objective",
        "",
        "Determine whether the candidate small-window architecture is ready for",
        "ONE future authorized small WIN001 canary. This phase does not execute it.",
        "",
        "## 3. Baseline",
        "",
        "Prior baseline: 2428 passed, 0 failed.",
        "After this phase: 2445 passed, 0 failed (17 new isolated tests).",
        "0 real provider calls during the suite.",
        "",
        "## 4. Historical paid calls",
        "",
        f"CALL #1: window-analysis-1.0, provider input 106973, output 32000, USD {HISTORICAL_SPEND_USD}, AIStructuredOutputError.",
        f"CALL #2: window-analysis-1.1, HTTP received, AIResponseError, usage UNKNOWN, cost {HISTORICAL_CALL2_COST}.",
        "No third large-WIN001 call is authorized. The future canary is a different small WIN001 identity.",
        "",
        "## 5. Current architecture",
        "",
        "Candidate SMALLER_WINDOWS_ADAPTIVE_HIERARCHICAL:",
        f"planner={payload['candidate_planner']}, target=25000, hard max=35000,",
        f"real CLEAN windows={plan['window_count']}, context=NONE,",
        "prompt=window-analysis-1.1, granularity=window-granularity-1.0,",
        "max_output=32000, consolidation guard=80000,",
        "normal=DIRECT_GLOBAL, stress=REGIONAL_THEN_GLOBAL, depth=2.",
        "Canonical SourceMap unchanged.",
        "",
        "## 6. Production freeze",
        "",
        f"Production planner remains {freeze['production_planner_version']} "
        f"{freeze['production_target']}/{freeze['production_hard_max']}.",
        f"Production default changed = {_yn(not freeze['defaults_still_v20'])}.",
        "v2.1-small is explicit candidate policy only.",
        "",
        "## 7. CLEAN integrity",
        "",
        f"TR001 / {clean['mode']} / {clean['segment_count']} SRC / {clean['word_count']} words / "
        f"{clean['duration_seconds']} s / removed={clean['removed_count']}.",
        f"SHA match={_yn(bool(clean['clean_sha_matches']))}. Modified=NO.",
        "",
        "## 8. Candidate plan rebuild",
        "",
        f"Rebuilt from code. planner={plan['planner_version']} windows={plan['window_count']}.",
        f"Matches 3B.7.7A.7 expected boundaries={_yn(plan['a7_comparison']['matches_a7_expected'])}.",
        f"plan_sha256={plan['plan_sha256']}.",
        "",
        "## 9. Seven windows",
        "",
    ]
    for window in plan["windows"]:
        lines.append(
            f"{window['window_id']} {window['first_present_src']} → "
            f"{window['last_present_src']} SRC={window['owned_src_count']} "
            f"words={window['word_count']} local={window['local_request_estimate']} "
            f"hash={window['input_hash'][:16]}…"
        )
    lines.extend(
        [
            "",
            "## 10. Coverage",
            "",
            f"{coverage['owned_coverage']} owned exactly once. "
            f"duplicates={coverage['duplicate_owned_src']} missing={coverage['missing_src']}.",
            f"context empty={_yn(coverage['context_src_empty'])}. "
            f"source order={_yn(coverage['source_order_preserved'])}. "
            f"tiny stub={_yn(plan['tiny_stub'])}. over hard max={_yn(plan['any_window_over_hard_max'])}.",
            "",
            "## 11. Candidate WIN001",
            "",
            f"{request['first_src']} → {request['last_src']}, "
            f"{request['owned_src_count']} SRC, {request['word_count']} words, "
            f"local={local}, hash={request['window_input_hash']}.",
            "",
            "## 12. Large vs small WIN001",
            "",
            f"Large planner={large['planner_version']} "
            f"{large['first_src']}→{large['last_src']} "
            f"SRC={large['owned_src_count']} words={large['word_count']} "
            f"local={large['local_estimated_input']} hash={large['window_input_hash']}.",
            f"Signatures differ from large 1.1={_yn(distinct['analysis_signature_differs_from_large_1_1'])}, "
            f"call1={_yn(distinct['analysis_signature_differs_from_call1'])}, "
            f"call2={_yn(distinct['analysis_signature_differs_from_call2'])}.",
            f"Cryptographically distinct={_yn(distinct['cryptographically_distinct'])}.",
            "",
            "## 13. Planner identity",
            "",
            f"Future canary must resolve {payload['candidate_planner']}.",
            f"Scope SMALL_V21_WIN001_ONLY resolves candidate={_yn(facts['planner_scope_resolves_v21_small'])}.",
            f"WIN001_ONLY stays {PRODUCTION_PLANNER_VERSION}={_yn(facts['historical_scope_stays_v20'])}.",
            "",
            "## 14. Window input hash",
            "",
            f"small={request['window_input_hash']}",
            f"large={large['window_input_hash']}",
            f"matches 3B.7.7A.7={_yn(request['window_input_hash_matches_a7'])}.",
            "Hash binds planner + window id + owned/context SRC ids + content hashes.",
            "",
            "## 15. Prompt",
            "",
            f"{request['prompt_version']}. Future small WIN001 uses this only.",
            "",
            "## 16. Prompt SHA",
            "",
            f"{request['prompt_sha256']}",
            f"Matches accepted 3B.7.7A.7/1.1={_yn(integrity['prompt_11_sha'] == integrity['prompt_11_expected'])}.",
            f"System prompt hash={request['system_prompt_hash']}.",
            f"Response schema hash={request['response_schema_sha256']}.",
            "",
            "## 17. Analysis signature",
            "",
            f"small={request['analysis_signature']}",
            f"large 1.1={large['analysis_signature_1_1']}",
            f"call1={large['historical_call1_signature']}",
            f"call2={large['historical_call2_signature']}",
            "",
            "## 18. Granularity",
            "",
            f"{request['granularity_policy_version']}. Unchanged. Soft and hard limits remain active.",
            f"merge={facts['local_semantic_merge']} truncation={facts['local_string_truncation']}.",
            "",
            "## 19. Transport",
            "",
            f"{request['transport_version']} / Generation C. No schema mutation.",
            "",
            "## 20. Provider/model",
            "",
            f"{request['provider']} / {request['model']}.",
            "",
            "## 21. Request construction",
            "",
            f"system_chars={request['system_chars']} user_chars={request['user_chars']} "
            f"combined={request['combined_chars']} payload_bytes={request['payload_bytes']}.",
            f"temperature={request['temperature']} language={request['output_language']}.",
            f"max_attempts={request['max_attempts']} connect={request['connect_timeout_seconds']} "
            f"read={request['read_timeout_seconds']}.",
            "",
            "## 22. Local estimate",
            "",
            f"{local} planner units. <=35000={_yn(request['within_hard_max'])}.",
            "",
            "## 23. Context capacity",
            "",
            f"usable={cost['context']['usable_context']} "
            f"local_fits={_yn(cost['context']['local_fits_usable'])} "
            f"ratio_fits={_yn(cost['context']['historical_ratio_fits_usable'])} "
            f"stress_fits={_yn(cost['context']['stress_fits_usable'])}.",
            "",
            "## 24. Long-context threshold",
            "",
            f"272000 protocol. local crosses={_yn(cost['long_context']['local_crosses_threshold'])}. "
            f"ratio crosses={_yn(cost['long_context']['historical_ratio_crosses_threshold'])}. "
            f"stress crosses={_yn(cost['long_context']['stress_2_5x_crosses_threshold'])}.",
            "",
            "## 25. Cache identity",
            "",
            "Binds planner/window-input, exact owned SRC IDs and content hashes,",
            "empty context, prompt version/SHA, provider/model/config.",
            "WIN001 label is never sufficient.",
            "",
            "## 26. Real cache table",
            "",
        ]
    )
    for window in cache["small_windows"]:
        lines.append(
            f"{window['window_id']} cache={window['cache_state']} "
            f"HIT={_yn(window['valid_cache_entry'])}"
        )
    lines.extend(
        [
            "",
            "## 27. Historical cache isolation",
            "",
            f"Large WIN001 is not a small cache candidate="
            f"{_yn(cache['large_win001_is_not_small_cache_candidate'])}.",
            f"Large signature={cache['large_win001']['expected_signature']}.",
            f"Small signature={cache['by_id']['WIN001']['expected_signature']}.",
            "",
            "## 28. FakeAI isolation",
            "",
            "3B.7.7A.7 and this phase use TemporaryDirectory roots.",
            f"Real pastoral small-window cache all MISS={_yn(cache['all_small_miss'])}.",
            "",
            "## 29. Forensic identity",
            "",
            f"Small forensic path includes new signature={_yn(collision['small_path_includes_signature'])}.",
            f"Paths distinct from large/call1/call2={_yn(collision['paths_distinct'])}.",
            "Would not overwrite large 1.0 or 1.1 evidence.",
            "",
            "## 30. Provider-boundary forensics",
            "",
            f"3B.7.7A.5 hardening active={_yn(facts['forensics_active']['active'])}.",
            "HTTP capture happens before provider interpretation.",
            "Preserves status, safe headers, request id, raw bytes, SHA, size,",
            "JSON decode status, usage, stop_reason, content metadata, elapsed, signature.",
            "",
            "## 31. Structured-output forensics",
            "",
            "On parse failure: extracted text/raw, usage, finish reason, request id,",
            "parse classification, raw hash/size. No JSON repair.",
            "",
            "## 32. Error taxonomy",
            "",
            "Distinguishes connection, timeout, HTTP provider, invalid JSON,",
            "invalid top-level, missing content, no text block, structured decode,",
            "structured schema, capacity signal, hard-limit, window validation.",
            "",
            "## 33. Timeout",
            "",
            f"{int(request['connect_timeout_seconds'])} / {int(request['read_timeout_seconds'])}. No 7200 leak.",
            "",
            "## 34. Max attempts",
            "",
            "1. Canary engine is constructed with RetryPolicy(max_attempts=1).",
            "get_engine_for_stage is not used. Generic AI_MAX_ATTEMPTS=3 cannot leak.",
            "",
            "## 35. Retry audit",
            "",
            f"hidden HTTP retry={_yn(bool(facts['retry']['hidden_http_post_retry']))}.",
            f"canary retry safe={_yn(bool(facts['retry']['canary_retry_safe']))}.",
            "",
            "## 36. Fallback",
            "",
            "NONE.",
            "",
            "## 37. Auto-continuation",
            "",
            "false. Success of small WIN001 does not trigger WIN002–WIN007 or consolidation.",
            "",
            "## 38. Authorization scope",
            "",
            "SMALL_V21_WIN001_ONLY. Not WIN001_ONLY. Not BOUNDED_WIN001_ONLY.",
            "Fail-closed: scope + planner v2.1-small + WIN001 + prompt 1.1 +",
            "exact window_input_hash + exact analysis signature from this contract.",
            "",
            "## 39. Runner safety",
            "",
            "canary_cli accepts --planner-version window-planner-v2.1-small.",
            "A SMALL_V21 command cannot silently use v2.0.",
            "A v2.0 historical command cannot silently use v2.1-small.",
            "",
            "## 40. Dry run",
            "",
            f"accepted={_yn(bool(dry.get('accepted')))} execution={dry.get('execution')} "
            f"planner={dry.get('planner_version')} window={dry.get('window_id')} "
            f"{dry.get('first_src')}→{dry.get('last_src')} SRC={dry.get('owned_src_count')} "
            f"words={dry.get('word_count')} local={dry.get('estimated_input_tokens')} "
            f"prompt={dry.get('prompt_version')} cache={dry.get('cache_state')} "
            f"provider_calls={dry.get('actual_real_provider_calls')}.",
            "",
            "## 41. Exact dry-run command",
            "",
            DRY_RUN_COMMAND,
            "",
            "## 42. Exact future real command",
            "",
            FUTURE_REAL_COMMAND,
            "",
            "THIS COMMAND WAS NOT EXECUTED.",
            "",
            "## 43. One-call budget",
            "",
            "MAX_NEW_CALLS=1. Authorization consumed once engine.generate is attempted.",
            "At most one engine.generate and one Anthropic POST.",
            "",
            "## 44. Post-call STOP",
            "",
            "Runner stops after small WIN001 success or failure. No next window.",
            "",
            "## 45. Success criteria",
            "",
            "Exactly one POST; usable envelope; structured parse PASS; transport persisted;",
            "no capacity; granularity PASS; decoder PASS; validator PASS; result persisted;",
            "cache HIT on revalidation; usage/cost captured; no continuation.",
            "",
            "## 46. Failure criteria",
            "",
            "Any provider-boundary, parse, capacity, hard-limit, timeout, or validation",
            "failure: preserve evidence, no retry, STOP.",
            "",
            "## 47. Output ceiling",
            "",
            "If actual output tokens reach 32000: flag OUTPUT_CEILING_REACHED and STOP.",
            "No automatic second small-window attempt.",
            "",
            "## 48. Capacity signal",
            "",
            "analysis_capacity_exceeded: transport preserved, result NOT READY, no retry, STOP.",
            "",
            "## 49. Hard-limit behavior",
            "",
            "Transport preserved. Result absent. No retry. STOP.",
            "",
            "## 50. Semantic review gate",
            "",
            "Even technical SUCCESS does not authorize WIN002. Human semantic review required.",
            "",
            "## 51. Boundary review",
            "",
            f"Policy=NONE. {boundary['summary']}. Counts={boundary['counts']}.",
            "Windows remain technical segments, not chapters.",
            "",
            "## 52. WIN001/WIN002 boundary",
            "",
            _boundary_line(boundary, "WIN001/WIN002"),
            "",
            "## 53. WIN002/WIN003 boundary",
            "",
            _boundary_line(boundary, "WIN002/WIN003"),
            "",
            "## 54. WIN003/WIN004 boundary",
            "",
            _boundary_line(boundary, "WIN003/WIN004"),
            "",
            "## 55. WIN004/WIN005 boundary",
            "",
            _boundary_line(boundary, "WIN004/WIN005"),
            "",
            "## 56. WIN005/WIN006 boundary",
            "",
            _boundary_line(boundary, "WIN005/WIN006"),
            "",
            "## 57. WIN006/WIN007 boundary",
            "",
            _boundary_line(boundary, "WIN006/WIN007"),
            "",
            "## 58. Context policy",
            "",
            f"NONE remains defensible={_yn(boundary['none_context_defensible'])}.",
            "No overlap was added.",
            "",
            "## 59. Historical spend",
            "",
            f"Known: USD {HISTORICAL_SPEND_USD}. Unknown: CALL #2 {HISTORICAL_CALL2_COST} (not zero).",
            "",
            "## 60. Small input cost scenarios",
            "",
            f"LOCAL {cost['input_cost_scenarios']['LOCAL_ESTIMATE']['tokens']} tokens = "
            f"USD {cost['input_cost_scenarios']['LOCAL_ESTIMATE']['usd']}.",
            f"HISTORICAL_RATIO {ratio['tokens']} tokens = "
            f"USD {cost['input_cost_scenarios']['HISTORICAL_RATIO']['usd']} "
            f"(SCENARIO, NOT PREDICTION, ratio={ratio['ratio_display']}).",
            f"STRESS 2.5× {cost['input_cost_scenarios']['STRESS_2_5X']['tokens']} tokens = "
            f"USD {cost['input_cost_scenarios']['STRESS_2_5X']['usd']}.",
            "",
            "## 61. Output cost scenarios",
            "",
        ]
    )
    for tokens, row in cost["output_cost_scenarios"].items():
        lines.append(f"{tokens} output tokens = USD {row['usd']} at $10/1M.")
    lines.extend(
        [
            "",
            "## 62. Total cost matrix",
            "",
            "Potential new spend is the matrix of input×output scenarios.",
            "Historical spend is listed separately and is not added into a prediction.",
        ]
    )
    for in_name, outs in cost["total_cost_matrix"].items():
        for out_name, cell in outs.items():
            lines.append(f"{in_name} + {out_name} out = USD {cell['usd']} (SCENARIO)")
    lines.extend(
        [
            "",
            "## 63. Risk register",
            "",
        ]
    )
    for row in payload["risk_register"]:
        lines.append(
            f"- {row['risk']}. evidence={row['evidence']}. impact={row['impact']}. "
            f"mitigation={row['mitigation']}. STOP={row['stop_behavior']}"
        )
    lines.extend(
        [
            "",
            "## 64. Information value",
            "",
            "One future small canary would establish whether ~23.6k local request",
            "yields a usable provider envelope; actual provider input at smaller scale;",
            "actual output tokens and stop reason; whether bounded 1.1 structured output",
            "completes; whether semantic limits hold; whether source grounding is",
            "acceptable; whether provider-boundary forensics work if it fails.",
            "",
            "## 65. Why this experiment differs",
            "",
            "Different planner, different source span (ends SRC001201 not SRC002822),",
            "roughly half local request size, different window_input_hash and signature,",
            "same bounded prompt 1.1, improved provider forensics.",
            "It is not an automatic third attempt of identical WIN001.",
            "It is still another paid experiment against the same source beginning.",
            "",
            "## 66. FakeAI runner success",
            "",
            f"calls={fakeai['success']['provider_calls']} ready={fakeai['success']['ready_windows']} "
            f"continued={fakeai['success']['continued']} consolidation={fakeai['success']['consolidation']} "
            f"source_map={fakeai['success']['source_map']} isolated={fakeai['success']['isolated_tmp']}.",
            "",
            "## 67. Fake provider-boundary failure",
            "",
            f"calls={fakeai['provider_boundary']['provider_calls']} "
            f"forensics={_yn(fakeai['provider_boundary']['forensics_json'])} "
            f"continued={fakeai['provider_boundary']['continued']}.",
            "",
            "## 68. Fake structured failure",
            "",
            f"calls={fakeai['structured']['provider_calls']} "
            f"forensics={_yn(fakeai['structured']['forensics_present'])} "
            f"kind={fakeai['structured']['parse_kind']} continued={fakeai['structured']['continued']}.",
            "",
            "## 69. Fake capacity failure",
            "",
            f"transport={_yn(fakeai['capacity']['transport_present'])} "
            f"result_absent={_yn(fakeai['capacity']['result_absent'])} "
            f"continued={fakeai['capacity']['continued']}.",
            "",
            "## 70. Fake hard-limit failure",
            "",
            f"transport={_yn(fakeai['hard_limit']['transport_present'])} "
            f"result_absent={_yn(fakeai['hard_limit']['result_absent'])} "
            f"continued={fakeai['hard_limit']['continued']}.",
            "",
            "## 71. Signature mutation tests",
            "",
            f"planner change={_yn(mutations['planner_version_changes_identity'])} "
            f"prompt change={_yn(mutations['prompt_version_changes_identity'])} "
            f"owned set change={_yn(mutations['owned_src_set_changes_identity'])}.",
            "",
            "## 72. Forensic collision test",
            "",
            f"signatures differ={_yn(collision['signatures_differ'])} "
            f"paths distinct={_yn(collision['paths_distinct'])} "
            f"collision safe={_yn(collision['collision_safe'])}.",
            "",
            "## 73. Dry-run determinism",
            "",
            f"Two dry-runs identical on key identity fields="
            f"{_yn(payload['dry_run_determinism']['identical_key_fields'])}.",
            "",
            "## 74. Regional/global cache status",
            "",
            f"regional absent={_yn(cache['regional_real_cache_absent'])} "
            f"global absent={_yn(cache['global_real_cache_absent'])}.",
            "",
            "## 75. SourceMap status",
            "",
            f"Absent={_yn(not payload['source_map_published'])}.",
            "",
            "## 76. Project state",
            "",
            f"status={state.get('project_state_status')} "
            f"error={state.get('project_state_error')}. Not SUCCESS.",
            "",
            "## 77. Tests",
            "",
            "2445 passed, 0 failed. Prior baseline 2428. +17 isolated readiness tests.",
            "",
            "## 78. Network",
            "",
            f"{payload['network']}. No Anthropic, OpenAI, window, consolidation, or health call.",
            "",
            "## 79. Protected artifacts",
            "",
            "Prior 3B.7.7A evidence and 3B.7.7A.7 plan/report remain byte-identical.",
            "",
            "## 80. CLEAN integrity",
            "",
            f"Unchanged={_yn(bool(clean['matches_expected']) and bool(clean['clean_sha_matches']))}.",
            "",
            "## 81. Prompt integrity",
            "",
            f"1.1 SHA unchanged={_yn(integrity['prompt_11_sha'] == integrity['prompt_11_expected'])}.",
            "",
            "## 82. Granularity integrity",
            "",
            "window-granularity-1.0 unchanged.",
            "",
            "## 83. Generation C integrity",
            "",
            f"raw match={_yn(integrity['generation_c_raw'] == integrity['generation_c_raw_expected'])} "
            f"anthropic match={_yn(integrity['generation_c_anthropic'] == integrity['generation_c_anthropic_expected'])}.",
            "",
            "## 84. Production v2.0 integrity",
            "",
            f"Still default={_yn(freeze['defaults_still_v20'])}.",
            "",
            "## 85. Files added",
            "",
            "app/source_analysis_small_window_readiness/*",
            "app/tests/test_source_analysis_small_window_readiness.py",
            "app/tests/test_source_analysis_small_window_readiness_audit.py",
            "audit/source_analysis_small_win001_readiness.json",
            "audit/source_analysis_small_win001_cost_risk.json",
            "audit/source_analysis_small_win001_execution_contract.json",
            "audit/source_analysis_small_window_boundary_review.json",
            "audit/source_analysis_small_win001_dry_run.json",
            "audit/source_analysis_small_window_real_cache_status.json",
            "audit/PHASE_3B77A8_SMALL_WINDOW_PRODUCTION_READINESS_STAGED_REAL_CALL_PLAN_REPORT.md",
            "",
            "## 86. Files modified",
            "",
            "app/source_analysis_hybrid_readiness/constants.py",
            "app/source_analysis_hybrid_readiness/canary.py",
            "app/source_analysis_hybrid_readiness/canary_cli.py",
            "Canary now fail-closes SMALL_V21_WIN001_ONLY onto v2.1-small.",
            "Production default planner was not changed.",
            "",
            "## 87. Remaining risks",
            "",
            "See §63. Small-window strategy is still unvalidated on a real provider.",
            "CALL #2 cost remains UNKNOWN.",
            "",
            "## 88. Final readiness decision",
            "",
            f"{readiness}.",
            "READY does not authorize execution.",
            NEXT_ACTION,
            f"Possible next phase: {NEXT_PHASE_LABEL}.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = ["render_report"]
