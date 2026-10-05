**PHASE 4B.2.7.4 — OFFLINE SEMANTIC GATE CONSOLIDATION**

RESULT = PASS
PROVIDER CALLS = 0
OPENAI HTTP = 0
ANTHROPIC HTTP = 0
HISTORICAL H01 = PARTIAL
HISTORICAL H02 = PARTIAL
CANONICAL PYTHON = C:\TranscriptionAI\.venv\Scripts\python.exe
SOURCE HASHES PRE/POST = pre source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958; post source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958
H02 CLAIMS REVIEWED = 11
H02 FALSE REJECTIONS = 2
H02 JUSTIFIED RESERVATIONS = 4
H02 INDETERMINATE CLAIMS = 1
REASON CODE POLICY = CLOSED_CATALOG_STRICT_COMPLIANCE
UNKNOWN CODES HANDLING = COMPLIANCE_FAIL_NO_SILENT_ACCEPTANCE
PUNCTUATION COVERAGE = ADMISSIBLE_SEPARATORS_ALLOWED
SUBSTANTIVE COVERAGE = WORDS_AND_CONNECTIVES_MANDATORY
CONTRACT CANDIDATE = book-semantic-validator-1.1.2-candidate
TRANSPORT = book-semantic-validation-transport-1.1-candidate
HISTORICAL CONTRACTS MODIFIED = NO
H01 REPLAY = json=PASS 1.1.1=PASS 1.1.2=FAIL
H02 REPLAY = json=PASS 1.1.1=FAIL 1.1.2=FAIL
FAKEAI POSITIVES = 6
FAKEAI NEGATIVES = 4
TESTS PASSED / FAILED = 109 / 0
NEW REGRESSIONS = 0
COST ANALYSIS = h01=0.018812 h02=0.066036 input_similar completion_and_reasoning_higher_on_h02 no_single_factor_claimed no_provider_spend_here
PRODUCTION CACHE = UNCHANGED
book.json = NOT PUBLISHED
READY_FOR_NEXT_CANARY_DESIGN_REVIEW = YES
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

Do not rewrite any historical result.
h01 remains PARTIAL. h02 remains PARTIAL and is not a PASS.

## Investigation

h01 remains a documented false rejection of supported paraphrase. h02 correctly isolated and blocked the invented because-clause, then failed contract compliance on unknown reason codes and separator coverage. Offline review finds two neighboring false rejections (very person; since the beginning), several justified reservations, and one indeterminate origin-framing claim. 1.1.2-candidate lists the closed catalog, requires reservation codes, and generalizes admissible separator coverage. Frozen 1.0 / 1.1 / 1.1.1 are unchanged. Transport 1.1-candidate is reused. Replays are deterministic and do not rewrite historical verdicts. No provider call.

H02 causal clause isolated = True
H02 causal clause blocked = True
H01 1.1.2 replay status = FAIL
H02 1.1.2 replay status = FAIL
A replay difference is not proof that Terra would emit a 1.1.2-conformant answer.
FakeAI PASS is local orchestration only.
1.1.2-candidate is not promoted.

STOP. No Terra call. No Sonnet call. No CH016 regeneration. No 19-chapter run. No contract promotion. No label change. No cache acceptance. No book.json. No Phase 5. Wait for human review.
