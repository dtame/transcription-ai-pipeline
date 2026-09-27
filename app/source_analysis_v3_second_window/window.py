"""Charge et vérifie la fenêtre sélectionnée v2.1-small + identité V3 1.3.1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.cleanup_application.writer import clean_json_path
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.materialize import materialize_window_content
from app.source_analysis_local_v3.prompt import estimate_v131_request_tokens
from app.source_analysis_small_window_hierarchy.planner import plan_windows_v21_small
from app.source_analysis_v3_a19_forensics.future_retry import future_v131_win001_identity
from app.source_analysis_v3_hardened_win001.window import load_candidate_win001
from app.source_analysis_v3_second_window.constants import (
    A13_SYNTHETIC_IDENTITY,
    A15_V2_SIGNATURE,
    A18_REQUEST_IDENTITY,
    A19_V3_FORENSIC,
    A19_V3_SIGNATURE,
    A21_V3_FORENSIC,
    A21_V3_SIGNATURE,
    CALL1_SIGNATURE,
    CALL2_SIGNATURE,
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    CANDIDATE_PLANNER,
    EXPECTED_CLEAN_FILE_SHA,
    EXPECTED_CLEAN_SHA,
    EXPECTED_CONTEXT_COUNT,
    EXPECTED_PROMPT_FINGERPRINT,
    EXPECTED_PROMPT_SHA256,
    EXPECTED_WIN004_FIRST_OWNED_SRC,
    EXPECTED_WIN004_INPUT_HASH,
    EXPECTED_WIN004_LAST_OWNED_SRC,
    EXPECTED_WIN004_OWNED_SRC_COUNT,
    EXPECTED_WIN004_WORD_COUNT,
    PREFERRED_WINDOW_ID,
    PROJECT_NAME,
    SMALL_SIGNATURE,
)
from app.source_analysis_v3_second_window.guard import SecondWindowError
from app.source_analysis_v3_second_window.selection import select_representative_window


def load_selected_window(
    project_name: str = PROJECT_NAME,
    *,
    requested_window_id: str | None = None,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    selection = select_representative_window(transcript)
    selected_id = selection["selected_window_id"]
    if requested_window_id:
        requested = str(requested_window_id).strip()
        if requested and requested != selected_id:
            raise SecondWindowError(
                f"Requested {requested!r} is not the selected target {selected_id!r}."
            )
    plan = plan_windows_v21_small(transcript)
    try:
        window = next(item for item in plan.windows if item.window_id == selected_id)
    except StopIteration as exc:
        raise SecondWindowError(
            f"{selected_id} absent from candidate small plan."
        ) from exc
    content = materialize_window_content(transcript, window)
    estimate = estimate_v131_request_tokens(transcript, window, content=content)
    identity = future_v131_win001_identity(window, transcript)
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
    }
    collisions = {
        name: value == identity["analysis_signature"]
        or value == identity["forensic_identity"]
        for name, value in historical.items()
    }
    identity = dict(identity)
    identity["historical"] = historical
    identity["cache_collisions"] = collisions
    identity["forensic_collides"] = any(collisions.values())
    identity["cache"] = (
        "HIT" if identity["analysis_signature"] in historical.values() else "MISS"
    )
    clean_path = clean_json_path(project_name, sortie_dir=sortie_dir)
    a21 = load_candidate_win001(project_name, sortie_dir=sortie_dir)
    return {
        "transcript": transcript,
        "plan": plan,
        "window": window,
        "content": content,
        "estimate": estimate,
        "identity": identity,
        "selection": selection,
        "clean_file_sha256": sha256_of_file(clean_path) if clean_path.is_file() else None,
        "a21_window": a21["window"],
        "a21_identity": a21["identity"],
    }


def verify_selected_identity(bundle: dict[str, Any]) -> dict[str, Any]:
    transcript = bundle["transcript"]
    window = bundle["window"]
    identity = bundle["identity"]
    estimate = bundle["estimate"]
    selection = bundle["selection"]
    a21_window = bundle["a21_window"]
    errors: list[str] = []
    selected_id = selection["selected_window_id"]
    if window.window_id != selected_id:
        errors.append(f"window_id={window.window_id!r} selected={selected_id!r}")
    if window.window_id == "WIN001":
        errors.append("selected WIN001 — forbidden")
    if window.planner_version != CANDIDATE_PLANNER:
        errors.append(f"planner={window.planner_version!r}")
    if window.context_src_count != EXPECTED_CONTEXT_COUNT:
        errors.append(f"context_src_count={window.context_src_count}")
    if list(window.owned_src_refs) == list(a21_window.owned_src_refs):
        errors.append("owned SRC refs collide with A.21 WIN001")
    if window.input_hash == a21_window.input_hash:
        errors.append("window input_hash collides with A.21 WIN001")
    if selected_id == PREFERRED_WINDOW_ID:
        if window.first_owned_src_ref != EXPECTED_WIN004_FIRST_OWNED_SRC:
            errors.append(f"first_owned={window.first_owned_src_ref}")
        if window.last_owned_src_ref != EXPECTED_WIN004_LAST_OWNED_SRC:
            errors.append(f"last_owned={window.last_owned_src_ref}")
        if window.owned_src_count != EXPECTED_WIN004_OWNED_SRC_COUNT:
            errors.append(f"owned_src_count={window.owned_src_count}")
        if window.word_count != EXPECTED_WIN004_WORD_COUNT:
            errors.append(f"word_count={window.word_count}")
        if window.input_hash != EXPECTED_WIN004_INPUT_HASH:
            errors.append(f"input_hash={window.input_hash}")
    if transcript.content_sha256 != EXPECTED_CLEAN_SHA:
        errors.append(f"clean_sha={transcript.content_sha256}")
    if bundle.get("clean_file_sha256") != EXPECTED_CLEAN_FILE_SHA:
        errors.append(f"clean_file_sha={bundle.get('clean_file_sha256')}")
    if identity["analysis_signature"] == A21_V3_SIGNATURE:
        errors.append("A.22 signature collided with A.21 V3 signature")
    if identity["forensic_identity"] == A21_V3_FORENSIC:
        errors.append("A.22 forensic identity collided with A.21")
    if identity["analysis_signature"] == A19_V3_SIGNATURE:
        errors.append("A.22 signature collided with A.19 V3 signature")
    if identity["forensic_identity"] == A19_V3_FORENSIC:
        errors.append("A.22 forensic identity collided with A.19")
    if identity["analysis_signature"] == A15_V2_SIGNATURE:
        errors.append("A.22 signature collided with A.15 V2 signature")
    if identity["analysis_signature"] == A18_REQUEST_IDENTITY:
        errors.append("A.22 signature collided with A.18 canary identity")
    if identity["analysis_signature"] in {
        CALL1_SIGNATURE,
        CALL2_SIGNATURE,
        SMALL_SIGNATURE,
        A13_SYNTHETIC_IDENTITY,
    }:
        errors.append("A.22 signature collided with historical call")
    if identity.get("forensic_collides"):
        errors.append("forensic identity collides with historical call")
    if identity.get("cache") != "MISS":
        errors.append(f"cache={identity.get('cache')}")
    if identity.get("prompt_sha256") != EXPECTED_PROMPT_SHA256:
        errors.append(f"prompt_sha={identity.get('prompt_sha256')}")
    if identity.get("prompt_fingerprint") == EXPECTED_PROMPT_FINGERPRINT:
        errors.append("prompt fingerprint collided with A.21 WIN001 user prompt")
    local_est = int(estimate["total_tokens"])
    if local_est > CANDIDATE_HARD_MAX_INPUT_TOKENS:
        errors.append("local estimate exceeds candidate hard max 35000")
    if errors:
        raise SecondWindowError(
            "Selected-window 1.3.1 identity unexpected — STOP WITHOUT NETWORK: "
            + "; ".join(errors)
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
        "differs_from_a21_signature": True,
        "differs_from_a21_ownership": True,
        "differs_from_a19_signature": True,
        "selection_reason": selection["selection_reason"],
        "win004_used": selection["win004_used"],
    }


__all__ = ["load_selected_window", "verify_selected_identity"]
