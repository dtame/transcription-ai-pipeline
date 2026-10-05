"""Architecture C implementation notes. Isolated candidate. Not production."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b29.constants import (
    OFFSET_CONVENTION,
    PHASE,
    PROMPT_VERSION_20_CANDIDATE,
    TARGET_ARCHITECTURE,
    TRANSPORT_VERSION_20_CANDIDATE,
)


def architecture_implementation() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "target": TARGET_ARCHITECTURE,
        "module": "app.book_semantic_gate_4b29",
        "production_connected": False,
        "flow": [
            "Generated paragraph",
            "Deterministic preparation",
            "Validation units + compact context + evidence",
            "Semantic model interface (injected transport)",
            "Model verdicts by unit_id",
            "Deterministic contract validation",
            "Semantic acceptance policy",
            "PASS / BLOCK / REVIEW",
        ],
        "components": {
            "A_preparation": "app.book_semantic_gate_4b29.preparation (reuses 4b28 segmentation)",
            "coverage": "app.book_semantic_gate_4b29.coverage",
            "B_interface": "app.book_semantic_gate_4b29.interface + fakeai",
            "contract": PROMPT_VERSION_20_CANDIDATE,
            "transport": TRANSPORT_VERSION_20_CANDIDATE,
            "C_validator": "app.book_semantic_gate_4b29.validator",
            "policy": "app.book_semantic_gate_4b29.policy",
            "engine": "app.book_semantic_gate_4b29.engine",
        },
        "independence": True,
        "each_step_testable": True,
        "provider_requires_explicit_injection": True,
        "offset_convention": OFFSET_CONVENTION,
        "model_does_not_own_offsets": True,
        "book_validator_not_replaced": True,
        "secrets_included": False,
    }


__all__ = ["architecture_implementation"]
