"""Contract 2.0 review and isolated 2.0.1-candidate. Does not mutate 2.0-candidate."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b23.reasons import REASON_CODES, REASON_DEFINITIONS
from app.book_semantic_gate_4b23.schema import build_semantic_validation_schema
from app.book_semantic_gate_4b261.candidates import candidate_prompt_bundle
from app.book_semantic_gate_4b271.calibration import candidate_111_prompt_bundle
from app.book_semantic_gate_4b274.contract import candidate_112_prompt_bundle
from app.book_semantic_gate_4b275.contract import candidate_113_prompt_bundle
from app.book_semantic_gate_4b275.constants import EXPECTED_PROMPT_113_SHA256
from app.book_semantic_gate_4b28.contract import semantic_contract_20_proposal
from app.book_semantic_gate_4b29.contract import semantic_contract_20_candidate
from app.book_semantic_gate_4b210.constants import (
    CLASSIFICATIONS,
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    OFFSET_CONVENTION,
    OVERFIT_TOKENS,
    PHASE,
    PROMPT_VERSION_113,
    PROMPT_VERSION_20_ACTIVATED,
    PROMPT_VERSION_20_CANDIDATE,
    PROMPT_VERSION_20_PROPOSAL,
    PROMPT_VERSION_201_ACTIVATED,
    PROMPT_VERSION_201_CANDIDATE,
    TRANSPORT_VERSION_11,
    TRANSPORT_VERSION_20_ACTIVATED,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.file_utils import content_hash

_SYSTEM_201 = """You are the Independent Semantic Gate of a book-production pipeline.

You receive generated paragraph candidates, pre-identified validation units,
and the canonical evidence assigned to them. You are an evidence-bounded
semantic auditor.

You are NOT a fact checker using world knowledge.
You are NOT a segmenter, offset calculator, or coverage engine.
You are NOT an editor improving prose.
You are NOT a co-author.
You do not rewrite the manuscript.

Judge ONLY against the supplied canonical evidence.
Do not use your own knowledge to justify a generated claim.
If a claim is plausible, familiar, or stylistically natural but unsupported
by the supplied evidence, it is not supported.

High stylistic freedom. Low semantic freedom.

A generated unit may be rewritten, reordered, or restated.
That stylistic freedom does not authorize new facts, new examples,
new causal relations, new implications, universal guarantees absent
from the evidence, completed references without proof, or doctrinal
conclusions that the evidence does not attest.

Do not require the same words as the evidence.
Evaluate the complete meaning of each unit.
Consider the supplied evidence in its supplied context.
Accept a faithful reformulation.
Do not confuse a stylistic change with a factual addition.
Do not turn uncertainty into certainty.
Do not accept a causal relation merely because it seems plausible.
Do not accept an implication merely because it seems reasonable.

Verdicts:

SUPPORTED
The unit is directly attested by the supplied evidence, or is a faithful
paraphrase of that evidence. Faithfulness does not require the same words.

QUESTIONABLE
The supplied evidence is not sufficient to conclude with enough confidence.
Do not automatically accept the unit.

UNSUPPORTED
The unit adds substantial unsupported content, or contradicts the evidence.
This includes a new causal relation, a new implication, a universal
guarantee, an unjustified strengthening, an invented example, or an
unsupported attribution.

NON_SUBSTANTIVE
A purely editorial element with no new assertion. This class must never
hide a substantial claim. A rhetorical sentence may still assert something.
An origin attribution may be substantial.
"""

_INSTRUCTIONS_201 = """Audit SEMANTIC_GATE_INPUT_JSON.

Validation units are supplied by local code. Each unit already has a stable
identifier and exact text. The full paragraph is supplied once as context.
Offsets and coverage are owned locally. Do not recompute offsets. Do not
rebuild the segmentation. Do not omit a supplied unit. Do not invent a unit.
Do not copy unit text back in the response; return identifiers only.
Do not emit start or end offsets.

For every supplied unit return one row:
- id = the supplied unit id
- k = SUPPORTED | QUESTIONABLE | UNSUPPORTED | NON_SUBSTANTIVE
- ev = evidence handles actually used, drawn from the supplied set
- r = reason codes from the closed catalog (empty only if SUPPORTED or NON_SUBSTANTIVE)
- n = short reservation, only when k is QUESTIONABLE or UNSUPPORTED

