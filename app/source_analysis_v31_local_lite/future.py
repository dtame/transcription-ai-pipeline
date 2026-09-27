"""Préflight offline futur WIN004 local-lite. 0 réseau. Non autorisé."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ai.thinking import thinking_fingerprint, thinking_identity
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_models import (
    TARGET_MODEL,
    TARGET_PROVIDER,
    WINDOW_MAX_OUTPUT_TOKENS,
)
from app.source_analysis.window_signature import (
    WindowSignatureInputs,
    build_window_analysis_signature,
)
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v3.constants import CANDIDATE_PLANNER_VERSION
from app.source_analysis_local_v3.pipeline import build_v140_window_request
from app.source_analysis_local_v3.prompt import (
    build_window_system_prompt_v140,
    build_window_user_prompt_v140,
    estimate_v140_request_tokens,
    window_prompt_v140_fingerprint,
    window_prompt_v140_sha256,
)
from app.source_analysis_local_v3.schema import semantic_transport_v31_local_lite_fingerprint
from app.source_analysis_small_window_hierarchy.planner import plan_windows_v21_small
from app.source_analysis_thinking_contract.signature import v2_forensic_identity
from app.source_analysis_v31_local_lite.constants import (
    A21_SIGNATURE,
    A22_SIGNATURE,
    A24_SIGNATURE,
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    FUTURE_REAL_CALL_AUTHORIZED,
    MODE,
    NEXT_PHASE_LABEL,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    THINKING,
    TRANSPORT_VERSION,
    WIN004_RETRY_AUTHORIZED,
)


def future_v140_win004_identity(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    provider: str = TARGET_PROVIDER,
    model: str = TARGET_MODEL,
    max_output_tokens: int = WINDOW_MAX_OUTPUT_TOKENS,
    context_safety_ratio: float = 0.7,
) -> dict[str, Any]:
    system = build_window_system_prompt_v140(transcript.primary_language)
    user = build_window_user_prompt_v140(transcript, window)
    prompt_sha = window_prompt_v140_sha256(system)
    prompt_fp = window_prompt_v140_fingerprint(system, user)
    schema_sha = semantic_transport_v31_local_lite_fingerprint()
    thinking = thinking_identity(thinking_mode=THINKING, effort=None)
    inputs = WindowSignatureInputs(
        window_input_hash=window.input_hash,
        window_id=window.window_id,
        transcript_id=transcript.transcript_id,
        transcript_sha256=transcript.content_sha256,
        planner_version=window.planner_version or CANDIDATE_PLANNER_VERSION,
        prompt_version=PROMPT_VERSION,
        prompt_sha256=prompt_fp,
        transport_version=TRANSPORT_VERSION,
        response_schema_sha256=schema_sha,
        provider=provider,
        model=model,
        temperature=None,
        max_output_tokens=max_output_tokens,
        output_language=transcript.primary_language,
        context_safety_ratio=float(context_safety_ratio),
        thinking_mode=THINKING,
        effort=None,
    )
    signature = build_window_analysis_signature(inputs)
    forensic = v2_forensic_identity(
        window_id=window.window_id,
        content_sha256=transcript.content_sha256,
        thinking_mode=THINKING,
        effort=None,
        prompt_sha256=prompt_fp,
        schema_sha256=schema_sha,
    )
    request = build_v140_window_request(window, transcript, model=model)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "executed": False,
        "authorized": False,
        "window_id": window.window_id,
        "analysis_signature": signature,
        "forensic_identity": forensic,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_sha,
        "prompt_fingerprint": prompt_fp,
        "schema_sha256": schema_sha,
        "thinking_mode": THINKING,
        "effort": None,
        "thinking_identity": thinking,
        "thinking_fingerprint": thinking_fingerprint(THINKING, None),
        "planner_version": window.planner_version or CANDIDATE_PLANNER_VERSION,
        "transport": TRANSPORT_VERSION,
        "max_output_tokens": max_output_tokens,
        "differs_from_a22_signature": signature != A22_SIGNATURE,
        "differs_from_a24_signature": signature != A24_SIGNATURE,
        "differs_from_a21_signature": signature != A21_SIGNATURE,
        "a22_signature": A22_SIGNATURE,
        "a24_signature": A24_SIGNATURE,
        "cache": "MISS",
        "request_prompt_version": request.metadata.get("prompt_version"),
        "request_transport": request.metadata.get("transport_version"),
        "signature_inputs": inputs.to_dict(),
    }


def build_future_win004_readiness(
    *,
    schema_identity: dict[str, Any],
    estimates: dict[str, Any],
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    plan = plan_windows_v21_small(transcript)
    window = next(item for item in plan.windows if item.window_id == "WIN004")
    identity = future_v140_win004_identity(window, transcript)
    estimate = estimate_v140_request_tokens(transcript, window)
    local = int(estimate["total_tokens"])
    identical = bool(schema_identity.get("identical_to_a18"))
    ready = (
        identity["differs_from_a22_signature"]
        and identity["differs_from_a24_signature"]
        and identity["cache"] == "MISS"
        and local <= CANDIDATE_HARD_MAX_INPUT_TOKENS
        and local == int((estimates.get("windows") or {}).get("WIN004") or local)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "future_real_call_ready": ready,
        "future_real_call_authorized": FUTURE_REAL_CALL_AUTHORIZED,
        "win004_retry_authorized": WIN004_RETRY_AUTHORIZED,
        "future_win004_input_estimate": local,
        "within_35000": local <= CANDIDATE_HARD_MAX_INPUT_TOKENS,
        "future_win004_signature": identity["analysis_signature"],
        "future_forensic_identity": identity["forensic_identity"],
        "future_cache": identity["cache"],
        "schema_identical_to_a18": identical,
        "grammar_canary_required": not identical,
        "thinking": THINKING,
        "max_output": WINDOW_MAX_OUTPUT_TOKENS,
        "purpose": (
            "Does the simplified local-lite contract produce a technically "
            "valid and semantically acceptable WIN004 without local IDEA "
            "subtype classification?"
        ),
        "identity": identity,
        "estimate": estimate,
        "next_phase_if_pass_and_identical": NEXT_PHASE_LABEL,
        "do_not_execute": True,
    }


__all__ = ["build_future_win004_readiness", "future_v140_win004_identity"]
