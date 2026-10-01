"""Correspondance SRC007337 ↔ record WIN007. Lecture CLEAN uniquement."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v3.source_refs import is_canonical_src
from app.source_analysis_v31_src_typo_forensics.constants import (
    EXPECTED_CANONICAL,
    MALFORMED_TOKEN,
    MODE,
    NUMERIC_PAYLOAD,
    PHASE,
    SCHEMA_VERSION,
    WINDOW_ID,
)

_WORD = re.compile(r"[A-Za-zÀ-ÿ']{3,}")


def _words(text: str) -> set[str]:
    return {match.group(0).casefold() for match in _WORD.finditer(text or "")}


def _segment_map(transcript: TranscriptInput) -> dict[str, Any]:
    return {segment.src_id: segment for segment in transcript.segments}


def numeric_owned_in_window(window: WindowInput) -> dict[str, Any]:
    candidate = EXPECTED_CANONICAL
    owned = set(window.owned_src_refs)
    first = window.owned_src_refs[0] if window.owned_src_refs else None
    last = window.owned_src_refs[-1] if window.owned_src_refs else None
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "window_id": WINDOW_ID,
        "numeric_payload": NUMERIC_PAYLOAD,
        "canonical_candidate": candidate,
        "owned_by_win007": candidate in owned,
        "first_owned": first,
        "last_owned": last,
        "owned_src_count": window.owned_src_count,
        "in_range": bool(
            first
            and last
            and first <= candidate <= last
        ),
    }


def compare_record_to_source(
    record_text: str,
    source_text: str,
) -> dict[str, Any]:
    rec = _words(record_text)
    src = _words(source_text)
    shared = sorted(rec & src)
    recall = (len(rec & src) / len(src)) if src else 0.0
    precision = (len(rec & src) / len(rec)) if rec else 0.0
    return {
        "shared_content_words": shared[:40],
        "shared_count": len(shared),
        "record_content_words": len(rec),
        "source_content_words": len(src),
        "recall": round(recall, 4),
        "precision": round(precision, 4),
    }


def neighborhood_check(
    transcript: TranscriptInput,
    window: WindowInput,
    record_text: str,
    *,
    radius: int = 3,
) -> dict[str, Any]:
    segments = _segment_map(transcript)
    owned = list(window.owned_src_refs)
    try:
        index = owned.index(EXPECTED_CANONICAL)
    except ValueError:
        index = -1
    neighbors: list[dict[str, Any]] = []
    if index >= 0:
        start = max(0, index - radius)
        end = min(len(owned), index + radius + 1)
        for src_id in owned[start:end]:
            segment = segments.get(src_id)
            text = segment.text if segment is not None else ""
            cmp = compare_record_to_source(record_text, text)
            neighbors.append(
                {
                    "src_id": src_id,
                    "is_canonical_candidate": src_id == EXPECTED_CANONICAL,
                    "text": text,
                    "word_count": len(text.split()) if text else 0,
                    **cmp,
                }
            )
    ranked = sorted(
        neighbors, key=lambda row: (row["shared_count"], row["recall"]), reverse=True
    )
    best = ranked[0]["src_id"] if ranked else None
    unique_best = bool(ranked) and (
        len(ranked) == 1 or ranked[0]["shared_count"] > ranked[1]["shared_count"]
    )
    return {
        "radius": radius,
        "neighbors": neighbors,
        "best_overlap_src": best,
        "unique_best_overlap": unique_best,
        "other_plausible_neighbor": bool(
            ranked
            and ranked[0]["src_id"] != EXPECTED_CANONICAL
            and ranked[0]["shared_count"] >= 3
        ),
    }


def intended_source_analysis(
    *,
    window: WindowInput,
    transcript: TranscriptInput,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    ownership = numeric_owned_in_window(window)
    segments = _segment_map(transcript)
    source = segments.get(EXPECTED_CANONICAL)
    source_text = source.text if source is not None else ""
    record_text = str(record.get("v") or "")
    comparison = compare_record_to_source(record_text, source_text)
    neighborhood = neighborhood_check(transcript, window, record_text)
    other_refs = [
        token
        for token in (record.get("s") or [])
        if isinstance(token, str) and is_canonical_src(token)
    ]
    uncited_neighbors = [
        row
        for row in neighborhood.get("neighbors") or []
        if row["src_id"] != EXPECTED_CANONICAL and row["src_id"] not in other_refs
    ]
    better_uncited = [
        row
        for row in uncited_neighbors
        if row["shared_count"] > comparison["shared_count"]
    ]
    sandwich = False
    if other_refs and ownership["owned_by_win007"]:
        sandwich = any(ref < EXPECTED_CANONICAL for ref in other_refs) and any(
            ref > EXPECTED_CANONICAL for ref in other_refs
        )
    intended = "AMBIGUOUS"
    if not ownership["owned_by_win007"] or source is None:
        intended = "NOT_INTENDED_SOURCE"
    elif better_uncited:
        intended = "AMBIGUOUS"
    elif comparison["shared_count"] == 0 and not sandwich:
        intended = "NOT_INTENDED_SOURCE"
    elif (
        neighborhood["best_overlap_src"] == EXPECTED_CANONICAL
        and comparison["shared_count"] >= 1
        and not better_uncited
        and (sandwich or comparison["shared_count"] >= 3)
    ):
        intended = "EXACT_INTENDED_SOURCE"
    elif comparison["shared_count"] >= 1 and not better_uncited:
        intended = "PLAUSIBLE_INTENDED_SOURCE"
    neighborhood["other_cited_canonical_refs"] = other_refs
    neighborhood["sequential_sandwich"] = sandwich
    neighborhood["better_uncited_neighbor"] = [row["src_id"] for row in better_uncited]
    neighborhood["digits_alone_insufficient"] = True
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "malformed_token": MALFORMED_TOKEN,
        "canonical_candidate": EXPECTED_CANONICAL,
        "numeric_owned": ownership,
        "record_kind": str(record.get("k") or ""),
        "record_handle": record.get("h"),
        "record_text": record_text,
        "source_text": source_text,
        "source_present": source is not None,
        "comparison": comparison,
        "neighborhood": neighborhood,
        "intended_source_class": intended,
        "digits_do_not_alone_prove_intent": True,
        "external_knowledge_used": False,
        "second_llm_used": False,
    }


__all__ = [
    "intended_source_analysis",
    "neighborhood_check",
    "numeric_owned_in_window",
]
