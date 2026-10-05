"""Read-only CH018 integrity, JSON/Markdown consistency, and lock review."""

from __future__ import annotations

import json
from typing import Any

from app.book_authorial_voice_4b218.chapter_io import iter_paragraphs, paragraph_ids, section_ids
from app.book_batch_preparation_4b222.constants import (
    ACCEPTED_CH018_ID,
    ACCEPTED_CH018_TITLE,
    CH018_EX046,
    CH018_IDEAS,
    CH018_SECTIONS,
    EXPECTED_CH018_JSON_SHA256,
    EXPECTED_CH018_MD_SHA256,
    LOCK_CONSUMED_STATES,
    LOCK_STATE_RESPONSE_VALIDATED,
    PHASE,
)
from app.book_batch_preparation_4b222.guard import BookBatchPreparation4222Error
from app.book_batch_preparation_4b222.hashes import file_sha256
from app.book_batch_preparation_4b222.paths import (
    ch018_json_path,
    ch018_lock_path,
    ch018_md_path,
)
from app.book_editorial_acceptance_4b219.consistency import parse_markdown_prose
from app.book_generation.evidence import classify_handle
from app.book_generation_4b221.lock import read_lock


def load_ch018_chapter() -> dict[str, Any]:
    path = ch018_json_path()
    if not path.is_file():
        raise BookBatchPreparation4222Error(f"CH018 JSON missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BookBatchPreparation4222Error("CH018 JSON is not an object")
    if payload.get("chapter_id") != ACCEPTED_CH018_ID:
        raise BookBatchPreparation4222Error(
            f"CH018 chapter_id {payload.get('chapter_id')!r} ≠ {ACCEPTED_CH018_ID}"
        )
    if payload.get("title") != ACCEPTED_CH018_TITLE:
        raise BookBatchPreparation4222Error(
            f"CH018 title {payload.get('title')!r} ≠ {ACCEPTED_CH018_TITLE}"
        )
    return payload


def load_ch018_markdown() -> str:
    path = ch018_md_path()
    if not path.is_file():
        raise BookBatchPreparation4222Error(f"CH018 markdown missing: {path}")
    return path.read_text(encoding="utf-8")


def _handles_from_paragraphs(chapter: dict[str, Any], kind: str) -> list[str]:
    found: list[str] = []
    for _pid, row in iter_paragraphs(chapter):
        for handle in row.get("evidence_handles") or []:
            if classify_handle(str(handle)) == kind:
                found.append(str(handle))
        extra_key = {
            "IDEA": "idea_refs",
            "EX": "example_refs",
            "REF": "reference_refs",
            "SRC": "source_refs",
        }.get(kind)
        if extra_key:
            for handle in row.get(extra_key) or []:
                if classify_handle(str(handle)) == kind:
                    found.append(str(handle))
    return list(dict.fromkeys(found))


def compare_ch018_markdown_json(chapter: dict[str, Any], markdown: str) -> dict[str, Any]:
    parsed = parse_markdown_prose(markdown)
    json_rows = list(iter_paragraphs(chapter))
    json_texts = [row["text"].strip() for _pid, row in json_rows]
    md_texts = [text.strip() for text in parsed["paragraphs"]]
    json_section_titles = [
        str(section.get("title") or "") for section in chapter.get("sections") or []
    ]
    md_section_titles = [section["title"] for section in parsed["sections"]]
    mismatches = []
    pairs = []
    for index, (json_text, md_text) in enumerate(zip(json_texts, md_texts)):
        paragraph_id = json_rows[index][0] if index < len(json_rows) else f"index-{index}"
        same = json_text == md_text
        pairs.append(
            {
                "paragraph_id": paragraph_id,
                "json_chars": len(json_text),
                "markdown_chars": len(md_text),
                "prose_match": same,
            }
        )
        if not same:
            mismatches.append(paragraph_id)
    if len(json_texts) != len(md_texts):
        mismatches.append("paragraph_count_mismatch")
    consistent = (
        chapter.get("chapter_id") == ACCEPTED_CH018_ID
        and parsed["title"] == ACCEPTED_CH018_TITLE
        and list(section_ids(chapter)) == list(CH018_SECTIONS)
        and json_section_titles == md_section_titles
        and not mismatches
        and len(json_texts) == len(md_texts)
    )
    return {
        "phase": PHASE,
        "chapter_id": ACCEPTED_CH018_ID,
        "consistent": consistent,
        "json_chapter_id": chapter.get("chapter_id"),
        "markdown_title": parsed["title"],
        "json_sections": list(section_ids(chapter)),
        "expected_sections": list(CH018_SECTIONS),
        "json_paragraph_ids": list(paragraph_ids(chapter)),
        "json_paragraph_count": len(json_texts),
        "markdown_paragraph_count": len(md_texts),
        "section_titles_match": json_section_titles == md_section_titles,
        "prose_pairs": pairs,
        "prose_mismatches": mismatches,
        "rewritten": False,
        "secrets_included": False,
    }


def inspect_ch018_lock() -> dict[str, Any]:
    path = ch018_lock_path()
    payload = read_lock(path)
    if payload is None:
        raise BookBatchPreparation4222Error("CH018 call lock is missing. STOP.")
    state = str(payload.get("state") or "")
    consumed = bool(payload.get("consumed")) or state in LOCK_CONSUMED_STATES
    reusable = payload.get("reusable")
    return {
        "phase": PHASE,
        "path": str(path).replace("\\", "/"),
        "exists": True,
        "state": state,
        "consumed": consumed,
        "reusable": reusable,
        "authorization_scope": payload.get("authorization_scope"),
        "validated": state == LOCK_STATE_RESPONSE_VALIDATED,
        "reusable_blocked": reusable is False and consumed,
        "secrets_included": False,
    }


def inspect_ch018_integrity() -> dict[str, Any]:
    json_info = file_sha256(ch018_json_path())
    md_info = file_sha256(ch018_md_path())
    lock_info = file_sha256(ch018_lock_path())
    if not json_info["exists"] or not md_info["exists"] or not lock_info["exists"]:
        raise BookBatchPreparation4222Error("CH018 accepted artifacts are incomplete. STOP.")
    if json_info["sha256"] != EXPECTED_CH018_JSON_SHA256:
        raise BookBatchPreparation4222Error(
            f"CH018 JSON hash {json_info['sha256']} ≠ {EXPECTED_CH018_JSON_SHA256}"
        )
    if md_info["sha256"] != EXPECTED_CH018_MD_SHA256:
        raise BookBatchPreparation4222Error(
            f"CH018 Markdown hash {md_info['sha256']} ≠ {EXPECTED_CH018_MD_SHA256}"
        )
    chapter = load_ch018_chapter()
    markdown = load_ch018_markdown()
    consistency = compare_ch018_markdown_json(chapter, markdown)
    if not consistency["consistent"]:
        raise BookBatchPreparation4222Error("CH018 JSON/Markdown consistency failed. STOP.")
    ideas = _handles_from_paragraphs(chapter, "IDEA")
    examples = _handles_from_paragraphs(chapter, "EX")
    missing_ideas = [item for item in CH018_IDEAS if item not in ideas]
    extra_ideas = [item for item in ideas if item not in CH018_IDEAS]
    lock = inspect_ch018_lock()
    if not lock["consumed"] or lock["reusable"] is not False:
        raise BookBatchPreparation4222Error(
            "CH018 call lock must be consumed and non-reusable. STOP."
        )
    return {
        "phase": PHASE,
        "files_present": True,
        "integrity_ok": True,
        "chapter_id_exact": chapter.get("chapter_id") == ACCEPTED_CH018_ID,
        "sections": list(section_ids(chapter)),
        "expected_sections": list(CH018_SECTIONS),
        "sections_exact": list(section_ids(chapter)) == list(CH018_SECTIONS),
        "ideas_expected": list(CH018_IDEAS),
        "ideas_found": ideas,
        "ideas_expected_count": len(CH018_IDEAS),
        "ideas_found_count": len(ideas),
        "ideas_missing": missing_ideas,
        "ideas_extra": extra_ideas,
        "ideas_traced": not missing_ideas and not extra_ideas,
        "examples_in_paras_e": examples,
        "ex046_in_paras_e": CH018_EX046 in examples,
        "markdown_json_consistency": consistency,
        "lock": lock,
        "json_sha256": json_info["sha256"],
        "markdown_sha256": md_info["sha256"],
        "lock_sha256": lock_info["sha256"],
        "unchanged_since_generation": (
            json_info["sha256"] == EXPECTED_CH018_JSON_SHA256
            and md_info["sha256"] == EXPECTED_CH018_MD_SHA256
        ),
        "prose_modified": False,
        "secrets_included": False,
    }


__all__ = [
    "compare_ch018_markdown_json",
    "inspect_ch018_integrity",
    "inspect_ch018_lock",
    "load_ch018_chapter",
    "load_ch018_markdown",
]
