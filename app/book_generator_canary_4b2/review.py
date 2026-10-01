"""
Automated + structured human-readable CH016 fidelity / quality review.

Does not repair provider prose. Does not invoke Phase 5 Book Validator.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.book_generation.constants import (
    PARAGRAPH_KIND_CONNECTIVE,
    PARAGRAPH_KIND_SUBSTANTIVE,
)
from app.book_generation.coverage import assigned_idea_ids_for_chapter
from app.book_generation.evidence import classify_handle
from app.editorial_planning.models import EditorialChapter
from app.source_analysis.models import SourceMap

_ORAL = (
    r"\bcan you hear\b",
    r"\bare you there\b",
    r"\bnext session\b",
    r"\bwe'?re recording\b",
    r"\bthe recording\b",
    r"\binterpreter\b",
    r"\bplease mute\b",
    r"\bas i (said|was saying)\b",
    r"\byou know\b",
    r"\buh+\b",
    r"\bum+\b",
    r"\bok(ay)? so\b",
)
_BIBLE = re.compile(
    r"\b(?:Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|"
    r"Samuel|Kings|Chronicles|Ezra|Nehemiah|Esther|Job|Psalm|Psalms|Proverbs|"
    r"Ecclesiastes|Song|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|"
    r"Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|"
    r"Malachi|Matthew|Mark|Luke|John|Acts|Romans|Corinthians|Galatians|"
    r"Ephesians|Philippians|Colossians|Thessalonians|Timothy|Titus|Philemon|"
    r"Hebrews|James|Peter|Jude|Revelation)\s+\d+:\d+(?:-\d+)?\b",
    re.IGNORECASE,
)
_CONNECTIVE_CLAIM = (
    r"\bbecause\b",
    r"\btherefore\b",
    r"\bscripture says\b",
    r"\bthe bible\b",
    r"\bjesus (said|says|taught)\b",
    r"\bpaul (said|says|wrote)\b",
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9']{4,}", _norm(text))}


def _overlap(a: str, b: str) -> float:
    left = _tokens(a)
    right = _tokens(b)
    if not left or not right:
        return 0.0
    return len(left & right) / float(len(left))


def _evidence_index(evidence: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for key, id_field, text_fields in (
        ("ideas", "id", ("sum",)),
        ("examples", "id", ("sum",)),
        ("references", "id", ("raw", "norm")),
        ("uncertainties", "id", ("desc",)),
        ("src_text", "id", ("t",)),
    ):
        for row in evidence.get(key) or []:
            if not isinstance(row, Mapping):
                continue
            handle = str(row.get(id_field) or "")
            if not handle:
                continue
            text = " ".join(str(row.get(field) or "") for field in text_fields)
            index[handle] = {"kind": key, "text": text, "row": dict(row)}
    for src_id in evidence.get("src") or []:
        index.setdefault(str(src_id), {"kind": "src", "text": "", "row": {"id": src_id}})
    return index


def _bible_in_evidence(evidence: Mapping[str, Any]) -> set[str]:
    blob = _norm(
        " ".join(
            [
                str(row.get("raw") or "")
                for row in evidence.get("references") or []
            ]
            + [
                str(row.get("norm") or "")
                for row in evidence.get("references") or []
            ]
            + [
                str(row.get("sum") or "")
                for row in (evidence.get("ideas") or []) + (evidence.get("examples") or [])
            ]
            + [str(row.get("t") or "") for row in evidence.get("src_text") or []]
        )
    )
    return {match.group(0).lower() for match in _BIBLE.finditer(blob)}


def classify_paragraph(
    paragraph: Mapping[str, Any],
    *,
    evidence_index: Mapping[str, dict[str, Any]],
    allowed: set[str],
    source_map: SourceMap,
) -> dict[str, Any]:
    kind = str(paragraph.get("kind") or "")
    text = str(paragraph.get("text") or "")
    handles = list(paragraph.get("evidence_handles") or [])
    unc = list(paragraph.get("uncertainty_refs") or [])
    src_refs = list(paragraph.get("source_refs") or [])
    idea_refs = list(paragraph.get("idea_refs") or [])
    combined = handles + unc
    unknown = [handle for handle in combined if handle not in allowed]
    cited_text = " ".join(
        str((evidence_index.get(handle) or {}).get("text") or "")
        for handle in combined
    )
    overlap = _overlap(text, cited_text) if cited_text else 0.0
    oral_hits = [pat for pat in _ORAL if re.search(pat, text, re.IGNORECASE)]
    classification = "UNSUPPORTED"
    notes: list[str] = []
    if kind == PARAGRAPH_KIND_CONNECTIVE:
        claim_hits = [pat for pat in _CONNECTIVE_CLAIM if re.search(pat, text, re.IGNORECASE)]
        if claim_hits or len(text) > 400:
            classification = "QUESTIONABLE_SUPPORT"
            notes.append("connective paragraph may introduce a substantive claim")
        else:
            classification = "CONNECTIVE_NON_SUBSTANTIVE"
    elif kind == PARAGRAPH_KIND_SUBSTANTIVE:
        if unknown:
            classification = "UNSUPPORTED"
            notes.append(f"unknown handles: {unknown}")
        elif not combined or not src_refs:
            classification = "UNSUPPORTED"
            notes.append("substantive paragraph does not resolve to SRC")
        elif overlap < 0.04 and not idea_refs:
            classification = "QUESTIONABLE_SUPPORT"
            notes.append("weak lexical overlap with cited evidence")
        elif overlap < 0.02:
            classification = "QUESTIONABLE_SUPPORT"
            notes.append("very weak lexical overlap with cited evidence")
        else:
            classification = "SUBSTANTIVE_SUPPORTED"
    else:
        classification = "UNSUPPORTED"
        notes.append(f"unknown paragraph kind {kind!r}")
    if oral_hits:
        notes.append(f"oral-artifact patterns: {oral_hits}")
    return {
        "text": text,
        "kind": kind,
        "classification": classification,
        "evidence_handles": handles,
        "uncertainty_refs": unc,
        "idea_refs": idea_refs,
        "source_refs": src_refs,
        "unknown_handles": unknown,
        "overlap_with_cited_evidence": round(overlap, 4),
        "oral_artifact_hits": oral_hits,
        "notes": notes,
        "provider_handle": paragraph.get("provider_handle") or "",
        "known_source_map": bool(source_map),
    }


def idea_coverage_review(
    candidate: Mapping[str, Any],
    chapter: EditorialChapter,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    expected = list(assigned_idea_ids_for_chapter(chapter))
    ideas = {row.get("id"): row for row in evidence.get("ideas") or []}
    paragraphs = [
        paragraph
        for section in candidate.get("sections") or []
        for paragraph in section.get("paragraphs") or []
    ]
    rows: list[dict[str, Any]] = []
    missing = 0
    weak = 0
    clear = 0
    for idea_id in expected:
        cited = [
            paragraph
            for paragraph in paragraphs
            if idea_id in (paragraph.get("idea_refs") or [])
            or idea_id in (paragraph.get("evidence_handles") or [])
        ]
        summary = str((ideas.get(idea_id) or {}).get("sum") or "")
        best = 0.0
        for paragraph in cited:
            best = max(best, _overlap(str(paragraph.get("text") or ""), summary))
        if not cited:
            status = "MISSING"
            missing += 1
        elif best < 0.05:
            status = "WEAKLY_REPRESENTED"
            weak += 1
        else:
            status = "CLEARLY_REPRESENTED"
            clear += 1
        rows.append(
            {
                "idea_id": idea_id,
                "status": status,
                "cited_paragraphs": len(cited),
                "summary_overlap": round(best, 4),
                "summary": summary,
            }
        )
    return {
        "expected": expected,
        "CLEARLY_REPRESENTED": clear,
        "WEAKLY_REPRESENTED": weak,
        "MISSING": missing,
        "ideas": rows,
        "coverage_complete": missing == 0,
    }


def paragraph_provenance_review(
    candidate: Mapping[str, Any],
    evidence: Mapping[str, Any],
    source_map: SourceMap,
) -> dict[str, Any]:
    allowed = set(evidence.get("allowed") or [])
    index = _evidence_index(evidence)
    rows: list[dict[str, Any]] = []
    counts = {
        "SUBSTANTIVE_SUPPORTED": 0,
        "CONNECTIVE_NON_SUBSTANTIVE": 0,
        "QUESTIONABLE_SUPPORT": 0,
        "UNSUPPORTED": 0,
    }
    path_index = 1
    for section in candidate.get("sections") or []:
        for paragraph in section.get("paragraphs") or []:
            row = classify_paragraph(
                paragraph,
                evidence_index=index,
                allowed=allowed,
                source_map=source_map,
            )
            row["path"] = f"{section.get('section_id')}.p{path_index}"
            row["section_id"] = section.get("section_id")
            counts[row["classification"]] = counts.get(row["classification"], 0) + 1
            rows.append(row)
            path_index += 1
    return {
        "paragraphs": rows,
        "counts": counts,
        "QUESTIONABLE_SUPPORT": counts["QUESTIONABLE_SUPPORT"],
        "UNSUPPORTED": counts["UNSUPPORTED"],
        "CONNECTIVE_NON_SUBSTANTIVE": counts["CONNECTIVE_NON_SUBSTANTIVE"],
        "SUBSTANTIVE_SUPPORTED": counts["SUBSTANTIVE_SUPPORTED"],
        "exhaustive": True,
        "sample_only": False,
    }


def invention_scan(
    candidate: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    prose = " ".join(
        str(paragraph.get("text") or "")
        for section in candidate.get("sections") or []
        for paragraph in section.get("paragraphs") or []
    )
    allowed_bible = _bible_in_evidence(evidence)
    found_bible = {match.group(0) for match in _BIBLE.finditer(prose)}
    invented_refs = [
        item for item in found_bible if item.lower() not in allowed_bible
    ]
    oral = [pat for pat in _ORAL if re.search(pat, prose, re.IGNORECASE)]
    return {
        "invented_bible_or_completed_references": invented_refs,
        "oral_artifact_patterns": oral,
        "allowed_bible_in_evidence": sorted(allowed_bible),
    }


def default_fidelity_review(
    candidate: Mapping[str, Any] | None,
    *,
    chapter: EditorialChapter,
    evidence: Mapping[str, Any],
    source_map: SourceMap,
    provenance: Mapping[str, Any],
    coverage: Mapping[str, Any],
    language: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(candidate, Mapping):
        return {
            "status": "FAIL",
            "source_meaning": "FAIL",
            "oral_to_written": "FAIL",
            "author_voice": "WEAK",
            "invented_facts": "n/a",
            "invented_arguments": "n/a",
            "invented_examples": "n/a",
            "invented_references": "n/a",
            "uncertainty_preservation": "n/a",
            "repetition_control": "n/a",
            "notes": ["no candidate to review"],
        }
    invention = invention_scan(candidate, evidence)
    questionable = int(provenance.get("QUESTIONABLE_SUPPORT") or 0)
    unsupported = int(provenance.get("UNSUPPORTED") or 0)
    missing = int(coverage.get("MISSING") or 0)
    weak = int(coverage.get("WEAKLY_REPRESENTED") or 0)
    invented_refs = list(invention.get("invented_bible_or_completed_references") or [])
    oral = list(invention.get("oral_artifact_patterns") or [])
    meaning = "PASS"
    if missing or unsupported:
        meaning = "FAIL"
    elif questionable or weak:
        meaning = "REVIEW"
    oral_status = "REVIEW" if oral else "PASS"
    if unsupported:
        oral_status = "FAIL"
    voice = "ACCEPTABLE"
    if language.get("status") != "PASS":
        meaning = "FAIL" if meaning != "FAIL" else meaning
    status = "PASS"
    if meaning == "FAIL" or unsupported or missing or invented_refs:
        status = "FAIL"
    elif meaning == "REVIEW" or oral or weak or questionable:
        status = "REVIEW_REQUIRED"
    return {
        "status": status,
        "source_meaning": meaning,
        "oral_to_written": oral_status,
        "author_voice": voice,
        "invented_facts": 0 if not unsupported else "REVIEW",
        "invented_arguments": 0 if not unsupported else "REVIEW",
        "invented_examples": 0 if not unsupported else "REVIEW",
        "invented_references": invented_refs or 0,
        "uncertainty_preservation": "PASS"
        if not any(
            "UNC" in str(row.get("uncertainty_refs") or [])
            and "certain" in _norm(str(row.get("text") or ""))
            for row in provenance.get("paragraphs") or []
        )
        else "REVIEW",
        "repetition_control": "REVIEW",
        "invention_scan": invention,
        "questionable_support": questionable,
        "unsupported": unsupported,
        "weak_ideas": weak,
        "missing_ideas": missing,
        "notes": [
            "Automated first-pass review. Exhaustive human-readable inspection "
            "is recorded in the same audit after reading the candidate."
        ],
        "phase_5_not_invoked": True,
    }


def default_quality_review(
    candidate: Mapping[str, Any] | None,
    *,
    fidelity: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(candidate, Mapping):
        return {
            "status": "FAIL",
            "clarity": "n/a",
            "coherence": "n/a",
            "flow": "n/a",
            "written_book_quality": "n/a",
            "redundancy": "n/a",
            "source_fidelity": "n/a",
        }
    paragraphs = [
        str(paragraph.get("text") or "")
        for section in candidate.get("sections") or []
        for paragraph in section.get("paragraphs") or []
    ]
    connective = int(provenance.get("CONNECTIVE_NON_SUBSTANTIVE") or 0)
    formulaic = 0
    for text in paragraphs:
        lowered = _norm(text)
        if lowered.startswith("in conclusion") or lowered.startswith("to conclude"):
            formulaic += 1
    status = "PASS"
    if fidelity.get("status") == "FAIL":
        status = "FAIL"
    elif fidelity.get("status") == "REVIEW_REQUIRED":
        status = "REVIEW"
    return {
        "status": status,
        "clarity": "REVIEW",
        "coherence": "REVIEW",
        "flow": "REVIEW",
        "written_book_quality": "REVIEW",
        "redundancy": "REVIEW" if formulaic else "PASS",
        "source_fidelity": fidelity.get("source_meaning"),
        "formulaic_conclusions": formulaic,
        "connective_paragraphs": connective,
        "section_conclusions_required": False,
        "chapter_conclusion_required": False,
        "phase_5_not_invoked": True,
        "notes": [
            "Quality fields are completed after exhaustive reading of CH016."
        ],
    }


__all__ = [
    "default_fidelity_review",
    "default_quality_review",
    "idea_coverage_review",
    "paragraph_provenance_review",
]