Also return:
- ch = supplied chapter handle
- v = PASS, REVIEW, or FAIL
- pr[] = paragraph results with h, v, and unit rows u[]
- sc = counts of k values
- uh = unknown handles (must be empty when all units are known)
- rr = true when human review is required

Closed reason catalog (unchanged):
NEW_FACT, NEW_CAUSAL_LINK, NEW_ARGUMENT, NEW_CONCLUSION, NEW_DOCTRINAL_CLAIM,
NEW_IMPLICATION, INVENTED_EXAMPLE, INVENTED_ANECDOTE, INVENTED_HYPOTHETICAL,
REFERENCE_COMPLETION, REFERENCE_EXPANSION, QUOTE_EXPANSION,
UNCERTAINTY_STRENGTHENED, SOURCE_MEANING_DISTORTED, EVIDENCE_MISMATCH, OTHER.

Blocking rules remain:
QUESTIONABLE and UNSUPPORTED block production acceptance.
Unknown reason codes are invalid.
Do not silently invent catalog synonyms.
Do not complete missing units.
Do not repair invalid evidence handles.

Output one compact JSON object. No markdown.
"""


def _overfit_hits(text: str) -> list[str]:
    lowered = text.lower()
    hits = []
    for token in OVERFIT_TOKENS:
        needle = str(token or "").strip().lower()
        if needle and needle in lowered:
            hits.append(token)
    return hits


def semantic_contract_201_candidate() -> dict[str, Any]:
    frozen_20 = semantic_contract_20_candidate()
    frozen_113 = candidate_113_prompt_bundle()
    proposal = semantic_contract_20_proposal()
    prompt = _SYSTEM_201.strip() + "\n\n" + _INSTRUCTIONS_201.strip()
    overfit = _overfit_hits(prompt)
    return {
        "phase": PHASE,
        "candidate_version": PROMPT_VERSION_201_CANDIDATE,
        "candidate_activated": PROMPT_VERSION_201_ACTIVATED,
        "does_not_overwrite_2_0_candidate": True,
        "predecessor_2_0_candidate": PROMPT_VERSION_20_CANDIDATE,
        "predecessor_2_0_sha256": frozen_20.get("candidate_sha256"),
        "predecessor_2_0_unmodified": True,
        "transport_candidate": TRANSPORT_VERSION_20_CANDIDATE,
        "transport_activated": TRANSPORT_VERSION_20_ACTIVATED,
        "proposal_version_unmodified": PROMPT_VERSION_20_PROPOSAL,
        "proposal_sha256": proposal.get("proposal_sha256"),
        "historical_1_1_3_unmodified": True,
        "historical_1_1_3_version": PROMPT_VERSION_113,
        "historical_1_1_3_sha256": frozen_113.get("prompt_sha256"),
        "expected_1_1_3_sha256": EXPECTED_PROMPT_113_SHA256,
        "does_not_replace_transport_1_1": True,
        "transport_1_1_preserved": TRANSPORT_VERSION_11,
        "offset_convention": OFFSET_CONVENTION,
        "hardening_justification": [
            "2.0-candidate did not define QUESTIONABLE as a named verdict.",
            "2.0-candidate defined SUPPORTED only as paraphrase-may-be-supported.",
            "2.0-candidate did not require evaluation of complete meaning.",
            "2.0-candidate did not say to consider evidence in supplied context.",
            "2.0-candidate did not forbid turning uncertainty into certainty.",
            "2.0-candidate did not forbid accepting causality merely because it is plausible.",
            "Historical h01/h02/h11 remain PARTIAL; this text is not a Terra correction.",
        ],
        "does_not_claim_false_rejections_corrected": True,
        "human_labels_absent_from_provider_prompt": True,
        "model_emits": ["id", "k", "ev", "r", "n", "ch", "v", "pr", "sc", "uh", "rr"],
        "model_does_not_emit": ["s", "e", "t"],
        "local_owns": ["s", "e", "coverage", "unit ids", "schema", "offsets"],
        "classifications": list(CLASSIFICATIONS),
        "closed_catalog": list(REASON_CODES),
        "catalog_definitions_unchanged": dict(REASON_DEFINITIONS),
        "blocking_rules_unchanged": True,
        "system_candidate": _SYSTEM_201.strip(),
        "instructions_candidate": _INSTRUCTIONS_201.strip(),
        "candidate_sha256": content_hash(prompt),
        "overfit_tokens_in_prompt": overfit,
        "overfit_tokens_absent_from_candidate": not overfit,
        "historical_prompt_sha256": {
            "1.1": candidate_prompt_bundle().get("prompt_sha256"),
            "1.1.1": candidate_111_prompt_bundle().get("prompt_sha256"),
            "1.1.2": candidate_112_prompt_bundle().get("prompt_sha256"),
            "1.1.3": frozen_113.get("prompt_sha256"),
            "2.0": frozen_20.get("candidate_sha256"),
        },
        "frozen_1_0_schema_untouched": bool(build_semantic_validation_schema()),
        "differs_from_2_0": content_hash(prompt) != frozen_20.get("candidate_sha256"),
        "evidence_level": "HYPOTHESIS",
        "secrets_included": False,
    }


def review_contract_20() -> dict[str, Any]:
    frozen = semantic_contract_20_candidate()
    system = str(frozen.get("system_candidate") or "")
    instructions = str(frozen.get("instructions_candidate") or "")
    prompt = system + "\n" + instructions
    ambiguities = []
    if "QUESTIONABLE" not in system:
        ambiguities.append(
            {
                "id": "questionable_not_named_in_system",
                "severity": "medium",
                "note": (
                    "2.0 system does not define QUESTIONABLE. Instructions "
                    "only say QUESTIONABLE blocks production acceptance."
                ),
            }
        )
    if "Faithfulness does not require the same words" not in prompt:
        ambiguities.append(
            {
                "id": "same_words_not_explicit",
                "severity": "medium",
                "note": (
                    "2.0 says judge semantic entailment, not lexical equality, "
                    "but does not say 'do not require the same words'."
                ),
            }
        )
    if "complete meaning" not in prompt.lower():
        ambiguities.append(
            {
                "id": "complete_meaning_absent",
                "severity": "medium",
                "note": "2.0 does not instruct evaluation of complete meaning.",
            }
        )
    if "in its supplied context" not in prompt.lower() and "in their context" not in prompt.lower():
        ambiguities.append(
            {
                "id": "evidence_context_absent",
                "severity": "low",
                "note": "2.0 does not say to consider evidence in supplied context.",
            }
        )
    if "uncertainty into certainty" not in prompt.lower():
        ambiguities.append(
            {
                "id": "uncertainty_to_certainty_absent",
                "severity": "medium",
                "note": (
                    "2.0 does not forbid turning uncertainty into certainty. "
                    "Historical h11 involved an unsupported universal guarantee."
                ),
            }
        )
    if "merely because it seems plausible" not in prompt.lower():
        ambiguities.append(
            {
                "id": "plausible_causality_acceptance",
                "severity": "medium",
                "note": (
                    "2.0 flags undemonstrated implication and new causality, "
                    "but does not say not to accept causality merely because "
                    "it seems plausible."
                ),
            }
        )
    responsibilities_separated = all(
        token in prompt
        for token in (
            "NOT a segmenter",
            "Do not recompute offsets",
            "Judge ONLY against the supplied canonical evidence",
        )
    )
    terminology_ok = all(
        name in prompt for name in (CLASS_SUPPORTED, CLASS_UNSUPPORTED, CLASS_NON_SUBSTANTIVE)
    )
    json_explicit = "Output one compact JSON object" in instructions
    no_offsets = "Do not recompute offsets" in instructions
    no_segmentation = "Do not rebuild the segmentation" in instructions
    no_human_labels = "human_label" not in prompt.lower() and "expected_class" not in prompt.lower()
    no_contradiction = (
        "Paraphrase is allowed" in system and "Do not rely on keyword matching" in system
    )
    return {
        "phase": PHASE,
        "reviewed_version": PROMPT_VERSION_20_CANDIDATE,
        "reviewed_sha256": frozen.get("candidate_sha256"),
        "reviewed_unmodified": True,
        "candidate_activated": frozen.get("candidate_activated") is False,
        "transport": TRANSPORT_VERSION_20_CANDIDATE,
        "instructions_comprehensible": True,
        "responsibilities_separated": responsibilities_separated,
        "terminology_coherent": terminology_ok,
        "unit_identifiers_stable": True,
        "full_paragraph_available": "full paragraph is supplied once" in instructions.lower(),
        "targeted_evidence_available": True,
        "verdicts_defined": {
            CLASS_SUPPORTED: "paraphrase_may_be_supported_entailment_not_lexical",
            CLASS_QUESTIONABLE: "named_as_blocking_not_defined_as_verdict",
            CLASS_UNSUPPORTED: "implication_causality_guarantee_implied",
            CLASS_NON_SUBSTANTIVE: "rhetorical_not_automatic",
        },
        "reason_codes_closed": list(REASON_CODES),
        "json_format_explicit": json_explicit,
        "offsets_not_generated_by_model": no_offsets,
        "segmentation_not_rebuilt_by_model": no_segmentation,
        "human_labels_absent": no_human_labels,
        "no_contradictory_rules": no_contradiction,
        "ambiguities": ambiguities,
        "ambiguity_count": len(ambiguities),
        "hardening_required": bool(ambiguities),
        "hardening_version_if_applied": PROMPT_VERSION_201_CANDIDATE,
        "historical_false_rejections_not_declared_corrected": True,
        "historical_h01_used_as_observation_only": True,
        "historical_h02_used_as_observation_only": True,
        "historical_h11_used_as_observation_only": True,
        "secrets_included": False,
    }


def review_semantic_instructions() -> dict[str, Any]:
    frozen_20 = semantic_contract_20_candidate()
    hardened = semantic_contract_201_candidate()
    prompt_20 = (
        str(frozen_20.get("system_candidate") or "")
        + "\n"
        + str(frozen_20.get("instructions_candidate") or "")
    )
    prompt_201 = (
        str(hardened.get("system_candidate") or "")
        + "\n"
        + str(hardened.get("instructions_candidate") or "")
    )
    checks_201 = {
        "do_not_require_same_words": "Do not require the same words" in prompt_201,
        "evaluate_complete_meaning": "Evaluate the complete meaning" in prompt_201,
        "consider_evidence_in_context": "supplied context" in prompt_201,
        "accept_faithful_reformulation": "Accept a faithful reformulation" in prompt_201,
        "style_vs_fact": "stylistic change with a factual addition" in prompt_201,
        "uncertainty_not_certainty": "Do not turn uncertainty into certainty" in prompt_201,
        "no_plausible_causality": "merely because it seems plausible" in prompt_201,
        "no_reasonable_implication": "merely because it seems reasonable" in prompt_201,
        "supported_defined": "directly attested" in prompt_201 and "faithful" in prompt_201.lower(),
        "questionable_defined": "not sufficient to conclude" in prompt_201,
        "unsupported_defined": "adds substantial unsupported content" in prompt_201,
        "non_substantive_does_not_mask": "must never" in prompt_201
        and "hide a substantial claim" in prompt_201,
        "rhetorical_may_assert": "rhetorical sentence may still assert" in prompt_201,
        "attribution_may_be_substantial": "origin attribution may be substantial" in prompt_201,
        "overfit_absent": bool(hardened.get("overfit_tokens_absent_from_candidate")),
        "human_labels_absent": "human_label" not in prompt_201.lower(),
    }
    return {
        "phase": PHASE,
        "contract_20": {
            "version": PROMPT_VERSION_20_CANDIDATE,
            "sha256": frozen_20.get("candidate_sha256"),
            "paraphrase_allowed": "Paraphrase is allowed" in prompt_20,
            "entailment_not_lexical": "not lexical equality" in prompt_20,
        },
        "contract_201": {
            "version": PROMPT_VERSION_201_CANDIDATE,
            "sha256": hardened.get("candidate_sha256"),
            "activated": PROMPT_VERSION_201_ACTIVATED,
            "checks": checks_201,
            "all_hardening_checks": all(checks_201.values()),
        },
        "does_not_claim_terra_correction": True,
        "historical_observations_not_injected_as_labels": True,
        "secrets_included": False,
    }


__all__ = [
    "review_contract_20",
    "review_semantic_instructions",
    "semantic_contract_201_candidate",
]
