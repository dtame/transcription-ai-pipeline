# PHASE 4B.2 — BOOK GENERATOR ONE REAL SMALL-CHAPTER CANARY

## Result

FAIL

AUTHORIZED PROVIDER CALLS = 1

ACTUAL PROVIDER CALLS = 1

RETRIES = 0

FALLBACKS = 0

TARGET CHAPTER = CH016

SOURCE MAP SHA256 PRE/POST = df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855/df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855

EDITORIAL PLAN SHA256 PRE/POST = 01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440/01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440

CLEAN TRANSCRIPT SHA256 PRE/POST = 1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958/1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958

INPUTS UNCHANGED = YES

CANONICAL LANGUAGE = en

MODEL = Anthropic / claude-sonnet-5

PROMPT = book-generator-1.0

TRANSPORT = book-generation-transport-1.0

SCHEMA RAW / ADAPTED = 1035 / 1128

SCHEMA SHA256 = 075455fdbf18548b3bd2c05b5c7abf35bf43d2c4cecc74f3af6963c540028273

THINKING = disabled

MAX_OUTPUT = 16384

REQUEST SHA256 = 3e1b3ab243eb17ce07186fe38853c54d903470d81391c7540b757245f92744d8

REQUEST DETERMINISM = PASS

CHAPTER SECTIONS EXPECTED = SEC063

CHAPTER IDEAS EXPECTED = IDEA224, IDEA225, IDEA226, IDEA250, IDEA251, IDEA252

HYDRATED SRC COUNT = 35

HYDRATED CHARS = 1177

HTTP / FINISH = 200 / end_turn

REQUEST ID = req_011CfaqRxmb35jVjr2TemSxb

INPUT TOKENS = 6063

OUTPUT TOKENS = 1754

THINKING TOKENS = 0

ELAPSED = 22108 ms

ACTUAL COST = 0.0296660 USD

STRUCTURED PARSE = PASS

TRANSPORT DECODER = PASS

RECONSTRUCTION = PASS

SECTION COVERAGE = PASS

SECTION ORDER = PASS

IDEA COVERAGE = PASS

SILENT IDEA OMISSIONS = 0

UNKNOWN IDEA REFS = 0

UNKNOWN SRC REFS = 0

UNSOURCED SUBSTANTIVE PARAGRAPHS = 1

CONNECTIVE PARAGRAPHS = 4

EDITORIAL LANGUAGE = PASS

LOCAL VALIDATOR = FAIL

PARAGRAPHS = 14

WORDS = 828

QUESTIONABLE SUPPORT PARAGRAPHS = 1

UNSUPPORTED PARAGRAPHS = 1

SOURCE MEANING = FAIL

ORAL-TO-WRITTEN TRANSFORMATION = PASS

AUTHOR VOICE = ACCEPTABLE

INVENTED FACTS = 0

INVENTED ARGUMENTS = 1

INVENTED EXAMPLES = 1

INVENTED REFERENCES = 0

UNCERTAINTY PRESERVATION = PASS

REPETITION CONTROL = PASS

MANUSCRIPT QUALITY = FAIL

DETERMINISTIC REPLAY = PASS

CANDIDATE SHA256 = 51635cedf7fee34b34fd80466c2361968494e2e98c15d861682401bddd2aaad5

book.json = NOT PUBLISHED

READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT = NO

READY_FOR_FULL_REAL_BOOK_GENERATION = NO

NEXT ACTION = HUMAN REVIEW

## Notes

Exactly one Anthropic claude-sonnet-5 call was made. Zero retries. Zero fallbacks.

CH016 remains the smallest production chapter under the frozen 4B.1 measurement (1 section, 6 IDEAs). Request SHA-256 matches the 4B.1 preflight identity. Thinking was requested disabled and no thinking block was returned.

The provider completed normally (HTTP 200, finish=end_turn). Structured parse, transport decode, local reconstruction, section identity/order, IDEA handle coverage, language, and deterministic replay all passed.

The local BookGenerationValidator failed on provider handle p9b: an empty substantive paragraph with no text and no evidence handles. The frozen 4B.1 schema cannot use minLength, so empty `t` is schema-legal. The validator is the correct stop. The empty paragraph was not repaired.

Exhaustive paragraph review of the remaining prose finds source-faithful written-book English for the six assigned IDEAs. One connective closer (p13) advances a new summarizing argument. One invented illustration appears in p8 ("verse quoted at funerals"). No new Bible references, no interpreter/session debris, no book.json publication.

Defect belongs to the empty-paragraph hole in the frozen schema/prompt contract, not to hydration, request identity, or language. Do not regenerate CH016. Do not start the 19-call production sequence. Wait for human review.

Focused and related tests after the call (network blocked): 67 passed, 0 new failures.
