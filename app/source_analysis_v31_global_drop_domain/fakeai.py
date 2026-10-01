"""Cas FakeAI déterministes — domaine drop IDEA-only. 0 réseau."""

from __future__ import annotations

import copy
from typing import Any

from app.source_analysis_v31_global_drop_domain.analysis import inspect_handles_including_drop
from app.source_analysis_v31_global_drop_domain.gate import publication_eligibility
from app.source_analysis_v31_global_output_architecture.membership import (
    derived_src_union,
    validate_global_transport_v20,
)
from app.source_analysis_v31_global_v20_grammar_canary.fixture import (
    build_synthetic_fixture,
    expected_valid_transport_v20,
)
from app.source_analysis_v31_global_v20_grammar_canary.validate import (
    interpret_canary_response_v20,
)

NON_IDEA_DROP_CASES = (
    ("RELATION_IN_DROP", "SYN:L001", "RELATION"),
    ("TOPIC_IN_DROP", "SYN:T001", "TOPIC"),
    ("EXAMPLE_IN_DROP", "SYN:E001", "EXAMPLE"),
    ("REFERENCE_IN_DROP", "SYN:F001", "REFERENCE"),
    ("UNCERTAINTY_IN_DROP", "SYN:U001", "UNCERTAINTY"),
)


def valid_deferred_relation_transport() -> dict[str, Any]:
    payload = expected_valid_transport_v20()
    blob = str(payload)
    assert "SYN:L001" not in blob
    return payload


def with_non_idea_drop(local_id: str) -> dict[str, Any]:
    payload = copy.deepcopy(expected_valid_transport_v20())
    payload["drop"].append({"i": local_id, "w": "transport_artifact"})
    return payload


def interpret_next_contract(payload: dict[str, Any], *, signature: str) -> dict[str, Any]:
    fixture = build_synthetic_fixture()
    interpreted = interpret_canary_response_v20(
        payload, fixture=fixture, signature=signature
    )
    handles = inspect_handles_including_drop(
        payload,
        allowed_input_ids=set(fixture.allowed_input_ids),
        kind_by_input=fixture.kind_by_input,
    )
    validator = validate_global_transport_v20(
        payload,
        idea_input_ids=list(fixture.idea_input_ids),
        allowed_input_ids=set(fixture.allowed_input_ids),
        local_kind_by_input=fixture.kind_by_input,
    )
    pub = publication_eligibility(
        global_validator_ok=bool(validator.get("ok")),
        canonical_reconstruction_ok=interpreted.get("canonical_reconstruction") == "PASS",
    )
    interpreted["next_handle_validation"] = handles.get("handle_validation")
    interpreted["next_handles"] = handles
    interpreted["publication"] = pub
    interpreted["next_global_validator"] = "PASS" if validator.get("ok") else "FAIL"
    return interpreted


def catalog_fakeai_cases() -> dict[str, Any]:
    fixture = build_synthetic_fixture()
    valid = interpret_next_contract(
        valid_deferred_relation_transport(), signature="a41-valid-deferred-relation"
    )
    relation_omitted = "SYN:L001" not in str(valid_deferred_relation_transport())
    negatives = {}
    for name, local_id, kind in NON_IDEA_DROP_CASES:
        payload = with_non_idea_drop(local_id)
        result = interpret_next_contract(payload, signature=f"a41-{name.lower()}")
        negatives[name] = {
            "expected": "FAIL",
            "global_validator": result.get("next_global_validator"),
            "handle_validation": result.get("next_handle_validation"),
            "publication_eligible": (result.get("publication") or {}).get(
                "publication_eligible"
            ),
            "blocked_invalid_transport": (result.get("publication") or {}).get(
                "blocked_because_invalid_transport"
            ),
            "kind": kind,
            "id": local_id,
            "ok": (
                result.get("next_global_validator") == "FAIL"
                and result.get("next_handle_validation") == "FAIL"
                and (result.get("publication") or {}).get("publication_eligible") is False
            ),
        }
    members = ["SYN:I002", "SYN:I003"]
    src = derived_src_union(members, fixture.src_by_input)
    valid_ok = (
        valid.get("global_validator") == "PASS"
        and valid.get("next_handle_validation") == "PASS"
        and valid.get("set_equality") is True
        and relation_omitted
        and (valid.get("publication") or {}).get("blocked_because_invalid_transport")
        is False
    )
    return {
        "valid_deferred_relation": {
            "expected": "PASS",
            "ok": valid_ok,
            "relation_absent_from_output": relation_omitted,
            "global_validator": valid.get("global_validator"),
            "set_equality": valid.get("set_equality"),
            "coverage": valid.get("idea_disposition_coverage"),
        },
        "negatives": negatives,
        "derived_src_sample": src,
        "all_negatives_fail": all(row["ok"] for row in negatives.values()),
        "valid_passes": valid_ok,
    }


__all__ = [
    "NON_IDEA_DROP_CASES",
    "catalog_fakeai_cases",
    "interpret_next_contract",
    "valid_deferred_relation_transport",
    "with_non_idea_drop",
]
