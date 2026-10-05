"""
Conservative deterministic segmentation prototype.

Does not call a provider. Does not judge semantic fidelity. Does not invent
evidence. Does not mutate the paragraph. Offsets are Unicode code points
(Python 3 str indices). Experimental and isolated from production.
"""

from __future__ import annotations

import re
from typing import Any

from app.book_semantic_gate_4b28.constants import PHASE

WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’][0-9A-Za-zÀ-ÖØ-öø-ÿ]+)*")

CONNECTOR_TOKENS = (
    "because",
    "unless",
    "however",
    "therefore",
    "thus",
    "although",
    "which means",
    "and so",
    "not",
    "never",
    "no",
    "if",
    "but",
)

# Known abbreviations. A period after these is not a sentence boundary.
ABBREVIATIONS = frozenset(
    {
        "mr",
        "mrs",
        "ms",
        "dr",
        "vs",
        "etc",
        "eg",
        "ie",
        "cf",
        "al",
        "gen",
        "ex",
        "lev",
        "num",
        "deut",
        "ps",
        "prov",
        "isa",
        "jer",
        "matt",
        "mt",
        "mk",
        "lk",
        "jn",
        "rom",
        "cor",
        "gal",
        "eph",
        "phil",
        "col",
        "thess",
        "tim",
        "tit",
        "heb",
        "jas",
        "pet",
        "rev",
        "ch",
        "vol",
        "pp",
        "no",
        "st",
        "jr",
        "sr",
        "corinthians",
    }
)

# (marker, kind, split_offset_into_marker). Connectives stay with the next unit.
CLAUSE_MARKERS: tuple[tuple[str, str, int], ...] = (
    (", which means ", "IMPLICATIVE_CONNECTIVE", 2),
    (", because ", "CAUSAL_CONNECTIVE", 2),
    (", although ", "ADVERSATIVE", 2),
    (", unless ", "CONDITIONAL", 2),
    (", and so ", "RESULT_CONNECTIVE", 2),
    (" because ", "CAUSAL_CONNECTIVE", 1),
    (" — ", "EM_DASH", 1),
    (" – ", "EN_DASH", 1),
    ("; ", "SEMICOLON", 2),
)

SENTENCE_TERMINATORS = frozenset({".", "?", "!"})
BOUNDARY_SENTENCE = "SENTENCE"
BOUNDARY_WHOLE = "WHOLE_PARAGRAPH"
BOUNDARY_AMBIGUOUS = "AMBIGUOUS"


def _unit_id(index: int) -> str:
    return f"u{index:02d}"


def _token_before_period(text: str, period_index: int) -> str:
    cursor = period_index - 1
    while cursor >= 0 and text[cursor].isalpha():
        cursor -= 1
    return text[cursor + 1 : period_index]


def _looks_like_abbreviation(text: str, period_index: int) -> bool:
    token = _token_before_period(text, period_index).lower()
    if not token:
        return False
    if token in ABBREVIATIONS:
        return True
    if len(token) == 1 and token.isalpha():
        return True
    return False


def _ellipsis_at(text: str, index: int) -> bool:
    if index + 2 < len(text) and text[index : index + 3] == "...":
        return True
    if index >= 2 and text[index - 2 : index + 1] == "...":
        return True
    if index >= 1 and index + 1 < len(text) and text[index - 1 : index + 2] == "...":
        return True
    return False


def _is_sentence_boundary(text: str, index: int) -> bool:
    if index < 0 or index >= len(text):
        return False
    char = text[index]
    if char not in SENTENCE_TERMINATORS:
        return False
    if char == "." and _looks_like_abbreviation(text, index):
        return False
    if char == "." and _ellipsis_at(text, index):
        return False
    nxt = index + 1
    if nxt >= len(text):
        return True
    while nxt < len(text) and text[nxt].isspace():
        nxt += 1
    if nxt >= len(text):
        return True
    following = text[nxt]
    if following.isupper() or following in {"“", "\"", "‘", "'"}:
        return True
    return False


def _next_unit_start_after_sentence(text: str, terminator_index: int) -> int:
    cursor = terminator_index + 1
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    return cursor


def find_sentence_starts(text: str) -> list[int]:
    starts = [0] if text else []
    index = 0
    while index < len(text):
        if _is_sentence_boundary(text, index):
            nxt = _next_unit_start_after_sentence(text, index)
            if 0 < nxt < len(text) and nxt not in starts:
                starts.append(nxt)
            index = max(index + 1, nxt)
            continue
        index += 1
    return starts


