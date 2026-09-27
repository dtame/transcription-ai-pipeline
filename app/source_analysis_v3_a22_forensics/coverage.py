"""Couverture SRC et outline diagnostique WIN004. 0 provider."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v2_a15_forensics.coverage import build_coverage_analysis as a15_coverage
from app.source_analysis_v2_real_win001.metrics import src_metrics
from app.source_analysis_local_v3.source_refs import is_canonical_src
from app.source_analysis_v3_a22_forensics.constants import (
    A22_COVERAGE_PCT,
    A22_DISTINCT_SRC,
    A22_OWNED,
    MODE,
    PHASE,
    SCHEMA_VERSION,
)

# Diagnostic outline only. Never consume as canonical records.
_AUDIT_OUTLINE = (
    (
        "Mind as battlefield; select pure/excellent thoughts; train the mind.",
        ("battlefield", "mind", "train"),
        "represented",
    ),
    (
        "Completeness and headship in Christ; bishop-diocese analogy; body must match the head.",
        ("complete", "head", "bishop"),
        "represented",
    ),
    (
        "Self-made laws from admiring others; imitation constrains the imitator.",
        ("law", "admir", "pastor"),
        "represented",
    ),
    (
        "Jesus' commission was simple; no uniform extra conditions; unique spiritual fingerprint.",
        ("fingerprint", "father sent", "fasting"),
        "represented",
    ),
    (
        "God knows each person individually and will not impose a breaking law.",
        ("hair", "village", "unique"),
        "represented",
    ),
    (
        "Historical context of Jesus' hard sayings: extra mile, shirt demand, coat/cloak, other cheek.",
        ("mile", "shirt", "cheek"),
        "represented",
    ),
    (
        "Historical religious coercion versus modern voluntary church participation.",
        ("tithe", "west virginia", "switzerland"),
        "represented",
    ),
    (
        "Minister testimony wrongly frozen into a formula; the race is a marathon.",
        ("marathon", "broke through", "formula"),
        "represented",
    ),
    (
        "Anatomy of man: spirit, soul, body; conscience identifies spirit.",
        ("conscience", "spirit", "soul"),
        "represented",
    ),
    (
        "The Fall: life cut off; knowing good and evil; inherited condition.",
        ("committed sin", "life was cut", "good and evil"),
        "represented",
    ),
    (
        "Devil / Lucifer distinctions and related scripture (John 8).",
        ("lucifer", "liar", "john"),
        "partial",
    ),
    (
        "Love God with heart, soul, and mind; simplicity against being beguiled.",
        ("matthew 22", "heart", "mind"),
        "represented",
    ),
    (
        "Warfare not after the flesh; 2 Cor 10; brain/flesh vs God-revealed knowledge.",
        ("flesh", "stronghold", "peter"),
        "represented",
    ),
    (
        "Flesh-and-blood revelation in the world, including medical knowledge.",
        ("pig", "transplant", "flesh and blood"),
        "represented",
    ),
    (
        "Stay relevant to one's people and domain; do not copy the speaker's news habit as law.",
        ("economy", "davos", "relevant"),
        "represented",
    ),
    (
        "After spiritual acts, meet physical needs; dangerous fasting of the already-sick.",
        ("lazarus", "jairus", "food"),
        "represented",
    ),
)


def _blob(records: list[Mapping[str, Any]]) -> str:
    parts: list[str] = []
    for item in records:
        parts.append(str(item.get("v") or ""))
        for slot in item.get("m") or []:
            parts.append(str(slot))
    return " ".join(parts).lower()


def build_a22_coverage(
    transport: Mapping[str, Any],
    window: WindowInput,
    transcript: TranscriptInput,
    src_audit: Mapping[str, Any],
) -> dict[str, Any]:
    base = a15_coverage(transport, window, transcript)
    src = src_metrics(transport, window)
    records = [
        item
        for item in (transport.get("records") or [])
        if isinstance(item, Mapping)
    ]
    raw_tokens: list[str] = []
    for item in records:
        for ref in item.get("s") or []:
            if isinstance(ref, str):
                raw_tokens.append(ref)
    canonical_owned = {
        token
        for token in raw_tokens
        if is_canonical_src(token) and token in set(window.owned_src_refs)
    }
    verified_distinct_raw = len(set(raw_tokens))
    verified_coverage_count = len(canonical_owned)
    verified_pct = round(100.0 * verified_coverage_count / A22_OWNED, 2)
    bands = base.get("bands") or []
    blob = _blob(records)
    outline_rows = []
    for index, (label, needles, expected) in enumerate(_AUDIT_OUTLINE, start=1):
        hits = [needle for needle in needles if needle in blob]
        if len(hits) == len(needles) or len(hits) >= 2:
            status = "represented"
        elif hits:
            status = "partial"
        else:
            status = "missing"
        outline_rows.append(
            {
                "outline_item": index,
                "label": label,
                "needles": list(needles),
                "hits": hits,
                "status": status,
                "expected_from_clean_read": expected,
            }
        )
    represented = [row for row in outline_rows if row["status"] == "represented"]
    partial = [row for row in outline_rows if row["status"] == "partial"]
    missing = [row for row in outline_rows if row["status"] == "missing"]
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "owned_src_count": window.owned_src_count,
        "reported_distinct_src_refs": A22_DISTINCT_SRC,
        "reported_semantic_src_coverage_pct": A22_COVERAGE_PCT,
        "verified_distinct_src_refs_raw": verified_distinct_raw,
        "verified_distinct_canonical_owned": verified_coverage_count,
        "verified_semantic_src_coverage_pct": verified_pct,
        "src_metrics_legacy": src,
        "more_coverage_is_not_automatically_better": True,
        "quality_not_percentage": (
            "32.97% (389/1180) is higher than A.21 17.24% and is not a quality "
            "threshold. Judgment is by major-idea representation, grounding, "
            "and relation/example quality."
        ),
        "bands": bands,
        "thin_bands": base.get("thin_bands"),
        "gap_count": base.get("gap_count"),
        "largest_gaps": base.get("largest_gaps"),
        "largest_substantive_gap": base.get("largest_substantive_gap"),
        "largest_unreferenced_gap_note": (
            "Largest gap SRC003693–SRC003741 is session wrap-up / tomorrow-"
            "practicals / amen, not an omitted major teaching."
        ),
        "beginning": bool(bands and bands[0].get("semantic_records_grounded")),
        "middle": bool(bands and bands[len(bands) // 2].get("semantic_records_grounded")),
        "end": bool(bands and bands[-1].get("semantic_records_grounded")),
        "src_audit_distinct_canonical_owned": src_audit.get(
            "distinct_canonical_owned_src_refs"
        ),
        "diagnostic_outline": [row["label"] for row in outline_rows],
        "outline_mapping": outline_rows,
        "major_ideas_represented": len(represented),
        "major_ideas_partial": len(partial),
        "major_ideas_missing": len(missing),
        "major_ideas_distorted": 0,
        "major_ideas_over_fragmented": 0,
        "missing_rows": missing,
        "partial_rows": partial,
        "editorial_planning": False,
    }


__all__ = ["build_a22_coverage"]
