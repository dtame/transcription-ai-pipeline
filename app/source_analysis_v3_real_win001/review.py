"""Revue sémantique OFFLINE du transport V3 vs CLEAN WIN001. 0 LLM."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.source_analysis.canonical_vocabulary import RELATION_KINDS
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v3.handles import handle_kind
from app.source_analysis_v2_a15_forensics.coverage import build_coverage_analysis
from app.source_analysis_v2_a15_forensics.semantic import (
    _AUDIT_OUTLINE,
    classify_record,
)
from app.source_analysis_v3_real_win001.constants import SEMANTIC_REVIEW_STATUS
from app.source_analysis_v3_real_win001.handles import example_target_kinds
from app.source_analysis_v3_real_win001.metrics import record_metrics, src_metrics

_INTERPRETER = (
    "the interpreter",
    "l'interprète",
    "l'interprete",
    "he says that",
    "she says that",
    "il dit que",
    "elle dit que",
    "translation:",
    "traduction :",
)

_EXAMPLE_PROBES = (
    {
        "id": "daughter_meat",
        "label": "daughter / meat example",
        "needles": (("daughter", "meat"), ("fille", "viande")),
    },
    {
        "id": "grandmother_clay",
        "label": "grandmother / clay pots example",
        "needles": (("grandmother", "clay"), ("grandmother", "pot"), ("grand", "argile")),
    },
    {
        "id": "longevity_sinner",
        "label": "long-lived sinner example",
        "needles": (("sinner", "long"), ("longevity",), ("lived", "sin")),
    },
)

_OUTLINE_NEEDLES = (
    ("prayer", "timothy"),
    ("hear", "god"),
    ("couscous", "meat"),
    ("daughter", "meat"),
    ("grandmother", "clay"),
    ("longevity", "faith"),
    ("thomas", "flesh"),
    ("adam", "eve"),
    ("hebrews", "death"),
)


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


def _blob(records: list[Mapping[str, Any]]) -> str:
    return " ".join(str(item.get("v") or "") for item in records).lower()


def _match_needles(text: str, groups: tuple[tuple[str, ...], ...]) -> bool:
    low = text.lower()
    return any(all(token in low for token in group) for group in groups)


def _idea_map(records: list[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for item in records:
        if str(item.get("k") or "") != "IDEA":
            continue
        handle = item.get("h")
        if isinstance(handle, str) and handle:
            out[handle] = item
    return out


def _probe_examples(records: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    examples = [
        item for item in records if str(item.get("k") or "") == "EXAMPLE"
    ]
    for probe in _EXAMPLE_PROBES:
        hits: list[dict[str, Any]] = []
        for index, item in enumerate(records):
            if str(item.get("k") or "") != "EXAMPLE":
                continue
            value = str(item.get("v") or "")
            if not _match_needles(value, probe["needles"]):
                continue
            links = [raw for raw in (item.get("l") or []) if isinstance(raw, str)]
            hits.append(
                {
                    "index": index,
                    "value_excerpt": value[:180],
                    "links": links,
                    "target_kinds": [handle_kind(raw) for raw in links],
                    "associated_with_idea": any(
                        handle_kind(raw) == "IDEA" for raw in links
                    ),
                    "associated_with_topic": any(
                        handle_kind(raw) == "TOPIC" for raw in links
                    ),
                }
            )
        rows.append(
            {
                "id": probe["id"],
                "label": probe["label"],
                "present": bool(hits),
                "hits": hits,
                "idea_associated": all(hit["associated_with_idea"] for hit in hits)
                if hits
                else None,
                "topic_associated": any(hit["associated_with_topic"] for hit in hits)
                if hits
                else False,
            }
        )
    return rows


def _relation_quality(
    records: list[Mapping[str, Any]],
    reviewed: list[dict[str, Any]],
) -> dict[str, Any]:
    ideas = _idea_map(records)
    rows: list[dict[str, Any]] = []
    vocab_ok = 0
    plausible = 0
    loose = 0
    for index, item in enumerate(records):
        if str(item.get("k") or "") != "RELATION":
            continue
        rel = str(item.get("v") or "").strip()
        links = [raw for raw in (item.get("l") or []) if isinstance(raw, str)]
        targets = [ideas.get(raw) for raw in links]
        target_values = [
            str(target.get("v") or "") if target is not None else None
            for target in targets
        ]
        in_vocab = rel in RELATION_KINDS
        distinct = len(set(links)) == 2 and len(links) == 2
        self_target = len(links) == 2 and links[0] == links[1]
        idea_targets = all(handle_kind(raw) == "IDEA" for raw in links) and all(
            target is not None for target in targets
        )
        if in_vocab:
            vocab_ok += 1
        quality = "not_comparable"
        if idea_targets and distinct and in_vocab:
            quality = "plausible"
            plausible += 1
        elif idea_targets and in_vocab:
            quality = "loose"
            loose += 1
        reviewed_row = next((row for row in reviewed if row["index"] == index), None)
        rows.append(
            {
                "index": index,
                "type": rel,
                "links": links,
                "target_values": [value[:120] if value else None for value in target_values],
                "vocab_ok": in_vocab,
                "distinct_idea_targets": distinct,
                "self_target": self_target,
                "empty_s_by_contract": not [
                    ref for ref in (item.get("s") or []) if isinstance(ref, str) and ref
                ],
                "grounding": (reviewed_row or {}).get("status"),
                "quality": quality,
            }
        )
    if not rows:
        overall = "not_comparable"
    elif plausible >= max(1, len(rows) // 2) and loose <= len(rows) // 2:
        overall = "preserves_or_improves"
    elif loose > plausible:
        overall = "worsens_or_loose"
    else:
        overall = "preserves"
    return {
        "rows": rows,
        "vocab_ok_count": vocab_ok,
        "plausible_count": plausible,
        "loose_count": loose,
        "overall_vs_a16": overall,
        "do_not_attribute_automatically_to_handles": True,
    }


def review_transport(
    transport: Mapping[str, Any] | None,
    *,
    window: WindowInput,
    transcript: TranscriptInput,
    capacity_signal: bool,
    handle_gate_pass: bool,
    technical_ok: bool,
) -> dict[str, Any]:
    if not isinstance(transport, Mapping):
        return {
            "performed": False,
            "status": SEMANTIC_REVIEW_STATUS,
            "semantic_quality": "INADEQUATE",
            "thinking_disabled_local_extraction": "NOT_SUPPORTED",
            "unsupported_content": "not reviewed — no valid transport",
            "reason": "technical validation did not produce a transport",
        }
    records = _records(transport)
    src_index = _src_index(transcript, window)
    owned_text = " ".join(src_index.get(ref, "") for ref in window.owned_src_refs)
    reviewed = [
        classify_record(index, item, " ".join(src_index.get(ref, "") for ref in (
            [str(r).strip() for r in (item.get("s") or []) if isinstance(r, str) and str(r).strip()]
        )), owned_text)
        for index, item in enumerate(records)
    ]
    for row, item in zip(reviewed, records):
        if str(item.get("k") or "") != "RELATION":
            continue
        # Empty s[] is contractual. Evaluate via resolved IDEA targets.
        if row.get("status") == "UNDETERMINABLE_FROM_CITED_SRC":
            links = [raw for raw in (item.get("l") or []) if isinstance(raw, str)]
            idea_hits = 0
            for raw in links:
                target = next(
                    (
                        other
                        for other in records
                        if str(other.get("h") or "") == raw
                        and str(other.get("k") or "") == "IDEA"
                    ),
                    None,
                )
                if target is None:
                    continue
                target_review = next(
                    (
                        other
                        for other in reviewed
                        if other.get("index")
                        == next(
                            (
                                idx
                                for idx, rec in enumerate(records)
                                if rec is target
                            ),
                            None,
                        )
                    ),
                    None,
                )
                if target_review and target_review.get("status") in {
                    "SUPPORTED",
                    "PARTIALLY_SUPPORTED",
                }:
                    idea_hits += 1
            if idea_hits == 2:
                row["status"] = "PARTIALLY_SUPPORTED"
                row["note"] = (
                    "RELATION s[] empty by contract; both IDEA targets are "
                    "source-grounded. Not auto-unsupported."
                )
            elif idea_hits == 1:
                row["status"] = "PARTIALLY_SUPPORTED"
                row["note"] = (
                    "RELATION s[] empty by contract; one IDEA target is grounded."
                )
    counts = {
        "SUPPORTED": 0,
        "PARTIALLY_SUPPORTED": 0,
        "UNSUPPORTED": 0,
        "UNDETERMINABLE_FROM_CITED_SRC": 0,
    }
    for row in reviewed:
        status = str(row.get("status") or "UNDETERMINABLE_FROM_CITED_SRC")
        counts[status] = counts.get(status, 0) + 1
    blob = _blob(records)
    interpreter = [marker for marker in _INTERPRETER if marker in blob]
    french_kept = bool(
        re.search(
            r"(néanti|nanti|c'est pourquoi|timothée|évangile|assemblée)",
            blob,
            re.IGNORECASE,
        )
    )
    rec = record_metrics(transport)
    src = src_metrics(transport, window)
    coverage = build_coverage_analysis(transport, window, transcript)
    bands = coverage.get("bands") or []
    beginning = bool(bands and bands[0].get("semantic_records_grounded"))
    middle = bool(bands and bands[len(bands) // 2].get("semantic_records_grounded"))
    end = bool(bands and bands[-1].get("semantic_records_grounded"))
    outline_hits = []
    for index, needles in enumerate(_OUTLINE_NEEDLES, start=1):
        outline_hits.append(
            {
                "outline_item": index,
                "needles": list(needles),
                "represented": all(token in blob for token in needles)
                or any(token in blob for token in needles),
            }
        )
    example_probes = _probe_examples(records)
    example_rows = example_target_kinds(transport)
    stretched_examples = [
        row
        for row in example_rows
        if row.get("links_to_topic")
    ]
    relations = _relation_quality(records, reviewed)
    material_unsupported = counts["UNSUPPORTED"]
    quality = "ACCEPTABLE_FOR_LOCAL_EXTRACTION"
    thinking = (
        "SUPPORTED_BY_TWO_REAL_WIN001 OBSERVATIONS "
        "(A.15 semantic-content forensic evidence + A.19 valid V3 evidence; "
        "ONE source window analyzed twice, not two independent windows)"
    )
    reasons: list[str] = []
    if not technical_ok or capacity_signal or not handle_gate_pass:
        quality = "INADEQUATE"
        thinking = "NOT_SUPPORTED"
        reasons.append("technical V3 gate failed")
    if rec["IDEA"] < 3:
        quality = "INADEQUATE"
        thinking = "NOT_SUPPORTED"
        reasons.append("too few ideas for WIN001")
    if material_unsupported:
        quality = "INADEQUATE"
        thinking = "NOT_SUPPORTED"
        reasons.append("material unsupported content")
    if not (beginning and middle and end):
        if quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION":
            quality = "REVIEW_REQUIRED"
            thinking = "REVIEW_REQUIRED"
        reasons.append("beginning/middle/end coverage incomplete")
    if interpreter:
        if quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION":
            quality = "REVIEW_REQUIRED"
            thinking = "REVIEW_REQUIRED"
        reasons.append("possible interpreter material")
    if any(probe.get("topic_associated") for probe in example_probes):
        if quality != "INADEQUATE":
            quality = "REVIEW_REQUIRED"
            thinking = "REVIEW_REQUIRED"
        reasons.append("analogous example still associated with TOPIC handle")
    outline_represented = sum(1 for row in outline_hits if row["represented"])
    if outline_represented < 5 and rec["IDEA"] >= 3:
        if quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION":
            quality = "REVIEW_REQUIRED"
            thinking = "REVIEW_REQUIRED"
        reasons.append("major-idea outline weakly represented")
    return {
        "performed": True,
        "status": SEMANTIC_REVIEW_STATUS,
        "validated_result": technical_ok and quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION",
        "response_repaired": False,
        "source_refs_substituted": False,
        "external_fact_check": False,
        "second_llm": False,
        "semantic_quality": quality,
        "thinking_disabled_local_extraction": thinking,
        "unsupported_content": material_unsupported,
        "unsupported_count": material_unsupported,
        "grounding_counts": counts,
        "records_reviewed": len(reviewed),
        "records": reviewed,
        "record_metrics": rec,
        "src_metrics": src,
        "coverage": {
            "distinct_src_refs": src.get("distinct_srcs_referenced"),
            "semantic_src_coverage_pct": src.get("semantic_src_coverage_pct"),
            "bands": bands,
            "largest_substantive_gap": coverage.get("largest_substantive_gap"),
            "beginning": beginning,
            "middle": middle,
            "end": end,
            "appears_spatially_complete": beginning and middle and end,
        },
        "major_idea_coverage": {
            "outline_status": "DIAGNOSTIC_ONLY",
            "never_consume_as_canonical": True,
            "outline": list(_AUDIT_OUTLINE),
            "hits": outline_hits,
            "represented_count": outline_represented,
        },
        "example_probes": example_probes,
        "example_targets": example_rows,
        "stretched_or_topic_examples": stretched_examples,
        "relations": relations,
        "language": {
            "primary": transcript.primary_language,
            "legitimate_french_may_remain": True,
            "french_markers_in_values": french_kept,
            "interpreter_markers_in_values": interpreter,
            "removed_interpreter_translations_reconstructed": False,
            "english_primary_represented": True,
        },
        "do_not_generalize": True,
        "editorial_quality_evaluated": False,
        "reasons": reasons,
        "notes": (
            "Deterministic forensic review against exact CLEAN WIN001. "
            "RELATION s[] empty is contractual. Not a second model call."
        ),
    }


__all__ = ["review_transport"]
