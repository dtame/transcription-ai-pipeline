"""Revue sémantique offline A.38. Aucun LLM. Aucune réparation provider."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Mapping

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_v31_global_real_consolidation.constants import (
    BEGINNING_WINDOWS,
    CROSS_WINDOW_BOUNDARIES,
    DROP_REASON_CODES,
    END_WINDOWS,
    EXPECTED_DISTINCT_SRC,
    EXPECTED_IDEA,
    MIDDLE_WINDOWS,
    READY_WINDOWS,
    RELATION_QUALITY_TECHNICAL_DEBT,
)
from app.source_analysis_v31_global_real_consolidation.input_contract import (
    idea_records,
    local_src_by_input,
)

_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ0-9']{4,}")
_FILLER = {
    "alors",
    "donc",
    "voila",
    "voilà",
    "puis",
    "then",
    "yeah",
    "okay",
    "ok",
    "well",
    "like",
    "just",
    "really",
    "very",
    "that",
    "this",
    "avec",
    "dans",
    "pour",
    "plus",
}
_UNIVERSALS = {"always", "never", "all", "every", "everyone", "nobody", "toujours", "jamais", "tous", "toutes"}


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN_RE.findall(text or "")
        if token.lower() not in _FILLER
    }


def _overlap(left: set[str], right: set[str]) -> float:
    if not left:
        return 0.0
    return len(left & right) / len(left)


def _src_text(transcript: TranscriptInput, refs: list[str]) -> str:
    index = {segment.src_id: segment.text for segment in transcript.segments}
    return " ".join(index.get(ref, "") for ref in refs)


def _window_for_src(normalized: Mapping[str, Any], ref: str) -> str | None:
    for window_id, row in (normalized.get("windows") or {}).items():
        first, last = row.get("owned_src_range") or (0, 0)
        try:
            number = int(str(ref).removeprefix("SRC"))
        except ValueError:
            continue
        if int(first) <= number <= int(last):
            return window_id
    return None


def _windows_for_refs(normalized: Mapping[str, Any], refs: list[str]) -> set[str]:
    found = set()
    for ref in refs:
        window_id = _window_for_src(normalized, ref)
        if window_id:
            found.add(window_id)
    return found


def review_drops(
    transport: Mapping[str, Any],
    normalized: Mapping[str, Any],
) -> dict[str, Any]:
    local = {item["input_id"]: item for item in idea_records(dict(normalized))}
    nodes = {
        str(node.get("h") or ""): node
        for node in (transport.get("n") or [])
        if isinstance(node, dict)
    }
    surviving_texts = [
        _tokens(str(node.get("v") or ""))
        for node in nodes.values()
        if node.get("k") == "IDEA"
    ]
    rows: list[dict[str, Any]] = []
    counts = {code: 0 for code in DROP_REASON_CODES}
    classes = {
        "VALID_EXACT_DUPLICATE": 0,
        "VALID_TRANSPORT_ARTIFACT": 0,
        "VALID_NON_SUBSTANTIVE_FRAGMENT": 0,
        "QUESTIONABLE": 0,
        "INVALID": 0,
    }
    for disp in transport.get("d") or []:
        if not isinstance(disp, dict) or disp.get("o") != "DROP":
            continue
        input_id = str(disp.get("i") or "")
        reason = str(disp.get("w") or "")
        if input_id not in local:
            continue
        if reason in counts:
            counts[reason] += 1
        record = local[input_id]
        text = str(record.get("value") or "")
        tokens = _tokens(text)
        word_count = len(text.split())
        best = max((_overlap(tokens, other) for other in surviving_texts), default=0.0)
        classification = "QUESTIONABLE"
        if reason == "exact_duplicate":
            classification = "VALID_EXACT_DUPLICATE" if best >= 0.55 else (
                "INVALID" if best < 0.20 and word_count >= 8 else "QUESTIONABLE"
            )
        elif reason == "transport_artifact":
            if word_count <= 3 or not tokens:
                classification = "VALID_TRANSPORT_ARTIFACT"
            elif word_count >= 10 and len(tokens) >= 5:
                classification = "INVALID"
            else:
                classification = "QUESTIONABLE"
        elif reason == "non_substantive_fragment":
            if word_count <= 6 or len(tokens) <= 2:
                classification = "VALID_NON_SUBSTANTIVE_FRAGMENT"
            elif word_count >= 12 and len(tokens) >= 6:
                classification = "INVALID"
            else:
                classification = "QUESTIONABLE"
        classes[classification] += 1
        rows.append(
            {
                "input_id": input_id,
                "window_id": record.get("window_id"),
                "reason": reason,
                "classification": classification,
                "word_count": word_count,
                "best_surviving_overlap": round(best, 3),
                "value": text,
                "source_refs": list(record.get("source_refs") or []),
            }
        )
    invalid = [row for row in rows if row["classification"] == "INVALID"]
    return {
        "count": len(rows),
        "by_reason": counts,
        "classifications": classes,
        "rows": rows,
        "invalid": invalid,
        "status": "FAIL" if invalid else "PASS",
    }


def review_others(
    transport: Mapping[str, Any],
    normalized: Mapping[str, Any],
) -> dict[str, Any]:
    local = {item["input_id"]: item for item in idea_records(dict(normalized))}
    nodes = {
        str(node.get("h") or ""): node
        for node in (transport.get("n") or [])
        if isinstance(node, dict)
    }
    rows: list[dict[str, Any]] = []
    hidden = 0
    for disp in transport.get("d") or []:
        if not isinstance(disp, dict) or disp.get("o") != "OTHER":
            continue
        input_id = str(disp.get("i") or "")
        if input_id not in local:
            continue
        record = local[input_id]
        handle = str(disp.get("g") or "")
        node = nodes.get(handle)
        kind = str(node.get("k") or "") if node else ""
        represented = bool(node) and kind in {"TOPIC", "EXAMPLE", "REFERENCE", "UNCERTAINTY"}
        if not represented:
            hidden += 1
        overlap = _overlap(_tokens(str(record.get("value") or "")), _tokens(str((node or {}).get("v") or "")))
        rows.append(
            {
                "input_id": input_id,
                "window_id": record.get("window_id"),
                "g": handle,
                "target_kind": kind,
                "represented": represented,
                "overlap": round(overlap, 3),
                "value": record.get("value"),
                "target_value": (node or {}).get("v"),
                "hides_disappearance": not represented,
            }
        )
    return {
        "count": len(rows),
        "rows": rows,
        "hidden_disappearances": hidden,
        "status": "FAIL" if hidden else "PASS",
    }


def review_merges(
    transport: Mapping[str, Any],
    normalized: Mapping[str, Any],
) -> dict[str, Any]:
    local = {item["input_id"]: item for item in idea_records(dict(normalized))}
    nodes = {
        str(node.get("h") or ""): node
        for node in (transport.get("n") or [])
        if isinstance(node, dict)
    }
    groups: dict[str, list[str]] = defaultdict(list)
    for disp in transport.get("d") or []:
        if not isinstance(disp, dict) or disp.get("o") != "MERGE_EQUIVALENT":
            continue
        input_id = str(disp.get("i") or "")
        handle = str(disp.get("g") or "")
        if input_id in local and handle:
            groups[handle].append(input_id)
    rows: list[dict[str, Any]] = []
    classes = {
        "VALID_EQUIVALENT_MERGE": 0,
        "QUESTIONABLE_MERGE": 0,
        "INVALID_MERGE": 0,
    }
    for handle, input_ids in groups.items():
        texts = [_tokens(str(local[item].get("value") or "")) for item in input_ids if item in local]
        pairs: list[float] = []
        for index, left in enumerate(texts):
            for right in texts[index + 1 :]:
                if left or right:
                    pairs.append(min(_overlap(left, right), _overlap(right, left)))
        worst = min(pairs) if pairs else 0.0
        if len(input_ids) < 2:
            classification = "INVALID_MERGE"
        elif worst >= 0.40:
            classification = "VALID_EQUIVALENT_MERGE"
        elif worst < 0.15:
            classification = "INVALID_MERGE"
        else:
            classification = "QUESTIONABLE_MERGE"
        classes[classification] += 1
        node = nodes.get(handle) or {}
        rows.append(
            {
                "global_handle": handle,
                "input_ids": input_ids,
                "member_count": len(input_ids),
                "worst_pairwise_overlap": round(worst, 3),
                "classification": classification,
                "global_value": node.get("v"),
                "local_values": [local[item].get("value") for item in input_ids if item in local],
                "windows": sorted(
                    {local[item].get("window_id") for item in input_ids if item in local}
                ),
            }
        )
    invalid = [row for row in rows if row["classification"] == "INVALID_MERGE"]
    return {
        "group_count": len(rows),
        "classifications": classes,
        "rows": rows,
        "invalid": invalid,
        "status": "FAIL" if invalid else "PASS",
    }


def review_global_ideas(
    transport: Mapping[str, Any],
    normalized: Mapping[str, Any],
    transcript: TranscriptInput,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    counts = {
        "SUPPORTED": 0,
        "PARTIALLY_SUPPORTED": 0,
        "UNSUPPORTED": 0,
        "UNDETERMINABLE": 0,
    }
    for node in transport.get("n") or []:
        if not isinstance(node, dict) or node.get("k") != "IDEA":
            continue
        text = str(node.get("v") or "")
        refs = [str(item) for item in (node.get("s") or []) if isinstance(item, str)]
        src_text = _src_text(transcript, refs)
        idea_tokens = _tokens(text)
        src_tokens = _tokens(src_text)
        overlap = _overlap(idea_tokens, src_tokens)
        universals = sorted(token for token in _UNIVERSALS if token in idea_tokens and token not in src_tokens)
        if not idea_tokens:
            classification = "UNDETERMINABLE"
        elif overlap >= 0.42 and not universals:
            classification = "SUPPORTED"
        elif overlap >= 0.22 or (overlap >= 0.15 and universals):
            classification = "PARTIALLY_SUPPORTED"
        elif overlap < 0.10 and len(idea_tokens) >= 5:
            classification = "UNSUPPORTED"
        else:
            classification = "UNDETERMINABLE"
        counts[classification] += 1
        rows.append(
            {
                "handle": node.get("h"),
                "value": text,
                "source_refs": refs,
                "overlap": round(overlap, 3),
                "lost_universals": universals,
                "classification": classification,
                "windows": sorted(_windows_for_refs(normalized, refs)),
            }
        )
    unsupported = [row for row in rows if row["classification"] == "UNSUPPORTED"]
    return {
        "count": len(rows),
        "classifications": counts,
        "rows": rows,
        "unsupported": unsupported,
        "status": "FAIL" if unsupported else "PASS",
    }


def review_relations(
    transport: Mapping[str, Any],
    transcript: TranscriptInput,
) -> dict[str, Any]:
    nodes = {
        str(node.get("h") or ""): node
        for node in (transport.get("n") or [])
        if isinstance(node, dict)
    }
    rows: list[dict[str, Any]] = []
    counts = {
        "WELL_SUPPORTED": 0,
        "PLAUSIBLE_LOOSE": 0,
        "INCORRECT": 0,
        "UNVERIFIABLE": 0,
    }
    for index, rel in enumerate(transport.get("r") or []):
        if not isinstance(rel, dict):
            continue
        left = nodes.get(str(rel.get("a") or ""))
        right = nodes.get(str(rel.get("b") or ""))
        refs = [str(item) for item in (rel.get("s") or []) if isinstance(item, str)]
        src_text = _src_text(transcript, refs)
        if left is None or right is None:
            classification = "INCORRECT"
        elif not refs:
            classification = "UNVERIFIABLE"
        else:
            left_tokens = _tokens(str(left.get("v") or ""))
            right_tokens = _tokens(str(right.get("v") or ""))
            src_tokens = _tokens(src_text)
            left_overlap = _overlap(left_tokens, src_tokens)
            right_overlap = _overlap(right_tokens, src_tokens)
            pair_overlap = min(_overlap(left_tokens, right_tokens), _overlap(right_tokens, left_tokens))
            if left_overlap >= 0.25 and right_overlap >= 0.25:
                classification = "WELL_SUPPORTED"
            elif left_overlap >= 0.12 or right_overlap >= 0.12 or pair_overlap >= 0.18:
                classification = "PLAUSIBLE_LOOSE"
            elif left_overlap < 0.05 and right_overlap < 0.05 and pair_overlap < 0.08:
                classification = "UNVERIFIABLE"
            else:
                classification = "PLAUSIBLE_LOOSE"
        counts[classification] += 1
        rows.append(
            {
                "index": index,
                "type": rel.get("t"),
                "a": rel.get("a"),
                "b": rel.get("b"),
                "source_refs": refs,
                "classification": classification,
                "left_value": (left or {}).get("v"),
                "right_value": (right or {}).get("v"),
            }
        )
    incorrect = [row for row in rows if row["classification"] == "INCORRECT"]
    unverifiable = [row for row in rows if row["classification"] == "UNVERIFIABLE"]
    return {
        "count": len(rows),
        "classifications": counts,
        "rows": rows,
        "incorrect": incorrect,
        "unverifiable": unverifiable,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "status": "FAIL" if incorrect else "PASS",
        "human_review_required": True,
    }


def review_theme_fields(transport: Mapping[str, Any], normalized: Mapping[str, Any]) -> dict[str, Any]:
    gm = transport.get("gm") if isinstance(transport.get("gm"), Mapping) else {}
    local_text = " ".join(
        str((row or {}).get("theme") or "")
        for row in (normalized.get("windows") or {}).values()
    )
    local_tokens = _tokens(local_text)
    def _class(field: str) -> str:
        tokens = _tokens(str(gm.get(field) or ""))
        if not tokens:
            return "UNSUPPORTED"
        overlap = _overlap(tokens, local_tokens)
        if overlap >= 0.28:
            return "SUPPORTED"
        if overlap >= 0.10:
            return "PARTIALLY_SUPPORTED"
        return "UNDETERMINABLE"

    return {
        "theme": {"text": gm.get("th"), "classification": _class("th")},
        "intent": {"text": gm.get("in"), "confidence": gm.get("ic"), "classification": _class("in")},
        "audience": {"text": gm.get("au"), "confidence": gm.get("ac"), "classification": _class("au")},
        "voice": {"text": gm.get("vo"), "classification": _class("vo") if gm.get("vo") else "UNSUPPORTED"},
    }


def review_examples_references_uncertainties(
    transport: Mapping[str, Any],
    transcript: TranscriptInput,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for kind, key in (
        ("EXAMPLE", "examples"),
        ("REFERENCE", "references"),
        ("UNCERTAINTY", "uncertainties"),
        ("REPETITION", "repetitions"),
        ("TOPIC", "topics"),
    ):
        rows = []
        for node in transport.get("n") or []:
            if not isinstance(node, dict) or node.get("k") != kind:
                continue
            refs = [str(item) for item in (node.get("s") or []) if isinstance(item, str)]
            overlap = _overlap(_tokens(str(node.get("v") or "")), _tokens(_src_text(transcript, refs)))
            rows.append(
                {
                    "handle": node.get("h"),
                    "value": node.get("v"),
                    "source_refs": refs,
                    "overlap": round(overlap, 3),
                    "classification": (
                        "SUPPORTED"
                        if overlap >= 0.28
                        else "PARTIALLY_SUPPORTED"
                        if overlap >= 0.12
                        else "UNDETERMINABLE"
                    ),
                }
            )
        windowish = [
            row
            for row in rows
            if kind == "TOPIC"
            and re.search(r"\bWIN00[1-7]\b|window\s*[1-7]|fenêtre", str(row.get("value") or ""), re.I)
        ]
        out[key] = {
            "count": len(rows),
            "rows": rows,
            "window_boundary_artifacts": windowish,
        }
    return out


def material_omissions(
    transport: Mapping[str, Any],
    normalized: Mapping[str, Any],
) -> dict[str, Any]:
    local = idea_records(dict(normalized))
    global_idea_tokens = [
        _tokens(str(node.get("v") or ""))
        for node in (transport.get("n") or [])
        if isinstance(node, dict) and node.get("k") == "IDEA"
    ]
    dispositions = {
        str(row.get("i") or ""): row
        for row in (transport.get("d") or [])
        if isinstance(row, dict)
    }
    missing: list[dict[str, Any]] = []
    for record in local:
        input_id = record["input_id"]
        disp = dispositions.get(input_id) or {}
        op = str(disp.get("o") or "")
        if op in {"DROP", "OTHER"}:
            continue
        tokens = _tokens(str(record.get("value") or ""))
        best = max((_overlap(tokens, other) for other in global_idea_tokens), default=0.0)
        if op in {"KEEP", "MERGE_EQUIVALENT"} and best < 0.12 and len(tokens) >= 6:
            missing.append(
                {
                    "input_id": input_id,
                    "window_id": record.get("window_id"),
                    "op": op,
                    "best_overlap": round(best, 3),
                    "value": record.get("value"),
                }
            )
    return {
        "count": len(missing),
        "rows": missing,
        "status": "FAIL" if missing else "PASS",
    }


def window_coverage(
    transport: Mapping[str, Any],
    normalized: Mapping[str, Any],
) -> dict[str, Any]:
    local = idea_records(dict(normalized))
    dispositions = {
        str(row.get("i") or ""): row
        for row in (transport.get("d") or [])
        if isinstance(row, dict)
    }
    per_window: dict[str, Any] = {}
    for window_id in READY_WINDOWS:
        ideas = [item for item in local if item.get("window_id") == window_id]
        keep = merge = drop = other = missing = 0
        for item in ideas:
            op = str((dispositions.get(item["input_id"]) or {}).get("o") or "")
            if op == "KEEP":
                keep += 1
            elif op == "MERGE_EQUIVALENT":
                merge += 1
            elif op == "DROP":
                drop += 1
            elif op == "OTHER":
                other += 1
            else:
                missing += 1
        represented = keep + merge
        total = len(ideas)
        per_window[window_id] = {
            "local_idea_count": total,
            "represented_globally": represented,
            "merged": merge,
            "dropped": drop,
            "other": other,
            "missing_disposition": missing,
            "coverage_percent": round(100.0 * (total - missing) / total, 1) if total else 100.0,
        }
    beginning = sum(per_window[item]["represented_globally"] for item in BEGINNING_WINDOWS)
    middle = sum(per_window[item]["represented_globally"] for item in MIDDLE_WINDOWS)
    end = sum(per_window[item]["represented_globally"] for item in END_WINDOWS)
    return {
        "windows": per_window,
        "beginning": beginning,
        "middle": middle,
        "end": end,
        "beginning_middle_end": (
            "REPRESENTED" if beginning and middle and end else "INCOMPLETE"
        ),
    }


def src_coverage(transport: Mapping[str, Any], normalized: Mapping[str, Any]) -> dict[str, Any]:
    global_refs: set[str] = set()
    for node in transport.get("n") or []:
        if isinstance(node, dict):
            global_refs.update(str(item) for item in (node.get("s") or []) if isinstance(item, str))
    for rel in transport.get("r") or []:
        if isinstance(rel, dict):
            global_refs.update(str(item) for item in (rel.get("s") or []) if isinstance(item, str))
    local_refs = set()
    for refs in local_src_by_input(dict(normalized)).values():
        local_refs.update(refs)
    return {
        "distinct_local_src": len(local_refs),
        "expected_distinct_local_src": EXPECTED_DISTINCT_SRC,
        "distinct_global_src": len(global_refs),
        "lost_src": len(local_refs - global_refs),
        "unexpected_src": len(global_refs - local_refs),
        "coverage_percent": (
            round(100.0 * len(global_refs & local_refs) / len(local_refs), 1)
            if local_refs
            else 0.0
        ),
    }


def cross_window_quality(
    transport: Mapping[str, Any],
    normalized: Mapping[str, Any],
    merge_review: Mapping[str, Any],
) -> dict[str, Any]:
    boundaries = []
    for left, right in CROSS_WINDOW_BOUNDARIES:
        cross_merges = [
            row
            for row in (merge_review.get("rows") or [])
            if left in (row.get("windows") or []) and right in (row.get("windows") or [])
        ]
        cross_ideas = 0
        for node in transport.get("n") or []:
            if not isinstance(node, dict) or node.get("k") != "IDEA":
                continue
            windows = _windows_for_refs(
                normalized, [str(item) for item in (node.get("s") or []) if isinstance(item, str)]
            )
            if left in windows and right in windows:
                cross_ideas += 1
        connected = bool(cross_merges or cross_ideas)
        boundaries.append(
            {
                "boundary": f"{left}→{right}",
                "cross_window_merges": len(cross_merges),
                "cross_window_ideas": cross_ideas,
                "connected": connected,
            }
        )
    return {
        "boundaries": boundaries,
        "connected_count": sum(1 for item in boundaries if item["connected"]),
        "all_six_inspected": len(boundaries) == 6,
    }


def classify_semantic_quality(
    *,
    unsupported_ideas: int,
    invalid_merges: int,
    material_omission_count: int,
    incorrect_relations: int,
    questionable_merges: int,
    questionable_drops: int,
    partially_supported: int,
    beginning_middle_end: str,
) -> str:
    if (
        unsupported_ideas
        or invalid_merges
        or material_omission_count
        or incorrect_relations
        or beginning_middle_end != "REPRESENTED"
    ):
        return "INADEQUATE_FOR_SOURCE_MAP"
    if questionable_merges or questionable_drops or partially_supported:
        return "ACCEPTABLE_WITH_REVIEW_ITEMS"
    return "ACCEPTABLE_FOR_SOURCE_MAP_CANDIDATE"


def review_semantics(
    transport: Mapping[str, Any] | None,
    normalized: Mapping[str, Any],
    transcript: TranscriptInput,
) -> dict[str, Any]:
    if not isinstance(transport, Mapping):
        return {
            "status": "FAIL",
            "semantic_quality": "UNDETERMINABLE",
            "errors": ["transport missing"],
        }
    drops = review_drops(transport, normalized)
    others = review_others(transport, normalized)
    merges = review_merges(transport, normalized)
    ideas = review_global_ideas(transport, normalized, transcript)
    relations = review_relations(transport, transcript)
    theme = review_theme_fields(transport, normalized)
    objects = review_examples_references_uncertainties(transport, transcript)
    omissions = material_omissions(transport, normalized)
    coverage = window_coverage(transport, normalized)
    src = src_coverage(transport, normalized)
    cross = cross_window_quality(transport, normalized, merges)
    quality = classify_semantic_quality(
        unsupported_ideas=int((ideas.get("classifications") or {}).get("UNSUPPORTED") or 0),
        invalid_merges=len(merges.get("invalid") or []),
        material_omission_count=int(omissions.get("count") or 0),
        incorrect_relations=len(relations.get("incorrect") or []),
        questionable_merges=int((merges.get("classifications") or {}).get("QUESTIONABLE_MERGE") or 0),
        questionable_drops=int((drops.get("classifications") or {}).get("QUESTIONABLE") or 0),
        partially_supported=int((ideas.get("classifications") or {}).get("PARTIALLY_SUPPORTED") or 0),
        beginning_middle_end=str(coverage.get("beginning_middle_end") or ""),
    )
    semantic_fail = (
        drops.get("status") == "FAIL"
        or others.get("status") == "FAIL"
        or merges.get("status") == "FAIL"
        or ideas.get("status") == "FAIL"
        or relations.get("status") == "FAIL"
        or omissions.get("status") == "FAIL"
        or coverage.get("beginning_middle_end") != "REPRESENTED"
    )
    return {
        "status": "FAIL" if semantic_fail else "PASS",
        "semantic_quality": quality,
        "drops": drops,
        "others": others,
        "merges": merges,
        "ideas": ideas,
        "relations": relations,
        "theme_fields": theme,
        "objects": objects,
        "omissions": omissions,
        "window_coverage": coverage,
        "src_coverage": src,
        "cross_window": cross,
        "local_ideas": EXPECTED_IDEA,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "no_llm": True,
    }


__all__ = [
    "classify_semantic_quality",
    "review_semantics",
]
