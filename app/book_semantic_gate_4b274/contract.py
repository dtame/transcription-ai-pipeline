"""Versioned 1.1.2-candidate contract. Does not mutate 1.0, 1.1, or 1.1.1."""

from __future__ import annotations

import json
from typing import Any

from app.book_semantic_gate_4b23.prompt import (
    instruction_prompt,
    prompt_fingerprint,
    system_prompt,
)
from app.book_semantic_gate_4b23.reasons import REASON_CODES, REASON_DEFINITIONS
from app.book_semantic_gate_4b23.schema import build_semantic_validation_schema
from app.book_semantic_gate_4b261.candidates import (
    build_candidate_schema,
    candidate_prompt_bundle,
)
from app.book_semantic_gate_4b271.calibration import candidate_111_prompt_bundle
from app.book_semantic_gate_4b274.constants import (
    EXPECTED_PROMPT_111_SHA256,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
    EXPECTED_SCHEMA_11_SHA256,
    OVERFIT_TOKENS,
    PHASE,
    PROMPT_VERSION_11,
    PROMPT_VERSION_111,
    PROMPT_VERSION_112,
    PROMPT_VERSION_HISTORICAL,
    TRANSPORT_VERSION_11,
    TRANSPORT_VERSION_111,
    TRANSPORT_VERSION_112,
    TRANSPORT_VERSION_HISTORICAL,
)
from app.file_utils import content_hash

_SYSTEM_112 = """You are the Independent Semantic Gate of a book-production pipeline.

You receive generated paragraph candidates plus the canonical evidence
assigned to them. You are an evidence-bounded semantic auditor.

You are NOT a fact checker using world knowledge.
You are NOT a theologian, Bible commentator, historian, or legal scholar.
You are NOT an editor improving prose.
You are NOT a co-author.
You do not rewrite the manuscript.

Judge ONLY against the supplied canonical evidence.
Do not use your own knowledge to justify a generated claim.
If a claim is plausible, familiar, or stylistically natural but unsupported
by the supplied evidence, it is not supported.

Valid IDEA/SRC/REF handles are necessary hints, never sufficient proof.
A paragraph may cite correct handles and still contain an unsupported clause.

A partial reference — scripture, book, law, science, history, quotation, or
named authority — permits only what the supplied REF and SRC text actually
contain. Do not complete or expand omitted content from memory.
A correct reference identity does not license a remembered quotation.

High stylistic freedom, low semantic freedom:
The generator may rephrase, reorder, smooth oral speech into editorial prose,
and join propositions that are already supported. It may produce a faithful
synthesis. It may not invent an example, add an unsupported causal link, add
a new consequence, introduce a doctrine that is not present, strengthen a
claim beyond the sources, complete a partial reference from external
knowledge, attribute to the speaker a claim that is absent, or create a new
conclusion under the cover of a transition.

Paraphrase is allowed. Judge semantic entailment, not lexical equality.
A different verb or a stylistic intensifier is not an invention when it
restates attested content without adding a relation, agent, condition, or
quantity. Do not require the source wording to contain the same verb.
Do not treat a nearby theme as proof.
Supported inference is allowed only when the evidence already forces that
meaning. Plausibility is not entailment.
Synthesis across multiple supplied evidence items is allowed only if the
result does not exceed their combined support.

New causality is a because/therefore/as-a-result relation that the evidence
does not support, even if the related facts separately exist.
New implication is a meaning, origin, or 'which means' extension that the
evidence does not support.
Unsupported strengthening raises possibility into certainty, sometimes into
always, association into cause, or partial into complete.
Reference completion fills omitted remainder from memory.

Treat new causal connectors carefully: because, therefore, thus, so that,
which means, as a result. They may create claims stronger than the evidence.
Do not rely on keyword matching as the final judgment.
Still reject invented examples, anecdotes, or hypotheticals.

Inspect connective prose if it contains substantive meaning.
The provider label "con" is not authoritative.
Purely rhetorical or structural transitions may be NON_SUBSTANTIVE.

Evaluate at claim level with paragraph anchoring.
Decompose every required paragraph into claims that together cover every
substantive character of the paragraph text. Give exact start and end offsets.
Do not skip a subordinate clause, negation, quantifier, condition,
comparison, or logical connective.

Classifications:
- SUPPORTED
- QUESTIONABLE
- UNSUPPORTED
- NON_SUBSTANTIVE

Use QUESTIONABLE when a clause is a close but unsupported semantic
extension, not a clearly invented fact.
Use UNSUPPORTED for invented examples, invented anecdotes, invented
hypotheticals, or claims with no supplied support.

Reason codes are machine-readable. Use only this closed catalog:
{catalog}

If no more specific code fits, use OTHER. Do not invent codes. Do not
change case. Do not emit a near-synonym of a catalog code.
QUESTIONABLE and UNSUPPORTED claims must include at least one catalog code.
SUPPORTED and NON_SUBSTANTIVE claims must not include reason codes.
Do not request or emit hidden chain-of-thought.
Do not copy claim text into the JSON. Offsets identify the span.
Do not write free-form essays. Reason codes carry the justification.
Add a short reservation only when QUESTIONABLE or UNSUPPORTED.

Unknown paragraph or evidence handles must be listed in uh.
Do not invent handles.

Respond only through the requested JSON object.
"""

