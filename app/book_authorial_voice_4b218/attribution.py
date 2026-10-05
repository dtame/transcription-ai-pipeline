"""SRC-backed attribution evidence. AUDIO ids are not speakers."""

from __future__ import annotations

import re
from typing import Any

from app.book_authorial_voice_4b218.chapter_io import iter_paragraphs
from app.book_authorial_voice_4b218.constants import PHASE, TARGET_CHAPTER_ID
from app.book_generation.hydrate import load_clean_transcript_index
from app.book_generation.identity import load_production_inputs
from app.book_authorial_voice_4b218.constants import PROJECT_NAME

_FIRST_PERSON_FR = re.compile(
    r"\b(je|j'|moi|mon|ma|mes|nous|notre|nos)\b",
    re.IGNORECASE,
)
_FIRST_PERSON_EN = re.compile(r"\b(i|me|my|we|our|myself)\b", re.IGNORECASE)


def _segment_fields(segment) -> list[str]:
    return [
        name
        for name in ("src_id", "source_id", "start", "end", "text", "source_order")
        if hasattr(segment, name)
    ]


def collect_attribution_evidence(
    chapter: dict[str, Any],
    *,
    transcript_index=None,
    source_map=None,
) -> dict[str, Any]:
    if transcript_index is None:
        transcript_index = load_clean_transcript_index(PROJECT_NAME)
    if source_map is None:
        source_map = load_production_inputs(PROJECT_NAME).source_map
    lookup = transcript_index.by_src()
    sample = transcript_index.segments[0] if transcript_index.segments else None
    rows: list[dict[str, Any]] = []
    for paragraph_id, paragraph in iter_paragraphs(chapter):
        src_rows = []
        for src_id in paragraph["source_refs"]:
            segment = lookup.get(src_id)
            text = segment.text if segment is not None else ""
            src_rows.append(
                {
                    "src_id": src_id,
                    "recording_id": getattr(segment, "source_id", None),
                    "text": text,
                    "speaker_field": None,
                    "first_person_fr": sorted(
                        set(match.group(1).lower() for match in _FIRST_PERSON_FR.finditer(text))
                    ),
                    "first_person_en": sorted(
                        set(match.group(1).lower() for match in _FIRST_PERSON_EN.finditer(text))
                    ),
                }
            )
        rows.append(
            {
                "paragraph_id": paragraph_id,
                "section_id": paragraph["section_id"],
                "source_refs": paragraph["source_refs"],
                "segments": src_rows,
                "recording_ids": sorted(
                    {
                        item["recording_id"]
                        for item in src_rows
                        if item["recording_id"]
                    }
                ),
            }
        )
    ideas = {
        item.idea_id: {
            "id": item.idea_id,
            "summary": item.summary,
            "source_refs": list(item.source_refs),
        }
        for item in source_map.ideas
    }
    examples = {
        item.example_id: {
            "id": item.example_id,
            "summary": item.summary,
            "kind": item.kind,
            "supports_idea_refs": list(item.supports_idea_refs),
            "source_refs": list(item.source_refs),
        }
        for item in source_map.examples
    }
    return {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "speaker_field_present_on_segments": hasattr(sample, "speaker") if sample else False,
        "segment_fields": _segment_fields(sample) if sample else [],
        "recording_ids_are_not_speakers": True,
        "recording_ids": sorted({seg.source_id for seg in transcript_index.segments}),
        "paragraphs": rows,
        "supporting_units": {
            "IDEA184": ideas.get("IDEA184"),
            "IDEA186": ideas.get("IDEA186"),
            "IDEA238": ideas.get("IDEA238"),
            "EX030": examples.get("EX030"),
        },
        "established_authorial_first_person": {
            "P000003": [
                "SRC004918 Nous étions sincères",
                "SRC004920 nous étions très sincères",
                "SRC004921 C'est parce que nous ne savions pas",
                "SRC004923 nous ne connaissons pas",
            ],
            "P000008": [
                "SRC004891 Il a vu comment j'ai prié",
                "SRC004893 J'étais au sol",
                "SRC004895 Ma voix était cassée",
            ],
            "P000009": [
                "SRC004898 il m'a dit mon fils",
                "SRC004899 tu es fatigué",
                "SRC004905 Parce que si je te laisse ainsi",
                "SRC004906 tu vas prêcher une mauvaise doctrine",
            ],
        },
        "uncertain_attribution": {
            "P000001": [
                "SRC004846 Tu viens juste d'exercer le bavardage",
                "SRC004850 Nous sommes tellement fatigués",
                "SRC004851 Nous prions toute la nuit en langue",
            ],
        },
        "secrets_included": False,
    }


__all__ = ["collect_attribution_evidence"]
