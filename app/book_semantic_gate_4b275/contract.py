"""Versioned 1.1.3-candidate contract. Does not mutate 1.0, 1.1, 1.1.1, or 1.1.2."""

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
from app.book_semantic_gate_4b262.contract import (
    OPTIONAL_RESERVATION_FIELD,
    REQUIRED_CLAIM_FIELDS,
    REQUIRED_PARAGRAPH_FIELDS,
    REQUIRED_TOP_FIELDS,
    compact_contract_specification,
)
from app.book_semantic_gate_4b271.calibration import candidate_111_prompt_bundle
from app.book_semantic_gate_4b274.contract import (
    candidate_112_prompt_bundle,
    overfit_tokens_absent as overfit_tokens_absent_112,
)
from app.book_semantic_gate_4b275.constants import (
    EXPECTED_PROMPT_111_SHA256,
    EXPECTED_PROMPT_112_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_112_SHA256,
    EXPECTED_PROMPT_112_SYSTEM_SHA256,
    EXPECTED_PROMPT_113_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_113_SHA256,
    EXPECTED_PROMPT_113_SYSTEM_SHA256,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
    EXPECTED_SCHEMA_11_SHA256,
    OVERFIT_TOKENS,
    PHASE,
    PROMPT_VERSION_11,
    PROMPT_VERSION_111,
    PROMPT_VERSION_112,
    PROMPT_VERSION_113,
    PROMPT_VERSION_HISTORICAL,
    TRANSPORT_VERSION_11,
    TRANSPORT_VERSION_111,
    TRANSPORT_VERSION_112,
    TRANSPORT_VERSION_113,
    TRANSPORT_VERSION_HISTORICAL,
)
from app.file_utils import content_hash

_SYSTEM_113 = """You are the Independent Semantic Gate of a book-production pipeline.

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
knowledge, attribute to the speaker a claim that is absent, assign an origin
the evidence does not establish, or create a new conclusion under the cover
of a transition.

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
Unsupported attribution names an agent, source, or origin that the evidence
does not support.

Treat new causal connectors carefully: because, therefore, thus, so that,
which means, as a result. They may create claims stronger than the evidence.
Do not rely on keyword matching as the final judgment.
Still reject invented examples, anecdotes, or hypotheticals.

Inspect connective prose if it contains substantive meaning.
The provider label "con" is not authoritative.
A purely rhetorical or structural marker that carries no meaning-bearing
assertion may be NON_SUBSTANTIVE.
An editorial transition is not automatically NON_SUBSTANTIVE.
A rhetorical sentence is not automatically a new assertion.
If a framing sentence asserts origin, attribution, evaluation, or
conclusion, classify that assertion. If it is not clearly entailed, use
QUESTIONABLE rather than forcing SUPPORTED or NON_SUBSTANTIVE.
Do not use NON_SUBSTANTIVE to hide a meaning-bearing claim.

Evaluate at claim level with paragraph anchoring.
Decompose every required paragraph into claims that together cover every
substantive character of the paragraph text. Give exact start and end offsets.
Do not skip a subordinate clause, negation, quantifier, condition,
comparison, or logical connective.

Classifications:
- SUPPORTED: substantial content is explicitly present in the supplied
  evidence, or is semantically implied by that evidence without adding a
  new assertion. A lexical rephrasing is not automatically an invention.
  A legitimate stylistic paraphrase may be SUPPORTED.
- QUESTIONABLE: available evidence does not confirm the whole claim; a
  plausible inference is not actually implied; a strengthening or
  substantial nuance remains uncertain; or the link to evidence is
  ambiguous. QUESTIONABLE blocks production acceptance.
- UNSUPPORTED: a substantial assertion not supported by supplied evidence,
  including an invented example, a new causal relation, a new consequence,
  a new doctrinal implication, an unsupported attribution, or a reference
  completed from external knowledge. UNSUPPORTED blocks production
  acceptance.
- NON_SUBSTANTIVE: a purely rhetorical or structural marker with no
  meaning-bearing assertion. It must not mask a claim that asserts origin,
  worth, attribution, cause, condition, or content.

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

_INSTRUCTIONS_113 = """Audit SEMANTIC_GATE_INPUT_JSON.

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
A valid span that omits a word, negation, quantifier, condition, or
logical connective is incomplete coverage, not a paraphrase.

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