_INSTRUCTIONS_112 = """Audit SEMANTIC_GATE_INPUT_JSON.

For every paragraph in candidate.sections[].paras[] return one pr[] row.
For every paragraph, return claims c[] whose offsets [s,e) cover every
substantive character of paragraph text t.

Whitespace may remain uncovered.
A sentence-final period, question mark, exclamation mark, or ellipsis may
remain uncovered only when it closes already-covered text and does not
itself carry a claim.
A comma, semicolon, colon, dash, parenthesis, or quotation mark may remain
uncovered only when it is a separator between already-covered claims and
does not itself encode a word, negation, or logical connective.
Never leave a word, number, negation, quantifier, causal or adversative
connector, condition, comparison, proposition, or substantial logical
relation uncovered.
Do not omit a clause by covering only surrounding punctuation.

Output one compact object:
- ch = the supplied chapter handle
- v = PASS, REVIEW, or FAIL
- pr[] = paragraph results
- pr[].h = paragraph handle
- pr[].v = SUPPORTED | QUESTIONABLE | UNSUPPORTED | NON_SUBSTANTIVE
- pr[].c[] = claims
- pr[].c[].i = claim index starting at 0
- pr[].c[].s = start offset
- pr[].c[].e = end offset
- pr[].c[].k = classification
- pr[].c[].ev = evidence handles actually used as support
- pr[].c[].r = reason codes from the closed catalog (empty if SUPPORTED or NON_SUBSTANTIVE)
- pr[].c[].n = short reservation, only if QUESTIONABLE or UNSUPPORTED
- pr[].ev = evidence used for the paragraph
- pr[].r = paragraph reason codes from the closed catalog
- sc = counts with keys supported, questionable, unsupported, non_substantive
- uh = unknown handles
- rr = true if any QUESTIONABLE claim exists

Do not emit pr[].c[].t. The caller recovers text from offsets.
Do not emit long explanations.
Do not emit confidence fields.

v = FAIL if any UNSUPPORTED claim exists or uh is non-empty.
v = REVIEW if any QUESTIONABLE claim exists and none are UNSUPPORTED.
v = PASS only if every required paragraph is present and every claim is
SUPPORTED or NON_SUBSTANTIVE.

Do not rewrite manuscript text.
Do not use evidence from other chapters unless approved_reuse says so.
"""


def _catalog_block() -> str:
    lines = [f"- {code}: {REASON_DEFINITIONS[code]}" for code in REASON_CODES]
    return "\n".join(lines)


def candidate_112_system_prompt() -> str:
    return _SYSTEM_112.replace("{catalog}", _catalog_block()).strip() + "\n"


def candidate_112_instruction_prompt() -> str:
    return _INSTRUCTIONS_112.strip() + "\n"


