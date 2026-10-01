"""Replay contre-factuel : une seule substitution SRec007337→SRC007337. Copie dérivée."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.source_analysis_local_v2.granularity import validate_v2_transport_granularity
from app.source_analysis_v31_final_three.canonical import reconstruct_mixed
from app.source_analysis_v31_final_three.paths import candidate_window_dir
from app.source_analysis_v31_real_win004.validate import interpret_local_lite_response
from app.source_analysis_v31_remaining_windows.review import review_transport
from app.source_analysis_v31_src_typo_forensics.constants import (
    EXPECTED_CANONICAL,
    MALFORMED_TOKEN,
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    WIN007_RAW_SHA256,
    WIN007_SIGNATURE,
    WINDOW_ID,
)
from app.source_analysis_v31_src_typo_forensics.evidence import (
    read_win007_raw_bytes,
    win007_raw_path,
)
from app.source_analysis_v31_src_typo_forensics.replay import derived_single_correction


def _technical_pass(validation: Mapping[str, Any]) -> bool:
    return (
        validation.get("structured_parse") == "PASS"
        and validation.get("v31_decoder") == "PASS"
        and validation.get("handle_registry") == "PASS"
        and validation.get("handle_resolution") == "PASS"
        and validation.get("v31_validator") == "PASS"
        and not list(validation.get("errors") or [])
    )


def replay_derived_correction(
    replay: Mapping[str, Any],
    *,
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    original = replay["payload"]
    if not isinstance(original, dict):
        raise ValueError("WIN007 payload absent for counterfactual")
    derived = derived_single_correction(original)
    raw_before = win007_raw_path(project_name, sortie_dir=sortie_dir).read_bytes()
    window = replay["window"]
    transcript = replay["transcript"]
    validation = interpret_local_lite_response(derived, window=window)
    length_ok = True
    length_error = None
    transport = validation.get("transport")
    if isinstance(transport, dict):
        try:
            validate_v2_transport_granularity(transport)
        except Exception as exc:  # noqa: BLE001
            length_ok = False
            length_error = str(exc)
    technical_ok = _technical_pass(validation) and length_ok
    other_errors = list(validation.get("errors") or [])
    if length_error:
        other_errors.append(length_error)
    src_forensic = validation.get("src_forensic") or {}
    semantic = None
    if technical_ok:
        semantic = review_transport(
            transport if isinstance(transport, dict) else None,
            window=window,
            transcript=transcript,
            capacity_signal=bool(validation.get("capacity_signal")),
            handle_gate_pass=bool(
                (validation.get("handle_gate") or {}).get("handle_gate_pass")
            ),
            technical_ok=True,
            src_audit=validation.get("src_audit"),
        )
    canonical = None
    mixed = None
    if technical_ok and isinstance(transport, dict):
        canonical = reconstruct_mixed(
            transport,
            window,
            signature=WIN007_SIGNATURE,
            project_name=project_name,
            sortie_dir=sortie_dir,
        )
        from app.source_analysis_local_v3.decoder import decode_v31_local_lite_transport
        from app.source_analysis_v31_real_win004.canonical import normalized_src_refs

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
                payload = json.loads(path.read_text(encoding="utf-8"))
                try:
                    decode_v31_local_lite_transport(
                        payload,
                        allowed_source_refs=set(normalized_src_refs(payload)),
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
        mixed = {
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
            "consolidated": False,
            "production_cache_written": False,
        }
    raw_after = read_win007_raw_bytes(project_name, sortie_dir=sortie_dir)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "derived_only": True,
        "original_raw_unchanged": raw_before == raw_after
        and hashlib_sha(raw_after) == WIN007_RAW_SHA256,
        "original_payload_token_still_srec": (
            (original.get("records") or [{}])[13].get("s") or [None, None]
        )[1]
        == MALFORMED_TOKEN,
        "derived_token": (
            (derived.get("records") or [{}])[13].get("s") or [None, None]
        )[1],
        "only_change": f"{MALFORMED_TOKEN}→{EXPECTED_CANONICAL}",
        "structured_parse": validation.get("structured_parse"),
        "v31_decoder": validation.get("v31_decoder"),
        "handle_registry": validation.get("handle_registry"),
        "handle_resolution": validation.get("handle_resolution"),
        "v31_validator": validation.get("v31_validator"),
        "length_policy": "PASS" if length_ok else "FAIL",
        "capacity_signal": validation.get("capacity_signal"),
        "errors": other_errors,
        "technical": "PASS" if technical_ok else "FAIL",
        "other_technical_failures_after_correction": other_errors,
        "sole_root_cause": technical_ok,
        "src_forensic": src_forensic,
        "eligible_for_semantic_review": technical_ok,
        "semantic_review": semantic,
        "canonical": canonical,
        "mixed_compatibility": None
        if mixed is None
        else mixed.get("mixed_compatibility"),
        "mixed": mixed,
        "promoted": False,
        "production_policy_mutated": False,
        "derived_payload": derived,
        "validation": validation,
    }


def hashlib_sha(raw: bytes) -> str:
    import hashlib

    return hashlib.sha256(raw).hexdigest()


def jsonable_counterfactual(counterfactual: Mapping[str, Any]) -> dict[str, Any]:
    skip = {
        "derived_payload",
        "validation",
        "semantic_review",
        "canonical",
        "mixed",
        "window",
        "transcript",
    }
    public = {key: value for key, value in counterfactual.items() if key not in skip}
    semantic = counterfactual.get("semantic_review")
    if isinstance(semantic, Mapping):
        public["semantic_review_summary"] = {
            "semantic_quality": semantic.get("semantic_quality"),
            "unsupported_count": semantic.get("unsupported_count")
            or semantic.get("material_unsupported"),
            "material_omissions": semantic.get("material_omissions"),
            "relation_quality_summary": semantic.get("relation_quality_summary"),
            "grounding_counts": semantic.get("grounding_counts"),
            "transport_valid": semantic.get("transport_valid"),
            "status": semantic.get("status"),
            "beginning": semantic.get("beginning"),
            "middle": semantic.get("middle"),
            "end": semantic.get("end"),
        }
    canonical = counterfactual.get("canonical")
    if isinstance(canonical, Mapping):
        public["canonical_summary"] = {
            "idea_validation": (canonical.get("local") or canonical).get(
                "idea_validation"
            ),
            "all_kinds_empty": (canonical.get("local") or canonical).get(
                "all_kinds_empty"
            ),
            "importance_to_kind_contamination": (
                canonical.get("local") or canonical
            ).get("importance_to_kind_contamination"),
            "mixed_compatibility": canonical.get("mixed_compatibility"),
        }
    return public


def dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2)


__all__ = [
    "jsonable_counterfactual",
    "replay_derived_correction",
]
