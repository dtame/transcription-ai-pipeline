"""Offline replay A/B/C of the 4B.2.11 response. No provider. No historical rewrite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b29.coverage import validate_prepared_coverage
from app.book_semantic_gate_4b211.request import paragraph_context
from app.book_semantic_gate_4b211.review import review_h01_semantic_response
from app.book_semantic_gate_4b211.validation import apply_policy, validate_contract
from app.book_semantic_gate_4b212.constants import (
    EXPECTED_4B211_RAW_TEXT_SHA256,
    FIXTURE_KIND,
    H01_EVIDENCE_HANDLES,
    HISTORICAL_4B211_STATUS,
    PHASE,
    PROMPT_VERSION_201_CANDIDATE,
    PROMPT_VERSION_202_CANDIDATE,
    REQUIRED_UNIT_IDS,
    SELECTED_CASE_HANDLE,
    TARGET_UNIT_ID,
)
from app.book_semantic_gate_4b212.forensics import load_historical_raw
from app.book_semantic_gate_4b212.policy import apply_acceptance_policy_202
from app.book_semantic_gate_4b212.validator import validate_response_202
from app.file_utils import content_hash


def _canonical(payload: Mapping[str, Any]) -> str:
    return content_hash(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True))


def historical_replay_201(*, root: Path | None = None) -> dict[str, Any]:
    saved = load_historical_raw(root=root)
    raw_text = str(saved.get("text") or "")
    context = paragraph_context(root=root)
    prepared = dict(context.get("prepared") or {})
    allowed = list(context.get("allowed_handles") or H01_EVIDENCE_HANDLES)
    first = validate_contract(raw_text, prepared, allowed_evidence=allowed)
    second = validate_contract(raw_text, prepared, allowed_evidence=allowed)
    first_policy = apply_policy(prepared, first)
    second_policy = apply_policy(prepared, second)
    first_hash = _canonical(
        {
            "status": first.get("status"),
            "errors": first.get("errors"),
            "decision": first_policy.get("decision"),
        }
    )
    second_hash = _canonical(
        {
            "status": second.get("status"),
            "errors": second.get("errors"),
            "decision": second_policy.get("decision"),
        }
    )
    identical = first_hash == second_hash
    return {
        "phase": PHASE,
        "replay": "A_historical_contract_201",
        "contract": PROMPT_VERSION_201_CANDIDATE,
        "provider_calls": 0,
        "raw_text_sha256": content_hash(raw_text),
        "expected_raw_text_sha256": EXPECTED_4B211_RAW_TEXT_SHA256,
        "raw_unmodified": content_hash(raw_text) == EXPECTED_4B211_RAW_TEXT_SHA256,
        "json_parse": first.get("json_parse"),
        "contract_validation": first.get("status"),
        "acceptance_policy": first_policy.get("decision"),
        "expected_contract_validation": "FAIL",
        "expected_acceptance_policy": "BLOCK",
        "matches_historical_fail": first.get("status") == "FAIL" and first_policy.get("decision") == "BLOCK",
        "errors": first.get("errors") or [],
        "identical_second_pass": identical,
        "pass": (
            identical
            and first.get("status") == "FAIL"
            and first_policy.get("decision") == "BLOCK"
            and first.get("json_parse") == "PASS"
        ),
        "historical_4b211_status_unchanged": HISTORICAL_4B211_STATUS,
        "does_not_rewrite_historical_response": True,
        "does_not_convert_pass_to_supported": True,
        "does_not_convert_sc_keys": True,
        "secrets_included": False,
    }


def historical_semantic_observations(*, root: Path | None = None) -> dict[str, Any]:
    saved = load_historical_raw(root=root)
    parsed = saved.get("parsed") if isinstance(saved.get("parsed"), Mapping) else {}
    context = paragraph_context(root=root)
    prepared = dict(context.get("prepared") or {})
    allowed = list(context.get("allowed_handles") or H01_EVIDENCE_HANDLES)
    contract = validate_contract(parsed, prepared, allowed_evidence=allowed)
    coverage_ids = [str(item.get("unit_id") or "") for item in contract.get("verdicts") or []]
    review = review_h01_semantic_response(
        parsed,
        prepared_units=list(context.get("units") or prepared.get("units") or []),
        allowed_handles=allowed,
        contract_status=str(contract.get("status") or "FAIL"),
        coverage_ok=coverage_ids == list(REQUIRED_UNIT_IDS),
        evidence_ok=all(
            handle in allowed
            for item in (contract.get("verdicts") or [])
            for handle in (item.get("ev") or [])
        ),
    )
    classifications = [
        {
            "unit_id": item.get("unit_id"),
            "terra_k": item.get("terra_verdict"),
            "human_k_audit_only": item.get("human_verdict"),
            "evidence": item.get("terra_evidence"),
            "false_rejection": item.get("false_rejection"),
        }
        for item in review.get("units") or []
    ]
    return {
        "phase": PHASE,
        "replay": "B_semantic_observations",
        "provider_calls": 0,
        "raw_unmodified": True,
        "historical_canary_not_declared_pass": True,
        "historical_4b211_status": HISTORICAL_4B211_STATUS,
        "five_classifications": classifications,
        "all_five_supported": all(item.get("terra_k") == "SUPPORTED" for item in classifications),
        "target_unit_id": TARGET_UNIT_ID,
        "target_paraphrase": review.get("target_paraphrase_verdict"),
        "target_recognized": review.get("target_paraphrase_recognized"),
        "evidence_handles": review.get("cited_evidence"),
        "invalid_evidence": review.get("invalid_evidence_references"),
        "false_rejections": review.get("other_supported_false_rejections"),
        "no_false_rejection_observed": not review.get("other_supported_false_rejections")
        and bool(review.get("target_paraphrase_recognized")),
        "ambiguities": [
            "u02 evidence is looser than IDEA224 alone but stays inside the supplied set.",
            "Contract failure still blocks historical PASS.",
            "h02 and h11 were not re-evaluated by Terra under 2.0.1 or 2.0.2.",
        ],
        "finding": review.get("finding"),
        "semantic_status": review.get("semantic_status"),
        "human_labels_unmodified": True,
        "human_labels_not_transmitted": True,
        "secrets_included": False,
    }


def build_synthetic_202_fixture(*, root: Path | None = None) -> dict[str, Any]:
    saved = load_historical_raw(root=root)
    parsed = saved.get("parsed") if isinstance(saved.get("parsed"), Mapping) else {}
    paragraph = (parsed.get("pr") or [{}])[0]
    units = []
    for row in paragraph.get("u") or []:
        item = {
            "id": row.get("id"),
            "k": row.get("k"),
            "ev": list(row.get("ev") or []),
            "r": list(row.get("r") or []),
        }
        if row.get("n"):
            item["n"] = row.get("n")
        units.append(item)
    payload = {
        "ch": parsed.get("ch"),
        "pr": [{"h": paragraph.get("h") or SELECTED_CASE_HANDLE, "u": units}],
    }
    return {
        "fixture_kind": FIXTURE_KIND,
        "not_a_terra_response": True,
        "not_a_new_terra_call": True,
        "source_phase": "4B.2.11",
        "source_raw_sha256": EXPECTED_4B211_RAW_TEXT_SHA256,
        "preserves_observed_classifications": True,
        "does_not_map_pass_to_supported": True,
        "does_not_copy_paragraph_v": True,
        "does_not_copy_sc": True,
        "payload": payload,
        "secrets_included": False,
    }


def synthetic_202_fixture_replay(*, root: Path | None = None) -> dict[str, Any]:
    fixture = build_synthetic_202_fixture(root=root)
    context = paragraph_context(root=root)
    prepared = dict(context.get("prepared") or {})
    coverage = validate_prepared_coverage(prepared)
    payload = dict(fixture.get("payload") or {})
    validation = validate_response_202(
        payload,
        prepared,
        allowed_evidence=list(context.get("allowed_handles") or H01_EVIDENCE_HANDLES),
        expected_chapter="CH016",
    )
    policy = apply_acceptance_policy_202(prepared, coverage, validation)
    kinds = [str(item.get("k") or "") for item in validation.get("verdicts") or []]
    return {
        "phase": PHASE,
        "replay": "C_synthetic_202",
        "fixture_kind": FIXTURE_KIND,
        "not_a_terra_response": True,
        "provider_calls": 0,
        "contract": PROMPT_VERSION_202_CANDIDATE,
        "contract_ok": bool(validation.get("ok")),
        "technical_conformance": validation.get("technical_conformance"),
        "acceptance_policy": policy.get("decision"),
        "derived_paragraph_classification": validation.get("derived_paragraph_classification"),
        "derived_counts": validation.get("derived_counts"),
        "unit_kinds": kinds,
        "errors": validation.get("errors") or [],
        "pass": bool(validation.get("ok")) and policy.get("decision") == "PASS",
        "fixture": fixture,
        "historical_raw_not_used_as_202_without_rebuild": True,
        "secrets_included": False,
    }


__all__ = [
    "build_synthetic_202_fixture",
    "historical_replay_201",
    "historical_semantic_observations",
    "synthetic_202_fixture_replay",
]
