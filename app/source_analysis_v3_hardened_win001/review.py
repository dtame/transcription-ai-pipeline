"""Revue sémantique OFFLINE du transport V3 vs CLEAN WIN001. 0 LLM."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v3_hardened_win001.constants import (
    SEMANTIC_REVIEW_INVALID,
    SEMANTIC_REVIEW_STATUS,
)
from app.source_analysis_v3_real_win001.review import (
    _EXAMPLE_PROBES,
    _OUTLINE_NEEDLES,
    _blob,
    _match_needles,
    review_transport as review_a19_transport,
)

_A21_PROBES = _EXAMPLE_PROBES + (
    {
        "id": "land_grant",
        "label": "land-grant example",
        "needles": (("land", "grant"), ("concession", "terre"), ("land grant",)),
    },
    {
        "id": "early_relation_concepts",
        "label": "early relation concepts",
        "needles": (("relation",), ("supports",), ("because",), ("therefore",)),
    },
)


def review_transport(
    transport: Mapping[str, Any] | None,
    *,
    window: WindowInput,
    transcript: TranscriptInput,
    capacity_signal: bool,
    handle_gate_pass: bool,
    technical_ok: bool,
) -> dict[str, Any]:
    base = review_a19_transport(
        transport,
        window=window,
        transcript=transcript,
        capacity_signal=capacity_signal,
        handle_gate_pass=handle_gate_pass,
        technical_ok=technical_ok,
    )
    records = [
        item
        for item in ((transport or {}).get("records") or [])
        if isinstance(item, Mapping)
    ]
    blob = _blob(records)
    extra_probes = []
    for probe in _A21_PROBES:
        extra_probes.append(
            {
                "id": probe["id"],
                "label": probe["label"],
                "present": _match_needles(blob, probe["needles"]),
            }
        )
    quality = base.get("semantic_quality")
    if technical_ok and quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION":
        thinking = "SUPPORTED_ON_WIN001"
        thinking_note = (
            "Multiple runs of the SAME source window, not independent windows. "
            "Do not generalize to WIN002–WIN007, other transcripts, languages, "
            "or domains."
        )
        status = SEMANTIC_REVIEW_STATUS
        transport_valid = True
    else:
        thinking = base.get("thinking_disabled_local_extraction")
        thinking_note = (
            "Thinking-disabled local extraction is not confirmed for A.21 "
            "because the technical or semantic gate did not fully pass."
        )
        status = SEMANTIC_REVIEW_STATUS if technical_ok else SEMANTIC_REVIEW_INVALID
        transport_valid = bool(technical_ok)
    merged = dict(base)
    merged.update(
        {
            "status": status,
            "transport_valid": transport_valid,
            "known_content_checks": extra_probes,
            "thinking_disabled_local_extraction": thinking,
            "thinking_disabled_limitation": thinking_note,
            "do_not_generalize": True,
            "generalization_forbidden": (
                "WIN002–WIN007, other transcripts, other languages, other domains"
            ),
        }
    )
    return merged


__all__ = ["review_transport"]
