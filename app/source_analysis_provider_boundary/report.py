"""Rapport markdown déterministe 3B.7.7A.5."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_provider_boundary.constants import (
    NEXT_ACTION,
    NEXT_PHASE_LABEL,
    PRIMARY_FINDING,
    RESULT,
    SECONDARY_FINDING,
    THIRD_WIN001_CALL,
    WINDOW_ANALYSIS_11_REAL_STATUS,
)


def _yn(value: Any) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    if value is None:
        return "UNKNOWN"
    return str(value)


def render_report(bundle: Mapping[str, Any]) -> str:
    d = bundle["diagnosis"]
    matrix = bundle["matrix"]
    arch = bundle["architecture"]
    two = bundle["two_call"]
    narrowing = d["call_2_narrowing"]
    integ = d["integrity"]
    rows = "\n".join(
        f"| {row['FAILURE_CLASS']} | {_yn(row['HTTP_RESPONSE_AVAILABLE'])} | "
        f"{_yn(row['RAW_BYTES_AVAILABLE'])} | {_yn(row['CURRENTLY_PERSISTED'])} | "
        f"{row['CURRENTLY_LOGGED']} | {row['SECRET_RISK']} |"
        for row in matrix["rows"]
    )
    inventory = "\n".join(
        f"- `{item['module']}.{item['function']}` — {item['condition']} "
        f"→ `{item['classification']}`"
        for item in d["inventory"]
    )
    comparison = "\n".join(
        f"| {row['dimension']} | {row['call_1_0']} | {row['call_1_1']} |"
        for row in two["comparison"]
    )
    alternatives = "\n".join(
        f"- {item['id']}. {item['label']} — {item['status']}"
        for item in arch["alternatives_reviewed_not_selected"]
    )

    return f"""# PHASE 3B.7.7A.5 — AIResponseError Provider Boundary Forensics & Architecture Review

## Result

{RESULT}

REAL PROVIDER CALLS THIS PHASE =
0

THIRD WIN001 CALL =
{THIRD_WIN001_CALL}

CALL #1 =
AIStructuredOutputError

CALL #2 =
AIResponseError

CALL #2 EXACT SUB-CONDITION =
UNKNOWN

HTTP RESPONSE RECEIVED =
PROVEN

HTTP STATUS KNOWN =
NO

RAW BODY AVAILABLE HISTORICALLY =
NO

RAW BODY PERSISTED =
NO

USAGE PERSISTED =
NO

STOP REASON PERSISTED =
NO

REQUEST ID PERSISTED =
NO

CURRENT FORENSIC COVERAGE =
AIStructuredOutputError plus all HTTP-received provider-boundary failures

NEW FORENSIC BOUNDARY =
capture_http_response before JSON/content interpretation

OFFLINE REPLAY =
READY

WINDOW-ANALYSIS-1.1 REAL STATUS =
{WINDOW_ANALYSIS_11_REAL_STATUS}

PRIMARY ARCHITECTURAL FINDING =
{PRIMARY_FINDING}

SOURCE MAP =
NOT PUBLISHED

PHASE 3B =
INCOMPLETE

NEXT ACTION =
{NEXT_ACTION}


## 1. Result

PARTIAL.

Architecture and forensics were hardened offline. Call #2 cannot be narrowed
beyond `AIResponseError` among four HTTP-success interpretation branches.
The historical raw body is irrecoverable. No provider call was made.


## 2. Objective

Determine where `AIResponseError` can occur on the Anthropic path before
`ProviderResult` / `AIResponse`, then persist a forensic envelope as soon as
an HTTP response exists.


## 3. Baseline

Before implementation: **2357 passed, 0 failed**.


## 4. Real-call history

Two authorized Anthropic WIN001 calls exist. A third is not authorized.


## 5. Call #1 evidence

Immutable 3B.7.7A evidence. `window-analysis-1.0`. `AIStructuredOutputError`.
Provider usage 106973 / 32000. Cost USD 0.533946. HTTP body received.
Structured parse attempted and failed. Transport absent. Result absent.


## 6. Call #2 evidence

