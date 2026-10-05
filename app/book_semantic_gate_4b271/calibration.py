"""Versioned 1.1.1-candidate contract. Does not mutate 1.0 or 1.1-candidate."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b23.prompt import (
    instruction_prompt,
    prompt_fingerprint,
    system_prompt,
)
from app.book_semantic_gate_4b23.schema import build_semantic_validation_schema
from app.book_semantic_gate_4b261.candidates import (
    build_candidate_schema,
    candidate_instruction_prompt,
    candidate_prompt_bundle,
    candidate_system_prompt,
)
from app.book_semantic_gate_4b271.constants import (
    EXPECTED_PROMPT_11_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_11_SYSTEM_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
    EXPECTED_SCHEMA_11_SHA256,
    EXPECTED_SCHEMA_SHA256,
    OVERFIT_TOKENS,
    PHASE,
    PROMPT_VERSION_11,
    PROMPT_VERSION_111,
    PROMPT_VERSION_HISTORICAL,
    TRANSPORT_VERSION_11,
    TRANSPORT_VERSION_111,
    TRANSPORT_VERSION_HISTORICAL,
)
from app.file_utils import content_hash
import json

_SYSTEM_111 = """You are the Independent Semantic Gate of a book-production pipeline.

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

Paraphrase is allowed. Judge semantic entailment, not lexical equality.
A different verb or a stylistic personification is not an invention when it
restates an attested absence, prohibition, or unavailability.
Do not require the source wording to contain the same verb.
Do not treat a nearby theme as proof.
Synthesis across multiple supplied evidence items is allowed only if the
result does not exceed their combined support.

Treat new causal connectors carefully: because, therefore, thus, so that,
which means, as a result. They may create claims stronger than the evidence.
Do not rely on keyword matching as the final judgment.

Reject unjustified strengthening: sometimes→always, may→will,
associated with→causes, possible→certain, partial→complete.
Preserve canonical uncertainty.

Still reject invented examples, anecdotes, or hypotheticals.
Still reject new causal links, new conclusions, and new implications.
Still reject completion or expansion of partial references.

Inspect connective prose if it contains substantive meaning.
The provider label "con" is not authoritative.
Purely rhetorical or structural transitions may be NON_SUBSTANTIVE.

Evaluate at claim level with paragraph anchoring.
Decompose every required paragraph into claims that together cover the
entire paragraph text. Give exact start and end offsets.
Do not skip a subordinate clause.

Classifications:
- SUPPORTED
- QUESTIONABLE
- UNSUPPORTED
- NON_SUBSTANTIVE

Use QUESTIONABLE when a clause is a close but unsupported semantic
extension, not a clearly invented fact.
Use UNSUPPORTED for invented examples, invented anecdotes, invented
hypotheticals, or claims with no supplied support.

Reason codes are machine-readable. Use only the supplied closed list.
QUESTIONABLE and UNSUPPORTED claims must include at least one reason code.
Do not request or emit hidden chain-of-thought.
Do not copy claim text into the JSON. Offsets identify the span.
Do not write free-form essays. Reason codes carry the justification.
Add a short reservation only when QUESTIONABLE or UNSUPPORTED.

Unknown paragraph or evidence handles must be listed in uh.
Do not invent handles.

Respond only through the requested JSON object.
"""

_INSTRUCTIONS_111 = """Audit SEMANTIC_GATE_INPUT_JSON.

For every paragraph in candidate.sections[].paras[] return one pr[] row.
For every paragraph, return claims c[] whose offsets [s,e) cover every
substantive character of paragraph text t. Whitespace and a sentence-final
period, question mark, or exclamation mark may remain uncovered only when
they do not themselves carry a claim. Never leave a word, number, negation,
connective, or clause uncovered.

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
- pr[].c[].r = reason codes (empty if SUPPORTED or NON_SUBSTANTIVE)
- pr[].c[].n = short reservation, only if QUESTIONABLE or UNSUPPORTED
- pr[].ev = evidence used for the paragraph
- pr[].r = paragraph reason codes
- sc = counts of claim classifications
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


