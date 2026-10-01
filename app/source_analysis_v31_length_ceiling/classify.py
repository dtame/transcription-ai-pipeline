"""Classification forensique des 3 valeurs WIN003. Pas de réparation."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v2_a15_forensics.semantic import classify_record
from app.source_analysis_v31_length_ceiling.constants import (
    MODE,
    PHASE,
    SCHEMA_VERSION,
)


def _cited_text(transcript: TranscriptInput, refs: list[str]) -> str:
    wanted = set(refs)
    parts = [
        segment.text
        for segment in transcript.segments
        if segment.src_id in wanted
    ]
    return " ".join(parts)


def _independent_clauses(text: str) -> list[str]:
    pieces: list[str] = []
    for chunk in text.replace(";", ".").split("."):
        cleaned = chunk.strip()
        if cleaned:
            pieces.append(cleaned)
    return pieces


def classify_theme(value: str, *, owned_text: str) -> dict[str, Any]:
    clauses = _independent_clauses(value)
    john17 = "john 17" in value.lower() or "high priestly" in value.lower()
    rapture = "rapture" in value.lower()
    identity = "identity" in value.lower() or "indwelling" in value.lower()
    themes_named = sum(bool(flag) for flag in (john17, rapture, identity))
    supported = john17 and "john 17" in owned_text.lower()
    rapture_supported = rapture and "rapture" in owned_text.lower()
    return {
        "classification": "MULTIPLE_IDEAS_COLLAPSED",
        "secondary": "NECESSARY_LENGTH",
        "reason": (
            "Window theme concatenates three distinct teaching clusters "
            f"({themes_named} named) with semicolons. A window-level theme "
            "may legitimately need a different bound than a single IDEA.v. "
            "Compressible by dropping one cluster, but not clearly verbose "
            "as a window summary."
        ),
        "clause_count": len(clauses),
        "theme_clusters": themes_named,
        "should_share_record_value_ceiling": False,
        "grounding": "fully supported" if supported and rapture_supported else "partially supported",
        "chars": len(value),
        "value": value,
    }


def classify_idea(
    value: str,
    *,
    cited: str,
    owned_text: str,
    record: Mapping[str, Any],
    index: int,
) -> dict[str, Any]:
    clauses = _independent_clauses(value)
    and_joins = value.count(" and ")
    collapsed = len(clauses) >= 2 or (and_joins >= 2 and len(value) > 180)
    row = classify_record(index, record, cited, owned_text)
    grounding = str(row.get("status") or "UNDETERMINABLE")
    mapped = {
        "SUPPORTED": "fully supported",
        "PARTIALLY_SUPPORTED": "partially supported",
        "UNSUPPORTED": "unsupported",
    }.get(grounding, "unsupported")
    if collapsed:
        classification = "MULTIPLE_IDEAS_COLLAPSED"
        reason = (
            "The 209-character IDEA joins more than one proposition "
            "(clause/conjunction structure). Raising a universal 200 ceiling "
            "would hide an extraction-granularity issue if treated as one IDEA. "
            "Production IDEA.v is already 280, so this value is currently legal."
        )
    else:
        classification = "NECESSARY_LENGTH"
        reason = (
            "One coherent proposition whose wording is slightly long. "
            "Already legal under production IDEA.v=280."
        )
    return {
        "classification": classification,
        "secondary": "REASONABLY_COMPRESSIBLE",
        "reason": reason,
        "clause_count": len(clauses),
        "and_joins": and_joins,
        "one_coherent_proposition": not collapsed,
        "grounding": mapped,
        "grounding_status": grounding,
        "chars": len(value),
        "value": value,
        "cited_excerpt": cited[:400],
    }


def classify_example(
    value: str,
    *,
    cited: str,
    owned_text: str,
    record: Mapping[str, Any],
    index: int,
) -> dict[str, Any]:
    row = classify_record(index, record, cited, owned_text)
    grounding = str(row.get("status") or "UNDETERMINABLE")
    mapped = {
        "SUPPORTED": "fully supported",
        "PARTIALLY_SUPPORTED": "partially supported",
        "UNSUPPORTED": "unsupported",
    }.get(grounding, "unsupported")
    return {
        "classification": "NECESSARY_LENGTH",
        "secondary": "REASONABLY_COMPRESSIBLE",
        "reason": (
            "One sentence names the Nigeria village-deliverance illustration "
            "and the reason the story exists (villagers asked him to destroy "
            "idols / higher anointing / no local backlash). That motive is "
            "the illustration's point, not decorative detail. 213 characters "
            "is 13 over EXAMPLE.v=200 but is not a transcript dump."
        ),
        "concise_necessary_description": True,
        "unnecessarily_detailed": False,
        "grounding": mapped,
        "grounding_status": grounding,
        "chars": len(value),
        "value": value,
        "cited_excerpt": cited[:400],
    }


def classify_offenders(
    offenders: Mapping[str, Mapping[str, Any]],
    *,
    window: WindowInput,
    transcript: TranscriptInput,
    transport: Mapping[str, Any],
) -> dict[str, Any]:
    owned = {
        segment.src_id: segment.text
        for segment in transcript.segments
        if segment.src_id in set(window.owned_src_refs)
    }
    owned_text = " ".join(owned.values())
    records = list(transport.get("records") or [])
    theme = classify_theme(str(offenders["theme"]["value"]), owned_text=owned_text)
    idea_rec = records[int(offenders["idea"]["index"])]
    example_rec = records[int(offenders["example"]["index"])]
    idea = classify_idea(
        str(offenders["idea"]["value"]),
        cited=_cited_text(transcript, list(offenders["idea"].get("source_refs") or [])),
        owned_text=owned_text,
        record=idea_rec,
        index=int(offenders["idea"]["index"]),
    )
    example = classify_example(
        str(offenders["example"]["value"]),
        cited=_cited_text(transcript, list(offenders["example"].get("source_refs") or [])),
        owned_text=owned_text,
        record=example_rec,
        index=int(offenders["example"]["index"]),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "repaired": False,
        "theme": theme,
        "idea": idea,
        "example": example,
        "theme_should_share_record_ceiling": False,
        "idea_already_legal_under_280": not bool(offenders["idea"]["exceeds_production"]),
        "production_failures": ["theme", "EXAMPLE.v"],
        "a28_inventory_extra": ["IDEA.v vs assumed 200"],
    }


__all__ = ["classify_offenders"]
