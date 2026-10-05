"""Deterministic contract 2.0 response validator. No silent repair."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    CLASSIFICATIONS,
)
from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b29.constants import (
    MODEL_VERDICTS,
    MODEL_VERDICT_FAIL,
    MODEL_VERDICT_PASS,
    MODEL_VERDICT_REVIEW,
    PHASE,
    TRANSPORT_VERSION_20_CANDIDATE,
)

_TOP = frozenset({"ch", "v", "pr", "sc", "uh", "rr"})
_PARAGRAPH = frozenset({"h", "v", "u"})
_UNIT = frozenset({"id", "k", "ev", "r", "n"})
_COUNTS = frozenset({"supported", "questionable", "unsupported", "non_substantive"})
_COUNT_BY_CLASS = {
    CLASS_SUPPORTED: "supported",
    CLASS_QUESTIONABLE: "questionable",
    CLASS_UNSUPPORTED: "unsupported",
    CLASS_NON_SUBSTANTIVE: "non_substantive",
}


def _reject_unknown(payload: Mapping[str, Any], allowed: frozenset[str], path: str, errors: list[str]) -> None:
    extra = sorted(set(payload.keys()) - allowed)
    if extra:
        errors.append(f"{path}:unexpected_fields:{','.join(extra)}")


def _as_list(value: Any, path: str, errors: list[str]) -> list[Any]:
    if value is None:
        errors.append(f"{path}:missing")
        return []
    if not isinstance(value, list):
        errors.append(f"{path}:not_array")
        return []
    return value


def parse_raw_response(raw: Any) -> tuple[Any, list[str]]:
    errors: list[str] = []
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None, ["invalid_encoding"]
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None, ["empty_response"]
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None, ["invalid_json"]
        return parsed, errors
    if isinstance(raw, Mapping):
        return dict(raw), errors
    return None, [f"unexpected_type:{type(raw).__name__}"]


def _reason_ok(codes: Any, path: str, kind: str, errors: list[str]) -> list[str]:
    values = _as_list(codes, path, errors)
    cleaned: list[str] = []
    for index, item in enumerate(values):
        if not isinstance(item, str):
            errors.append(f"{path}[{index}]:not_string")
            continue
        if item not in REASON_CODES:
            errors.append(f"{path}[{index}]:unknown_reason_code:{item}")
            continue
        cleaned.append(item)
    if kind in {CLASS_SUPPORTED, CLASS_NON_SUBSTANTIVE} and cleaned:
        errors.append(f"{path}:reasons_not_empty_for_{kind}")
    if kind in {CLASS_QUESTIONABLE, CLASS_UNSUPPORTED} and not cleaned:
        errors.append(f"{path}:reasons_required_for_{kind}")
    return cleaned


def _handles_ok(
    values: Any,
    path: str,
    errors: list[str],
    *,
    allowed: Sequence[str] | None,
) -> list[str]:
    items = _as_list(values, path, errors)
    cleaned: list[str] = []
    allowed_set = set(allowed or ())
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{path}[{index}]:invalid_handle")
            continue
        handle = item.strip()
        if allowed is not None and handle not in allowed_set:
            errors.append(f"{path}[{index}]:unknown_evidence_handle:{handle}")
            continue
        cleaned.append(handle)
    return cleaned


def _expected_global(kinds: list[str]) -> str:
    if CLASS_UNSUPPORTED in kinds:
        return MODEL_VERDICT_FAIL
    if CLASS_QUESTIONABLE in kinds:
        return MODEL_VERDICT_REVIEW
    return MODEL_VERDICT_PASS


def _expected_paragraph(kinds: list[str]) -> str:
    if CLASS_UNSUPPORTED in kinds:
        return CLASS_UNSUPPORTED
    if CLASS_QUESTIONABLE in kinds:
        return CLASS_QUESTIONABLE
    if CLASS_NON_SUBSTANTIVE in kinds and CLASS_SUPPORTED not in kinds:
        return CLASS_NON_SUBSTANTIVE
    return CLASS_SUPPORTED


def validate_response_20(
    raw: Any,
    prepared: Mapping[str, Any],
    *,
    allowed_evidence: Sequence[str] | None = None,
    expected_chapter: str | None = None,
) -> dict[str, Any]:
    """Validate a 2.0 response. Missing units are refused. Nothing is repaired."""
    errors: list[str] = []
    parsed, parse_errors = parse_raw_response(raw)
    errors.extend(parse_errors)
    unit_ids = [str(unit.get("unit_id") or "") for unit in prepared.get("units") or []]
    expected_handle = str(prepared.get("paragraph_id") or "")
    allowed = list(allowed_evidence if allowed_evidence is not None else prepared.get("evidence_handles") or [])
    verdicts: list[dict[str, Any]] = []
    if parsed is None:
        return _result(errors, parsed, verdicts, unit_ids, raw)
    if not isinstance(parsed, Mapping):
        errors.append("schema:not_object")
        return _result(errors, parsed, verdicts, unit_ids, raw)

    _reject_unknown(parsed, _TOP, "$", errors)
    chapter = parsed.get("ch")
    if not isinstance(chapter, str) or not chapter.strip():
        errors.append("ch:missing")
    elif expected_chapter and chapter != expected_chapter:
        errors.append(f"ch:mismatch:{chapter}")
    global_verdict = parsed.get("v")
    if global_verdict not in MODEL_VERDICTS:
        errors.append(f"v:invalid:{global_verdict!r}")
    if not isinstance(parsed.get("rr"), bool):
        errors.append("rr:not_boolean")
    unknown = _as_list(parsed.get("uh"), "uh", errors)
    for index, item in enumerate(unknown):
        if not isinstance(item, str):
            errors.append(f"uh[{index}]:not_string")
    counts = parsed.get("sc")
    if not isinstance(counts, Mapping):
        errors.append("sc:missing")
        counts = {}
    else:
        _reject_unknown(counts, _COUNTS, "sc", errors)
        for key in _COUNTS:
            if not isinstance(counts.get(key), int):
                errors.append(f"sc.{key}:not_integer")

    paragraphs = _as_list(parsed.get("pr"), "pr", errors)
    seen_handles: list[str] = []
    observed_kinds: list[str] = []
    seen_unit_ids: list[str] = []
    if len(paragraphs) != 1:
        errors.append("pr:expected_single_paragraph")
    for p_index, para in enumerate(paragraphs):
        path = f"pr[{p_index}]"
        if not isinstance(para, Mapping):
            errors.append(f"{path}:not_object")
            continue
        _reject_unknown(para, _PARAGRAPH, path, errors)
        handle = para.get("h")
        if not isinstance(handle, str) or not handle.strip():
            errors.append(f"{path}.h:missing")
        else:
            if handle in seen_handles:
                errors.append(f"{path}.h:duplicate")
            seen_handles.append(handle)
            if expected_handle and handle != expected_handle:
                errors.append(f"{path}.h:unknown_paragraph:{handle}")
        para_verdict = para.get("v")
        if para_verdict not in CLASSIFICATIONS:
            errors.append(f"{path}.v:invalid")
        rows = _as_list(para.get("u"), f"{path}.u", errors)
        para_kinds: list[str] = []
        for u_index, row in enumerate(rows):
            upath = f"{path}.u[{u_index}]"
            if not isinstance(row, Mapping):
                errors.append(f"{upath}:not_object")
                continue
            _reject_unknown(row, _UNIT, upath, errors)
            uid = row.get("id")
            if not isinstance(uid, str) or not uid.strip():
                errors.append(f"{upath}.id:missing")
                uid = ""
            if uid in seen_unit_ids:
                errors.append(f"{upath}.id:duplicate:{uid}")
            seen_unit_ids.append(uid)
            if uid and uid not in unit_ids:
                errors.append(f"{upath}.id:unknown_unit:{uid}")
            kind = row.get("k")
            if kind not in CLASSIFICATIONS:
                errors.append(f"{upath}.k:invalid:{kind!r}")
            else:
                para_kinds.append(kind)
                observed_kinds.append(kind)
            used = _handles_ok(row.get("ev"), f"{upath}.ev", errors, allowed=allowed)
            reasons = _reason_ok(row.get("r"), f"{upath}.r", str(kind or ""), errors)
            note = row.get("n", "")
            if "n" in row and not isinstance(note, str):
                errors.append(f"{upath}.n:not_string")
                note = ""
            if kind in {CLASS_QUESTIONABLE, CLASS_UNSUPPORTED} and not str(note or "").strip():
                errors.append(f"{upath}.n:required")
            verdicts.append(
                {
                    "unit_id": uid,
                    "k": kind,
                    "ev": used,
                    "r": reasons,
                    "n": str(note or ""),
                }
            )
        if para_verdict in CLASSIFICATIONS and para_kinds:
            expected = _expected_paragraph(para_kinds)
            if para_verdict != expected:
                errors.append(f"{path}.v:incoherent:{para_verdict}!={expected}")

    missing = [uid for uid in unit_ids if uid not in seen_unit_ids]
    if missing:
        errors.append("missing_units:" + ",".join(missing))
    if isinstance(counts, Mapping) and all(isinstance(counts.get(key), int) for key in _COUNTS):
        expected_counts = {key: 0 for key in _COUNTS}
        for kind in observed_kinds:
            expected_counts[_COUNT_BY_CLASS[kind]] += 1
        for key in _COUNTS:
            if counts.get(key) != expected_counts[key]:
                errors.append(f"sc.{key}:incoherent")
    if global_verdict in MODEL_VERDICTS and observed_kinds:
        expected_global = _expected_global(observed_kinds)
        if global_verdict != expected_global:
            errors.append(f"v:incoherent:{global_verdict}!={expected_global}")
    rr = parsed.get("rr")
    if isinstance(rr, bool) and observed_kinds:
        needs_review = CLASS_QUESTIONABLE in observed_kinds or CLASS_UNSUPPORTED in observed_kinds
        if needs_review and not rr:
            errors.append("rr:incoherent_false")
        if global_verdict == MODEL_VERDICT_REVIEW and not rr:
            errors.append("rr:required_for_REVIEW")
        if global_verdict == MODEL_VERDICT_FAIL and not rr:
            errors.append("rr:required_for_FAIL")
        if global_verdict == MODEL_VERDICT_PASS and rr and CLASS_QUESTIONABLE not in observed_kinds:
            errors.append("rr:incoherent_true")

    return _result(errors, parsed, verdicts, unit_ids, raw)


def _result(
    errors: list[str],
    parsed: Any,
    verdicts: list[dict[str, Any]],
    unit_ids: Sequence[str],
    raw: Any,
) -> dict[str, Any]:
    ok = not errors
    return {
        "phase": PHASE,
        "transport": TRANSPORT_VERSION_20_CANDIDATE,
        "ok": ok,
        "status": "PASS" if ok else "BLOCK",
        "errors": errors,
        "parsed": parsed,
        "verdicts": verdicts,
        "required_unit_ids": list(unit_ids),
        "raw_preserved": True,
        "raw_type": type(raw).__name__,
        "does_not_complete_missing_units": True,
        "does_not_repair_reason_codes": True,
        "does_not_rewrite_model_response": True,
        "secrets_included": False,
    }


__all__ = ["parse_raw_response", "validate_response_20"]
