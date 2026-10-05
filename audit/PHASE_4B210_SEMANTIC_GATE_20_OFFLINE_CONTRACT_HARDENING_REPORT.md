**PHASE 4B.2.10 — SEMANTIC GATE 2.0 OFFLINE CONTRACT HARDENING**

RESULT = PASS
PROVIDER CALLS = 0
OPENAI HTTP = 0
ANTHROPIC HTTP = 0
HISTORICAL H01 = PARTIAL
HISTORICAL H02 = PARTIAL
HISTORICAL H11 = PARTIAL
CANONICAL PYTHON = C:\TranscriptionAI\.venv\Scripts\python.exe
OPENAI SDK VERSION = 2.43.0
CANONICAL HASHES PRE/POST = pre source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958; post source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958
HISTORICAL CONTRACTS MODIFIED = NO
HISTORICAL LABELS MODIFIED = NO
PRODUCTION PIPELINE MODIFIED = NO
SEMANTIC GATE 2.0 CONTRACT = book-semantic-validator-2.0-candidate
SEMANTIC GATE 2.0 TRANSPORT = book-semantic-validation-transport-2.0-candidate
CONTRACT HARDENING = book-semantic-validator-2.0.1-candidate
UNIT INTEGRITY = PASS
CONTEXT PRESERVATION = PARAGRAPH_ONCE_PLUS_UNIT_TEXTS
SELECTED CANARY = 4b210_h01
HUMAN LABEL = SUPPORTED — audit interne uniquement
LABEL LEAKAGE = PASS
REQUEST SHA256 = d62ee35106f89d34170fb93364ce202b021fd0c60c582248c241cb296008c484
REQUEST DETERMINISM = PASS
SDK SERIALIZATION = PASS
MODEL = gpt-5.6-terra
MAX_COMPLETION_TOKENS = 8192
RETRIES = 0
FALLBACKS = 0
COST ESTIMATE = 0.065272
MAXIMUM COST ESTIMATE = 0.100924
FAKEAI CONTRACT TESTS = PASS
TESTS PASSED / FAILED = 103 / 0
NEW REGRESSIONS = 0
PROVIDER SAFETY = PASS
STRATEGIC STOP RULE = DEFINED
PRODUCTION CACHE = UNCHANGED
book.json = NOT PUBLISHED
READY_FOR_SEMANTIC_GATE_20_HUMAN_REVIEW = YES
READY_FOR_ONE_REAL_TERRA_CANARY = YES
REAL_TERRA_CANARY_AUTHORIZED = NO
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
4B.2.7.7 = PARTIAL
4B.2.8 = PASS
4B.2.9 = PASS

h01 remains PARTIAL. h02 remains PARTIAL. h11 remains PARTIAL.
Do not rewrite any historical result.
FakeAI PASS is local contract and orchestration only, not Terra quality.
Contract 2.0.1-candidate is a hardening of instructions, not a Terra correction.

## Notes

Semantic Gate 2.0-candidate is preserved. 2.0.1-candidate hardens verdict definitions and paraphrase instructions without claiming that historical false rejections are corrected. One h01 request is frozen for a possible later Terra canary. No provider call. Production pipeline and cache are unchanged.

Estimates use configured project rates dated in the catalog. They are not live provider prices.
Reasoning tokens are not assumed to be low. max_completion_tokens does not guarantee a complete answer.
Do not count reasoning tokens twice when they are already included in completion tokens.
2.0-candidate is preserved. 2.0.1-candidate is a new version and is not activated.
Transport 2.0-candidate is not enabled for a real call.

STOP. No Terra call. No Sonnet call. No CH016 regeneration. No 19-chapter run. No Semantic Gate 2.0 promotion. No production pipeline change. No cache acceptance. No book.json. No Phase 5. No Word/PDF. Wait for human review before any real experiment.
