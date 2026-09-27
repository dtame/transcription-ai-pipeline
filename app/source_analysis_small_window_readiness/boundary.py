"""Revue offline des 6 frontières small-window. Aucun dump massif."""

from __future__ import annotations

from typing import Any, Sequence

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowPlan

_SENTENCE_END = (".", "!", "?", "…", '."', '!"', '?"', ".'", "!'", "?'")
_CONTINUATION_END = (",", ";", ":", "—", "–", "-", "(")
_CONJUNCTIONS = frozenset(
    {
        "and",
        "but",
        "or",
        "that",
        "which",
        "because",
        "so",
        "then",
        "when",
        "if",
        "as",
        "while",
        "although",
        "though",
        "with",
    }
)
_NEIGHBORHOOD = 8


def _segment_map(transcript: TranscriptInput) -> dict[str, str]:
    return {segment.src_id: segment.text for segment in transcript.segments}


def _ends_sentence(text: str) -> bool:
    stripped = text.rstrip()
    return any(stripped.endswith(token) for token in _SENTENCE_END)


def _classify(left_text: str, right_text: str) -> str:
    left = left_text.strip()
    right = right_text.strip()
    last_word = left.split()[-1].strip("\"'()[]").lower() if left.split() else ""
    ends_continuation = left.endswith(_CONTINUATION_END) or last_word in _CONJUNCTIONS
    starts_lower = bool(right) and right[0].islower()
    if ends_continuation or (starts_lower and not _ends_sentence(left)):
        return "CLEAR_SEMANTIC_SPLIT"
    if not _ends_sentence(left):
        return "POSSIBLE_SEMANTIC_SPLIT"
    return "CLEAN_BOUNDARY"


def _neighborhood(
    src_ids: Sequence[str],
    texts: dict[str, str],
    *,
    tail: bool,
    limit: int = _NEIGHBORHOOD,
) -> list[dict[str, Any]]:
    chosen = list(src_ids[-limit:] if tail else src_ids[:limit])
    rows: list[dict[str, Any]] = []
    for src in chosen:
        text = texts.get(src, "")
        rows.append(
            {
                "src_id": src,
                "word_count": len(text.split()),
                "ends_sentence": _ends_sentence(text),
                "preview": text[:48].replace("\n", " "),
            }
        )
    return rows


def review_boundaries(transcript: TranscriptInput, plan: WindowPlan) -> dict[str, Any]:
    texts = _segment_map(transcript)
    pairs: list[dict[str, Any]] = []
    windows = list(plan.windows)
    for left, right in zip(windows, windows[1:]):
        left_text = texts.get(left.last_owned_src_ref, "")
        right_text = texts.get(right.first_owned_src_ref, "")
        classification = _classify(left_text, right_text)
        pairs.append(
            {
                "boundary": f"{left.window_id}/{right.window_id}",
                "left_window": left.window_id,
                "right_window": right.window_id,
                "left_last_src": left.last_owned_src_ref,
                "right_first_src": right.first_owned_src_ref,
                "classification": classification,
                "left_ends_sentence": _ends_sentence(left_text),
                "right_starts_lower": bool(right_text) and right_text[0].islower(),
                "left_neighborhood": _neighborhood(left.owned_src_refs, texts, tail=True),
                "right_neighborhood": _neighborhood(
                    right.owned_src_refs, texts, tail=False
                ),
                "technical_only": True,
            }
        )
    counts = {
        "CLEAN_BOUNDARY": 0,
        "POSSIBLE_SEMANTIC_SPLIT": 0,
        "CLEAR_SEMANTIC_SPLIT": 0,
    }
    for pair in pairs:
        counts[str(pair["classification"])] += 1
    frequent_clear = counts["CLEAR_SEMANTIC_SPLIT"] >= 3
    none_defensible = not frequent_clear
    return {
        "context_policy": "NONE",
        "boundaries": pairs,
        "counts": counts,
        "frequent_clear_splits": frequent_clear,
        "none_context_defensible": none_defensible,
        "overlap_added": False,
        "windows_are_not_chapters": True,
        "summary": (
            "NONE remains ready"
            if none_defensible
            else "CLEAR splits frequent — BLOCKED pending context-policy design"
        ),
    }


__all__ = ["review_boundaries"]