Immutable 3B.7.7A.4 evidence. `window-analysis-1.1`. `AIResponseError` after
320639 ms. Structured parse not reached. Transport absent. Forensics absent.
Usage / finish reason / request id / cost unavailable.


## 7. Evidence limitations

Logs contain `error_type=AIResponseError` only. No traceback. No exception
message. No HTTP status. No raw body. Do not invent one.


## 8. Exact AIResponseError inventory

{inventory}

Wrappers: `translate_sdk_error` (OpenAI unrecognized). No other conversion
invents `AIResponseError` from a different type.


## 9. Anthropic request lifecycle

WindowAnalyzer → `BaseAIEngine.generate` → `AnthropicEngine._invoke` →
`build_payload` → `execute_provider_post` / `requests.post` →
`capture_http_response` → status → JSON-from-bytes →
`extract_anthropic_text` → `ProviderResult` → `AIResponse` →
`parse_structured_output`.


## 10. HTTP boundary

Capture now occurs immediately after `requests.post` returns. Timeouts and
connection errors set `response_received=false` and fabricate no body.


## 11. JSON decoding

JSON is decoded from captured `response.content` bytes, not from a later
`response.json()` that could fail after discarding bytes.


## 12. Envelope validation

Non-object JSON is `INVALID_RESPONSE_TOP_LEVEL`. Object JSON continues.


## 13. Content validation

Missing content / non-list content / no text block / malformed text block
are distinct classifications. Usage and `stop_reason` are extracted first.


## 14. Text extraction

`extract_anthropic_text` requires `type=text` and `text` as a string.
`_extract_text` remains an alias to the same parser.


## 15. ProviderResult construction

Only after a valid text extraction. The HTTP envelope is attached.


## 16. AIResponse construction

Only after `ProviderResult`. Structured-parse failures still attach
`exc.response` (Phase 3B.2) and now also the HTTP envelope.


## 17. Structured parsing

Unchanged fail-closed path. Classification
`STRUCTURED_JSON_DECODE` / `STRUCTURED_SCHEMA_VALIDATION`.


## 18. Failure boundaries

Transport, HTTP error, invalid JSON, wrong top-level type, missing content,
wrong content type, no text, malformed text, ProviderResult, AIResponse,
structured JSON, schema, semantic/granularity/window validation.


## 19. Current data-loss points

Historical call #2 already lost its body. New failures after HTTP receive
persist bytes + envelope. Interrupt after HTTP attempts persist.


## 20. Current forensic coverage

`AIStructuredOutputError` already persisted extracted text. `AIResponseError`
before `ProviderResult` now persists the HTTP envelope.


## 21. Forensic matrix

| FAILURE CLASS | HTTP | RAW BYTES | PERSISTED NOW | LOGGED | SECRET RISK |
| --- | --- | --- | --- | --- | --- |
{rows}


## 22. Raw bytes

Authoritative. Stored as `provider_raw_response.bin`. Size recorded.


## 23. Raw text

UTF-8 decode is metadata only (`text_decode_ok`). Bytes remain source.


## 24. HTTP status

Captured on the envelope. Call #2 status remains unknown.


## 25. Request ID

Whitelist: `request-id`, `x-request-id`. Body `id` is best-effort backup.
Call #2 request id remains unavailable.


## 26. Usage

Best-effort from JSON `usage`. Failure to parse does not drop the raw body.


## 27. Stop reason

Best-effort from `stop_reason`. Same independence.


## 28. Content metadata

`content_present`, type, block count, block types, text lengths. No raw
text in Markdown or logs.


## 29. Cost accounting

`CostTracker.record_failure` can use tokens on the error when no AIResponse
exists. Absent usage stays UNKNOWN, never zero.


## 30. Call accounting

`requests.post` count remains independent of AIResponse creation.


## 31. Error taxonomy

HTTP_TRANSPORT_FAILURE, HTTP_ERROR, INVALID_RESPONSE_JSON,
INVALID_RESPONSE_TOP_LEVEL, MISSING_CONTENT, INVALID_CONTENT_TYPE,
NO_TEXT_BLOCK, INVALID_TEXT_BLOCK, STRUCTURED_JSON_DECODE,
STRUCTURED_SCHEMA_VALIDATION, plus existing semantic/window classes.
`AIResponseError` remains the base type.


