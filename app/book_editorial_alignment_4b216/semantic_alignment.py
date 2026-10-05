"""
How the candidate editorial policy is used to read Semantic Gate results.

Does not modify book-semantic-validator-2.0.2-candidate.
Does not rewrite historical h11 labels.
"""

from __future__ import annotations

from typing import Any

from app.book_editorial_alignment_4b216.constants import (
    HISTORICAL_4B215_STATUS,
    HISTORICAL_H11_STATUS,
    HISTORICAL_SEMANTIC_CONTRACT,
    PHASE,
    SEMANTIC_GATE_202_ENABLED,
)
from app.book_semantic_gate_4b212.constants import PROMPT_VERSION_202_ACTIVATED
from app.book_semantic_gate_4b212.contract import semantic_contract_202_candidate
from app.book_semantic_gate_4b28.constants import H11_HUMAN_LABEL
from app.file_utils import content_hash


def semantic_gate_alignment() -> dict[str, Any]:
    contract = semantic_contract_202_candidate()
    prompt = str(contract.get("prompt") or contract.get("system") or "")
    if not prompt:
        prompt = str(contract.get("candidate_prompt") or "")
    return {
        "phase": PHASE,
        "contract": HISTORICAL_SEMANTIC_CONTRACT,
        "contract_modified": False,
        "contract_activated": PROMPT_VERSION_202_ACTIVATED,
        "semantic_gate_enabled": SEMANTIC_GATE_202_ENABLED,
        "candidate_sha256": contract.get("candidate_sha256"),
        "historical_4b215_status": HISTORICAL_4B215_STATUS,
        "historical_h11_status": HISTORICAL_H11_STATUS,
        "historical_h11_human_label": H11_HUMAN_LABEL,
        "historical_h11_human_label_modified": False,
        "historical_results_requalified": False,
        "what_the_gate_continues_to_seek": [
            "invented assertions",
            "invented causalities",
            "new implications",
            "unsupported guarantees",
            "distortions",
            "changes of certainty",
            "incorrect attributions",
        ],
        "omissions_are_a_complementary_coverage_control": True,
        "omissions_are_not_silently_relabeled_by_this_phase": True,
        "automatic_unsupported_to_supported": False,
        "automatic_block_to_pass": False,
        "false_rejection_resolution": "traceable human resolution; Terra response stays immutable",
        "historical_h11_false_rejections_remain_documented": {
            "status": HISTORICAL_H11_STATUS,
            "human_label": H11_HUMAN_LABEL,
            "pattern": (
                "4B.2.8 recorded historically supported clauses rejected at "
                "claim indexes 0, 2, and 4, while the universal guarantee was "
                "rightly rejected. This phase does not change those labels "
                "and does not convert the PARTIAL result into PASS."
            ),
            "not_converted_to_pass": True,
        },
        "publication_still_requires_independent_validation": True,
        "interpretation_only": True,
        "prompt_hash_if_present": content_hash(prompt) if prompt else "",
        "secrets_included": False,
    }


__all__ = ["semantic_gate_alignment"]
