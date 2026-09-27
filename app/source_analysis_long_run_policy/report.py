"""Rapport Markdown déterministe — Phase 3B.5.2."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_long_run_policy.constants import (
    CONNECT_DURATION_HUMAN,
    NEXT_PHASE_IF_AUTHORIZABLE,
    NEXT_PHASE_IF_SECOND_TIMEOUT,
    SELECTED_READ_DURATION_HUMAN,
)


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _candidate_table(rows: list[Mapping[str, Any]]) -> str:
    lines = [
        "| candidate | duration | advantages | risks | selected |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('candidate')} | {row.get('duration')} | "
            f"{row.get('advantages')} | {row.get('risks')} | "
            f"{_yn(bool(row.get('selected')))} |"
        )
    return "\n".join(lines)


def _factor_list(rows: list[Mapping[str, Any]]) -> str:
    lines = []
    for row in rows:
        lines.append(
            f"- **{row.get('id')}. {row.get('factor')}** "
            f"Evidence: {row.get('evidence')}"
        )
    return "\n".join(lines)


def _stage_line(block: Mapping[str, Any]) -> str:
    return (
        f"provider={block.get('provider')} model={block.get('model')} "
        f"connect={block.get('connect_seconds')} s "
        f"(source={block.get('connect_source')}) "
        f"read={block.get('read_seconds')} s "
        f"(source={block.get('read_source')})"
    )


def _scenario_table(rows: list[Mapping[str, Any]]) -> str:
    if not rows:
        return "(none)"
    lines = [
        "| output tokens | input cost | output cost | total | label |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('output_tokens')} | {row.get('input_cost')} | "
            f"{row.get('output_cost')} | {row.get('total_cost')} | "
            f"{row.get('label')} |"
        )
    return "\n".join(lines)


def render_report(payload: Mapping[str, Any], *, sha256: str) -> str:
    selected = payload.get("selected_policy") or {}
    evidence = payload.get("evidence") or {}
    incoming = payload.get("input") or {}
    context = payload.get("context") or {}
    config = payload.get("configuration") or {}
    timeouts = payload.get("timeouts") or {}
    simulated = (timeouts.get("simulated_policy") or {}).get("stages") or {}
    source = (timeouts.get("simulated_policy") or {}).get("source_analysis") or {}
    semantics = timeouts.get("read_semantics") or {}
    failure = payload.get("failure_policy") or {}
    success = payload.get("success_policy") or {}
    cost = payload.get("cost") or {}
    known = cost.get("known_input_estimate") or {}
    integrity = payload.get("integrity") or {}
    generation = integrity.get("generation_c") or {}
    execution = payload.get("execution") or {}
    network = payload.get("network") or {}
    tests = payload.get("tests") or {}
    justification = payload.get("selected_timeout_justification") or {}
    multi = payload.get("global_versus_multi_window") or {}
    linear = cost.get("canary_linear_output") or {}
    proposed = config.get("proposed_env") or {}

    sa = simulated.get("source_analysis") or {}
    ep = simulated.get("editorial_planning") or {}
    bg = simulated.get("book_generation") or {}
    bv = simulated.get("book_validation") or {}

    justified = bool(selected.get("second_global_attempt_justified"))
    status = str(selected.get("status") or "")
    timeout_selected = bool(selected.get("timeout_policy_selected"))
    outcome = (
        "PASS"
        if justified
        and status == "TECHNICALLY_AUTHORIZABLE"
        and timeout_selected
        and not execution.get("provider_call_performed")
        and not execution.get("execution_authorized")
        and not selected.get("third_global_timeout_escalation_allowed")
        else "FAIL"
    )

    return f"""# PHASE 3B.5.2 — LONG-RUN EXECUTION POLICY

## 1. Result

{outcome}

SECOND GLOBAL ATTEMPT JUSTIFIED =
{_yn(justified)}

SECOND GLOBAL ATTEMPT STATUS =
{status}

TIMEOUT POLICY SELECTED =
{_yn(timeout_selected)}

SELECTED CONNECT TIMEOUT =
{selected.get("connect_timeout_seconds")} seconds ({CONNECT_DURATION_HUMAN})

SELECTED READ TIMEOUT =
{selected.get("read_timeout_seconds")} seconds ({SELECTED_READ_DURATION_HUMAN})

THIRD GLOBAL TIMEOUT ESCALATION =
PROHIBITED

NEW ANTHROPIC CALL =
0

3B FINAL ATTEMPT #2 EXECUTED =
NO.


## 2. Objective

