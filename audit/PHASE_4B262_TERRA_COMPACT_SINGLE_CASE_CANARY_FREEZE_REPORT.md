PHASE 4B.2.6.2 — TERRA COMPACT SINGLE-CASE CANARY FREEZE

RESULT = PASS
PROVIDER CALLS = 0
OPENAI HTTP = 0
ANTHROPIC HTTP = 0
CANONICAL PYTHON = C:\TranscriptionAI\.venv\Scripts\python.exe
OPENAI SDK VERSION = 2.43.0
HISTORICAL 4B.2.6 = FAIL
HISTORICAL 4B.2.6.1 = PASS
CONTRACT 1.0 = UNCHANGED
CONTRACT 1.1 CANDIDATE = book-semantic-validator-1.1-candidate FINALIZED_NOT_PROMOTED
SELECTED CASE = h01 / 4b22_p2_supported
SELECTED CASE HUMAN LABEL = SUPPORTED (positive) — audit interne uniquement
BENCHMARK IDENTITY = PASS
LABEL LEAKAGE = 0
SOURCE HASHES PRE/POST = pre source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958; post source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958
SDK SERIALIZATION = PASS
REQUEST SHA256 = 9520a4f3e5ff36ec2957b74e82d492019ff630f764e1413853b19d9b96dec6af
REQUEST DETERMINISM = PASS
MAX_COMPLETION_TOKENS = 8192
REASONING TOKEN TELEMETRY = PASS
JSON_OBJECT SERVER CAPABILITY = UNKNOWN
CONTEXT SAFETY = PASS
ESTIMATED COST = short=0.004356 detailed=0.008196 if_8192=0.1017
TESTS PASSED / FAILED = 199 / 0
NEW REGRESSIONS = 0
PRODUCTION CACHE = UNCHANGED
book.json = NOT PUBLISHED
READY_FOR_SINGLE_CASE_CANARY_HUMAN_REVIEW = YES
READY_FOR_NEW_REMOTE_TERRA_CALL = NO
READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT = NO
READY_FOR_FULL_REAL_BOOK_GENERATION = NO
NEXT ACTION = HUMAN REVIEW

## Notes

4B.2.6 remains FAIL (empty JSON after 8192 completion tokens). 4B.2.6.1 remains PASS (B+C). This phase freezes the compact 1.1-candidate single-case request without calling Terra.

A single-case PASS later must not be read as a ten-case validation.
FakeAI PASS is local orchestration only, not Terra semantic quality.
0/10 in 4B.2.6 remains absence of decisions, not ten misclassifications.
Contract 1.1-candidate is not promoted.

STOP. No Terra call. No Sonnet call. No CH016 regeneration. No 19-chapter run. No cache acceptance. No book.json. Wait for human review and a new explicit remote authorization.
