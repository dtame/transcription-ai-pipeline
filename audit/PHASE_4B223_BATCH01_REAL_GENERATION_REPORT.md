**PHASE 4B.2.23 — BATCH-01 REAL GENERATION**

RESULT = PARTIAL
AUTHORIZATION SCOPE = BOOK_GENERATION_BATCH_01_CH001_CH004_ONE_SHOT_PER_CHAPTER
BATCH = BATCH-01
CHAPTERS AUTHORIZED = CH001, CH002, CH003, CH004
CHAPTERS ATTEMPTED = CH001, CH002
CHAPTERS GENERATED = CH001
CHAPTERS NOT GENERATED = CH002, CH003, CH004
PROVIDER CALLS = 2
ANTHROPIC HTTP = 2
OPENAI HTTP = 0
MODEL = anthropic/claude-sonnet-5
PROMPT = book-generator-faithful-restatement-1.1-candidate
PROMPT HASH = e39084dc9ed3b048bfdaa2e112b380d15957085eeb613dd74c97a32b880cec50
AUTHORIZED GLOBAL CAP = 0.66 USD
PREFLIGHT MAX COST = 0.58299
ACTUAL COST BY CHAPTER = CH001 0.035854 USD; CH002 0.039430 USD; CH003 n/a; CH004 n/a
ACTUAL TOTAL COST = 0.075284 USD
RESERVED / UNCERTAIN COST = 0.0
REMAINING BUDGET = 0.584716 USD
RETRIES = 0
FALLBACKS = 0
STRUCTURAL VALIDATION BY CHAPTER = CH001 PASS; CH002 FAIL (empty paragraph SEC006.p4 / P000008); CH003 not called; CH004 not called
IDEA COVERAGE BY CHAPTER = CH001 12/12 traced; CH002 15/15 traced; CH003 n/a; CH004 n/a
SRC VALIDATION BY CHAPTER = CH001 no invalid SRC; CH002 no invalid SRC
EX / REF TRACEABILITY = CH001 EX001 EX002 REF001 REF003 present_and_traced; CH002 REF002 handle absent (not treated as omission); UNC001 UNC003 traced
AUTHORIAL VOICE REVIEW = CH001 first and second person observed, no conference-report frame; CH002 first and second person observed, no conference-report frame
POTENTIAL SUBSTANTIVE ISSUES = regex STRENGTHENED_CLAIM on both attempted chapters; not established as blocking. CH002 also contains a strong heresy/antichrist attribution and a counterfactual about Adam's intercession, reserved for human review.
CANONICAL HASHES PRE/POST = pre source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958; post source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958
CH012 IMMUTABLE = YES
CH018 IMMUTABLE = YES
PRODUCTION CACHE = UNCHANGED
SEMANTIC CERTIFICATION = NOT PERFORMED
HUMAN EDITORIAL ACCEPTANCE = PENDING
book.json = NOT PUBLISHED
READY_FOR_HUMAN_REVIEW = YES
READY_FOR_BATCH02 = NO
NEXT ACTION = HUMAN EDITORIAL REVIEW OF CH001. DECIDE WHETHER CH002'S EMPTY-PARAGRAPH FAILURE IS ACCEPTABLE TO RE-AUTHORIZE AS A DISTINCT ONE-SHOT, OR TO REJECT. DO NOT LAUNCH BATCH-02. DO NOT GENERATE CH003 OR CH004. DO NOT RETRY WITHOUT A NEW EXPLICIT AUTHORIZATION. DO NOT SPEND THE REMAINING 0.584716 USD.

## Chapter table

| Chapter | Status | Cost | Tokens in/out | Structural | IDEA missing | SRC invalid | Editorial | Notes |
|---|---|---|---|---|---|---|---|---|
| CH001 | GENERATED | 0.035854 USD | 9132 / 1759 | PASS | none | none | REVIEW_RECOMMENDED | Candidate written. Human acceptance pending. |
| CH002 | INVALID_CONTRACT | 0.039430 USD | 9815 / 1980 | FAIL | none | none | REVIEW_RECOMMENDED | Empty connective paragraph P000008 in SEC006. Call consumed. No retry. |
| CH003 | NOT_STARTED | n/a | n/a | n/a | n/a | n/a | n/a | No provider call. Preflight only. |
| CH004 | NOT_STARTED | n/a | n/a | n/a | n/a | n/a | n/a | No provider call. Preflight only. |

