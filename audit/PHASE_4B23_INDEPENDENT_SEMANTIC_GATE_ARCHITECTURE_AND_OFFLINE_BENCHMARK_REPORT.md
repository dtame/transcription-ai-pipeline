# PHASE 4B.2.3 — INDEPENDENT SEMANTIC GATE ARCHITECTURE + OFFLINE BENCHMARK

## Result

PASS

REAL PROVIDER CALLS =
0

4B.2 STATUS =
FAIL

4B.2.2 STATUS =
PARTIAL

SOURCE MAP UNCHANGED =
YES

EDITORIAL PLAN UNCHANGED =
YES

CLEAN TRANSCRIPT UNCHANGED =
YES

GENERATOR MODEL =
Anthropic / claude-sonnet-5

GENERATOR PROMPT =
book-generator-1.0.1

DETERMINISTIC VALIDATOR =
book-generation-validator-1.0.1

SEMANTIC GATE MODEL =
OpenAI / gpt-5.6-terra

SEMANTIC GATE PROMPT =
book-semantic-validator-1.0

SEMANTIC GATE TRANSPORT =
book-semantic-validation-transport-1.0

SEMANTIC GATE SCHEMA =
9e84248aa5d6fc454b79041085d915ecaa3a13f74f1ce245900b2f1665673689

SEMANTIC VALIDATION GRANULARITY =
CLAIM_LEVEL_AUDIT_WITH_PARAGRAPH_ANCHORING

EVIDENCE SCOPE =
DECLARED_FIRST_PLUS_BOUNDED_SECTION_EVIDENCE

SUPPORTED CLASS =
SUPPORTED

QUESTIONABLE CLASS =
QUESTIONABLE

UNSUPPORTED CLASS =
UNSUPPORTED

NON_SUBSTANTIVE CLASS =
NON_SUBSTANTIVE

QUESTIONABLE ACCEPTED =
NO

UNSUPPORTED ACCEPTED =
NO

CACHE ACCEPTANCE REQUIRES SEMANTIC PASS =
YES

HISTORICAL BENCHMARK CASES =
11

POSITIVE CASES =
6

NEGATIVE CASES =
4

P3 EXPECTED CLASS =
QUESTIONABLE

P3 EXPECTED REASON =
NEW_CAUSAL_LINK / NEW_IMPLICATION

P8 EXPECTED CLASS =
QUESTIONABLE

P8 EXPECTED REASON =
REFERENCE_COMPLETION / REFERENCE_EXPANSION

FUNERAL CASE EXPECTED =
UNSUPPORTED + INVENTED_EXAMPLE

CONNECTIVE CASE EXPECTED =
UNSUPPORTED + NEW_ARGUMENT / NEW_CONCLUSION / NEW_IMPLICATION

FAKEAI TESTS =
PASS

CH016 SEMANTIC REQUEST ESTIMATE =
7483

LARGEST CHAPTER SEMANTIC REQUEST ESTIMATE =
38042

19-CHAPTER SEMANTIC GATE ESTIMATED COST =
1.708446 USD

BOOK-GENERATOR-1.0.1 SUFFICIENCY =
SUFFICIENT_WITH_SEMANTIC_GATE

4B.2.2 CANDIDATE PRODUCTION CACHE =
NOT ACCEPTED

book.json =
NOT PUBLISHED

READY_FOR_ONE_REAL_TERRA_SEMANTIC_GATE_CANARY =
YES

READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT =
NO

READY_FOR_FULL_REAL_BOOK_GENERATION =
NO

NEXT ACTION =
HUMAN REVIEW

## Notes

Zero provider calls. Historical 4B.2 remains FAIL. 4B.2.1 remains PASS. 4B.2.2 remains PARTIAL. No CH016 regeneration. No book-generator-1.0.2. No production cache acceptance. No book.json.

Clean transcript SHA-256=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958.

A paragraph may reference valid IDEA/SRC handles and still contain an unsupported clause. Valid source_refs are necessary but not sufficient evidence of semantic fidelity.

If canonical evidence contains a partial biblical, literary, historical, or other reference, the generator may not complete or expand its content from model knowledge.

A claim may be reasonable, theologically familiar, logically plausible, and stylistically natural, and still be unsupported by canonical evidence.

Gate placement: Sonnet chapter candidate → deterministic BookGenerationValidator → independent semantic gate → production chapter cache acceptance. Deterministic PASS is required before a semantic provider call. Empty paragraph remains validator territory.

Granularity=CLAIM_LEVEL_AUDIT_WITH_PARAGRAPH_ANCHORING. Evidence scope=DECLARED_FIRST_PLUS_BOUNDED_SECTION_EVIDENCE. Declared handles are hints, never proof. Section-bounded evidence is the verification scope. Other chapters cannot rescue a claim unless EditorialPlan authorized reuse.

Terra thinking is unverified; proposed configuration is provider_default with temperature omitted. OpenAIEngine structured output remains json_object. The schema is the local contract.

FakeAI catalog: 8 cases, determinism=True, passed=True.

19-chapter cost status=base_estimate. Long-context threshold modeled=NO. Assumed applied=NO. Previous rough estimate 0.668268 is not frozen. Unknown != zero. Not spent.

book-generator-1.0.1 sufficiency=SUFFICIENT_WITH_SEMANTIC_GATE. Two residual 4B.2.2 QUESTIONABLE paragraphs block cache acceptance. Do not infer a 19-chapter rejection rate from two CH016 samples.

Recommended next: A. Terra benchmark canary on frozen historical cases. Future Terra canary uses frozen historical candidates only. No Sonnet call. Phase 5 is not started.

Focused tests: 24 passed in 1.14s. New failures=0. Network blocked.

Wait for human review.
