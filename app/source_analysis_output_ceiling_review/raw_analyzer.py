"""
Analyseur forensique OFFLINE du corps provider persisté.

Ne répare pas le JSON. N'écrit pas transport.json / result.json /
source_map.json. N'appelle aucun provider. N'émet que des agrégats.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any, Mapping

from app.ai.estimation import CHARS_PER_TOKEN
from app.ai.provider_forensics import RAW_BODY_NAME
from app.ai.structured_forensics import FORENSICS_RAW_NAME
from app.source_analysis.window_granularity import (
    HARD_CEILINGS,
    SOFT_TARGETS,
    SOURCE_REFS_HARD_MAX,
    TEXT_HARD_LIMITS,
    TOTAL_HARD_CEILING,
)
from app.source_analysis_output_ceiling_review.raw_parser import extract_root_prefix

RECORD_KINDS = (
    "TOPIC",
    "IDEA",
    "RELATION",
    "EXAMPLE",
    "REFERENCE",
    "UNCERTAINTY",
    "REPETITION",
    "VOICE",
    "INTENT_KIND",
    "AUDIENCE_KIND",
)

SRC_PREFIX = "SRC"
_SAFE_USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "thinking_tokens",
    "cache_creation",
    "cache_read",
)


def local_token_estimate(char_count: int) -> int:
    return int(math.ceil(char_count / CHARS_PER_TOKEN)) if char_count else 0


def word_count(text: str) -> int:
    return len(text.split()) if text else 0


def _safe_usage(usage: Any) -> dict[str, Any]:
    if not isinstance(usage, Mapping):
        return {"present": False, "keys": []}
    keys = sorted(str(key) for key in usage)
    compact: dict[str, Any] = {"present": True, "keys": keys}
    for key in keys:
        value = usage[key]
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            compact[key] = value
        elif isinstance(value, Mapping):
            nested = {
                str(inner): inner_value
                for inner, inner_value in value.items()
                if isinstance(inner_value, (int, float))
                and not isinstance(inner_value, bool)
            }
            compact[key] = nested
        else:
            compact[key] = type(value).__name__
    return compact


def analyze_http_raw_bytes(raw: bytes) -> dict[str, Any]:
    """Métadonnées d'enveloppe uniquement. Jamais le texte thinking/JSON."""
    payload: dict[str, Any] = {
        "raw_bytes": len(raw),
        "json_decode_ok": False,
        "top_level_type": None,
        "top_level_keys": [],
        "usage": {"present": False, "keys": []},
        "stop_reason": None,
        "content_blocks": [],
        "thinking_block_count": 0,
        "text_block_count": 0,
        "thinking_chars": 0,
        "thinking_bytes": 0,
        "text_chars": 0,
        "text_bytes": 0,
        "signature_chars": 0,
    }
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return payload
    payload["json_decode_ok"] = True
    payload["top_level_type"] = type(data).__name__
    if not isinstance(data, dict):
        return payload
    payload["top_level_keys"] = sorted(str(key) for key in data)
    payload["usage"] = _safe_usage(data.get("usage"))
    payload["stop_reason"] = data.get("stop_reason")
    content = data.get("content")
    blocks: list[dict[str, Any]] = []
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                blocks.append({"type": type(block).__name__, "keys": []})
                continue
            block_type = block.get("type")
            info: dict[str, Any] = {
                "type": block_type,
                "keys": sorted(str(key) for key in block),
            }
            if block_type == "thinking" and isinstance(block.get("thinking"), str):
                thinking = block["thinking"]
                encoded = thinking.encode("utf-8")
                info["thinking_chars"] = len(thinking)
                info["thinking_bytes"] = len(encoded)
                payload["thinking_chars"] += len(thinking)
                payload["thinking_bytes"] += len(encoded)
                payload["thinking_block_count"] += 1
            if isinstance(block.get("signature"), str):
                info["signature_chars"] = len(block["signature"])
                payload["signature_chars"] += len(block["signature"])
            if block_type == "text" and isinstance(block.get("text"), str):
                text = block["text"]
                encoded = text.encode("utf-8")
                info["text_chars"] = len(text)
                info["text_bytes"] = len(encoded)
                payload["text_chars"] += len(text)
                payload["text_bytes"] += len(encoded)
                payload["text_block_count"] += 1
            blocks.append(info)
    payload["content_blocks"] = blocks
    payload["output_token_split_note"] = (
        "Provider output_tokens is a single integer. Thinking and text "
        "are not separately billed in the persisted usage object unless "
        "a thinking_tokens key is present."
    )
    return payload


