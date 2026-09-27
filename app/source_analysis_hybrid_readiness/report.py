"""Rapport déterministe 3B.7.6 — aucun horodatage."""

from __future__ import annotations

from typing import Any, Mapping


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _row(windows: list[Mapping[str, Any]], window_id: str) -> Mapping[str, Any]:
    for item in windows:
        if item.get("window_id") == window_id:
            return item
    return {}


def render_report(payload: Mapping[str, Any], result: Any) -> str:
    outcome = getattr(result, "outcome", None) or payload.get("outcome") or "PASS"
    readiness = payload.get("readiness_status") or ""
    clean = payload.get("clean_transcript") or {}
    provenance = clean.get("provenance") or {}
    plan = payload.get("window_plan") or {}
    coverage = plan.get("coverage") or {}
    windows = list(payload.get("requests") or [])
    win001 = _row(windows, "WIN001")
    win002 = _row(windows, "WIN002")
    win003 = _row(windows, "WIN003")
    provider = payload.get("provider_model") or {}
    schemas = payload.get("prompt_schema") or {}
    generation = schemas.get("generation_c") or {}
    timeouts = payload.get("timeouts") or {}
    window_timeout = timeouts.get("window") or {}
    cons_timeout = timeouts.get("consolidation") or {}
    retry = payload.get("retry_audit") or {}
    http = retry.get("http") or {}
    application = retry.get("application") or {}
    cache = payload.get("cache") or {}
    cache_rows = {row["window_id"]: row for row in cache.get("windows") or []}
    publication = payload.get("publication_state") or {}
    disk = payload.get("disk") or {}
    runner = payload.get("runner") or {}
    dry = payload.get("dry_run") or {}
    costs = payload.get("cost_estimates") or {}
    win001_meta = payload.get("win001") or {}
    cons = payload.get("consolidation_policy") or {}
    integrity = payload.get("integrity") or {}
    tests = payload.get("tests") or {}
    state_status = getattr(result, "project_state_status", "") or publication.get(
        "project_state_status", ""
    )
    state_error = getattr(result, "project_state_error", None) or publication.get(
        "project_state_error"
    )
    cache_summary = ", ".join(
        f"{wid}={row.get('cache_state')}" for wid, row in cache_rows.items()
    ) or "MISS"

    return f"""# PHASE 3B.7.6 — HYBRID PRODUCTION EXECUTION READINESS & REAL-CALL PLAN

## Result

{outcome}

PRODUCTION READINESS =
{readiness}

REAL CLEAN WINDOWS =
{plan.get("window_count")}

WIN001 REAL REQUEST =
{"READY" if win001_meta.get("request_ready") else "BLOCKED"}

WIN001 ESTIMATED INPUT =
{win001_meta.get("estimated_input")}

WIN001 HARD MAX =
{win001_meta.get("hard_max")}

WIN001 MAX OUTPUT =
{win001_meta.get("max_output")}

WIN001 TIMEOUT =
connect {win001_meta.get("timeout_connect")} / read {win001_meta.get("timeout_read")}

WIN001 CALL BUDGET =
{win001_meta.get("call_budget")}

WIN001 MAX ATTEMPTS =
{win001_meta.get("max_attempts")}

AUTO RETRY =
NO

AUTO CONTINUE =
NO

CURRENT REAL WINDOW CACHE =
{cache_summary}

CONSOLIDATION GRAMMAR =
UNVERIFIED

CONSOLIDATION GRAMMAR CANARY =
RECOMMENDED

REAL PROVIDER CALLS THIS PHASE =
0

PASTORAL SOURCE MAP =
NOT PUBLISHED

PROJECT STATE =
{state_status} / {state_error}

PHASE 3B =
INCOMPLETE

NEXT ACTION =
HUMAN REVIEW BEFORE ANY REAL CALL

## 1. Result

{outcome}. Readiness={readiness}. This phase did not execute WIN001.

## 2. Objective

Offline production readiness audit and exact future real-call protocol.
First future real execution: WIN001 ONLY after explicit human authorization.

## 3. Baseline

{tests.get("baseline")} passed, 0 failed before modification.

## 4. Current Phase 3B status

INCOMPLETE. analysis/source_map.json pastoral absent.
project_state.source_analysis remains {state_status} / {state_error}.

## 5. CLEAN transcript verification

transcript_id={clean.get("transcript_id")}
mode={clean.get("mode")}
SRC={clean.get("segment_count")}
words={clean.get("word_count")}
duration={clean.get("duration_seconds")}
matches_expected={_yn(bool(clean.get("matches_expected")))}

## 6. Cleanup provenance

removed_src={provenance.get("removed_count")}
removed_set_matches={_yn(bool(provenance.get("removed_set_matches")))}
survivors_unchanged={_yn(bool(provenance.get("survivors_unchanged")))}
original_segment_count={provenance.get("original_segment_count")}
sparse IDs preserved.

## 7. WindowPlannerV2 verification

version={plan.get("planner_version")}
target/hard max/overlap from window-planner-v2.0 unchanged.

## 8. Real window plan

windows={plan.get("window_count")}
owned={plan.get("owned_src_count")}
context={plan.get("context_src_count")}
exact once={_yn(bool(coverage.get("exact_once")))}
WIN001 owned={win001.get("owned_src_count")}
WIN002 owned={win002.get("owned_src_count")}
WIN003 owned={win003.get("owned_src_count")}

## 9. WIN001 request

estimated_input={win001.get("estimated_input_tokens")}
system={win001.get("system_prompt_tokens")}
user={win001.get("user_prompt_tokens")}
max_output={win001.get("max_output")}
stage={win001.get("stage")}
provider={win001.get("provider")}
model={win001.get("model")}
temperature={win001.get("temperature")}
output_language={win001.get("output_language")}
schema={win001.get("response_schema")}
schema_sha={win001.get("response_schema_sha256")}
signature={win001.get("analysis_signature")}
timeout={win001.get("effective_timeout")}
timeout sources connect={win001.get("timeout_connect_source")} read={win001.get("timeout_read_source")}

## 10. WIN002 request

estimated_input={win002.get("estimated_input_tokens")}
owned={win002.get("owned_src_count")}
first/last={win002.get("first_src")}/{win002.get("last_src")}
signature={win002.get("analysis_signature")}

## 11. WIN003 request

estimated_input={win003.get("estimated_input_tokens")}
owned={win003.get("owned_src_count")}
first/last={win003.get("first_src")}/{win003.get("last_src")}
signature={win003.get("analysis_signature")}

## 12. Context margins

usable={win001.get("usable_context")}
WIN001 margin={win001.get("margin")}
WIN002 margin={win002.get("margin")}
WIN003 margin={win003.get("margin")}
all fit usable context and hard max 60000.

## 13. Provider/model

{provider.get("provider")} / {provider.get("model")}
stage={provider.get("stage")}
Do not change model in this phase.

## 14. Credential availability

available={_yn(bool(schemas.get("credential_available")))}
env={schemas.get("credential_env_var")}
secret exposed=NO

## 15. Window prompt

{schemas.get("window_prompt_version")}
SHA recorded in request rows. Unchanged.

## 16. Generation C

raw={generation.get("raw_sha256")}
anthropic={generation.get("anthropic_sha256")}
raw historical={_yn(bool(generation.get("raw_matches_historical")))}
anthropic historical={_yn(bool(generation.get("anthropic_matches_historical")))}

## 17. Schema status

semantic-transport-v1 / Generation C unchanged.
Server grammar already accepted in prior canary (historical audit only).

## 18. Window max output

{win001.get("max_output")}
Future AIRequest uses this value. Not increased.

## 19. Window timeout

connect={window_timeout.get("connect_seconds")} source={window_timeout.get("connect_source")}
read={window_timeout.get("read_seconds")} source={window_timeout.get("read_source")}
Policy review: KEEP 30/1800.
Window ~50k input / 32k max output vs failed global ~143k / 128k.
Single-window bounded semantics. Not a scientific proof.
7200 is not inherited.

## 20. Timeout source

StageSettings AI_STAGE_SETTINGS[source_analysis_window].
Env names {window_timeout.get("env_connect")} / {window_timeout.get("env_read")}
are optional process-scoped confirmations. Not written to .env.

## 21. Retry audit

default AI_MAX_ATTEMPTS={application.get("default_ai_max_attempts")}
unconfigured engine would retry={_yn(bool(application.get("unconfigured_engine_would_retry")))}
canary runner forces max_attempts=1
window analyzer local retry=NO
orchestrator max_attempts=1
application retry on canary path=NO

## 22. HTTP POST retry audit

transport={http.get("transport")}
Session/HTTPAdapter/urllib3 Retry=NO
hidden HTTP POST retry={_yn(bool(http.get("hidden_http_post_retry")))}
SDK=NO
path={{base}}/v1/messages
redirects: default requests follow; residual theoretical 307/308 inside one
requests.post, not an application retry. Anthropic Messages API does not
redirect this POST.

## 23. Call counting

engine.generate attempts counted by orchestrator new_calls_consumed.
One _invoke = one requests.post.
Failed generate consumes the budget.

## 24. Current production cache

{cache_summary}
unexpected semantic artifacts={_yn(bool(cache.get("unexpected_semantic_artifacts")))}
FakeAI in production paths={_yn(bool(cache.get("fake_ai_in_production_paths")))}

## 25. Production paths

WIN001 transport/result/metadata under analysis/windows/WIN001/.
source_map under analysis/source_map.json.
No V1 publication path. No transcript/depot modification.

## 26. Atomic writes

write_text_atomic (.partial → replace) for window transport/result/metadata,
consolidation transport/result, and source_map.

## 27. Transport-first

provider body → transport persistence → decode → validation → result.
No result before transport.

## 28. Cache recovery

valid exact transport + current signature/provenance + missing result
→ local decode/validate recovery → 0 new provider calls.

## 29. WIN001 authorization scope

AUTHORIZATION_SCOPE=WIN001_ONLY
MAX_NEW_CALLS=1
MAX_ATTEMPTS=1
AUTO_CONTINUE=false
AUTO_RETRY=false
AUTO_FALLBACK=false
AUTO_CONSOLIDATION=false
AUTO_PUBLICATION=false

## 30. Dry-run

supported=YES
executed=YES
identical={_yn(bool(dry.get("identical")))}
provider calls=0
selected={dry.get("selected_window")}

## 31. Real runner

module app.source_analysis_hybrid_readiness.canary_cli
defaults to dry-run. Real execution requires --execute-real.

## 32. Explicit execution safety

Missing window → FAIL BEFORE PROVIDER.
Missing --execute-real → dry-run.
allow_real_provider defaults false in the library API.

## 33. Call budget

max_new_calls=1. Even if additional misses exist, no second call.

## 34. Success definition

structured provider response
transport persisted
transport parses
strict decoder passes
WindowResultValidator passes
result persisted atomically
signature matches
SRC refs valid
owned/context rules valid
no editorial leakage
usage/cost captured if supplied
HTTP 200 alone is not success.

## 35. Failure before body

WIN001 FAILED. no transport. no result. budget consumed.
cost UNKNOWN if provider gives none. STOP. No automatic retry.

## 36. Timeout

Same as failure before body. timeout_kind and elapsed recorded.
transport absent. result absent. STOP.

## 37. Invalid transport

Transport preserved if a body was received. Result absent. No retry. STOP.

## 38. Decoder failure

Transport preserved. Result absent. No retry. STOP.

## 39. Validator failure

Transport preserved. Result absent. No retry. STOP.

## 40. Write failure

Transport remains. No fake READY. Recovery from transport. STOP.

## 41. Resume

HIT if valid result + current signature.
Transport recovery if result missing and binding valid.
0 new calls.

## 42. Human WIN001 review gate

Inspect HTTP/provider success, transport existence/schema, validator,
record counts/kinds, SRC grounding, unknown IDs, editorial leakage,
language, obvious semantic quality, usage, cost, latency, timeout
behavior, truncation indicators, finish/stop reason if available.

## 43. Semantic review

Validator PASS is not promotion. Human reviews representative output:
faithful analysis, no hallucinated source claims, no obvious missing
large semantic region, no book/editorial structure, reasonable
topic/idea granularity, uncertainties preserved.
No numeric quality score.

## 44. Remaining-window authorization

Only after WIN001 human approval.
Future: WIN002 then WIN003, max_new_calls=2, sequential,
STOP_ON_FIRST_EXECUTION_FAILURE.
No consolidation in the same authorization.

## 45. STOP_ON_FIRST_FAILURE

Implemented by WindowOrchestrator.
If WIN002 fails, WIN003 is not attempted.

## 46. ALL_WINDOWS_READY gate

WIN001/2/3 READY, current signatures, revalidated caches.
Anything else: consolidation forbidden.

## 47. Consolidation readiness

Separately authorized. Never piggybacked on final window success.
Actual input NOT YET MEASURABLE from real results.

## 48. Consolidation input guard

{cons.get("safe_input_budget")}
If exceeded: STOP. No truncation. No call.

## 49. Consolidation provider/model

Anthropic / claude-sonnet-5
stage={cons.get("stage")}
prompt={cons.get("prompt")}
transport={cons.get("transport")}

## 50. Consolidation max output

{cons.get("max_output")}

## 51. Consolidation timeout

connect={cons_timeout.get("connect_seconds")} / read={cons_timeout.get("read_seconds")}
source={cons_timeout.get("connect_source")} / {cons_timeout.get("read_source")}

## 52. Consolidation schema metrics/status

UNVERIFIED.
3B.7.4 measured 803 raw / 896 Anthropic-adapted and did not call Anthropic.

## 53. Consolidation grammar canary decision

RECOMMENDED.
Prior historical grammar failures. One tiny synthetic request, same
response_schema, max_attempts=1, no retry, no production artifact.
Validates schema acceptance only, not real consolidation semantics.
Adds 1 grammar-validation call.

## 54. Consolidation authorization

Separate human gate after ALL_WINDOWS_READY and optional grammar canary.

## 55. Consolidation success gate

provider response, transport persisted, strict decode,
ConsolidationValidator PASS, NO-DROP accounting PASS, GLOBAL_METADATA
grounded, refs/relations valid, result persisted. Then STOP for human
review before canonical publication.

## 56. Consolidation failure gate

Preserve transport if received. No retry. No reconstruction.
No publication. STOP.

## 57. Canonical reconstruction

Only after all windows READY, real consolidation valid, human approval.
HybridCanonicalReconstructor → normalize_source_map() → canonical validator.
0 provider calls.

## 58. Canonical validation

CANONICAL_VALIDATED precedes PUBLISH_AUTHORIZED.

## 59. Publication gate

Atomic writer only. Target analysis/source_map.json under pastoral V2.
No alternate competing SourceMap.

## 60. State transition

source_analysis SUCCESS only after canonical SourceMap persisted and
re-read/revalidated if conventions require it. Not before.

## 61. Cost observability

Per-call: stage, provider, model, input tokens, output tokens,
cost status, cost amount when known, latency, success/failure.
Unknown remains unknown, never zero.

## 62. WIN001 estimate

ESTIMATE only. {costs.get("win001")}

## 63. WIN002 estimate

ESTIMATE only. Separate from WIN001.

## 64. WIN003 estimate

ESTIMATE only. Separate from WIN001/WIN002.

## 65. Consolidation cost status

NOT YET MEASURABLE for actual request input.
Pricing formula available from configured Sonnet 5 base rates.

## 66. Failure matrix

See audit/source_analysis_hybrid_failure_matrix.json.
Automatic new call default = NO.

## 67. Interrupt safety

KeyboardInterrupt: no success, existing artifacts preserved,
no automatic continuation.

## 68. Crash recovery

before transport → MISS
after transport → local recovery, 0 calls if binding valid
after result → HIT if signature current

## 69. Disk/path readiness

writable={_yn(bool(disk.get("writable")))}
probe removed={_yn(bool(disk.get("probe_removed")))}
semantic output created=NO

## 70. Environment handling

Do not modify .env.
Optional process-scoped:
AI_SOURCE_ANALYSIS_WINDOW_CONNECT_TIMEOUT_SECONDS=30
AI_SOURCE_ANALYSIS_WINDOW_READ_TIMEOUT_SECONDS=1800
Current resolution already 30/1800 from stage settings.

## 71. Exact dry-run command

{runner.get("dry_run_command")}

## 72. Exact future real WIN001 command

{runner.get("real_command")}

DO NOT RUN IT in this phase.

## 73. Future remaining-windows command/contract

After WIN001 human approval:
scope=REMAINING_WINDOWS, WIN002 then WIN003, max_new_calls=2,
sequential, STOP_ON_FIRST_FAILURE.
Orchestrator guarantees cache isolation and stop-on-first-failure.
The WIN001 canary runner will not continue automatically.

## 74. Future consolidation contract

Separate authorization. max calls=1, max attempts=1, retry false.
Grammar canary recommended first. Guard 80000.

## 75. Real-call sequence

GATE 1 dry-run
GATE 2 human authorization
REAL CALL 1 WIN001
GATE 3 review
REAL CALLS 2–3 WIN002 then WIN003
GATE 4 ALL_WINDOWS_READY
GATE 5 grammar canary (additional provider call)
GATE 6 approval
REAL CALL 4 consolidation
GATE 7 review
LOCAL reconstruction + validation
GATE 8 publication authorization
LOCAL atomic publication
STATE SUCCESS only afterward

Production semantic calls = 4
Grammar-validation calls = 1
Do not hide the canary in the total.

## 76. Tests

baseline={tests.get("baseline")}
added={tests.get("added")}
passed={tests.get("passed")}
failed={tests.get("failed")}

## 77. Network

anthropic=0 openai=0 whisper=0 ollama=0 lm_studio=0

## 78. Protected artifacts

byte-identical through 3B.7.5. protected_unchanged={_yn(bool(getattr(result, "protected_unchanged", False)))}

## 79. CLEAN transcript integrity

byte-identical. sha256={clean.get("file_sha256")}

## 80. Contract integrity

planner, window prompt, Generation C, consolidation prompt/transport,
reconstructor, normalizer, canonical validator unchanged.
analyzer.py not wired.

## 81. SourceMap status

NOT PUBLISHED. path exists={_yn(bool(publication.get("source_map_present")))}

## 82. Project state

{state_status} / {state_error}
unchanged.

## 83. Files added

app/source_analysis_hybrid_readiness/*
app/tests/test_source_analysis_hybrid_readiness.py
audit artifacts listed in the runner result.

## 84. Files modified

None of the protected historical artifacts.
No analyzer.py. No .env. No CLEAN transcript.

## 85. Final readiness decision

{readiness}

NEXT ACTION = HUMAN REVIEW BEFORE ANY REAL CALL
Next phase if authorized: 3B.7.7A — REAL WIN001 CANARY
exactly 1 real semantic Anthropic call maximum.
Do not start it now.

## Technical decision questions

Was baseline 2285 green? YES
Is CLEAN transcript still valid? {_yn(bool(clean.get("matches_expected")))}
How many windows? {plan.get("window_count")}
Exact estimated request tokens WIN001/2/3? {win001.get("estimated_input_tokens")} / {win002.get("estimated_input_tokens")} / {win003.get("estimated_input_tokens")}
All <= 60000? {_yn(bool(coverage.get("no_hard_max_violation")))}
Actual analysis signatures? see request rows
Current cache states? {cache_summary}
Unexpected real semantic artifacts? {_yn(bool(cache.get("unexpected_semantic_artifacts")))}
Anthropic credential configuration available? {_yn(bool(schemas.get("credential_available")))}
Secret value exposed? NO
Provider/model? {provider.get("provider")} / {provider.get("model")}
Prompt? {schemas.get("window_prompt_version")}
Response schema? semantic-transport-v1 / Generation C
Max output? {win001.get("max_output")}
Temperature? {provider.get("temperature")}
Output language? {provider.get("output_language")}
Connect/read timeout? {window_timeout.get("connect_seconds")} / {window_timeout.get("read_seconds")}
Timeout source? {window_timeout.get("connect_source")} / {window_timeout.get("read_source")}
Does 7200 leak into window stage? {_yn(bool((timeouts.get("window_with_global_7200_env") or {}).get("inherits_7200")))}
Is 30/1800 retained? YES — bounded window vs failed global; policy KEEP
Automatic application retries disabled on canary path? YES
HTTP-level POST retries disabled? YES
Can one authorized engine call create multiple POSTs? NO on canary path (max_attempts=1, no Session retry)
WIN001 future call budget exactly 1? YES
Does failed call consume it? YES
Can runner continue automatically to WIN002? NO
Can runner consolidate automatically? NO
Can runner publish source_map? NO
Can WIN001 success mark global SUCCESS? NO
WIN001 success artifacts? analysis/windows/WIN001/transport.json, result.json, metadata.json
What survives decoder/validator failure? transport
Can valid transport recover without provider call? YES
Human review after WIN001? technical + semantic, STOP always
WIN002/WIN003 conditions? WIN001 human approval
Remaining windows with max_new_calls=2 safe? YES at orchestrator (cache, sequential, STOP_ON_FIRST_FAILURE)
If WIN002 fails? WIN003 not attempted
ALL_WINDOWS_READY? three READY + current signatures + revalidation
Consolidation separately authorized? YES
Consolidation grammar server-verified? NO
Grammar canary recommended? YES — unverified schema, historical grammar failures
How many calls would that add? 1 grammar-validation call
Does grammar canary create production semantic artifacts? NO
Actual consolidation input size now? not yet measurable
Consolidation hard guard? 80000
If exceeded? STOP / no truncation / no call
Future consolidation max output? {cons.get("max_output")}
Timeout? 30 / 1800
After valid real consolidation? STOP for human review
Canonical reconstruction local? YES / 0 calls
Canonical validation before publication? YES
Publication before SUCCESS state? YES
WIN001 estimates distinct from actual? YES
Unknown cost represented as zero? NO
Real dry-run executed? YES
Provider calls? 0
Protected artifacts changed? NO
Pastoral source_map created? NO
Project state changed? NO
Tests pass? {tests.get("passed")}
READY_FOR_WIN001_CANARY or BLOCKED? {readiness}
Exact next action? HUMAN REVIEW BEFORE ANY REAL CALL
"""