def _clause_splits_in_span(text: str, start: int, end: int) -> list[tuple[int, str]]:
    splits: list[tuple[int, str]] = []
    cursor = start
    while cursor < end:
        chosen: tuple[int, int, str] | None = None
        for marker, kind, offset in CLAUSE_MARKERS:
            found = text.find(marker, cursor, end)
            if found < 0:
                continue
            connective_start = found + offset
            if kind == "CAUSAL_CONNECTIVE":
                prefix = text[max(start, connective_start - 4) : connective_start].lower()
                if prefix.rstrip().endswith("not"):
                    continue
            if chosen is None or found < chosen[0] or (
                found == chosen[0] and offset > 0 and connective_start < chosen[1]
            ):
                chosen = (found, connective_start, kind)
        if chosen is None:
            break
        _found, connective_start, kind = chosen
        if start < connective_start < end:
            splits.append((connective_start, kind))
        cursor = connective_start + 1
    return splits


def _boundary_positions(text: str) -> list[tuple[int, str]]:
    if not text:
        return []
    sentence_starts = find_sentence_starts(text)
    positions: list[tuple[int, str]] = [(0, BOUNDARY_SENTENCE)]
    for start in sentence_starts[1:]:
        positions.append((start, BOUNDARY_SENTENCE))
    spans = sentence_starts + [len(text)]
    for left, right in zip(spans, spans[1:]):
        positions.extend(_clause_splits_in_span(text, left, right))
    unique: dict[int, str] = {}
    for index, kind in sorted(positions, key=lambda item: item[0]):
        if index < 0 or index >= len(text):
            continue
        unique.setdefault(index, kind)
    return sorted(unique.items(), key=lambda item: item[0])


def _mark_ambiguous(text: str, start: int, end: int, boundary_type: str) -> bool:
    snippet = text[start:end]
    if boundary_type == BOUNDARY_WHOLE:
        return True
    if not any(char in SENTENCE_TERMINATORS for char in snippet) and len(snippet) > 80:
        return True
    if "..." in snippet or "…" in snippet:
        return True
    lower = snippet.lower()
    if lower.startswith("how ") or lower.startswith("what ") or lower.startswith("why "):
        if snippet.rstrip().endswith("?"):
            return True
    if " — " in snippet and boundary_type == BOUNDARY_SENTENCE:
        return True
    return False


def _words(text: str) -> list[tuple[int, int, str]]:
    return [(match.start(), match.end(), match.group(0)) for match in WORD_RE.finditer(text)]


def _coverage_map(length: int, units: list[dict[str, Any]]) -> list[str]:
    mapping = [""] * length
    for unit in units:
        start = int(unit["start_offset"])
        end = int(unit["end_offset"])
        uid = str(unit["id"])
        for index in range(start, end):
            mapping[index] = uid
    return mapping


def _uncovered(mapping: list[str]) -> list[list[int]]:
    gaps: list[list[int]] = []
    gap_start: int | None = None
    for index, owner in enumerate(mapping):
        if not owner and gap_start is None:
            gap_start = index
        elif owner and gap_start is not None:
            gaps.append([gap_start, index])
            gap_start = None
    if gap_start is not None:
        gaps.append([gap_start, len(mapping)])
    return gaps


