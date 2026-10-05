**PHASE 4B.2.15 — ONE REAL TERRA SEMANTIC GATE 2.0.2 H11 NEGATIVE CANARY**

RESULT = PARTIAL
AUTHORIZED REMOTE CALLS = 1
ACTUAL REMOTE CALLS = 1
RETRIES = 0
FALLBACKS = 0
SONNET CALLS = 0
CANONICAL PYTHON = C:\TranscriptionAI\.venv\Scripts\python.exe
OPENAI SDK VERSION = 2.43.0
MODEL = gpt-5.6-terra
CASE ID = 4b276_p4_new_implication
CONTRACT = book-semantic-validator-2.0.2-candidate
TRANSPORT = book-semantic-validation-transport-2.0-candidate
REQUEST SHA256 = a02867c0ab31c3ff4bf791dfe6472103c1cb9919a7b01b1101c4ae6f2343a2f1
LABEL LEAKAGE = 0
MAX_COMPLETION_TOKENS = 7766
BUDGET CAP = 0.10 USD
PRECALL MAX COST = 0.09999
ACTUAL CALCULATED COST = 0.008264 USD
HTTP STATUS = UNKNOWN
FINISH_REASON = stop
INPUT TOKENS = 1546
COMPLETION TOKENS = 431
REASONING TOKENS = 195
JSON PARSE = PASS
CONTRACT VALIDATION = PASS
UNIT COVERAGE = PASS
EVIDENCE VALIDITY = PASS
UNIVERSAL GUARANTEE CLASSIFICATION = UNSUPPORTED
SUPPORTED CLAIMS REVIEW = FALSE_REJECTION
PYTHON ACCEPTANCE POLICY = BLOCK
HUMAN SEMANTIC REVIEW = PARTIAL
DETERMINISTIC REPLAY = PASS
TESTS PASSED / FAILED = 160 / 0
NEW REGRESSIONS = 0
CANONICAL HASHES PRE/POST = pre source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958; post source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958
HISTORICAL H01 / H02 / H11 = PARTIAL
HISTORICAL 4B.2.11 = PARTIAL
PRODUCTION PIPELINE = UNCHANGED
PRODUCTION CACHE = UNCHANGED
book.json = NOT PUBLISHED
READY_FOR_ONE_REAL_CHAPTER_EXPERIMENT = NO
READY_FOR_FULL_REAL_BOOK_GENERATION = NO
NEXT ACTION = HUMAN REVIEW

## Historical status

h01 remains PARTIAL. h02 remains PARTIAL. h11 remains PARTIAL.
4B.2.11 remains PARTIAL. 4B.2.12 remains PASS. 4B.2.13 remains PASS.
4B.2.14 remains PASS. 4B.2.7.7 remains PARTIAL.
Do not rewrite any historical result.

## Notes

PARTIAL because Terra correctly blocked the universal guarantee (u04 = UNSUPPORTED) and Python derived BLOCK, but it also rejected two historically supported prefix units (u01, u03). A blocking operational decision is not a semantic PASS by itself.

Request `chatcmpl-EUJ1xPQzkp0LGawdf56i4mf7314dJ`. Finish reason `stop`. Elapsed 6968 ms. HTTP status UNKNOWN (SDK did not expose a status code).
Cost 0.008264 USD is calculated from configured project rates dated 2026-09-18 (input 1546 × $2/1M, completion 431 × $12/1M). Reasoning tokens 195 are included in completion tokens and were not billed twice. This is not a provider invoice. Precall theoretical maximum was 0.09999 USD with max_completion_tokens=7766; 8192 would have exceeded the 0.10 USD cap.

The human UNSUPPORTED label stayed in local evaluation data only.
Contract 2.0.2-candidate is not promoted.
The 4B.2.14 production bridge remains disabled.

## Unit-by-unit review

| Unit | Human | Terra | Codes | Agreement |
|---|---|---|---|---|
| u00 mental technique | SUPPORTED | SUPPORTED | — | yes |
| u01 mind over matter / positive thinking | SUPPORTED | UNSUPPORTED | NEW_ARGUMENT, EVIDENCE_MISMATCH | no |
| u02 death as gain / lived reality | SUPPORTED | SUPPORTED | — | yes |
| u03 sermon / substance of ending | SUPPORTED | UNSUPPORTED | INVENTED_EXAMPLE, REFERENCE_EXPANSION | no |
| u04 every believer guaranteed a fearless death | UNSUPPORTED | UNSUPPORTED | NEW_CONCLUSION, UNCERTAINTY_STRENGTHENED | yes |

u04 occupies the independent IMPLICATIVE_CONNECTIVE unit [294, 357). Terra names the fearless-death guarantee and blocks it. NEW_CONCLUSION / UNCERTAINTY_STRENGTHENED are acceptable catalog neighbors of NEW_IMPLICATION.

u01 and u03 are the same false-rejection family observed on 4B.2.7.7 (positive thinking; sermon / intellectual idea). Terra treats those stylistic expansions as new content rather than faithful paraphrase.

Cited evidence handles are a subset of IDEA226 / SRC006192 / SRC006193 / SRC006195. SRC006195 was authorized but unused. No invented handles. Contract 2.0.2 VALID. Coverage complete. Offline replay identical on two local passes.

Regression tests: 160 passed / 0 failed. No new regressions.
Historical h01/h02/h11 and 4B.2.11 remain PARTIAL. Canonical hashes unchanged.
Production cache unchanged. book.json not published. Authorization consumed. No retry.

STOP. No second Terra call. No Sonnet call. No CH016 regeneration. No other canary. No 19-chapter run. No Semantic Gate 2.0 promotion. No bridge activation. No cache acceptance. No book.json. No Phase 5. Wait for human review.
