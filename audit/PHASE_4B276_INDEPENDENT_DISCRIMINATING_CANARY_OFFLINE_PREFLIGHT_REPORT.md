PHASE 4B.2.7.6 — INDEPENDENT DISCRIMINATING CANARY OFFLINE PREFLIGHT

RESULT = PASS
PROVIDER CALLS = 0
OPENAI HTTP = 0
ANTHROPIC HTTP = 0
HISTORICAL H01 = PARTIAL
HISTORICAL H02 = PARTIAL
CANONICAL PYTHON = C:\TranscriptionAI\.venv\Scripts\python.exe
OPENAI SDK VERSION = 2.43.0
CANONICAL HASHES PRE/POST = pre source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958; post source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958
SELECTED CANARY ID = 4b276_p4_new_implication
CANARY ORIGIN = SYNTHETIC_VARIANT_OF_4B22_P4_SUPPORTED
CANARY INDEPENDENCE = PASS
TARGET FAILURE FAMILY = NEW_IMPLICATION_AND_UNCERTAINTY_STRENGTHENED
HUMAN REFERENCE LABEL = UNSUPPORTED — audit interne uniquement
LABEL LEAKAGE = 0
CONTRACT = book-semantic-validator-1.1.3-candidate
TRANSPORT = book-semantic-validation-transport-1.1-candidate
REQUEST SHA256 = b3cc1574858acdd5bdd0e223aa136d5058c4eb1deb1495cd9ad312d332e8c30f
REQUEST DETERMINISM = PASS
SDK SERIALIZATION = PASS
MAX_COMPLETION_TOKENS = 8192
INPUT TOKENS ESTIMATE = 2913
SHORT RESPONSE COST ESTIMATE = 0.006786
FULL BUDGET COST ESTIMATE = 0.10413
FAKEAI POSITIVES = 6
FAKEAI NEGATIVES = 4
TESTS PASSED / FAILED = 81 / 0
NEW REGRESSIONS = 0
PRODUCTION CACHE = UNCHANGED
book.json = NOT PUBLISHED
READY_FOR_ONE_REAL_CANARY_HUMAN_REVIEW = YES
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

Do not rewrite any historical result.
h01 remains PARTIAL. h02 remains PARTIAL and is not a PASS.

## Notes

4B.2.7 remains PARTIAL (h01). 4B.2.7.3 remains PARTIAL (h02). This phase freezes an independent synthetic which-means canary from canonical 4b22_p4_supported evidence without calling Terra.

Observed h01 cost remains 0.018812 USD. Observed h02 cost remains 0.066036 USD.
Estimates use configured project rates dated in the catalog. They are not live provider prices.
Reasoning tokens are not assumed to be low. max_completion_tokens does not guarantee a complete answer.
FakeAI PASS is local contract and orchestration only, not proof that Terra will agree.
1.1.3-candidate is not promoted. Frozen historical contracts are unchanged.
The selected paragraph is a documented synthetic variant of 4b22_p4_supported. It is not an authentic citation.

STOP. No Terra call. No Sonnet call. No CH016 regeneration. No 19-chapter run. No contract promotion. No historical benchmark change. No cache acceptance. No book.json. No Phase 5. Wait for human review and a new explicit remote authorization.
