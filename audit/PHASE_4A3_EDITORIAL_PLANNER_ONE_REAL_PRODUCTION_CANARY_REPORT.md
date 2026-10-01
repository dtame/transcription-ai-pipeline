# PHASE 4A.3 — EDITORIAL PLANNER ONE REAL PRODUCTION CANARY

## Result

PARTIAL

AUTHORIZED PROVIDER CALLS = 1

ACTUAL PROVIDER CALLS = 1

RETRIES = 0

SOURCE MAP SHA256 PRE = df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855

SOURCE MAP SHA256 POST = df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855

SOURCE MAP UNCHANGED = YES

PROMPT = editorial-planner-1.0

TRANSPORT = editorial-plan-transport-1.0

SCHEMA RAW / ADAPTED = 3661 / 3909

SCHEMA HASH = 1cebcf97ed7fa5cfa4b4758d1eb1451b6770347e9508772e8287228a768ba77e

SCHEMA IDENTITY = MATCH

EXPECTED REQUEST SHA256 = 99ee7e8f4f9a732b52fceab667d9d1fe8b9ce9acedc1e7b1e7c08c1f62b7b734

ACTUAL REQUEST SHA256 = 99ee7e8f4f9a732b52fceab667d9d1fe8b9ce9acedc1e7b1e7c08c1f62b7b734

REQUEST IDENTITY = MATCH

REQUEST CHARS / BYTES = 114042 / 114142

MODEL = claude-opus-5

THINKING MODE = provider_default

MAX_OUTPUT = 65536

CONNECT / READ TIMEOUT = 30.0 / 1800.0

HTTP / STATUS = 200

FINISH = end_turn

REQUEST ID = req_011CfYPb3BxdkpP88S7Me9Md

INPUT TOKENS = 41425

OUTPUT TOKENS = 17791

THINKING TOKENS = 6443

OUTPUT UTILIZATION = 0.271469

ELAPSED = 172016

ACTUAL COST = 0.6519000 USD

A.2 EXPECTED COST = 0.5624

A.2 CONSERVATIVE COST = 0.8373

A.2 HARD COST = 1.2095

STRUCTURED PARSE = PASS

TRANSPORT DECODER = PASS

HANDLE VALIDATION = PASS

CANONICAL RECONSTRUCTION = PASS

CANONICAL CANDIDATE SHA256 = abc87e082878e0281689ecc022ed8b40ca318510fc90d960c31795d6186bd95e

CHAPTERS = 13

SECTIONS = 67

IDEA COVERAGE = 286 / 286

SILENT OMISSIONS = 0

ASSIGNED = 286

DEFERRED = 0

EXCLUDED = 0

REUSED IDEAS = 0

EXTRA SECTION ASSIGNMENTS = 0

UNKNOWN IDEA REFS = 0

UNKNOWN TOPIC REFS = 0

UNKNOWN EXAMPLE REFS = 0

UNKNOWN REFERENCE REFS = 0

UNKNOWN UNCERTAINTY REFS = 0

TRACEABILITY = PASS

INVENTION BOUNDARY = PASS

UNCERTAINTY PRESERVATION = PASS

TITLE REVIEW = PASS

EDITORIAL ANGLE REVIEW = PASS

TARGET READER REVIEW = PASS

BOOK CONCEPT REVIEW = PASS

CHAPTER REVIEW = PASS

SECTION REVIEW = PASS

BALANCE = PASS

MANUSCRIPT LEAKAGE = PASS

EDITORIAL PLAN VALIDATOR = PASS

DETERMINISTIC REPLAY = PASS

SEMANTIC REVIEW = REVIEW_REQUIRED

PUBLICATION_ELIGIBLE = NO

TESTS = 112 passed (9 A.3 including saved-response replay + planner 4A/4A.1/4A.2 + AI structured/contracts/thinking). 0 provider calls during tests.

NEW FAILURES = 0

editorial_plan.json = NOT PUBLISHED

READY_FOR_CONTROLLED_EDITORIAL_PLAN_PUBLICATION = NO

BOOK GENERATOR = NOT STARTED

NEXT ACTION = HUMAN REVIEW

## Notes

One real Anthropic claude-opus-5 call. Request identity MATCHED the frozen 4A.2 payload (SHA-256 99ee7e8f…b734, max_tokens=65536, thinking omitted / provider_default). Historical frozen max_output remains 16384; A.3 applied 65536 only via the A.2 production_settings.replace path.

Actual usage: input 41425 (local estimate 25313, +63.7%; provider-adjusted 52283, −20.8%; A.2 planning 58890, −29.7%). Output 17791 including provider-reported thinking_tokens=6443 inside usage.output_tokens_details (A.2 expected 8670 / conservative 19666). Utilization 17791/65536 = 27.1%. Finish end_turn; not max_tokens. Elapsed 172.016s. Actual cost 0.6519 USD (A.2 expected 0.5624, +15.9%; below conservative 0.8373).

Technical contract: structured parse, transport decoder, handles, canonical reconstruction CH001–CH013 / SEC001–SEC067, 286/286 ASSIGNED, 0 silent omissions, 0 unknown refs, traceability, invention boundary, uncertainty preservation, validator PASS, deterministic replay PASS. Candidate audit-only at audit/real/editorial_planner_4a3/editorial_plan_candidate.json (SHA-256 abc87e08…d95e). editorial_plan.json NOT PUBLISHED. SourceMap hash unchanged.

Semantic REVIEW_REQUIRED (not FAIL): the plan is a faithful French organization of the English SourceMap (inherited identity, Hebrews 2, John 17, offices, practice, testimonies) without inventing substantive content. Human review is required for (1) French editorial language vs SourceMap primary_language=en, (2) working title “Déjà héritiers” is an editorial construct not a final approved title, (3) all 286 IDEAs ASSIGNED with 0 DEFERRED/EXCLUDED. No second provider call. No repair.

WAIT FOR HUMAN REVIEW.
