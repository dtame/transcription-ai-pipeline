"""Audit des frontières techniques et de la continuité thématique. Diagnostique only."""

from __future__ import annotations

from typing import Any, Mapping

from app.language_cleanup.transcript_source import (
    load_audit_transcript,
    transcript_data_file,
)
from app.source_analysis_v31_global_preflight.constants import (
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    WINDOW_IS_NOT_CHAPTER,
    WINDOW_IS_NOT_EDITORIAL_UNIT,
    WINDOW_IS_NOT_SECTION,
    WINDOW_SPECS,
)
from app.source_analysis_v31_global_preflight.normalize import src_number

BOUNDARIES = (
    ("WIN001", "WIN002"),
    ("WIN002", "WIN003"),
    ("WIN003", "WIN004"),
    ("WIN004", "WIN005"),
    ("WIN005", "WIN006"),
    ("WIN006", "WIN007"),
)
NEAR_SRC = 8
NEAR_RECORDS = 6


def _tokens(text: str) -> set[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in text)
    return {part for part in cleaned.split() if len(part) >= 5}


def _nearby_records(records: list[Mapping[str, Any]], *, side: str) -> list[dict[str, Any]]:
    scored: list[tuple[int, Mapping[str, Any]]] = []
    for item in records:
        nums = [src_number(ref) for ref in item.get("source_refs") or []]
        nums = [num for num in nums if num is not None]
        if not nums:
            continue
        key = max(nums) if side == "left" else min(nums)
        scored.append((key, item))
    scored.sort(key=lambda pair: pair[0], reverse=(side == "left"))
    out = []
    for _, item in scored[:NEAR_RECORDS]:
        if item.get("kind") in {"IDEA", "TOPIC"}:
            out.append(
                {
                    "input_id": item.get("input_id"),
                    "kind": item.get("kind"),
                    "value": item.get("value"),
                    "source_refs": list(item.get("source_refs") or []),
                }
            )
    return out


def _continuity(left_records: list[dict[str, Any]], right_records: list[dict[str, Any]]) -> str:
    left_tokens: set[str] = set()
    right_tokens: set[str] = set()
    for item in left_records:
        left_tokens |= _tokens(str(item.get("value") or ""))
    for item in right_records:
        right_tokens |= _tokens(str(item.get("value") or ""))
    if not left_tokens or not right_tokens:
        return "NONE"
    shared = left_tokens & right_tokens
    ratio = len(shared) / max(1, min(len(left_tokens), len(right_tokens)))
    if ratio >= 0.28 or len(shared) >= 8:
        return "HIGH"
    if ratio >= 0.16 or len(shared) >= 4:
        return "MODERATE"
    if shared:
        return "LOW"
    return "NONE"


def _excerpt(transcript, src_id: str) -> dict[str, Any] | None:
    for segment in transcript.segments:
        if segment.src_id == src_id:
            text = segment.text or ""
            return {
                "src_id": src_id,
                "text": text[:240],
                "word_count": len(text.split()),
            }
    return None


def _ownership_violations(normalized: Mapping[str, Any]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for window_id, row in (normalized.get("windows") or {}).items():
        first, last = row.get("owned_src_range") or (0, 0)
        for item in row.get("records") or []:
            kind = item.get("kind")
            if kind == "RELATION":
                continue
            for ref in item.get("source_refs") or []:
                number = src_number(ref)
                if number is None:
                    violations.append(
                        {
                            "window_id": window_id,
                            "input_id": item.get("input_id"),
                            "kind": kind,
                            "src": ref,
                            "reason": "noncanonical_or_unparseable",
                        }
                    )
                    continue
                if number < int(first) or number > int(last):
                    violations.append(
                        {
                            "window_id": window_id,
                            "input_id": item.get("input_id"),
                            "kind": kind,
                            "src": ref,
                            "reason": "cross_window_or_unowned",
                            "owned": [first, last],
                        }
                    )
    return violations


def build_boundary_audit(
    normalized: Mapping[str, Any],
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Any = None,
) -> dict[str, Any]:
    transcript = load_audit_transcript(
        transcript_data_file(project_name, sortie_dir=sortie_dir),
        project_name=project_name,
    )
    windows = normalized.get("windows") or {}
    boundaries: list[dict[str, Any]] = []
    for left_id, right_id in BOUNDARIES:
        left_spec = WINDOW_SPECS[left_id]
        right_spec = WINDOW_SPECS[right_id]
        left_last = str(left_spec["last_owned_src"])
        right_first = str(right_spec["first_owned_src"])
        left_records = list((windows.get(left_id) or {}).get("records") or [])
        right_records = list((windows.get(right_id) or {}).get("records") or [])
        left_near = _nearby_records(left_records, side="left")
        right_near = _nearby_records(right_records, side="right")
        continuity = _continuity(left_near, right_near)
        boundaries.append(
            {
                "boundary": f"{left_id}→{right_id}",
                "left_last_owned": left_last,
                "right_first_owned": right_first,
                "contiguous": src_number(right_first) == (src_number(left_last) or 0) + 1,
                "left_source_excerpt": _excerpt(transcript, left_last),
                "right_source_excerpt": _excerpt(transcript, right_first),
                "left_nearby_records": left_near,
                "right_nearby_records": right_near,
                "continuity": continuity,
                "diagnostic_only": True,
            }
        )
    violations = _ownership_violations(normalized)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "window_invariant": {
            "WINDOW_NE_CHAPTER": WINDOW_IS_NOT_CHAPTER,
            "WINDOW_NE_SECTION": WINDOW_IS_NOT_SECTION,
            "WINDOW_NE_EDITORIAL_UNIT": WINDOW_IS_NOT_EDITORIAL_UNIT,
            "consolidator_must_not_preserve_windows_as_book_structure": True,
        },
        "cross_window_src_violations": violations,
        "cross_window_src_violation_count": len(violations),
        "expected_violations": 0,
        "ownership_pass": len(violations) == 0,
        "boundaries": boundaries,
        "continuity_summary": {
            item["boundary"]: item["continuity"] for item in boundaries
        },
    }


__all__ = ["build_boundary_audit"]