def _record_metrics(records: list[Any]) -> dict[str, Any]:
    kind_counts = {kind: 0 for kind in RECORD_KINDS}
    kind_counts["UNKNOWN"] = 0
    serialized_sizes: list[int] = []
    value_by_kind: dict[str, list[int]] = {kind: [] for kind in RECORD_KINDS}
    words_by_kind: dict[str, list[int]] = {kind: [] for kind in RECORD_KINDS}
    refs_per_record: list[int] = []
    serialized_ref_entries = 0
    distinct_src: set[str] = set()
    multi_src = 0
    order: list[str] = []
    for item in records:
        if not isinstance(item, Mapping):
            kind_counts["UNKNOWN"] += 1
            continue
        kind = str(item.get("k") or "UNKNOWN")
        if kind not in kind_counts:
            kind_counts[kind] = 0
            value_by_kind.setdefault(kind, [])
            words_by_kind.setdefault(kind, [])
        kind_counts[kind] += 1
        order.append(kind)
        encoded = json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        serialized_sizes.append(len(encoded))
        value = item.get("v")
        value_text = value if isinstance(value, str) else ""
        value_by_kind.setdefault(kind, []).append(len(value_text))
        words_by_kind.setdefault(kind, []).append(word_count(value_text))
        refs = item.get("s")
        ref_list = [str(ref) for ref in refs] if isinstance(refs, list) else []
        refs_per_record.append(len(ref_list))
        serialized_ref_entries += len(ref_list)
        if len(ref_list) > 1:
            multi_src += 1
        for ref in ref_list:
            if ref.startswith(SRC_PREFIX):
                distinct_src.add(ref)
    def _stats(values: list[int]) -> dict[str, Any]:
        if not values:
            return {
                "count": 0,
                "mean": None,
                "median": None,
                "max": None,
                "min": None,
            }
        return {
            "count": len(values),
            "mean": round(statistics.fmean(values), 4),
            "median": statistics.median(values),
            "max": max(values),
            "min": min(values),
        }

    owned_numeric = []
    for ref in distinct_src:
        if ref.startswith(SRC_PREFIX) and ref[3:].isdigit():
            owned_numeric.append(int(ref[3:]))
    return {
        "kind_counts": {key: kind_counts[key] for key in sorted(kind_counts)},
        "record_order": order,
        "first_kind": order[0] if order else None,
        "last_complete_kind": order[-1] if order else None,
        "serialized_size_bytes": _stats(serialized_sizes),
        "value_chars_by_kind": {
            kind: _stats(values) for kind, values in sorted(value_by_kind.items())
        },
        "value_words_by_kind": {
            kind: _stats(values) for kind, values in sorted(words_by_kind.items())
        },
        "source_refs": {
            "per_record": _stats(refs_per_record),
            "total_serialized_entries": serialized_ref_entries,
            "multi_src_record_count": multi_src,
            "distinct_src_count": len(distinct_src),
            "earliest_src": (
                f"{SRC_PREFIX}{min(owned_numeric):06d}" if owned_numeric else None
            ),
            "latest_src": (
                f"{SRC_PREFIX}{max(owned_numeric):06d}" if owned_numeric else None
            ),
            "hard_max_per_record": SOURCE_REFS_HARD_MAX,
            "any_over_hard_max": any(
                count > SOURCE_REFS_HARD_MAX for count in refs_per_record
            ),
        },
        "grouping_observed": multi_src > 0,
        "approx_one_record_per_src": (
            len(distinct_src) > 0
            and len(records) >= max(1, int(0.8 * len(distinct_src)))
        ),
    }


