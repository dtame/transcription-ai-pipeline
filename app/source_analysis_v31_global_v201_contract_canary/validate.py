"""Interprétation canary A.42 : decoder 2.0 + IDEA-only drop + type-boundary."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v31_global_drop_domain.analysis import inspect_handles_including_drop
from app.source_analysis_v31_global_drop_domain.gate import publication_eligibility
from app.source_analysis_v31_global_v20_grammar_canary.fixture import (
    SyntheticConsolidationFixtureV20,
)
from app.source_analysis_v31_global_v20_grammar_canary.validate import (
    interpret_canary_response_v20,
    review_semantic_v20,
)
from app.source_analysis_v31_global_v201_contract_canary.constants import (
    RELATION_HINT_ID,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_v201_contract_canary.type_boundary import (
    classify_a40_root_defect,
    type_boundary_audit,
)


def review_semantic_v201(
    transport: Mapping[str, Any] | None,
    fixture: SyntheticConsolidationFixtureV20,
    *,
    boundary: Mapping[str, Any],
) -> dict[str, Any]:
    base = review_semantic_v20(transport, fixture)
    notes = list(base.get("notes") or [])
    relation_ignored = (
        boundary.get("RELATION_HINT_IN_MEMBERS") == "NO"
        and boundary.get("RELATION_HINT_IN_DROP") == "NO"
    )
    if not relation_ignored:
        notes.append("relation hint entered IDEA membership or drop[]")
    non_idea_ok = (
        int(boundary.get("NON_IDEA_IN_MEMBERS") or 0) == 0
        and int(boundary.get("NON_IDEA_IN_DROP") or 0) == 0
        and int(boundary.get("TOPIC_IDEA_DOMAIN_VIOLATIONS") or 0) == 0
        and int(boundary.get("EXAMPLE_IDEA_DOMAIN_VIOLATIONS") or 0) == 0
        and int(boundary.get("REFERENCE_IDEA_DOMAIN_VIOLATIONS") or 0) == 0
        and int(boundary.get("UNCERTAINTY_IDEA_DOMAIN_VIOLATIONS") or 0) == 0
    )
    if not non_idea_ok:
        notes.append("non-IDEA object entered IDEA membership or drop[]")
    reasonable = (
        base.get("status") == "PASS" and relation_ignored and non_idea_ok
    )
    return {
        **base,
        "status": "PASS" if reasonable else "FAIL",
        "relation_hint_ignored_by_idea_accountability": relation_ignored,
        "non_idea_kinds_absent_from_idea_domain": non_idea_ok,
        "notes": notes,
        "not_production_quality_proof": True,
    }


def interpret_canary_response_v201(
    parsed: dict[str, Any] | None,
    *,
    fixture: SyntheticConsolidationFixtureV20,
    raw_text: str | None = None,
    signature: str = "",
) -> dict[str, Any]:
    interpreted = interpret_canary_response_v20(
        parsed,
        fixture=fixture,
        raw_text=raw_text,
        signature=signature or "a42-v201",
    )
    transport = interpreted.get("transport")
    handles = inspect_handles_including_drop(
        transport if isinstance(transport, dict) else None,
        allowed_input_ids=set(fixture.allowed_input_ids),
        kind_by_input=fixture.kind_by_input,
    )
    boundary = type_boundary_audit(
        transport if isinstance(transport, dict) else None,
        kind_by_input=fixture.kind_by_input,
        relation_hint_id=RELATION_HINT_ID,
    )
    pub = publication_eligibility(
        global_validator_ok=interpreted.get("global_validator") == "PASS",
        canonical_reconstruction_ok=interpreted.get("canonical_reconstruction")
        == "PASS",
    )
    semantic = review_semantic_v201(
        transport if isinstance(transport, dict) else None,
        fixture,
        boundary=boundary,
    )
    reconstruction_ok = interpreted.get("canonical_reconstruction") == "PASS"
    invalid_transport_gate = (
        "PASS"
        if (
            pub.get("publication_eligible") is False
            and (
                interpreted.get("global_validator") != "PASS"
                or not reconstruction_ok
                or pub.get("source_map_authorized") is False
            )
        )
        else "FAIL"
    )
    if interpreted.get("global_validator") == "PASS":
        invalid_transport_gate = (
            "PASS"
            if pub.get("blocked_because_invalid_transport") is False
            and pub.get("publication_eligible") is False
            else "FAIL"
        )
    interpreted["handle_validation"] = handles.get("handle_validation")
    interpreted["handles"] = handles
    interpreted["type_boundary"] = boundary
    interpreted["NON_IDEA_IN_MEMBERS"] = boundary.get("NON_IDEA_IN_MEMBERS")
    interpreted["NON_IDEA_IN_DROP"] = boundary.get("NON_IDEA_IN_DROP")
    interpreted["RELATION_HINT_IN_MEMBERS"] = boundary.get("RELATION_HINT_IN_MEMBERS")
    interpreted["RELATION_HINT_IN_DROP"] = boundary.get("RELATION_HINT_IN_DROP")
    interpreted["TOPIC_IDEA_DOMAIN_VIOLATIONS"] = boundary.get(
        "TOPIC_IDEA_DOMAIN_VIOLATIONS"
    )
    interpreted["EXAMPLE_IDEA_DOMAIN_VIOLATIONS"] = boundary.get(
        "EXAMPLE_IDEA_DOMAIN_VIOLATIONS"
    )
    interpreted["REFERENCE_IDEA_DOMAIN_VIOLATIONS"] = boundary.get(
        "REFERENCE_IDEA_DOMAIN_VIOLATIONS"
    )
    interpreted["UNCERTAINTY_IDEA_DOMAIN_VIOLATIONS"] = boundary.get(
        "UNCERTAINTY_IDEA_DOMAIN_VIOLATIONS"
    )
    interpreted["publication"] = pub
    interpreted["invalid_transport_publication_gate"] = invalid_transport_gate
    interpreted["semantic_review"] = semantic
    interpreted["a40_root_defect"] = classify_a40_root_defect(boundary)
    interpreted["transport_version"] = TRANSPORT_VERSION
    interpreted["prompt_version"] = "global-consolidation-2.0.1"
    interpreted["repaired"] = False
    return interpreted


__all__ = [
    "interpret_canary_response_v201",
    "review_semantic_v201",
]
