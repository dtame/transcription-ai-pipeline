# PHASE 4B.2.6 — ONE REAL TERRA SEMANTIC-GATE CANARY

RESULT = FAIL
HISTORICAL 4B.2.5 = FAIL
4B.2.5.1 = PASS
AUTHORIZED REMOTE INVOCATIONS = 1
EXECUTION ATTEMPTS = 1
REMOTE INVOCATIONS = 1
HTTP REQUESTS = 1
PROVIDER RESPONSES = 1
SONNET CALLS = 0
RETRIES = 0
FALLBACKS = 0
PYTHON EXECUTABLE = C:\TranscriptionAI\.venv\Scripts\python.exe
OPENAI SDK VERSION = 2.43.0
MODEL/ENDPOINT = gpt-5.6-terra / chat.completions
PROVIDER READINESS = PASS
CANONICAL HASHES PRE/POST = pre source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958; post source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958
BENCHMARK IDENTITY = MATCH
REQUEST SHA256 = 8a92848e412763f0e67468245f9c007ee9537ffa4f2f5469af9a6934d9ebeb31
REQUEST DETERMINISM = PASS
TOKEN FIELD = max_completion_tokens
TOKEN BUDGET = 8192
JSON_OBJECT = local PASS / server UNKNOWN
SERVER-ONLY UNKNOWNS = json_object_server_acceptance=UNKNOWN; max_completion_tokens_server_acceptance=UNKNOWN; temperature_server_behavior=UNKNOWN; reasoning_or_thinking_server_behavior=UNKNOWN; actual_cost=UNKNOWN
LABEL LEAKAGE = 0
CONTEXT SAFETY = PASS
ESTIMATED COST = 0.114384 USD
HTTP/FINISH = None / length
REQUEST ID = chatcmpl-EU9Ip28ayYHuhTrVYGY0CPP4JGEH5
INPUT TOKENS = 4076
OUTPUT TOKENS = 8192
REASONING TOKENS = unknown
ACTUAL COST = 0.1064560 USD
JSON PARSE = FAIL
TRANSPORT = PASS
CASE COVERAGE = FAIL
CLAIM/SPAN COVERAGE = PASS
POSITIVES ACCEPTED = 0 / 6
POSITIVE FALSE REJECTIONS = 0
NEGATIVES BLOCKED = 0 / 4
NEGATIVE FALSE NEGATIVES = 0
FUNERAL = MISSING (none)
CONNECTIVE = MISSING (none)
P3 = MISSING (none)
P8 = MISSING (none)
EXTERNAL-KNOWLEDGE RESISTANCE = FAIL
REASON-CODE COMPATIBILITY = 0 / 4
DETERMINISTIC REPLAY = PASS
TESTS = 301 passed in 8.38s
PRODUCTION CACHE = UNCHANGED
book.json = NOT PUBLISHED
READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT = NO
READY_FOR_FULL_REAL_BOOK_GENERATION = NO
NEXT ACTION = HUMAN REVIEW

## Historical status

4B.2 = FAIL
4B.2.1 = PASS
4B.2.2 = PARTIAL
4B.2.3 = PASS
4B.2.4 = FAIL
4B.2.4.1 = PASS
4B.2.5 = FAIL
4B.2.5.1 = PASS

Do not rewrite any historical result.

## Server-only uncertainties documented before the call

- json_object_server_acceptance = UNKNOWN. Local serialization of response_format=json_object was PASS. 4B.2.5 never observed a JSON body. UNKNOWN is not PASS.
- max_completion_tokens_server_acceptance = UNKNOWN. Local mapping to max_completion_tokens=8192 was PASS. No successful Terra response had been observed before this call.
- temperature_server_behavior = UNKNOWN. Temperature omitted locally.
- reasoning_or_thinking_server_behavior = UNKNOWN. Thinking is provider_default / omitted.
- actual_cost = UNKNOWN before the call. The earlier estimate 0.114384 USD was not a guarantee.

UNKNOWN is not PASS. No separate live probe was authorized.

## What happened

