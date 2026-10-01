# PHASE 4B.2.2 — BOOK GENERATOR HARDENED CH016 CANARY

## Result

PARTIAL

AUTHORIZED PROVIDER CALLS =
1

ACTUAL PROVIDER CALLS =
1

RETRIES =
0

FALLBACKS =
0

4B.2 HISTORICAL STATUS =
FAIL

SOURCE MAP SHA256 PRE / POST =
df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 / df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855

EDITORIAL PLAN SHA256 PRE / POST =
01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 / 01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440

CLEAN TRANSCRIPT SHA256 PRE / POST =
1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958 / 1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958

INPUTS UNCHANGED =
YES

TARGET =
CH016

CANONICAL LANGUAGE =
en

MODEL =
Anthropic / claude-sonnet-5

PROMPT =
book-generator-1.0.1

VALIDATOR =
book-generation-validator-1.0.1

TRANSPORT =
book-generation-transport-1.0

SCHEMA CHANGED =
NO

SCHEMA RAW / ADAPTED =
1035 / 1128

SCHEMA SHA256 =
075455fdbf18548b3bd2c05b5c7abf35bf43d2c4cecc74f3af6963c540028273

THINKING =
disabled

MAX_OUTPUT =
16384

EXPECTED REQUEST SHA256 =
3fade89f3bda5a4e008242c28be9babf29c00dec5666a2bcde1900a99d46d071

ACTUAL REQUEST SHA256 =
3fade89f3bda5a4e008242c28be9babf29c00dec5666a2bcde1900a99d46d071

REQUEST IDENTITY =
MATCH

REQUEST DETERMINISM =
PASS

CACHE SIGNATURE =
23588669ee551e402a030b0987ef3f94a76c5f6c64bdcdbc7f14a91f3f4c4578

SECTIONS EXPECTED =
['SEC063']

IDEAS EXPECTED =
['IDEA224', 'IDEA225', 'IDEA226', 'IDEA250', 'IDEA251', 'IDEA252']

HYDRATED SRC =
35

CONTEXT SAFETY =
PASS

ESTIMATED COST =
0.038092 USD (production estimator; 4B.2.1 reference 0.031204 USD; estimate only)

HTTP / FINISH =
200 / end_turn

REQUEST ID =
req_011CfatMh6WSVme4Zq9oyUCn

INPUT TOKENS =
6626

OUTPUT TOKENS =
1292

THINKING TOKENS =
0

ELAPSED =
14530

ACTUAL COST =
0.0261720 USD

STRUCTURED PARSE =
PASS

TRANSPORT DECODER =
PASS

RECONSTRUCTION =
PASS

LOCAL VALIDATOR =
PASS

SECTION COVERAGE =
PASS

SECTION ORDER =
PASS

IDEA COVERAGE =
PASS

SILENT IDEA OMISSIONS =
0

UNKNOWN IDEA REFS =
0

UNKNOWN SRC REFS =
0

EMPTY PARAGRAPHS =
0

WHITESPACE PARAGRAPHS =
0

UNSOURCED SUBSTANTIVE PARAGRAPHS =
0

CONNECTIVE PARAGRAPHS =
1

UNSUPPORTED CONNECTIVE CLAIMS =
0

EXAMPLE-LIKE ELEMENTS =
3

INVENTED EXAMPLES =
0

INVENTED REFERENCES =
0

QUESTIONABLE PARAGRAPHS =
2

UNSUPPORTED PARAGRAPHS =
0

WEAKLY REPRESENTED IDEAS =
0

MISSING IDEAS =
0

EDITORIAL LANGUAGE =
PASS

SOURCE MEANING =
REVIEW

ORAL-TO-WRITTEN =
PASS

AUTHOR VOICE =
ACCEPTABLE

UNCERTAINTY =
PASS

REPETITION CONTROL =
PASS

MANUSCRIPT QUALITY =
PASS

DETERMINISTIC REPLAY =
PASS

CANDIDATE CANONICAL SHA256 =
e218bea95aaa46f45de66d3532da28fc05807eb9a436bf2e22fe6e9daaa8147c

CANDIDATE FILE SHA256 =
4c0bd8aaa7b8ed760ea48b34877581d8822272daed6b18388386f8fa94aa87e9

PARAGRAPHS =
8

WORDS =
542

book.json =
NOT PUBLISHED

PRODUCTION CACHE =
NOT ACCEPTED

READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT =
NO

READY_FOR_INDEPENDENT_SEMANTIC_GATE_DESIGN =
YES

READY_FOR_FULL_REAL_BOOK_GENERATION =
NO

NEXT ACTION =
HUMAN REVIEW

TESTS =
111 passed / 0 new failures

## Notes

Exactly one Anthropic Sonnet 5 call. Zero retries. Zero fallbacks. Historical 4B.2 remains FAIL permanently. 4B.2 raw response, candidate, and 4B.2.1 audits were not mutated.

Request rebuilt twice through the production path with prompt book-generator-1.0.1. SHA-256 MATCH to the frozen 4B.2.1 future request. Differs from historical 4B.2 request 3e1b3ab243eb17ce07186fe38853c54d903470d81391c7540b757245f92744d8. Cache signature 1.0.1 = 23588669ee551e402a030b0987ef3f94a76c5f6c64bdcdbc7f14a91f3f4c4578. A 1.0 historical result does not satisfy a 1.0.1 lookup. Evidence SHA-256 unchanged: bc15f06b05b1160aed413720f52c104cbb63cf4c98f07ce3fb8e8d2d732a0e93. Hydration = SOURCE_MAP_PLUS_TARGETED_TRANSCRIPT_HYDRATION, 35 SRC, whole transcript not sent.

Provider: HTTP 200, finish=end_turn, thinking tokens=0, thinking blocks=NO. Structured parse PASS. Transport decode PASS. Reconstruction PASS. Local validator 1.0.1 PASS. Empty paragraph p9b did not recur. Invented funeral illustration did not recur. Unsupported connective closer p13 did not recur.

Exhaustive human paragraph review of all 8 paragraphs:

- p1 connective opener = CONNECTIVE_NON_SUBSTANTIVE. Continuity question only.
- p2 IDEA224 = SUPPORTED.
- p3 IDEA225 = QUESTIONABLE. Core abuse / devil's old unchanged strategy is supported. The clause "because it still works wherever it is not resisted by truth" is a new causal implication.
- p4 IDEA226 = SUPPORTED.
- p5 IDEA250 = SUPPORTED / CLEARLY_REPRESENTED. Automated first-pass weakly-represented flag was a lexical false negative.
- p6 IDEA251 + REF051/REF056 = SUPPORTED.
- p7 IDEA252 = SUPPORTED source testimony. Not an invented example.
- p8 REF050 closer = QUESTIONABLE. "1 Corinthians 15" is supplied. "the sting long since removed from death" completes partial REF050 with unsourced 1 Cor 15:55-57 wording.

Clean PASS requires QUESTIONABLE = 0. Result is therefore PARTIAL, not FAIL. Severity is residual semantic expansion inside an otherwise faithful chapter. Do not regenerate CH016 automatically. Investigate whether prompt 1.0.1 is sufficient before any further provider call.

The hybrid strategy is confirmed: deterministic validator PASSed while human review still found two QUESTIONABLE sentences. That is why an independent semantic gate remains necessary before production cache acceptance. This candidate is AUDIT_ONLY. It is not a VALIDATED_AUDIT_CANDIDATE and must not be promoted.

book.json not published. Production cache not accepted. Terra not called. No other chapter generated. No 19-call rollout. Wait for human review.