## 32. New forensic boundary

`capture_http_response` before interpretation. Persist on failure, including
from `provider_forensic_scope` in `analyze_window`.


## 33. Provider response envelope

See architecture artifact. No secrets. No raw body inside the JSON
metadata file.


## 34. Persistence order

POST → capture → persist-on-failure → interpret → extract → AIResponse →
structured parse.


## 35. Raw storage policy

Failure: full raw bytes. Success: in-memory compact metadata only.


## 36. Header whitelist

`request-id`, `x-request-id`, `content-type`, `content-length`, `retry-after`.


## 37. Secret handling

Never persist Authorization, x-api-key, cookies, or secret request headers.
Tests assert absence.


## 38. Signature-aware paths

`analysis/provider_forensics/<window_id>/<analysis_signature>/`


## 39. Collision behavior

Refuse silent overwrite. Same SHA is idempotent. Different SHA raises
`ProviderForensicCollisionError`.


## 40. Atomicity

`.partial` + replace for envelope JSON and raw bytes.


## 41. Interruption behavior

If HTTP already arrived, `KeyboardInterrupt` attempts persist. If persist
has not started, evidence can still be lost. Documented, not over-engineered.


## 42. Offline replay

`replay_provider_http`. Diagnostic only.


## 43. Replay strictness

Same production parsers. No JSON repair. No transport/result publish.


## 44. Generic provider responsibility

HTTP capture, status, JSON-from-bytes, header whitelist, persist, replay shell.


## 45. Anthropic-specific responsibility

Content blocks, usage/stop_reason keys, content metadata.


## 46. Other-provider regression

Ollama and LM Studio use the generic HTTP envelope without Anthropic
content assumptions. OpenAI remains on the SDK path.


## 47. Call #1 vs call #2

| Dimension | 1.0 call | 1.1 call |
| --- | --- | --- |
{comparison}


## 48. 1.1 bounded-policy status

UNVALIDATED_REAL. Not proven good. Not proven bad.


## 49. Current primary problem

{PRIMARY_FINDING}


## 50. Secondary problems

{SECONDARY_FINDING}


## 51. Architecture alternatives

{alternatives}

This phase does not authorize implementing B–E.


## 52. Invalid JSON fixture

HTTP 200, invalid JSON. Classification `INVALID_RESPONSE_JSON`. Raw preserved.
No AIResponse. No retry.


## 53. Non-object fixture

JSON array. Fail closed + forensics.


## 54. Missing-content fixture

Usage and stop_reason retained when present.


## 55. No-text fixture

Raw response retained. Classification `NO_TEXT_BLOCK`.


## 56. Structured-parse fixture

Valid provider envelope, invalid semantic JSON. `AIStructuredOutputError`.
Raw HTTP + extracted text preserved.


## 57. Non-2xx fixture

`HTTP_ERROR` / existing HTTP error class. Safe body preserved. Not a
semantic parse error.


## 58. Timeout fixture

`response_received=false`. No fabricated body.


## 59. Connection fixture

Same distinction.


## 60. Request-id fixture

Safe `request-id` header persisted.


## 61. Secret fixture

Authorization / cookie-like fields not persisted.


## 62. Usage-before-AIResponse fixture

Malformed content, valid usage retained.


## 63. Collision fixture

Second write does not destroy the first artifact.


## 64. Atomicity fixture

Interrupted write leaves no valid final JSON.


## 65. Replay fixtures

Invalid JSON, missing content, no text, invalid structured, valid structured.
No network.


## 66. Success regression

Existing Anthropic valid structured-output tests remain green.


## 67. Tests

New provider-boundary tests plus full suite. Expected green after this phase.


## 68. Network

0 real network. 0 provider calls.


## 69. Protected artifacts

Historical artifacts through 3B.7.7A.4 remain byte-identical.


## 70. CLEAN integrity

SHA expected `{integ["clean_expected"]}`. Unchanged = {_yn(integ["clean_unchanged"])}.


## 71. Prompt integrity

window-analysis-1.0 SHA unchanged = {_yn(integ["prompt_1_0_unchanged"])}.
window-analysis-1.1 SHA unchanged = {_yn(integ["prompt_1_1_unchanged"])}.
Neither prompt was modified.


