"""Local feasibility of strict JSON schema structured output. No provider call."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_semantic_gate_4b26.runtime import runtime_snapshot
from app.book_semantic_gate_4b212.constants import (
    MODEL,
    OUTPUT_MODE,
    PHASE,
    PRODUCTION_ENDPOINT,
    PRODUCTION_SDK_METHOD,
    REMOTE_STRICT_SCHEMA_COMPATIBILITY,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_semantic_gate_4b212.contract import build_response_schema_202
from app.book_semantic_gate_4b212.paths import repo_root, venv_python_path
from app.file_utils import content_hash


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def strict_schema_feasibility(*, root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    runtime = runtime_snapshot(root=root)
    site = (
        venv_python_path(root=root).parent.parent
        / "Lib"
        / "site-packages"
        / "openai"
        / "types"
    )
    json_schema_file = site / "shared_params" / "response_format_json_schema.py"
    create_params_file = site / "chat" / "completion_create_params.py"
    engine_file = base / "app" / "ai" / "providers" / "openai_engine.py"
    schema_src = _read_text(json_schema_file)
    create_src = _read_text(create_params_file)
    engine_src = _read_text(engine_file)
    local_schema = build_response_schema_202()
    sdk_exposes_json_schema = "class ResponseFormatJSONSchema" in schema_src
    sdk_exposes_strict = "strict:" in schema_src or "strict: Optional[bool]" in schema_src
    engine_hardcodes_json_object = (
        'payload["response_format"] = {"type": "json_object"}' in engine_src
    )
    engine_sends_json_schema = "json_schema" in engine_src and '"type": "json_schema"' in engine_src
    return {
        "phase": PHASE,
        "provider_calls": 0,
        "openai_sdk_version": runtime.get("openai_sdk_version"),
        "sdk_files_inspected_as_text": True,
        "openai_package_not_imported_by_4b212": True,
        "sdk_capabilities": {
            "response_format_json_object": "ResponseFormatJSONObject" in create_src,
            "response_format_json_schema": sdk_exposes_json_schema,
            "json_schema_strict_field": sdk_exposes_strict,
            "chat_completions_accepts_response_format": "ResponseFormat" in create_src,
            "local_serialization_possible": sdk_exposes_json_schema,
        },
        "required_parameters_if_used": {
            "endpoint": PRODUCTION_ENDPOINT,
            "method": PRODUCTION_SDK_METHOD,
            "response_format.type": "json_schema",
            "response_format.json_schema.name": "book_semantic_validator_202",
            "response_format.json_schema.strict": True,
            "response_format.json_schema.schema": "JSON Schema object",
        },
        "existing_code_compatibility": {
            "semantic_gate_output_mode": OUTPUT_MODE,
            "openai_engine_hardcodes_json_object": engine_hardcodes_json_object,
            "openai_engine_sends_json_schema_today": engine_sends_json_schema,
            "transport_20_candidate": TRANSPORT_VERSION_20_CANDIDATE,
            "transport_20_kept": True,
            "strict_schema_not_wired": True,
        },
        "known_limitations": [
            "SDK serialization does not prove gpt-5.6-terra accepts json_schema.",
            "OpenAI strict mode supports only a subset of JSON Schema.",
            "Optional unit field n is awkward under strict required-property rules.",
            "Existing OpenAIEngine always emits response_format=json_object.",
            "4B.2.11 succeeded at JSON PARSE with json_object; the failure was contract case/field mixing.",
        ],
        "added_complexity": [
            "New engine branch for json_schema vs json_object.",
            "Schema must stay inside the provider subset.",
            "Failures become schema-rejection rather than local validator errors, reducing forensic detail.",
            "Transport change would be a new candidate, not a silent swap.",
        ],
        "transport_impact": {
            "keep_existing_transport": True,
            "strict_schema_option_documented": True,
            "strict_schema_activated": False,
            "new_transport_version_not_created": True,
        },
        "local_202_schema": local_schema,
        "local_202_schema_sha256": content_hash(
            __import__("json").dumps(local_schema, ensure_ascii=False, sort_keys=True)
        ),
        "feasibility": "LOCAL_SDK_CAN_SERIALIZE_UNVERIFIED_REMOTE",
        "REMOTE_COMPATIBILITY": REMOTE_STRICT_SCHEMA_COMPATIBILITY,
        "do_not_assume_terra_accepts_parameter_because_sdk_can_serialize": True,
        "activated": False,
        "secrets_included": False,
    }


__all__ = ["strict_schema_feasibility"]
