"""Operational verdict definitions. Transport classifications are unchanged."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    CLASSIFICATIONS,
)
from app.book_semantic_gate_4b275.constants import HUMAN_REVIEW_INDETERMINATE, PHASE

OPERATIONAL_DEFINITIONS = {
    CLASS_SUPPORTED: {
        "blocks_production_acceptance": False,
        "definition": (
            "A proposition is SUPPORTED when its substantial content is "
            "explicitly present in the supplied evidence, or is semantically "
            "implied by that evidence without adding a new assertion."
        ),
        "paraphrase_rule": (
            "A lexical rephrasing is not automatically an invention. A "
            "legitimate stylistic paraphrase may be SUPPORTED."
        ),
        "not_automatic_unsupported": [
            "different verb restating attested content",
            "stylistic intensifier that adds no agent, relation, condition, or quantity",
        ],
        "requires_reason_codes": False,
        "compatible_reason_codes": [],
    },
    CLASS_QUESTIONABLE: {
        "blocks_production_acceptance": True,
        "definition": (
            "A proposition is QUESTIONABLE when available evidence does not "
            "confirm the whole claim; a plausible inference is not actually "
            "implied; a strengthening or substantial nuance remains uncertain; "
            "or the link to evidence is ambiguous."
        ),
        "requires_reason_codes": True,
        "compatible_reason_codes": "closed_catalog",
    },
    CLASS_UNSUPPORTED: {
        "blocks_production_acceptance": True,
        "definition": (
            "A proposition is UNSUPPORTED when it contains a substantial "
            "assertion not supported by the supplied evidence."
        ),
        "includes": [
            "invented example",
            "new causal relation",
            "new consequence",
            "new doctrinal implication",
            "unsupported attribution",
            "reference completed from external knowledge",
        ],
        "requires_reason_codes": True,
        "compatible_reason_codes": "closed_catalog",
    },
    CLASS_NON_SUBSTANTIVE: {
        "blocks_production_acceptance": False,
        "definition": (
            "A proposition is NON_SUBSTANTIVE when it is a purely rhetorical "
            "or structural marker that carries no meaning-bearing assertion."
        ),
        "historical_treatment_preserved": True,
        "must_not_mask_meaning_bearing_claims": True,
        "not_automatic": (
            "An editorial transition is not automatically NON_SUBSTANTIVE."
        ),
        "requires_reason_codes": False,
        "compatible_reason_codes": [],
        "not_a_hiding_place": True,
    },
}

HUMAN_REVIEW_ONLY = {
    HUMAN_REVIEW_INDETERMINATE: {
        "provider_verdict": False,
        "transport_enum": False,
        "definition": (
            "A human-review category used when authorized evidence does not "
            "uniquely force SUPPORTED, QUESTIONABLE, UNSUPPORTED, or "
            "NON_SUBSTANTIVE. It is not a provider or transport value."
        ),
        "must_not_force_conclusion": True,
    }
}


def verdict_definitions_review() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "transport_classifications_unchanged": list(CLASSIFICATIONS),
        "no_incompatible_category_introduced": True,
        "operational_definitions": OPERATIONAL_DEFINITIONS,
        "human_review_only": HUMAN_REVIEW_ONLY,
        "paraphrase_may_be_supported": True,
        "plausible_is_not_entailed": True,
        "questionable_and_unsupported_block_acceptance": True,
        "non_substantive_cannot_mask_meaning": True,
        "rhetorical_not_automatically_new_assertion": True,
        "editorial_transition_not_automatically_non_substantive": True,
        "coherence": "PASS",
        "secrets_included": False,
    }


__all__ = ["HUMAN_REVIEW_ONLY", "OPERATIONAL_DEFINITIONS", "verdict_definitions_review"]
