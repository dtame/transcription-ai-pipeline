"""Cas FakeAI déterministes — contrat reuse 3.0. 0 réseau."""

from __future__ import annotations

from typing import Any

from app.source_analysis_v31_global_reuse_output.decoder import decode_global_transport_v30
from app.source_analysis_v31_global_reuse_output.fixture import (
    all_distinct_reuse_transport,
    build_full_scale_inventory,
    expected_valid_transport_v30,
    mixed_full_scale_transport,
    with_forbidden_single_member_rewrite,
    with_missing_synthesis,
)
from app.source_analysis_v31_global_reuse_output.reconstruct import reconstruct_source_map_v30
from app.source_analysis_v31_global_reuse_output.validate import (
    derived_src_union,
    validate_global_transport_v30,
)
from app.source_analysis_v31_global_v20_grammar_canary.fixture import build_synthetic_fixture
from app.source_analysis_v31_global_v20_grammar_canary.handles import inspect_global_handles_v20


def interpret_transport_v30(
    transport: dict[str, Any],
    inventory: dict[str, Any],
    *,
    signature: str,
) -> dict[str, Any]:
    decoded = decode_global_transport_v30(transport)
    validated = validate_global_transport_v30(
        transport,
        idea_input_ids=list(inventory["idea_input_ids"]),
        allowed_input_ids=set(inventory["allowed_input_ids"]),
        local_kind_by_input=inventory["kind_by_input"],
    )
    handles = inspect_global_handles_v20(
        transport,
        allowed_input_ids=set(inventory["allowed_input_ids"]),
        kind_by_input=inventory["kind_by_input"],
    )
    reconstructed = None
    if validated.get("ok") and decoded.get("ok"):
        reconstructed = reconstruct_source_map_v30(
            transport,
            inventory,
            inventory["transcript"],
            signature=signature,
        )
    unions_ok = True
    if validated.get("ok"):
        local_src = inventory["src_by_input"]
        for idea in transport.get("i") or []:
            members = list(idea.get("m") or [])
            derived = derived_src_union(members, local_src)
            expected: list[str] = []
            seen: set[str] = set()
            for member in members:
                for ref in local_src.get(member) or []:
                    if ref not in seen:
                        seen.add(ref)
                        expected.append(ref)
            if derived != expected:
                unions_ok = False
    pipeline = bool(
        decoded.get("ok")
        and validated.get("ok")
        and reconstructed
        and reconstructed.get("ok")
        and unions_ok
        and reconstructed.get("reuse_text_exact")
    )
    return {
        "decoder": decoded.get("decoder"),
        "structured_parse": decoded.get("structured_parse"),
        "validator": validated,
        "handles": handles.get("handle_validation"),
        "reconstruction": reconstructed,
        "pipeline_pass": pipeline,
        "derived_src_ok": unions_ok,
        "canonical_reconstruction": (
            reconstructed.get("validate_source_map") if reconstructed else "FAIL"
        ),
        "canonical_validation": (
            reconstructed.get("ensure_valid_source_map") if reconstructed else "FAIL"
        ),
        "reuse_text_exact": (
            reconstructed.get("reuse_text_exact") if reconstructed else False
        ),
        "idea_accountability": validated.get("exact_set_equality"),
        "coverage": validated.get("idea_disposition_coverage"),
    }


def catalog_fakeai_cases() -> dict[str, Any]:
    fixture = build_synthetic_fixture()
    inventory = fixture.inventory()
    valid = interpret_transport_v30(
        expected_valid_transport_v30(), inventory, signature="a43-valid-reuse"
    )
    rewrite = interpret_transport_v30(
        with_forbidden_single_member_rewrite(),
        inventory,
        signature="a43-forbidden-rewrite",
    )
    missing = interpret_transport_v30(
        with_missing_synthesis(), inventory, signature="a43-missing-synthesis"
    )
    relation_omitted = "SYN:L001" not in str(expected_valid_transport_v30())
    return {
        "valid_reuse_and_merge": {
            "expected": "PASS",
            "ok": valid.get("pipeline_pass") is True,
            "relation_absent": relation_omitted,
            **{k: valid.get(k) for k in (
                "decoder",
                "canonical_reconstruction",
                "canonical_validation",
                "reuse_text_exact",
                "idea_accountability",
                "coverage",
            )},
        },
        "forbidden_single_member_rewrite": {
            "expected": "FAIL",
            "ok": rewrite.get("pipeline_pass") is False
            and bool((rewrite.get("validator") or {}).get("forbidden_rewrites")),
            "errors": (rewrite.get("validator") or {}).get("errors") or [],
        },
        "missing_multi_member_synthesis": {
            "expected": "FAIL",
            "ok": missing.get("pipeline_pass") is False
            and bool((missing.get("validator") or {}).get("missing_synthesis")),
            "errors": (missing.get("validator") or {}).get("errors") or [],
        },
        "valid_passes": valid.get("pipeline_pass") is True and relation_omitted,
        "negatives_fail": (
            rewrite.get("pipeline_pass") is False
            and bool((rewrite.get("validator") or {}).get("forbidden_rewrites"))
            and missing.get("pipeline_pass") is False
            and bool((missing.get("validator") or {}).get("missing_synthesis"))
        ),
    }


def full_scale_stress() -> dict[str, Any]:
    inventory = build_full_scale_inventory()
    distinct = interpret_transport_v30(
        all_distinct_reuse_transport(inventory),
        inventory,
        signature="a43-all-distinct-reuse",
    )
    mixed = interpret_transport_v30(
        mixed_full_scale_transport(inventory),
        inventory,
        signature="a43-mixed-full-scale",
    )
    high_synthesis = {
        "applicable": False,
        "reason": "Hard rule forbids single-member rewrite exceptions; no cap to exercise.",
        "status": "N/A",
    }
    distinct_ok = distinct.get("pipeline_pass") is True and len(
        inventory["idea_input_ids"]
    ) == 286
    mixed_ok = mixed.get("pipeline_pass") is True
    return {
        "all_distinct_286_reuse": {
            "status": "PASS" if distinct_ok else "FAIL",
            "ok": distinct_ok,
            "ideas": len(inventory["idea_input_ids"]),
            "coverage": distinct.get("coverage"),
            "canonical_reconstruction": distinct.get("canonical_reconstruction"),
            "canonical_validation": distinct.get("canonical_validation"),
            "reuse_text_exact": distinct.get("reuse_text_exact"),
            "derived_src_ok": distinct.get("derived_src_ok"),
        },
        "mixed_full_scale": {
            "status": "PASS" if mixed_ok else "FAIL",
            "ok": mixed_ok,
            "coverage": mixed.get("coverage"),
            "canonical_reconstruction": mixed.get("canonical_reconstruction"),
            "canonical_validation": mixed.get("canonical_validation"),
            "reuse_text_exact": mixed.get("reuse_text_exact"),
        },
        "high_synthesis": high_synthesis,
        "ok": distinct_ok and mixed_ok,
    }


__all__ = [
    "catalog_fakeai_cases",
    "full_scale_stress",
    "interpret_transport_v30",
]
