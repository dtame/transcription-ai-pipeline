"""Candidats de doublons lexicaux cross-window. Heuristique offline. Pas de merge."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Mapping

from app.source_analysis_v31_global_preflight.constants import (
    MODE,
    PHASE,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_global_preflight.normalize import src_number

_WORD = re.compile(r"[a-z0-9]{4,}")
_STOP = frozenset(
    {
        "that",
        "this",
        "with",
        "from",
        "have",
        "they",
        "them",
        "their",
        "there",
        "about",
        "would",
        "could",
        "should",
        "because",
        "which",
        "when",
        "what",
        "your",
        "into",
        "just",
        "like",
        "been",
        "were",
        "will",
        "also",
        "some",
        "more",
        "than",
        "then",
        "them",
        "very",
        "really",
        "people",
        "thing",
        "things",
        "going",
        "know",
        "think",
        "want",
        "need",
        "make",
        "come",
        "came",
        "said",
        "says",
        "lord",
        "god",
        "jesus",
        "christ",
        "church",
        "spirit",
        "father",
        "holy",
        "amen",
        "yeah",
        "okay",
    }
)


def _norm_text(value: str) -> str:
    return " ".join(_WORD.findall(str(value or "").lower()))


def _terms(value: str) -> set[str]:
    return {word for word in _WORD.findall(str(value or "").lower()) if word not in _STOP}


def _similarity(left: str, right: str) -> tuple[float, float, list[str]]:
    a = _norm_text(left)
    b = _norm_text(right)
    ratio = SequenceMatcher(None, a, b).ratio() if a and b else 0.0
    ta, tb = _terms(left), _terms(right)
    jaccard = (len(ta & tb) / len(ta | tb)) if ta and tb else 0.0
    shared = sorted(ta & tb, key=len, reverse=True)[:8]
    return ratio, jaccard, shared


def _earliest(refs: list[str]) -> int:
    nums = [src_number(ref) for ref in refs]
    nums = [num for num in nums if num is not None]
    return min(nums) if nums else 10**9


def _classify(ratio: float, jaccard: float, shared: list[str], adjacent: bool) -> str:
    if ratio >= 0.82 or jaccard >= 0.65:
        return "LIKELY_SAME_IDEA"
    if adjacent and len(shared) >= 4:
        return "RELATED_BUT_DISTINCT"
    if ratio >= 0.55 and len(shared) >= 4:
        return "RELATED_BUT_DISTINCT"
    if (not adjacent) and (ratio >= 0.50 or jaccard >= 0.28) and len(shared) >= 4:
        return "REPETITION_IN_SOURCE"
    return "UNCERTAIN"


def _topic_groups(topics: list[Mapping[str, Any]]) -> dict[str, Any]:
    exact: dict[str, list[str]] = {}
    for item in topics:
        key = _norm_text(str(item.get("value") or ""))
        exact.setdefault(key, []).append(str(item.get("input_id")))
    exact_dupes = {key: ids for key, ids in exact.items() if key and len(ids) > 1}
    near: list[dict[str, Any]] = []
    hierarchical: list[dict[str, Any]] = []
    for i, left in enumerate(topics):
        lv = str(left.get("value") or "")
        ln = _norm_text(lv)
        for right in topics[i + 1 :]:
            if left.get("window_id") == right.get("window_id"):
                continue
            rv = str(right.get("value") or "")
            rn = _norm_text(rv)
            ratio, jaccard, shared = _similarity(lv, rv)
            if ln and rn and (ln in rn or rn in ln) and ln != rn:
                hierarchical.append(
                    {
                        "left": left.get("input_id"),
                        "right": right.get("input_id"),
                        "left_value": lv,
                        "right_value": rv,
                    }
                )
            elif ratio >= 0.72 or jaccard >= 0.55:
                near.append(
                    {
                        "left": left.get("input_id"),
                        "right": right.get("input_id"),
                        "ratio": round(ratio, 4),
                        "jaccard": round(jaccard, 4),
                        "shared_terms": shared,
                        "left_value": lv,
                        "right_value": rv,
                    }
                )
    return {
        "exact_duplicates": exact_dupes,
        "near_duplicates": near[:40],
        "hierarchical_overlaps": hierarchical[:40],
        "topic_count": len(topics),
        "do_not_promote_local_topic_ids": True,
    }


def build_duplicate_candidates(normalized: Mapping[str, Any]) -> dict[str, Any]:
    records = list(normalized.get("all_records") or [])
    ideas = [item for item in records if item.get("kind") == "IDEA"]
    topics = [item for item in records if item.get("kind") == "TOPIC"]
    pairs: list[dict[str, Any]] = []
    for i, left in enumerate(ideas):
        for right in ideas[i + 1 :]:
            if left.get("window_id") == right.get("window_id"):
                continue
            ratio, jaccard, shared = _similarity(
                str(left.get("value") or ""), str(right.get("value") or "")
            )
            left_last = max(
                [src_number(ref) or 0 for ref in left.get("source_refs") or []] or [0]
            )
            right_first = _earliest(list(right.get("source_refs") or []))
            adjacent = abs(right_first - left_last) <= 80
            keep = (
                (len(shared) >= 4 and jaccard >= 0.20)
                or (ratio >= 0.42 and len(shared) >= 3)
                or (adjacent and len(shared) >= 3)
                or (ratio >= 0.55)
            )
            if not keep:
                continue
            classification = _classify(ratio, jaccard, shared, adjacent)
            pairs.append(
                {
                    "left_id": left.get("input_id"),
                    "right_id": right.get("input_id"),
                    "left_window": left.get("window_id"),
                    "right_window": right.get("window_id"),
                    "ratio": round(ratio, 4),
                    "jaccard": round(jaccard, 4),
                    "shared_distinctive_terms": shared,
                    "adjacent_boundary": adjacent,
                    "classification": classification,
                    "proof_of_duplication": False,
                    "left_value": left.get("value"),
                    "right_value": right.get("value"),
                    "left_src": list(left.get("source_refs") or []),
                    "right_src": list(right.get("source_refs") or []),
                }
            )
    pairs.sort(key=lambda row: (-row["ratio"], -row["jaccard"], row["left_id"], row["right_id"]))
    high = [row for row in pairs if row["classification"] == "LIKELY_SAME_IDEA"]
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "method": "deterministic_lexical_and_source_position",
        "llm_used": False,
        "merged": False,
        "candidates_modified": False,
        "idea_count": len(ideas),
        "candidate_pair_count": len(pairs),
        "pairs": pairs[:80],
        "high_confidence": high[:30],
        "classification_counts": {
            label: sum(1 for row in pairs if row["classification"] == label)
            for label in (
                "LIKELY_SAME_IDEA",
                "RELATED_BUT_DISTINCT",
                "REPETITION_IN_SOURCE",
                "UNCERTAIN",
            )
        },
        "topics": _topic_groups(topics),
        "repetition_design": {
            "local_lite_deferred_repetition": True,
            "global_must_identify_genuine_source_recurrence": True,
            "must_not_delete_meaningful_recurrence": True,
            "must_cite_all_relevant_src": True,
            "generated_in_a34": False,
        },
    }


__all__ = ["build_duplicate_candidates"]