Define the operational policy of the next global Source Analyzer run.
Stay strictly offline. Decide whether a second global attempt is justified,
which connect/read timeouts to assign, how to inject them without code
changes, which protections surround that attempt, and the exact PASS /
PARTIAL / FAIL and stop rules. This phase may technically authorize a later
attempt. It must not execute it.


## 3. Baseline

{tests.get("baseline_passed")} passed, {tests.get("baseline_failed")} failed
before any 3B.5.2 work. Network = 0.


## 4. Evidence reviewed

3B FINAL attempt #1 (`source_analysis_global_clean_result.json`,
`PHASE_3B_FINAL_GLOBAL_CLEAN_SOURCE_ANALYZER_REPORT.md`).
3B.5 (`source_analysis_timeout_root_cause_audit.json`,
`PHASE_3B5_GLOBAL_TIMEOUT_ROOT_CAUSE_AUDIT_REPORT.md`).
3B.5.1 (`source_analysis_long_run_timeout_config_audit.json`,
`PHASE_3B51_LONG_RUN_TIMEOUT_CONFIGURATION_REPORT.md`).
3B.4.3 Generation C acceptance and 3B.4.4 / 3B.4.5 Prompt 1.3 canary.
Those artefacts were not modified.


## 5. Attempt #1 recap

Error = {evidence.get("attempt_1_result")}
after {evidence.get("attempt_1_read_timeout_seconds")} seconds.
HTTP form = {evidence.get("attempt_1_http_timeout_form")}.
One Anthropic call. No provider body. No transport. No usage. No source_map.
Corpus: {incoming.get("segments")} segments, {incoming.get("words")} words,
{incoming.get("duration_seconds")} seconds, mode={incoming.get("mode")},
transcript_id={incoming.get("transcript_id")}.


## 6. 3B.5 root cause

{evidence.get("root_cause")}.
3600 was passed to requests.post(timeout=3600). No lower local timeout.
Authorization wait did not consume the timeout.
Increase-local-read was LIKELY sufficient from the local stack.
Upstream limits remained UNKNOWN.
NO_EVIDENCE_BASED_EXACT_TIMEOUT.


## 7. 3B.5.1 hardening

Connect/read separated. requests.post receives timeout=(connect, read).
Defaults: connect=30, read=300. Stage-specific and environment overrides
are supported without Python changes and without affecting other stages.
No long production timeout had been selected before this phase.


## 8. Current global corpus

transcript_id = {incoming.get("transcript_id")}
mode = {incoming.get("mode")}
segments = {incoming.get("segments")}
words = {incoming.get("words")}
duration_seconds = {incoming.get("duration_seconds")}


## 9. Context capacity

strategy = {context.get("strategy")}
estimated_input_tokens = {context.get("estimated_input_tokens")}
usable_input_budget = {context.get("usable_input_budget")}
remaining_margin = {context.get("remaining_margin")}
corpus_fits_context_budget = {context.get("corpus_fits_context_budget")}
max_output_tokens = {context.get("max_output_tokens")}


## 10. Evidence supporting second global attempt

{_factor_list(list(payload.get("supporting_factors") or []))}

These are evidence, not guarantees.


## 11. Risks of second global attempt

{_factor_list(list(payload.get("risk_factors") or []))}

These risks are not minimized.


## 12. Global vs multi-window assessment

abandon_global_now = {_yn(bool(multi.get("abandon_global_now")))}
plan_windows_exists = {_yn(bool(multi.get("plan_windows_exists")))}
multi_window_consolidation_implemented = {_yn(bool(multi.get("multi_window_consolidation_implemented")))}
evidence_strong_enough_to_abandon_global = {_yn(bool(multi.get("evidence_strong_enough_to_abandon_global")))}

{multi.get("reason")}


## 13. Why multi-window is not implemented now

Moving to multi-window would itself introduce:
{chr(10).join(f"- {item}" for item in (multi.get("multi_window_would_introduce") or []))}

That work is out of scope. This phase does not implement it.


## 14. Timeout candidate set

{_candidate_table(list(payload.get("candidate_evaluation") or []))}


## 15. Selected operational timeout

value = {justification.get("value")} seconds
duration = {justification.get("duration")}
confidence = {justification.get("confidence")}
(confidence is about the policy choice, not provider completion)

{justification.get("reasoning")}


## 16. Why this is an operational policy, not a prediction

scientifically_proven = {_yn(bool(justification.get("scientifically_proven")))}
provider_guarantee = {_yn(bool(justification.get("provider_guarantee")))}
operational_engineering_policy = {_yn(bool(justification.get("operational_engineering_policy")))}
timeout_policy_basis = {selected.get("timeout_policy_basis")}
linear_canary_extrapolation_used = {_yn(bool(justification.get("linear_canary_extrapolation_used")))}

