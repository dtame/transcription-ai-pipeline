"""Distribution des longueurs d'intent. Données existantes seulement."""

from __future__ import annotations

from typing import Any

from app.source_analysis_v31_global_a47_contract_forensics.constants import A46_INTENT_LENGTH
from app.source_analysis_v31_global_grammar_canary.fixture import expected_valid_transport
from app.source_analysis_v31_global_v20_grammar_canary.fixture import expected_valid_transport_v20
from app.source_analysis_v31_global_v30_grammar_canary.fixture import expected_valid_transport_v30


def _intent_len(payload: dict[str, Any]) -> int:
    gm = payload.get("gm") if isinstance(payload.get("gm"), dict) else {}
    return len(str(gm.get("in") or ""))


def intent_length_distribution(*, a46_intent: str) -> dict[str, Any]:
    synthetic = {
        "v10_grammar_canary": _intent_len(expected_valid_transport()),
        "v20_grammar_canary": _intent_len(expected_valid_transport_v20()),
        "v30_grammar_canary": _intent_len(expected_valid_transport_v30()),
    }
    values = list(synthetic.values()) + [len(a46_intent)]
    return {
        "synthetic_canaries": synthetic,
        "a46": {"length": len(a46_intent), "expected": A46_INTENT_LENGTH},
        "historical_global_attempts_parseable": {
            "A.35": "tiny grammar; not production intent",
            "A.38": "max_tokens truncated JSON — gm.in not parseable",
            "A.40": "compact grammar canary; synthetic garden intent",
            "A.42": "compact contract canary; synthetic garden intent",
            "A.44": "v3.0 grammar canary; synthetic garden intent",
            "A.46": len(a46_intent),
        },
        "min": min(values),
        "max": max(values),
        "observation": (
            "Synthetic canary intents are workshop-scale (~60 chars). "
            "The only real production global intent observed is A.46 at 290."
        ),
    }


__all__ = ["intent_length_distribution"]
