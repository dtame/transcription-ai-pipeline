# Human review guide — Phase 4B.2.28

This dossier lets you read the book without opening 19 chapter files.
This phase did not approve any pending chapter.

## Where to read the complete manuscript

Open `audit/book_full_manuscript_review_4b228/manuscript_reading_draft.md`.
That file contains the book title from the EditorialPlan, a table of contents,
and the 19 chapters in canonical order. Paragraphs are unchanged.

Integrity status: PASS.
Paragraph integrity: PASS.

## Chapters already approved

CH001, CH002, CH003, CH004, CH012, CH018.
Recorded status: `HUMAN_EDITORIALLY_ACCEPTED`.
Do not regenerate or rewrite them.

- CH001: `audit/real/book_generation_4b223_batch01/chapters/CH001/`
- CH002: recovered artefacts only, `audit/book_ch002_offline_recovery_4b224/`
- CH003 and CH004: `audit/real/book_generation_4b225_batch01_resume/chapters/`
- CH012: authorial v2 designated by the 4B.2.19 acceptance manifest
- CH018: artefacts designated by the 4B.2.22 acceptance manifest

## Chapters still awaiting editorial approval

CH005, CH006, CH007, CH008, CH009, CH010, CH011, CH013, CH014, CH015, CH016, CH017, CH019.
Recorded status: `HUMAN_REVIEW_PENDING`.
They are generated and structurally valid. They are not approved.

## Observations that deserve particular attention

### Strengthened claims in the 13 new chapters

- CH005 SEC022 P000021 — `never`. An `always` / `never` wording is not automatically an error. Keep or change it only by human decision.
- CH006 SEC027 P000024 — `never`. An `always` / `never` wording is not automatically an error. Keep or change it only by human decision.
- CH008 SEC033 P000004 — `never`. An `always` / `never` wording is not automatically an error. Keep or change it only by human decision.
- CH009 SEC036 P000001 — `always`. An `always` / `never` wording is not automatically an error. Keep or change it only by human decision.
- CH010 SEC040 P000007 — `never`. An `always` / `never` wording is not automatically an error. Keep or change it only by human decision.
- CH013 SEC052 P000004 — `never`. An `always` / `never` wording is not automatically an error. Keep or change it only by human decision.
- CH014 SEC055 P000008 — `never`. An `always` / `never` wording is not automatically an error. Keep or change it only by human decision.
- CH017 SEC065 P000022 — `never`. An `always` / `never` wording is not automatically an error. Keep or change it only by human decision.

### Historical reference / example notes

- CH003: EX005 without an explicit handle.
- CH004: REF011, REF012, REF013 without explicit handles; references present in the prose.
- CH012: EX030, historically documented partial coverage.
- CH018: EX046 present in the text without an explicit handle.

### Similar handle-absent notes among the 13 new chapters

- CH006 REF REF009 — correspondence_uncertain.
- CH006 REF REF020 — correspondence_uncertain.
- CH006 REF REF021 — correspondence_uncertain.
- CH006 REF REF022 — correspondence_uncertain.
- CH006 REF REF023 — correspondence_uncertain.
- CH007 REF REF025 — correspondence_uncertain.
- CH010 EX EX017 — correspondence_uncertain.
- CH010 EX EX018 — correspondence_uncertain.
- CH010 EX EX019 — correspondence_uncertain.
- CH010 REF REF030 — correspondence_uncertain.
- CH010 REF REF031 — correspondence_uncertain.
- CH015 EX EX037 — correspondence_uncertain.
- CH017 EX EX043 — correspondence_uncertain.

### Continuity notes

