"""Évaluation des options de politique de longueur. Offline. Pas d'implémentation."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v31_length_ceiling.constants import (
    MODE,
    PHASE,
    SCHEMA_VERSION,
    WIN003_COST_USD,
    WIN003_ELAPSED_MS,
)


def build_options(
    *,
    offenders: Mapping[str, Any],
    classification: Mapping[str, Any],
    counterfactual: Mapping[str, Any],
    boundary: Mapping[str, Any],
) -> dict[str, Any]:
    idea_already_legal = bool(classification.get("idea_already_legal_under_280"))
    theme_chars = int(offenders["theme"]["chars"])
    example_chars = int(offenders["example"]["chars"])
    idea_chars = int(offenders["idea"]["chars"])
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "options": {
            "A": {
                "name": "Keep 200 universally and harden prompt",
                "verdict": "REJECT",
                "why": (
                    "200 is not universal today. IDEA.v is 280; intent/aud are 280. "
                    "Forcing 200 on IDEA would make the currently legal 209-char "
                    "IDEA fail. Prompt 1.4.0 never stated theme/EXAMPLE 200; a "
                    "1.4.1 harden would still require a paid WIN003 retry."
                ),
            },
            "B": {
                "name": "Raise universal ceiling modestly",
                "verdict": "REJECT_AS_STATED",
                "why": (
                    "A universal raise would also move IDEA.v (280) or flatten "
                    "kind-specific limits. Evidence supports raising only the "
                    "two 200-capped fields that actually failed."
                ),
            },
            "C": {
                "name": "Use kind-specific ceilings",
                "verdict": "SELECT",
                "why": (
                    "Already the architecture. Production: theme=200, EXAMPLE.v=200, "
                    "IDEA.v=280, TOPIC.v=80, RELATION.v=40, REFERENCE.v=220. "
                    "Minimum change: theme=225, EXAMPLE.v=225, IDEA.v remains 280."
                ),
                "proposed": {
                    "theme": 225,
                    "EXAMPLE.v": 225,
                    "IDEA.v": 280,
                    "TOPIC.v": 80,
                    "RELATION.v": 40,
                    "REFERENCE.v": 220,
                    "UNCERTAINTY.v": 280,
                    "intent": 280,
                    "aud": 280,
                },
            },
            "D": {
                "name": "Keep transport permissive but enforce a softer semantic-quality policy",
                "verdict": "PARTIAL_ALREADY_TRUE",
                "why": (
                    "Transport schema is already permissive (no maxLength). Soft "
                    "quality-only enforcement would accept 212/213 without a "
                    "versioned hard gate. Rejected as the sole policy: length "
                    "still needs a hard local bound, just not 200 for theme/EXAMPLE."
                ),
            },
            "E": {
                "name": "Split/compress overlong records deterministically",
                "verdict": "REJECT",
                "why": (
                    "Deterministic truncation/compression/splitting is silent "
                    "semantic repair. It would violate no-repair, semantic "
                    "fidelity, and traceability. Default remains no silent repair."
                ),
                "violates": [
                    "no repair",
                    "semantic fidelity",
                    "traceability",
                ],
                "determinism": (
                    "A split heuristic can be deterministic but still invents "
                    "new record boundaries the model did not emit."
                ),
            },
            "F": {
                "name": "Reject and retry provider output",
                "verdict": "REJECT",
                "why": (
                    f"WIN003 cost {WIN003_COST_USD} USD / {WIN003_ELAPSED_MS} ms "
                    f"for theme {theme_chars} and EXAMPLE {example_chars} "
                    f"({theme_chars - 200}/{example_chars - 200} extra chars). "
                    f"IDEA {idea_chars} is already legal. Retrying an otherwise "
                    "excellent parse for 9–13 characters is not justified."
                ),
                "retry_not_executed": True,
            },
        },
        "repair_policy": {
            "option_e_justified": False,
            "default": "no silent semantic repair",
            "implemented": False,
        },
        "retry_policy": {
            "economically_justified": False,
            "architecturally_justified": False,
            "cost_usd": WIN003_COST_USD,
            "elapsed_ms": WIN003_ELAPSED_MS,
            "retry_executed": False,
        },
        "false_fail": {
            "class": "LIKELY_FALSE_NEGATIVE_FROM_OVERSTRICT_LIMIT",
            "not": [
                "TRUE_SEMANTIC_FAILURE",
                "TRUE_STRUCTURAL_FAILURE",
            ],
            "also": "POLICY_FAILURE",
            "explanation": (
                "Provider finished normally. Parse/decoder/handles/SRC/metadata "
                "passed. Rejection is the 200-character local validator on theme "
                "and EXAMPLE. A.28 skipped semantic review because the technical "
                "gate failed. Counterfactual 225+ is technically clean. IDEA 209 "
                f"is not a production failure (limit 280). idea_already_legal="
                f"{idea_already_legal}."
            ),
        },
        "provider_schema_enforces_200": boundary.get("provider_schema_enforces_200"),
        "canonical_model_requires_200": boundary.get("canonical_model_requires_200"),
        "counterfactual_225": counterfactual.get("counterfactual_225"),
        "counterfactual_250": counterfactual.get("counterfactual_250"),
        "counterfactual_300": counterfactual.get("counterfactual_300"),
    }


__all__ = ["build_options"]
