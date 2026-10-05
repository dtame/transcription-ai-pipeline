"""Benchmark request through the frozen 4B.2.3 production semantic-gate path."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.ai.contracts import AIRequest
from app.book_semantic_gate_4b23.constants import (
    CONSERVATIVE_MAX_OUTPUT_TOKENS,
    DEFAULT_MAX_OUTPUT_TOKENS,
)
from app.book_semantic_gate_4b23.evidence import (
    build_gate_input,
    render_gate_input_json,
)
from app.book_semantic_gate_4b23.payload import build_gate_request
from app.book_semantic_gate_4b24.constants import (
    AUTHORIZATION_SCOPE,
    PHASE,
    SCORED_CASE_ORDER,
    TARGET_CHAPTER_ID,
    TARGET_SECTION_ID,
)
from app.book_semantic_gate_4b24.engine import CountingOpenAIEngine
from app.book_semantic_gate_4b24.identity import scored_cases
from app.file_utils import content_hash


def _paragraph_from_candidate(
    candidate: Mapping[str, Any], handle: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    for section in candidate.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        for para in section.get("paragraphs") or []:
            if not isinstance(para, Mapping):
                continue
            if str(para.get("provider_handle") or "") == handle:
                return dict(para), dict(section)
    raise KeyError(handle)


def opaque_handle_map() -> dict[str, str]:
    return {case_id: handle for handle, case_id in SCORED_CASE_ORDER}


def case_id_for_handle(handle: str) -> str:
    for opaque, case_id in SCORED_CASE_ORDER:
        if opaque == handle:
            return case_id
    raise KeyError(handle)


def build_benchmark_candidate(
    *,
    benchmark: Mapping[str, Any],
    candidate_4b2: Mapping[str, Any],
    candidate_4b22: Mapping[str, Any],
) -> dict[str, Any]:
    by_id = {str(item.get("case_id") or ""): item for item in scored_cases(benchmark)}
    paragraphs: list[dict[str, Any]] = []
    for opaque, case_id in SCORED_CASE_ORDER:
        case = by_id[case_id]
        source_candidate = (
            candidate_4b22 if str(case.get("source") or "") == "4B.2.2" else candidate_4b2
        )
        original, section = _paragraph_from_candidate(
            source_candidate, str(case["paragraph_handle"])
        )
        if str(original.get("text") or "") != str(case.get("text") or ""):
            raise ValueError(f"benchmark text drift for {case_id}")
        rewritten = dict(original)
        rewritten["provider_handle"] = opaque
        rewritten["h"] = opaque
        paragraphs.append(rewritten)
    title = str(candidate_4b22.get("title") or candidate_4b2.get("title") or "")
    return {
        "chapter_id": TARGET_CHAPTER_ID,
        "title": title,
        "sections": [
            {
                "section_id": TARGET_SECTION_ID,
                "title": str(
                    (candidate_4b22.get("sections") or [{}])[0].get("title")
                    or (candidate_4b2.get("sections") or [{}])[0].get("title")
                    or ""
                ),
                "paragraphs": paragraphs,
            }
        ],
    }


def build_benchmark_gate_input(
    *,
    candidate: Mapping[str, Any],
    evidence: Mapping[str, Any],
    language: str,
) -> dict[str, Any]:
    return build_gate_input(
        candidate=candidate,
        evidence=evidence,
        language=language,
    )


def build_canary_request(
    gate_input: Mapping[str, Any],
    *,
    max_output_tokens: int | None = None,
) -> AIRequest:
    output = (
        max_output_tokens
        if max_output_tokens is not None
        else CONSERVATIVE_MAX_OUTPUT_TOKENS
    )
    base = build_gate_request(gate_input, max_output_tokens=output)
    metadata = dict(base.metadata)
    metadata["authorization_scope"] = AUTHORIZATION_SCOPE
    metadata["phase"] = PHASE
    metadata["benchmark_canary"] = True
    return AIRequest(
        prompt=base.prompt,
        system_prompt=base.system_prompt,
        model=base.model,
        temperature=None,
        max_output_tokens=base.max_output_tokens,
        response_schema=base.response_schema,
        thinking_mode=None,
        effort=None,
        thinking_budget_tokens=None,
        metadata=metadata,
    )


def build_openai_payload(request: AIRequest) -> dict[str, Any]:
    engine = CountingOpenAIEngine(api_key="offline-phase4b24-unused", client=object())
    payload = engine.build_payload(request, str(request.model))
    payload.pop("timeout", None)
    return payload


def serialize_payload(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, sort_keys=True)


def request_identity_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw = serialize_payload(payload)
    encoded = raw.encode("utf-8")
    return {
        "sha256": content_hash(raw),
        "chars": len(raw),
        "bytes": len(encoded),
        "model": payload.get("model"),
        "temperature_present": "temperature" in payload,
        "thinking_present": "thinking" in payload,
        "response_format": payload.get("response_format"),
        "max_tokens": payload.get("max_tokens"),
        "max_completion_tokens": payload.get("max_completion_tokens"),
    }


def build_request_twice(
    gate_input: Mapping[str, Any],
    *,
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    first_request = build_canary_request(
        gate_input, max_output_tokens=max_output_tokens
    )
    second_request = build_canary_request(
        gate_input, max_output_tokens=max_output_tokens
    )
    first = build_openai_payload(first_request)
    second = build_openai_payload(second_request)
    first_id = request_identity_from_payload(first)
    second_id = request_identity_from_payload(second)
    deterministic = (
        first_id["sha256"] == second_id["sha256"]
        and first_id["chars"] == second_id["chars"]
        and first_id["bytes"] == second_id["bytes"]
    )
    return {
        "request": first_request,
        "payload": first,
        "first": first_id,
        "second": second_id,
        "deterministic": deterministic,
        "gate_input_sha256": content_hash(render_gate_input_json(gate_input)),
        "required_handles": [handle for handle, _case_id in SCORED_CASE_ORDER],
        "default_max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
        "conservative_max_output_tokens": CONSERVATIVE_MAX_OUTPUT_TOKENS,
    }


def paragraph_texts_from_candidate(candidate: Mapping[str, Any]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for section in candidate.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        for para in section.get("paragraphs") or []:
            if not isinstance(para, Mapping):
                continue
            handle = str(para.get("provider_handle") or para.get("h") or "")
            if handle:
                texts[handle] = str(para.get("text") or para.get("t") or "")
    return texts


__all__ = [
    "build_benchmark_candidate",
    "build_benchmark_gate_input",
    "build_canary_request",
    "build_openai_payload",
    "build_request_twice",
    "case_id_for_handle",
    "opaque_handle_map",
    "paragraph_texts_from_candidate",
    "request_identity_from_payload",
    "serialize_payload",
]
