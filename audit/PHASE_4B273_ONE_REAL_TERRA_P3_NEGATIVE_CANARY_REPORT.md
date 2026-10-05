**PHASE 4B.2.7.3 — ONE REAL TERRA P3 NEGATIVE CANARY**

RESULT = PARTIAL
HISTORICAL 4B.2.7 = PARTIAL
HISTORICAL 4B.2.7.1 = PASS
HISTORICAL 4B.2.7.2 = PASS
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
CASE HANDLE = h02
BENCHMARK ID = 4b22_p3_new_causal
HUMAN LABEL = QUESTIONABLE
LABEL LEAKAGE = 0
CONTRACT = book-semantic-validator-1.1.1-candidate
TRANSPORT = book-semantic-validation-transport-1.1-candidate
REQUEST SHA256 = 5ace261296d808437910f8f9efe247a80daebbb2237bc8af46bda56bf98d7897
REQUEST DETERMINISM = PASS
SDK SERIALIZATION = PASS
CANONICAL HASHES PRE/POST = pre source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958; post source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958
MAX_COMPLETION_TOKENS = 8192
HTTP STATUS = UNKNOWN
FINISH_REASON = stop
RESPONSE CONTENT LENGTH = 1691
INPUT TOKENS = 1692
COMPLETION TOKENS = 5221
REASONING TOKENS = 4595
ACTUAL COST = 0.0660360 USD
JSON PARSE = PASS
CONTRACT VALIDATION = FAIL
CLAIM COVERAGE = FAIL
SPAN VALIDITY = PASS
EVIDENCE VALIDITY = PASS
TERRA GLOBAL VERDICT = UNSUPPORTED
DISPUTED CAUSAL CLAUSE VERDICT = UNSUPPORTED
DISPUTED CAUSAL CLAUSE REASON CODE = INVENTED_CAUSAL_LINK
SUPPORTED CLAIMS REVIEW = PARTIAL
SEMANTIC REVIEW = PARTIAL
DETERMINISTIC REPLAY = PASS
TESTS PASSED / FAILED = 221 / 0
NEW REGRESSIONS = 0
PRODUCTION CACHE = UNCHANGED
book.json = NOT PUBLISHED
READY_FOR_SEMANTIC_GATE_COMPARATIVE_REVIEW = NO
READY_FOR_NEW_REMOTE_TERRA_CALL = NO
READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT = NO
READY_FOR_FULL_REAL_BOOK_GENERATION = NO
NEXT ACTION = HUMAN REVIEW

## Historical status

4B.2.6 = FAIL
4B.2.6.1 = PASS
4B.2.6.2 = PASS
4B.2.7 = PARTIAL (h01 valid JSON, local false-rejection investigation).
4B.2.7.1 = PASS (offline forensics and 1.1.1-candidate).
4B.2.7.2 = PASS (frozen independent P3 negative request, no Terra call).

Do not rewrite any historical result.

## Notes

PARTIAL — usable Terra JSON, but not a semantic PASS.

Terra isolated the disputed clause at offsets 406–465, classified it UNSUPPORTED, and blocked paragraph acceptance (paragraph v=UNSUPPORTED, chapter v=FAIL). Four other claims were SUPPORTED, so this is not an undiscriminating all-QUESTIONABLE dump.

Remaining gaps, recorded and not repaired:

1. Reason codes are outside the frozen catalog. The causal clause used INVENTED_CAUSAL_LINK instead of NEW_CAUSAL_LINK or NEW_IMPLICATION. Other invented codes: NO_EVIDENCE, UNJUSTIFIED_STRENGTHENING, UNSUPPORTED_IMPLICATION, PARTIAL_REFERENCE_EXPANSION.
2. Compact 1.1.1 coverage FAILED on uncovered punctuation spans (93–96 em dash, 124–126 comma, 270–272 semicolon, 404–406 comma). Words, negations, and the because-clause itself were covered. JSON was not repaired.
3. Supported-claims review is PARTIAL. Offline 4B.2.7.2 treated SRC006154 / SRC006156 as supporting nearby clauses that Terra flagged (abuse to your very person; used since the beginning). Those rejections have notes, so they are disagreements, not silent omissions.
4. A relevant catalog reason code is therefore missing even though the causal reservation text is on-target.

A P3 negative PASS is not a ten-case validation.
Contract 1.1.1-candidate is not promoted.
Human QUESTIONABLE label stayed in local evaluation data only.
A global QUESTIONABLE verdict is not a semantic PASS by itself.

A P3 negative PASS is not a ten-case validation.
Contract 1.1.1-candidate is not promoted.
Human QUESTIONABLE label stayed in local evaluation data only.
A global QUESTIONABLE verdict is not a semantic PASS by itself.

STOP. No second Terra call. No Sonnet call. No CH016 regeneration. No 19-chapter run. No 1.1.1 promotion. No cache acceptance. No book.json. No Phase 5. Wait for human review.
