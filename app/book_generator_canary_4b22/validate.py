"""Offline decode / reconstruct / validate. Extra empty/whitespace counts."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generator_canary_4b2.validate import (
    interpret_production_response as _interpret_production_response,
    validate_temporary_handles,
)


def count_empty_and_whitespace(transport: Mapping[str, Any] | None) -> dict[str, Any]:
    empty = 0
    whitespace = 0
    rows: list[dict[str, Any]] = []
    if not isinstance(transport, Mapping):
        return {
            "empty_paragraphs": 0,
            "whitespace_paragraphs": 0,
            "rows": [],
        }
    for section in transport.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        sid = str(section.get("sid") or "")
        for para in section.get("paras") or []:
            if not isinstance(para, Mapping):
                continue
            raw = para.get("t")
            text = "" if raw is None else str(raw)
            handle = str(para.get("h") or "")
            is_empty = text == ""
            is_ws = (not is_empty) and text.strip() == ""
            if is_empty:
                empty += 1
            if is_ws:
                whitespace += 1
            if is_empty or is_ws:
                rows.append(
                    {
                        "section_id": sid,
                        "handle": handle,
                        "empty": is_empty,
                        "whitespace_only": is_ws,
                    }
                )
    return {
        "empty_paragraphs": empty,
        "whitespace_paragraphs": whitespace,
        "rows": rows,
    }


def interpret_production_response(
    raw_parsed: Mapping[str, Any] | None,
    **kwargs: Any,
) -> dict[str, Any]:
    contract = _interpret_production_response(raw_parsed, **kwargs)
    transport = contract.get("transport")
    emptiness = count_empty_and_whitespace(
        transport if isinstance(transport, Mapping) else raw_parsed
    )
    contract["empty_paragraphs"] = emptiness["empty_paragraphs"]
    contract["whitespace_paragraphs"] = emptiness["whitespace_paragraphs"]
    contract["empty_whitespace_rows"] = emptiness["rows"]
    validator = dict(contract.get("local_validator") or {})
    contract["validator_evidence"] = {
        "empty_paragraph_checks": emptiness["empty_paragraphs"] == 0
        and not any("empty text" in str(item) for item in validator.get("errors") or []),
        "whitespace_checks": emptiness["whitespace_paragraphs"] == 0,
        "evidence_checks": int(contract.get("unsourced_substantive_paragraphs") or 0)
        == 0
        and int(contract.get("unknown_src_refs") or 0) == 0,
        "structure": contract.get("section_coverage") == "PASS"
        and contract.get("section_order") == "PASS",
        "idea_coverage": contract.get("idea_coverage") == "PASS"
        and int(contract.get("silent_idea_omissions") or 0) == 0,
        "src_validity": int(contract.get("unknown_src_refs") or 0) == 0,
        "language": (contract.get("language") or {}).get("status"),
        "validator_version": validator.get("validator_version"),
        "validator_status": validator.get("status"),
        "errors": list(validator.get("errors") or []),
        "warnings": list(validator.get("warnings") or []),
    }
    return contract


__all__ = [
    "count_empty_and_whitespace",
    "interpret_production_response",
    "validate_temporary_handles",
]
