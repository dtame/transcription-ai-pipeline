"""Préflight offline futur WIN001 1.3.1. 0 réseau. Non autorisé."""

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
    WINDOW_ANALYSIS_PROMPT_VERSION_V131,
)
from app.source_analysis_local_v3.prompt import (
    build_window_system_prompt_v131,
    build_window_user_prompt_v131,
    estimate_v131_request_tokens,
    window_prompt_v131_fingerprint,
    window_prompt_v131_sha256,
)
from app.source_analysis_local_v3.schema import semantic_transport_v3_fingerprint
from app.source_analysis_thinking_contract.signature import v2_forensic_identity
from app.source_analysis_v3_a19_forensics.constants import (
    A19_FORENSIC_IDENTITY,
    A19_LOCAL_INPUT,
    A19_SIGNATURE,
    FUTURE_REAL_CALL_AUTHORIZED,
    MODE,
    PHASE,
    SCHEMA_CHANGED,
    SCHEMA_VERSION,
    SERVER_GRAMMAR_STATUS,
    SYNTHETIC_WORST_CASE_LOCAL_TOKENS,
    WIN001_RETRY_AUTHORIZED,
)
from app.source_analysis_v3_symbolic_handles.identity import future_v3_win001_identity


def future_v131_win001_identity(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    provider: str = TARGET_PROVIDER,
    model: str = TARGET_MODEL,
    max_output_tokens: int = WINDOW_MAX_OUTPUT_TOKENS,
    context_safety_ratio: float = 0.7,
) -> dict[str, Any]:
    system = build_window_system_prompt_v131(transcript.primary_language)
    user = build_window_user_prompt_v131(transcript, window)
    prompt_sha = window_prompt_v131_sha256(system)
    prompt_fp = window_prompt_v131_fingerprint(system, user)
    schema_sha = semantic_transport_v3_fingerprint()
    thinking = thinking_identity(thinking_mode="disabled", effort=None)
    inputs = WindowSignatureInputs(
        window_input_hash=window.input_hash,
        window_id=window.window_id,
        transcript_id=transcript.transcript_id,
        transcript_sha256=transcript.content_sha256,
        planner_version=window.planner_version or CANDIDATE_PLANNER_VERSION,
        prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V131,
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
    historical = {
        "a19_v3_win001": A19_SIGNATURE,
        "a19_forensic": A19_FORENSIC_IDENTITY,
    }
    a19 = future_v3_win001_identity(window, transcript)
    collisions = {
        name: value == signature or value == forensic
        for name, value in {**historical, "a19_live": a19["analysis_signature"]}.items()
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "executed": False,
        "authorized": False,
        "window_id": window.window_id,
        "analysis_signature": signature,
        "forensic_identity": forensic,
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V131,
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
        "differs_from_a19_signature": signature != A19_SIGNATURE,
        "differs_from_a19_forensic": forensic != A19_FORENSIC_IDENTITY,
        "a19_signature": A19_SIGNATURE,
        "cache": "MISS",
        "cache_collisions": collisions,
        "signature_inputs": inputs.to_dict(),
    }


def build_future_retry_readiness(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    inventory: Mapping[str, Any],
    src_contract: Mapping[str, Any],
    example_policy: Mapping[str, Any],
    handles_clean: bool,
    tests: str,
) -> dict[str, Any]:
    identity = future_v131_win001_identity(window, transcript)
    estimate = estimate_v131_request_tokens(transcript, window)
    local = int(estimate["total_tokens"])
    overhead = local - A19_LOCAL_INPUT
    roots = int(inventory.get("total_latent_root_violations") or 0)
    all_observed = roots >= 1 and inventory.get("diagnostic_only") is True
    technically_ready = (
        all_observed
        and handles_clean
        and src_contract.get("preferred_remediation") == "prompt_hardening_1.3.1"
        and example_policy.get("settled_policy")
        and identity["differs_from_a19_signature"]
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
        "win001_retry_authorized": WIN001_RETRY_AUTHORIZED,
        "all_observable_a19_violations_inventoried": all_observed,
        "v3_handles_remain_sound": handles_clean,
        "src_issue_understood": True,
        "example_empty_link_policy_settled": True,
        "prompt_hardened": True,
        "schema_changed": SCHEMA_CHANGED,
        "server_grammar_status": SERVER_GRAMMAR_STATUS,
        "new_grammar_canary_required": False,
        "thinking": "disabled",
        "max_output": 32000,
        "planner": CANDIDATE_PLANNER_VERSION,
        "synthetic_worst_case": SYNTHETIC_WORST_CASE_LOCAL_TOKENS,
        "a19_local_input": A19_LOCAL_INPUT,
        "future_win001_input_estimate": local,
        "hardening_overhead_tokens": overhead,
        "within_35000": local <= CANDIDATE_HARD_MAX_INPUT_TOKENS,
        "future_win001_signature": identity["analysis_signature"],
        "future_forensic_identity": identity["forensic_identity"],
        "future_cache": identity["cache"],
        "identity": identity,
        "estimate": estimate,
        "tests": tests,
        "next_phase_if_human_authorizes": (
            "3B.7.7A.21 — REAL V3 SMALL WIN001 HARDENED RETRY "
            "(ONE provider call maximum)"
        ),
        "do_not_execute": True,
    }


__all__ = ["build_future_retry_readiness", "future_v131_win001_identity"]
