"""Identité future WIN001 — calculée, non exécutée."""

from __future__ import annotations

from typing import Any

from app.ai.thinking import thinking_fingerprint, thinking_identity
from app.source_analysis.window_models import (
    TARGET_MODEL,
    TARGET_PROVIDER,
    WINDOW_MAX_OUTPUT_TOKENS,
)
from app.source_analysis.window_signature import (
    WindowSignatureInputs,
    build_window_analysis_signature,
)
from app.source_analysis_local_v2.constants import SEMANTIC_TRANSPORT_VERSION_V2
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_local_v2.prompt import (
    build_window_system_prompt_v121,
    build_window_user_prompt_v121,
    window_prompt_v121_fingerprint,
    window_prompt_v121_sha256,
)
from app.source_analysis_local_v2.schema import semantic_transport_v2_fingerprint
from app.source_analysis_thinking_contract.signature import v2_forensic_identity
from app.source_analysis_v2_link_semantics.constants import (
    A13_REQUEST_IDENTITY,
    CALL1_SIGNATURE,
    CALL2_SIGNATURE,
    CANDIDATE_PLANNER_VERSION,
    CANDIDATE_WINDOW_ANALYSIS_PROMPT_VERSION,
    MODE,
    PHASE,
    SCHEMA_VERSION,
    SMALL_SIGNATURE,
    THINKING_MODE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V121,
)


def future_win001_identity(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    provider: str = TARGET_PROVIDER,
    model: str = TARGET_MODEL,
    max_output_tokens: int = WINDOW_MAX_OUTPUT_TOKENS,
    context_safety_ratio: float = 0.7,
) -> dict[str, Any]:
    system = build_window_system_prompt_v121(transcript.primary_language)
    user = build_window_user_prompt_v121(transcript, window)
    prompt_sha = window_prompt_v121_sha256(system)
    prompt_fp = window_prompt_v121_fingerprint(system, user)
    schema_sha = semantic_transport_v2_fingerprint()
    thinking = thinking_identity(thinking_mode=THINKING_MODE, effort=None)
    inputs = WindowSignatureInputs(
        window_input_hash=window.input_hash,
        window_id=window.window_id,
        transcript_id=transcript.transcript_id,
        transcript_sha256=transcript.content_sha256,
        planner_version=window.planner_version or CANDIDATE_PLANNER_VERSION,
        prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V121,
        prompt_sha256=prompt_fp,
        transport_version=SEMANTIC_TRANSPORT_VERSION_V2,
        response_schema_sha256=schema_sha,
        provider=provider,
        model=model,
        temperature=None,
        max_output_tokens=max_output_tokens,
        output_language=transcript.primary_language,
        context_safety_ratio=float(context_safety_ratio),
        thinking_mode=THINKING_MODE,
        effort=None,
    )
    signature = build_window_analysis_signature(inputs)
    forensic = v2_forensic_identity(
        window_id=window.window_id,
        content_sha256=transcript.content_sha256,
        thinking_mode=THINKING_MODE,
        effort=None,
        prompt_sha256=prompt_fp,
        schema_sha256=schema_sha,
    )
    historical = {
        "large_1_0_or_call1": CALL1_SIGNATURE,
        "large_1_1_or_call2": CALL2_SIGNATURE,
        "small_1_1": SMALL_SIGNATURE,
        "a13_synthetic_canary": A13_REQUEST_IDENTITY,
    }
    collisions = {
        name: value == signature or value == forensic
        for name, value in historical.items()
    }
    cache_miss = signature not in historical.values()
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "executed": False,
        "authorized": False,
        "window_id": window.window_id,
        "window_input_hash": window.input_hash,
        "analysis_signature": signature,
        "prompt_version": CANDIDATE_WINDOW_ANALYSIS_PROMPT_VERSION,
        "prompt_sha256": prompt_sha,
        "prompt_fingerprint": prompt_fp,
        "thinking_contract": "THINKING_DISABLED",
        "thinking_identity": thinking,
        "thinking_fingerprint": thinking_fingerprint(THINKING_MODE, None),
        "planner_version": window.planner_version or CANDIDATE_PLANNER_VERSION,
        "transport": SEMANTIC_TRANSPORT_VERSION_V2,
        "schema_sha256": schema_sha,
        "provider": provider,
        "model": model,
        "max_output_tokens": max_output_tokens,
        "forensic_identity": forensic,
        "historical": historical,
        "cache": "MISS" if cache_miss else "HIT",
        "cache_collisions": collisions,
        "forensic_collides": any(collisions.values()),
        "signature_inputs": inputs.to_dict(),
    }


__all__ = ["future_win001_identity"]
