"""Assemble les trois artefacts de diagnostic 3B.7.7A.1. 0 appel provider."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

from app.ai.errors import AIStructuredOutputError
from app.ai.providers.anthropic_engine import AnthropicEngine, _extract_text
from app.ai.providers.base import BaseAIEngine
from app.ai.structured import parse_json_payload, parse_structured_output, validate_payload
from app.ai.structured_forensics import (
    FORENSICS_DIR_NAME,
    FORENSICS_JSON_NAME,
    FORENSICS_RAW_NAME,
)
from app.cleanup_application.writer import clean_json_path
from app.file_utils import content_hash
from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis.window_cache import inspect_window_cache
from app.source_analysis.window_writer import (
    leftover_partial,
    metadata_path,
    result_path,
    transport_path,
    windows_root,
)
from app.source_analysis_execution_strategy.review import inspect_project_state
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_win001_failure_diagnosis.accounting import diagnose_request
from app.source_analysis_win001_failure_diagnosis.constants import (
    EXPECTED_MODEL,
    EXPECTED_PROVIDER,
    FAILURE_DIAGNOSIS_ARTIFACT,
    HISTORICAL_3B_GLOBAL_MALFORMED,
    MODE,
    NEXT_ACTION,
    NEXT_PHASE,
    NEXT_PHASE_LABEL,
    OBSERVED_COST_USD,
    OBSERVED_ERROR_TYPE,
    OBSERVED_LOCAL_ESTIMATE,
    OBSERVED_MAX_OUTPUT,
    OBSERVED_PROVIDER_INPUT,
    OBSERVED_PROVIDER_OUTPUT,
    OBSERVABILITY_ARTIFACT,
    PHASE,
    PRIMARY_CLASSIFICATION,
    PROJECT_NAME,
    PROTECTED_EVIDENCE,
    PROXIMATE_FAILURE,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REPORT_NAME,
    SCHEMA_VERSION,
    TOKEN_ACCOUNTING_ARTIFACT,
    WINDOW_ID,
    WIN001_RETRIED,
)
from app.source_analysis_win001_failure_diagnosis.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _file_sha(path: Path) -> str | None:
    return sha256_of_file(path) if path.is_file() else None


# Lignes publiées en 3B.7.7A.1. Les phases suivantes ne doivent pas
# réécrire cet artefact historique parce que le code a bougé.
_PUBLISHED_3B77A1_LINES = {
    "http_payload_builder": 121,
    "text_extraction": 203,
    "structured_parse": 208,
    "parse_json_payload": 76,
    "validate_payload": 175,
    "engine_attach": 164,
}


def _lineno(func) -> int | None:
    published = {
        "build_payload": _PUBLISHED_3B77A1_LINES["http_payload_builder"],
        "_extract_text": _PUBLISHED_3B77A1_LINES["text_extraction"],
        "parse_structured_output": _PUBLISHED_3B77A1_LINES["structured_parse"],
        "parse_json_payload": _PUBLISHED_3B77A1_LINES["parse_json_payload"],
        "validate_payload": _PUBLISHED_3B77A1_LINES["validate_payload"],
        "generate": _PUBLISHED_3B77A1_LINES["engine_attach"],
    }
    name = getattr(func, "__name__", "")
    if name in published:
        return published[name]
    try:
        return int(inspect.getsourcelines(func)[1])
    except (OSError, TypeError):
        return None


def historical_usage(audit: Path) -> dict[str, Any]:
    ultra = _load_json(audit / "source_analysis_ultra_compact_canary_result.json") or {}
    vocab = _load_json(audit / "source_analysis_vocabulary_compliance_canary_result.json") or {}
    usage_u = ultra.get("usage") or ultra
    usage_v = vocab.get("usage") or vocab
    return {
        "3b43_grammar_canary": {
            "label": "3B.4.3 grammar canary",
            "input_tokens": usage_u.get("input_tokens"),
            "output_tokens": usage_u.get("output_tokens"),
            "source": "audit/source_analysis_ultra_compact_canary_result.json",
            "persisted_audit_usage": True,
        },
        "3b45_vocabulary_canary": {
            "label": "3B.4.5 vocabulary canary",
            "input_tokens": usage_v.get("input_tokens"),
            "output_tokens": usage_v.get("output_tokens"),
            "source": "audit/source_analysis_vocabulary_compliance_canary_result.json",
            "persisted_audit_usage": True,
        },
        "3b_global_malformed_json": HISTORICAL_3B_GLOBAL_MALFORMED,
        "win001": {
            "label": "WIN001 real canary",
            "local_estimate": OBSERVED_LOCAL_ESTIMATE,
            "input_tokens": OBSERVED_PROVIDER_INPUT,
            "output_tokens": OBSERVED_PROVIDER_OUTPUT,
            "source": "audit/source_analysis_real_win001_canary_execution.json",
            "persisted_audit_usage": True,
        },
    }


def code_path_facts() -> dict[str, Any]:
    return {
        "ai_request_builder": {
            "function": "build_window_ai_request",
            "module": "app.source_analysis.window_analyzer",
        },
        "http_payload_builder": {
            "function": "AnthropicEngine.build_payload",
            "module": "app.ai.providers.anthropic_engine",
            "line": _lineno(AnthropicEngine.build_payload),
        },
        "http_post": {
            "function": "post_json / requests.post",
            "module": "app.ai.providers._http",
            "this_phase_invoked": False,
        },
        "text_extraction": {
            "function": "_extract_text",
            "module": "app.ai.providers.anthropic_engine",
            "line": _lineno(_extract_text),
            "raises_if_no_text_block": "AIResponseError",
            "observed_error_was_not_this": True,
        },
        "structured_parse": {
            "function": "parse_structured_output",
            "module": "app.ai.structured",
            "line": _lineno(parse_structured_output),
            "callees": {
                "parse_json_payload": _lineno(parse_json_payload),
                "validate_payload": _lineno(validate_payload),
            },
            "raises": "AIStructuredOutputError",
        },
        "engine_attach": {
            "function": "BaseAIEngine.generate",
            "module": "app.ai.providers.base",
            "line": _lineno(BaseAIEngine.generate),
            "attaches_response_before_reraise": True,
        },
        "window_boundary": {
            "function": "analyze_window",
            "module": "app.source_analysis.window_analyzer",
            "transport_requires": "AIResponse.parsed mapping",
            "on_structured_error_before_hardening": "re-raise, discard in-memory response",
            "on_structured_error_after_hardening": (
                "persist structured_output_forensics, then re-raise; "
                "no transport.json, no result.json"
            ),
        },
        "proximate_raiser": {
            "type": "AIStructuredOutputError",
            "confirmed": inspect.isclass(AIStructuredOutputError),
        },
    }


def observability_review(*, hardening_implemented: bool) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "provider_metadata_exists_in_response_body": {
            "usage.input_tokens": "YES — extracted to ProviderResult / AIResponse",
            "usage.output_tokens": "YES — extracted",
            "stop_reason": "YES — mapped to AIResponse.finish_reason",
            "id": "YES — mapped to AIResponse.request_id",
            "content_blocks": "YES — used by _extract_text then discarded as structure",
            "raw_text": "YES — AIResponse.text after extraction",
            "http_status": "DISCARDED by post_json after success",
            "request_id_header": "NOT READ by current engine",
        },
        "failed_win001_call": {
            "http_response_object": "AVAILABLE IN MEMORY then DISCARDED",
            "response_json": "AVAILABLE IN MEMORY then DISCARDED",
            "content_blocks": "AVAILABLE IN MEMORY then DISCARDED",
            "raw_text": "AVAILABLE IN MEMORY (AIResponse.text / exc.response.text) then DISCARDED",
            "usage": "PERSISTED in log + 3B.7.7A execution artifact",
            "stop_reason": "AVAILABLE IN MEMORY (finish_reason) then DISCARDED — not logged on failure before 3B.7.7A.1",
            "request_id": "AVAILABLE IN MEMORY then DISCARDED — not logged on failure before 3B.7.7A.1",
            "actual_failed_call_stop_reason_value": "UNKNOWN",
            "actual_failed_call_request_id_value": "UNKNOWN",
            "raw_content_persisted": False,
        },
        "before_hardening": {
            "ai_call_failed_logged": ["usage", "error_type", "latency"],
            "ai_call_failed_not_logged": [
                "finish_reason",
                "request_id",
                "raw_text_sha256",
                "parse_failure_kind",
            ],
            "forensic_artifact": False,
            "exc.response_attached": True,
            "analyze_window_persists_on_error": False,
        },
        "recommended_hardening": [
            "persist stop_reason / request_id / usage on AIStructuredOutputError",
            "classify parse_failure_kind (empty / json_decode / schema)",
            "persist raw text hash/size",
            "persist raw failed content under analysis/structured_output_forensics",
            "log finish_reason and request_id on structured failure",
        ],
        "implemented_hardening": {
            "implemented": hardening_implemented,
            "semantic_behavior_changed": False,
            "prompt_changed": False,
            "generation_c_changed": False,
            "planner_changed": False,
            "max_output_changed": False,
            "window_size_changed": False,
            "attaches_diagnostics_on_AIStructuredOutputError": True,
            "logs_finish_reason_and_request_id_on_failure": True,
            "persists_forensics_on_window_structured_failure": True,
            "forensics_location": f"analysis/{FORENSICS_DIR_NAME}/<window_id>/{FORENSICS_JSON_NAME}",
            "raw_content_location": f"analysis/{FORENSICS_DIR_NAME}/<window_id>/{FORENSICS_RAW_NAME}",
            "does_not_write_transport_or_result": True,
            "does_not_repair_json": True,
            "this_failed_call_cannot_be_retroactively_recovered": True,
        },
        "transport_first_boundary": {
            "begins_after": "AIResponse.parsed exists as a mapping",
            "why_transport_absent": (
                "parse_structured_output raised before parsed was attached; "
                "write_window_transport was not reached"
            ),
            "pre_parse_preservation_should_exist": True,
            "implemented_for_future_failures": hardening_implemented,
        },
        "secrets_included": False,
    }


def build_diagnosis(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    accounting = diagnose_request(transcript, window_id=WINDOW_ID)
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    execution = _load_json(audit / "source_analysis_real_win001_canary_execution.json") or {}
    clean_path = clean_json_path(project_name, sortie_dir=sortie_dir)
    root = windows_root(project_name, sortie_dir=sortie_dir)
    from app.source_analysis.window_analyzer import build_window_ai_request
    from app.source_analysis_hybrid.planner import plan_windows_v2

    plan = plan_windows_v2(transcript)
    window = next(w for w in plan.windows if w.window_id == WINDOW_ID)
    from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION_V10

    bundle = build_window_ai_request(
        window, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V10
    )
    cache = inspect_window_cache(
        window,
        transcript,
        windows_root=root,
        project_name=project_name,
        expected_signature=bundle.signature,
    )
    state = inspect_project_state(project_name, sortie_dir=sortie_dir)
    protected = []
    for rel in PROTECTED_EVIDENCE:
        path = audit / Path(rel).name
        protected.append(
            {
                "path": rel,
                "present": path.is_file(),
                "sha256": _file_sha(path),
            }
        )
    production = {
        "transport_exists": transport_path(
            project_name, WINDOW_ID, root=root
        ).is_file(),
        "result_exists": result_path(project_name, WINDOW_ID, root=root).is_file(),
        "metadata_exists": metadata_path(project_name, WINDOW_ID, root=root).is_file(),
        "leftover_partial": leftover_partial(
            transport_path(project_name, WINDOW_ID, root=root)
        )
        is not None,
        "source_map_exists": source_map_path(
            project_name, sortie_dir=sortie_dir
        ).exists(),
        "analysis_dir_windows_existed": root.exists(),
    }
    failure = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "result": "PASS",
        "real_provider_calls_this_phase": REAL_PROVIDER_CALLS_THIS_PHASE,
        "win001_retried": WIN001_RETRIED,
        "proximate_failure": PROXIMATE_FAILURE,
        "output_tokens": f"{OBSERVED_PROVIDER_OUTPUT} / {OBSERVED_MAX_OUTPUT}",
        "output_limit_reached": "OBSERVED",
        "stop_reason": "UNKNOWN",
        "local_input_estimate": OBSERVED_LOCAL_ESTIMATE,
        "provider_input_tokens": OBSERVED_PROVIDER_INPUT,
        "input_ratio": accounting["provider_actual"]["ratio"],
        "payload_duplication": (
            "NO"
            if accounting["duplication"].get("src_user_counts_all_one")
            and not accounting["duplication"]["unexpected_duplication"]
            else "YES"
        ),
        "raw_provider_content_at_failure": "AVAILABLE_IN_MEMORY_THEN_DISCARDED",
        "raw_content_persisted": False,
        "transport": "ABSENT",
        "win001_cache": cache.cache_state,
        "root_cause_confidence": "HIGH_PROXIMATE / MEDIUM_UPSTREAM / HIGH_INDEPENDENT_ESTIMATOR",
        "semantic_contract_changed": False,
        "next_action": NEXT_ACTION,
        "next_phase": NEXT_PHASE,
        "next_phase_label": NEXT_PHASE_LABEL,
        "primary_classification": PRIMARY_CLASSIFICATION,
        "error_type": OBSERVED_ERROR_TYPE,
        "anthropic_http_outcome": {
            "timeout": False,
            "usage_received": True,
            "body_received": True,
            "http_status_persisted": False,
            "classification": (
                "successful provider HTTP body followed by local structured-output failure"
            ),
            "evidence": "3B.7.7A execution artifact + ai_call_failed usage",
        },
        "exact_exception_trigger": {
            "raiser": "app.ai.structured.parse_structured_output",
            "type": OBSERVED_ERROR_TYPE,
            "sub_condition": "NOT_DETERMINABLE",
            "sub_condition_candidates": ["json_decode", "schema"],
            "empty_content_likely": False,
            "empty_reason": "output_tokens=32000 makes an empty extracted text unlikely",
            "missing_text_block": False,
            "missing_text_block_reason": (
                "that path raises AIResponseError, not AIStructuredOutputError"
            ),
            "truncation_proves_parse_failure": False,
            "truncation_support": "STRONGLY_SUPPORTED",
        },
        "code_path": code_path_facts(),
        "evidence_execution": {
            "error_type": (execution.get("provider_outcome") or {}).get("error_type"),
            "parsed_available": (execution.get("provider_outcome") or {}).get(
                "parsed_available"
            ),
            "usage": execution.get("usage"),
            "stop_reason": execution.get("stop_reason"),
            "request_id": execution.get("request_id"),
        },
        "cache_after": {
            "WIN001": cache.cache_state,
            "transport_present": cache.transport_present,
            "result_present": cache.result_present,
        },
        "production_artifacts": production,
        "project_state": state,
        "clean_transcript": {
            "sha256_file": _file_sha(clean_path),
            "content_sha256": transcript.content_sha256,
            "segment_count": transcript.segment_count,
            "word_count": transcript.word_count,
        },
        "protected_evidence": protected,
        "historical_usage": historical_usage(audit),
        "win002_calls": 0,
        "win003_calls": 0,
        "consolidation_calls": 0,
        "source_map_published": False,
        "phase_3b": "INCOMPLETE",
        "contracts_unchanged": {
            "window-analysis-1.0": True,
            "semantic-transport-v1": True,
            "Generation_C": True,
            "WindowPlannerV2": True,
            "window_max_output": True,
            "window_timeout": True,
            "canonical_vocabularies": True,
        },
        "secrets_included": False,
        "transcript_text_included": False,
    }
    token = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "local_estimate": accounting["local_estimate"],
        "provider_actual": accounting["provider_actual"],
        "ratio": accounting["provider_actual"]["ratio"],
        "ratio_exact": accounting["provider_actual"]["ratio_exact"],
        "request_text_chars": accounting["character_counts"],
        "payload_bytes": {
            "serialized_compact_bytes": accounting["payload"]["serialized_compact_bytes"],
            "serialized_pretty_bytes": accounting["payload"]["serialized_pretty_bytes"],
            "system_bytes": accounting["payload"]["system_bytes"],
            "messages_bytes": accounting["payload"]["messages_bytes"],
            "user_content_bytes": accounting["payload"]["user_content_bytes"],
            "schema_bytes_in_payload": accounting["payload"]["schema_bytes_in_payload"],
        },
        "schema_bytes": accounting["schema_sizes"],
        "duplication_checks": accounting["duplication"],
        "estimator_semantics": accounting["local_estimate"],
        "provider_accounting": {
            "known": (
                "usage.input_tokens and usage.output_tokens are integers "
                "returned in the Anthropic JSON body and copied by AnthropicEngine._invoke"
            ),
            "unknown": (
                "whether Anthropic counts compiled structured-output grammar, "
                "JSON escaping, system/message wrappers, or hidden request-side "
                "tokens inside input_tokens. Not established by local evidence."
            ),
        },
        "context_margin": accounting["context"],
        "long_context": accounting["long_context"],
        "cost_arithmetic": accounting["cost"],
        "reconstructed_request": {
            "system_chars": accounting["character_counts"]["system_chars"],
            "user_chars": accounting["character_counts"]["user_chars"],
            "combined_chars": accounting["character_counts"]["combined_chars"],
            "estimated_tokens": accounting["local_estimate"]["system_plus_user_tokens"],
            "message_count": accounting["payload"]["message_count"],
            "system_block_count": accounting["payload"]["system_block_count"],
            "user_content_block_count": accounting["payload"]["user_content_block_count"],
            "max_output": accounting["max_output_tokens"],
            "model": accounting["model"],
            "temperature": accounting["temperature"],
            "structured_output": accounting["structured_output"],
            "prompt_sha256": accounting["prompt_sha256"],
            "response_schema_sha256": accounting["response_schema_sha256"],
            "analysis_signature": accounting["analysis_signature"],
        },
        "payload_keys": accounting["payload"]["payload_keys"],
        "payload_estimate_diagnostic_only": accounting["payload_estimate_diagnostic_only"],
        "record_bounds": accounting["record_bounds"],
        "historical_usage": historical_usage(audit),
        "transcript_text_included": False,
        "secrets_included": False,
    }
    observability = observability_review(hardening_implemented=True)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "project_name": project_name,
        "failure": failure,
        "token": token,
        "observability": observability,
        "accounting": accounting,
        "artifact_names": {
            "failure": FAILURE_DIAGNOSIS_ARTIFACT,
            "token": TOKEN_ACCOUNTING_ARTIFACT,
            "observability": OBSERVABILITY_ARTIFACT,
            "report": REPORT_NAME,
        },
        "content_hash": content_hash(
            json.dumps(
                {
                    "failure": failure,
                    "token": token,
                    "observability": observability,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        ),
    }
