"""Revue sémantique OFFLINE du transport V2 vs CLEAN WIN001. 0 LLM."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.source_analysis.canonical_vocabulary import RELATION_KINDS
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v2_real_win001.metrics import (
    link_metrics,
    record_metrics,
    src_metrics,
)

_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "that",
        "this",
        "it",
        "is",
        "are",
        "was",
        "were",
        "be",
        "as",
        "by",
        "from",
        "at",
        "we",
        "you",
        "he",
        "she",
        "they",
        "not",
        "but",
        "if",
        "so",
        "our",
        "his",
        "her",
        "their",
        "les",
        "des",
        "une",
        "que",
        "qui",
        "dans",
        "pour",
        "avec",
        "est",
        "pas",
        "nous",
        "vous",
        "ils",
    }
)
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
_BIBLE = re.compile(
    r"\b(?:genesis|exodus|leviticus|numbers|deuteronomy|psalm|psalms|"
    r"proverbs|isaiah|jeremiah|matthew|mark|luke|john|acts|romans|"
    r"corinthians|galatians|ephesians|philippians|colossians|"
    r"thessalonians|timothy|titus|hebrews|james|peter|jude|revelation|"
    r"genèse|exode|lévitique|nombres|deutéronome|psaume|proverbes|"
    r"matthieu|marc|luc|jean|actes|romains|corinthiens|galates|"
    r"éphésiens|philippiens|hébreux|jacques|pierre|apocalypse)"
    r"(?:\s+\d+(?::\d+(?:-\d+)?)?)?",
    re.IGNORECASE,
)


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-zÀ-ÿ']{3,}", text.lower())
        if token not in _STOP
    }


def _src_index(transcript: TranscriptInput, window: WindowInput) -> dict[str, str]:
    wanted = set(window.owned_src_refs)
    return {
        segment.src_id: segment.text
        for segment in transcript.segments
        if segment.src_id in wanted
    }


def _cited_text(item: Mapping[str, Any], src_index: Mapping[str, str]) -> str:
    refs = [
        str(ref).strip()
        for ref in (item.get("s") or [])
        if isinstance(ref, str) and str(ref).strip()
    ]
    return " ".join(src_index.get(ref, "") for ref in refs)


def review_transport(
    transport: Mapping[str, Any] | None,
    *,
    window: WindowInput,
    transcript: TranscriptInput,
    capacity_signal: bool,
    links_valid: bool,
) -> dict[str, Any]:
    if not isinstance(transport, Mapping):
        return {
            "performed": False,
            "semantic_quality": "INADEQUATE",
            "thinking_disabled_local_extraction": "NOT_SUPPORTED",
            "unsupported_content": "not reviewed — no valid transport",
            "reason": "technical validation did not produce a transport",
        }
    src_index = _src_index(transcript, window)
    owned_text = " ".join(src_index.get(ref, "") for ref in window.owned_src_refs)
    owned_tokens = _tokens(owned_text)
    records = [item for item in (transport.get("records") or []) if isinstance(item, Mapping)]
    unsupported: list[dict[str, Any]] = []
    invented_refs: list[dict[str, Any]] = []
    sample: list[dict[str, Any]] = []
    idea_src_counts: list[int] = []
    for index, item in enumerate(records):
        kind = str(item.get("k") or "")
        value = str(item.get("v") or "")
        cited = _cited_text(item, src_index)
        tokens = _tokens(value)
        cited_tokens = _tokens(cited)
        overlap = tokens & cited_tokens
        ratio = (len(overlap) / len(tokens)) if tokens else 1.0
        row = {
            "index": index,
            "kind": kind,
            "value_excerpt": value[:180],
            "src_refs": [
                str(ref).strip()
                for ref in (item.get("s") or [])
                if isinstance(ref, str)
            ],
            "support_ratio": round(ratio, 3),
            "overlap_tokens": sorted(list(overlap))[:12],
        }
        if index < 12 or ratio < 0.25 or kind in {"REFERENCE", "UNCERTAINTY"}:
            sample.append(row)
        if kind in {"TOPIC", "IDEA", "EXAMPLE", "REFERENCE"} and tokens and ratio < 0.2:
            unsupported.append(row)
        if kind == "IDEA":
            idea_src_counts.append(len(row["src_refs"]))
        if kind == "REFERENCE":
            matches = [match.group(0) for match in _BIBLE.finditer(value)]
            for match in matches:
                if match.lower() not in cited.lower() and match.lower() not in owned_text.lower():
                    invented_refs.append(
                        {"index": index, "value_excerpt": value[:180], "citation": match}
                    )
    relation_issues: list[str] = []
    for index, item in enumerate(records):
        if str(item.get("k") or "") != "RELATION":
            continue
        rel_type = str(item.get("v") or "").strip()
        if rel_type and rel_type not in RELATION_KINDS:
            relation_issues.append(f"records[{index}] type {rel_type!r} not in vocabulary")
    interpreter_hits = [
        marker
        for marker in _INTERPRETER
        if marker in " ".join(str(item.get("v") or "") for item in records).lower()
    ]
    records_blob = " ".join(str(item.get("v") or "") for item in records)
    idea_tokens = _tokens(
        " ".join(
            str(item.get("v") or "")
            for item in records
            if str(item.get("k") or "") == "IDEA"
        )
    )
    probe = []
    owned_refs = list(window.owned_src_refs)
    for position in (0, len(owned_refs) // 2, max(0, len(owned_refs) - 1)):
        if not owned_refs:
            break
        src = owned_refs[position]
        text = src_index.get(src, "")
        tokens = [token for token in _tokens(text) if token in owned_tokens]
        hit = bool(set(tokens) & idea_tokens) if tokens else True
        probe.append({"src": src, "represented": hit, "sample": text[:120]})
    omitted_probes = [row for row in probe if not row["represented"]]
    rec = record_metrics(transport)
    src = src_metrics(transport, window)
    links = link_metrics(transport)
    single_src_ideas = sum(1 for count in idea_src_counts if count == 1)
    grouping = "reasonable"
    if rec["IDEA"] == 0:
        grouping = "missing"
    elif rec["IDEA"] >= window.owned_src_count * 0.8:
        grouping = "too_fine_one_idea_per_src_risk"
    elif rec["IDEA"] <= 2 and window.owned_src_count > 100:
        grouping = "too_coarse"
    elif idea_src_counts and (sum(idea_src_counts) / len(idea_src_counts)) >= 3:
        grouping = "grouped"
    material_unsupported = len(unsupported) + len(invented_refs)
    quality = "ACCEPTABLE_FOR_LOCAL_EXTRACTION"
    thinking = "SUPPORTED_BY_ONE_REAL_WINDOW"
    reasons: list[str] = []
    if capacity_signal:
        quality = "INADEQUATE"
        thinking = "NOT_SUPPORTED"
        reasons.append("capacity signal present")
    if not links_valid or not links["links_valid"]:
        quality = "INADEQUATE"
        thinking = "NOT_SUPPORTED"
        reasons.append("invalid link graph")
    if rec["IDEA"] < 3:
        quality = "INADEQUATE"
        thinking = "NOT_SUPPORTED"
        reasons.append("too few ideas for WIN001")
    if material_unsupported >= 8:
        quality = "INADEQUATE"
        thinking = "NOT_SUPPORTED"
        reasons.append("material unsupported content")
    elif material_unsupported or invented_refs or omitted_probes or relation_issues:
        quality = "REVIEW_REQUIRED"
        thinking = "REVIEW_REQUIRED"
        reasons.append("semantic issues require human review")
    if grouping in {"too_fine_one_idea_per_src_risk", "too_coarse", "missing"}:
        if quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION":
            quality = "REVIEW_REQUIRED"
            thinking = "REVIEW_REQUIRED"
        reasons.append(f"idea grouping={grouping}")
    if interpreter_hits:
        if quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION":
            quality = "REVIEW_REQUIRED"
            thinking = "REVIEW_REQUIRED"
        reasons.append("possible interpreter material")
    return {
        "performed": True,
        "semantic_quality": quality,
        "thinking_disabled_local_extraction": thinking,
        "unsupported_content": material_unsupported,
        "unsupported_records": unsupported[:20],
        "invented_references": invented_refs,
        "relation_issues": relation_issues,
        "interpreter_markers": interpreter_hits,
        "idea_grouping": grouping,
        "single_src_ideas": single_src_ideas,
        "mean_src_refs_per_idea": round(sum(idea_src_counts) / len(idea_src_counts), 3)
        if idea_src_counts
        else 0.0,
        "topics_useful": rec["TOPIC"] >= 1 and rec["TOPIC"] <= 14,
        "major_ideas_probe": probe,
        "omitted_probe_count": len(omitted_probes),
        "language": {
            "primary": transcript.primary_language,
            "interpreter_markers": interpreter_hits,
            "records_char_len": len(records_blob),
        },
        "record_metrics": rec,
        "src_metrics": src,
        "link_metrics": links,
        "sample": sample[:24],
        "reasons": reasons,
        "do_not_generalize": True,
        "editorial_quality_evaluated": False,
        "notes": (
            "Deterministic overlap review against cited CLEAN SRC text. "
            "Not a second model call. Conservative flags only."
        ),
    }


__all__ = ["review_transport"]
