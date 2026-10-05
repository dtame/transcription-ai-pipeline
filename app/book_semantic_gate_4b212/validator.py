"""Deterministic contract 2.0.2 response validator. No silent repair or aliasing."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    CLASSIFICATIONS,
)
from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b29.validator import parse_raw_response
from app.book_semantic_gate_4b212.constants import (
    FORBIDDEN_MODEL_FIELDS,
    OPERATIONAL_VALUES,
    PHASE,
    PROMPT_VERSION_202_CANDIDATE,
    TECHNICAL_CONFORMANCE,
)

_TOP = frozenset({"ch", "pr"})
_PARAGRAPH = frozenset({"h", "u"})
_UNIT = frozenset({"id", "k", "ev", "r", "n"})
_LOWERCASE_CLASS = {item.lower() for item in CLASSIFICATIONS}


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


def derive_paragraph_classification(kinds: Sequence[str]) -> str:
    if CLASS_UNSUPPORTED in kinds:
        return CLASS_UNSUPPORTED
    if CLASS_QUESTIONABLE in kinds:
        return CLASS_QUESTIONABLE
    if CLASS_NON_SUBSTANTIVE in kinds and CLASS_SUPPORTED not in kinds:
        return CLASS_NON_SUBSTANTIVE
    return CLASS_SUPPORTED


def derive_counts(kinds: Sequence[str]) -> dict[str, int]:
    counts = {key: 0 for key in CLASSIFICATIONS}
    for kind in kinds:
        if kind in counts:
            counts[kind] += 1
    return counts


def validate_response_202(
    raw: Any,
    prepared: Mapping[str, Any],
    *,
    allowed_evidence: Sequence[str] | None = None,
    expected_chapter: str | None = None,
) -> dict[str, Any]:
    """Validate a 2.0.2 response. Missing units are refused. Nothing is repaired.

    Historical 2.0.1 payloads are not rewritten. Uppercase sc keys are not
    folded to lowercase. PASS is not converted to SUPPORTED.
    """
    errors: list[str] = []
    parsed, parse_errors = parse_raw_response(raw)
    errors.extend(parse_errors)
    unit_ids = [str(unit.get("unit_id") or "") for unit in prepared.get("units") or []]
    expected_handle = str(prepared.get("paragraph_id") or "")
    allowed = list(allowed_evidence if allowed_evidence is not None else prepared.get("evidence_handles") or [])
    verdicts: list[dict[str, Any]] = []
    if parsed is None:
        return _result(errors, parsed, verdicts, unit_ids, raw, kinds=[])
    if not isinstance(parsed, Mapping):
        errors.append("schema:not_object")
        return _result(errors, parsed, verdicts, unit_ids, raw, kinds=[])

    _reject_unknown(parsed, _TOP, "$", errors)
    for forbidden in FORBIDDEN_MODEL_FIELDS:
        if forbidden in parsed:
            errors.append(f"$:operational_or_derived_field_forbidden:{forbidden}")
    chapter = parsed.get("ch")
    if not isinstance(chapter, str) or not chapter.strip():
        errors.append("ch:missing")
    elif expected_chapter and chapter != expected_chapter:
        errors.append(f"ch:mismatch:{chapter}")

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
        if "v" in para:
            received = para.get("v")
            errors.append(f"{path}.v:forbidden_model_field")
            if received in OPERATIONAL_VALUES:
                errors.append(f"{path}.v:operational_value_in_semantic_context:{received}")
            errors.append(f"{path}.v:not_silently_converted")
        handle = para.get("h")
        if not isinstance(handle, str) or not handle.strip():
            errors.append(f"{path}.h:missing")
        else:
            if handle in seen_handles:
                errors.append(f"{path}.h:duplicate")
            seen_handles.append(handle)
            if expected_handle and handle != expected_handle:
                errors.append(f"{path}.h:unknown_paragraph:{handle}")
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
            if kind in OPERATIONAL_VALUES:
                errors.append(f"{upath}.k:operational_value_in_semantic_field:{kind}")
                errors.append(f"{upath}.k:not_silently_converted")
            elif isinstance(kind, str) and kind.lower() in _LOWERCASE_CLASS and kind not in CLASSIFICATIONS:
                errors.append(f"{upath}.k:invalid_case:{kind!r}")
                errors.append(f"{upath}.k:not_silently_converted")
            elif kind not in CLASSIFICATIONS:
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
            if kind in {CLASS_SUPPORTED, CLASS_NON_SUBSTANTIVE} and str(note or "").strip():
                errors.append(f"{upath}.n:forbidden_for_{kind}")
            verdicts.append(
                {
                    "unit_id": uid,
                    "k": kind,
                    "ev": used,
                    "r": reasons,
                    "n": str(note or ""),
                }
            )

    missing = [uid for uid in unit_ids if uid not in seen_unit_ids]
    if missing:
        errors.append("missing_units:" + ",".join(missing))

    return _result(errors, parsed, verdicts, unit_ids, raw, kinds=observed_kinds)


def _result(
    errors: list[str],
    parsed: Any,
    verdicts: list[dict[str, Any]],
    unit_ids: Sequence[str],
    raw: Any,
    *,
    kinds: Sequence[str],
) -> dict[str, Any]:
    ok = not errors
    derived_kinds = [str(item.get("k") or "") for item in verdicts if item.get("k") in CLASSIFICATIONS]
    observed = list(kinds) or derived_kinds
    return {
        "phase": PHASE,
        "contract": PROMPT_VERSION_202_CANDIDATE,
        "ok": ok,
        "status": "PASS" if ok else "BLOCK",
        "technical_conformance": "VALID" if ok else "INVALID",
        "technical_values": list(TECHNICAL_CONFORMANCE),
        "errors": errors,
        "parsed": parsed,
        "verdicts": verdicts,
        "required_unit_ids": list(unit_ids),
        "derived_paragraph_classification": derive_paragraph_classification(observed) if observed else None,
        "derived_counts": derive_counts(observed),
        "raw_preserved": True,
        "raw_type": type(raw).__name__,
        "does_not_complete_missing_units": True,
        "does_not_repair_reason_codes": True,
        "does_not_rewrite_model_response": True,
        "does_not_convert_pass_to_supported": True,
        "does_not_convert_supported_to_lowercase": True,
        "secrets_included": False,
    }


__all__ = [
    "derive_counts",
    "derive_paragraph_classification",
    "parse_raw_response",
    "validate_response_202",
]
