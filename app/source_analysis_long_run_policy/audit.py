"""
Construction déterministe de la politique 3B.5.2.

Aucun engine.generate(), aucun requests.post(), aucun appel réseau.
Pas d'horodatage, pas d'UUID.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Mapping

from app.file_utils import content_hash
from app.project_state import load_project_state
from app.source_analysis import state as state_module
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.writer import source_map_path
from app.source_analysis_long_run_policy.constants import (
    ATTEMPT_1_HTTP_TIMEOUT_FORM,
    ATTEMPT_1_READ_TIMEOUT_SECONDS,
    ATTEMPT_1_RESULT,
    BASELINE_FAILED,
    BASELINE_PASSED,
    FINAL_FAILED,
    FINAL_PASSED,
    CANDIDATE_READ_TIMEOUTS_SECONDS,
    DEFAULT_CONNECT_SECONDS,
    DEFAULT_READ_SECONDS,
    EXECUTION_AUTHORIZED,
    EXPECTED_DURATION_SECONDS,
    EXPECTED_INPUT_MODE,
    EXPECTED_INPUT_TOKENS,
    EXPECTED_MAX_OUTPUT_TOKENS,
    EXPECTED_MODEL,
    EXPECTED_PROMPT_VERSION,
    EXPECTED_PROVIDER,
    EXPECTED_REMAINING_MARGIN,
    EXPECTED_SEGMENTS,
    EXPECTED_STAGE,
    EXPECTED_STRATEGY,
    EXPECTED_TRANSCRIPT_ID,
    EXPECTED_USABLE_INPUT_BUDGET,
    EXPECTED_WORDS,
    FAILURE_POST_PROVIDER_LOCAL,
    FAILURE_PROVIDER_ERROR,
    FAILURE_SECOND_TIMEOUT,
    FAILURE_TRUNCATION,
    FALLBACK,
    GLOBAL_ATTEMPT_NUMBER,
    LINEAR_CANARY_EXTRAPOLATION_ALLOWED,
    MAX_ATTEMPTS,
    MAX_REAL_CALLS,
    MODE,
    NEXT_PHASE_IF_AUTHORIZABLE,
    NEXT_PHASE_IF_SECOND_TIMEOUT,
    OTHER_STAGES_AFFECTED,
    PHASE,
    PREVIOUS_CLASSIFICATION,
    PROVIDER_CALL_PERFORMED,
    PYTHON_CODE_CHANGE_REQUIRED,
    REQUIRES_HUMAN_REVIEW,
    RETRY,
    SCHEMA_VERSION,
    SECOND_GLOBAL_ATTEMPT_JUSTIFIED,
    SELECTED_OPERATIONAL_CONNECT_TIMEOUT_SECONDS,
    SELECTED_OPERATIONAL_READ_TIMEOUT_SECONDS,
    SELECTED_POLICY_STATUS,
    SOURCE_ANALYSIS_CONNECT_ENV,
    SOURCE_ANALYSIS_READ_ENV,
    THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED,
    TIMEOUT_IS_PROVIDER_GUARANTEE,
    TIMEOUT_POLICY_BASIS,
    TIMEOUT_POLICY_SELECTED,
)
from app.source_analysis_long_run_policy.policy import (
    canary_linear_output_forbidden,
    current_default_stage_timeouts,
    evaluate_candidates,
    global_versus_multi_window,
    illustrative_output_scenarios,
    input_side_cost_estimate,
    justify_selected_timeout,
    local_failure_requirements,
    other_stages_isolated,
    proposed_environ,
    read_timeout_semantics,
    risk_factors,
    selected_policy,
    simulate_source_analysis_timeouts,
    simulate_stage_timeouts,
    supporting_factors,
)
from app.source_analysis_timeout_config.audit import generation_c_hashes

_EMPTY_NETWORK = {
    "anthropic": 0,
    "openai": 0,
    "whisper": 0,
    "ollama": 0,
    "lm_studio": 0,
    "other": 0,
}

_PACKAGE_DIR = Path(__file__).resolve().parent


def package_calls_generate_or_post() -> list[str]:
    hits: list[str] = []
    for path in sorted(_PACKAGE_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
                if "requests" in names:
                    hits.append(f"{path.name}:import requests")
            if isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root == "requests":
                    hits.append(f"{path.name}:from requests")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"generate", "post"}:
                    hits.append(f"{path.name}:{node.func.attr}")
    return hits


def assert_offline_package() -> None:
    hits = package_calls_generate_or_post()
    if hits:
        raise RuntimeError("Chemin réseau/generate interdit : " + ", ".join(hits))


def assert_source_map_absent(
    project_name: str, *, sortie_dir: Path | None = None
) -> None:
    path = source_map_path(project_name, sortie_dir=sortie_dir)
    if path.exists():
        raise RuntimeError(f"source_map de production présent : {path}")


def inspect_project_state(project_name: str) -> dict[str, Any]:
    state = load_project_state(project_name)
    block = state_module.load_state_block(state) or {}
    return {
        "status": block.get("status"),
        "error": block.get("error"),
        "path": block.get("path"),
    }


def build_policy_audit() -> dict[str, Any]:
    assert_offline_package()
    policy = selected_policy()
    justification = justify_selected_timeout()
    simulated = simulate_stage_timeouts()
    source_resolved = simulate_source_analysis_timeouts()
    current = current_default_stage_timeouts()
    generation = generation_c_hashes()
    isolation = other_stages_isolated(simulated)
    if not isolation:
        raise RuntimeError("La politique Source Analysis fuit vers une autre étape.")
    if SOURCE_ANALYZER_PROMPT_VERSION != EXPECTED_PROMPT_VERSION:
        raise RuntimeError("Prompt 1.3 a dérivé.")
    if not generation["raw_matches_historical"] or not generation["anthropic_matches_historical"]:
        raise RuntimeError("Generation C a dérivé.")
    if policy.status == "AUTHORIZED_FOR_EXECUTION":
        raise RuntimeError("3B.5.2 ne peut pas atteindre AUTHORIZED_FOR_EXECUTION.")
    if policy.third_global_timeout_escalation_allowed:
        raise RuntimeError("L'escalade de timeout #3 est interdite.")
    if policy.retry or policy.fallback is not None:
        raise RuntimeError("retry/fallback interdits pour l'essai #2.")
    if policy.max_real_calls != 1 or policy.max_attempts != 1:
        raise RuntimeError("L'essai #2 doit rester one-call.")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "evidence": {
            "attempt_1_result": ATTEMPT_1_RESULT,
            "attempt_1_read_timeout_seconds": ATTEMPT_1_READ_TIMEOUT_SECONDS,
            "attempt_1_http_timeout_form": ATTEMPT_1_HTTP_TIMEOUT_FORM,
            "root_cause": PREVIOUS_CLASSIFICATION,
            "canary_pipeline": "PASS",
            "generation_c_server_acceptance": "VERIFIED",
            "prompt_1_3_vocabulary_compliance": "VERIFIED",
            "connect_read_separated": True,
            "stage_specific_override_supported": True,
            "linear_canary_extrapolation_allowed": LINEAR_CANARY_EXTRAPOLATION_ALLOWED,
        },
        "input": {
            "transcript_id": EXPECTED_TRANSCRIPT_ID,
            "mode": EXPECTED_INPUT_MODE,
            "segments": EXPECTED_SEGMENTS,
            "words": EXPECTED_WORDS,
            "duration_seconds": EXPECTED_DURATION_SECONDS,
        },
        "context": {
            "strategy": EXPECTED_STRATEGY,
            "estimated_input_tokens": EXPECTED_INPUT_TOKENS,
            "usable_input_budget": EXPECTED_USABLE_INPUT_BUDGET,
            "remaining_margin": EXPECTED_REMAINING_MARGIN,
            "max_output_tokens": EXPECTED_MAX_OUTPUT_TOKENS,
            "corpus_fits_context_budget": True,
        },
        "supporting_factors": supporting_factors(),
        "risk_factors": risk_factors(),
        "global_versus_multi_window": global_versus_multi_window(),
        "candidate_read_timeouts_seconds": list(CANDIDATE_READ_TIMEOUTS_SECONDS),
        "candidate_evaluation": evaluate_candidates(),
        "selected_timeout_justification": justification,
        "selected_policy": {
            "status": policy.status,
            "attempt_number": policy.attempt_number,
            "connect_timeout_seconds": policy.connect_timeout_seconds,
            "read_timeout_seconds": policy.read_timeout_seconds,
            "timeout_policy_basis": policy.timeout_policy_basis,
            "timeout_is_provider_guarantee": policy.timeout_is_provider_guarantee,
            "timeout_policy_selected": TIMEOUT_POLICY_SELECTED,
            "max_real_calls": policy.max_real_calls,
            "max_attempts": policy.max_attempts,
            "retry": policy.retry,
            "fallback": policy.fallback,
            "third_global_timeout_escalation_allowed": (
                policy.third_global_timeout_escalation_allowed
            ),
            "second_global_attempt_justified": SECOND_GLOBAL_ATTEMPT_JUSTIFIED,
        },
        "configuration": {
            "source_analysis_connect_env": SOURCE_ANALYSIS_CONNECT_ENV,
            "source_analysis_read_env": SOURCE_ANALYSIS_READ_ENV,
            "proposed_env": proposed_environ(),
            "python_code_change_required": PYTHON_CODE_CHANGE_REQUIRED,
            "other_stages_affected": OTHER_STAGES_AFFECTED,
            "real_env_modified": False,
        },
        "timeouts": {
            "current_defaults": {
                "connect_seconds": DEFAULT_CONNECT_SECONDS,
                "read_seconds": DEFAULT_READ_SECONDS,
                "stages": current,
            },
            "simulated_policy": {
                "source_analysis": source_resolved,
                "stages": simulated,
                "other_stages_isolated": isolation,
            },
            "read_semantics": read_timeout_semantics(),
        },
        "failure_policy": {
            "second_timeout": FAILURE_SECOND_TIMEOUT,
            "provider_error": FAILURE_PROVIDER_ERROR,
            "post_provider_local_failure": FAILURE_POST_PROVIDER_LOCAL,
            "truncation": FAILURE_TRUNCATION,
            "local_failure_requirements": local_failure_requirements(),
            "next_phase_if_second_timeout": NEXT_PHASE_IF_SECOND_TIMEOUT,
        },
        "success_policy": {
            "requires_full_canonical_pipeline": True,
            "requires_atomic_source_map_publication": True,
            "project_state_success_before_publication": False,
            "gates": [
                "provider response complete",
                "finish reason acceptable",
                "transport preserved",
                "semantic-transport parse PASS",
                "canonical vocabulary PASS",
                "source refs PASS",
                "links PASS",
                "fail-closed decoder PASS",
                "canonical reconstruction PASS",
                "normalization PASS",
                "canonical validator PASS",
                "editorial leakage PASS",
                "determinism PASS",
                "atomic source_map publication PASS",
                "project_state SUCCESS only after publication",
            ],
        },
        "cost": {
            "known_input_estimate": input_side_cost_estimate(),
            "illustrative_output_scenarios": illustrative_output_scenarios(),
            "canary_linear_output": canary_linear_output_forbidden(),
            "provider_actual_usage": "unavailable_until_run",
            "unknown_must_not_become_zero": True,
        },
        "integrity": {
            "prompt_version": SOURCE_ANALYZER_PROMPT_VERSION,
            "prompt_unchanged": SOURCE_ANALYZER_PROMPT_VERSION == EXPECTED_PROMPT_VERSION,
            "generation_c": generation,
            "decoder_semantic_changes": False,
            "canonical_validator_changes": False,
            "expected_provider": EXPECTED_PROVIDER,
            "expected_model": EXPECTED_MODEL,
            "expected_stage": EXPECTED_STAGE,
            "global_attempt_number": GLOBAL_ATTEMPT_NUMBER,
        },
        "execution": {
            "provider_call_performed": PROVIDER_CALL_PERFORMED,
            "execution_authorized": EXECUTION_AUTHORIZED,
            "requires_human_review": REQUIRES_HUMAN_REVIEW,
            "attempt_2_executed": False,
            "next_phase_if_technically_authorizable": NEXT_PHASE_IF_AUTHORIZABLE,
            "max_real_calls": MAX_REAL_CALLS,
            "max_attempts": MAX_ATTEMPTS,
            "retry": RETRY,
            "fallback": FALLBACK,
            "third_global_timeout_escalation_allowed": (
                THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED
            ),
        },
        "tests": {
            "baseline_passed": BASELINE_PASSED,
            "baseline_failed": BASELINE_FAILED,
            "final_passed": FINAL_PASSED,
            "final_failed": FINAL_FAILED,
        },
        "network": dict(_EMPTY_NETWORK),
        "engine_generate": 0,
    }
    return payload


def policy_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"
    return content_hash(encoded)


def build_deterministic_policy() -> tuple[dict[str, Any], str, str]:
    first = build_policy_audit()
    second = build_policy_audit()
    sha1 = policy_sha256(first)
    sha2 = policy_sha256(second)
    if sha1 != sha2:
        raise RuntimeError("Politique 3B.5.2 non déterministe : SHA run1 ≠ run2.")
    return first, sha1, sha2
