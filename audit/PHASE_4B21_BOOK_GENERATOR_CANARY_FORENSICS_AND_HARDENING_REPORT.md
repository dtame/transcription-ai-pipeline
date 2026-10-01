# PHASE 4B.2.1 — BOOK GENERATOR CANARY FORENSICS + HARDENING

## Result

PASS

REAL PROVIDER CALLS = 0

4B.2 HISTORICAL STATUS = FAIL

SOURCE MAP UNCHANGED = YES

EDITORIAL PLAN UNCHANGED = YES

CLEAN TRANSCRIPT UNCHANGED = YES

4B.2 RAW RESPONSE UNCHANGED = YES

4B.2 CANDIDATE UNCHANGED = YES

EMPTY PARAGRAPH HANDLE = p9b

EMPTY PARAGRAPH ROOT CAUSE = SCHEMA_EXPRESSIVENESS_LIMIT + PROVIDER_COMPLIANCE_FAILURE

VALIDATOR CORRECT = YES

CONNECTIVE CLAIM HANDLE = p13

CONNECTIVE CLAIM CLASSIFICATION = SUBSTANTIVE_UNSUPPORTED

CONNECTIVE CLAIM SUPPORTED = NO

INVENTED ILLUSTRATION HANDLE = p8

ILLUSTRATION CLASSIFICATION = INVENTED_EXAMPLE

ILLUSTRATION SOURCE-SUPPORTED = NO

HYDRATION DEFECT = NO

GENERATION GRANULARITY DEFECT = NO

OUTPUT BUDGET DEFECT = NO

THINKING CONFIGURATION DEFECT = NOT_DEMONSTRATED

SELECTED HARDENING = book-generator-1.0.1 + existing hard local validator + hybrid semantic validation strategy

SUCCESSOR PROMPT = book-generator-1.0.1

TRANSPORT = book-generation-transport-1.0

SCHEMA CHANGED = NO

SCHEMA LIMITATION = Anthropic structured-output subset does not permit minLength. Empty string remains schema-legal. Local validator + prompt hardening hold the non-empty invariant.

LOCAL VALIDATOR CHANGED = YES

NEW GRAMMAR CANARY REQUIRED = NO

SEMANTIC VALIDATION STRATEGY = D_HYBRID

FUTURE CH016 REQUEST SHA256 = 3fade89f3bda5a4e008242c28be9babf29c00dec5666a2bcde1900a99d46d071

FUTURE REQUEST DETERMINISM = PASS

FUTURE MODEL = Anthropic / claude-sonnet-5

FUTURE THINKING = disabled

FUTURE MAX_OUTPUT = 16384

FUTURE HYDRATION = SOURCE_MAP_PLUS_TARGETED_TRANSCRIPT_HYDRATION

FUTURE ESTIMATED COST = 0.031204 USD

FAKEAI TESTS = PASS

TOTAL TESTS = 53

NEW FAILURES = 0

book.json = NOT PUBLISHED

READY_FOR_ONE_HARDENED_CH016_CANARY = YES

READY_FOR_PRODUCTION_PREFLIGHT = NO

READY_FOR_FULL_REAL_BOOK_GENERATION = NO

NEXT ACTION = HUMAN REVIEW

## Notes

Zero provider calls. Historical 4B.2 remains FAIL permanently.

Clean transcript: C:/TranscriptionAI/sortie/pastoral_retreat_v2_validation/transcripts/clean/transcript_data.json SHA-256=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958

Historical candidate file SHA-256=6b1a1f2308a88576d38211c32ec569d9a94441cc27936fd0d4c0f3cb7b3d8e76; canonical SHA-256=51635cedf7fee34b34fd80466c2361968494e2e98c15d861682401bddd2aaad5.

Empty paragraph p9b raw text case=""; evidence case=[]. Schema accepted empty `t` because Anthropic structured output cannot express minLength. Local validator correctly rejected it. VALIDATOR_DEFECT=NO.

Connective closer p13 classified SUBSTANTIVE_UNSUPPORTED. The new proposition is not supported by supplied IDEA/EX/REF/UNC/SRC evidence. Provider self-label kind=con is not trusted.

Invented illustration in p8 classified INVENTED_EXAMPLE. Funeral-verse scenario is absent from canonical CH016 evidence. This is not an invented Bible reference.

Historical raw response replayed through the strengthened validator: FAIL. Empty paragraph still FAIL. No silent drop / retroactive PASS.

Successor prompt book-generator-1.0.1 is a narrow hardening of frozen book-generator-1.0. Transport and schema bytes are unchanged. NEW_GRAMMAR_CANARY_REQUIRED=NO.

Semantic validation strategy is HYBRID: BookGenerationValidator for deterministic checks; human review for the next single hardened CH016 canary; future independent OpenAI gpt-5.6-terra chapter-level semantic gate before cache accept. Phase 5 is not started. Estimated Terra 19-chapter gate cost is architecture only (0.668268).

Future CH016 request uses the production builder, language=en, model=claude-sonnet-5, thinking=disabled, max_output=16384, hydration unchanged. SHA-256=3fade89f3bda5a4e008242c28be9babf29c00dec5666a2bcde1900a99d46d071. Determinism=True. Differs from historical 4B.2 request. Cache signature changes with prompt 1.0.1.

book.json is not published. Do not send the future request. Wait for human review.