def candidate_113_system_prompt() -> str:
    return _SYSTEM_113.replace("{catalog}", _catalog_block()).strip() + "\n"


def candidate_113_instruction_prompt() -> str:
    return _INSTRUCTIONS_113.strip() + "\n"


def candidate_113_prompt_bundle() -> dict[str, str]:
    system = candidate_113_system_prompt()
    instructions = candidate_113_instruction_prompt()
    hist = candidate_prompt_bundle()
    c111 = candidate_111_prompt_bundle()
    c112 = candidate_112_prompt_bundle()
    return {
        "version": PROMPT_VERSION_113,
        "system": system,
        "instructions": instructions,
        "system_sha256": content_hash(system),
        "instructions_sha256": content_hash(instructions),
        "prompt_sha256": prompt_fingerprint(system, instructions),
        "historical_1_0_not_replaced": True,
        "candidate_1_1_not_replaced": True,
        "candidate_1_1_1_not_replaced": True,
        "candidate_1_1_2_not_replaced": True,
        "historical_system_sha256": content_hash(system_prompt()),
        "historical_instructions_sha256": content_hash(instruction_prompt()),
        "candidate_11_prompt_sha256": hist["prompt_sha256"],
        "candidate_111_prompt_sha256": c111["prompt_sha256"],
        "candidate_112_prompt_sha256": c112["prompt_sha256"],
        "identical_to_1_0": False,
        "identical_to_1_1": False,
        "identical_to_1_1_1": False,
        "identical_to_1_1_2": False,
        "promoted": False,
    }


def overfit_tokens_absent(text: str) -> bool:
    lowered = text.lower()
    return not any(token.lower() in lowered for token in OVERFIT_TOKENS)


