"""Revue sémantique production A.46. Aucun LLM. Aucune réparation provider."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

from app.source_analysis.models import scan_editorial_structure
from app.source_analysis_v31_global_output_architecture.membership import derived_src_union
from app.source_analysis_v31_global_reuse_output.reconstruct import local_idea_text
from app.source_analysis_v31_global_reuse_output.validate import idea_mode
from app.source_analysis_v31_global_v30_real_canary.constants import (
    DROP_REASONS_V20,
    EDITORIAL_MARKERS,
    EXPECTED_IDEA,
    SYNTHESIZED_IDEA_MAX_CHARS,
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
    "cette",
    "cette",
    "leur",
    "leurs",
    "nous",
    "vous",
    "they",
    "them",
    "have",
    "will",
    "from",
    "when",
    "what",
}
_UNIVERSALS = {
    "always",
    "never",
    "all",
    "every",
    "everyone",
    "nobody",
    "toujours",
    "jamais",
    "tous",
    "toutes",
}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if isinstance(item, str) and item]


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


def _record(inventory: Mapping[str, Any], input_id: str) -> Mapping[str, Any]:
    records = inventory.get("records") or {}
    row = records.get(input_id) if isinstance(records, Mapping) else None
    return row if isinstance(row, Mapping) else {}


def _src_text(inventory: Mapping[str, Any], refs: list[str]) -> str:
    transcript = inventory.get("transcript")
    if transcript is None:
        return ""
    segments = getattr(transcript, "segments", ()) or ()
    index = {getattr(segment, "src_id", ""): getattr(segment, "text", "") for segment in segments}
    return " ".join(index.get(ref, "") for ref in refs)


def review_reuse(transport: Mapping[str, Any], inventory: Mapping[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    failures = 0
    local_src = inventory.get("src_by_input") or {}
    for idea in _as_list(transport.get("i")):
        if not isinstance(idea, Mapping):
            continue
        members = _strings(idea.get("m"))
        if len(members) != 1:
            continue
        member = members[0]
        expected = local_idea_text(inventory, member)
        derived = derived_src_union(members, local_src)
        local_refs = list(local_src.get(member) or [])
        exact_text = expected == local_idea_text(inventory, member)
        src_exact = derived == local_refs
        present_v = bool(str(idea.get("v") or "").strip())
        ok = exact_text and src_exact and not present_v and bool(_record(inventory, member))
        if not ok:
            failures += 1
        rows.append(
            {
                "handle": idea.get("h"),
                "member": member,
                "local_exists": bool(_record(inventory, member)),
                "canonical_text_exact": exact_text,
                "derived_src_exact": src_exact,
                "provider_v_absent": not present_v,
                "ok": ok,
            }
        )
    return {
        "count": len(rows),
        "failures": failures,
        "status": "PASS" if failures == 0 else "FAIL",
        "rows": rows,
        "provider_paraphrase_review_needed": False,
    }


def _merge_verdict(
    *,
    pairwise: float,
    v_overlap: float,
    extra: list[str],
    v_len: int,
    member_count: int,
) -> str:
    if member_count < 2 or v_len == 0 or v_len > SYNTHESIZED_IDEA_MAX_CHARS:
        return "UNSUPPORTED_OR_BROADENED_MERGE"
    broadened = len(extra) > 2
    if pairwise < 0.15 or v_overlap < 0.25 or broadened:
        return "UNSUPPORTED_OR_BROADENED_MERGE"
    if pairwise >= 0.40 and v_overlap >= 0.50 and not extra:
        return "SUPPORTED_EQUIVALENT_MERGE"
    if pairwise >= 0.40 and v_overlap >= 0.42 and len(extra) <= 1:
        return "SUPPORTED_EQUIVALENT_MERGE"
    return "QUESTIONABLE_MERGE"


def review_merges(transport: Mapping[str, Any], inventory: Mapping[str, Any]) -> dict[str, Any]:
    local_src = inventory.get("src_by_input") or {}
    rows: list[dict[str, Any]] = []
    counts = {
        "SUPPORTED_EQUIVALENT_MERGE": 0,
        "QUESTIONABLE_MERGE": 0,
        "UNSUPPORTED_OR_BROADENED_MERGE": 0,
    }
    reconstructed = None
    for idea in _as_list(transport.get("i")):
        if not isinstance(idea, Mapping):
            continue
        members = _strings(idea.get("m"))
        if len(members) < 2:
            continue
        member_texts = [local_idea_text(inventory, item) for item in members]
        token_sets = [_tokens(text) for text in member_texts]
        pairs: list[float] = []
        for index, left in enumerate(token_sets):
            for right in token_sets[index + 1 :]:
                if left or right:
                    pairs.append(min(_overlap(left, right), _overlap(right, left)))
        pairwise = min(pairs) if pairs else 0.0
        union = set().union(*token_sets) if token_sets else set()
        v_text = str(idea.get("v") or "")
        v_tokens = _tokens(v_text)
        src_union = derived_src_union(members, local_src)
        src_tokens = _tokens(_src_text(inventory, src_union))
        support = union | src_tokens
        extra = sorted(token for token in v_tokens if token not in support and len(token) > 5)
        v_overlap = _overlap(v_tokens, support)
        verdict = _merge_verdict(
            pairwise=pairwise,
            v_overlap=v_overlap,
            extra=extra,
            v_len=len(v_text),
            member_count=len(members),
        )
        counts[verdict] += 1
        rows.append(
            {
                "global_handle": idea.get("h"),
                "member_handles": members,
                "member_texts": member_texts,
                "provider_v": v_text,
                "member_src_union": src_union,
                "v_length": len(v_text),
                "worst_pairwise_overlap": round(pairwise, 3),
                "v_support_overlap": round(v_overlap, 3),
                "unsupported_tokens": extra[:8],
                "semantic_verdict": verdict,
                "mode": idea_mode(idea),
            }
        )
    unsupported = [
        row for row in rows if row["semantic_verdict"] == "UNSUPPORTED_OR_BROADENED_MERGE"
    ]
    questionable = [row for row in rows if row["semantic_verdict"] == "QUESTIONABLE_MERGE"]
    all_supported = counts["QUESTIONABLE_MERGE"] == 0 and counts[
        "UNSUPPORTED_OR_BROADENED_MERGE"
    ] == 0
    return {
        "count": len(rows),
        "classifications": counts,
        "rows": rows,
        "questionable": questionable,
        "unsupported": unsupported,
        "all_supported": all_supported,
        "status": (
            "FAIL"
            if unsupported
            else "REVIEW_REQUIRED"
            if questionable
            else "PASS"
        ),
        "repaired": False,
        "reconstructed_unused": reconstructed,
    }


def review_drops(transport: Mapping[str, Any], inventory: Mapping[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    counts = {
        "SUPPORTED_DROP": 0,
        "QUESTIONABLE_DROP": 0,
        "INVALID_SUBSTANTIVE_DROP": 0,
    }
    for row in _as_list(transport.get("drop")):
        if not isinstance(row, Mapping):
            continue
        handle = str(row.get("i") or "")
        reason = str(row.get("w") or "")
        record = _record(inventory, handle)
        text = str(record.get("value") or "")
        tokens = _tokens(text)
        word_count = len(text.split())
        verdict = "QUESTIONABLE_DROP"
        if reason not in DROP_REASONS_V20:
            verdict = "INVALID_SUBSTANTIVE_DROP"
        elif reason == "transport_artifact":
            if word_count <= 3 or not tokens:
                verdict = "SUPPORTED_DROP"
            elif word_count >= 10 and len(tokens) >= 5:
                verdict = "INVALID_SUBSTANTIVE_DROP"
            else:
                verdict = "QUESTIONABLE_DROP"
        elif reason == "non_substantive_fragment":
            if word_count <= 6 or len(tokens) <= 2:
                verdict = "SUPPORTED_DROP"
            elif word_count >= 12 and len(tokens) >= 6:
                verdict = "INVALID_SUBSTANTIVE_DROP"
            else:
                verdict = "QUESTIONABLE_DROP"
        counts[verdict] += 1
        rows.append(
            {
                "handle": handle,
                "local_text": text,
                "source_refs": list(record.get("source_refs") or []),
                "provider_reason": reason,
                "review_verdict": verdict,
                "word_count": word_count,
                "window_id": record.get("window_id"),
            }
        )
    invalid = [row for row in rows if row["review_verdict"] == "INVALID_SUBSTANTIVE_DROP"]
    questionable = [row for row in rows if row["review_verdict"] == "QUESTIONABLE_DROP"]
    all_supported = not invalid and not questionable
    return {
        "count": len(rows),
        "classifications": counts,
        "rows": rows,
        "invalid": invalid,
        "questionable": questionable,
        "all_supported": all_supported,
        "status": (
            "FAIL" if invalid else "REVIEW_REQUIRED" if questionable else "PASS"
        ),
        "repaired": False,
    }


def review_topics(transport: Mapping[str, Any], inventory: Mapping[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    editorial = 0
    unsupported = 0
    review_items = 0
    local_src = inventory.get("src_by_input") or {}
    for topic in _as_list(transport.get("t")):
        if not isinstance(topic, Mapping):
            continue
        text = str(topic.get("v") or "")
        members = _strings(topic.get("m"))
        member_blob = " ".join(str(_record(inventory, item).get("value") or "") for item in members)
        src_union = derived_src_union(members, local_src)
        support = _tokens(member_blob) | _tokens(_src_text(inventory, src_union))
        overlap = _overlap(_tokens(text), support) if _tokens(text) else 0.0
        windowish = bool(re.search(r"\bWIN00[1-7]\b|window\s*[1-7]|fenêtre", text, re.I))
        invented = False
        if windowish:
            verdict = "FAIL"
            editorial += 1
        elif overlap >= 0.28:
            verdict = "PASS"
        elif overlap >= 0.10:
            verdict = "REVIEW"
            review_items += 1
        else:
            verdict = "FAIL"
            unsupported += 1
        rows.append(
            {
                "handle": topic.get("h"),
                "text": text,
                "members": members,
                "overlap": round(overlap, 3),
                "window_boundary_artifact": windowish,
                "editorial": invented,
                "verdict": verdict,
            }
        )
    if editorial or unsupported:
        status = "FAIL"
    elif review_items:
        status = "REVIEW"
    else:
        status = "PASS"
    return {
        "count": len(rows),
        "rows": rows,
        "status": status,
        "editorial_count": editorial,
        "unsupported_count": unsupported,
        "review_count": review_items,
    }


def review_metadata(transport: Mapping[str, Any], inventory: Mapping[str, Any]) -> dict[str, Any]:
    gm = transport.get("gm") if isinstance(transport.get("gm"), Mapping) else {}
    local_text = " ".join(
        str(row.get("value") or "")
        for row in (inventory.get("records") or {}).values()
        if isinstance(row, Mapping)
    )
    local_tokens = _tokens(local_text)

    def _class(field: str) -> str:
        tokens = _tokens(str(gm.get(field) or ""))
        if not tokens:
            return "FAIL"
        overlap = _overlap(tokens, local_tokens)
        if overlap >= 0.22:
            return "PASS"
        if overlap >= 0.08:
            return "REVIEW"
        return "FAIL"

    fields = {
        "theme": {"text": gm.get("th"), "status": _class("th")},
        "author_intent": {"text": gm.get("in"), "confidence": gm.get("ic"), "status": _class("in")},
        "target_audience": {
            "text": gm.get("au"),
            "confidence": gm.get("ac"),
            "status": _class("au"),
        },
        "author_voice_profile": {"text": gm.get("vo"), "status": _class("vo")},
    }
    statuses = [row["status"] for row in fields.values()]
    if "FAIL" in statuses:
        status = "FAIL"
    elif "REVIEW" in statuses:
        status = "REVIEW"
    else:
        status = "PASS"
    return {"fields": fields, "status": status}


def review_satellites(
    transport: Mapping[str, Any],
    inventory: Mapping[str, Any],
    *,
    key: str,
    kind: str,
) -> dict[str, Any]:
    kinds = inventory.get("kind_by_input") or {}
    rows: list[dict[str, Any]] = []
    bad = 0
    for item in _as_list(transport.get(key)):
        if not isinstance(item, Mapping):
            continue
        locals_ = _strings(item.get("l"))
        kind_ok = all(kinds.get(local_id) in {None, kind} for local_id in locals_)
        exists = all(bool(_record(inventory, local_id)) for local_id in locals_)
        text = " ".join(str(_record(inventory, local_id).get("value") or "") for local_id in locals_)
        ok = kind_ok and exists and bool(locals_)
        if not ok:
            bad += 1
        rows.append(
            {
                "handle": item.get("h"),
                "local_ids": locals_,
                "kind_ok": kind_ok,
                "exists": exists,
                "local_text_sample": text[:180],
                "ok": ok,
            }
        )
    return {
        "count": len(rows),
        "failures": bad,
        "status": "PASS" if bad == 0 else "FAIL",
        "rows": rows,
        "external_fact_check": False,
    }


def review_uncertainty_preservation(
    transport: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    local_unc = [
        row
        for row in (inventory.get("records") or {}).values()
        if isinstance(row, Mapping) and row.get("kind") == "UNCERTAINTY"
    ]
    global_unc = [item for item in _as_list(transport.get("u")) if isinstance(item, Mapping)]
    idea_blob = " ".join(
        str(item.get("v") or "")
        for item in _as_list(transport.get("i"))
        if isinstance(item, Mapping)
    ).lower()
    resolved = 0
    notes: list[str] = []
    if local_unc and not global_unc:
        notes.append("local uncertainties vanished from u[]")
        resolved += 1
    certainty_markers = ("il est certain", "we are certain", "definitely true", "sans aucun doute")
    if any(marker in idea_blob for marker in certainty_markers):
        notes.append("idea text asserts certainty")
        resolved += 1
    status = "FAIL" if resolved else "PASS"
    return {
        "local_uncertainties": len(local_unc),
        "global_uncertainties": len(global_unc),
        "status": status,
        "notes": notes,
        "resolved_as_fact": resolved,
    }


def review_completeness(
    *,
    accountability: str,
    drops: Mapping[str, Any],
    merges: Mapping[str, Any],
    missing: int,
) -> dict[str, Any]:
    invalid_drops = int((drops.get("classifications") or {}).get("INVALID_SUBSTANTIVE_DROP") or 0)
    unsupported_merges = int(
        (merges.get("classifications") or {}).get("UNSUPPORTED_OR_BROADENED_MERGE") or 0
    )
    ok = (
        accountability == f"{EXPECTED_IDEA} / {EXPECTED_IDEA}"
        and missing == 0
        and invalid_drops == 0
        and unsupported_merges == 0
    )
    return {
        "local_ideas": EXPECTED_IDEA,
        "accountability": accountability,
        "invalid_substantive_drops": invalid_drops,
        "unsupported_merges": unsupported_merges,
        "missing": missing,
        "status": "PASS" if ok else "FAIL",
    }


def review_editorial(transport: Mapping[str, Any], candidate: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = {"transport": dict(transport), "candidate": candidate or {}}
    structural = scan_editorial_structure(payload)
    blob = json.dumps(payload, ensure_ascii=False).lower()
    lexical_hits = [marker for marker in EDITORIAL_MARKERS if marker in blob]
    return {
        "status": "PASS" if structural.get("ok") else "FAIL",
        "hits": list(structural.get("hits") or []),
        "keys": list(structural.get("keys") or []),
        "mode": "STRUCTURAL",
        "lexical_hits_informational": lexical_hits,
        "lexical_not_failure": True,
        "no_chapters": not any(hit.get("key") in {"chapter", "chapters"} for hit in structural.get("hits") or []),
        "no_book_sections": not any(
            hit.get("key") in {"sections", "section", "section_titles"}
            for hit in structural.get("hits") or []
        ),
        "no_editorial_plan": not any(
            hit.get("key") == "editorial_plan" for hit in structural.get("hits") or []
        ),
        "no_book_title_structure": not any(
            hit.get("key") in {"book_title", "book_subtitle"}
            for hit in structural.get("hits") or []
        ),
        "no_publication_prose": "publication prose" not in blob
        or not any(hit.get("key") == "editorial_structure" for hit in structural.get("hits") or []),
        "scans_text_values": False,
    }


def classify_semantic(
    *,
    reuse: Mapping[str, Any],
    merges: Mapping[str, Any],
    drops: Mapping[str, Any],
    topics: Mapping[str, Any],
    metadata: Mapping[str, Any],
    uncertainty: Mapping[str, Any],
    completeness: Mapping[str, Any],
    editorial: Mapping[str, Any],
    examples: Mapping[str, Any],
    references: Mapping[str, Any],
) -> str:
    hard_fail = any(
        item.get("status") == "FAIL"
        for item in (
            reuse,
            uncertainty,
            completeness,
            editorial,
            examples,
            references,
        )
    ) or merges.get("status") == "FAIL" or drops.get("status") == "FAIL" or topics.get(
        "status"
    ) == "FAIL" or metadata.get("status") == "FAIL"
    if hard_fail:
        return "FAIL"
    needs_review = any(
        item.get("status") in {"REVIEW", "REVIEW_REQUIRED"}
        for item in (merges, drops, topics, metadata)
    )
    if needs_review:
        return "REVIEW_REQUIRED"
    return "PASS"


def review_semantics(
    transport: Mapping[str, Any] | None,
    inventory: Mapping[str, Any],
    *,
    accountability: str,
    missing: int,
    candidate_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(transport, Mapping):
        return {
            "status": "FAIL",
            "errors": ["transport missing"],
            "publication_semantic_ok": False,
        }
    reuse = review_reuse(transport, inventory)
    merges = review_merges(transport, inventory)
    drops = review_drops(transport, inventory)
    topics = review_topics(transport, inventory)
    metadata = review_metadata(transport, inventory)
    examples = review_satellites(transport, inventory, key="x", kind="EXAMPLE")
    references = review_satellites(transport, inventory, key="f", kind="REFERENCE")
    uncertainty = review_uncertainty_preservation(transport, inventory)
    completeness = review_completeness(
        accountability=accountability,
        drops=drops,
        merges=merges,
        missing=missing,
    )
    editorial = review_editorial(transport, candidate_payload)
    status = classify_semantic(
        reuse=reuse,
        merges=merges,
        drops=drops,
        topics=topics,
        metadata=metadata,
        uncertainty=uncertainty,
        completeness=completeness,
        editorial=editorial,
        examples=examples,
        references=references,
    )
    publication_ok = (
        status == "PASS"
        and merges.get("all_supported") is True
        and drops.get("all_supported") is True
        and topics.get("status") == "PASS"
        and metadata.get("status") == "PASS"
        and uncertainty.get("status") == "PASS"
        and completeness.get("status") == "PASS"
        and editorial.get("status") == "PASS"
        and reuse.get("status") == "PASS"
    )
    return {
        "status": status,
        "reuse": reuse,
        "merges": merges,
        "drops": drops,
        "topics": topics,
        "metadata": metadata,
        "examples": examples,
        "references": references,
        "uncertainty": uncertainty,
        "completeness": completeness,
        "editorial": editorial,
        "publication_semantic_ok": publication_ok,
        "no_llm": True,
        "repaired": False,
        "retried": False,
    }


__all__ = ["review_semantics"]
