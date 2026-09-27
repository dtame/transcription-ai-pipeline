"""Préflight offline futur WIN004 1.3.2. 0 réseau. Non autorisé."""

from __future__ import annotations

from typing import Any, Mapping

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
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v3.constants import (
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    CANDIDATE_PLANNER_VERSION,
    SEMANTIC_TRANSPORT_VERSION_V3,
    WINDOW_ANALYSIS_PROMPT_VERSION_V132,
)
from app.source_analysis_local_v3.prompt import (
    build_window_system_prompt_v132,
    build_window_user_prompt_v132,
    estimate_v131_request_tokens,
    estimate_v132_request_tokens,
    window_prompt_v132_fingerprint,
    window_prompt_v132_sha256,
)
from app.source_analysis_local_v3.schema import semantic_transport_v3_fingerprint
from app.source_analysis_thinking_contract.signature import v2_forensic_identity
from app.source_analysis_v3_a22_forensics.constants import (
    A22_FORENSIC_IDENTITY,
    A22_LOCAL_INPUT,
    A22_SIGNATURE,
    FUTURE_REAL_CALL_AUTHORIZED,
    MODE,
    NEXT_PHASE_LABEL,
    PHASE,
    SCHEMA_CHANGED,
    SCHEMA_VERSION,
    SERVER_GRAMMAR_STATUS,
    WIN004_RETRY_AUTHORIZED,
)


def future_v132_win004_identity(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    provider: str = TARGET_PROVIDER,
    model: str = TARGET_MODEL,
    max_output_tokens: int = WINDOW_MAX_OUTPUT_TOKENS,
    context_safety_ratio: float = 0.7,
) -> dict[str, Any]:
    system = build_window_system_prompt_v132(transcript.primary_language)
    user = build_window_user_prompt_v132(transcript, window)
    prompt_sha = window_prompt_v132_sha256(system)
    prompt_fp = window_prompt_v132_fingerprint(system, user)
    schema_sha = semantic_transport_v3_fingerprint()
    thinking = thinking_identity(thinking_mode="disabled", effort=None)
    inputs = WindowSignatureInputs(
        window_input_hash=window.input_hash,
        window_id=window.window_id,
        transcript_id=transcript.transcript_id,
        transcript_sha256=transcript.content_sha256,
        planner_version=window.planner_version or CANDIDATE_PLANNER_VERSION,
        prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V132,
        prompt_sha256=prompt_fp,
        transport_version=SEMANTIC_TRANSPORT_VERSION_V3,
        response_schema_sha256=schema_sha,
        provider=provider,
        model=model,
        temperature=None,
        max_output_tokens=max_output_tokens,
        output_language=transcript.primary_language,
        context_safety_ratio=float(context_safety_ratio),
        thinking_mode="disabled",
        effort=None,
    )
    signature = build_window_analysis_signature(inputs)
    forensic = v2_forensic_identity(
        window_id=window.window_id,
        content_sha256=transcript.content_sha256,
        thinking_mode="disabled",
        effort=None,
        prompt_sha256=prompt_fp,
        schema_sha256=schema_sha,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "executed": False,
        "authorized": False,
        "window_id": window.window_id,
        "analysis_signature": signature,
        "forensic_identity": forensic,
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V132,
        "prompt_sha256": prompt_sha,
        "prompt_fingerprint": prompt_fp,
        "schema_sha256": schema_sha,
        "thinking_mode": "disabled",
        "effort": None,
        "thinking_identity": thinking,
        "thinking_fingerprint": thinking_fingerprint("disabled", None),
        "planner_version": window.planner_version or CANDIDATE_PLANNER_VERSION,
        "transport": SEMANTIC_TRANSPORT_VERSION_V3,
        "max_output_tokens": max_output_tokens,
        "differs_from_a22_signature": signature != A22_SIGNATURE,
        "differs_from_a22_forensic": forensic != A22_FORENSIC_IDENTITY,
        "a22_signature": A22_SIGNATURE,
        "cache": "MISS",
        "signature_inputs": inputs.to_dict(),
    }


def build_future_retry_readiness(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    inventory: Mapping[str, Any],
    contract: Mapping[str, Any],
    semantic: Mapping[str, Any],
    handles_clean: bool,
    tests: str,
) -> dict[str, Any]:
    identity = future_v132_win004_identity(window, transcript)
    estimate = estimate_v132_request_tokens(transcript, window)
    estimate_131 = estimate_v131_request_tokens(transcript, window)
    local = int(estimate["total_tokens"])
    overhead = local - int(estimate_131["total_tokens"])
    roots = int(inventory.get("total_latent_root_violations") or 0)
    all_observed = roots == 4 and inventory.get("diagnostic_only") is True
    technically_ready = (
        all_observed
        and handles_clean
        and contract.get("prompt_hardening_justified") is True
        and semantic.get("semantic_counterfactual")
        == "SEMANTICALLY_ACCEPTABLE_BUT_FOR_TRANSPORT_METADATA"
        and identity["differs_from_a22_signature"]
        and identity["cache"] == "MISS"
        and local <= CANDIDATE_HARD_MAX_INPUT_TOKENS
        and SCHEMA_CHANGED is False
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "future_real_call_ready": technically_ready,
        "future_real_call_authorized": FUTURE_REAL_CALL_AUTHORIZED,
        "win004_retry_authorized": WIN004_RETRY_AUTHORIZED,
        "all_observable_a22_violations_inventoried": all_observed,
        "v3_handles_remain_sound": handles_clean,
        "type_contract_understood": True,
        "prompt_hardened": True,
        "schema_changed": SCHEMA_CHANGED,
        "server_grammar_status": SERVER_GRAMMAR_STATUS,
        "new_grammar_canary_required": False,
        "thinking": "disabled",
        "max_output": 32000,
        "planner": CANDIDATE_PLANNER_VERSION,
        "a22_local_input": A22_LOCAL_INPUT,
        "future_win004_input_estimate": local,
        "hardening_overhead_tokens": overhead,
        "within_35000": local <= CANDIDATE_HARD_MAX_INPUT_TOKENS,
        "future_win004_signature": identity["analysis_signature"],
        "future_forensic_identity": identity["forensic_identity"],
        "future_cache": identity["cache"],
        "identity": identity,
        "estimate": estimate,
        "tests": tests,
        "next_phase_if_human_authorizes": NEXT_PHASE_LABEL,
        "do_not_execute": True,
        "do_not_spend_on_remaining_windows": True,
    }


__all__ = ["build_future_retry_readiness", "future_v132_win004_identity"]
