"""
4B.2.2 inventories and first-pass semantic review.

Automated first-pass does not replace exhaustive human reading of CH016.
Does not repair provider prose. Does not invoke Terra or Phase 5.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.book_generation.constants import (
    PARAGRAPH_KIND_CONNECTIVE,
    PARAGRAPH_KIND_SUBSTANTIVE,
)
from app.book_generator_canary_4b2.review import (
    _evidence_index,
    _norm,
    _overlap,
    default_fidelity_review,
    default_quality_review,
    idea_coverage_review,
    invention_scan,
    paragraph_provenance_review,
)

_BIBLE = re.compile(
    r"\b(?:Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|"
    r"(?:1|2|I|II)\s*Samuel|(?:1|2|I|II)\s*Kings|(?:1|2|I|II)\s*Chronicles|"
    r"Ezra|Nehemiah|Esther|Job|Psalm|Psalms|Proverbs|Ecclesiastes|"
    r"Song(?: of (?:Songs|Solomon))?|Isaiah|Jeremiah|Lamentations|Ezekiel|"
    r"Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|"
    r"Haggai|Zechariah|Malachi|Matthew|Mark|Luke|John|Acts|Romans|"
    r"(?:1|2|I|II)\s*Corinthians|Galatians|Ephesians|Philippians|Colossians|"
    r"(?:1|2|I|II)\s*Thessalonians|(?:1|2|I|II)\s*Timothy|Titus|Philemon|"
    r"Hebrews|James|(?:1|2|I|II)\s*Peter|(?:1|2|3|I|II|III)\s*John|Jude|"
    r"Revelation)\s+\d+:\d+(?:-\d+)?\b",
    re.IGNORECASE,
)
_EXAMPLE_CUES = (
    r"\bfor example\b",
    r"\bfor instance\b",
    r"\bimagine\b",
    r"\bpicture\b",
    r"\bsuppose\b",
    r"\bhypothetical\b",
    r"\banecdote\b",
    r"\billustration\b",
    r"\blike the (man|woman|person|pastor|widow|family)\b",
    r"\ba (man|woman|person|pastor|widow) who\b",
    r"\bfuneral\b",
    r"\bgrave(side)?\b",
    r"\bas if\b",
)
_CONNECTIVE_CLAIM = (
    r"\bbecause\b",
    r"\btherefore\b",
    r"\bthus\b",
    r"\bhence\b",
    r"\bscripture says\b",
    r"\bthe bible\b",
    r"\bjesus (said|says|taught)\b",
    r"\bpaul (said|says|wrote)\b",
    r"\bthis (proves|means|shows|implies)\b",
    r"\bmust (therefore )?(be|mean)\b",
)


def _paragraphs(candidate: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(candidate, Mapping):
        return rows
    path_index = 1
    for section in candidate.get("sections") or []:
        for paragraph in section.get("paragraphs") or []:
            row = dict(paragraph)
            row["section_id"] = section.get("section_id")
            row["path"] = f"{section.get('section_id')}.p{path_index}"
            rows.append(row)
            path_index += 1
    return rows


def paragraph_inventory(
    candidate: Mapping[str, Any] | None,
    *,
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    provenance_rows = {
        str(row.get("provider_handle") or row.get("path") or index): row
        for index, row in enumerate((provenance or {}).get("paragraphs") or [])
    }
    rows = []
    for paragraph in _paragraphs(candidate):
        handle = str(paragraph.get("provider_handle") or "")
        proven = provenance_rows.get(handle) or {}
        text = str(paragraph.get("text") or "")
        rows.append(
            {
                "handle": handle,
                "path": paragraph.get("path"),
                "section": paragraph.get("section_id"),
                "kind": paragraph.get("kind"),
                "text_presence": bool(text.strip()),
                "text": text,
                "evidence_handles": list(paragraph.get("evidence_handles") or []),
                "resolved_src": list(paragraph.get("source_refs") or []),
                "idea_refs": list(paragraph.get("idea_refs") or []),
                "example_refs": list(paragraph.get("example_refs") or []),
                "reference_refs": list(paragraph.get("reference_refs") or []),
                "uncertainty_refs": list(paragraph.get("uncertainty_refs") or []),
                "semantic_classification": proven.get("classification")
                or "PENDING_HUMAN_REVIEW",
                "overlap_with_cited_evidence": proven.get("overlap_with_cited_evidence"),
                "notes": list(proven.get("notes") or []),
                "reviewer": "automated_first_pass",
            }
        )
    return {
        "paragraphs": rows,
        "count": len(rows),
        "reviewer": "automated_first_pass",
        "exhaustive_human_review_required": True,
    }


def connective_review(
    candidate: Mapping[str, Any] | None,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    index = _evidence_index(evidence)
    rows = []
    unsupported = 0
    for paragraph in _paragraphs(candidate):
        if paragraph.get("kind") != PARAGRAPH_KIND_CONNECTIVE:
            continue
        text = str(paragraph.get("text") or "")
        claim_hits = [pat for pat in _CONNECTIVE_CLAIM if re.search(pat, text, re.IGNORECASE)]
        handles = list(paragraph.get("evidence_handles") or [])
        cited = " ".join(
            str((index.get(handle) or {}).get("text") or "") for handle in handles
        )
        overlap = _overlap(text, cited) if cited else 0.0
        if claim_hits and not handles:
            classification = "SUBSTANTIVE_UNSUPPORTED"
            supported = False
            unsupported += 1
        elif claim_hits and overlap < 0.04:
            classification = "SUBSTANTIVE_UNSUPPORTED"
            supported = False
            unsupported += 1
        elif claim_hits:
            classification = "SOURCE_SUPPORTED_DESPITE_CONNECTIVE_FUNCTION"
            supported = True
        else:
            classification = "CONNECTIVE_NON_SUBSTANTIVE"
            supported = True
        rows.append(
            {
                "handle": paragraph.get("provider_handle"),
                "path": paragraph.get("path"),
                "section": paragraph.get("section_id"),
                "text": text,
                "provider_kind": "con",
                "provider_kind_trusted": False,
                "claim_cues": claim_hits,
                "evidence_handles": handles,
                "classification": classification,
                "supported": supported,
                "questions": [
                    "Does it merely connect supported ideas?",
                    "Or does it introduce a new proposition, implication, conclusion, argument, doctrine, or example?",
                ],
                "reviewer": "automated_first_pass",
                "human_override_required": True,
            }
        )
    return {
        "connective_paragraphs": rows,
        "count": len(rows),
        "unsupported_connective_claims": unsupported,
        "pass": unsupported == 0,
        "reviewer": "automated_first_pass",
        "note": (
            "Provider kind=con is not trusted. Exhaustive human reading "
            "must confirm each connective paragraph."
        ),
    }


def example_review(
    candidate: Mapping[str, Any] | None,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    corpus = " ".join(
        [
            str(row.get("sum") or "")
            for row in (evidence.get("ideas") or []) + (evidence.get("examples") or [])
        ]
        + [str(row.get("t") or "") for row in evidence.get("src_text") or []]
    ).lower()
    rows = []
    invented = 0
    for paragraph in _paragraphs(candidate):
        text = str(paragraph.get("text") or "")
        cues = [pat for pat in _EXAMPLE_CUES if re.search(pat, text, re.IGNORECASE)]
        if not cues:
            continue
        distinctive = [
            token
            for token in re.findall(r"[A-Za-z']{5,}", text)
            if token.lower() not in {
                "example",
                "instance",
                "imagine",
                "picture",
                "suppose",
                "illustration",
            }
        ]
        supported = any(token.lower() in corpus for token in distinctive[:8])
        if not supported:
            invented += 1
        rows.append(
            {
                "handle": paragraph.get("provider_handle"),
                "path": paragraph.get("path"),
                "section": paragraph.get("section_id"),
                "kind": paragraph.get("kind"),
                "text": text,
                "cues": cues,
                "source_supported": supported,
                "classification": "SUPPORTED_EXAMPLE" if supported else "INVENTED_EXAMPLE",
                "reviewer": "automated_first_pass",
                "human_override_required": True,
            }
        )
    return {
        "example_like_elements": rows,
        "count": len(rows),
        "invented_examples": invented,
        "pass": invented == 0,
        "reviewer": "automated_first_pass",
        "note": (
            "Cue-based inventory only. Human review must decide whether "
            "each element is actually an example and whether canonical "
            "evidence supports it."
        ),
    }


def reference_review(
    candidate: Mapping[str, Any] | None,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    allowed = {
        match.group(0).lower()
        for match in _BIBLE.finditer(
            " ".join(
                [str(row.get("raw") or "") for row in evidence.get("references") or []]
                + [str(row.get("norm") or "") for row in evidence.get("references") or []]
                + [str(row.get("sum") or "") for row in evidence.get("ideas") or []]
                + [str(row.get("t") or "") for row in evidence.get("src_text") or []]
            )
        )
    }
    rows = []
    invented = 0
    for paragraph in _paragraphs(candidate):
        text = str(paragraph.get("text") or "")
        found = [match.group(0) for match in _BIBLE.finditer(text)]
        for item in found:
            supported = item.lower() in allowed
            if not supported:
                invented += 1
            rows.append(
                {
                    "handle": paragraph.get("provider_handle"),
                    "path": paragraph.get("path"),
                    "section": paragraph.get("section_id"),
                    "reference": item,
                    "source_supported": supported,
                    "classification": "SUPPORTED_REFERENCE"
                    if supported
                    else "INVENTED_REFERENCE",
                    "reviewer": "automated_first_pass",
                    "human_override_required": True,
                }
            )
    return {
        "references": rows,
        "count": len(rows),
        "invented_references": invented,
        "allowed_bible_in_evidence": sorted(allowed),
        "pass": invented == 0,
        "reviewer": "automated_first_pass",
    }


def apply_human_review(
    *,
    inventory: Mapping[str, Any],
    connective: Mapping[str, Any],
    examples: Mapping[str, Any],
    references: Mapping[str, Any],
    coverage: Mapping[str, Any],
    fidelity: Mapping[str, Any],
    quality: Mapping[str, Any],
    overlay: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply exhaustive human classifications without mutating provider prose."""
    updated_inventory = dict(inventory)
    if overlay.get("paragraphs"):
        updated_inventory["paragraphs"] = list(overlay["paragraphs"])
        updated_inventory["reviewer"] = "human_exhaustive"
        updated_inventory["exhaustive_human_review_required"] = False
    updated_connective = dict(connective)
    if overlay.get("connective"):
        updated_connective.update(dict(overlay["connective"]))
        updated_connective["reviewer"] = "human_exhaustive"
    updated_examples = dict(examples)
    if overlay.get("examples"):
        updated_examples.update(dict(overlay["examples"]))
        updated_examples["reviewer"] = "human_exhaustive"
    updated_references = dict(references)
    if overlay.get("references"):
        updated_references.update(dict(overlay["references"]))
        updated_references["reviewer"] = "human_exhaustive"
    updated_coverage = dict(coverage)
    if overlay.get("coverage"):
        updated_coverage.update(dict(overlay["coverage"]))
        updated_coverage["reviewer"] = "human_exhaustive"
    updated_fidelity = dict(fidelity)
    if overlay.get("fidelity"):
        updated_fidelity.update(dict(overlay["fidelity"]))
        updated_fidelity["reviewer"] = "human_exhaustive"
    updated_quality = dict(quality)
    if overlay.get("quality"):
        updated_quality.update(dict(overlay["quality"]))
        updated_quality["reviewer"] = "human_exhaustive"
    return {
        "inventory": updated_inventory,
        "connective": updated_connective,
        "examples": updated_examples,
        "references": updated_references,
        "coverage": updated_coverage,
        "fidelity": updated_fidelity,
        "quality": updated_quality,
    }


__all__ = [
    "apply_human_review",
    "connective_review",
    "default_fidelity_review",
    "default_quality_review",
    "example_review",
    "idea_coverage_review",
    "invention_scan",
    "paragraph_inventory",
    "paragraph_provenance_review",
    "reference_review",
]