def _truncation(text: str, prefix: Mapping[str, Any], parse_col: int | None) -> dict[str, Any]:
    stopped = int(prefix.get("scan_stopped_at") or 0)
    tail = text[max(0, stopped - 80) : min(len(text), stopped + 40)]
    visible_kind = None
    marker = '"k":"'
    found = tail.rfind(marker)
    if found >= 0:
        kind_end = tail.find('"', found + len(marker))
        if kind_end > found:
            visible_kind = tail[found + len(marker) : kind_end]
    return {
        "json_decode_colno": parse_col,
        "scan_stopped_at_char": stopped,
        "inside_records_array": bool(prefix.get("records_array_reached")),
        "records_array_closed": bool(prefix.get("records_array_closed")),
        "incomplete_record_present": bool(prefix.get("incomplete_record_present")),
        "last_complete_kind": (
            prefix.get("complete_records")[-1].get("k")
            if prefix.get("complete_records")
            and isinstance(prefix["complete_records"][-1], Mapping)
            else None
        ),
        "incomplete_kind_if_visible": visible_kind,
        "unterminated_string_at_col": parse_col,
        "semantic_location": (
            "inside_incomplete_record_string"
            if prefix.get("incomplete_record_present")
            else "before_or_outside_records"
        ),
    }


def _compliance(metrics: Mapping[str, Any]) -> dict[str, str]:
    counts = metrics.get("kind_counts") or {}
    total = sum(int(counts.get(kind, 0) or 0) for kind in RECORD_KINDS)
    refs = metrics.get("source_refs") or {}
    ideas = int(counts.get("IDEA", 0) or 0)
    relations = int(counts.get("RELATION", 0) or 0)
    ceilings = {
        "record_ceilings": (
            "COMPLIANT"
            if total < TOTAL_HARD_CEILING
            else (
                "NONCOMPLIANT"
                if total > TOTAL_HARD_CEILING
                else "PARTIALLY_COMPLIANT"
            )
        ),
        "idea_soft": (
            "COMPLIANT"
            if ideas <= SOFT_TARGETS["IDEA"]
            else (
                "PARTIALLY_COMPLIANT"
                if ideas <= HARD_CEILINGS["IDEA"]
                else "NONCOMPLIANT"
            )
        ),
        "idea_hard": (
            "COMPLIANT"
            if ideas <= HARD_CEILINGS["IDEA"]
            else "NONCOMPLIANT"
        ),
        "relation_hard": (
            "COMPLIANT"
            if relations <= HARD_CEILINGS["RELATION"]
            else "NONCOMPLIANT"
        ),
        "grouping": (
            "COMPLIANT"
            if metrics.get("grouping_observed")
            else "PARTIALLY_COMPLIANT"
        ),
        "compactness": "UNKNOWN",
        "source_grounding": (
            "COMPLIANT"
            if int((refs.get("distinct_src_count") or 0)) > 0
            else "UNKNOWN"
        ),
    }
    value_chars = metrics.get("value_chars_by_kind") or {}
    over_text = False
    any_value = False
    for kind, stats in value_chars.items():
        limit = TEXT_HARD_LIMITS.get(f"{kind}.v")
        maximum = stats.get("max")
        if maximum is None or limit is None:
            continue
        any_value = True
        if int(maximum) > limit:
            over_text = True
    if any_value:
        ceilings["compactness"] = "NONCOMPLIANT" if over_text else "COMPLIANT"
    return ceilings


