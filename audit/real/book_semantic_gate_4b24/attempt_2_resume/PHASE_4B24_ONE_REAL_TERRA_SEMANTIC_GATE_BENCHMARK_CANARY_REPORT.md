# PHASE 4B.2.4 — ONE REAL TERRA SEMANTIC-GATE BENCHMARK CANARY

## Attempts

ATTEMPT 1 =
BLOCKED_PRECALL
OPENAI_API_KEY missing
provider calls 0

ATTEMPT 2 =
credential available
exact frozen request reconstructed
provider call 1
FAIL

## Result

FAIL

AUTHORIZED TERRA CALLS =
1

ACTUAL TERRA CALLS =
1

SONNET CALLS =
0

RETRIES =
0

FALLBACKS =
0

4B.2 =
FAIL

4B.2.2 =
PARTIAL

4B.2.3 =
PASS

SOURCE MAP SHA256 PRE / POST =
df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 / df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855

EDITORIAL PLAN SHA256 PRE / POST =
01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 / 01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440

CLEAN TRANSCRIPT SHA256 PRE / POST =
1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958 / 1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958

BENCHMARK SHA256 =
3888806c68eeff7dc363790d4e0ffcf063e099c3f295e684b80b3c9e8167af82

BENCHMARK CASES =
10

SUPPORTED POSITIVES =
6

SEMANTIC NEGATIVES =
4

LABEL LEAKAGE =
0

MODEL =
OpenAI / gpt-5.6-terra

PROMPT =
book-semantic-validator-1.0

TRANSPORT =
book-semantic-validation-transport-1.0

OUTPUT MODE =
json_object

THINKING =
provider_default

TEMPERATURE =
omitted

REQUEST SHA256 =
09d6472e544bc60231c77908e6608ff7ee7b6fd4746317f206301082e21eab53

REQUEST DETERMINISM =
PASS

CONTEXT ESTIMATE =
8040

LONG-CONTEXT REGIME =
NOT APPLICABLE

ESTIMATED COST =
0.114384 USD

HTTP / FINISH =
None / None

REQUEST ID =
—

INPUT TOKENS =
—

OUTPUT TOKENS =
—

THINKING / REASONING TOKENS =
unknown

ACTUAL COST =
UNKNOWN

JSON PARSE =
FAIL

TRANSPORT DECODE =
PASS

CASE COVERAGE =
FAIL

UNKNOWN CASES =
0

DUPLICATE RESULTS =
0

SPAN VALIDATION =
PASS

POSITIVE ACCEPTED =
0 / 6

POSITIVE FALSE REJECTIONS =
0

NEGATIVE BLOCKED =
0 / 4

NEGATIVE FALSE NEGATIVES =
0

VERDICT ACCURACY =
0.0

NEGATIVE RECALL =
0.0

POSITIVE SPECIFICITY =
0.0

REASON-CODE COMPATIBLE =
0 / 4

FUNERAL CASE =
MISSING (none)

CONNECTIVE CASE =
MISSING (none)

P3 CASE =
MISSING (none)

P8 CASE =
MISSING (none)

PARTIAL-PARAGRAPH DETECTION =
FAIL

EXTERNAL-KNOWLEDGE RESISTANCE =
FAIL

RATIONALE QUALITY =
MISSING

DETERMINISTIC REPLAY =
PASS

4B.2.2 CANDIDATE CACHE =
NOT ACCEPTED

PRODUCTION CACHE =
UNCHANGED

book.json =
NOT PUBLISHED

FOCUSED TESTS =
36 passed
0 new failures
network blocked

READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT =
NO

READY_FOR_FULL_REAL_BOOK_GENERATION =
NO

NEXT ACTION =
HUMAN REVIEW

## Notes

ATTEMPT 1 = BLOCKED_PRECALL. OPENAI_API_KEY was missing. Provider calls = 0. Evidence preserved under `audit/real/book_semantic_gate_4b24/attempt_1_blocked_precall/`.

ATTEMPT 2 = credential available. Exact frozen request reconstructed twice. REQUEST SHA256 = 09d6472e544bc60231c77908e6608ff7ee7b6fd4746317f206301082e21eab53. LABEL LEAKAGE = 0. Context safety PASS. Estimated cost 0.114384 USD (estimate only). The one-shot engine.generate / _invoke authorization was then consumed.

The OpenAI Python SDK is not installed in this interpreter (`C:\Program Files\Python311\python.exe`). `_invoke` failed at `from openai import OpenAI` before any HTTP request. No request ID. No HTTP status. No finish reason. No tokens. No raw response. HTTP to OpenAI = 0. Actual spend UNKNOWN, not inferred as zero.

ACTUAL TERRA CALLS TOTAL = 1 because the one-shot guard and lock were consumed. This is not a completed provider semantic-gate result. RETRIES = 0. FALLBACKS = 0. SONNET CALLS = 0. The lock `book_semantic_gate_4b24_real_call.lock` remains consumed. No second call is authorized.

RESULT = FAIL because the response contract and case coverage materially failed (empty payload). This is not a semantic FAIL on funeral / connective / p3 / p8 false negatives. Those four negatives were never classified SUPPORTED; they were never returned. All 10 Terra decisions are MISSING.

EXTERNAL-KNOWLEDGE RESISTANCE and PARTIAL-PARAGRAPH DETECTION are recorded FAIL only because p3/p8 were absent, not because Terra rescued them from memory.

DETERMINISTIC REPLAY = PASS only for the empty failure canonical, replayed twice from the saved null response. It is not a replay of a Terra JSON object.

10 cases are an engineering canary, not a statistical model-quality benchmark.

book-generator-1.0.1 remains SUFFICIENT_WITH_SEMANTIC_GATE. This phase does not automatically change that assessment.

book.json = NOT PUBLISHED. PRODUCTION CACHE = UNCHANGED. CH016 was not generated or accepted.

Wait for human review.
