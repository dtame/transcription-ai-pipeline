"""Deterministic candidate detection plus reviewed CH012 classifications."""

from __future__ import annotations

import re
from typing import Any

from app.book_authorial_voice_4b218.chapter_io import iter_paragraphs
from app.book_authorial_voice_4b218.constants import (
    CLASS_ATTRIBUTION_UNCERTAIN,
    CLASS_AUTHORIAL_OK,
    CLASS_EXTERNAL_CONFIRMED,
    CLASS_POSSIBLE_EXTERNAL,
    CLASS_THIRD_PERSON_LEGITIMATE,
    FORBIDDEN_EXTERNAL_FRAMES,
    PHASE,
    TARGET_CHAPTER_ID,
)

_EXTERNAL_PHRASE = re.compile(
    r"\b("
    r"the speaker|the preacher|the author|one speaker|"
    r"the speaker recounted|the speaker explained|"
    r"the speaker emphasized|according to the speaker|"
    r"he taught that|he had prayed|"
    r"as taught here|in the delivery"
    r")\b",
    re.IGNORECASE,
)

# Reviewed classification for each CH012 paragraph. Detectors may flag
# candidates; they do not by themselves establish speaker identity.
PARAGRAPH_CLASSIFICATIONS: dict[str, dict[str, Any]] = {
    "P000001": {
        "classification": CLASS_ATTRIBUTION_UNCERTAIN,
        "point_of_view": "second-person quotation plus third-person frame",
        "external_author_reference": True,
        "person_shift": "source uses tu/nous; prose uses 'one speaker' / 'him'",
        "quotes_present": True,
        "note": (
            "SRC004846 is second-person address. Neighboring SRC004847-851 "
            "use tu/on/nous. The addressee of 'Tu viens juste d'exercer le "
            "bavardage' is not proven. Do not convert to I was told."
        ),
    },
    "P000002": {
        "classification": CLASS_AUTHORIAL_OK,
        "point_of_view": "inclusive we plus mild reportage of a question",
        "external_author_reference": False,
        "person_shift": "source 'nous' is kept as 'us'",
        "quotes_present": False,
        "note": (
            "The question 'Pourquoi ça ne marche pas avec nous?' is kept. "
            "Source 'ce qu'il a dit' is Scripture/God, not the author."
        ),
    },
    "P000003": {
        "classification": CLASS_EXTERNAL_CONFIRMED,
        "point_of_view": "source first-person plural rewritten as those/they",
        "external_author_reference": True,
        "person_shift": "nous/we became those/they/their",
        "quotes_present": False,
        "note": (
            "SRC004918/920/921/923 say 'Nous étions sincères' and "
            "'nous ne savions pas'. The prose reports that group as others."
        ),
    },
    "P000004": {
        "classification": CLASS_EXTERNAL_CONFIRMED,
        "point_of_view": "conference-report frame around a teaching citation",
        "external_author_reference": True,
        "person_shift": "'the speaker' / 'as taught here' / 'in the delivery'",
        "quotes_present": False,
        "note": (
            "SRC006459 'he says in verse 3' refers to Isaiah, not a proven "
            "external preacher. Neutralize the conference-report frame. "
            "Do not invent 'I referred'."
        ),
    },
    "P000005": {
        "classification": CLASS_THIRD_PERSON_LEGITIMATE,
        "point_of_view": "citation of Isaiah, 1 Corinthians, and Jude",
        "external_author_reference": False,
        "person_shift": None,
        "quotes_present": False,
        "note": "Jude and the biblical books are third-person referents.",
    },
    "P000006": {
        "classification": CLASS_AUTHORIAL_OK,
        "point_of_view": "second-person counsel preserved",
        "external_author_reference": False,
        "person_shift": None,
        "quotes_present": False,
        "note": "Source 'Quand vous êtes fatigué, priez en langue pour 5 minutes.'",
    },
    "P000007": {
        "classification": CLASS_AUTHORIAL_OK,
        "point_of_view": "second-person teaching with mild 'the teaching states'",
        "external_author_reference": False,
        "person_shift": None,
        "quotes_present": False,
        "note": "Source already uses you. No author-as-external-speaker.",
    },
    "P000008": {
        "classification": CLASS_EXTERNAL_CONFIRMED,
        "point_of_view": "first-person testimony rewritten as 'the speaker' / he",
        "external_author_reference": True,
        "person_shift": "j'ai / j'étais / ma voix became he / his",
        "quotes_present": False,
        "note": (
            "SRC004891 'Il a vu comment j'ai prié', SRC004893 'J'étais au sol', "
            "SRC004895 'Ma voix était cassée'. The witness 'Il' stays third person."
        ),
    },
    "P000009": {
        "classification": CLASS_EXTERNAL_CONFIRMED,
        "point_of_view": "author as recipient of God's speech, rewritten as him",
        "external_author_reference": True,
        "person_shift": "il m'a dit / tu es fatigué became him / he",
        "quotes_present": True,
        "note": (
            "SRC004898 'il m'a dit mon fils'. God remains third person. "
            "The recipient is first person in the source."
        ),
    },
    "P000010": {
        "classification": CLASS_THIRD_PERSON_LEGITIMATE,
        "point_of_view": "God speaking in the first person; prayer addressed as you",
        "external_author_reference": False,
        "person_shift": None,
        "quotes_present": True,
        "note": (
            "SRC004909/910 are God's 'Je'. SRC004915/917 address 'ta prière' / 'te'."
        ),
    },
    "P000011": {
        "classification": CLASS_AUTHORIAL_OK,
        "point_of_view": "quoted second-person correction",
        "external_author_reference": False,
        "person_shift": None,
        "quotes_present": True,
        "note": "Quoted words match SRC006452/454. Mild reportage left in place.",
    },
    "P000012": {
        "classification": CLASS_THIRD_PERSON_LEGITIMATE,
        "point_of_view": "Isaiah 44:3 quoted as God's speech",
        "external_author_reference": False,
        "person_shift": None,
        "quotes_present": True,
        "note": "First-person 'I will pour' is God's biblical voice.",
    },
    "P000013": {
        "classification": CLASS_THIRD_PERSON_LEGITIMATE,
        "point_of_view": "Jesus' beatitude quoted",
        "external_author_reference": False,
        "person_shift": None,
        "quotes_present": True,
        "note": "Third person names Jesus. Quoted you is the beatitude.",
    },
    "P000014": {
        "classification": CLASS_AUTHORIAL_OK,
        "point_of_view": "general teaching about God",
        "external_author_reference": False,
        "person_shift": None,
        "quotes_present": False,
        "note": "God as he is legitimate. Mild 'the teaching anchors' left in place.",
    },
}


