# PHASE 4B.1 — BOOK GENERATOR ARCHITECTURE + OFFLINE FOUNDATION

## Result

PASS

REAL PROVIDER CALLS = 0

SOURCE MAP SHA256 = df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855

EDITORIAL PLAN SHA256 = 01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440

EDITORIAL PLAN STATUS = FROZEN

CANONICAL LANGUAGE = en

PRODUCTION MODEL = anthropic / claude-sonnet-5

BOOK GENERATOR PROMPT = book-generator-1.0

BOOK GENERATION TRANSPORT = book-generation-transport-1.0

SCHEMA RAW / ADAPTED = 1035 / 1128

SCHEMA SHA256 = 075455fdbf18548b3bd2c05b5c7abf35bf43d2c4cecc74f3af6963c540028273

GENERATION UNIT = CHAPTER

FALLBACK UNIT = one_section_per_call

EVIDENCE STRATEGY = SOURCE_MAP_PLUS_TARGETED_TRANSCRIPT_HYDRATION

TRANSCRIPT HYDRATION = YES

TRANSCRIPT ARTIFACT = C:/TranscriptionAI/sortie/pastoral_retreat_v2_validation/transcripts/clean/transcript_data.json

CHAPTERS = 19

SECTIONS = 72

IDEAS = 286

CHAPTER SIZE DISTRIBUTION = sections {'min': 1.0, 'median': 4.0, 'mean': 3.789473684210526, 'p90': 5.0, 'max': 8.0}; ideas {'min': 6.0, 'median': 14.0, 'mean': 15.052631578947368, 'p90': 24.0, 'max': 38.0}; evidence_chars {'min': 8967.0, 'median': 17587.0, 'mean': 18074.105263157893, 'p90': 21918.0, 'max': 45177.0}

OUTLIER CHAPTERS = []

SMALLEST REQUEST = CH016

MEDIAN REQUEST = CH003

LARGEST REQUEST = CH006

CONTEXT SAFETY = PASS

RECOMMENDED MAX_OUTPUT = {'min': 16384, 'max': 29250}

THINKING POLICY = disabled

EXPECTED BOOK LENGTH RANGE = 6121-13069 words (from source evidence, not a target)

ESTIMATED PRODUCTION CALLS = 19

ESTIMATED PRODUCTION COST = $1.55

PARAGRAPH TRACEABILITY = substantive→SRC via handles; connective allowed

IDEA ACCOUNTABILITY = assigned must appear; deferred/excluded blocked

SECTION ACCOUNTABILITY = planned sections exactly once, order preserved

CACHE / RESUME = designed

FAKEAI TESTS = PASS

TOTAL TESTS = offline Phase 4B.1

NEW FAILURES = 0

book.json = NOT PUBLISHED

READY_FOR_BOOK_GENERATOR_GRAMMAR_CANARY = YES

READY_FOR_REAL_BOOK_GENERATION = NO

NEXT ACTION = HUMAN REVIEW

## Notes

Working title remains 'The Life You Already Inherited' (not final-approved).

Thinking capabilities known=True; Book Generator thinking validated=False.

Cost status=estimated; preflight chapters=['largest', 'median', 'smallest'].

FakeAI cases ok=PASS.