## 72. Generation C integrity

Raw unchanged = {_yn(integ["generation_c_raw_unchanged"])}.
Anthropic closed schema unchanged = {_yn(integ["generation_c_anthropic_unchanged"])}.


## 73. Granularity-policy integrity

window-granularity-1.0 unchanged. 160 / 64 IDEA / 36 RELATION unchanged.


## 74. SourceMap status

NOT PUBLISHED. Absent.


## 75. Project state

Not SUCCESS. Historical `failed` / `AITimeoutError` unchanged by this phase.


## 76. Files added

Application: `app/ai/provider_forensics.py`,
`app/source_analysis_provider_boundary/*`,
`app/tests/test_ai_provider_response_boundary.py`,
`app/tests/test_source_analysis_provider_boundary_audit.py`.

Audit: the four JSON artifacts and this report.


## 77. Files modified

`app/ai/errors.py`, `app/ai/structured.py`, `app/ai/providers/_http.py`,
`app/ai/providers/anthropic_engine.py`, `app/ai/providers/base.py`,
`app/ai/providers/ollama.py`, `app/ai/providers/lmstudio.py`,
`app/ai/providers/openai_engine.py`, `app/ai/cost.py`,
`app/source_analysis/window_analyzer.py`, `app/tests/ai_fakes.py`,
timeout inspect tests, 3B.7.7A.1 diagnosis line freeze.


## 78. Remaining unknowns

Call #2 exact AIResponseError branch. HTTP status. Raw body. Usage.
Stop reason. Request id. Cost. Whether content existed.


## 79. Recommended next phase

{NEXT_PHASE_LABEL}

Offline architecture decision only. Do not call WIN001 again from that phase.


## Questions

Were any provider calls made? NO.

Was WIN001 called again? NO.

What exact functions can raise AIResponseError? See inventory.

Which branch most closely matches 3B.7.7A.4? One of four HTTP-success
interpretation branches. Not proven.

Is that branch proven? NO.

What data existed before each branch? After HTTP receive: status, headers,
raw bytes. After JSON object: usage/stop_reason if present.

When is response.content available? After requests.post returns a response.

When is response.text available? Same, as a decode of those bytes.

When is response.json() attempted? No longer. Bytes are decoded.

Can response.json() fail before forensic persistence? Historically YES.
Now decode uses already-captured bytes.

Can valid JSON have wrong top-level type? YES. Now classified and persisted.

What happens if content is missing? MISSING_CONTENT + forensics.

What happens if content is not a list? INVALID_CONTENT_TYPE + forensics.

What happens if there is no text block? NO_TEXT_BLOCK + forensics.

Where was call #2 evidence lost? After HTTP receive, before/during
interpretation, because persist required AIResponse / structured error.

Does forensic persistence currently depend on AIResponse existing?
Historically YES. Now NO.

What new boundary was implemented? capture_http_response before interpretation.

Does it occur before provider interpretation? YES.

Can invalid JSON now be preserved? YES.

Can missing-content response now be preserved? YES.

Can usage be retained even if content is malformed? YES.

Can stop_reason be retained if present? YES.

Can request ID be retained? YES, from whitelist headers or body id.

Are raw bodies kept out of logs? YES.

Are secrets excluded? YES.

Are paths signature-aware? YES.

Can evidence be overwritten silently? NO.

Are writes atomic? YES.

Is offline replay available? YES.

Does replay use production parser? YES.

Does replay repair JSON? NO.

Can malformed-response cost be known if usage exists? YES.

Can cost remain unknown if usage absent? YES.

Did generic changes break other providers? Covered by regression tests.

Is window-analysis-1.1 proven bad? NO.

Is window-analysis-1.1 proven good? NO.

Correct status? UNVALIDATED_REAL.

Was prompt changed? NO.

Was max_output changed? NO.

Were windows replanned? NO.

Is a third WIN001 call authorized? NO.

What is the primary architectural finding? {PRIMARY_FINDING}

What remains unknowable about call #2? Exact sub-condition, status, body,
usage, stop reason, request id, cost.

What exact next phase is recommended? {NEXT_PHASE_LABEL}
"""
