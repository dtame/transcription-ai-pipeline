"""Prochain fixture canary compact — préparé, non exécuté. 0 provider."""

from __future__ import annotations

from typing import Any

from app.source_analysis_v31_global_drop_domain.constants import (
    NEXT_PROMPT_VERSION,
    OLD_TRANSPORT_VERSION,
    SECOND_COMPACT_CONTRACT_CANARY_REQUIRED,
)
from app.source_analysis_v31_global_drop_domain.policy import local_object_kind_policy
from app.source_analysis_v31_global_v20_grammar_canary.fixture import (
    build_synthetic_fixture,
    expected_valid_transport_v20,
    fixture_hash,
)


def next_compact_canary_fixture() -> dict[str, Any]:
    fixture = build_synthetic_fixture()
    kinds = fixture.kind_by_input
    counts = {
        "IDEA": sum(1 for kind in kinds.values() if kind == "IDEA"),
        "RELATION": sum(1 for kind in kinds.values() if kind == "RELATION"),
        "TOPIC": sum(1 for kind in kinds.values() if kind == "TOPIC"),
        "EXAMPLE": sum(1 for kind in kinds.values() if kind == "EXAMPLE"),
        "REFERENCE": sum(1 for kind in kinds.values() if kind == "REFERENCE"),
        "UNCERTAINTY": sum(1 for kind in kinds.values() if kind == "UNCERTAINTY"),
    }
    policy = local_object_kind_policy()
    expected = expected_valid_transport_v20()
    return {
        "executed": False,
        "second_compact_contract_canary_required": SECOND_COMPACT_CONTRACT_CANARY_REQUIRED,
        "prompt_version": NEXT_PROMPT_VERSION,
        "transport_version": OLD_TRANSPORT_VERSION,
        "based_on_a40_fixture_hash": fixture_hash(),
        "cardinalities": counts,
        "requirements": {
            "local_ideas_min": 7,
            "local_relation_hint_min": 1,
            "local_topic_min": 1,
            "local_example_min": 1,
            "local_reference_min": 1,
            "local_uncertainty_min": 1,
        },
        "requirements_met": (
            counts["IDEA"] >= 7
            and counts["RELATION"] >= 1
            and counts["TOPIC"] >= 1
            and counts["EXAMPLE"] >= 1
            and counts["REFERENCE"] >= 1
            and counts["UNCERTAINTY"] >= 1
        ),
        "expected_behavior": {
            "only_idea_ids_in_membership_or_drop": True,
            "relation_may_be_absent": True,
            "relation_absence_is_not_drop": True,
            "topic_example_reference_uncertainty_follow_own_arrays": True,
            "valid_fakeai": expected,
            "invalid_non_idea_drop": "FAIL deterministically",
        },
        "idea_input_ids": list(fixture.idea_input_ids),
        "relation_ids": [
            key for key, kind in kinds.items() if kind == "RELATION"
        ],
        "kind_policy": policy["kinds"],
        "pastoral": False,
        "real_windows": False,
    }


__all__ = ["next_compact_canary_fixture"]
