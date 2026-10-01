"""Decode book-semantic-validation-transport-1.0. No provider call."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.constants import (
    CLASSIFICATIONS,
    SEMANTIC_VALIDATION_TRANSPORT_VERSION,
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_REVIEW,
)
from app.book_semantic_gate_4b23.reasons import REASON_CODES

_TOP = frozenset({"ch", "v", "pr", "sc", "uh", "rr"})
_PARAGRAPH = frozenset({"h", "v", "c", "ev", "r"})
_CLAIM = frozenset({"i", "t", "s", "e", "k", "ev", "r", "x", "cf"})
_COUNTS = frozenset({"supported", "questionable", "unsupported", "non_substantive"})
_VERDICTS = frozenset({VERDICT_PASS, VERDICT_REVIEW, VERDICT_FAIL})


class SemanticTransportError(ValueError):
    pass


def decode_transport(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise SemanticTransportError(f"transport inattendu : {type(payload).__name__}")
    errors: list[str] = []
    _reject_unknown(payload, _TOP, "transport", errors)
    chapter = payload.get("ch")
    if not isinstance(chapter, str) or not chapter.strip():
        errors.append("ch manquant")
    verdict = payload.get("v")
    if verdict not in _VERDICTS:
        errors.append(f"v invalide : {verdict!r}")
    if not isinstance(payload.get("rr"), bool):
        errors.append("rr doit être un booléen")
    unknown = _as_list(payload.get("uh"), "uh", errors)
    counts = payload.get("sc")
    if not isinstance(counts, Mapping):
        errors.append("sc manquant")
    else:
        _reject_unknown(counts, _COUNTS, "sc", errors)
        for key in _COUNTS:
            if not isinstance(counts.get(key), int):
                errors.append(f"sc.{key} doit être un entier")
    paragraphs = _as_list(payload.get("pr"), "pr", errors)
    for p_index, para in enumerate(paragraphs):
        if not isinstance(para, Mapping):
            errors.append(f"pr[{p_index}] n'est pas un objet")
            continue
        _reject_unknown(para, _PARAGRAPH, f"pr[{p_index}]", errors)
        if not isinstance(para.get("h"), str) or not str(para.get("h") or "").strip():
            errors.append(f"pr[{p_index}].h manquant")
        if para.get("v") not in CLASSIFICATIONS:
            errors.append(f"pr[{p_index}].v invalide")
        _as_list(para.get("ev"), f"pr[{p_index}].ev", errors)
        _reason_list(para.get("r"), f"pr[{p_index}].r", errors)
        claims = _as_list(para.get("c"), f"pr[{p_index}].c", errors)
        for c_index, claim in enumerate(claims):
            path = f"pr[{p_index}].c[{c_index}]"
            if not isinstance(claim, Mapping):
                errors.append(f"{path} n'est pas un objet")
                continue
            _reject_unknown(claim, _CLAIM, path, errors)
            if not isinstance(claim.get("i"), int):
                errors.append(f"{path}.i doit être un entier")
            if not isinstance(claim.get("t"), str) or not str(claim.get("t") or "").strip():
                errors.append(f"{path}.t manquant")
            if not isinstance(claim.get("s"), int) or not isinstance(claim.get("e"), int):
                errors.append(f"{path}.s/e doivent être des entiers")
            if claim.get("k") not in CLASSIFICATIONS:
                errors.append(f"{path}.k invalide")
            _as_list(claim.get("ev"), f"{path}.ev", errors)
            _reason_list(claim.get("r"), f"{path}.r", errors)
            if not isinstance(claim.get("x"), str) or not str(claim.get("x") or "").strip():
                errors.append(f"{path}.x manquant")
    if errors:
        raise SemanticTransportError("; ".join(errors))
    return {
        "chapter_handle": str(chapter),
        "verdict": str(verdict),
        "paragraph_results": [
            _normalize_paragraph(item) for item in paragraphs if isinstance(item, Mapping)
        ],
        "summary_counts": dict(counts) if isinstance(counts, Mapping) else {},
        "unknown_handles": [str(item) for item in unknown],
        "review_required": bool(payload.get("rr")),
        "transport_version": SEMANTIC_VALIDATION_TRANSPORT_VERSION,
        "raw": dict(payload),
    }


def _normalize_paragraph(para: Mapping[str, Any]) -> dict[str, Any]:
    claims = []
    for claim in para.get("c") or []:
        if not isinstance(claim, Mapping):
            continue
        claims.append(
            {
                "claim_index": claim.get("i"),
                "claim_text": str(claim.get("t") or ""),
                "start_offset": claim.get("s"),
                "end_offset": claim.get("e"),
                "classification": str(claim.get("k") or ""),
                "evidence_handles": [str(item) for item in claim.get("ev") or []],
                "reason_codes": [str(item) for item in claim.get("r") or []],
                "explanation": str(claim.get("x") or ""),
                "confidence": claim.get("cf"),
            }
        )
    return {
        "paragraph_handle": str(para.get("h") or ""),
        "verdict": str(para.get("v") or ""),
        "claim_results": claims,
        "evidence_used": [str(item) for item in para.get("ev") or []],
        "reason_codes": [str(item) for item in para.get("r") or []],
    }


def _as_list(value: Any, path: str, errors: list[str]) -> list:
    if value is None:
        errors.append(f"{path} manquant")
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        errors.append(f"{path} doit être un tableau")
        return []
    return list(value)


def _reason_list(value: Any, path: str, errors: list[str]) -> list[str]:
    rows = _as_list(value, path, errors)
    cleaned: list[str] = []
    for item in rows:
        text = str(item)
        if text not in REASON_CODES:
            errors.append(f"{path} code inconnu : {text}")
            continue
        cleaned.append(text)
    return cleaned


def _reject_unknown(
    payload: Mapping[str, Any],
    allowed: frozenset[str],
    path: str,
    errors: list[str],
) -> None:
    extra = sorted(str(key) for key in payload.keys() if str(key) not in allowed)
    for key in extra:
        errors.append(f"champ inconnu {path}.{key}")


def transport_identity() -> dict[str, Any]:
    return {
        "version": SEMANTIC_VALIDATION_TRANSPORT_VERSION,
        "top_level": sorted(_TOP),
        "paragraph_fields": sorted(_PARAGRAPH),
        "claim_fields": sorted(_CLAIM),
        "canonical_ids_from_provider": False,
        "engine_decode": "local_only",
        "no_service_json_loads_of_http": True,
    }


__all__ = [
    "SemanticTransportError",
    "decode_transport",
    "transport_identity",
]
