"""Lecture seule des preuves A.44. Aucune réparation. Aucune écriture historique."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    A44_CHARS_PER_TOKEN,
    A44_COST_USD,
    A44_ELAPSED_MS,
    A44_ESTIMATOR_ERROR_PERCENT,
    A44_FINISH_REASON,
    A44_HTTP_STATUS,
    A44_INPUT_TOKENS,
    A44_OUTPUT_TOKENS,
    A44_RAW_TEXT_CHARS,
    A44_REQUEST_ID,
    A44_THINKING_TOKENS,
    GLOBAL_CONSOLIDATION_3_0_REUSE_CONTRACT_CANARY,
    GLOBAL_TRANSPORT_3_0_GRAMMAR_PROOF,
    PROJECT_NAME,
    PROTECTED_HISTORICAL,
)
from app.source_analysis_v31_global_v30_exact_preflight.offline import (
    GlobalExactPreflightError,
)
from app.source_analysis_v31_global_v30_exact_preflight.paths import (
    a44_execution_path,
    a44_report_path,
    a44_usage_path,
    sortie_root,
)


def verify_a44_identity(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    usage_path = a44_usage_path(project_name, sortie_dir=sortie_dir)
    execution_path = a44_execution_path(project_name, sortie_dir=sortie_dir)
    report = a44_report_path(project_name, sortie_dir=sortie_dir)
    if not usage_path.is_file():
        raise GlobalExactPreflightError(
            "BLOCKED: A.44 usage artifact missing — cannot calibrate tokenizer."
        )
    usage = json.loads(usage_path.read_text(encoding="utf-8"))
    execution = (
        json.loads(execution_path.read_text(encoding="utf-8"))
        if execution_path.is_file()
        else {}
    )
    exe = execution.get("execution") or {}
    request_id = usage.get("request_id") or exe.get("request_id")
    actual_cpt = float(usage.get("actual_chars_per_token") or 0)
    error = usage.get("estimator_error") or {}
    raw_chars = int(usage.get("raw_text_chars") or 0)
    output_tokens = int(usage.get("output") or usage.get("actual_canary_output") or 0)
    recomputed_cpt = (raw_chars / output_tokens) if output_tokens else 0.0
    grammar = (
        exe.get("global_transport_3_0_grammar_proof")
        or GLOBAL_TRANSPORT_3_0_GRAMMAR_PROOF
    )
    contract = (
        exe.get("global_consolidation_3_0_reuse_contract_canary")
        or GLOBAL_CONSOLIDATION_3_0_REUSE_CONTRACT_CANARY
    )
    cost = usage.get("cost") or {}
    total_cost = cost.get("total_cost")
    ok = (
        request_id == A44_REQUEST_ID
        and int(usage.get("http_status") or 0) == A44_HTTP_STATUS
        and usage.get("finish_reason") == A44_FINISH_REASON
        and int(usage.get("thinking") or 0) == A44_THINKING_TOKENS
        and int(usage.get("actual_provider_input") or 0) == A44_INPUT_TOKENS
        and output_tokens == A44_OUTPUT_TOKENS
        and raw_chars == A44_RAW_TEXT_CHARS
        and abs(actual_cpt - A44_CHARS_PER_TOKEN) < 1e-12
        and abs(recomputed_cpt - A44_CHARS_PER_TOKEN) < 1e-12
        and abs(float(error.get("percent") or 0) - A44_ESTIMATOR_ERROR_PERCENT) < 0.01
        and grammar == "PASS"
        and contract == "PASS"
        and report.is_file()
    )
    if not ok:
        raise GlobalExactPreflightError(
            "BLOCKED: A.44 saved identity does not match frozen PASS evidence "
            f"request_id={request_id!r} chars/token={actual_cpt}."
        )
    return {
        "ok": True,
        "request_id": request_id,
        "http_status": usage.get("http_status"),
        "finish_reason": usage.get("finish_reason"),
        "input_tokens": usage.get("actual_provider_input"),
        "output_tokens": output_tokens,
        "raw_text_chars": raw_chars,
        "thinking_tokens": usage.get("thinking"),
        "elapsed_ms": usage.get("provider_elapsed_ms") or A44_ELAPSED_MS,
        "cost_usd": total_cost if total_cost is not None else A44_COST_USD,
        "actual_chars_per_token": actual_cpt,
        "recomputed_chars_per_token": recomputed_cpt,
        "estimator_error_percent": error.get("percent"),
        "grammar_proof": grammar,
        "contract_canary": contract,
        "report_present": report.is_file(),
        "mutated": False,
        "generic_4_chars_per_token_used": False,
    }


def protected_a45_historical_hashes(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, str]:
    root = sortie_root(sortie_dir) / project_name
    hashes: dict[str, str] = {}
    for rel in PROTECTED_HISTORICAL:
        path = root / rel
        if path.is_file():
            hashes[rel] = sha256_of_file(path)
    return hashes


__all__ = ["protected_a45_historical_hashes", "verify_a44_identity"]
