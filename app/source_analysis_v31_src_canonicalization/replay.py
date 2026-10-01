"""Replay offline WIN007 : politique stricte 1.0 vs canonicalisation 1.1. 0 provider."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.source_analysis.errors import WindowGranularityLimitExceeded
from app.source_analysis_local_v2.granularity import (
    EXAMPLE_V_TEXT_HARD_LIMIT,
    validate_v2_transport_granularity,
)
from app.source_analysis_local_v3.constants import (
    SRC_REFERENCE_POLICY_VERSION_10_STRICT,
    SRC_REFERENCE_POLICY_VERSION_11_NARROW_CANONICALIZATION,
)
from app.source_analysis_local_v3.src_canonicalization import (
    apply_src_reference_policy,
    clean_transcript_src_ids,
)
from app.source_analysis_v31_final_three.canonical import reconstruct_mixed
from app.source_analysis_v31_final_three.paths import candidate_window_dir
from app.source_analysis_v31_real_win004.validate import interpret_local_lite_response
from app.source_analysis_v31_remaining_windows.review import review_transport
from app.source_analysis_v31_remaining_windows.window import load_candidate_plan
from app.source_analysis_v31_src_canonicalization.constants import (
    A31_VALIDATOR_ERROR,
    EXPECTED_CANONICAL,
    EXPECTED_CANONICALIZED_SRC,
    EXPECTED_EXAMPLE_LIMIT,
    EXPECTED_EXAMPLE_MAX_CHARS,
    EXPECTED_RAW_EXACT_SRC,
    EXPECTED_RAW_MALFORMED_SRC,
    EXPECTED_RAW_SRC_TOTAL,
    EXPECTED_REJECTED_MALFORMED_SRC,
    MALFORMED_TOKEN,
    MODE,
    PHASE,
    PROJECT_NAME,
    RECORD_INDEX,
    RECORD_S_POSITION,
    SCHEMA_VERSION,
    SRC_POLICY_NEW,
    SRC_POLICY_OLD,
    WIN007_RAW_SHA256,
    WIN007_SIGNATURE,
    WINDOW_ID,
)
from app.source_analysis_v31_src_canonicalization.identity import (
    verify_saved_win007_identity,
)
from app.source_analysis_v31_src_typo_forensics.evidence import (
    read_win007_raw_bytes,
    win007_raw_path,
)
from app.source_analysis_v31_src_typo_forensics.replay import replay_win007_offline


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _technical_pass(validation: dict[str, Any], *, length_ok: bool) -> bool:
    return (
        validation.get("structured_parse") == "PASS"
        and validation.get("v31_decoder") == "PASS"
        and validation.get("handle_registry") == "PASS"
        and validation.get("handle_resolution") == "PASS"
        and validation.get("v31_validator") == "PASS"
        and length_ok
        and not list(validation.get("errors") or [])
    )


def measure_lengths(transport: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(transport, dict):
        return {
            "theme": 0,
            "EXAMPLE_max": 0,
            "IDEA_max": 0,
            "example_limit": EXAMPLE_V_TEXT_HARD_LIMIT,
        }
    example_max = 0
    idea_max = 0
    for item in transport.get("records") or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("k") or "")
        value = str(item.get("v") or "")
        if kind == "EXAMPLE":
            example_max = max(example_max, len(value))
        if kind == "IDEA":
            idea_max = max(idea_max, len(value))
    return {
        "theme": len(str(transport.get("theme") or "")),
        "EXAMPLE_max": example_max,
        "IDEA_max": idea_max,
        "example_limit": EXAMPLE_V_TEXT_HARD_LIMIT,
        "example_max_within_limit": example_max <= EXAMPLE_V_TEXT_HARD_LIMIT,
    }


def _observed_token(payload: dict[str, Any] | None) -> Any:
    if not isinstance(payload, dict):
        return None
    records = payload.get("records") or []
    if len(records) <= RECORD_INDEX or not isinstance(records[RECORD_INDEX], dict):
        return None
    refs = records[RECORD_INDEX].get("s") or []
    if len(refs) <= RECORD_S_POSITION:
        return None
    return refs[RECORD_S_POSITION]


def replay_strict_and_canonical(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    identity = verify_saved_win007_identity(project_name, sortie_dir=sortie_dir)
    raw_before = win007_raw_path(project_name, sortie_dir=sortie_dir).read_bytes()
    strict = replay_win007_offline(project_name, sortie_dir=sortie_dir)
    payload = strict.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("WIN007 parsed payload absent")
    original_token = _observed_token(payload)
    bundle = load_candidate_plan(project_name, sortie_dir=sortie_dir)
    window = bundle["windows"][WINDOW_ID]
    transcript = bundle["transcript"]
    owned = set(window.owned_src_refs)
    existing = clean_transcript_src_ids(transcript)
    strict_applied = apply_src_reference_policy(
        payload,
        owned=owned,
        existing=existing,
        policy_version=SRC_REFERENCE_POLICY_VERSION_10_STRICT,
    )
    derived_applied = apply_src_reference_policy(
        payload,
        owned=owned,
        existing=existing,
        policy_version=SRC_REFERENCE_POLICY_VERSION_11_NARROW_CANONICALIZATION,
    )
    derived = derived_applied["derived"]
    derived_audit = derived_applied["audit"]
    if original_token != MALFORMED_TOKEN:
        raise ValueError(f"WIN007 raw token drift: {original_token!r}")
    if _observed_token(payload) != MALFORMED_TOKEN:
        raise ValueError("canonicalizer mutated the original parsed payload")
    derived_token = _observed_token(derived)
    extra_canonicalizations = int(derived_audit.get("canonicalized_src_count") or 0)
    if extra_canonicalizations > 1:
        raise RuntimeError(
            "A.33 WIN007 bound exceeded: more than one SRC canonicalization"
        )
    derived_validation = interpret_local_lite_response(derived, window=window)
    length_error = None
    length_ok = False
    transport = derived_validation.get("transport")
    if isinstance(transport, dict):
        try:
            validate_v2_transport_granularity(transport)
            length_ok = True
        except WindowGranularityLimitExceeded as exc:
            length_error = str(exc)
    lengths = measure_lengths(transport if isinstance(transport, dict) else None)
    technical_ok = _technical_pass(derived_validation, length_ok=length_ok)
    src_ok = bool((derived_validation.get("src_forensic") or {}).get("src_success"))
    metadata = derived_validation.get("metadata") or {}
    handle_gate = derived_validation.get("handle_gate") or {}
    handle_ok = bool(handle_gate.get("handle_gate_pass"))
    numeric = handle_gate.get("numeric_link_regression") == "YES"
    capacity = bool(derived_validation.get("capacity_signal"))
    review: dict[str, Any] = {"performed": False, "semantic_quality": None}
    canonical: dict[str, Any] = {}
    if technical_ok and isinstance(transport, dict):
        review = review_transport(
            transport,
            window=window,
            transcript=transcript,
            capacity_signal=capacity,
            handle_gate_pass=handle_ok,
            technical_ok=True,
            src_audit=derived_validation.get("src_audit"),
        )
        canonical = reconstruct_mixed(
            transport,
            window,
            signature=WIN007_SIGNATURE,
            project_name=project_name,
            sortie_dir=sortie_dir,
        )
        extra: dict[str, Any] = {}
        extra_ok = True
        for window_id in ("WIN005", "WIN006"):
            path = (
                candidate_window_dir(project_name, window_id, sortie_dir=sortie_dir)
                / "transport.json"
            )
            readable = False
            error = None
            if path.is_file():
                import json

                extra_payload = json.loads(path.read_text(encoding="utf-8"))
                try:
                    from app.source_analysis_local_v3.decoder import (
                        decode_v31_local_lite_transport,
                    )
                    from app.source_analysis_v31_real_win004.canonical import (
                        normalized_src_refs,
                    )

                    decode_v31_local_lite_transport(
                        extra_payload,
                        allowed_source_refs=set(normalized_src_refs(extra_payload)),
                    )
                    readable = True
                except Exception as exc:  # noqa: BLE001
                    extra_ok = False
                    error = str(exc)
            else:
                extra_ok = False
                error = "candidate transport missing"
            extra[window_id] = {
                "present": path.is_file(),
                "readable_as_local_lite": readable,
                "error": error,
            }
        mixed_status = canonical.get("mixed_compatibility")
        if extra_ok and mixed_status == "PASS":
            mixed_status = "PASS"
        elif not extra_ok:
            mixed_status = "FAIL"
        canonical = {
            **canonical,
            "mixed_compatibility": mixed_status,
            "ready_windows_checked": (
                "WIN001",
                "WIN002",
                "WIN003",
                "WIN004",
                "WIN005",
                "WIN006",
            ),
            "win005_win006_candidates": extra,
        }
    raw_after = read_win007_raw_bytes(project_name, sortie_dir=sortie_dir)
    inventory = strict.get("src_inventory") or {}
    errors = list(derived_validation.get("errors") or [])
    if length_error:
        errors.append(length_error)
    correction_ok = (
        extra_canonicalizations == EXPECTED_CANONICALIZED_SRC
        and derived_token == EXPECTED_CANONICAL
        and original_token == MALFORMED_TOKEN
        and int(derived_audit.get("rejected_malformed_src_count") or 0)
        == EXPECTED_REJECTED_MALFORMED_SRC
        and int(derived_audit.get("raw_malformed_src_count") or 0)
        == EXPECTED_RAW_MALFORMED_SRC
    )
    historical_ok = (
        original_token == MALFORMED_TOKEN
        and strict.get("reproduced") is True
        and strict.get("v31_decoder") == "FAIL"
        and any(
            A31_VALIDATOR_ERROR in err or MALFORMED_TOKEN in err
            for err in (strict.get("validation_errors") or [])
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "window_id": WINDOW_ID,
        "identity": identity,
        "analysis_signature": WIN007_SIGNATURE,
        "src_policy_old": SRC_POLICY_OLD,
        "src_policy_new": SRC_POLICY_NEW,
        "strict_historical_replay": "FAIL as expected" if historical_ok else "FAIL unexpected",
        "strict_reproduced": historical_ok,
        "strict_decoder": strict.get("v31_decoder"),
        "strict_validator": strict.get("v31_validator"),
        "strict_errors": list(strict.get("validation_errors") or []),
        "strict_root": A31_VALIDATOR_ERROR if historical_ok else None,
        "strict_policy_applied": strict_applied["audit"],
        "raw_src_tokens": inventory.get("total_src_occurrences"),
        "raw_exact_src": inventory.get("exact_valid_occurrences"),
        "raw_malformed_src": inventory.get("malformed_occurrences"),
        "expected_raw_src_tokens": EXPECTED_RAW_SRC_TOTAL,
        "expected_raw_exact_src": EXPECTED_RAW_EXACT_SRC,
        "expected_raw_malformed_src": EXPECTED_RAW_MALFORMED_SRC,
        "raw_totals_unchanged": (
            inventory.get("total_src_occurrences") == EXPECTED_RAW_SRC_TOTAL
            and inventory.get("exact_valid_occurrences") == EXPECTED_RAW_EXACT_SRC
            and inventory.get("malformed_occurrences") == EXPECTED_RAW_MALFORMED_SRC
        ),
        "canonicalized_src": derived_audit.get("canonicalized_src_count"),
        "rejected_malformed_src": derived_audit.get("rejected_malformed_src_count"),
        "raw_malformed_from_policy": derived_audit.get("raw_malformed_src_count"),
        "raw_token": original_token,
        "canonical_token": derived_token,
        "authorized_mapping": f"{MALFORMED_TOKEN}→{EXPECTED_CANONICAL}",
        "correction_ok": correction_ok,
        "exactly_one_canonicalization": extra_canonicalizations == 1,
        "derived_audit": derived_audit,
        "strict_raw_validity": derived_audit.get("strict_raw_validity"),
        "derived_canonical_validity": derived_audit.get("derived_canonical_validity"),
        "structured_parse": derived_validation.get("structured_parse"),
        "decoder": derived_validation.get("v31_decoder"),
        "handle_registry": derived_validation.get("handle_registry"),
        "handle_resolution": derived_validation.get("handle_resolution"),
        "handles": _status(handle_ok),
        "src": _status(src_ok),
        "local_validator": _status(
            derived_validation.get("v31_validator") == "PASS" and length_ok
        ),
        "v31_validator": derived_validation.get("v31_validator"),
        "length_policy": _status(length_ok),
        "length_error": length_error,
        "lengths": lengths,
        "example_max": lengths.get("EXAMPLE_max"),
        "example_max_expected": EXPECTED_EXAMPLE_MAX_CHARS,
        "example_limit": EXPECTED_EXAMPLE_LIMIT,
        "numeric_regression": "YES" if numeric else "NO",
        "capacity": "present" if capacity else "absent",
        "metadata": metadata,
        "subtype_leakage": int(metadata.get("idea_subtype_leakage") or 0),
        "old_v3_shape": int(metadata.get("old_v3_idea_shape") or 0),
        "invalid_importance": int(metadata.get("invalid_importance") or 0),
        "technical_ok": technical_ok and src_ok and handle_ok and not numeric and not capacity,
        "review": review,
        "semantic_quality": review.get("semantic_quality"),
        "unsupported_content": review.get("unsupported_content"),
        "unsupported_count": review.get("unsupported_count"),
        "material_omissions": review.get("material_omissions"),
        "relation_quality_summary": review.get("relation_quality_summary"),
        "canonical": canonical,
        "canonical_reconstruction": (canonical.get("local") or canonical).get(
            "idea_validation"
        )
        if canonical
        else None,
        "mixed_compatibility": canonical.get("mixed_compatibility"),
        "importance_to_kind_contamination": (canonical.get("local") or {}).get(
            "importance_to_kind_contamination"
        ),
        "all_kinds_empty": (canonical.get("local") or {}).get("all_kinds_empty"),
        "local_idea_kind": (canonical.get("local") or {}).get("idea_kinds"),
        "raw_response_mutated": hashlib.sha256(raw_after).hexdigest() != WIN007_RAW_SHA256
        or raw_after != raw_before,
        "original_payload_token_still_srec": original_token == MALFORMED_TOKEN
        and _observed_token(payload) == MALFORMED_TOKEN,
        "derived_payload": derived,
        "transport": transport,
        "window": window,
        "transcript": transcript,
        "strict_replay": strict,
        "derived_validation": derived_validation,
        "validation_errors": errors,
        "provider_calls": 0,
        "response_repaired": False,
        "normalized": False,
    }


__all__ = ["measure_lengths", "replay_strict_and_canonical"]