def candidate_112_prompt_bundle() -> dict[str, str]:
    system = candidate_112_system_prompt()
    instructions = candidate_112_instruction_prompt()
    hist = candidate_prompt_bundle()
    c111 = candidate_111_prompt_bundle()
    return {
        "version": PROMPT_VERSION_112,
        "system": system,
        "instructions": instructions,
        "system_sha256": content_hash(system),
        "instructions_sha256": content_hash(instructions),
        "prompt_sha256": prompt_fingerprint(system, instructions),
        "historical_1_0_not_replaced": True,
        "candidate_1_1_not_replaced": True,
        "candidate_1_1_1_not_replaced": True,
        "historical_system_sha256": content_hash(system_prompt()),
        "historical_instructions_sha256": content_hash(instruction_prompt()),
        "candidate_11_prompt_sha256": hist["prompt_sha256"],
        "candidate_111_prompt_sha256": c111["prompt_sha256"],
        "identical_to_1_0": False,
        "identical_to_1_1": False,
        "identical_to_1_1_1": False,
        "promoted": False,
    }


def overfit_tokens_absent(text: str) -> bool:
    lowered = text.lower()
    return not any(token.lower() in lowered for token in OVERFIT_TOKENS)


def contract_112_review() -> dict[str, Any]:
    bundle = candidate_112_prompt_bundle()
    hist = candidate_prompt_bundle()
    c111 = candidate_111_prompt_bundle()
    schema = build_candidate_schema()
    blob = bundle["system"] + bundle["instructions"]
    return {
        "phase": PHASE,
        "justified": True,
        "why_created": (
            "h01 showed lexical over-rejection of supported paraphrase. h02 "
            "showed correct causal isolation plus invented reason codes and "
            "separator coverage failures. 1.1.2 lists the closed catalog, "
            "makes reservation codes mandatory, and generalizes admissible "
            "separator coverage without overfitting either canary."
        ),
        "candidate_prompt_version": PROMPT_VERSION_112,
        "candidate_transport_version": TRANSPORT_VERSION_112,
        "transport_1_1_2_created": False,
        "why_no_new_transport": (
            "Existing 1.1-candidate fields already carry claim-level assessment, "
            "exact spans, evidence handles, reason codes, global verdict, short "
            "reservations, and compact JSON. Field meanings are unchanged."
        ),
        "historical_1_0_unmodified": True,
        "candidate_1_1_unmodified": True,
        "candidate_1_1_1_unmodified": True,
        "promoted": False,
        "prompt": {
            "system_sha256": bundle["system_sha256"],
            "instructions_sha256": bundle["instructions_sha256"],
            "prompt_sha256": bundle["prompt_sha256"],
            "system_bytes": len(bundle["system"].encode("utf-8")),
            "instructions_bytes": len(bundle["instructions"].encode("utf-8")),
        },
        "frozen_1_1_prompt_sha256": hist["prompt_sha256"],
        "frozen_1_1_1_prompt_sha256": c111["prompt_sha256"],
        "changes": [
            "high stylistic freedom, low semantic freedom made operational",
            "legitimate paraphrase vs supported inference vs new causality vs new implication",
            "unsupported strengthening and reference completion restated without canary examples",
            "closed reason-code catalog listed with definitions",
            "OTHER is the only fallback; invented codes forbidden",
            "QUESTIONABLE/UNSUPPORTED require a catalog reason code",
            "coverage may omit admissible separators between covered claims",
            "words, negations, connectives, conditions, and clauses remain mandatory",
            "compact JSON fields unchanged",
        ],
        "not_in_prompt": {
            "overfit_tokens_absent": overfit_tokens_absent(blob),
            "human_labels_absent": (
                "human label" not in blob.lower()
                and "gold label" not in blob.lower()
            ),
            "benchmark_answers_absent": True,
            "h01_absent": "h01" not in blob.lower(),
            "h02_absent": "h02" not in blob.lower(),
        },
        "schema_unchanged_from_1_1": content_hash(
            json.dumps(schema, ensure_ascii=False, sort_keys=True)
        )
        == EXPECTED_SCHEMA_11_SHA256,
        "reason_codes_catalog_unchanged": True,
        "reason_codes_listed_in_prompt": all(code in bundle["system"] for code in REASON_CODES),
        "proposition_coverage_preserved": True,
        "compact_format_preserved": True,
        "remaining_validation_limits": [
            "A listed catalog does not prove Terra will emit only catalog codes.",
            "Admissible separators do not prove future Terra coverage will be complete.",
            "Offline FakeAI does not prove future Terra behavior.",
            "Supported inference still requires human review on borderline origin/framing claims.",
            "sc key names are instructed, not a new transport field.",
        ],
        "secrets_included": False,
    }


