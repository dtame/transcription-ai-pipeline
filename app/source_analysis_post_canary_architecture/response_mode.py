"""Revue offline du mode de réponse actuel. Aucune capacité inventée."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from app.source_analysis_post_canary_architecture.constants import (
    PHASE,
    RESPONSE_MODE_DECISION,
    SCHEMA_VERSION,
)

_AI = Path(__file__).resolve().parents[1] / "ai"
_ANTHROPIC = _AI / "providers" / "anthropic_engine.py"
_HTTP = _AI / "providers" / "_http.py"
_OPENAI = _AI / "providers" / "openai_engine.py"
_SEMANTIC_BATCH = Path(__file__).resolve().parents[1] / "semantic_batch"


def _source_mentions_stream(path: Path) -> bool:
    if not path.is_file():
        return False
    return "stream" in path.read_text(encoding="utf-8").lower()


def _anthropic_payload_has_stream() -> bool:
    tree = ast.parse(_ANTHROPIC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "stream":
            return True
    return False


def review_response_modes() -> dict[str, Any]:
    anthropic = _ANTHROPIC.read_text(encoding="utf-8")
    http = _HTTP.read_text(encoding="utf-8")
    streaming_supported_now = _anthropic_payload_has_stream()
    structured_streaming = "UNKNOWN"
    async_batch_in_providers = False
    for path in (_ANTHROPIC, _OPENAI, _HTTP):
        text = path.read_text(encoding="utf-8")
        if "batches" in text.lower() or "async_batch" in text.lower():
            async_batch_in_providers = True
    semantic_batch_exists = _SEMANTIC_BATCH.is_dir()
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "current_mode": "synchronous_non_streaming_http",
        "capture_http_response_before_provider_result": "capture_http_response" in http,
        "streaming": {
            "anthropic_engine_supports_streaming_now": streaming_supported_now,
            "payload_contains_stream_key": streaming_supported_now,
            "semantic_structured_output_path_supports_streaming": structured_streaming,
            "partial_bytes_or_tokens_observable": False,
            "can_be_proven_offline": True,
            "what_it_could_solve": [
                "earlier bytes",
                "progress visibility",
                "possibly better failure evidence",
            ],
            "what_it_would_not_solve": [
                "semantic overgeneration",
                "invalid structured JSON",
                "granularity",
                "provider-side generation failure",
            ],
            "provider_streaming_support_verified": False,
            "external_provider_verification_required": True,
        },
        "async_batch": {
            "repository_support": "NOT_IMPLEMENTED" if not async_batch_in_providers else "PRESENT",
            "semantic_batch_package": (
                "3A classifier, not provider Message Batches"
                if semantic_batch_exists
                else "absent"
            ),
            "provider_async_batch_verified": False,
            "external_provider_verification_required": True,
        },
        "forensics": {
            "hardened_boundary_active": "capture_http_response" in http
            and "ProviderHttpExchange" in http,
            "improves_observability": True,
            "improves_generation_reliability": False,
        },
        "decision": RESPONSE_MODE_DECISION,
        "required_now": False,
        "justification": (
            "Current code is synchronous non-streaming. Streaming and "
            "async/batch are not locally implemented or verified. They "
            "would not by themselves fix structured-output explosion or "
            "semantic reliability. Forensic hardening already improves "
            "failure evidence."
        ),
        "anthropic_mentions_stream_string": _source_mentions_stream(_ANTHROPIC),
        "openai_mentions_stream_string": _source_mentions_stream(_OPENAI),
    }