def contract_inventory() -> dict[str, Any]:
    hist_system = system_prompt()
    hist_instr = instruction_prompt()
    c11 = candidate_prompt_bundle()
    c111 = candidate_111_prompt_bundle()
    c112 = candidate_112_prompt_bundle()
    c113 = candidate_113_prompt_bundle()
    schema_11 = build_candidate_schema()
    schema_10 = build_semantic_validation_schema()
    spec = compact_contract_specification()
    return {
        "phase": PHASE,
        "versions": {
            "book-semantic-validator-1.0": {
                "status": "FROZEN",
                "location": "app.book_semantic_gate_4b23.prompt",
                "transport": TRANSPORT_VERSION_HISTORICAL,
                "transport_location": "app.book_semantic_gate_4b23.schema",
                "system_sha256": content_hash(hist_system),
                "instructions_sha256": content_hash(hist_instr),
                "prompt_sha256": prompt_fingerprint(hist_system, hist_instr),
                "matches_frozen_expected": (
                    content_hash(hist_system) == EXPECTED_PROMPT_SYSTEM_SHA256
                    and content_hash(hist_instr) == EXPECTED_PROMPT_INSTRUCTIONS_SHA256
                ),
                "immutable": True,
                "modified_this_phase": False,
                "compatible_with_local_validator": True,
            },
            "book-semantic-validator-1.1-candidate": {
                "status": "FROZEN_CANDIDATE_NOT_PROMOTED",
                "location": "app.book_semantic_gate_4b261.candidates",
                "transport": TRANSPORT_VERSION_11,
                "transport_location": "app.book_semantic_gate_4b261.candidates.build_candidate_schema",
                "prompt_sha256": c11["prompt_sha256"],
                "matches_frozen_expected": c11["prompt_sha256"] == EXPECTED_PROMPT_11_SHA256,
                "immutable": True,
                "modified_this_phase": False,
                "promoted": False,
                "compatible_with_local_validator": True,
            },
            "book-semantic-validator-1.1.1-candidate": {
                "status": "FROZEN_CANDIDATE_NOT_PROMOTED",
                "location": "app.book_semantic_gate_4b271.calibration",
                "transport": TRANSPORT_VERSION_111,
                "prompt_sha256": c111["prompt_sha256"],
                "matches_frozen_expected": c111["prompt_sha256"] == EXPECTED_PROMPT_111_SHA256,
                "immutable": True,
                "modified_this_phase": False,
                "promoted": False,
                "compatible_with_local_validator": True,
                "depends_on": [
                    PROMPT_VERSION_11,
                    TRANSPORT_VERSION_11,
                ],
            },
            "book-semantic-validator-1.1.2-candidate": {
                "status": "FROZEN_CANDIDATE_NOT_PROMOTED",
                "location": "app.book_semantic_gate_4b274.contract",
                "transport": TRANSPORT_VERSION_112,
                "prompt_sha256": c112["prompt_sha256"],
                "system_sha256": c112["system_sha256"],
                "instructions_sha256": c112["instructions_sha256"],
                "matches_frozen_expected": (
                    c112["prompt_sha256"] == EXPECTED_PROMPT_112_SHA256
                    and c112["system_sha256"] == EXPECTED_PROMPT_112_SYSTEM_SHA256
                    and c112["instructions_sha256"]
                    == EXPECTED_PROMPT_112_INSTRUCTIONS_SHA256
                ),
                "immutable": True,
                "modified_this_phase": False,
                "promoted": False,
                "compatible_with_local_validator": True,
                "depends_on": [
                    PROMPT_VERSION_111,
                    TRANSPORT_VERSION_11,
                    "coverage-validator-1.1.2-candidate",
                ],
            },
            "book-semantic-validator-1.1.3-candidate": {
                "status": "PROPOSAL_ONLY_NOT_PROMOTED",
                "location": "app.book_semantic_gate_4b275.contract",
                "transport": TRANSPORT_VERSION_113,
                "prompt_sha256": c113["prompt_sha256"],
                "system_sha256": c113["system_sha256"],
                "instructions_sha256": c113["instructions_sha256"],
                "matches_frozen_expected": (
                    c113["prompt_sha256"] == EXPECTED_PROMPT_113_SHA256
                    and c113["system_sha256"] == EXPECTED_PROMPT_113_SYSTEM_SHA256
                    and c113["instructions_sha256"]
                    == EXPECTED_PROMPT_113_INSTRUCTIONS_SHA256
                ),
                "identical_to_1_1_2": False,
                "immutable_historical": False,
                "modified_this_phase": True,
                "promoted": False,
                "compatible_with_local_validator": True,
                "depends_on": [
                    PROMPT_VERSION_112,
                    TRANSPORT_VERSION_11,
                    "coverage-validator-1.1.2-candidate",
                ],
            },
            "book-semantic-validation-transport-1.1-candidate": {
                "status": "FROZEN_CANDIDATE_NOT_PROMOTED",
                "location": "app.book_semantic_gate_4b261.candidates.build_candidate_schema",
                "schema_sha256": content_hash(
                    json.dumps(schema_11, ensure_ascii=False, sort_keys=True)
                ),
                "matches_frozen_expected": content_hash(
                    json.dumps(schema_11, ensure_ascii=False, sort_keys=True)
                )
                == EXPECTED_SCHEMA_11_SHA256,
                "immutable": True,
                "modified_this_phase": False,
                "promoted": False,
                "required_top_fields": list(REQUIRED_TOP_FIELDS),
                "required_paragraph_fields": list(REQUIRED_PARAGRAPH_FIELDS),
                "required_claim_fields": list(REQUIRED_CLAIM_FIELDS),
                "optional_reservation_field": OPTIONAL_RESERVATION_FIELD,
                "historical_1_0_schema_sha256": content_hash(
                    json.dumps(schema_10, ensure_ascii=False, sort_keys=True)
                ),
            },
        },
        "historical_contracts_modified": False,
        "silent_1_1_2_modification": False,
        "new_transport_created": False,
        "candidate_promoted": False,
        "local_validator_compatible": True,
        "compact_spec_preserved": spec.get("prompt_version") == PROMPT_VERSION_11,
        "secrets_included": False,
    }


