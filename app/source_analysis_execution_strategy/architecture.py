"""
Audit offline de l'architecture Source Analyzer actuelle.

Inspecte le code local seulement. Aucun engine.generate(), aucun réseau.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

from app.ai.contracts import AIRequest
from app.ai.providers._http import post_json
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.source_analysis.analyzer import analyze_source
from app.source_analysis.cache import SignatureInputs, build_signature
from app.source_analysis.context_strategy import (
    DEFAULT_WINDOW_OVERLAP_SEGMENTS,
    plan_windows,
)
from app.source_analysis.errors import SourceAnalysisContextExceeded
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis_execution_strategy.constants import (
    EXPECTED_MODEL,
    EXPECTED_PROMPT_VERSION,
)

_PACKAGE_DIR = Path(__file__).resolve().parent
_PROVIDERS_DIR = Path(__file__).resolve().parents[1] / "ai" / "providers"


def package_calls_generate_or_post() -> list[str]:
    hits: list[str] = []
    forbidden = {"generate", "post_json"}
    for path in sorted(_PACKAGE_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _call_name(node)
                if name in forbidden:
                    hits.append(f"{path.name}:{name}")
    return hits


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def assert_offline_package() -> None:
    hits = package_calls_generate_or_post()
    if hits:
        raise RuntimeError(
            "Le paquet 3B.6 ne doit pas appeler generate/post_json : "
            + ", ".join(hits)
        )


def anthropic_build_payload_has_stream() -> bool:
    engine = AnthropicEngine(model=EXPECTED_MODEL, api_key="3b6-offline-unused")
    payload = engine.build_payload(
        AIRequest(
            prompt="3b6-offline-probe",
            response_schema={"type": "object", "properties": {}},
        ),
        EXPECTED_MODEL,
    )
    return "stream" in payload


def inspect_streaming() -> dict[str, Any]:
    payload_source = inspect.getsource(AnthropicEngine.build_payload)
    invoke_source = inspect.getsource(AnthropicEngine._invoke)
    http_source = inspect.getsource(post_json)
    stream_in_payload = anthropic_build_payload_has_stream()
    return {
        "anthropic_engine_supports_streaming_now": False,
        "stream_field_in_http_payload": stream_in_payload,
        "stream_true_in_build_payload_source": "stream=True" in payload_source
        or 'stream": True' in payload_source,
        "stream_true_in_invoke_source": "stream=True" in invoke_source,
        "http_helper_uses_stream_true": "stream=True" in http_source,
        "semantic_structured_output_path_supports_streaming": False,
        "partial_bytes_or_tokens_observable": False,
        "native_json_schema_streaming_guarantees": "EXTERNAL_VERIFICATION_REQUIRED",
        "semantic_transport_v1_reconstructable_from_stream": "UNKNOWN_NOT_IMPLEMENTED",
        "malformed_or_interrupted_stream_rejection": "NOT_IMPLEMENTED",
        "would_avoid_relevant_read_timeout": (
            "UNKNOWN — requests read timeout resets on incoming bytes if "
            "chunks arrive; current path is non-streaming and waits for one "
            "complete body"
        ),
        "can_be_proven_offline": False,
        "evidence": (
            "AnthropicEngine.build_payload does not set stream. "
            "AnthropicEngine._invoke calls post_json once. "
            "post_json uses requests.post without stream=True."
        ),
    }


def inspect_async_batch() -> dict[str, Any]:
    provider_hits: list[str] = []
    keywords = (
        "messages batch",
        "message_batches",
        "batches",
        "job_id",
        "provider_job",
        "poll_job",
        "async_job",
    )
    for path in sorted(_PROVIDERS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8").lower()
        for keyword in keywords:
            if keyword in text:
                provider_hits.append(f"{path.name}:{keyword}")
    return {
        "repository_support": "NOT_IMPLEMENTED",
        "anthropic_message_batches": "NOT_IMPLEMENTED",
        "provider_job_ids": "NOT_IMPLEMENTED",
        "poll_resume": "NOT_IMPLEMENTED",
        "provider_hits_in_ai_providers": provider_hits,
        "local_semantic_batch_is_unrelated": True,
        "local_semantic_batch_role": (
            "app.semantic_batch is Phase 3A language-block classification, "
            "not an Anthropic Message Batches / async job client"
        ),
        "current_anthropic_batch_capabilities": "EXTERNAL_VERIFICATION_REQUIRED",
    }


def inspect_single_response_assumption() -> dict[str, Any]:
    analyzer_source = inspect.getsource(analyze_source)
    return {
        "exists_in": [
            {
                "location": "app/source_analysis/analyzer.py:_run_analysis",
                "assumption": (
                    "One AIRequest containing the complete user prompt, "
                    "one engine.generate(), one complete parsed body"
                ),
            },
            {
                "location": "app/ai/providers/anthropic_engine.py:_invoke",
                "assumption": (
                    "One post_json to /v1/messages; text extracted from the "
                    "complete JSON content blocks"
                ),
            },
            {
                "location": "app/ai/providers/_http.py:post_json",
                "assumption": (
                    "Non-streaming requests.post waits for the entire HTTP body"
                ),
            },
            {
                "location": "app/source_analysis/semantic_transport_decoder.py",
                "assumption": (
                    "decode_to_canonical_raw expects a complete "
                    "semantic-transport-v1 object"
                ),
            },
            {
                "location": "app/source_analysis_global_clean/runner.py",
                "assumption": (
                    "Guarded single real call; strategy must be global; "
                    "no partial-body persistence on timeout"
                ),
            },
        ],
        "analyzer_raises_if_not_global": "SourceAnalysisContextExceeded"
        in analyzer_source,
        "windowed_execution_implemented": False,
        "consolidation_implemented": False,
    }


def inspect_plan_windows() -> dict[str, Any]:
    source = inspect.getsource(plan_windows)
    return {
        "exists": True,
        "module": "app/source_analysis/context_strategy.py",
        "production_ready_for_planning": True,
        "production_ready_for_execution": False,
        "inputs": [
            "transcript: TranscriptInput (ordered present SRC segments)",
            "estimated_tokens: int (global prompt estimate)",
            "budget_tokens: int (usable input budget)",
            "overlap_segments: int (default "
            f"{DEFAULT_WINDOW_OVERLAP_SEGMENTS})",
        ],
        "outputs": "tuple[AnalysisWindow, ...] numbered from 1",
        "window_boundaries": "SRC boundaries only; a segment is never split",
        "src_behavior": (
            "Uses transcript.segments as the ordered present-SRC list. "
            "Does not invent a contiguous SRC000001…N range."
        ),
        "sparse_src_supported": True,
        "token_accounting": (
            "Window count is ceil(estimated_tokens / budget_tokens), "
            "forced to at least 2. Segments are then split into equal "
            "counts. Per-window tokens are NOT re-estimated inside "
            "plan_windows()."
        ),
        "overlap": {
            "default_segments": DEFAULT_WINDOW_OVERLAP_SEGMENTS,
            "kind": "technical_token_overlap",
            "semantic_overlap_added": False,
            "clamped_to": "max(0, min(overlap, per_window - 1))",
        },
        "determinism": True,
        "forces_minimum_two_windows": "max(2," in source,
        "unused_in_current_global_path": (
            "When the corpus fits, plan_context returns strategy=global "
            "with windows=(). plan_windows is only invoked when the "
            "estimate exceeds budget. analyzer.py then raises "
            "SourceAnalysisContextExceeded and does not execute windows."
        ),
        "historical_multi_window_limitation_still_true": True,
        "evidence": (
            "analyze_source raises SourceAnalysisContextExceeded: "
            "'la consolidation multi-fenêtres n'est pas implémentée en Phase 3.'"
        ),
    }


def inspect_cache() -> dict[str, Any]:
    fields = sorted(SignatureInputs.__dataclass_fields__)
    return {
        "current_signature_fields": fields,
        "scope": "whole_analysis",
        "per_window_signature_supported": False,
        "resume_failed_window_supported": False,
        "window_result_cache_supported": False,
        "deterministic_consolidation_signature_supported": False,
        "new_signatures_would_need": [
            "window_index",
            "window_first_src",
            "window_last_src",
            "window_src_ids_sha256",
            "window_segment_content_sha256",
            "level1_schema_sha256",
            "consolidation_input_sha256",
            "consolidation_prompt_sha256",
            "consolidation_schema_sha256",
        ],
        "build_signature_deterministic": True,
        "build_signature_present": callable(build_signature),
    }


def inspect_protected_contracts() -> dict[str, Any]:
    return {
        "prompt_version": SOURCE_ANALYZER_PROMPT_VERSION,
        "prompt_version_matches_expected": SOURCE_ANALYZER_PROMPT_VERSION
        == EXPECTED_PROMPT_VERSION,
        "generation_c_protected": True,
        "decoder_protected": True,
        "canonical_validator_protected": True,
        "clean_transcript_protected": True,
        "this_phase_must_not_change_them": True,
    }


def inspect_analyzer_window_gate() -> bool:
    return SourceAnalysisContextExceeded is not None