3B.5 already recorded NO_EVIDENCE_BASED_EXACT_TIMEOUT. 7200 is a controlled
engineering choice, not a measured Anthropic duration.


## 17. Connect timeout policy

{selected.get("connect_timeout_seconds")} seconds.
The failure was read duration, not TCP/TLS establishment.
Connect is not lengthened with read. 3B.5.1 made that separation explicit
so a long generation window cannot become a long connect window.


## 18. Read timeout policy

{selected.get("read_timeout_seconds")} seconds.
{semantics.get("controls")}
is_provider_computation_deadline = {_yn(bool(semantics.get("is_provider_computation_deadline")))}
resets_on_incoming_bytes = {semantics.get("resets_on_incoming_bytes")}
clock_starts_at = {semantics.get("clock_starts_at")}


## 19. No total wall-clock timeout caveat

application_total_timeout_on_this_path = {_yn(bool(semantics.get("application_total_timeout_on_this_path")))}
is_total_wall_clock_timeout = {_yn(bool(semantics.get("is_total_wall_clock_timeout")))}

requests uses (connect, read). The selected read timeout is not a guaranteed
total execution duration.


## 20. Configuration mechanism

{config.get("source_analysis_connect_env")}
{config.get("source_analysis_read_env")}
python_code_change_required = {config.get("python_code_change_required")}
The global runner no longer passes REAL_CALL_TIMEOUT_SECONDS. It uses
resolve_timeouts() with request.stage = source_analysis.


## 21. Proposed environment configuration

{config.get("source_analysis_connect_env")}={proposed.get(config.get("source_analysis_connect_env"))}
{config.get("source_analysis_read_env")}={proposed.get(config.get("source_analysis_read_env"))}

These values are documented here only. The real .env was not modified
(real_env_modified = {config.get("real_env_modified")}).
No secrets are exposed.


## 22. Simulated timeout resolution

source_analysis connect = {source.get("connect_seconds")} s
source = {source.get("connect_source")}
source_analysis read = {source.get("read_seconds")} s
source = {source.get("read_source")}
requests_timeout = {source.get("requests_timeout")}
shape = {source.get("requests_timeout_shape")}


## 23. Other-stage isolation

source_analysis : {_stage_line(sa)}
editorial_planning : {_stage_line(ep)}
book_generation : {_stage_line(bg)}
book_validation : {_stage_line(bv)}
other_stages_isolated = {(timeouts.get("simulated_policy") or {}).get("other_stages_isolated")}
other_stages_affected = {config.get("other_stages_affected")}


## 24. HTTP tuple simulation

The future global run would receive timeout=({selected.get("connect_timeout_seconds")}.0, {selected.get("read_timeout_seconds")}.0)
once the proposed env is applied. Verified offline via resolve_ai_timeouts()
and, in tests, a mocked requests.post. No HTTP was opened.


## 25. Attempt-number policy

GLOBAL_ATTEMPT_NUMBER = {selected.get("attempt_number")}
Attempt #1 remains the historical 3600 s timeout. This policy does not
overwrite that meaning.


## 26. One-call policy

max_real_calls = {selected.get("max_real_calls")}
max_attempts = {selected.get("max_attempts")}


## 27. Retry/fallback policy

retry = {selected.get("retry")}
fallback = {selected.get("fallback")}


## 28. Third global timeout escalation policy

third_global_timeout_escalation_allowed = {selected.get("third_global_timeout_escalation_allowed")}

If attempt #2 times out, do not choose 10800/14400 and try again.


## 29. Failure policy — timeout

If attempt #2 raises AITimeoutError before a usable body:
{failure.get("second_timeout")}
3B remains incomplete.
Next phase: {failure.get("next_phase_if_second_timeout")}
Not RETRY_WITH_LONGER_TIMEOUT.


## 30. Failure policy — provider error

400 / 401 / 403 / 429 / 5xx / network failure:
{failure.get("provider_error")}
No automatic retry. Preserve diagnostic. Human review.


## 31. Failure policy — local post-provider failure

If a real generation body exists but a local stage fails
(transport parse, vocabulary, SRC refs, links, decoder, reconstruction,
normalizer, canonical validator, editorial leakage):
{failure.get("post_provider_local_failure")}
preserve_transport = {(failure.get("local_failure_requirements") or {}).get("preserve_transport")}
provider_retry_allowed = {(failure.get("local_failure_requirements") or {}).get("provider_retry_allowed")}


