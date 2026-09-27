"""Rapport markdown déterministe 3B.7.7A.1."""

from __future__ import annotations

from typing import Any, Mapping


def _yn(value: Any) -> str:
    return "YES" if value else "NO"


def render_report(diagnosis: Mapping[str, Any]) -> str:
    failure = diagnosis["failure"]
    token = diagnosis["token"]
    obs = diagnosis["observability"]
    accounting = diagnosis["accounting"]
    local = token["local_estimate"]
    actual = token["provider_actual"]
    cost = token["cost_arithmetic"]
    ctx = token["context_margin"]
    schema = token["schema_bytes"]
    dup = token["duplication_checks"]
    trigger = failure["exact_exception_trigger"]
    http = failure["anthropic_http_outcome"]
    impl = obs["implemented_hardening"]
    hist = token["historical_usage"]
    rec = token["reconstructed_request"]
    bounds = token["record_bounds"]

    unexpected = dup.get("unexpected_duplication") or []
    marker_lines = "\n".join(
        f"- {row['marker']}: payload={row['payload_count']} "
        f"system={row['system_count']} user={row['user_count']} "
        f"expected={row['expected_payload_count']} "
        f"match={row['matches_expected']}"
        for row in dup.get("rows") or []
    )
    protected_lines = "\n".join(
        f"- `{item['path']}` present={item['present']} sha256=`{item['sha256']}`"
        for item in failure.get("protected_evidence") or []
    )

    return f"""# PHASE 3B.7.7A.1 — WIN001 STRUCTURED OUTPUT FAILURE & TOKEN ACCOUNTING DIAGNOSIS

## Result

{failure["result"]}

REAL PROVIDER CALLS THIS PHASE =
{failure["real_provider_calls_this_phase"]}

WIN001 RETRIED =
{_yn(failure["win001_retried"])}

PROXIMATE FAILURE =
{failure["proximate_failure"]}

OUTPUT TOKENS =
{failure["output_tokens"]}

OUTPUT LIMIT REACHED =
{failure["output_limit_reached"]}

STOP REASON =
{failure["stop_reason"]}

LOCAL INPUT ESTIMATE =
{failure["local_input_estimate"]}

PROVIDER INPUT TOKENS =
{failure["provider_input_tokens"]}

INPUT RATIO =
{failure["input_ratio"]}

PAYLOAD DUPLICATION =
{failure["payload_duplication"]}

RAW PROVIDER CONTENT AT FAILURE =
{failure["raw_provider_content_at_failure"]}

RAW CONTENT PERSISTED =
{_yn(failure["raw_content_persisted"])}

TRANSPORT =
{failure["transport"]}

WIN001 CACHE =
{failure["win001_cache"]}

ROOT CAUSE CONFIDENCE =
{failure["root_cause_confidence"]}

SEMANTIC CONTRACT CHANGED =
{_yn(failure["semantic_contract_changed"])}

NEXT ACTION =
{failure["next_action"]}

## 1. Result

{failure["result"]}. Offline forensic diagnosis only. Authorized real provider calls this phase = 0. WIN001 was not retried. Proximate exception path identified. Token mismatch quantified. Observability hardening implemented without semantic-contract changes.

## 2. Objective

Determine, from existing code and persisted evidence only: why local estimate {failure["local_input_estimate"]} ≠ provider input {failure["provider_input_tokens"]}; why output_tokens reached {failure["output_tokens"]}; what raised `{failure["error_type"]}`; whether raw provider content was available then discarded; whether observability can distinguish the cases; and the smallest safe correction before any future real call.

## 3. Baseline

Before this phase: 2310 passed, 0 failed.

## 4. Previous call facts

From `audit/source_analysis_real_win001_canary_execution.json`:

- provider = anthropic / claude-sonnet-5
- engine.generate attempts = 1
- Anthropic POST attempts = 1
- request estimate = {failure["local_input_estimate"]}
- actual input = {failure["provider_input_tokens"]}
- actual output = {actual["output_tokens"]}
- cost = USD {cost["total_cost"]}
- error = {failure["error_type"]}
- transport / decoder / validator / result = ABSENT / NOT RUN / NOT RUN / ABSENT
- WIN001 cache = MISS
- WIN002/WIN003/consolidation = 0
- timeout occurred = NO

## 5. Evidence sources

- `audit/PHASE_3B77A_REAL_WIN001_CANARY_REPORT.md` (byte-identical, not rewritten)
- `audit/source_analysis_real_win001_canary_execution.json`
- 3B.7.6 dry-run / readiness / real-call-plan artifacts
- 3B.4.3 and 3B.4.5 persisted canary usage
- current application code (estimator, Anthropic engine, structured parser, window analyzer)

## 6. Proximate exception

`{failure["error_type"]}` raised by `parse_structured_output()` inside `BaseAIEngine.generate()` after `_invoke()` returned a `ProviderResult` with text and usage.

## 7. Anthropic HTTP outcome

{http["classification"]}.

Timeout = NO. Usage received = YES. HTTP status persisted = NO. A provider HTTP error would have raised `AIRequestError` / `AIServerError` / `AITimeoutError` before structured parse.

## 8. Structured-output path

AIRequest → `AnthropicEngine.build_payload` → `requests.post` (already consumed in 3B.7.7A) → response JSON → `_extract_text` → `ProviderResult` → `AIResponse(parsed=None)` → `parse_structured_output` → `{failure["error_type"]}` → `exc.response` attached → `analyze_window` re-raises → no transport.

## 9. Exact exception trigger

Raiser = `{trigger["raiser"]}`.

Type = `{trigger["type"]}`.

Sub-condition (empty / json_decode / schema) = {trigger["sub_condition"]}.

Empty content likely = {_yn(trigger["empty_content_likely"])} ({trigger["empty_reason"]}).

Missing text block = {_yn(trigger["missing_text_block"])} ({trigger["missing_text_block_reason"]}).

The exact 3B.7.7A parse message was not persisted.

## 10. Response data available

See observability review. In memory after `_invoke`: HTTP JSON, text, usage, `stop_reason`, body `id`. HTTP status discarded by `post_json`. Header request-id never read.

## 11. Response data persisted

Usage persisted (log + 3B.7.7A artifact). Stop reason / request id / raw text / parse excerpt: not persisted for the failed call.

## 12. Raw content

YES — raw model text existed as `ProviderResult.text` / `AIResponse.text` / `exc.response.text` before parse. It was discarded when the exception left `analyze_window`. It was never written to disk. It cannot be reconstructed.

## 13. Stop reason

Anthropic field `stop_reason` is mapped to `AIResponse.finish_reason` in `AnthropicEngine._invoke`. Before this phase it was not logged on structured-output failure and not persisted. Actual failed-call value = UNKNOWN. `output_tokens == 32000` is not treated as proof of `max_tokens`.

## 14. Request ID

Body field `id` is mapped to `AIResponse.request_id`. Not persisted for the failed call. Actual value = UNKNOWN. Header request-id = NOT READ.

## 15. Usage

Provider usage persisted: input={actual["input_tokens"]} output={actual["output_tokens"]} source=provider.

## 16. Local token estimate

{local["system_plus_user_tokens"]} via `estimate_tokens(system + user)`.

Method = {local["algorithm"]}.

Chars/token assumption = {local["chars_per_token_assumption"]}.

tiktoken available in this environment = {local["tiktoken_available_in_environment"]}.

Includes system = YES. Includes user = YES. Includes response schema = NO. Includes grammar / JSON escaping / Anthropic wrappers / tool transforms = NO.

## 17. Provider token count

{actual["input_tokens"]} reported in Anthropic `usage.input_tokens`.

## 18. Exact ratio

{actual["ratio_exact"]} = {actual["ratio"]}.

Gap = {actual["gap_tokens"]} tokens.

## 19. Estimator implementation

Phase 2 `app/ai/estimation.py`: tiktoken if importable, else `ceil(chars / 4.0)`. `estimate_request_tokens` joins prompt + system_prompt only. Planner hard max 60000 is `LOCAL_ESTIMATED_TOKENS`, not provider-billed input.

## 20. Exact reconstructed request

Offline, same path as the canary (`build_window_ai_request`):

- system chars = {rec["system_chars"]}
- user chars = {rec["user_chars"]}
- combined chars = {rec["combined_chars"]}
- estimated tokens = {rec["estimated_tokens"]}
- matches observed 49617 = {local["matches_observed_49617"]}
- message count = {rec["message_count"]}
- system blocks = {rec["system_block_count"]}
- user content blocks = {rec["user_content_block_count"]}
- max output = {rec["max_output"]}
- model = {rec["model"]}
- temperature = {rec["temperature"]}
- prompt_sha256 = `{rec["prompt_sha256"]}`
- response_schema_sha256 = `{rec["response_schema_sha256"]}`

## 21. Serialized payload

Built with `AnthropicEngine.build_payload` only. No POST. No API key.

- compact bytes = {token["payload_bytes"]["serialized_compact_bytes"]}
- pretty bytes = {token["payload_bytes"]["serialized_pretty_bytes"]}
- system bytes = {token["payload_bytes"]["system_bytes"]}
- messages bytes = {token["payload_bytes"]["messages_bytes"]}
- schema bytes in payload = {token["payload_bytes"]["schema_bytes_in_payload"]}
- keys = {", ".join(token["payload_keys"])}

## 22. Prompt sizes

system={token["request_text_chars"]["system_chars"]} chars / {token["request_text_chars"]["system_utf8_bytes"]} bytes.

user={token["request_text_chars"]["user_chars"]} chars / {token["request_text_chars"]["user_utf8_bytes"]} bytes.

## 23. Schema sizes

raw bytes = {schema["raw_schema_bytes"]}.

adapted bytes = {schema["adapted_schema_bytes"]}.

raw estimated tokens = {schema["raw_schema_estimated_tokens"]}.

adapted estimated tokens = {schema["adapted_schema_estimated_tokens"]}.

Could schema byte size explain the ~57k gap? NO. {schema["quantitative_reason"]}

## 24. Duplication audit

SRC payload duplication = {_yn(dup.get("payload_duplication_of_src"))}.

Unexpected marker mismatches = {len(unexpected)}.

Language directive is expected twice (system + user). Vocabulary header once (system). Window header once (user). OWNED/CONTEXT headers twice (system explanation + user section). First SRC may appear once in the versioned system example (`[SRC000001 | …]`) plus once as owned content. User-side SRC markers occur once — no second insertion of window transcript.

## 25. Representative marker counts

{marker_lines}

Transcript text is not persisted in this report.

## 26. Provider accounting uncertainty

KNOWN: integers copied from Anthropic `usage`.

UNKNOWN: whether compiled structured-output grammar, wrappers, or hidden request-side tokens are included in `input_tokens`. Ratio alone does not prove a cause.

## 27. Context capacity

context_window = {ctx["context_window"]}.

usable_context (safety {ctx["safety_ratio"]}) = {ctx["usable_context"]}.

actual input {ctx["actual_input"]} did not exceed usable context ({_yn(ctx["exceeded_usable_context"])}) nor the 1M window ({_yn(ctx["exceeded_context_window"])}).

margin vs usable context (input+32k output) = {ctx["margin_vs_usable_context"]}.

This failure is not context overflow.

## 28. Long-context pricing status

Protocol-cited threshold >{token["long_context"]["protocol_cited_threshold"]} is not encoded as a local constant. Actual input {token["long_context"]["actual_input"]} did not cross it. Sonnet 5 catalog line has no `unmodeled_regimes`. Base Phase 2B pricing applies.

## 29. Cost verification

{cost["input_formula"]} = {cost["input_cost"]}.

{cost["output_formula"]} = {cost["output_cost"]}.

total = {cost["total_cost"]}.

Arithmetic correct = {_yn(cost["arithmetic_correct"])}.

## 30. Output cost share

{cost["output_cost_share_percent"]}% of USD {cost["total_cost"]} is output ({cost["output_cost"]}). Overgeneration is the main cost driver of this call.

## 31. Output ceiling

output_tokens = configured max_output = {actual["output_tokens"]}.

Classification = OUTPUT REACHED CONFIGURED CEILING.

This does not prove `stop_reason=max_tokens`.

## 32. Truncation evidence

STRONGLY SUPPORTED by the ceiling plus a structured parse failure. NOT PROVEN: no persisted `stop_reason`, no persisted raw JSON.

## 33. Grammar status

Generation C was server-accepted in 3B.4.3. This call returned usage and text, so the failure is completion/parse of a large structured generation, not schema rejection. Grammar acceptance is not reopened.

## 34. Record expansion risk

records[] has no `maxItems`. No explicit caps on TOPIC / IDEA / RELATION / EXAMPLE / REFERENCE / UNCERTAINTY / REPETITION / VOICE / INTENT_KIND / AUDIENCE_KIND. Unbounded semantic record count subject only to max_output.

## 35. Granularity risk

2787 SRC / 12745 words plus « un record par unité réellement distincte » can, at contract level, emit far more records than 32000 output tokens can hold. Actual output was not persisted; this is contract-level risk only.

## 36. Window size implications

Planner target 50000 / hard max 60000 remain LOCAL_ESTIMATED_TOKENS. They did not constrain Anthropic's 106973 billed input. Do not re-plan in this phase.

## 37. Max-output implications

Keep 32000. Increasing blindly is forbidden. Evidence is insufficient to prove a valid transport needs >32k. Overproduction from missing granularity bounds is the leading redesign candidate.

## 38. Transport-first boundary

Transport-first begins only after `AIResponse.parsed` exists. This call failed before that boundary. Hence transport.json absent. Pre-parse provider evidence should be preserved for future failures.

## 39. Observability gap

Before this phase: usage logged; finish_reason, request_id, raw hash, parse kind, raw body discarded. That is an OBSERVABILITY GAP. It prevented proving truncation vs malformed-but-complete JSON vs local schema reject.

## 40. Forensic preservation design

Future structured-output failures persist:

- `analysis/structured_output_forensics/<WIN>/provider_response_forensics.json`
- optional `provider_raw_content.txt`

Fields: provider, model, HTTP status if known, usage, stop reason, request id, content metadata, raw SHA256 / byte / char counts, parse error, truncation indicators. No secrets. No transport. No result. No retry.

## 41. Hardening implemented

{_yn(impl["implemented"])}. Semantic behavior unchanged. Prompt / Generation C / planner / max_output / window size unchanged.

## 42. Error metadata

`AIStructuredOutputError` now carries parse_failure_kind, usage, finish_reason, request_id, raw text hash/size, JSON decode location. `diagnostics()` never includes raw text or secrets.

## 43. Raw response policy

Persist raw failed model text locally under `analysis/structured_output_forensics`, never logs/console.

Rationale: the 3B.7.7A body was discarded, so this diagnosis could not inspect it; transport-first already treats persisted provider output as the recovery surface; 32k tokens is a bounded disk cost; production result stays invalid.

This failed call is not retroactively fabricated.

## 44. Offline recovery implications

A future persisted raw response can be parsed offline. That may avoid another provider call for diagnosis. Raw preservation ≠ automatic salvage. No heuristic JSON repair.

## 45. Security/secrets

Forensic JSON redacts api_key / authorization / secret-like keys and `sk-ant-` prefixes. Payload reconstruction never includes the API key.

## 46. Failure classification

{failure["primary_classification"]}.

Contributing categories: OUTPUT_LIMIT_REACHED_WITH_STRUCTURED_PARSE_FAILURE, REQUEST_TOKEN_ESTIMATOR_MISMATCH, PROVIDER_RESPONSE_OBSERVABILITY_GAP.

## 47. Root cause

Proximate: local `{failure["error_type"]}` from `parse_structured_output`.

Likely upstream: provider output reached the 32000 ceiling and could not be parsed as complete valid transport JSON. Strongly supported, not proven.

Independent: local estimator under-counts provider input (~{actual["ratio"]}×).

## 48. Contributing factors

1. Unbounded record contract vs 32000 max_output.
2. Estimator ignores schema / provider wrappers / billed tokenizer.
3. Missing pre-parse persistence (finish_reason, raw body).

## 49. What is proven

- Baseline 2310 green at phase start.
- 0 provider calls this phase.
- WIN001 not retried.
- Exception type and function.
- HTTP body + usage received; not a timeout.
- output_tokens == max_output.
- Estimate is system+user text only.
- Schema bytes cannot explain the 57k input gap.
- Representative SRC markers occur once in the rebuilt payload.
- 106973 is below usable Sonnet 5 context.
- $0.533946 arithmetic.
- Transport-first starts at parsed.
- WIN001 remains MISS.

## 50. What remains unknown

- Actual `stop_reason` of the failed call.
- Actual request id.
- Exact parse sub-condition (json_decode vs schema).
- Raw model text of the failed call.
- Anthropic input_token accounting of grammar / wrappers.
- Whether a fully valid JSON was rejected locally.
- Whether a valid transport would need >32k.

## 51. Decision tree

If raw response had proven truncation → redesign output/granularity/window sizing before retry.

Raw response unavailable + output ceiling + parser failure → observability hardening (done) + offline architecture decision (next: bounding / granularity).

Payload duplication explaining input inflation → not found.

Estimator alone explaining mismatch → recalibrate planning later; not the proximate failure.

Structured parser rejecting a proven-valid response → not evidenced.

No call in this phase.

## 52. Tests

Synthetic HTTP fixtures: usage present, output at max, malformed/incomplete structured content. Forensics persisted. Valid path unchanged. Secrets absent. 0 real network.

## 53. Network

0 real network. 0 Anthropic. 0 OpenAI.

## 54. Protected artifacts

Historical reports through 3B.7.7A remain byte-identical.

{protected_lines}

## 55. CLEAN integrity

file sha256 = `{failure["clean_transcript"]["sha256_file"]}`

content sha256 = `{failure["clean_transcript"]["content_sha256"]}`

## 56. WIN001 cache status

{failure["win001_cache"]}. transport={failure["production_artifacts"]["transport_exists"]}. result={failure["production_artifacts"]["result_exists"]}.

## 57. WIN002/WIN003 status

Calls = 0. Untouched.

## 58. Consolidation status

Unauthorized. Untouched. 0 calls.

## 59. SourceMap status

Absent. `{_yn(failure["production_artifacts"]["source_map_exists"])}` published.

## 60. Project state

status={failure["project_state"].get("status")} error={failure["project_state"].get("error")}. Not SUCCESS.

## 61. Files added

- `app/ai/structured_forensics.py`
- `app/source_analysis_win001_failure_diagnosis/*`
- `app/tests/test_source_analysis_win001_failure_diagnosis.py`
- audit diagnostic JSON + this report

## 62. Files modified

- `app/ai/errors.py` (structured-error metadata)
- `app/ai/structured.py` (parse_failure_kind)
- `app/ai/providers/base.py` (attach + log diagnostics)
- `app/source_analysis/window_analyzer.py` (persist forensics on structured failure)

No prompt, Generation C, planner, max_output, CLEAN, or 3B.7.7A evidence rewrite.

## 63. Recommended next phase

{failure["next_phase_label"]}

Do not retry WIN001. Do not call WIN002/WIN003. Do not increase max_output. Do not start Phase 4.

Wait for human review.
"""