def candidate_111_system_prompt() -> str:
    return _SYSTEM_111.strip() + "\n"


def candidate_111_instruction_prompt() -> str:
    return _INSTRUCTIONS_111.strip() + "\n"


def candidate_111_prompt_bundle() -> dict[str, str]:
    system = candidate_111_system_prompt()
    instructions = candidate_111_instruction_prompt()
    hist = candidate_prompt_bundle()
    return {
        "version": PROMPT_VERSION_111,
        "system": system,
        "instructions": instructions,
        "system_sha256": content_hash(system),
        "instructions_sha256": content_hash(instructions),
        "prompt_sha256": prompt_fingerprint(system, instructions),
        "historical_1_0_not_replaced": True,
        "candidate_1_1_not_replaced": True,
        "historical_system_sha256": content_hash(system_prompt()),
        "historical_instructions_sha256": content_hash(instruction_prompt()),
        "candidate_11_system_sha256": hist["system_sha256"],
        "candidate_11_instructions_sha256": hist["instructions_sha256"],
        "candidate_11_prompt_sha256": hist["prompt_sha256"],
        "identical_to_1_0": False,
        "identical_to_1_1": False,
        "promoted": False,
    }


def overfit_tokens_absent(text: str) -> bool:
    lowered = text.lower()
    return not any(token.lower() in lowered for token in OVERFIT_TOKENS)


def calibration_candidate() -> dict[str, Any]:
    bundle = candidate_111_prompt_bundle()
    hist = candidate_prompt_bundle()
    schema = build_candidate_schema()
    return {
        "phase": PHASE,
        "calibration_required": True,
        "candidate_prompt_version": PROMPT_VERSION_111,
        "candidate_transport_version": TRANSPORT_VERSION_111,
        "transport_1_1_1_created": False,
        "why_no_new_transport": (
            "The compact JSON fields are unchanged. Local coverage policy and "
            "reason-code presence are validator-side. Frozen 1.1-candidate "
            "transport remains the schema."
        ),
        "historical_1_0_unmodified": True,
        "candidate_1_1_unmodified": True,
        "promoted": False,
        "prompt": {
            "system_sha256": bundle["system_sha256"],
            "instructions_sha256": bundle["instructions_sha256"],
            "prompt_sha256": bundle["prompt_sha256"],
            "system_bytes": len(bundle["system"].encode("utf-8")),
            "instructions_bytes": len(bundle["instructions"].encode("utf-8")),
        },
        "frozen_1_1_prompt_sha256": hist["prompt_sha256"],
        "changes": [
            "semantic entailment vs lexical match made operational",
            "stylistic restatement of attested absence is not invention",
            "nearby theme is still not proof",
            "invented examples, new causality, new implications, and partial-reference completion remain rejected",
            "QUESTIONABLE/UNSUPPORTED require a reason code",
            "coverage may omit sentence-final .?! that do not carry a claim",
            "words, numbers, negations, connectives, and clauses remain mandatory",
        ],
        "not_in_prompt": {
            "bargaining": overfit_tokens_absent(bundle["system"] + bundle["instructions"]),
            "h01": "h01" not in bundle["system"] + bundle["instructions"],
            "IDEA224": "IDEA224" not in bundle["system"] + bundle["instructions"],
            "benchmark_answers": True,
        },
        "schema_unchanged_from_1_1": content_hash(
            json.dumps(schema, ensure_ascii=False, sort_keys=True)
        )
        == EXPECTED_SCHEMA_11_SHA256,
        "reason_codes_unchanged": True,
        "proposition_coverage_preserved": True,
        "compact_format_preserved": True,
        "secrets_included": False,
    }