## Why the lot stopped

CH002 returned valid JSON, the four expected sections, and all fifteen planned IDEA handles in `paras[].e`. The book-generation contract still failed because SEC006 contained an empty connective paragraph (`P000008`, provider handle `p8`, `text=""`). That is a blocking structural error. The lot stopped before CH003. The CH002 lock is `FAILED` and consumed. Remaining budget is not authorization for another call.

CH003 and CH004 locks remain `PREFLIGHT_VALIDATED` and were never reserved. No invented provider responses were written for them.

## CH001 editorial reading (offline, not a certificate)

Candidate: `audit/real/book_generation_4b223_batch01/chapters/CH001/chapter_candidate.md`

The chapter is readable and uses first person for personal anecdotes (night eating, the daughter and meat, the grandmother and the clay pot) and second person for address. No conference-report frame was detected.

EX001, EX002, REF001 (1 Timothy 4:8) and REF003 (Romans 14:23) are present in the prose and traced. All twelve planned IDEA handles are in `paras[].e`. No invalid SRC.

Observations for the human reviewer, not repaired automatically:

- The sentence "You only did not accept it there." is awkward and may be an oral residue.
- "Faith is everything" and "The only thing accepted in the presence of God is Christ." may be slightly more absolute than the source. The deterministic regex also flagged "never" in the grandmother anecdote ("never cooked in an iron pot"), which is not a strengthened theological claim.
- Identifier coverage is not proof that every nuance of IDEA001–IDEA024 was restated.

CH001 is ready for human editorial acceptance or rejection. It is not published.

## CH002 notes (failed contract; raw candidate preserved)

Candidate prose exists at `audit/real/book_generation_4b223_batch01/chapters/CH002/chapter_candidate.md`. The markdown renderer omitted the empty paragraph, so the readable file looks continuous. The JSON still contains the empty `P000008`.

All fifteen IDEA handles are traced. REF002 has no handle in `paras[].e`; flesh-and-bone teaching is present in the opening section. Per the CH018 lesson, a missing REF handle is not treated as a proven omission.

Human-review flags in the preserved prose, not used to justify a retry:

- "I say plainly: that teaching is antichrist, and it is heresy."
- "And God would have forgiven the wife, had Adam interceded."
- UNC001 / UNC003 are traced around the density of the eternity-chain teaching.

Do not treat this chapter as generated for acceptance. Do not retry it unless the user issues a new one-shot authorization.

## Budget

Live preflight theoretical maximum for the four chapters: 0.58299 USD, under the 0.66 USD cap.

| Chapter | Preflight max | Actual |
|---|---|---|
| CH001 | 0.120924 | 0.035854 |
| CH002 | 0.144332 | 0.039430 |
| CH003 | 0.140364 | not called |
| CH004 | 0.177370 | not called |
| Lot | 0.582990 | 0.075284 |

Thinking tokens: 0. Unknown was not treated as zero. The unspent 0.584716 USD is not a new authorization.

## Integrity

- Canonical SourceMap, EditorialPlan, and clean transcript hashes match before and after.
- CH012 accepted markdown and JSON hashes unchanged.
- CH018 accepted markdown and JSON hashes unchanged.
- Production cache module unchanged.
- `book.json` absent.
- Prompt 1.1 remained isolated and unregistered.
- Historical prompts were not used.
- OpenAI HTTP = 0. Terra calls = 0.

A deterministic offline control does not certify semantic fidelity.
Do not treat identifier coverage as content coverage.
BATCH-01 is not accepted until an explicit human decision.

Canonical Python = C:\TranscriptionAI\.venv\Scripts\python.exe
Phase = 4B.2.23
Stop reason = INVALID_CONTRACT (CH002 empty paragraph)

## Stop

STOP. Do not launch BATCH-02. Do not generate the remaining 13 chapters.
Do not retry CH002. Do not spend the remaining budget.
No Terra call. No book.json. No DOCX/PDF.
Wait for human editorial review of CH001 and an explicit decision on CH002.