Precall gates passed. The production path built the corrected request twice. Both hashes matched `8a92848e412763f0e67468245f9c007ee9537ffa4f2f5469af9a6934d9ebeb31`. The payload used `max_completion_tokens=8192`, omitted `max_tokens`, omitted temperature, omitted thinking, and included `response_format=json_object`. Label leakage was 0. Canonical SourceMap / EditorialPlan / clean-transcript hashes matched before and after.

Exactly one OpenAI `gpt-5.6-terra` `chat.completions.create` invocation was executed. There was no retry, no fallback, no Sonnet call, and no request adaptation.

The 4B.2.5 HTTP 400 `unsupported_parameter max_tokens` failure did not recur. The server accepted `max_completion_tokens=8192` and returned a completion:

- request_id = chatcmpl-EU9Ip28ayYHuhTrVYGY0CPP4JGEH5
- elapsed = 77328 ms
- input_tokens = 4076
- output_tokens = 8192
- finish_reason = length
- visible message content = empty string
- raw response SHA256 = none (0 bytes)

Structured-output processing then failed: `Sortie structurée demandée mais la réponse du modèle est vide.` No JSON repair and no second model call were performed.

This is a response-contract failure, not an HTTP 400. The model consumed the entire 8192-token output budget and returned no usable JSON. Reasoning tokens were not exposed by the provider (`unknown`, not zero).

## Call accounting

- authorized_remote_invocations = 1
- execution_attempts = 1
- remote_invocations = 1
- http_requests = 1
- provider_responses = 1
- successful_payloads = 1 (SDK returned a completion object with empty content; the structured semantic payload was not usable)
- retries = 0
- fallbacks = 0
- sonnet_calls = 0

A remote SDK invocation counts against the authorized slot even with no usable content. The one-shot lock is consumed. No second Terra call is authorized.

## Cost

Estimated precall cost = 0.114384 USD (not a guarantee).
Actual billed-token estimate from provider usage = 0.1064560 USD (input 0.008152 + output 0.098304).
Status = base_estimate. Long-context pricing remains unmodeled. Unknown actual cost is not reported as zero.

## Response validation and benchmark

JSON parse = FAIL. Transport decode was recorded PASS only because there was no Mapping to decode; acceptance still reported `transport inattendu : NoneType`. Case coverage = FAIL: 0/10 required handles returned, 10 missing, 0 unknown, 0 duplicates.

Span / claim coverage = PASS is vacuous: there were no paragraph results to check. Deterministic replay = PASS is likewise vacuous: two empty parses are identical and the provider was not contacted again.

All ten frozen human-labeled cases are MISSING. There is no Terra verdict to compare.

- positives accepted = 0/6
- positive false rejections = 0 (no classifications were issued)
- negatives blocked = 0/4
- negative false negatives = 0 (no SUPPORTED negatives; the cases were absent)
- FUNERAL = MISSING
- CONNECTIVE = MISSING
- P3 = MISSING
- P8 = MISSING
- reason-code compatibility = 0/4
- external-knowledge resistance = FAIL (P8 never blocked because no result existed)

10 cases are an engineering canary, not a statistical model-quality benchmark.

## Post-call observations (do not rewrite precall UNKNOWN)

- The server accepted `max_completion_tokens=8192` and generated 8192 output tokens. That is stronger than the precall UNKNOWN, but it is not a usable semantic-gate response.
- The request with `json_object` was not rejected. No JSON body was returned, so json_object content acceptance remains unproven.
- finish_reason=length with empty visible content is consistent with hidden reasoning consuming the output budget. Reasoning tokens were not exposed.

## Tests

After the remote invocation, network was blocked. Focused suites: OpenAI compatibility, runtime preflight, request identity, semantic transport, response schema, span validation, claim coverage, reason codes, benchmark scoring, call accounting, secret leakage, deterministic replay, Anthropic non-regression.

TESTS = 301 passed in 8.38s. Failed = 0. New failures = 0.

## Readiness

READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT = NO
READY_FOR_FULL_REAL_BOOK_GENERATION = NO
PRODUCTION CACHE = UNCHANGED
book.json = NOT PUBLISHED
book-generator-1.0.1 remains SUFFICIENT_WITH_SEMANTIC_GATE unless new evidence materially requires reassessment.

No second Terra call. No CH016 regeneration. No 19-chapter production. No Phase 5, translation, Word, cover, or PDF.

NEXT ACTION = HUMAN REVIEW
