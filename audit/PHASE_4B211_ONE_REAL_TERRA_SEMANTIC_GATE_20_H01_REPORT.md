**PHASE 4B.2.11 — ONE REAL TERRA SEMANTIC GATE 2.0 H01 CANARY**

RESULT = PARTIAL
HISTORICAL H01 = PARTIAL
HISTORICAL H02 = PARTIAL
HISTORICAL H11 = PARTIAL
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
CASE ID = 4b210_h01
HUMAN LABEL = SUPPORTED
LABEL LEAKAGE = 0
CONTRACT = book-semantic-validator-2.0.1-candidate
TRANSPORT = book-semantic-validation-transport-2.0-candidate
REQUEST SHA256 = d62ee35106f89d34170fb93364ce202b021fd0c60c582248c241cb296008c484
REQUEST DETERMINISM = PASS
SDK SERIALIZATION = PASS
CANONICAL HASHES PRE/POST = pre source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958; post source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958
MAX_COMPLETION_TOKENS = 8192
HTTP STATUS = UNKNOWN
FINISH_REASON = stop
RESPONSE CONTENT LENGTH = 469
INPUT TOKENS = 1247
COMPLETION TOKENS = 316
REASONING TOKENS = 136
ACTUAL COST = 0.0062860 USD
JSON PARSE = PASS
CONTRACT VALIDATION = FAIL
UNIT COVERAGE = PASS
EVIDENCE VALIDITY = PASS
TERRA GLOBAL VERDICT = PASS
TARGET PARAPHRASE VERDICT = SUPPORTED
SUPPORTED CLAIMS REVIEW = PASS
SEMANTIC HUMAN REVIEW = PARTIAL
ACCEPTANCE POLICY RESULT = BLOCK
DETERMINISTIC REPLAY = PASS
TESTS PASSED / FAILED = 207 / 0
NEW REGRESSIONS = 0
PRODUCTION PIPELINE = UNCHANGED
PRODUCTION CACHE = UNCHANGED
book.json = NOT PUBLISHED
READY_FOR_SEMANTIC_GATE_20_COMPARATIVE_REVIEW = NO
READY_FOR_NEW_REMOTE_TERRA_CALL = NO
READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT = NO
READY_FOR_FULL_REAL_BOOK_GENERATION = NO
NEXT ACTION = HUMAN REVIEW

## Historical status

h01 remains PARTIAL. h02 remains PARTIAL. h11 remains PARTIAL.
4B.2.10 remains PASS. Do not rewrite any historical result.

## Notes

TARGET_RECOGNIZED_WITH_CONTRACT_OR_COVERAGE_ISSUES

The human SUPPORTED label stayed in local evaluation data only.
Contract 2.0.1-candidate is not promoted.
Semantic Gate 2.0 is not activated in production.
This cost uses configured project rates and is not a provider invoice.

## Semantic result

Terra recognized the historically rejected paraphrase as SUPPORTED.
Unit `u01` contains `that fear can calculate or bargain with`.
Terra did not require the evidence verbs calculate or bargain.
No other supported unit was rejected.
No reservation notes were emitted.
All five units were returned with stable identifiers.

## Unit-by-unit human review

- `u00` "Do not ever be afraid of death." Human SUPPORTED. Terra SUPPORTED via SRC006149. Match.
- `u01` "There is no fixed hour appointed that fear can calculate or bargain with," Human SUPPORTED. Terra SUPPORTED via IDEA224. Match. This is the h01 target. The old Semantic Gate had marked the bargain/calculate clause QUESTIONABLE.
- `u02` "and so fear itself is out of place." Human SUPPORTED. Terra SUPPORTED via IDEA224, SRC006180, SRC006182. Match. Evidence choice is looser than IDEA224 alone but stays inside the supplied set.
- `u03` "If somebody has gone to heaven, that should not produce dread in us." Human SUPPORTED. Terra SUPPORTED via IDEA224, SRC006187. Match.
- `u04` "It should be our joy." Human SUPPORTED. Terra SUPPORTED via IDEA224, SRC006183. Match.

## Contract failure that blocks PASS

The JSON is valid and complete (`finish_reason = stop`), but the 2.0.1 validator refused the payload:

- `sc` used uppercase keys `SUPPORTED` / `QUESTIONABLE` / `UNSUPPORTED` / `NON_SUBSTANTIVE` instead of `supported` / `questionable` / `unsupported` / `non_substantive`.
- Paragraph `pr[0].v` was `PASS`. The contract requires a classification (`SUPPORTED` | `QUESTIONABLE` | `UNSUPPORTED` | `NON_SUBSTANTIVE`) at paragraph level; `PASS` / `REVIEW` / `FAIL` belong only at top-level `v`.

The response was not repaired. Acceptance policy therefore remains BLOCK. Replay of that BLOCK is deterministic.

HTTP STATUS is UNKNOWN because the SDK envelope did not expose a status code. It is not inferred as 200.

## Strategic stop

The central semantic objective of this canary succeeded: the faithful paraphrase is no longer rejected.
There was no substantial false rejection on h01.
A schema mismatch still prevents promotion.

Do not launch a new paid Terra series automatically.
Do not treat this single positive case as validation of h02 or h11.
Do not activate Semantic Gate 2.0 in production.

Human review should decide among offline alternatives, none of which are activated here:

- Tighten 2.0.1 instructions so `sc` keys and paragraph `v` cannot be confused with top-level verdicts.
- Accept a local alias mapping only after an explicit later decision.
- Keep Terra for targeted high-risk propositions rather than full-paragraph JSON.
- Change the split between automatic validation and human review.

STOP. No second Terra call. No Sonnet call. No CH016 regeneration. No other canary. No 19-chapter run. No Semantic Gate 2.0 promotion. No cache acceptance. No book.json. No Phase 5. Wait for human review.
