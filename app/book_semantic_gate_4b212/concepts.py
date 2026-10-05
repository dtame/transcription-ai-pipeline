"""Formal split of semantic classification, operational decision, and technical conformance."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b212.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    DECISION_BLOCK,
    DECISION_PASS,
    DECISION_REVIEW,
    OPERATIONAL_DECISIONS,
    PHASE,
    SEMANTIC_CLASSIFICATIONS,
    TECHNICAL_CONFORMANCE,
)


def semantic_vs_operational_verdicts() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "concepts": {
            "A_semantic_classification": {
                "name": "semantic_classification",
                "values": list(SEMANTIC_CLASSIFICATIONS),
                "owner": "model",
                "describes": "Relation between a proposition and the supplied evidence.",
                "fields": ["pr[].u[].k"],
                "definitions": {
                    CLASS_SUPPORTED: (
                        "Directly attested by supplied evidence, or a faithful paraphrase."
                    ),
                    CLASS_QUESTIONABLE: (
                        "Supplied evidence is not sufficient to conclude with confidence."
                    ),
                    CLASS_UNSUPPORTED: (
                        "Adds substantial unsupported content, or contradicts the evidence."
                    ),
                    CLASS_NON_SUBSTANTIVE: (
                        "Purely editorial element with no new assertion. Must never hide a claim."
                    ),
                },
            },
            "B_operational_decision": {
                "name": "operational_decision",
                "values": list(OPERATIONAL_DECISIONS),
                "owner": "python",
                "describes": "What the system must do after validation.",
                "fields": [],
                "not_emitted_by_model": True,
                "definitions": {
                    DECISION_PASS: "Contract valid, coverage complete, all substantive units SUPPORTED.",
                    DECISION_REVIEW: (
                        "Contract valid, one or more QUESTIONABLE units, no UNSUPPORTED, "
                        "no technical block. Does not accept the production cache."
                    ),
                    DECISION_BLOCK: (
                        "Invalid contract, coverage, evidence, UNSUPPORTED, or critical anomaly."
                    ),
                },
            },
            "C_technical_conformance": {
                "name": "technical_conformance",
                "values": list(TECHNICAL_CONFORMANCE),
                "owner": "validator",
                "describes": "Whether the response respects the contract.",
                "fields": [],
                "not_emitted_by_model": True,
                "definitions": {
                    "VALID": "Payload matches the contract exactly.",
                    "INVALID": "Missing, unknown, mistyped, or incoherent contract content.",
                },
            },
        },
        "mixing_forbidden": True,
        "model_must_not_emit_operational_values": True,
        "python_computes_operational_decision": True,
        "validator_owns_technical_conformance": True,
        "historical_confusion": {
            "top_level_v": "2.0.1 asked the model for PASS/REVIEW/FAIL.",
            "paragraph_v": (
                "2.0.1 schema required a semantic classification, but the "
                "instructions did not say so. Terra emitted PASS."
            ),
            "sc_keys": (
                "2.0.1 schema required lowercase count keys. Instructions said "
                "counts of k values, which are uppercase."
            ),
        },
        "consolidated_rule": (
            "The model emits only semantic classifications and required "
            "justifications. Python computes PASS/BLOCK/REVIEW. The validator "
            "reports VALID/INVALID. No silent conversion between these spaces."
        ),
        "secrets_included": False,
    }


__all__ = ["semantic_vs_operational_verdicts"]
