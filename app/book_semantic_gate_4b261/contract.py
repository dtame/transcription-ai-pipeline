"""API response-contract analysis from adapter code and 4B.2.6 traces."""

from __future__ import annotations

import inspect
from typing import Any

from app.ai.openai_compat import (
    PRODUCTION_OPENAI_ENDPOINT,
    resolve_chat_completions_token_contract,
)
from app.ai.providers.openai_engine import OpenAIEngine
from app.ai.structured import parse_json_payload
from app.book_semantic_gate_4b23.prompt import instruction_prompt, system_prompt
from app.book_semantic_gate_4b23.schema import build_semantic_validation_schema
from app.book_semantic_gate_4b23.transport import SemanticTransportError, decode_transport
from app.book_semantic_gate_4b24.validate import validate_semantic_response
from app.book_semantic_gate_4b261.constants import (
    CONFIDENCE_CONFIRMED,
    CONFIDENCE_HYPOTHESIS,
    CONFIDENCE_LOCAL,
    CONFIDENCE_UNKNOWN,
    MODEL,
    OUTPUT_MODE,
    PHASE,
    PRODUCTION_ENDPOINT,
    SEMANTIC_TOKEN_BUDGET,
)
from app.book_semantic_gate_4b261.forensics import parse_recorded_empty_response


def _fact(fact: str, confidence: str, evidence: str) -> dict[str, str]:
    return {"fact": fact, "confidence": confidence, "evidence": evidence}