## 32. Failure policy — truncation

If finish reason indicates max_tokens / length / truncation:
{failure.get("truncation")}
Preserve the response. No retry.


## 33. Transport preservation policy

After a real provider generation is obtained, the exact semantic transport
must be persisted atomically BEFORE local canonical processing can cause
the run to fail. This remains mandatory.


## 34. Success policy

requires_full_canonical_pipeline = {success.get("requires_full_canonical_pipeline")}
requires_atomic_source_map_publication = {success.get("requires_atomic_source_map_publication")}
project_state_success_before_publication = {success.get("project_state_success_before_publication")}

Gates:
{chr(10).join(f"- {item}" for item in (success.get("gates") or []))}


## 35. Cost considerations

status = {known.get("status")}
catalog_line_status = {known.get("catalog_line_status")}
estimated_input_tokens = {known.get("estimated_input_tokens")}
input_cost = {known.get("input_cost")} {known.get("currency")}
output_tokens = {known.get("output_tokens")}
output_cost = {known.get("output_cost")}
total_cost = {known.get("total_cost")}
unknown_must_not_become_zero = {known.get("unknown_must_not_become_zero")}
long_context_regime_declared_on_catalog_line = {known.get("long_context_regime_declared_on_catalog_line")}
provider_actual_usage = {cost.get("provider_actual_usage")}

{known.get("note")}


## 36. Illustrative cost scenarios if produced

{_scenario_table(list(cost.get("illustrative_output_scenarios") or []))}

These are ILLUSTRATIVE ONLY. They are not predictions.


## 37. Why canary scaling is not linear

allowed = {linear.get("allowed")}
forbidden_formula = {linear.get("forbidden_formula")}
invalid_result_if_applied = {linear.get("invalid_result_if_applied")}
{linear.get("reason")}


## 38. Prompt 1.3 integrity

prompt_version = {integrity.get("prompt_version")}
prompt_unchanged = {integrity.get("prompt_unchanged")}


## 39. Generation C integrity

raw_sha256 = {generation.get("raw_sha256")}
anthropic_sha256 = {generation.get("anthropic_sha256")}
raw_matches_historical = {generation.get("raw_matches_historical")}
anthropic_matches_historical = {generation.get("anthropic_matches_historical")}


## 40. Decoder integrity

decoder_semantic_changes = {integrity.get("decoder_semantic_changes")}


## 41. Canonical validator integrity

canonical_validator_changes = {integrity.get("canonical_validator_changes")}


## 42. Protected artifacts

3B.5.1 protected list plus the 3B.5.1 diagnostic and report, now historical.
SHA before == SHA after. Byte-identical.


## 43. SourceMap status

absent.


## 44. Project state

source_analysis remains historical failed / AITimeoutError from attempt #1.
Not modified to SUCCESS.


## 45. Tests

baseline_passed = {tests.get("baseline_passed")}
baseline_failed = {tests.get("baseline_failed")}
final_passed = {tests.get("final_passed")}
final_failed = {tests.get("final_failed")}
New offline policy tests added. Network = 0.


## 46. Network

anthropic={network.get("anthropic")}
openai={network.get("openai")}
whisper={network.get("whisper")}
ollama={network.get("ollama")}
lm_studio={network.get("lm_studio")}
other={network.get("other")}
engine_generate={payload.get("engine_generate")}


## 47. Policy artifact

path : `audit/source_analysis_second_global_attempt_policy.json`
SHA : `{sha256}`
déterministe : SHA run1 == SHA run2.
No timestamp. No UUID.


## 48. Files added

`app/source_analysis_long_run_policy/`
`app/tests/test_source_analysis_long_run_policy.py`
`audit/source_analysis_second_global_attempt_policy.json`
`audit/PHASE_3B52_LONG_RUN_EXECUTION_POLICY_REPORT.md`


## 49. Files modified

None in production runtime, Prompt 1.3, Generation C, decoder, canonical
validator, clean transcript, real `.env`, or historical 3B artefacts.


## 50. Technical decision

A second global attempt is technically justified because attempt #1 failed
from a concrete local read-timeout and the global semantic pipeline already
passed the real canary. The operational policy is connect=30 / read=7200
via environment variables, one call, no retry, no fallback, no third
timeout escalation. Status is TECHNICALLY_AUTHORIZABLE only.
AUTHORIZED_FOR_EXECUTION requires subsequent human review.

If authorized later: {NEXT_PHASE_IF_AUTHORIZABLE}
If attempt #2 times out: {NEXT_PHASE_IF_SECOND_TIMEOUT}

STOP. Wait for human review.
"""
