"""Charge et vérifie WIN001 candidate v2.1-small. 0 réseau."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.cleanup_application.writer import clean_json_path
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.materialize import materialize_window_content
from app.source_analysis_local_v2.prompt import estimate_v121_request_tokens
from app.source_analysis_small_window_hierarchy.planner import plan_windows_v21_small
from app.source_analysis_v2_link_semantics.identity import future_win001_identity
from app.source_analysis_v2_real_win001.constants import (
    CANDIDATE_PLANNER,
    EXPECTED_ANALYSIS_SIGNATURE,
    EXPECTED_CLEAN_SHA,
    EXPECTED_CONTEXT_COUNT,
    EXPECTED_FIRST_OWNED_SRC,
    EXPECTED_LAST_OWNED_SRC,
    EXPECTED_OWNED_SRC_COUNT,
    EXPECTED_WINDOW_INPUT_HASH,
    EXPECTED_WORD_COUNT,
    PROJECT_NAME,
    WINDOW_ID,
)
from app.source_analysis_v2_real_win001.guard import RealWin001Error


def load_candidate_win001(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    plan = plan_windows_v21_small(transcript)
    try:
        window = next(item for item in plan.windows if item.window_id == WINDOW_ID)
    except StopIteration as exc:
        raise RealWin001Error("WIN001 absent from candidate small plan.") from exc
    content = materialize_window_content(transcript, window)
    estimate = estimate_v121_request_tokens(transcript, window, content=content)
    identity = future_win001_identity(window, transcript)
    clean_path = clean_json_path(project_name, sortie_dir=sortie_dir)
    return {
        "transcript": transcript,
        "plan": plan,
        "window": window,
        "content": content,
        "estimate": estimate,
        "identity": identity,
        "clean_file_sha256": sha256_of_file(clean_path) if clean_path.is_file() else None,
    }


def verify_win001_identity(bundle: dict[str, Any]) -> dict[str, Any]:
    transcript = bundle["transcript"]
    window = bundle["window"]
    identity = bundle["identity"]
    estimate = bundle["estimate"]
    errors: list[str] = []
    if window.window_id != WINDOW_ID:
        errors.append(f"window_id={window.window_id!r}")
    if window.planner_version != CANDIDATE_PLANNER:
        errors.append(f"planner={window.planner_version!r}")
    if window.first_owned_src_ref != EXPECTED_FIRST_OWNED_SRC:
        errors.append(f"first_owned={window.first_owned_src_ref}")
    if window.last_owned_src_ref != EXPECTED_LAST_OWNED_SRC:
        errors.append(f"last_owned={window.last_owned_src_ref}")
    if window.owned_src_count != EXPECTED_OWNED_SRC_COUNT:
        errors.append(f"owned_src_count={window.owned_src_count}")
    if window.word_count != EXPECTED_WORD_COUNT:
        errors.append(f"word_count={window.word_count}")
    if window.input_hash != EXPECTED_WINDOW_INPUT_HASH:
        errors.append(f"input_hash={window.input_hash}")
    if window.context_src_count != EXPECTED_CONTEXT_COUNT:
        errors.append(f"context_src_count={window.context_src_count}")
    if transcript.content_sha256 != EXPECTED_CLEAN_SHA:
        errors.append(f"clean_sha={transcript.content_sha256}")
    if identity["analysis_signature"] != EXPECTED_ANALYSIS_SIGNATURE:
        errors.append(f"signature={identity['analysis_signature']}")
    if identity.get("forensic_collides"):
        errors.append("forensic identity collides with historical call")
    if identity.get("cache") != "MISS" and identity["analysis_signature"] == EXPECTED_ANALYSIS_SIGNATURE:
        # Historical signature set does not include A.15; cache field is MISS vs those.
        pass
    if errors:
        raise RealWin001Error(
            "WIN001 identity differs from A.14 freeze — STOP WITHOUT NETWORK: "
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
        "local_input_estimate": estimate["total_tokens"],
        "cache": identity["cache"],
        "cache_collisions": identity["cache_collisions"],
        "forensic_collides": identity["forensic_collides"],
        "clean_provenance": "DERIVED",
        "context_policy": "NONE",
    }


__all__ = ["load_candidate_win001", "verify_win001_identity"]