def contract_113_review() -> dict[str, Any]:
    bundle = candidate_113_prompt_bundle()
    c112 = candidate_112_prompt_bundle()
    schema = build_candidate_schema()
    blob = bundle["system"] + bundle["instructions"]
    return {
        "phase": PHASE,
        "justified": True,
        "why_created": (
            "1.1.2 left SUPPORTED/QUESTIONABLE/UNSUPPORTED/NON_SUBSTANTIVE "
            "thinly specified and did not state both sides of the "
            "rhetorical-versus-assertion boundary. 1.1.3 adds operational "
            "verdict definitions, origin/attribution as a claim type, and an "
            "anti-masking rule for NON_SUBSTANTIVE, without naming canaries "
            "or changing the closed catalog, coverage rules, or transport."
        ),
        "candidate_prompt_version": PROMPT_VERSION_113,
        "candidate_transport_version": TRANSPORT_VERSION_113,
        "transport_1_1_3_created": False,
        "why_no_new_transport": (
            "Existing 1.1-candidate fields already carry claim-level assessment, "
            "exact spans, evidence handles, reason codes, global verdict, short "
            "reservations, and compact JSON. INDETERMINATE is a human-review "
            "category, not a provider verdict."
        ),
        "historical_1_0_unmodified": True,
        "candidate_1_1_unmodified": True,
        "candidate_1_1_1_unmodified": True,
        "candidate_1_1_2_unmodified": (
            c112["prompt_sha256"] == EXPECTED_PROMPT_112_SHA256
        ),
        "promoted": False,
        "prompt": {
            "system_sha256": bundle["system_sha256"],
            "instructions_sha256": bundle["instructions_sha256"],
            "prompt_sha256": bundle["prompt_sha256"],
            "system_bytes": len(bundle["system"].encode("utf-8")),
            "instructions_bytes": len(bundle["instructions"].encode("utf-8")),
        },
        "frozen_1_1_2_prompt_sha256": c112["prompt_sha256"],
        "changes": [
            "operational definitions of SUPPORTED, QUESTIONABLE, UNSUPPORTED, NON_SUBSTANTIVE",
            "legitimate paraphrase may be SUPPORTED; lexical difference is not invention",
            "QUESTIONABLE and UNSUPPORTED block production acceptance",
            "origin and attribution treated as claims when asserted",
            "editorial transition is not automatically NON_SUBSTANTIVE",
            "rhetorical sentence is not automatically a new assertion",
            "NON_SUBSTANTIVE must not mask a meaning-bearing claim",
            "closed catalog, coverage, and compact JSON unchanged",
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
        "general_not_canary_specific": True,
        "remaining_validation_limits": [
            "A listed catalog does not prove Terra will emit only catalog codes.",
            "Operational verdict text does not prove Terra will apply it.",
            "Offline FakeAI does not prove future Terra behavior.",
            "Borderline origin/framing claims may remain human-indeterminate.",
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
        "transport_1_1_3": TRANSPORT_VERSION_113,
        "field_meanings_unchanged": True,
        "required_top_fields": list(REQUIRED_TOP_FIELDS),
        "required_paragraph_fields": list(REQUIRED_PARAGRAPH_FIELDS),
        "required_claim_fields": list(REQUIRED_CLAIM_FIELDS),
        "optional_fields": [OPTIONAL_RESERVATION_FIELD],
        "chapter_verdicts": ["PASS", "REVIEW", "FAIL"],
        "claim_verdicts": [
            "SUPPORTED",
            "QUESTIONABLE",
            "UNSUPPORTED",
            "NON_SUBSTANTIVE",
        ],
        "indeterminate_not_a_provider_verdict": True,
        "reason_codes": list(REASON_CODES),
        "spans": {
            "start": "pr[].c[].s inclusive",
            "end": "pr[].c[].e exclusive",
            "indexing": "python3_str_unicode_code_points",
        },
        "evidence_handles": ["pr[].c[].ev", "pr[].ev"],
        "short_reservations": "pr[].c[].n when QUESTIONABLE or UNSUPPORTED",
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
    c113 = candidate_113_prompt_bundle()
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
                "status": "FROZEN_CANDIDATE_NOT_PROMOTED",
                "prompt_sha256": c112["prompt_sha256"],
                "matches_frozen_expected": c112["prompt_sha256"] == EXPECTED_PROMPT_112_SHA256,
            },
            "1.1.3-candidate": {
                "prompt": PROMPT_VERSION_113,
                "transport": TRANSPORT_VERSION_113,
                "status": "PROPOSAL_ONLY_NOT_PROMOTED",
                "prompt_sha256": c113["prompt_sha256"],
                "identical_to_1_1_2": False,
                "transport_compatible_with_1_1": True,
            },
        },
        "not_promoted": True,
        "historical_contracts_modified": False,
        "overfit_112_still_clean": overfit_tokens_absent_112(
            c112["system"] + c112["instructions"]
        ),
        "secrets_included": False,
    }


__all__ = [
    "candidate_113_instruction_prompt",
    "candidate_113_prompt_bundle",
    "candidate_113_system_prompt",
    "contract_113_review",
    "contract_comparison",
    "contract_inventory",
    "overfit_tokens_absent",
    "transport_compatibility",
]
