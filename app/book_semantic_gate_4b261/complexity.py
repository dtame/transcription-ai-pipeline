"""Prompt, benchmark, and output-schema complexity. Estimates are labeled."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.ai.estimation import estimate_tokens
from app.book_semantic_gate_4b23.prompt import instruction_prompt, system_prompt
from app.book_semantic_gate_4b23.schema import build_semantic_validation_schema, schema_identity
from app.book_semantic_gate_4b24.constants import (
    CONNECTIVE_CASE_ID,
    FUNERAL_CASE_ID,
    NEGATIVE_CASE_IDS,
    P3_CASE_ID,
    P8_CASE_ID,
    POSITIVE_CASE_IDS,
    SCORED_CASE_ORDER,
)
from app.book_semantic_gate_4b261.candidates import (
    build_candidate_schema,
    candidate_instruction_prompt,
    candidate_prompt_bundle,
    candidate_system_prompt,
    compact_claim,
)
from app.book_semantic_gate_4b261.constants import (
    CANDIDATE_PROMPT_VERSION,
    CANDIDATE_TRANSPORT_VERSION,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    PHASE,
    PROMPT_VERSION_HISTORICAL,
    TRANSPORT_VERSION_HISTORICAL,
)
from app.file_utils import content_hash


def _estimate(text: str) -> dict[str, Any]:
    est = estimate_tokens(text)
    return {
        "chars": len(text),
        "bytes": len(text.encode("utf-8")),
        "estimated_tokens": est.tokens,
        "estimated": True,
        "method": est.method,
    }


def _user_message(payload: Mapping[str, Any]) -> str:
    for message in payload.get("messages") or []:
        if message.get("role") == "user":
            return str(message.get("content") or "")
    return ""


def _split_user_prompt(user: str) -> tuple[str, str]:
    marker = "\nSEMANTIC_GATE_INPUT_JSON\n"
    if marker in user:
        instructions, raw = user.split(marker, 1)
        return instructions, raw.strip()
    fallback = "SEMANTIC_GATE_INPUT_JSON\n"
    if fallback in user:
        instructions, raw = user.split(fallback, 1)
        return instructions, raw.strip()
    return user, ""


def extract_gate_paragraphs(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    gate = extract_gate_input(payload)
    rows: list[dict[str, Any]] = []
    for section in (gate.get("candidate") or {}).get("sections") or []:
        for para in section.get("paras") or []:
            text = str(para.get("t") or "")
            rows.append(
                {
                    "handle": para.get("h"),
                    "kind": para.get("k"),
                    "text": text,
                    "chars": len(text),
                    "estimated_tokens": estimate_tokens(text).tokens,
                    "estimated": True,
                    "evidence_handles": list(para.get("e") or []),
                    "src": list(para.get("src") or []),
                    "ref": list(para.get("ref") or []),
                    "idea": list(para.get("idea") or []),
                }
            )
    return rows


def extract_gate_input(payload: Mapping[str, Any]) -> dict[str, Any]:
    _instructions, raw = _split_user_prompt(_user_message(payload))
    if not raw:
        return {}
    return json.loads(raw)


def _minimal_historical_response(paragraphs: list[dict[str, Any]]) -> dict[str, Any]:
    pr = []
    for para in paragraphs:
        text = str(para.get("text") or "")
        pr.append(
            {
                "h": para.get("handle"),
                "v": CLASS_SUPPORTED,
                "c": [
                    {
                        "i": 0,
                        "t": text,
                        "s": 0,
                        "e": len(text),
                        "k": CLASS_SUPPORTED,
                        "ev": list(para.get("src") or [])[:1],
                        "r": [],
                        "x": "ok",
                        "cf": "HIGH",
                    }
                ],
                "ev": list(para.get("src") or [])[:1],
                "r": [],
            }
        )
    return {
        "ch": "CH016",
        "v": "PASS",
        "pr": pr,
        "sc": {
            "supported": len(pr),
            "questionable": 0,
            "unsupported": 0,
            "non_substantive": 0,
        },
        "uh": [],
        "rr": False,
    }


def _detailed_historical_response(paragraphs: list[dict[str, Any]]) -> dict[str, Any]:
    pr = []
    supported = 0
    for para in paragraphs:
        text = str(para.get("text") or "")
        claims = []
        cursor = 0
        parts = [part.strip() for part in text.replace(";", ".").split(".") if part.strip()]
        if not parts:
            parts = [text]
        for index, part in enumerate(parts):
            start = text.find(part, cursor)
            if start < 0:
                start = cursor
            end = start + len(part)
            cursor = end
            explanation = (
                "The clause is judged against the supplied SRC/IDEA/REF handles "
                "without using external memory, and the offset coverage is complete."
            )
            claims.append(
                {
                    "i": index,
                    "t": text[start:end],
                    "s": start,
                    "e": end,
                    "k": CLASS_SUPPORTED,
                    "ev": list(para.get("evidence_handles") or []),
                    "r": [],
                    "x": explanation,
                    "cf": "MEDIUM",
                }
            )
            supported += 1
        pr.append(
            {
                "h": para.get("handle"),
                "v": CLASS_SUPPORTED,
                "c": claims,
                "ev": list(para.get("evidence_handles") or []),
                "r": [],
            }
        )
    return {
        "ch": "CH016",
        "v": "PASS",
        "pr": pr,
        "sc": {
            "supported": supported,
            "questionable": 0,
            "unsupported": 0,
            "non_substantive": 0,
        },
        "uh": [],
        "rr": False,
    }


def _minimal_candidate_response(paragraphs: list[dict[str, Any]]) -> dict[str, Any]:
    pr = []
    for para in paragraphs:
        text = str(para.get("text") or "")
        pr.append(
            {
                "h": para.get("handle"),
                "v": CLASS_SUPPORTED,
                "c": [
                    compact_claim(
                        0,
                        start=0,
                        end=len(text),
                        kind=CLASS_SUPPORTED,
                        evidence=list(para.get("src") or [])[:1],
                    )
                ],
                "ev": list(para.get("src") or [])[:1],
                "r": [],
            }
        )
    return {
        "ch": "CH016",
        "v": "PASS",
        "pr": pr,
        "sc": {
            "supported": len(pr),
            "questionable": 0,
            "unsupported": 0,
            "non_substantive": 0,
        },
        "uh": [],
        "rr": False,
    }


def analyze_prompt_and_benchmark(payload: Mapping[str, Any]) -> dict[str, Any]:
    messages = list(payload.get("messages") or [])
    system = ""
    user = ""
    for message in messages:
        if message.get("role") == "system":
            system = str(message.get("content") or "")
        elif message.get("role") == "user":
            user = str(message.get("content") or "")
    instructions, _raw_gate = _split_user_prompt(user)
    gate = extract_gate_input(payload)
    paragraphs = extract_gate_paragraphs(payload)
    src_text = list(gate.get("src_text") or [])
    evidence_blob = json.dumps(src_text, ensure_ascii=False)
    ideas = json.dumps(gate.get("ideas") or [], ensure_ascii=False)
    refs = json.dumps(gate.get("references") or [], ensure_ascii=False)
    schema = build_semantic_validation_schema()
    schema_text = json.dumps(schema, ensure_ascii=False, sort_keys=True)
    minimal = _minimal_historical_response(paragraphs)
    detailed = _detailed_historical_response(paragraphs)
    compact = _minimal_candidate_response(paragraphs)
    handle_map = {handle: case_id for handle, case_id in SCORED_CASE_ORDER}
    cases = []
    for para in paragraphs:
        handle = str(para.get("handle") or "")
        case_id = handle_map.get(handle)
        role = "positive" if case_id in POSITIVE_CASE_IDS else "negative"
        cases.append(
            {
                "handle": handle,
                "case_id": case_id,
                "role": role,
                "chars": para.get("chars"),
                "estimated_tokens": para.get("estimated_tokens"),
                "estimated": True,
                "critical": case_id
                in {FUNERAL_CASE_ID, CONNECTIVE_CASE_ID, P3_CASE_ID, P8_CASE_ID},
            }
        )
    return {
        "phase": PHASE,
        "prompt_version": PROMPT_VERSION_HISTORICAL,
        "transport_version": TRANSPORT_VERSION_HISTORICAL,
        "sizes": {
            "system_prompt": _estimate(system or system_prompt()),
            "validation_instructions": _estimate(instructions or instruction_prompt()),
            "evidence_src_text": _estimate(evidence_blob),
            "ideas": _estimate(ideas),
            "references": _estimate(refs),
            "paragraphs_total": _estimate(
                "\n".join(str(item.get("text") or "") for item in paragraphs)
            ),
            "full_user_message": _estimate(user),
            "output_schema_local": _estimate(schema_text),
            "full_request_payload": _estimate(
                json.dumps(dict(payload), ensure_ascii=False, sort_keys=True)
            ),
        },
        "paragraphs": paragraphs,
        "cases": cases,
        "case_count": len(cases),
        "positive_cases": list(POSITIVE_CASE_IDS),
        "negative_cases": list(NEGATIVE_CASE_IDS),
        "critical_negatives": {
            "FUNERAL": FUNERAL_CASE_ID,
            "CONNECTIVE": CONNECTIVE_CASE_ID,
            "P3": P3_CASE_ID,
            "P8": P8_CASE_ID,
        },
        "human_labels_not_modified": True,
        "coverage_obligations": {
            "every_paragraph_requires_pr_row": True,
            "claims_must_cover_full_paragraph_except_whitespace": True,
            "subordinate_clauses_must_not_be_skipped": True,
            "exact_offsets_required": True,
        },
        "justification_obligations": {
            "claim_text_copied_in_t": True,
            "free_text_explanation_x_required": True,
            "reason_codes_required_if_not_supported": True,
            "confidence_optional_but_prompted": True,
        },
        "verbosity_assessment": {
            "encourages_long_explanations": True,
            "duplicates_paragraph_text_in_claim_t": True,
            "repeats_evidence_handles_at_claim_and_paragraph": True,
            "essential_fidelity_requirements_must_remain": [
                "claim-level coverage",
                "exact spans",
                "reason codes",
                "evidence handles actually used",
                "SUPPORTED/QUESTIONABLE/UNSUPPORTED/NON_SUBSTANTIVE",
                "QUESTIONABLE and UNSUPPORTED block acceptance",
                "unevaluated substantive claims are never accepted",
            ],
            "safe_to_compact": [
                "copied claim text t (recoverable from s/e)",
                "free-form x when a reason code already names the defect",
                "confidence cf",
            ],
        },
        "output_size_estimates": {
            "minimal_valid_historical_json": _estimate(
                json.dumps(minimal, ensure_ascii=False, separators=(",", ":"))
            ),
            "detailed_valid_historical_json": _estimate(
                json.dumps(detailed, ensure_ascii=False, separators=(",", ":"))
            ),
            "minimal_valid_candidate_json": _estimate(
                json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
            ),
            "note": (
                "Estimates only. They describe local serialization size, not "
                "Terra reasoning tokens or billed completion tokens."
            ),
        },
        "observed_4b26_visible_json_bytes": 0,
        "observed_4b26_completion_tokens": 8192,
        "secrets_included": False,
    }


def analyze_output_schema() -> dict[str, Any]:
    historical = schema_identity()
    candidate = {
        "transport_version": CANDIDATE_TRANSPORT_VERSION,
        "raw_schema_sha256": content_hash(
            json.dumps(build_candidate_schema(), ensure_ascii=False, sort_keys=True)
        ),
    }
    return {
        "phase": PHASE,
        "historical": historical,
        "candidate_not_promoted": candidate,
        "historical_required_claim_fields": ["i", "t", "s", "e", "k", "ev", "r", "x"],
        "fields_that_inflate_output": ["t", "x", "cf"],
        "fields_essential_to_fidelity": ["s", "e", "k", "ev", "r", "h"],
        "native_json_schema_not_sent": True,
        "json_object_plus_local_validation": True,
        "secrets_included": False,
    }


def candidate_diff() -> dict[str, Any]:
    hist_system = system_prompt()
    hist_instr = instruction_prompt()
    cand = candidate_prompt_bundle()
    hist_schema = json.dumps(build_semantic_validation_schema(), ensure_ascii=False, sort_keys=True)
    cand_schema = json.dumps(build_candidate_schema(), ensure_ascii=False, sort_keys=True)
    return {
        "phase": PHASE,
        "historical_prompt_version": PROMPT_VERSION_HISTORICAL,
        "candidate_prompt_version": CANDIDATE_PROMPT_VERSION,
        "historical_transport_version": TRANSPORT_VERSION_HISTORICAL,
        "candidate_transport_version": CANDIDATE_TRANSPORT_VERSION,
        "candidate_is_not_historical_4b26_request": True,
        "prompt": {
            "historical_system_sha256": content_hash(hist_system),
            "candidate_system_sha256": cand["system_sha256"],
            "historical_instructions_sha256": content_hash(hist_instr),
            "candidate_instructions_sha256": cand["instructions_sha256"],
            "system_identical": hist_system == candidate_system_prompt(),
            "instructions_identical": hist_instr == candidate_instruction_prompt(),
            "system_char_delta": len(candidate_system_prompt()) - len(hist_system),
            "instruction_char_delta": len(candidate_instruction_prompt()) - len(hist_instr),
        },
        "schema": {
            "historical_sha256": content_hash(hist_schema),
            "candidate_sha256": content_hash(cand_schema),
            "identical": hist_schema == cand_schema,
            "historical_bytes": len(hist_schema.encode("utf-8")),
            "candidate_bytes": len(cand_schema.encode("utf-8")),
        },
        "semantic_invariants_kept": [
            "four verdicts",
            "claim-level spans",
            "reason codes",
            "evidence handles",
            "QUESTIONABLE/UNSUPPORTED block acceptance",
            "no external knowledge",
            "no label leakage tokens",
        ],
        "promoted": False,
        "secrets_included": False,
    }


__all__ = [
    "analyze_output_schema",
    "analyze_prompt_and_benchmark",
    "candidate_diff",
    "extract_gate_input",
    "extract_gate_paragraphs",
]