def analyze_api_contract(
    *,
    payload: dict[str, Any] | None = None,
    raw_text: str = "",
) -> dict[str, Any]:
    invoke = inspect.getsource(OpenAIEngine._invoke)
    build = inspect.getsource(OpenAIEngine.build_payload)
    normalize = inspect.getsource(OpenAIEngine._normalize)
    contract = resolve_chat_completions_token_contract(MODEL)
    schema = build_semantic_validation_schema()
    system = system_prompt()
    instructions = instruction_prompt()
    explicit_json = (
        "Respond only through the requested JSON object." in system
        and "Output one object:" in instructions
    )
    empty = parse_recorded_empty_response(raw_text)
    length_truncated = True
    missing = validate_semantic_response(
        None,
        required_handles=[f"h{index:02d}" for index in range(1, 11)],
        paragraph_texts={},
    )
    try:
        decode_transport(None)
        transport_empty = "unexpected_pass"
    except SemanticTransportError as exc:
        transport_empty = str(exc)

    return {
        "phase": PHASE,
        "endpoint": {
            "production": PRODUCTION_ENDPOINT,
            "sdk_method": "client.chat.completions.create",
            "responses_api_used": False,
            "invoke_uses_chat_completions": "chat.completions.create" in invoke,
            "confidence": CONFIDENCE_CONFIRMED,
        },
        "json_object": {
            "local_serialization": (
                (payload or {}).get("response_format") == {"type": OUTPUT_MODE}
            ),
            "engine_sets_response_format": 'response_format"] = {"type": "json_object"}'
            in build
            or '"json_object"' in build,
            "request_not_http_400": True,
            "usable_json_returned": False,
            "semantic_acceptance": CONFIDENCE_UNKNOWN,
            "note": (
                "The request was not rejected for json_object. That is not "
                "semantic acceptance. No JSON body was returned."
            ),
        },
        "explicit_json_instruction": {
            "present": explicit_json,
            "system_clause": "Respond only through the requested JSON object.",
            "user_clause": "Output one object:",
            "confidence": CONFIDENCE_CONFIRMED,
        },
        "expected_schema_constraints": {
            "required_top": schema.get("required"),
            "claim_required": schema["$defs"]["claim"]["required"],
            "paragraph_required": schema["$defs"]["paragraph"]["required"],
            "native_json_schema_sent": False,
            "engine_mode": OUTPUT_MODE,
            "confidence": CONFIDENCE_CONFIRMED,
        },
        "reasoning_policy": {
            "local": "provider_default / omitted",
            "explicit_thinking_fields_sent": False,
            "prompt_forbids_hidden_cot": "Do not request or emit hidden chain-of-thought."
            in system,
            "server_behavior": CONFIDENCE_UNKNOWN,
        },
        "completion_budget": {
            "field": contract.parameter,
            "value": SEMANTIC_TOKEN_BUDGET,
            "max_tokens_absent": "max_tokens" not in (payload or {}),
            "server_accepted_field": True,
            "server_exhausted_budget": True,
            "confidence_field_accepted": CONFIDENCE_CONFIRMED,
            "confidence_budget_sufficient": CONFIDENCE_HYPOTHESIS,
        },
        "parsing": {
            "entry": "parse_structured_output -> parse_json_payload",
            "empty_content_raises": empty,
            "no_json_repair": True,
            "no_second_model_call": True,
            "confidence": CONFIDENCE_LOCAL,
        },
        "finish_reason_length": {
            "persisted": True,
            "marks_truncated": True,
            "does_not_classify_missing_cases": True,
            "local_validation": {
                "json_parse": missing.get("json_parse"),
                "case_coverage": missing.get("case_coverage"),
                "missing_cases": missing.get("missing_cases"),
            },
            "confidence": CONFIDENCE_LOCAL,
        },
        "empty_message_content": {
            "normalize_none_raises_ai_response_error": "aucun contenu" in normalize,
            "empty_string_reaches_structured_parser": True,
            "4b26_error": "AIStructuredOutputError empty",
            "transport_on_none": transport_empty,
            "confidence": CONFIDENCE_CONFIRMED,
        },
        "confirmed": [
            _fact(
                "Production endpoint is chat.completions.create",
                CONFIDENCE_CONFIRMED,
                "OpenAIEngine._invoke",
            ),
            _fact(
                "4B.2.6 sent response_format=json_object and was not HTTP 400",
                CONFIDENCE_CONFIRMED,
                "request identity + provider evidence",
            ),
            _fact(
                "finish_reason=length and visible content empty",
                CONFIDENCE_CONFIRMED,
                "provider evidence + raw structured response",
            ),
            _fact(
                "Missing cases are not classified; 0/10 is absence of decisions",
                CONFIDENCE_CONFIRMED,
                "case results + validate_semantic_response(None)",
            ),
        ],
        "locally_verified": [
            _fact(
                "json_object serializes locally on SDK 2.43.0",
                CONFIDENCE_LOCAL,
                "OpenAI._build_request capture",
            ),
            _fact(
                "Empty text raises AIStructuredOutputError parse_failure_kind=empty",
                CONFIDENCE_LOCAL,
                "parse_json_payload('')",
            ),
            _fact(
                "None transport is refused and does not accept missing cases",
                CONFIDENCE_LOCAL,
                "decode_transport / apply_acceptance",
            ),
        ],
        "unknown_server_side": [
            _fact(
                "json_object semantic production by gpt-5.6-terra",
                CONFIDENCE_UNKNOWN,
                "No JSON body observed",
            ),
            _fact(
                "Whether hidden reasoning consumed the 8192-token budget",
                CONFIDENCE_UNKNOWN,
                "reasoning_tokens not persisted",
            ),
            _fact(
                "Whether a larger budget would emit JSON",
                CONFIDENCE_UNKNOWN,
                "No second observation",
            ),
        ],
        "hypotheses": [
            _fact(
                "Hidden reasoning or non-emitted tokens exhausted max_completion_tokens before JSON",
                CONFIDENCE_HYPOTHESIS,
                "length + empty content + 8192 completion tokens",
            ),
            _fact(
                "Ten-case verbose JSON contract increased planning cost enough to starve visible output",
                CONFIDENCE_HYPOTHESIS,
                "full claim-text copies + explanations + 10 paragraphs",
            ),
        ],
        "cannot_claim": [
            "json_object is semantically accepted because the API did not return HTTP 400",
            "reasoning_tokens = 8192 because completion_tokens = 8192",
            "increasing the budget will necessarily produce JSON",
        ],
        "secrets_included": False,
    }


def empty_content_is_not_accepted() -> bool:
    result = validate_semantic_response(
        None,
        required_handles=["h01"],
        paragraph_texts={"h01": "x"},
    )
    return (
        result["json_parse"] == "FAIL"
        and result["case_coverage"] == "FAIL"
        and result["missing_cases"] == ["h01"]
        and result["acceptance"]["cache_acceptance"] is False
    )


__all__ = ["analyze_api_contract", "empty_content_is_not_accepted"]