def _connector_coverage(text: str, units: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for token in CONNECTOR_TOKENS:
        lower = text.lower()
        start = 0
        occurrences = []
        while True:
            found = lower.find(token, start)
            if found < 0:
                break
            end = found + len(token)
            before_ok = found == 0 or not text[found - 1].isalnum()
            after_ok = end >= len(text) or not text[end].isalnum()
            if before_ok and after_ok:
                owners = {
                    str(unit["id"])
                    for unit in units
                    if int(unit["start_offset"]) <= found < int(unit["end_offset"])
                    and int(unit["start_offset"]) < end <= int(unit["end_offset"])
                }
                occurrences.append(
                    {
                        "token": token,
                        "start": found,
                        "end": end,
                        "fully_inside_one_unit": len(owners) == 1,
                        "owners": sorted(owners),
                    }
                )
            start = found + 1
        rows.extend(occurrences)
    fully = [item for item in rows if item["fully_inside_one_unit"]]
    return {
        "occurrences": rows,
        "present_count": len(rows),
        "fully_covered_count": len(fully),
        "split_across_units": [item for item in rows if not item["fully_inside_one_unit"]],
    }


def prepare_semantic_validation_units(paragraph: str) -> dict[str, Any]:
    """Partition a paragraph into conservative validation units.

    Returns identifiers, exact slices, Unicode offsets, boundary types, and
    a complete coverage map. Never judges fidelity. Never drops characters.
    """
    text = paragraph if isinstance(paragraph, str) else str(paragraph or "")
    if not text.strip():
        units = [
            {
                "id": _unit_id(0),
                "text": text,
                "start_offset": 0,
                "end_offset": len(text),
                "context": text,
                "boundary_type": BOUNDARY_WHOLE,
                "ambiguous": True,
            }
        ]
        conservative = True
        positions: list[tuple[int, str]] = [(0, BOUNDARY_WHOLE)]
    elif not any(char in SENTENCE_TERMINATORS or char in ";—–" for char in text):
        units = [
            {
                "id": _unit_id(0),
                "text": text,
                "start_offset": 0,
                "end_offset": len(text),
                "context": text,
                "boundary_type": BOUNDARY_WHOLE,
                "ambiguous": True,
            }
        ]
        conservative = True
        positions = [(0, BOUNDARY_WHOLE)]
    else:
        positions = _boundary_positions(text)
        if not positions:
            positions = [(0, BOUNDARY_WHOLE)]
        starts = [item[0] for item in positions] + [len(text)]
        kinds = [item[1] for item in positions]
        units = []
        for index, (start, end, kind) in enumerate(zip(starts, starts[1:], kinds)):
            snippet = text[start:end]
            ambiguous = _mark_ambiguous(text, start, end, kind)
            units.append(
                {
                    "id": _unit_id(index),
                    "text": snippet,
                    "start_offset": start,
                    "end_offset": end,
                    "context": text,
                    "boundary_type": kind,
                    "ambiguous": ambiguous,
                }
            )
        conservative = len(units) == 1 and kinds[0] in {BOUNDARY_WHOLE, BOUNDARY_AMBIGUOUS}

    mapping = _coverage_map(len(text), units)
    uncovered = _uncovered(mapping)
    reconstructed = "".join(unit["text"] for unit in units)
    words = _words(text)
    covered_words = []
    uncovered_words = []
    for start, end, token in words:
        owners = {
            mapping[index] for index in range(start, end) if 0 <= index < len(mapping)
        }
        if len(owners) == 1 and next(iter(owners)):
            covered_words.append(token)
        else:
            uncovered_words.append({"token": token, "start": start, "end": end})
    connectors = _connector_coverage(text, units)
    return {
        "phase": PHASE,
        "paragraph": text,
        "paragraph_unchanged": reconstructed == text,
        "units": units,
        "unit_count": len(units),
        "ambiguous_unit_count": sum(1 for unit in units if unit["ambiguous"]),
        "boundary_positions": [{"offset": offset, "type": kind} for offset, kind in positions],
        "coverage_map_owners": mapping,
        "coverage": {
            "char_count": len(text),
            "covered_chars": sum(1 for owner in mapping if owner),
            "uncovered_spans": uncovered,
            "word_count": len(words),
            "covered_word_count": len(covered_words),
            "uncovered_words": uncovered_words,
            "connector_coverage": connectors,
            "complete_chars": not uncovered and reconstructed == text,
            "complete_words": not uncovered_words,
        },
        "conservative_fallback": conservative,
        "offset_convention": "python3_str_unicode_code_points_half_open",
        "deterministic": True,
        "does_not_modify_paragraph": True,
        "does_not_drop_words": reconstructed == text,
        "does_not_invent_evidence": True,
        "does_not_judge_fidelity": True,
        "not_a_semantic_analysis": True,
        "evidence_level": "DETERMINISTICALLY_VERIFIED",
        "secrets_included": False,
    }


def unit_containing(result: dict[str, Any], start: int, end: int) -> dict[str, Any] | None:
    for unit in result.get("units") or []:
        if int(unit["start_offset"]) <= start and end <= int(unit["end_offset"]):
            return unit
    return None


def spans_preserved(result: dict[str, Any], spans: list[tuple[int, int, str]]) -> list[dict[str, Any]]:
    rows = []
    for start, end, label in spans:
        unit = unit_containing(result, start, end)
        rows.append(
            {
                "label": label,
                "start": start,
                "end": end,
                "preserved_in_one_unit": unit is not None,
                "unit_id": None if unit is None else unit["id"],
                "unit_text": None if unit is None else unit["text"],
                "evidence_level": "DETERMINISTICALLY_VERIFIED",
            }
        )
    return rows


__all__ = [
    "ABBREVIATIONS",
    "CLAUSE_MARKERS",
    "CONNECTOR_TOKENS",
    "prepare_semantic_validation_units",
    "spans_preserved",
    "unit_containing",
]
