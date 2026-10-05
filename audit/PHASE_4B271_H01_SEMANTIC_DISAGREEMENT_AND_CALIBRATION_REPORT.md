PHASE 4B.2.7.1 — H01 SEMANTIC DISAGREEMENT FORENSICS

RESULT = PASS
PROVIDER CALLS = 0
OPENAI HTTP = 0
ANTHROPIC HTTP = 0
HISTORICAL 4B.2.7 = PARTIAL
CANONICAL HASHES PRE/POST = pre source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958; post source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958
H01 HUMAN LABEL = SUPPORTED
H01 TERRA VERDICT = QUESTIONABLE
DISPUTED CLAUSE = that fear can calculate or bargain with
EVIDENCE INVENTORY = COMPLETE
SRC006180 RELEVANCE = available_not_cited_not_decisive_for_bargain
SEMANTIC FINDING = A — FALSE_REJECTION_SUPPORTED_BY_EVIDENCE
HUMAN LABEL MODIFIED = NO
HISTORICAL CONTRACTS MODIFIED = NO
SPAN SEPARATOR FINDING = 140-141 and 209-210 are sentence-final periods, not spaces
CALIBRATION REQUIRED = YES
CANDIDATE VERSION = book-semantic-validator-1.1.1-candidate
FAKEAI TESTS = PASS
REGRESSION TESTS = 89 / 0
NEW REGRESSIONS = 0
SOURCE HASHES UNCHANGED = YES
PRODUCTION CACHE = UNCHANGED
book.json = NOT PUBLISHED
READY_FOR_NEXT_CANARY_DESIGN_REVIEW = YES
READY_FOR_NEW_REMOTE_TERRA_CALL = NO
READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT = NO
READY_FOR_FULL_REAL_BOOK_GENERATION = NO
NEXT ACTION = HUMAN REVIEW

## Historical status

4B.2.4 = FAIL
4B.2.4.1 = PASS
4B.2.5 = FAIL
4B.2.5.1 = PASS
4B.2.6 = FAIL
4B.2.6.1 = PASS
4B.2.6.2 = PASS
4B.2.7 = PARTIAL

Do not rewrite any historical result.

## Investigation

Terra's QUESTIONABLE on 'bargain with' is a lexical over-read of a stylistic restatement of IDEA224 'no set time'. SRC006180 observes visible fear and does not supply bargaining. Coverage gaps are the periods after already-covered sentences. 1.1.1-candidate clarifies entailment versus lexicon without overfitting h01. Frozen 1.0 and 1.1-candidate are unchanged. No provider call.

Clause finding = FALSE_REJECTION_SUPPORTED_BY_EVIDENCE
SRC006180 cited by Terra = False
SRC006180 decisive for bargain = False
Span finding = The recorded 4B.2.7 intervals 140-141 and 209-210 are the sentence-final periods after already-covered clauses, not the following spaces. uncovered_spans() already ignores whitespace. It does not ignore those periods.
1.1.1 prompt sha256 = 4c280308ad70c850ff006c8f251e73696cee3b3afd55ca594df037a6756582ca
Transport 1.1.1 was not created; schema 1.1-candidate is reused.
FakeAI PASS is local orchestration only, not proof that Terra will follow 1.1.1.

STOP. No Terra call. No Sonnet call. No CH016 regeneration. No 19-chapter run. No contract promotion. No label change. No cache acceptance. No book.json. Wait for human review.
