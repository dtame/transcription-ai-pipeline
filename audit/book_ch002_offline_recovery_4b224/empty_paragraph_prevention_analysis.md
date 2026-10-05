# Empty-paragraph prevention analysis — Phase 4B.2.24

This note is a proposal. The production generation pipeline was not modified.

## Where the empty paragraph was introduced

- Model emitted empty connective: True
- Parser invented the paragraph: False
- Normalizer invented the paragraph: False
- Renderer invented the paragraph: False
- Contract defect: False
- Validation defect: False

The Anthropic parsed JSON already contains SEC006 handle p8 with t="" and e=[]. The materialized candidate preserves that object as P000008. The markdown renderer strips empty text, so the readable file hides the defect. The existing validator reported SEC006.p4: empty text and 1 empty paragraph(s).

The defect is attributed to the model because the raw parsed Anthropic JSON already contains `p8` with `t: ""` and `e: []`. Parsing, materialization, and paragraph-id assignment preserved that object. The markdown renderer omitted it, which hid the failure from the readable file but did not invent it. The existing validator correctly failed (`book-generation-validator-1.0.1`).

## Recommended future rule

Name: `strip_strictly_empty_unprovenanced_paragraphs`.

Authorized in this phase: no. Proposal only.

Apply only when all of the following are true:

- text is empty or whitespace-only
- no IDEA handle
- no SRC handle
- no EX handle
- no REF handle
- no UNC handle
- no other provenance fields
- paragraph is not referenced by another structure

Never:

- delete a paragraph that contains text
- delete a paragraph that carries an IDEA
- delete a paragraph that carries provenance
- delete a section
- renumber remaining paragraphs silently
- modify the raw provider response
- hide a substantial error

After a future authorized strip:

- re-run the existing structural validator, not a weakened copy
- keep the original response immutable
- label the result OFFLINE_DERIVED_ARTIFACT / NOT_PROVIDER_ORIGINAL
- require human review before acceptance

Had this deterministic strip existed as an authorized post-receipt repair, CH002 would not have stopped BATCH-01 for a provenance-less empty connective. The 4B.2.23 lock would still be consumed. This phase only proposes the rule.

Do not weaken the validator to obtain PASS.
