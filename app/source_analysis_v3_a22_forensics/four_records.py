"""Forensics des quatre IDEA m=[example, …]. Diagnostic only. Pas de mutation."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.models import IDEA_KINDS
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v3_a22_forensics.constants import (
    INVALID_IDEA_EXAMPLE_INDEXES,
    MODE,
    PHASE,
    SCHEMA_VERSION,
)

_NOTES = {
    30: {
        "handle": "I19",
        "label": "colonial-era tutors / shirt demand",
        "proposition": (
            "Colonial-era authorities held arbitrary coercive power analogous "
            "to the Roman-soldier backdrop of Jesus' hard sayings."
        ),
        "illustration": (
            "A tutor/colonel says 'I like that shirt' and the shirt must be given."
        ),
        "pattern": "ARGUES_FROM_X_THAT_Y",
        "collapsed_illustration_into_idea": True,
        "best_canonical_form": "IDEA claim/explanation + EXAMPLE anecdote",
        "diagnostic_class": "IDEA_WITH_COLLAPSED_ILLUSTRATION",
        "not_merely_example": (
            "The IDEA also states a historical-power proposition that supports "
            "I18/I20. EXAMPLE 108 already isolates the shirt anecdote."
        ),
    },
    38: {
        "handle": "I27",
        "label": "minister testimony turned into a formula",
        "proposition": (
            "Observing a successful minister's testimony can be wrongly turned "
            "into a rigid formula/law for others."
        ),
        "illustration": (
            "The minister's prayer, fasting, perseverance, and 'breakthrough' story."
        ),
        "pattern": "ARGUES_FROM_X_THAT_Y",
        "collapsed_illustration_into_idea": False,
        "best_canonical_form": "IDEA claim/explanation + EXAMPLE testimony",
        "diagnostic_class": "IDEA_PROPOSITION_MISLABELED_AS_EXAMPLE",
        "not_merely_example": (
            "I27.v is the teaching (do not freeze a testimony into a law), not "
            "the testimony itself. EXAMPLE 110 already holds the testimony. "
            "Metadata 'example' is the error; the record is an IDEA."
        ),
    },
    62: {
        "handle": "I51",
        "label": "pig-heart/liver transplants",
        "proposition": (
            "Powerful flesh-and-blood knowledge operates in the contemporary world."
        ),
        "illustration": "Pig hearts and livers transplanted into living humans.",
        "pattern": "ARGUES_FROM_X_THAT_Y",
        "collapsed_illustration_into_idea": True,
        "best_canonical_form": "IDEA claim/observation + EXAMPLE case_study",
        "diagnostic_class": "IDEA_WITH_COLLAPSED_ILLUSTRATION",
        "not_merely_example": (
            "The IDEA claims that flesh-and-blood revelation/knowledge is real "
            "and powerful. EXAMPLE 111 already holds the medical illustration."
        ),
    },
    64: {
        "handle": "I53",
        "label": "national leader and the economy",
        "proposition": (
            "Relevance and competence in one's assigned domain are necessary."
        ),
        "illustration": (
            "Paul Biya is recalled as always addressing the economy in public discourse."
        ),
        "pattern": "STORY_USED_TO_ILLUSTRATE_Y",
        "collapsed_illustration_into_idea": True,
        "best_canonical_form": "EXAMPLE case_study supporting I52 (already extracted)",
        "diagnostic_class": "ILLUSTRATION_EMITTED_AS_IDEA",
        "not_merely_example": (
            "I53.v is framed as illustration of I52. The proposition lives on "
            "I52. EXAMPLE 112 already isolates the Biya discourses. I53 is the "
            "clearest IDEA/EXAMPLE duplicate."
        ),
    },
}


def _records(transport: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(transport, Mapping):
        return []
    return [item for item in (transport.get("records") or []) if isinstance(item, Mapping)]


def _src_index(transcript: TranscriptInput, window: WindowInput) -> dict[str, str]:
    wanted = set(window.owned_src_refs)
    return {
        segment.src_id: segment.text
        for segment in transcript.segments
        if segment.src_id in wanted
    }


def _overlap_score(left: str, right: str) -> float:
    a = {tok for tok in left.lower().split() if len(tok) > 3}
    b = {tok for tok in right.lower().split() if len(tok) > 3}
    if not a or not b:
        return 0.0
    return round(len(a & b) / len(a | b), 3)


def audit_four_invalid_records(
    transport: Mapping[str, Any] | None,
    window: WindowInput,
    transcript: TranscriptInput,
) -> dict[str, Any]:
    records = _records(transport)
    src_index = _src_index(transcript, window)
    examples = [
        (idx, item)
        for idx, item in enumerate(records)
        if str(item.get("k") or "") == "EXAMPLE"
    ]
    rows: list[dict[str, Any]] = []
    for index in INVALID_IDEA_EXAMPLE_INDEXES:
        item = records[index] if index < len(records) else {}
        handle = str(item.get("h") or "")
        value = str(item.get("v") or "")
        refs = [str(ref) for ref in (item.get("s") or []) if isinstance(ref, str)]
        neighbors = []
        for other_idx in range(max(0, index - 3), min(len(records), index + 4)):
            other = records[other_idx]
            if str(other.get("k") or "") not in {"IDEA", "EXAMPLE", "TOPIC"}:
                continue
            neighbors.append(
                {
                    "index": other_idx,
                    "k": other.get("k"),
                    "h": other.get("h"),
                    "l": other.get("l"),
                    "v": other.get("v"),
                    "m": other.get("m"),
                }
            )
        overlapping = []
        for ex_idx, example in examples:
            score = _overlap_score(value, str(example.get("v") or ""))
            linked = handle in [str(raw) for raw in (example.get("l") or [])]
            src_overlap = sorted(
                set(refs)
                & {
                    str(ref)
                    for ref in (example.get("s") or [])
                    if isinstance(ref, str)
                }
            )
            if linked or score >= 0.15 or src_overlap:
                overlapping.append(
                    {
                        "example_index": ex_idx,
                        "example_v": example.get("v"),
                        "example_m": example.get("m"),
                        "example_l": example.get("l"),
                        "example_s": example.get("s"),
                        "links_to_this_idea": linked,
                        "value_overlap": score,
                        "shared_src": src_overlap,
                    }
                )
        note = dict(_NOTES[index])
        rows.append(
            {
                "index": index,
                "k": item.get("k"),
                "v": item.get("v"),
                "s": refs,
                "h": handle,
                "l": item.get("l"),
                "m": item.get("m"),
                "resolved_topics": item.get("l"),
                "clean_segments": [
                    {"src": ref, "text": src_index.get(ref, "")} for ref in refs
                ],
                "neighbors": neighbors,
                "overlapping_examples": overlapping,
                "duplicates_a_valid_example": bool(overlapping),
                "metadata_kind_valid": (
                    isinstance(item.get("m"), list)
                    and item["m"]
                    and item["m"][0] in IDEA_KINDS
                ),
                **note,
                "mutated": False,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "diagnostic_only": True,
        "mutated_payload": False,
        "normalized_metadata": False,
        "converted_to_example": False,
        "record_count": len(rows),
        "records": rows,
        "duplication_summary": {
            "all_four_have_a_matching_example": all(
                row["duplicates_a_valid_example"] for row in rows
            ),
            "interpretation": (
                "Claude generated both IDEA(example) and EXAMPLE for the same "
                "material. This is taxonomy confusion / duplication, not IDEA "
                "used as a fallback because EXAMPLE was missing."
            ),
        },
    }


__all__ = ["audit_four_invalid_records"]
