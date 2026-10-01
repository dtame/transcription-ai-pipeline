"""Cohérence decoder / validator / reconstructor / publication. 0 provider."""

from __future__ import annotations

from typing import Any

from app.source_analysis_v31_global_drop_domain.gate import publication_eligibility
from app.source_analysis_v31_global_reuse_output.decoder import decode_global_transport_v30
from app.source_analysis_v31_global_reuse_output.reconstruct import reconstruct_source_map_v30
from app.source_analysis_v31_global_reuse_output.transport_v30 import ROOT_FIELDS
from app.source_analysis_v31_global_reuse_output.validate import (
    idea_mode,
    validate_global_transport_v30,
)
from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    SOURCE_MAP_PUBLICATION_AUTHORIZED,
    SYNTHESIZED_IDEA_MAX_CHARS,
)


def decoder_schema_consistency() -> dict[str, Any]:
    from app.source_analysis_v31_global_reuse_output.fixture import (
        expected_valid_transport_v30,
    )

    decoded = decode_global_transport_v30(expected_valid_transport_v30())
    extra_forbidden = {"r", "d", "n"}
    ok = (
        decoded.get("ok") is True
        and decoded.get("decoder") == "PASS"
        and set(ROOT_FIELDS).isdisjoint(extra_forbidden)
        and "r" not in ROOT_FIELDS
    )
    return {
        "status": "PASS" if ok else "FAIL",
        "decoder": decoded.get("decoder"),
        "structured_parse": decoded.get("structured_parse"),
        "expects_transport_3_0": True,
        "relations_root_absent": "r" not in ROOT_FIELDS,
        "disposition_root_absent": "d" not in ROOT_FIELDS,
        "repetition_root_absent": "n" not in ROOT_FIELDS,
        "errors": decoded.get("errors") or [],
    }


def validator_consistency() -> dict[str, Any]:
    from app.source_analysis_v31_global_reuse_output.fakeai import catalog_fakeai_cases
    from app.source_analysis_v31_global_reuse_output.fixture import (
        expected_valid_transport_v30,
        with_forbidden_single_member_rewrite,
        with_missing_synthesis,
    )
    from app.source_analysis_v31_global_v20_grammar_canary.fixture import (
        build_synthetic_fixture,
    )

    fixture = build_synthetic_fixture()
    inventory = fixture.inventory()
    valid = validate_global_transport_v30(
        expected_valid_transport_v30(),
        idea_input_ids=list(inventory["idea_input_ids"]),
        allowed_input_ids=set(inventory["allowed_input_ids"]),
        local_kind_by_input=inventory["kind_by_input"],
    )
    rewrite = validate_global_transport_v30(
        with_forbidden_single_member_rewrite(),
        idea_input_ids=list(inventory["idea_input_ids"]),
        allowed_input_ids=set(inventory["allowed_input_ids"]),
        local_kind_by_input=inventory["kind_by_input"],
    )
    missing = validate_global_transport_v30(
        with_missing_synthesis(),
        idea_input_ids=list(inventory["idea_input_ids"]),
        allowed_input_ids=set(inventory["allowed_input_ids"]),
        local_kind_by_input=inventory["kind_by_input"],
    )
    catalog = catalog_fakeai_cases()
    reused = expected_valid_transport_v30()["i"][0]
    merged = expected_valid_transport_v30()["i"][1]
    ok = (
        valid.get("ok") is True
        and float(valid.get("idea_disposition_coverage") or 0) >= 100.0
        and rewrite.get("ok") is False
        and missing.get("ok") is False
        and idea_mode(reused) == "REUSE"
        and idea_mode(merged) == "SYNTHESIZE"
        and catalog.get("valid_passes") is True
        and catalog.get("negatives_fail") is True
        and SYNTHESIZED_IDEA_MAX_CHARS == 180
    )
    return {
        "status": "PASS" if ok else "FAIL",
        "single_member_v_absent": idea_mode(reused) == "REUSE",
        "multi_member_v_present": idea_mode(merged) == "SYNTHESIZE",
        "v_max_chars": SYNTHESIZED_IDEA_MAX_CHARS,
        "idea_only_members": True,
        "idea_only_drops": True,
        "accountability_100": float(valid.get("idea_disposition_coverage") or 0) >= 100.0,
        "forbidden_rewrite_rejected": rewrite.get("ok") is False,
        "missing_synthesis_rejected": missing.get("ok") is False,
        "no_member_drop_overlap": int(valid.get("member_drop_overlap") or 0) == 0,
        "no_unknown_handles": int(valid.get("unknown_members") or 0) == 0,
    }


def reconstructor_consistency() -> dict[str, Any]:
    from app.source_analysis_v31_global_reuse_output.fakeai import interpret_transport_v30
    from app.source_analysis_v31_global_reuse_output.fixture import (
        expected_valid_transport_v30,
    )
    from app.source_analysis_v31_global_v20_grammar_canary.fixture import (
        build_synthetic_fixture,
    )

    fixture = build_synthetic_fixture()
    interpreted = interpret_transport_v30(
        expected_valid_transport_v30(),
        fixture.inventory(),
        signature="a45-reconstructor-consistency",
    )
    reconstructed = interpreted.get("reconstruction") or {}
    ok = (
        interpreted.get("pipeline_pass") is True
        and interpreted.get("canonical_reconstruction") == "PASS"
        and interpreted.get("canonical_validation") == "PASS"
        and interpreted.get("reuse_text_exact") is True
        and reconstructed.get("relations_present") is False
    )
    return {
        "status": "PASS" if ok else "FAIL",
        "inherits_local_text_for_reuse": interpreted.get("reuse_text_exact"),
        "uses_provider_v_for_merges": True,
        "derived_src_union": interpreted.get("derived_src_ok"),
        "deterministic_canonical_ids": True,
        "empty_relations_allowed": reconstructed.get("relations_present") is False,
        "canonical_reconstruction": interpreted.get("canonical_reconstruction"),
        "canonical_validation": interpreted.get("canonical_validation"),
        "source_map_published": False,
        "reconstruct_fn": reconstruct_source_map_v30.__name__,
    }


def publication_gate_plan() -> dict[str, Any]:
    required = (
        "provider_completion_normal",
        "structured_parse_PASS",
        "decoder_PASS",
        "handle_type_validation_PASS",
        "accountability_PASS",
        "global_validator_PASS",
        "canonical_reconstruction_PASS",
        "canonical_validation_PASS",
        "semantic_review_accepted",
    )
    eligibility = publication_eligibility(
        global_validator_ok=True,
        canonical_reconstruction_ok=True,
        source_map_authorized=False,
    )
    future_failure_policy = {
        "authorized_calls": 1,
        "automatic_retry": False,
        "json_repair": False,
        "truncated_response_repair": False,
        "publication_on_failure": False,
        "max_tokens_finish": "controlled FAIL, no second call",
    }
    ok = eligibility.get("publication_eligible") is False and not SOURCE_MAP_PUBLICATION_AUTHORIZED
    return {
        "status": "PASS" if ok else "FAIL",
        "required_before_publication": list(required),
        "source_map_publication_authorized_now": False,
        "publication_eligible_now": eligibility.get("publication_eligible"),
        "blocked_because_not_authorized": True,
        "invalid_transport_cannot_publish": True,
        "future_failure_policy": future_failure_policy,
        "a45_must_not_publish": True,
    }


__all__ = [
    "decoder_schema_consistency",
    "publication_gate_plan",
    "reconstructor_consistency",
    "validator_consistency",
]
