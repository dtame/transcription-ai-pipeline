**PHASE 4B.2.7.7 — ONE REAL TERRA H11 DISCRIMINATING CANARY**

RESULT = PARTIAL
HISTORICAL H01 = PARTIAL
HISTORICAL H02 = PARTIAL
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
CASE HANDLE = h11
CASE ID = 4b276_p4_new_implication
HUMAN LABEL = UNSUPPORTED
LABEL LEAKAGE = 0
CONTRACT = book-semantic-validator-1.1.3-candidate
TRANSPORT = book-semantic-validation-transport-1.1-candidate
REQUEST SHA256 = b3cc1574858acdd5bdd0e223aa136d5058c4eb1deb1495cd9ad312d332e8c30f
REQUEST DETERMINISM = PASS
SDK SERIALIZATION = PASS
CANONICAL HASHES PRE/POST = pre source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958; post source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958
MAX_COMPLETION_TOKENS = 8192
HTTP STATUS = UNKNOWN
FINISH_REASON = stop
RESPONSE CONTENT LENGTH = 1098
INPUT TOKENS = 2562
COMPLETION TOKENS = 2036
REASONING TOKENS = 1647
ACTUAL COST = 0.0295560 USD
JSON PARSE = PASS
CONTRACT VALIDATION = FAIL
CLAIM COVERAGE = FAIL
SPAN VALIDITY = PASS
EVIDENCE VALIDITY = PASS
TERRA GLOBAL VERDICT = UNSUPPORTED
UNIVERSAL GUARANTEE VERDICT = UNSUPPORTED
UNIVERSAL GUARANTEE REASON CODE = NEW_CONCLUSION
SUPPORTED CLAIMS REVIEW = PARTIAL
SEMANTIC REVIEW = PARTIAL
DETERMINISTIC REPLAY = PASS
TESTS PASSED / FAILED = 200 / 0
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
4B.2.7 = PARTIAL
4B.2.7.1 = PASS
4B.2.7.2 = PASS
4B.2.7.3 = PARTIAL
4B.2.7.4 = PASS
4B.2.7.5 = PASS
4B.2.7.6 = PASS

h01 remains PARTIAL. h02 remains PARTIAL.
Do not rewrite any historical result.

## Notes

PARTIAL because Terra detected and blocked the universal guarantee, but it also
rejected historically supported prefix clauses and left significant coverage
gaps. A blocking global verdict is not a semantic PASS by itself.

Request `chatcmpl-EUFWtC031lMOU0pIbR9RzrXLjcPik`. Finish reason `stop`.
Elapsed 27483 ms. HTTP status UNKNOWN (SDK did not expose a status code).
Cost 0.029556 USD is calculated from configured project rates dated 2026-09-18
(input 2562 × $2/1M, completion 2036 × $12/1M). Reasoning tokens 1647 are
included in completion tokens and were not billed twice. This is not a
provider invoice.

The human UNSUPPORTED label stayed in local evaluation data only.
Contract 1.1.3-candidate is not promoted.

## Claim-by-claim review

Paragraph handle h11. Terra global `v=FAIL`, paragraph `UNSUPPORTED`.
Seven claims. Reason codes stayed inside the closed catalog.

| Span | Human | Terra | Code | Agreement |
|---|---|---|---|---|
| mental technique | SUPPORTED | QUESTIONABLE | EVIDENCE_MISMATCH | no |
| not mind over matter | SUPPORTED | SUPPORTED | — | yes |
| positive thinking | SUPPORTED | UNSUPPORTED | NEW_FACT | no |
| death as gain / lived reality | SUPPORTED | SUPPORTED | — | yes |
| sermon / intellectual idea | SUPPORTED | UNSUPPORTED | INVENTED_EXAMPLE | no |
| substance of one's ending | SUPPORTED | SUPPORTED | — | yes |
| which means every believer is guaranteed a fearless death | UNSUPPORTED | UNSUPPORTED | NEW_CONCLUSION | yes |

The disputed clause occupies [294, 356). Terra claim 6 occupies [291, 353):
it overlaps the guarantee, names the fearless-death conclusion, and blocks
acceptance. The code `NEW_CONCLUSION` is an acceptable catalog neighbor, not
the primary pair `NEW_IMPLICATION` / `UNCERTAINTY_STRENGTHENED`.

Coverage FAIL: uncovered gaps [(137, 139), (177, 179), (232, 234), (289, 291),
(353, 357)]. Several Terra spans end two characters short of the word they
cover (`subject`, `reality`, `aside`, `ending`, `death.`). Spans themselves
are valid half-open intervals. Evidence handles cited are a subset of
IDEA226 / SRC006192 / SRC006193 / SRC006195. SRC006195 was authorized but
unused. No invented handles.

Offline replay of the saved JSON was identical on two local passes.
Regression tests: 200 passed / 0 failed. No new regressions.
Historical h01/h02 reports, labels, and responses were not rewritten.
Canonical SourceMap / EditorialPlan / transcript hashes are unchanged.
Production cache unchanged. book.json not published.

STOP. No second Terra call. No Sonnet call. No CH016 regeneration. No 19-chapter run. No 1.1.3 promotion. No cache acceptance. No book.json. No Phase 5. Wait for human review.
