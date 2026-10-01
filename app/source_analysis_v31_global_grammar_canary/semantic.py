"""Revue sémantique légère hors ligne. Pas une preuve de qualité production."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v31_global_grammar_canary.fixture import (
    SyntheticConsolidationFixture,
    all_records,
)


def review_semantic_fixture(
    transport: Mapping[str, Any] | None,
    fixture: SyntheticConsolidationFixture,
) -> dict[str, Any]:
    if not isinstance(transport, Mapping):
        return {
            "status": "FAIL",
            "invented_facts": True,
            "lost_fixture_ideas": True,
            "unrelated_merge": True,
            "disposition_contract": False,
            "notes": ["transport missing"],
        }
    nodes = [item for item in (transport.get("n") or []) if isinstance(item, dict)]
    ideas = [item for item in nodes if item.get("k") == "IDEA"]
    uncertainties = [item for item in nodes if item.get("k") == "UNCERTAINTY"]
    examples = [item for item in nodes if item.get("k") == "EXAMPLE"]
    allowed_src = set(fixture.allowed_source_refs)
    invented = []
    for node in nodes:
        for ref in node.get("s") or []:
            if str(ref) not in allowed_src:
                invented.append(str(ref))
    local_ideas = [item for item in all_records() if item["k"] == "IDEA"]
    keep_or_merge = [
        item
        for item in local_ideas
        if fixture.expected_dispositions.get(item["id"])
        in {"KEEP", "MERGE_EQUIVALENT", "LINK_RELATED"}
    ]
    idea_texts = [str(item.get("v") or "").lower() for item in ideas]
    lost = []
    for item in keep_or_merge:
        tokens = [
            token
            for token in str(item.get("v") or "").lower().split()
            if len(token) > 5
        ]
        if tokens and not any(token in " ".join(idea_texts) for token in tokens[:3]):
            lost.append(item["id"])

    dispositions = [item for item in (transport.get("d") or []) if isinstance(item, dict)]
    merge_handles = [
        str(item.get("g") or "")
        for item in dispositions
        if item.get("o") == "MERGE_EQUIVALENT"
    ]
    unrelated_merge = False
    if merge_handles:
        unique = set(handle for handle in merge_handles if handle)
        if len(unique) != 1:
            unrelated_merge = True
        compost_ids = {"SYN001:I2", "SYN002:I1"}
        merged_inputs = {
            str(item.get("i") or "")
            for item in dispositions
            if item.get("o") == "MERGE_EQUIVALENT"
        }
        if merged_inputs and merged_inputs != compost_ids:
            unrelated_merge = True

    drop_ok = True
    for item in dispositions:
        if item.get("o") == "DROP" and item.get("w") not in {
            "exact_duplicate",
            "transport_artifact",
            "non_substantive_fragment",
        }:
            drop_ok = False

    uncertainty_promoted = False
    unc_text = "frost"
    for idea in ideas:
        if unc_text in str(idea.get("v") or "").lower():
            uncertainty_promoted = True
    example_promoted = False
    for idea in ideas:
        value = str(idea.get("v") or "").lower()
        if "chewed leaves" in value or "twice each week" in value:
            example_promoted = True

    notes: list[str] = []
    if invented:
        notes.append(f"unknown SRC {invented}")
    if lost:
        notes.append(f"possible lost ideas {lost}")
    if unrelated_merge:
        notes.append("merge grouping unexpected")
    if uncertainty_promoted:
        notes.append("uncertainty appears promoted to IDEA")
    if example_promoted:
        notes.append("example text appears as IDEA")
    if not uncertainties:
        notes.append("no uncertainty node")
    if not examples:
        notes.append("no example node")

    reasonable = (
        not invented
        and not lost
        and not unrelated_merge
        and drop_ok
        and not uncertainty_promoted
        and not example_promoted
        and bool(uncertainties)
        and bool(examples)
        and len(ideas) >= 3
    )
    return {
        "status": "PASS" if reasonable else "FAIL",
        "invented_facts": bool(invented),
        "lost_fixture_ideas": bool(lost),
        "unrelated_merge": unrelated_merge,
        "disposition_contract": drop_ok and not unrelated_merge,
        "uncertainty_remains_uncertainty": bool(uncertainties) and not uncertainty_promoted,
        "examples_remain_examples": bool(examples) and not example_promoted,
        "notes": notes,
        "idea_count": len(ideas),
        "not_production_quality_proof": True,
    }


__all__ = ["review_semantic_fixture"]