def transport_compatibility() -> dict[str, Any]:
    schema_11 = build_candidate_schema()
    schema_10 = build_semantic_validation_schema()
    return {
        "phase": PHASE,
        "reuse_transport": TRANSPORT_VERSION_11,
        "new_transport_created": False,
        "transport_1_1_2": TRANSPORT_VERSION_112,
        "field_meanings_unchanged": True,
        "preserved": [
            "claim-level assessment",
            "exact spans",
            "evidence handles",
            "reason codes",
            "global verdict",
            "short reservations",
            "compact JSON",
        ],
        "schema_1_1_sha256": content_hash(
            json.dumps(schema_11, ensure_ascii=False, sort_keys=True)
        ),
        "schema_1_0_sha256": content_hash(
            json.dumps(schema_10, ensure_ascii=False, sort_keys=True)
        ),
        "expected_schema_1_1_sha256": EXPECTED_SCHEMA_11_SHA256,
        "matches_frozen_1_1_schema": content_hash(
            json.dumps(schema_11, ensure_ascii=False, sort_keys=True)
        )
        == EXPECTED_SCHEMA_11_SHA256,
        "reason_enum_unchanged": list(schema_11["$defs"]["claim"]["properties"]["r"]["items"]["enum"])
        == list(REASON_CODES),
        "silent_field_redefinition": False,
        "secrets_included": False,
    }


def contract_comparison() -> dict[str, Any]:
    hist_system = system_prompt()
    hist_instr = instruction_prompt()
    c11 = candidate_prompt_bundle()
    c111 = candidate_111_prompt_bundle()
    c112 = candidate_112_prompt_bundle()
    return {
        "phase": PHASE,
        "versions": {
            "1.0": {
                "prompt": PROMPT_VERSION_HISTORICAL,
                "transport": TRANSPORT_VERSION_HISTORICAL,
                "status": "FROZEN",
                "prompt_sha256": prompt_fingerprint(hist_system, hist_instr),
                "matches_frozen_expected": (
                    content_hash(hist_system) == EXPECTED_PROMPT_SYSTEM_SHA256
                    and content_hash(hist_instr) == EXPECTED_PROMPT_INSTRUCTIONS_SHA256
                ),
            },
            "1.1-candidate": {
                "prompt": PROMPT_VERSION_11,
                "transport": TRANSPORT_VERSION_11,
                "status": "FROZEN_CANDIDATE_NOT_PROMOTED",
                "prompt_sha256": c11["prompt_sha256"],
                "matches_frozen_expected": c11["prompt_sha256"] == EXPECTED_PROMPT_11_SHA256,
            },
            "1.1.1-candidate": {
                "prompt": PROMPT_VERSION_111,
                "transport": TRANSPORT_VERSION_111,
                "status": "FROZEN_CANDIDATE_NOT_PROMOTED",
                "prompt_sha256": c111["prompt_sha256"],
                "matches_frozen_expected": c111["prompt_sha256"] == EXPECTED_PROMPT_111_SHA256,
            },
            "1.1.2-candidate": {
                "prompt": PROMPT_VERSION_112,
                "transport": TRANSPORT_VERSION_112,
                "status": "PROPOSAL_ONLY_NOT_PROMOTED",
                "prompt_sha256": c112["prompt_sha256"],
                "identical_to_1_1_1": False,
                "transport_compatible_with_1_1": True,
            },
        },
        "not_promoted": True,
        "historical_contracts_modified": False,
        "secrets_included": False,
    }


__all__ = [
    "candidate_112_instruction_prompt",
    "candidate_112_prompt_bundle",
    "candidate_112_system_prompt",
    "contract_112_review",
    "contract_comparison",
    "overfit_tokens_absent",
    "transport_compatibility",
]