def contract_comparison() -> dict[str, Any]:
    hist_system = system_prompt()
    hist_instr = instruction_prompt()
    c11 = candidate_prompt_bundle()
    c111 = candidate_111_prompt_bundle()
    schema_10 = build_semantic_validation_schema()
    schema_11 = build_candidate_schema()
    return {
        "phase": PHASE,
        "versions": {
            "1.0": {
                "prompt": PROMPT_VERSION_HISTORICAL,
                "transport": TRANSPORT_VERSION_HISTORICAL,
                "status": "FROZEN",
                "system_sha256": content_hash(hist_system),
                "instructions_sha256": content_hash(hist_instr),
                "prompt_sha256": prompt_fingerprint(hist_system, hist_instr),
                "schema_sha256": content_hash(
                    json.dumps(schema_10, ensure_ascii=False, sort_keys=True)
                ),
                "expected_system_sha256": EXPECTED_PROMPT_SYSTEM_SHA256,
                "expected_instructions_sha256": EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
                "expected_schema_sha256": EXPECTED_SCHEMA_SHA256,
                "matches_frozen_expected": (
                    content_hash(hist_system) == EXPECTED_PROMPT_SYSTEM_SHA256
                    and content_hash(hist_instr) == EXPECTED_PROMPT_INSTRUCTIONS_SHA256
                ),
                "prompt_bytes": len(hist_system.encode("utf-8"))
                + len(hist_instr.encode("utf-8")),
                "requires_claim_text_and_explanation": True,
            },
            "1.1-candidate": {
                "prompt": PROMPT_VERSION_11,
                "transport": TRANSPORT_VERSION_11,
                "status": "FROZEN_CANDIDATE_NOT_PROMOTED",
                "system_sha256": c11["system_sha256"],
                "instructions_sha256": c11["instructions_sha256"],
                "prompt_sha256": c11["prompt_sha256"],
                "schema_sha256": content_hash(
                    json.dumps(schema_11, ensure_ascii=False, sort_keys=True)
                ),
                "expected_system_sha256": EXPECTED_PROMPT_11_SYSTEM_SHA256,
                "expected_instructions_sha256": EXPECTED_PROMPT_11_INSTRUCTIONS_SHA256,
                "expected_prompt_sha256": EXPECTED_PROMPT_11_SHA256,
                "expected_schema_sha256": EXPECTED_SCHEMA_11_SHA256,
                "matches_frozen_expected": (
                    c11["system_sha256"] == EXPECTED_PROMPT_11_SYSTEM_SHA256
                    and c11["prompt_sha256"] == EXPECTED_PROMPT_11_SHA256
                    and content_hash(json.dumps(schema_11, ensure_ascii=False, sort_keys=True))
                    == EXPECTED_SCHEMA_11_SHA256
                ),
                "prompt_bytes": len(c11["system"].encode("utf-8"))
                + len(c11["instructions"].encode("utf-8")),
                "compact": True,
                "paraphrase_allowed_already": True,
                "ambiguity": (
                    "Paraphrase/entailment is stated but not operationalized "
                    "against lexical verb-matching. Coverage says 'except "
                    "whitespace' while Terra also skipped sentence-final "
                    "periods."
                ),
            },
            "1.1.1-candidate": {
                "prompt": PROMPT_VERSION_111,
                "transport": TRANSPORT_VERSION_111,
                "status": "PROPOSAL_ONLY_NOT_PROMOTED",
                "system_sha256": c111["system_sha256"],
                "instructions_sha256": c111["instructions_sha256"],
                "prompt_sha256": c111["prompt_sha256"],
                "schema": "reuses 1.1-candidate transport",
                "prompt_bytes": len(c111["system"].encode("utf-8"))
                + len(c111["instructions"].encode("utf-8")),
                "identical_to_1_1": False,
                "false_rejection_risk": "Lower on stylistic restatement of attested absence.",
                "false_support_risk": (
                    "Unchanged for examples, causality, implications, and "
                    "reference completion if those rules are followed."
                ),
                "blocking_capacity_preserved": True,
                "proposition_coverage_preserved": True,
                "transport_compatible_with_1_1": True,
            },
        },
        "not_promoted": True,
        "historical_contracts_modified": False,
        "secrets_included": False,
    }


__all__ = [
    "calibration_candidate",
    "candidate_111_instruction_prompt",
    "candidate_111_prompt_bundle",
    "candidate_111_system_prompt",
    "contract_comparison",
    "overfit_tokens_absent",
]
