**PHASE 4B.2.8 — SEMANTIC GATE COMPARATIVE FORENSICS & ARCHITECTURE DESIGN**

RESULT = PASS
PROVIDER CALLS = 0
OPENAI HTTP = 0
ANTHROPIC HTTP = 0
HISTORICAL H01 = PARTIAL
HISTORICAL H02 = PARTIAL
HISTORICAL H11 = PARTIAL
CANONICAL PYTHON = C:\TranscriptionAI\.venv\Scripts\python.exe
CANONICAL HASHES PRE/POST = pre source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958; post source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958
RAW RESPONSES PRESERVED = YES
HISTORICAL LABELS PRESERVED = YES
HISTORICAL CONTRACTS PRESERVED = YES
H01 FALSE REJECTION ANALYSIS = Relative clause stays in its sentence; disagreement is lexical vs entailment
H02 FALSE REJECTION ANALYSIS = Because-clause isolable locally; two stylistic false rejections remain semantic
H11 FALSE REJECTION ANALYSIS = Guarantee isolable; three supported-prefix rejections remain semantic; word-ending gaps would be locally owned
H11 COVERAGE GAPS CLASSIFICATION = SUBSTANTIVE_WORD_ENDINGS_NOT_SEPARATORS
FAILURE TAXONOMY = observed_false_rejections_unknown_codes_word_ending_gaps
ARCHITECTURE A = current_gate_model_owns_structure_and_semantics
ARCHITECTURE B = deterministic_presegmentation_prototype
ARCHITECTURE C = hybrid_two_level_proposed_target
DETERMINISTIC SEGMENTATION FEASIBILITY = CONSERVATIVE_HYBRID_FEASIBLE_OFFLINE
SEGMENTATION PROTOTYPE = CREATED
SEGMENTATION COVERAGE = COMPLETE_ON_H01_H02_H11_OFFLINE
NEGATION/CAUSALITY PRESERVATION = YES
CONTRACT 2.0 PROPOSAL = book-semantic-validator-2.0-proposal
TRANSPORT CHANGES REQUIRED = proposal_only; book-semantic-validation-transport-1.1-candidate reused; not activated
COST ANALYSIS = h01=0.018812 h02=0.066036 h11=0.029556 B_and_C_hypothetical_reasoning_unknown no_provider_spend_here
ARCHITECTURE COMPARISON = matrix_without_numeric_scores
PROPOSED TARGET ARCHITECTURE = C_HYBRID_TWO_LEVEL_WITH_CONSERVATIVE_PRESEGMENTATION
EVIDENCE LEVEL = OBSERVED_PLUS_HYPOTHESIS_NOT_TERRA_VALIDATED
MIGRATION PLAN = six_steps_with_stop_points
FAKEAI POSITIVES = 6
FAKEAI NEGATIVES = 4
TESTS PASSED / FAILED = 107 / 0
NEW REGRESSIONS = 0
PRODUCTION PIPELINE = UNCHANGED
PRODUCTION CACHE = UNCHANGED
book.json = NOT PUBLISHED
READY_FOR_ARCHITECTURE_HUMAN_REVIEW = YES
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
4B.2.7.6 = PASS
4B.2.7.7 = PARTIAL

h01 remains PARTIAL. h02 remains PARTIAL. h11 remains PARTIAL.
Do not rewrite any historical result.
FakeAI PASS is local orchestration only, not Terra quality.

## Investigation

Three real Terra canaries remain PARTIAL. h01 is a documented false rejection of supported paraphrase. h02 correctly blocked invented causality, then failed unknown reason codes and produced two false rejections plus one indeterminate origin claim. h11 correctly blocked the universal guarantee with NEW_CONCLUSION, rejected three historically supported prefixes, and left coverage gaps that are word endings, not separators. Architecture C with conservative presegmentation is proposed because it assigns observed structural failures to local code. It is not Terra-validated and does not automatically correct semantic false rejections. Contract 2.0 is a proposal only. Transport 1.1 is unchanged. No provider call.

h01 replay units = 5
h02 replay units = 8
h11 replay units = 5
Offline replay does not produce new Terra verdicts.

STOP. No Terra call. No Sonnet call. No CH016 regeneration. No 19-chapter run. No contract promotion. No transport replacement. No cache acceptance. No book.json. No Phase 5. Wait for human review.
