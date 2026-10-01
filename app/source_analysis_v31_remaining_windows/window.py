"""Charge et vérifie les 7 fenêtres v2.1-small + identités v3.1-local-lite. 0 réseau."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.cleanup_application.writer import clean_json_path
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.materialize import materialize_window_content
from app.source_analysis_local_v3.prompt import estimate_v140_request_tokens
from app.source_analysis_small_window_hierarchy.planner import plan_windows_v21_small
from app.source_analysis_v31_local_lite.future import future_v140_win004_identity
from app.source_analysis_v3_hardened_win001.window import load_candidate_win001
from app.source_analysis_v3_second_window.window import load_selected_window
from app.source_analysis_v31_remaining_windows.constants import (
    A13_SYNTHETIC_IDENTITY,
    A15_V2_SIGNATURE,
    A18_REQUEST_IDENTITY,
    A19_V3_FORENSIC,
    A19_V3_SIGNATURE,
    A21_V3_FORENSIC,
    A21_V3_SIGNATURE,
    A22_V3_SIGNATURE,
    A24_V3_FORENSIC,
    A24_V3_SIGNATURE,
    A27_SIGNATURE,
    A27_V31_FORENSIC,
    CALL1_SIGNATURE,
    CALL2_SIGNATURE,
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    CANDIDATE_PLANNER,
    EXPECTED_CLEAN_FILE_SHA,
    EXPECTED_CLEAN_SHA,
    EXPECTED_CONTEXT_COUNT,
    EXPECTED_PROMPT_SHA256,
    PROJECT_NAME,
    SMALL_SIGNATURE,
    WINDOW_SPECS,
)
from app.source_analysis_v31_remaining_windows.guard import RemainingWindowsError

_BUNDLE_CACHE: dict[tuple[str, str | None], dict[str, Any]] = {}


def load_candidate_plan(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    cache_key = (project_name, str(sortie_dir) if sortie_dir is not None else None)
    cached = _BUNDLE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    plan = plan_windows_v21_small(transcript)
    windows = {item.window_id: item for item in plan.windows}
    contents = {}
    estimates = {}
    identities = {}
    historical = {
        "large_1_0_or_call1": CALL1_SIGNATURE,
        "large_1_1_or_call2": CALL2_SIGNATURE,
        "small_1_1": SMALL_SIGNATURE,
        "a13_synthetic_canary": A13_SYNTHETIC_IDENTITY,
        "a15_v2_win001": A15_V2_SIGNATURE,
        "a18_synthetic_canary": A18_REQUEST_IDENTITY,
        "a19_v3_win001": A19_V3_SIGNATURE,
        "a19_forensic": A19_V3_FORENSIC,
        "a21_v3_win001": A21_V3_SIGNATURE,
        "a21_forensic": A21_V3_FORENSIC,
        "a22_v3_win004": A22_V3_SIGNATURE,
        "a24_v3_win004": A24_V3_SIGNATURE,
        "a24_forensic": A24_V3_FORENSIC,
        "a27_v31_win004": A27_SIGNATURE,
        "a27_forensic": A27_V31_FORENSIC,
    }
    for window_id, window in windows.items():
        content = materialize_window_content(transcript, window)
        estimate = estimate_v140_request_tokens(transcript, window, content=content)
        identity = dict(future_v140_win004_identity(window, transcript))
        collisions = {
            name: value == identity["analysis_signature"]
            or value == identity["forensic_identity"]
            for name, value in historical.items()
            if not (window_id == "WIN004" and name.startswith("a27_"))
        }
        identity["historical"] = historical
        identity["cache_collisions"] = collisions
        identity["forensic_collides"] = any(collisions.values())
        identity["cache"] = (
            "HIT"
            if identity["analysis_signature"] in historical.values()
            and window_id != "WIN004"
            else "MISS"
        )
        if window_id == "WIN004":
            identity["cache"] = "MISS"
        contents[window_id] = content
        estimates[window_id] = estimate
        identities[window_id] = identity
    clean_path = clean_json_path(project_name, sortie_dir=sortie_dir)
    a21 = load_candidate_win001(project_name, sortie_dir=sortie_dir)
    a22 = load_selected_window(
        project_name, requested_window_id="WIN004", sortie_dir=sortie_dir
    )
    bundle = {
        "transcript": transcript,
        "plan": plan,
        "windows": windows,
        "contents": contents,
        "estimates": estimates,
        "identities": identities,
        "clean_file_sha256": sha256_of_file(clean_path) if clean_path.is_file() else None,
        "a21_window": a21["window"],
        "a21_identity": a21["identity"],
        "a22_window": a22["window"],
        "a22_identity": a22["identity"],
    }
    _BUNDLE_CACHE[cache_key] = bundle
    return bundle


def verify_window_identity(bundle: dict[str, Any], window_id: str) -> dict[str, Any]:
    spec = WINDOW_SPECS[window_id]
    transcript = bundle["transcript"]
    window = bundle["windows"][window_id]
    identity = bundle["identities"][window_id]
    estimate = bundle["estimates"][window_id]
    a21_window = bundle["a21_window"]
    a22_window = bundle["a22_window"]
    errors: list[str] = []
    if window.window_id != window_id:
        errors.append(f"window_id={window.window_id!r}")
    if window.planner_version != CANDIDATE_PLANNER:
        errors.append(f"planner={window.planner_version!r}")
    if window.first_owned_src_ref != spec["first_owned_src"]:
        errors.append(f"first_owned={window.first_owned_src_ref}")
    if window.last_owned_src_ref != spec["last_owned_src"]:
        errors.append(f"last_owned={window.last_owned_src_ref}")
    if window.owned_src_count != spec["owned_src_count"]:
        errors.append(f"owned_src_count={window.owned_src_count}")
    if window.word_count != spec["word_count"]:
        errors.append(f"word_count={window.word_count}")
    if window.input_hash != spec["input_hash"]:
        errors.append(f"input_hash={window.input_hash}")
    if window.context_src_count != EXPECTED_CONTEXT_COUNT:
        errors.append(f"context_src_count={window.context_src_count}")
    if window_id == "WIN004":
        if list(window.owned_src_refs) != list(a22_window.owned_src_refs):
            errors.append("WIN004 owned SRC refs differ from A.22/A.24")
        if window.input_hash != a22_window.input_hash:
            errors.append("WIN004 input_hash differs from A.22/A.24")
    if window_id == "WIN001":
        if list(window.owned_src_refs) != list(a21_window.owned_src_refs):
            errors.append("WIN001 owned SRC refs differ from A.21")
        if window.input_hash != a21_window.input_hash:
            errors.append("WIN001 input_hash differs from A.21")
    else:
        if list(window.owned_src_refs) == list(a21_window.owned_src_refs):
            errors.append("owned SRC refs collide with A.21 WIN001")
        if window.input_hash == a21_window.input_hash:
            errors.append("window input_hash collides with A.21 WIN001")
    if transcript.content_sha256 != EXPECTED_CLEAN_SHA:
        errors.append(f"clean_sha={transcript.content_sha256}")
    if bundle.get("clean_file_sha256") != EXPECTED_CLEAN_FILE_SHA:
        errors.append(f"clean_file_sha={bundle.get('clean_file_sha256')}")
    if identity["analysis_signature"] != spec["analysis_signature"]:
        errors.append(f"signature={identity['analysis_signature']}")
    if identity["forensic_identity"] != spec["forensic_identity"]:
        errors.append(f"forensic={identity['forensic_identity']}")
    if identity.get("prompt_sha256") != EXPECTED_PROMPT_SHA256:
        errors.append(f"prompt_sha={identity.get('prompt_sha256')}")
    if identity.get("prompt_fingerprint") != spec["prompt_fingerprint"]:
        errors.append(f"prompt_fp={identity.get('prompt_fingerprint')}")
    if window_id != "WIN004" and identity["analysis_signature"] == A27_SIGNATURE:
        errors.append("signature collided with A.27 WIN004")
    if identity.get("forensic_collides"):
        errors.append("forensic identity collides with historical call")
    if identity.get("cache") != "MISS":
        errors.append(f"cache={identity.get('cache')}")
    local_est = int(estimate["total_tokens"])
    if local_est != spec["local_input_estimate"]:
        errors.append(f"local_input={local_est}")
    if local_est > CANDIDATE_HARD_MAX_INPUT_TOKENS:
        errors.append("local estimate exceeds candidate hard max 35000")
    if errors:
        raise RemainingWindowsError(
            f"{window_id} 1.4.0 local-lite identity unexpected — "
            "STOP WITHOUT NETWORK: " + "; ".join(errors)
        )
    return {
        "window_id": window.window_id,
        "planner_version": window.planner_version,
        "first_owned_src_ref": window.first_owned_src_ref,
        "last_owned_src_ref": window.last_owned_src_ref,
        "owned_src_count": window.owned_src_count,
        "word_count": window.word_count,
        "input_hash": window.input_hash,
        "context_src_count": window.context_src_count,
        "clean_sha256": transcript.content_sha256,
        "clean_file_sha256": bundle.get("clean_file_sha256"),
        "transcript_id": transcript.transcript_id,
        "primary_language": transcript.primary_language,
        "analysis_signature": identity["analysis_signature"],
        "forensic_identity": identity["forensic_identity"],
        "prompt_version": identity["prompt_version"],
        "prompt_sha256": identity["prompt_sha256"],
        "prompt_fingerprint": identity["prompt_fingerprint"],
        "schema_sha256": identity["schema_sha256"],
        "thinking_mode": identity["thinking_identity"]["thinking_mode"],
        "effort": identity["thinking_identity"]["effort"],
        "local_input_estimate": local_est,
        "cache": identity["cache"],
        "cache_collisions": identity["cache_collisions"],
        "forensic_collides": identity["forensic_collides"],
        "clean_provenance": "DERIVED",
        "context_policy": "NONE",
        "authorized": spec["authorized"],
        "historical_ready": spec["ready"],
    }


def verify_all_windows(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if len(bundle["windows"]) != 7:
        raise RemainingWindowsError(
            f"Expected 7 v2.1-small windows, got {len(bundle['windows'])}."
        )
    verified = {
        window_id: verify_window_identity(bundle, window_id)
        for window_id in WINDOW_SPECS
    }
    win001 = verified["WIN001"]
    win004 = verified["WIN004"]
    if win001["owned_src_count"] != 1195 or win001["word_count"] != 5447:
        raise RemainingWindowsError("WIN001 historical ownership drifted.")
    if win004["owned_src_count"] != 1180 or win004["word_count"] != 5662:
        raise RemainingWindowsError("WIN004 historical ownership drifted.")
    return verified


__all__ = ["load_candidate_plan", "verify_all_windows", "verify_window_identity"]