def analyze_structured_raw_text(
    text: str,
    *,
    parse_colno: int | None = None,
) -> dict[str, Any]:
    encoded = text.encode("utf-8")
    prefix = extract_root_prefix(text)
    records = [
        item
        for item in prefix.get("complete_records") or []
        if isinstance(item, Mapping)
    ]
    metrics = _record_metrics(records)
    emitted_kinds = {
        kind
        for kind, count in metrics["kind_counts"].items()
        if kind in RECORD_KINDS and count
    }
    missing = [kind for kind in RECORD_KINDS if kind not in emitted_kinds]
    return {
        "raw_bytes": len(encoded),
        "raw_chars": len(text),
        "local_token_estimate": local_token_estimate(len(text)),
        "estimator": "ceil(chars/4)",
        "starts_with_json_object": text.lstrip().startswith("{"),
        "ends_with_closed_json": text.rstrip().endswith("}"),
        "json_valid": False,
        "treated_as_transport": False,
        "root_keys_complete": prefix.get("root_keys_complete"),
        "records_array_reached": prefix.get("records_array_reached"),
        "records_array_closed": prefix.get("records_array_closed"),
        "complete_record_count": len(records),
        "incomplete_record_count": (
            1 if prefix.get("incomplete_record_present") else 0
        ),
        "total_hard_ceiling": TOTAL_HARD_CEILING,
        "exceeded_total_hard_ceiling": len(records) > TOTAL_HARD_CEILING,
        "truncation_before_160": len(records) < TOTAL_HARD_CEILING,
        "metrics": metrics,
        "missing_categories_before_truncation": missing,
        "prompt_compliance": _compliance(metrics),
        "truncation": _truncation(text, prefix, parse_colno),
        "header_preview_safe": {
            "theme_chars": len(str((prefix.get("root_scalar_values") or {}).get("theme") or "")),
            "intent_chars": len(
                str((prefix.get("root_scalar_values") or {}).get("intent") or "")
            ),
            "aud_chars": len(str((prefix.get("root_scalar_values") or {}).get("aud") or "")),
        },
    }


def analyze_persisted_forensics(
    *,
    raw_http_path: Path,
    raw_text_path: Path,
    parse_colno: int | None = None,
) -> dict[str, Any]:
    http = analyze_http_raw_bytes(Path(raw_http_path).read_bytes())
    text = Path(raw_text_path).read_text(encoding="utf-8")
    structured = analyze_structured_raw_text(text, parse_colno=parse_colno)
    thinking_chars = int(http.get("thinking_chars") or 0)
    text_chars = int(http.get("text_chars") or structured["raw_chars"])
    usage = http.get("usage") or {}
    details = usage.get("output_tokens_details")
    thinking_tokens = None
    if isinstance(details, Mapping) and details.get("thinking_tokens") is not None:
        thinking_tokens = int(details["thinking_tokens"])
    output_tokens = usage.get("output_tokens")
    text_tokens = None
    if output_tokens is not None and thinking_tokens is not None:
        text_tokens = int(output_tokens) - thinking_tokens
    return {
        "http_envelope": http,
        "structured_prefix": structured,
        "output_composition": {
            "thinking_chars": thinking_chars,
            "thinking_plaintext_present": thinking_chars > 0,
            "thinking_signature_chars": int(http.get("signature_chars") or 0),
            "text_chars": text_chars,
            "thinking_local_tokens": local_token_estimate(thinking_chars),
            "text_local_tokens": local_token_estimate(text_chars),
            "provider_output_tokens": output_tokens,
            "provider_thinking_tokens": thinking_tokens,
            "implied_non_thinking_output_tokens": text_tokens,
            "thinking_share_of_output_tokens": (
                round(thinking_tokens / output_tokens, 6)
                if thinking_tokens is not None and output_tokens
                else None
            ),
            "visible_char_sum_explains_32000": False,
            "note": (
                "Provider usage.output_tokens_details.thinking_tokens is the "
                "authoritative split when present. Thinking plaintext may be "
                "absent (signature only). Local char/4 is not provider tokenization."
            ),
        },
        "repairs_json": False,
        "writes_transport": False,
        "writes_result": False,
        "writes_source_map": False,
        "provider_called": False,
    }


__all__ = [
    "FORENSICS_RAW_NAME",
    "RAW_BODY_NAME",
    "analyze_http_raw_bytes",
    "analyze_persisted_forensics",
    "analyze_structured_raw_text",
    "local_token_estimate",
    "word_count",
]
