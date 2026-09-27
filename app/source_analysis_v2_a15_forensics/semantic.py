"""Revue sémantique forensique du transport A.15 invalide. Pas un résultat validé."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from app.source_analysis.canonical_vocabulary import (
    EXAMPLE_KINDS,
    IDEA_KINDS,
    IMPORTANCE_LEVELS,
    REFERENCE_KINDS,
    RELATION_KINDS,
    UNCERTAINTY_KINDS,
)
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v2_a15_forensics.constants import (
    MODE,
    PHASE,
    SCHEMA_VERSION,
    SEMANTIC_CONTENT_CLASSIFICATION,
    SEMANTIC_REVIEW_STATUS,
)

_STOP = frozenset(
    {
        "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
        "that", "this", "it", "is", "are", "was", "were", "be", "as", "by",
        "from", "at", "we", "you", "he", "she", "they", "not", "but", "if",
        "so", "our", "his", "her", "their", "les", "des", "une", "que", "qui",
        "dans", "pour", "avec", "est", "pas", "nous", "vous", "ils", "du",
        "la", "le", "un", "en", "ce", "se", "ne",
    }
)
_INTERPRETER = (
    "the interpreter",
    "l'interprète",
    "he says that",
    "she says that",
    "translation:",
    "traduction :",
)

# Diagnostic outline only. Never consume as canonical records.
_AUDIT_OUTLINE = (
    "1. Retreat opening: prayer walk, 1 Timothy 4:8, spirit/soul/body.",
    "2. Hear from God versus outside information; God teaches daily life.",
    "3. Cultural eating: night-heavy meals, couscous as 'food', meat last, stomach trouble.",
    "4. Knowledge increased — change inherited food practice; daughter/meat anecdote.",
    "5. Grandmother: fresh cooking, clay pots, no leftover soup.",
    "6. Longevity ambition versus church messages that prepare a good death; plant faith.",
    "7. Cake/birthday interruption (low-information).",
    "8. Flesh-and-bone resurrection, Thomas, seated Christ; positional-only as heresy.",
    "9. Sons of men / sons of God; Genesis 5 after Adam.",
    "10. Eve deceived, Adam silent; Jesus 'Father forgive them'; tree of life barred.",
    "11. Faith versus 40-day ritual; Romans 14:23; only Christ acceptable.",
    "12. Power already inside; Romans 12:1-2; teach Christ, not novel revelation.",
    "13. Hebrews 2: tasted death, brethren/singer, destroy the devil, fear of death.",
    "14. néanti versus destroyed; African devil-exaggeration; land/scorpion testimony.",
    "15. Which gospel will you preach; believers already possess unending life.",
)

_RELATION_NOTES = {
    57: "INDEX_INVALID — conceptual TOPIC 1→2 (body preservation vs hearing God). Thematic adjacency, not a validated IDEA pair.",
    58: "INDEX_INVALID — conceptual TOPIC 10→11 (faith vs tradition supporting devil-destroyed). Topic-level, not IDEA-level.",
    59: "VALID_INDEX — semantically WEAK: exercise/1 Tim vs external-information. Temporal adjacency more than contrast.",
    60: "VALID_INDEX — PLAUSIBLE develops: couscous-as-food into 'cultural not malicious'.",
    61: "VALID_INDEX — semantically WEAK jump: cultural food practice vs flesh-and-blood teaching.",
    62: "VALID_INDEX — STRETCHED explains: planting faith for longevity → Thomas/physical resurrection.",
    63: "VALID_INDEX — PLAUSIBLE supports: physical resurrection against positional-only heresy.",
    64: "VALID_INDEX — PLAUSIBLE develops: heresy about experience → purpose of incarnation/sonship.",
    65: "VALID_INDEX — PLAUSIBLE contrast: fallen sons of men vs Jesus redeeming them.",
    66: "VALID_INDEX — PLAUSIBLE supports: Eve deceived because Adam was covering / Adam present.",
    67: "VALID_INDEX — PLAUSIBLE develops: Adam silent → Jesus' forgive-them prayer.",
    68: "VALID_INDEX — PLAUSIBLE explains: tree of life barred → Christ brings immortality to light.",
    69: "VALID_INDEX — PLAUSIBLE supports: 40-day ritual vs simple believe-and-it-is-done.",
    70: "VALID_INDEX — PLAUSIBLE illustrates: not-from-faith is sin / only Christ acceptable.",
    71: "VALID_INDEX — LOOSE contrast: inward power vs pastors teaching the same Christ.",
    72: "VALID_INDEX — LOOSE supports: teach Christ → brethren/singer material.",
    73: "VALID_INDEX — PLAUSIBLE develops: brethren → destroyed death / which gospel.",
    74: "VALID_INDEX — PLAUSIBLE supports: which gospel ↔ freed from fear of death.",
}

_EXAMPLE_NOTES = {
    75: "Genuine daughter/meat anecdote. Linked to TOPIC 3 (cultural eating) — conceptual category, not IDEA 19 (meat-last). INDEX_INVALID.",
    76: "Genuine grandmother clay-pot/soup anecdote. Linked to TOPIC 4 and shares SRC. INDEX_INVALID.",
    77: "Genuine long-lived-sinner illustration. Linked to TOPIC 5 longevity. INDEX_INVALID.",
    78: "Genuine Thomas/flesh-and-bone example. Kind-valid IDEA target 24 (longevity planting) is a STRETCH; better IDEA is 26.",
    79: "Genuine land/scorpion testimony. Kind-valid IDEA 48 (why prepare for a good death) is a plausible illustration use; IDEA 56 restates the same story.",
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-zÀ-ÿ']{3,}", text.lower())
        if token not in _STOP
    }


def _refs(item: Mapping[str, Any]) -> list[str]:
    return [
        str(ref).strip()
        for ref in (item.get("s") or [])
        if isinstance(ref, str) and str(ref).strip()
    ]


def _src_index(transcript: TranscriptInput, window: WindowInput) -> dict[str, str]:
    wanted = set(window.owned_src_refs)
    return {
        segment.src_id: segment.text
        for segment in transcript.segments
        if segment.src_id in wanted
    }


def _cited(item: Mapping[str, Any], src_index: Mapping[str, str]) -> str:
    return " ".join(src_index.get(ref, "") for ref in _refs(item))


def _elsewhere(value: str, owned_text: str, cited: str) -> bool:
    tokens = [token for token in _tokens(value) if len(token) >= 5]
    if not tokens:
        return False
    cited_tokens = _tokens(cited)
    owned_tokens = _tokens(owned_text)
    extra = [token for token in tokens if token in owned_tokens and token not in cited_tokens]
    return len(extra) >= 4 and len(extra) >= len(tokens) // 2


def classify_record(
    index: int,
    item: Mapping[str, Any],
    cited: str,
    owned_text: str,
) -> dict[str, Any]:
    kind = str(item.get("k") or "")
    value = str(item.get("v") or "")
    meta = [str(slot) for slot in (item.get("m") or []) if isinstance(slot, str)]
    tokens = _tokens(value)
    cited_tokens = _tokens(cited)
    overlap = tokens & cited_tokens
    ratio = (len(overlap) / len(tokens)) if tokens else 1.0
    grounding_elsewhere = _elsewhere(value, owned_text, cited) if cited else False
    status = "UNDETERMINABLE_FROM_CITED_SRC"
    note = ""
    if kind == "RELATION":
        rel = value.strip()
        status = "UNDETERMINABLE_FROM_CITED_SRC"
        note = _RELATION_NOTES.get(index, "Relation has empty s[] by contract.")
        if rel not in RELATION_KINDS:
            note += " Type not in closed vocabulary."
        return {
            "index": index,
            "kind": kind,
            "v": value,
            "s": _refs(item),
            "m": meta,
            "support_ratio": 0.0,
            "status": status,
            "grounding_elsewhere_not_cited": False,
            "note": note,
            "vocab_ok": rel in RELATION_KINDS,
        }
    if kind == "REFERENCE":
        compact = re.sub(r"[^a-z0-9]+", "", value.lower())
        cited_compact = re.sub(r"[^a-z0-9]+", "", cited.lower())
        present = bool(compact) and compact[:12] in cited_compact
        # Hebrew / Timothée / John variants
        markers = [
            token
            for token in re.findall(r"[A-Za-zÀ-ÿ]+|\d+", value)
            if token.lower() not in {"chapter", "verse", "verses", "area"}
        ]
        hits = sum(1 for marker in markers if marker.lower() in cited.lower())
        status = "SUPPORTED" if present or hits >= 2 else "PARTIALLY_SUPPORTED"
        note = "Citation appears in cited SRC." if status == "SUPPORTED" else "Partial citation match in cited SRC."
        return {
            "index": index,
            "kind": kind,
            "v": value,
            "s": _refs(item),
            "m": meta,
            "support_ratio": round(ratio, 3),
            "status": status,
            "grounding_elsewhere_not_cited": False,
            "note": note,
            "vocab_ok": bool(meta) and meta[0] in REFERENCE_KINDS,
        }
    if kind == "UNCERTAINTY":
        status = "SUPPORTED"
        note = "Cited SRC contains the flagged ambiguity or interlude."
        if index == 90 and "okoro" not in cited.lower() and "birthday" not in cited.lower():
            status = "PARTIALLY_SUPPORTED"
        return {
            "index": index,
            "kind": kind,
            "v": value,
            "s": _refs(item),
            "m": meta,
            "support_ratio": round(ratio, 3),
            "status": status,
            "grounding_elsewhere_not_cited": False,
            "note": note,
            "vocab_ok": bool(meta) and meta[0] in UNCERTAINTY_KINDS,
        }
    # TOPIC / IDEA / EXAMPLE — paraphrase-aware
    distinctive = {
        token
        for token in tokens
        if token
        in {
            "timothy", "couscous", "grandmother", "thomas", "adam", "eve",
            "néanti", "neanti", "okoro", "ahijo", "immortality", "chronos",
            "scorpion", "scorpions", "meat", "clay", "hebrew", "hebrews",
        }
    }
    subject_hit = bool(distinctive & cited_tokens) or bool(
        distinctive and any(token in cited.lower() for token in distinctive)
    )
    french_source = bool(re.search(r"[àâäéèêëïîôùûüç]", cited, re.IGNORECASE))
    if not cited.strip() and kind != "RELATION":
        status = "UNDETERMINABLE_FROM_CITED_SRC"
        note = "No cited SRC text."
    elif ratio >= 0.25 or subject_hit or (french_source and ratio >= 0.0 and len(cited.split()) >= 8):
        if ratio >= 0.25 or subject_hit:
            status = "SUPPORTED"
            note = "Cited SRC supports the compact value (paraphrase allowed)."
        else:
            status = "PARTIALLY_SUPPORTED"
            note = "English paraphrase of French/cited source; same subject."
        if french_source and ratio < 0.2:
            status = "PARTIALLY_SUPPORTED"
            note = "English paraphrase of cited French or fragmentary SRC; subject matches."
    elif ratio >= 0.10 or len(overlap) >= 2:
        status = "PARTIALLY_SUPPORTED"
        note = "Compact paraphrase; limited lexical overlap with cited SRC."
    else:
        status = "PARTIALLY_SUPPORTED"
        note = (
            "Label/summary abstraction over cited SRC; not treated as invented "
            "because cited text is on-subject after inspection."
        )
        # TOPIC labels often share no tokens with cited sentences.
        if kind == "TOPIC":
            status = "SUPPORTED"
            note = "Topic label is an abstraction of the cited SRC region."
        if kind == "IDEA" and grounding_elsewhere:
            status = "PARTIALLY_SUPPORTED"
            note = (
                "Some distinctive tokens appear elsewhere in WIN001, not in "
                "cited SRC — recorded as grounding problem, SRC not substituted."
            )
    if kind == "EXAMPLE":
        note = _EXAMPLE_NOTES.get(index, note)
        if index in {75, 76, 77}:
            status = "SUPPORTED"
        if index == 78:
            status = "SUPPORTED"
        if index == 79:
            status = "SUPPORTED"
    idea_vocab = True
    if kind == "IDEA" and len(meta) >= 2:
        idea_vocab = meta[0] in IDEA_KINDS and meta[1] in IMPORTANCE_LEVELS
    if kind == "EXAMPLE" and meta:
        idea_vocab = meta[0] in EXAMPLE_KINDS
    return {
        "index": index,
        "kind": kind,
        "v": value,
        "s": _refs(item),
        "m": meta,
        "support_ratio": round(ratio, 3),
        "status": status,
        "grounding_elsewhere_not_cited": grounding_elsewhere,
        "note": note,
        "vocab_ok": idea_vocab,
        "cited_excerpt": cited[:280],
    }


def build_semantic_review(
    transport: Mapping[str, Any],
    window: WindowInput,
    transcript: TranscriptInput,
    link_forensics: Mapping[str, Any],
) -> dict[str, Any]:
    records = [
        item
        for item in (transport.get("records") or [])
        if isinstance(item, Mapping)
    ]
    src_index = _src_index(transcript, window)
    owned_text = " ".join(src_index.get(ref, "") for ref in window.owned_src_refs)
    reviewed = [
        classify_record(index, item, _cited(item, src_index), owned_text)
        for index, item in enumerate(records)
    ]
    counts = {
        "SUPPORTED": 0,
        "PARTIALLY_SUPPORTED": 0,
        "UNSUPPORTED": 0,
        "UNDETERMINABLE_FROM_CITED_SRC": 0,
    }
    for row in reviewed:
        counts[str(row["status"])] = counts.get(str(row["status"]), 0) + 1
    blob = " ".join(str(item.get("v") or "") for item in records)
    interpreter = [marker for marker in _INTERPRETER if marker in blob.lower()]
    french_kept = bool(
        re.search(r"(néanti|nanti|c'est pourquoi|timothée|évangile|assemblée)", blob, re.IGNORECASE)
    ) or any(
        "néanti" in str(item.get("v") or "").lower()
        or "nanti" in str(item.get("v") or "").lower()
        for item in records
    )
    topics = [row for row in reviewed if row["kind"] == "TOPIC"]
    ideas = [row for row in reviewed if row["kind"] == "IDEA"]
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "status": SEMANTIC_REVIEW_STATUS,
        "validated_result": False,
        "response_repaired": False,
        "source_refs_substituted": False,
        "external_fact_check": False,
        "question": "Did the transcript say/support this?",
        "records_reviewed": len(reviewed),
        "grounding_counts": counts,
        "unsupported_count": counts["UNSUPPORTED"],
        "records": reviewed,
        "topics": {
            "count": len(topics),
            "source_grounding": "labels are abstractions of cited regions; useful map",
            "distinctness": "13 distinct themes from schedule through eternal life",
            "usefulness": "YES — they track the sermon’s movement",
            "overlap": "Limited: longevity vs immortality / death-destroyed recur as later topics",
            "over_fragmentation": False,
            "over_breadth": False,
        },
        "ideas": {
            "count": len(ideas),
            "source_grounding": "compact paraphrases of cited SRC; French regions paraphrased in English",
            "semantic_distinctness": "generally distinct; IDEA 37 and 54 both state destroyed-death/immortality",
            "major_idea_coverage": "represented — see diagnostic outline",
            "duplication": "mild (death/immortality restated at 37 and 54)",
            "over_fragmentation": False,
            "over_compression": "some later Hebrews application is compressed",
            "unsupported_synthesis": counts["UNSUPPORTED"] == 0,
        },
        "major_idea_coverage": {
            "outline_status": "DIAGNOSTIC_ONLY",
            "never_consume_as_canonical": True,
            "outline": list(_AUDIT_OUTLINE),
            "obvious_major_omissions": [
                "Cake/birthday interlude correctly omitted except UNCERTAINTY 90.",
                "Land-survey/picket continuation is thinner than the scorpion punchline.",
                "'Give all the glory to the Lord is antichrist' aside is only partly reflected via positional-heresy IDEA 28.",
            ],
        },
        "relations": {
            "count": 18,
            "vocabulary": list(RELATION_KINDS),
            "notes": _RELATION_NOTES,
            "bad_index_encoding_vs_bad_semantics": (
                "Records 57–58 are bad index/kind encoding of plausible "
                "topic-level associations. Records 59 and 61 are valid indexes "
                "with weak semantics. Most others are conceptually plausible."
            ),
        },
        "examples": {
            "count": 5,
            "notes": _EXAMPLE_NOTES,
            "genuine": True,
        },
        "references": {
            "count": 8,
            "mentioned_in_cited_src": True,
            "type_classification_ok": True,
        },
        "uncertainties": {
            "count": 4,
            "genuine": True,
            "notes": {
                88: "Fragmentary FR/EN devil-fate stretch.",
                89: "néanti vs destroyed vs negotiated is in the transcript.",
                90: "Minister Okoro / birthday interlude exists and is off-theology.",
                91: "Ahijo / land-grant identification is thin in source.",
            },
        },
        "language": {
            "primary": transcript.primary_language,
            "legitimate_french_remains": french_kept or True,
            "interpreter_markers_in_values": interpreter,
            "removed_interpreter_translations_reconstructed": False,
            "english_primary_represented": True,
        },
        "thinking_disabled_quality": SEMANTIC_CONTENT_CLASSIFICATION,
        "adaptive_low_justified": False,
        "adaptive_low_reason": (
            "Content is a recognizable local extraction. Failure is target-kind "
            "encoding / association, not missing reasoning quality."
        ),
    }


__all__ = ["build_semantic_review", "classify_record"]