def detect_external_frames(text: str) -> list[str]:
    found = [frame for frame in FORBIDDEN_EXTERNAL_FRAMES if frame.lower() in text.lower()]
    for match in _EXTERNAL_PHRASE.finditer(text or ""):
        token = match.group(1)
        if token not in found:
            found.append(token)
    return found


def audit_chapter(chapter: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    counts = {
        CLASS_AUTHORIAL_OK: 0,
        CLASS_EXTERNAL_CONFIRMED: 0,
        CLASS_POSSIBLE_EXTERNAL: 0,
        CLASS_ATTRIBUTION_UNCERTAIN: 0,
        CLASS_THIRD_PERSON_LEGITIMATE: 0,
    }
    for paragraph_id, row in iter_paragraphs(chapter):
        reviewed = dict(PARAGRAPH_CLASSIFICATIONS.get(paragraph_id) or {})
        classification = reviewed.get("classification") or CLASS_POSSIBLE_EXTERNAL
        detector = detect_external_frames(row["text"])
        item = {
            "paragraph_id": paragraph_id,
            "section_id": row["section_id"],
            "section_title": row["section_title"],
            "classification": classification,
            "point_of_view": reviewed.get("point_of_view"),
            "external_author_reference": reviewed.get("external_author_reference"),
            "person_shift": reviewed.get("person_shift"),
            "quotes_present": reviewed.get("quotes_present"),
            "source_refs": row["source_refs"],
            "uncertainty_refs": row["uncertainty_refs"],
            "idea_refs": row["idea_refs"],
            "detector_candidates": detector,
            "detector_alone_establishes_identity": False,
            "note": reviewed.get("note"),
            "text": row["text"],
        }
        counts[classification] = counts.get(classification, 0) + 1
        rows.append(item)
    return {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "paragraphs_audited": len(rows),
        "classifications": rows,
        "counts": counts,
        "every_he_she_they_is_not_an_anomaly": True,
        "secrets_included": False,
    }


__all__ = [
    "PARAGRAPH_CLASSIFICATIONS",
    "audit_chapter",
    "detect_external_frames",
]
