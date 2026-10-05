**PHASE 4B.2.20 — CONTROLLED SCALE-UP PREPARATION & FIRST-CHAPTER READINESS**

RESULT = PASS
PROVIDER CALLS = 0
ANTHROPIC HTTP = 0
OPENAI HTTP = 0
CANONICAL HASHES PRE/POST = pre source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958; post source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958
CH012 IMMUTABLE = YES
REMAINING CHAPTERS = 18
TOTAL REMAINING SECTIONS = 68
TOTAL REMAINING IDEAS = 275
FIRST CHAPTER SELECTED = CH018 — Testimonies of Resurrection
FIRST CHAPTER SECTIONS = 4
FIRST CHAPTER IDEAS = 11
PROMPT 1.1 AVAILABLE = YES
PROMPT 1.1 ISOLATED = YES
GENERATION CONTRACT COMPATIBLE = YES
FIRST CHAPTER SOURCE CONTEXT READY = YES
ESTIMATED FIRST CHAPTER COST = expected 0.048528 USD; calculable maximum 0.113538 USD; authorized 0 USD
ESTIMATED 18-CHAPTER GENERATION COST = low 0.811943 / central 1.063124 / high 2.625794 USD; complete UNKNOWN
VALIDATION COST = UNKNOWN; Terra analog 1.72865 USD (hypothesis, not complete)
AUTHORIZED SPEND = 0 USD
HARD STOP TESTS = PASS
OFFLINE TESTS PASSED / FAILED = 34 / 0
PRODUCTION PIPELINE MODIFIED = NO
PRODUCTION CACHE = UNCHANGED
SEMANTIC GATE PROMOTED = NO
book.json = NOT PUBLISHED
READY_FOR_FIRST_REAL_CHAPTER = YES
READY_FOR_18_CHAPTER_RUN = NO
NEXT ACTION = HUMAN DECISION ON A DISTINCT ONE-CHAPTER AUTHORIZATION FOR THE SELECTED FIRST REMAINING CHAPTER. DO NOT RUN 18 CHAPTERS.

## Why this result

The 18 remaining chapters were inventoried from the canonical EditorialPlan. CH018 was selected as the first remaining chapter because it has 4 sections and 11 IDEA units, carries EX and REF handles, and presents testimony attribution risk without being CH001 or the shortest chapter. Prompt 1.1 is available through an isolated selector and is not globally activated. First-chapter sources resolve by targeted hydration. Authorized spend remains 0 USD. No remaining chapter was generated.

## Canonical identity

Canonical Python = C:\TranscriptionAI\.venv\Scripts\python.exe
SourceMap, EditorialPlan, and clean transcript were hashed before and after.
They were not modified. CH012 accepted artifacts and the 4B.2.17 lock were not modified.

## Remaining-chapter inventory

18 chapters remain after excluding CH012.
Total remaining sections = 68.
Total remaining planned IDEA units = 275.
A section or idea in the plan is not treated as covered.

## First chapter selection

Selected = CH018 — Testimonies of Resurrection.
Sections = 4. IDEA units = 11.

- CH018 has 4 sections and 11 planned IDEA units, matching the accepted CH012 scale without being the shortest remaining chapter.
- The chapter carries 3 EX and 2 REF units, which lets the first real call test the evidence-handle contract.
- Example kinds include testimony.
- Targeted source context is 377 hydrated SRC words. The 38 313-word transcript is not injected.
- CH001 was not auto-selected. The shortest chapters were not preferred.

Anticipated difficulties:
- Prompt 1.1 has never been used in a real provider call.
- The 4B.2.17 failure mode — IDEA handles in section metadata but not in paras[].e — must be detected immediately.
- Three testimony examples require first-person vs third-person attribution discipline.
- No UNC is assigned to this chapter; uncertainty preservation must be re-checked on a later chapter.
- Semantic equivalence is not proved by structural validation.

Stop conditions:
- Invalid or truncated JSON.
- Missing or extra sections.
- Missing planned IDEA content or invented IDEA handles.
- IDEA handles present in metadata only, absent from paragraph evidence.
- Invalid SRC, EX, REF, or UNC handles.
- Unknown cost or theoretical maximum above the distinct future cap.
- Missing human authorization for this chapter.
- Any automatic paid retry.

## Prompt 1.1

Version = book-generator-faithful-restatement-1.1-candidate.
Available = True. Isolated = True.
Registered in production prompt_select = False.
Activated = False. Ready for production = False. Automatically promoted = False.
Handle mention is not treated as content restatement.
paras[].e must not be completed after generation to satisfy a validator.

## Generation contract

| Exigence | Prompt 1.1 | Contrat JSON | Validateur | Statut |
|---|---|---|---|---|
| Couverture IDEA | Oui | paras[].e | idea_ids_from_paragraphs(evidence_handles/idea_refs); missing planned IDEAs = FAIL; unknown/unassigned IDEAs = FAIL | Compatible |
| Provenance SRC | Oui | paras[].e | resolve_src_for_handles; substantive paragraph without SRC = FAIL; unknown handle = FAIL | Compatible |
| Sections | Oui | sections[].sid | got_ids != planned_ids → missing/extra/wrong-order = FAIL | Compatible |
| Voix narrative | Oui | contrôle éditorial | No structural voice field. Editorial/human review only. Not a semantic-equivalence proof. | Compatible_with_editorial_gap |
| Références | Oui | paras[].e | REF handles must be known and allowed. Content correctness is not semantically certified by the structural validator. | Compatible |

validate_chapter_candidate reports missing planned IDEAs when paras[].e contains no IDEA handles. This is a hard stop after the first real remaining-chapter call.

## First-chapter source context

Chapter = CH018.
Missing sources = [].
Hydrated SRC count = 79.
Whole transcript injected = False.
A missing mandatory source blocks generation.

## Cost envelope

First chapter expected = 0.048528 USD.
First chapter calculable maximum = 0.113538 USD.
18-chapter low / central / high = 0.811943 / 1.063124 / 2.625794 USD.
Validation = UNKNOWN; Terra analog is a hypothesis, not a complete cost.
Authorized spend = 0 USD. Central estimates are not safety caps.
UNKNOWN items are listed and are not replaced by zero.

## Future human authorization if the first chapter is to be generated

This phase does not request a provider. If the user later authorizes exactly one remaining chapter, the token must be limited to:

- Chapter `CH018`.
- Model `anthropic/claude-sonnet-5`.
- Prompt `book-generator-faithful-restatement-1.1-candidate` via an isolated explicit option.
- One remote call. Zero retries. Zero fallbacks.
- A cost cap at or above the calculable theoretical maximum, not the central estimate.
- Hard stop on missing/invented IDEA handles, invalid JSON, truncation, unknown cost, or cap breach.
- Isolated audit output. No publication. No CH012 rewrite. No 18-chapter run.

## Stop

STOP. No Sonnet call. No Terra call. No remaining-chapter generation.
No CH012 regeneration. No global prompt activation. No book.json. No DOCX/PDF.
Wait for the explicit human decision on a distinct one-chapter authorization.