- `POSSIBLE_ABRUPT_TRANSITION` CH002 → CH003: No shared content word of length ≥ 4 between the last paragraph of the previous chapter and the first paragraph of the next chapter.
- `POSSIBLE_ABRUPT_TRANSITION` CH003 → CH004: No shared content word of length ≥ 4 between the last paragraph of the previous chapter and the first paragraph of the next chapter.
- `POSSIBLE_ABRUPT_TRANSITION` CH004 → CH005: No shared content word of length ≥ 4 between the last paragraph of the previous chapter and the first paragraph of the next chapter.
- `POSSIBLE_ABRUPT_TRANSITION` CH007 → CH008: No shared content word of length ≥ 4 between the last paragraph of the previous chapter and the first paragraph of the next chapter.
- `POSSIBLE_ABRUPT_TRANSITION` CH008 → CH009: No shared content word of length ≥ 4 between the last paragraph of the previous chapter and the first paragraph of the next chapter.
- `POSSIBLE_ABRUPT_TRANSITION` CH009 → CH010: No shared content word of length ≥ 4 between the last paragraph of the previous chapter and the first paragraph of the next chapter.
- `POSSIBLE_ABRUPT_TRANSITION` CH010 → CH011: No shared content word of length ≥ 4 between the last paragraph of the previous chapter and the first paragraph of the next chapter.
- `POSSIBLE_ABRUPT_TRANSITION` CH012 → CH013: No shared content word of length ≥ 4 between the last paragraph of the previous chapter and the first paragraph of the next chapter.
- `POSSIBLE_ABRUPT_TRANSITION` CH013 → CH014: No shared content word of length ≥ 4 between the last paragraph of the previous chapter and the first paragraph of the next chapter.
- `POSSIBLE_ABRUPT_TRANSITION` CH015 → CH016: No shared content word of length ≥ 4 between the last paragraph of the previous chapter and the first paragraph of the next chapter.
- `POSSIBLE_ABRUPT_TRANSITION` CH016 → CH017: No shared content word of length ≥ 4 between the last paragraph of the previous chapter and the first paragraph of the next chapter.
- `POSSIBLE_ABRUPT_TRANSITION` CH017 → CH018: No shared content word of length ≥ 4 between the last paragraph of the previous chapter and the first paragraph of the next chapter.
- `POSSIBLE_ABRUPT_TRANSITION` CH018 → CH019: No shared content word of length ≥ 4 between the last paragraph of the previous chapter and the first paragraph of the next chapter.

## How to signal a correction

1. Open `human_review_checklist.json`.
2. Set the chapter `decision` to `REQUEST_CORRECTION`.
3. Write the exact passage, the chapter, the section, and the required change in `correction_note`.
4. Do not edit the chapter files in place during this review.
5. Do not ask this phase to rewrite the prose automatically.

## How to approve one of the 13 chapters

1. Read the chapter in the assembled manuscript.
2. Check the observations listed above for that chapter.
3. In `human_review_checklist.json`, set `decision` to `APPROVE_UNCHANGED` or `APPROVE_WITH_DOCUMENTED_OBSERVATIONS`.
4. Fill `reviewer` and `date`.
5. A later phase must record a formal acceptance manifest. This phase does not do that.

## How to approve the whole manuscript

Approve the manuscript only after the 13 pending chapters have been reviewed.
Set `manuscript_decision` to `APPROVE_FULL_MANUSCRIPT` in the checklist.
That decision is a human record. It is not created by this phase.
Approval of the reading manuscript is not publication of `book.json`, DOCX, or PDF.

## Review grid for the 13 new chapters

| Chapter | Title | Voice | Strengthened claim | EX/REF notes | Continuity | Decision |
|---|---|---|---|---|---|---|
| CH005 | Access, Not Achievement | no frame flagged | yes | no similar note | abrupt-transition note | |
| CH006 | That They May Be One | no frame flagged | yes | handle-absent note | — | |
| CH007 | Loved Exactly as Jesus Is Loved | no frame flagged | no historical flag | handle-absent note | — | |
| CH008 | Set Your Mind Above | no frame flagged | yes | no similar note | abrupt-transition note | |
| CH009 | Laws You Gave Yourself | no frame flagged | yes | no similar note | abrupt-transition note | |
| CH010 | Spirit, Soul and Body | no frame flagged | yes | handle-absent note | abrupt-transition note | |
| CH011 | Reasonings and Strongholds | no frame flagged | no historical flag | no similar note | abrupt-transition note | |
| CH013 | The Renewed Mind and the Hidden Faculty | no frame flagged | yes | no similar note | abrupt-transition note | |
| CH014 | Operating What You Have | no frame flagged | yes | no similar note | abrupt-transition note | |
| CH015 | Grace Barely Touched | no frame flagged | no historical flag | handle-absent note | — | |
| CH016 | Death as Gain | no frame flagged | no historical flag | no similar note | abrupt-transition note | |
| CH017 | Nothing by Chance | no frame flagged | yes | handle-absent note | abrupt-transition note | |
| CH019 | Out of the Eater | no frame flagged | no historical flag | no similar note | abrupt-transition note | |

Leave the Decision column empty until a human writes it.

## What this phase did not do

- It did not approve the 13 candidates.
- It did not rewrite any sentence.
- It did not call a provider.
- It did not publish `book.json`.
- It did not generate DOCX or PDF.
