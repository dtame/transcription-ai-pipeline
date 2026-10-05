# PHASE 4B.2.5 — ONE REAL TERRA SEMANTIC-GATE BENCHMARK CANARY

## Result

FAIL

HISTORICAL 4B.2.4 =
FAIL

4B.2.4.1 =
PASS

AUTHORIZED REMOTE TERRA INVOCATIONS =
1

EXECUTION ATTEMPTS =
1

REMOTE INVOCATIONS =
1

HTTP REQUESTS =
1

PROVIDER RESPONSES =
1

SONNET CALLS =
0

RETRIES =
0

FALLBACKS =
0

PYTHON EXECUTABLE =
C:\TranscriptionAI\.venv\Scripts\python.exe

OPENAI SDK VERSION =
2.43.0

PROVIDER READINESS =
PASS

SOURCE MAP SHA =
df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855

EDITORIAL PLAN SHA =
01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440

CLEAN TRANSCRIPT SHA =
1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958

BENCHMARK IDENTITY =
MATCH

REQUEST SHA256 =
09d6472e544bc60231c77908e6608ff7ee7b6fd4746317f206301082e21eab53

REQUEST DETERMINISM =
PASS

LABEL LEAKAGE =
0

CONTEXT SAFETY =
PASS

LONG-CONTEXT =
NOT APPLICABLE

ESTIMATED COST =
0.114384 USD

HTTP / FINISH =
400 / invalid_request_error

REQUEST ID =
—

INPUT TOKENS =
—

OUTPUT TOKENS =
—

REASONING TOKENS =
unknown

ACTUAL COST =
UNKNOWN

JSON PARSE =
FAIL

TRANSPORT =
PASS

CASE COVERAGE =
FAIL

SPAN / CLAIM COVERAGE =
PASS

POSITIVE ACCEPTED =
0 / 6

POSITIVE FALSE REJECTIONS =
0

NEGATIVE BLOCKED =
0 / 4

NEGATIVE FALSE NEGATIVES =
0

FUNERAL =
MISSING (none)

CONNECTIVE =
MISSING (none)

P3 =
MISSING (none)

P8 =
MISSING (none)

EXTERNAL-KNOWLEDGE RESISTANCE =
FAIL

REASON-CODE COMPATIBILITY =
0 / 4

DETERMINISTIC REPLAY =
PASS

FOCUSED TESTS =
63 passed in 4.22s

PRODUCTION CACHE =
UNCHANGED

book.json =
NOT PUBLISHED

READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT =
NO

READY_FOR_FULL_REAL_BOOK_GENERATION =
NO

NEXT ACTION =
HUMAN REVIEW

## Historical status

4B.2 = FAIL
4B.2.1 = PASS
4B.2.2 = PARTIAL
4B.2.3 = PASS
4B.2.4 = FAIL
4B.2.4.1 = PASS

Do not rewrite any historical result.

## Notes

Precall PASSed on the canonical project interpreter. The new 4B.2.5 remote slot was then consumed exactly once.

Provider rejected the frozen production request before any Terra semantic payload was returned:

OpenAI HTTP 400 invalid_request_error
Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.

The frozen request SHA-256 remained
09d6472e544bc60231c77908e6608ff7ee7b6fd4746317f206301082e21eab53
and included max_tokens=8192. This phase did not repair the request, did not switch to max_completion_tokens, and did not make a second Terra call. Changing that parameter would change the frozen request identity and requires a new explicit authorization.

No JSON body was received. All 10 benchmark cases are therefore MISSING. This is a FAIL under the response-contract / case-coverage rule, not a scored semantic false negative.

Actual cost is UNKNOWN because the provider returned no usage. Unknown is not recorded as zero.

Focused tests after the call, with network blocked: 63 passed, 0 new failures.

Historical 4B.2.4 audits were not overwritten. 4B.2.2 CH016 was not accepted into production cache. book.json was not published. book-generator-1.0.1 remains SUFFICIENT_WITH_SEMANTIC_GATE.

10 cases are an engineering canary, not a statistical model-quality benchmark.

Wait for human review. No second Terra call.
