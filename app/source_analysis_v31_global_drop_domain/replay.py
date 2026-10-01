"""Replay A.40 immuable + contre-factuel drop SYN:L001. 0 provider. 0 réparation."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

from app.ai.structured import parse_structured_output
from app.source_analysis_v31_global_drop_domain.constants import (
    A40_GLOBAL_VALIDATOR,
    A40_GRAMMAR,
    A40_ROOT_VALIDATOR_ERROR,
    A40_STATUS_PRESERVED,
    A40_TRANSPORT_DECODER,
    A40_VIOLATING_ID,
    A40_VIOLATING_KIND,
    PROJECT_NAME,
    V20_TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_drop_domain.evidence import (
    extract_a40_text_and_json,
    verify_a40_identity,
)
from app.source_analysis_v31_global_output_architecture.transport_v20 import (
    build_global_consolidation_schema_v20,
)
from app.source_analysis_v31_global_v20_grammar_canary.fixture import build_synthetic_fixture
from app.source_analysis_v31_global_v20_grammar_canary.validate import (
    interpret_canary_response_v20,
)


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def parse_a40_transport(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    text, _envelope, raw = extract_a40_text_and_json(
        project_name, sortie_dir=sortie_dir
    )
    schema = build_global_consolidation_schema_v20()
    parsed = parse_structured_output(text, schema)
    if not isinstance(parsed, dict):
        raise ValueError("A.40 structured parse did not yield an object")
    return {
        "raw_text": text,
        "raw_bytes": raw,
        "parsed": parsed,
        "structured_parse": "PASS",
    }


def replay_a40_frozen(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    identity = verify_a40_identity(project_name, sortie_dir=sortie_dir)
    parsed_bundle = parse_a40_transport(project_name, sortie_dir=sortie_dir)
    fixture = build_synthetic_fixture()
    interpreted = interpret_canary_response_v20(
        parsed_bundle["parsed"],
        fixture=fixture,
        raw_text=parsed_bundle["raw_text"],
        signature="a41-replay-a40-frozen",
    )
    drops = []
    transport = interpreted.get("transport") if isinstance(interpreted.get("transport"), dict) else {}
    for index, row in enumerate(_as_list(transport.get("drop"))):
        if isinstance(row, Mapping):
            drops.append(
                {
                    "index": index,
                    "id": row.get("i"),
                    "reason": row.get("w"),
                    "kind": fixture.kind_by_input.get(str(row.get("i") or "")),
                }
            )
    violating = [
        row
        for row in drops
        if row.get("id") == A40_VIOLATING_ID and row.get("kind") == A40_VIOLATING_KIND
    ]
    validator_errors = list((interpreted.get("validator") or {}).get("errors") or [])
    return {
        "identity": identity,
        "raw_immutable": identity.get("raw_immutable"),
        "a40_status_preserved": A40_STATUS_PRESERVED,
        "transport_version": V20_TRANSPORT_VERSION,
        "structured_parse": interpreted.get("structured_parse"),
        "decoder": interpreted.get("decoder"),
        "handle_validation": interpreted.get("handle_validation"),
        "idea_accountability_coverage": interpreted.get("idea_disposition_coverage"),
        "derived_dispositions_status": (
            "PASS"
            if interpreted.get("drop_enum") == "PASS"
            and interpreted.get("other_count") == 0
            else "FAIL"
        ),
        "derived_src": interpreted.get("derived_src_union"),
        "global_validator": interpreted.get("global_validator"),
        "canonical_reconstruction": interpreted.get("canonical_reconstruction"),
        "canonical_validation": interpreted.get("canonical_validation"),
        "deterministic_replay": interpreted.get("deterministic_replay"),
        "semantic_fixture_review": (interpreted.get("semantic_review") or {}).get("status"),
        "grammar_proof": A40_GRAMMAR,
        "transport_decoder_historical": A40_TRANSPORT_DECODER,
        "global_validator_historical": A40_GLOBAL_VALIDATOR,
        "validator_errors": validator_errors,
        "root_error_reproduced": A40_ROOT_VALIDATOR_ERROR in validator_errors,
        "drops": drops,
        "violating_drop": violating[0] if violating else None,
        "provider_success_vs_contract_failure": {
            "provider_grammar": "SUCCESS",
            "global_contract_validation": "FAIL",
            "not_grammar_rejection": True,
            "not_json_corruption": True,
            "not_max_tokens": True,
            "not_thinking": True,
            "not_membership_failure": interpreted.get("missing_members") == 0,
            "not_src_derivation_failure": interpreted.get("derived_src_union") == "PASS",
            "not_canonical_reconstruction_failure": (
                interpreted.get("canonical_reconstruction") == "PASS"
            ),
        },
        "repaired": False,
        "interpreted": {
            "structured_parse": interpreted.get("structured_parse"),
            "decoder": interpreted.get("decoder"),
            "handle_validation": interpreted.get("handle_validation"),
            "global_validator": interpreted.get("global_validator"),
            "canonical_reconstruction": interpreted.get("canonical_reconstruction"),
            "canonical_validation": interpreted.get("canonical_validation"),
            "set_equality": interpreted.get("set_equality"),
            "membership": interpreted.get("membership"),
            "errors": interpreted.get("errors"),
        },
        "transport": transport,
    }


def derived_counterfactual_without_relation_drop(
    transport: dict[str, Any],
) -> dict[str, Any]:
    derived = copy.deepcopy(transport)
    original_drop = _as_list(derived.get("drop"))
    derived["drop"] = [
        row
        for row in original_drop
        if not (
            isinstance(row, dict) and str(row.get("i") or "") == A40_VIOLATING_ID
        )
    ]
    return derived


def replay_a40_counterfactual(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    frozen = replay_a40_frozen(project_name, sortie_dir=sortie_dir)
    original = frozen.get("transport") or {}
    derived = derived_counterfactual_without_relation_drop(original)
    fixture = build_synthetic_fixture()
    interpreted = interpret_canary_response_v20(
        derived,
        fixture=fixture,
        signature="a41-a40-counterfactual",
    )
    original_drop_ids = [
        str(row.get("i") or "")
        for row in _as_list(original.get("drop"))
        if isinstance(row, dict)
    ]
    derived_drop_ids = [
        str(row.get("i") or "")
        for row in _as_list(derived.get("drop"))
        if isinstance(row, dict)
    ]
    sole = (
        interpreted.get("global_validator") == "PASS"
        and interpreted.get("structured_parse") == "PASS"
        and interpreted.get("decoder") == "PASS"
        and interpreted.get("handle_validation") == "PASS"
        and interpreted.get("canonical_reconstruction") == "PASS"
        and interpreted.get("canonical_validation") == "PASS"
        and interpreted.get("derived_src_union") == "PASS"
        and A40_VIOLATING_ID in original_drop_ids
        and A40_VIOLATING_ID not in derived_drop_ids
        and set(original_drop_ids) - {A40_VIOLATING_ID} == set(derived_drop_ids)
    )
    return {
        "original_a40_status": A40_STATUS_PRESERVED,
        "original_raw_immutable": frozen.get("raw_immutable"),
        "original_global_validator": frozen.get("global_validator"),
        "counterfactual_drop_ids": derived_drop_ids,
        "removed_only": A40_VIOLATING_ID,
        "structured_parse": interpreted.get("structured_parse"),
        "decoder": interpreted.get("decoder"),
        "handle_validation": interpreted.get("handle_validation"),
        "global_validator": interpreted.get("global_validator"),
        "canonical_reconstruction": interpreted.get("canonical_reconstruction"),
        "canonical_validation": interpreted.get("canonical_validation"),
        "derived_src": interpreted.get("derived_src_union"),
        "set_equality": interpreted.get("set_equality"),
        "deterministic_replay": interpreted.get("deterministic_replay"),
        "semantic_fixture_review": (interpreted.get("semantic_review") or {}).get("status"),
        "validator_errors": list((interpreted.get("validator") or {}).get("errors") or []),
        "a40_sole_technical_root": (
            "NON_IDEA_IN_IDEA_DROP_DOMAIN" if sole else "NOT_SOLE_OR_INCOMPLETE"
        ),
        "sole_technical_root": sole,
        "a40_remains_fail": True,
        "repaired_original": False,
        "transport": derived,
    }


__all__ = [
    "derived_counterfactual_without_relation_drop",
    "parse_a40_transport",
    "replay_a40_counterfactual",
    "replay_a40_frozen",
]
