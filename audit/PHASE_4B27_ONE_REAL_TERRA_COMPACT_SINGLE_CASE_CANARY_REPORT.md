**PHASE 4B.2.7 — ONE REAL TERRA COMPACT SINGLE-CASE CANARY**

RESULT = PARTIAL
HISTORICAL 4B.2.6 = FAIL
HISTORICAL 4B.2.6.1 = PASS
HISTORICAL 4B.2.6.2 = PASS
AUTHORIZED REMOTE INVOCATIONS = 1
EXECUTION ATTEMPTS = 1
REMOTE INVOCATIONS = 1
HTTP REQUESTS = 1
PROVIDER RESPONSES = 1
RETRIES = 0
FALLBACKS = 0
SONNET CALLS = 0
CANONICAL PYTHON = C:\TranscriptionAI\.venv\Scripts\python.exe
OPENAI SDK VERSION = 2.43.0
MODEL = gpt-5.6-terra
ENDPOINT = chat.completions
CONTRACT = 1.1-candidate
SELECTED CASE = h01 / 4b22_p2_supported
BENCHMARK IDENTITY = PASS
LABEL LEAKAGE = 0
SOURCE HASHES PRE/POST = pre source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958; post source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958
REQUEST SHA256 = 9520a4f3e5ff36ec2957b74e82d492019ff630f764e1413853b19d9b96dec6af
REQUEST DETERMINISM = PASS
SDK SERIALIZATION = PASS
MAX_COMPLETION_TOKENS = 8192
JSON_OBJECT = observed
HTTP STATUS = —
FINISH_REASON = stop
RESPONSE CONTENT LENGTH = 772
INPUT TOKENS = 1654
COMPLETION TOKENS = 1292
REASONING TOKENS = 985
ACTUAL COST = 0.0188120 USD
JSON PARSE = PASS
CONTRACT VALIDATION = FAIL
CLAIM COVERAGE = FAIL
EVIDENCE/SPAN VALIDITY = PASS
TERRA VERDICT = QUESTIONABLE
HUMAN VERDICT = SUPPORTED
SEMANTIC REVIEW = POTENTIAL_FALSE_REJECTION
DETERMINISTIC REPLAY = PASS
TESTS PASSED / FAILED = 217 / 0
NEW REGRESSIONS = 0
PRODUCTION CACHE = UNCHANGED
book.json = NOT PUBLISHED
READY_FOR_NEGATIVE_CASE_CANARY_DESIGN = NO
READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT = NO
READY_FOR_FULL_REAL_BOOK_GENERATION = NO
NEXT ACTION = HUMAN REVIEW

## Historical status

4B.2.4 = FAIL
4B.2.4.1 = PASS
4B.2.5 = FAIL
4B.2.5.1 = PASS
4B.2.6 = FAIL (8 192 completion tokens, empty JSON).
4B.2.6.1 = PASS
4B.2.6.2 = PASS (compact single-case freeze, no provider call).

Do not rewrite any historical result.

## Notes

Usable compact JSON after one Terra call (finish_reason=stop). Terra paragraph verdict QUESTIONABLE vs local human SUPPORTED: the clause about fear calculating or bargaining was marked QUESTIONABLE because bargaining was judged unsourced. That is a potential false rejection on a positive case. Two coverage gaps are the 1-character spaces after sentence periods (offsets 140-141 and 209-210), not missing substantive clauses. SRC006180 was supplied but not cited. Reasoning tokens were reported as 985. No retry. Raw evidence was not repaired. Contract 1.1-candidate is not promoted.

A single-case PASS is not a ten-case validation.
Contract 1.1-candidate is not promoted.
Human SUPPORTED label stayed in local evaluation data only.

STOP. No second Terra call. No Sonnet call. No CH016 regeneration. No 19-chapter run. No cache acceptance. No book.json. No Phase 5. Wait for human review.
