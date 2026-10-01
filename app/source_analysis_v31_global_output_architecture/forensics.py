"""Forensics lexicales du préfixe A.38. Pas de réparation JSON. Pas de decode production."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any, Mapping

from app.source_analysis_v31_global_output_architecture.constants import (
    A34_INPUT_ERROR_PERCENT,
    A34_INPUT_ERROR_TOKENS,
    A34_INPUT_PREDICTION,
    A34_OUTPUT_PREDICTION,
    A38_CHARS_PER_PROVIDER_OUTPUT_TOKEN,
    A38_INPUT_TOKENS,
    A38_OUTPUT_TOKENS,
    A38_RAW_TEXT_CHARS,
    A38_ROOT_FAILURE,
    A38_UNTERMINATED_COLUMN,
)

_KIND_RE = re.compile(r'"k"\s*:\s*"(TOPIC|IDEA|EXAMPLE|REFERENCE|UNCERTAINTY|REPETITION)"')
_SRC_RE = re.compile(r"SRC\d{6}")
_ROOT_KEY_RE = {
    "n": re.compile(r'"n"\s*:'),
    "r": re.compile(r'"r"\s*:'),
    "d": re.compile(r'"d"\s*:'),
}
_DISP_RE = re.compile(r'"(KEEP|MERGE_EQUIVALENT|DROP|OTHER|LINK_RELATED)"')


def _count_kind(text: str, kind: str) -> int:
    return len(re.findall(rf'"k"\s*:\s*"{kind}"', text))


def classify_a38_failures() -> dict[str, Any]:
    return {
        "root_failure": A38_ROOT_FAILURE,
        "root_evidence": [
            "finish_reason=max_tokens",
            "output_tokens=32000/32000",
            "JSON unterminated mid-string",
        ],
        "cascade_failures": [
            "JSON truncation",
            "structured parse FAIL",
            "decoder FAIL",
            "global validator FAIL",
            "canonical reconstruction FAIL",
        ],
        "not_root": [
            "model intelligence failure",
            "thinking budget",
            "input context overflow",
            "HTTP error",
        ],
        "repaired": False,
        "converted_to_candidate": False,
    }


def extract_complete_objects(text: str) -> list[dict[str, Any]]:
    """Brace-scan complete objects only. Incomplete tail is discarded."""
    objects: list[dict[str, Any]] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        in_str = False
        escape = False
        j = i
        complete = False
        while j < n:
            ch = text[j]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        complete = True
                        j += 1
                        break
            j += 1
        if not complete:
            i += 1
            continue
        chunk = text[i:j]
        if '"k"' in chunk and '"h"' in chunk and chunk.count("{") == 1:
            try:
                parsed = json.loads(chunk)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict) and parsed.get("k") in {
                "TOPIC",
                "IDEA",
                "EXAMPLE",
                "REFERENCE",
                "UNCERTAINTY",
                "REPETITION",
            }:
                objects.append(parsed)
        i = j if j > i else i + 1
    return objects


def inspect_raw_prefix(text: str) -> dict[str, Any]:
    kinds = {
        "TOPIC": _count_kind(text, "TOPIC"),
        "IDEA": _count_kind(text, "IDEA"),
        "EXAMPLE": _count_kind(text, "EXAMPLE"),
        "REFERENCE": _count_kind(text, "REFERENCE"),
        "UNCERTAINTY": _count_kind(text, "UNCERTAINTY"),
        "REPETITION": _count_kind(text, "REPETITION"),
    }
    root_started = {key: bool(pattern.search(text)) for key, pattern in _ROOT_KEY_RE.items()}
    src_hits = _SRC_RE.findall(text)
    complete = extract_complete_objects(text)
    complete_by_kind: dict[str, list[dict[str, Any]]] = {
        "TOPIC": [],
        "IDEA": [],
        "EXAMPLE": [],
        "REFERENCE": [],
        "UNCERTAINTY": [],
        "REPETITION": [],
    }
    for item in complete:
        complete_by_kind[str(item.get("k"))].append(item)
    return {
        "label": "RAW_PREFIX_FORENSIC_ESTIMATE",
        "not_canonical": True,
        "not_provider_decoded": True,
        "raw_text_chars": len(text),
        "starts_with_object": text.startswith("{"),
        "unterminated_at_column": A38_UNTERMINATED_COLUMN,
        "kind_key_counts": kinds,
        "root_n_started": root_started["n"],
        "root_r_started": root_started["r"],
        "root_d_started": root_started["d"],
        "disposition_token_counts": {
            token: len(re.findall(rf'"{token}"', text))
            for token in (
                "KEEP",
                "MERGE_EQUIVALENT",
                "DROP",
                "OTHER",
                "LINK_RELATED",
            )
        },
        "src_identifier_occurrences": len(src_hits),
        "distinct_src_identifiers": len(set(src_hits)),
        "complete_objects_by_kind": {
            kind: len(rows) for kind, rows in complete_by_kind.items()
        },
        "complete_objects": complete_by_kind,
    }


def idea_similarity_forensics(
    prefix: Mapping[str, Any],
    local_ideas: SequenceLike,
) -> dict[str, Any]:
    extracted = list((prefix.get("complete_objects") or {}).get("IDEA") or [])
    local_values = [str(item.get("value") or "") for item in local_ideas]
    copied = 0
    lightly = 0
    rewritten = 0
    ratios: list[float] = []
    for item in extracted:
        value = str(item.get("v") or "")
        if not value or not local_values:
            continue
        best = max(SequenceMatcher(None, value, local).ratio() for local in local_values)
        ratios.append(best)
        if best >= 0.92:
            copied += 1
        elif best >= 0.72:
            lightly += 1
        else:
            rewritten += 1
    mean_ratio = (sum(ratios) / len(ratios)) if ratios else 0.0
    if copied >= lightly and copied >= rewritten:
        appearance = "mostly_copied_or_near_copy"
    elif lightly >= rewritten:
        appearance = "lightly_normalized"
    else:
        appearance = "meaningfully_rewritten"
    return {
        "label": "RAW_PREFIX_FORENSIC_ESTIMATE",
        "complete_idea_objects": len(extracted),
        "compared": len(ratios),
        "mean_best_ratio": round(mean_ratio, 4),
        "mostly_copied": copied,
        "lightly_normalized": lightly,
        "meaningfully_consolidated_or_rewritten": rewritten,
        "appearance": appearance,
        "interpretation": (
            "Forensic comparison of complete raw-prefix IDEA strings against "
            "normalized local idea text. Not a decoded global inventory."
        ),
    }


SequenceLike = list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...]


def input_estimate_review() -> dict[str, Any]:
    return {
        "a34_predicted_provider_adjusted_input": A34_INPUT_PREDICTION,
        "a38_actual_input": A38_INPUT_TOKENS,
        "error_tokens": A34_INPUT_ERROR_TOKENS,
        "error_percent": A34_INPUT_ERROR_PERCENT,
        "primary_architectural_failure": False,
        "note": "Reasonably close. Not the primary failure.",
    }


def output_estimate_review() -> dict[str, Any]:
    return {
        "a34_worst_case_output": A34_OUTPUT_PREDICTION,
        "a38_actual_output": A38_OUTPUT_TOKENS,
        "a38_complete": False,
        "actual_required_output": f">{A38_OUTPUT_TOKENS}",
        "status": "UNDERESTIMATED",
        "why": [
            "A.34 used chars/4 (~4.0 chars/token); A.38 observed "
            f"{A38_CHARS_PER_PROVIDER_OUTPUT_TOKEN:.3f} chars/token.",
            "A.34 assumed output would reuse/compress local text; A.38 emitted "
            "~281 global IDEA keys from 286 local ideas (almost no merge).",
            "Transport 1.1 repeats SRC arrays, full node text, and still owed "
            "r[] plus a 286-row d[] ledger that never started.",
            "A.34 sufficiency label was already MARGINAL (23.9% headroom).",
        ],
        "chars_per_token_model": {
            "a34_assumed": 4.0,
            "a38_observed": A38_CHARS_PER_PROVIDER_OUTPUT_TOKEN,
            "density_ratio_vs_a34": round(4.0 / A38_CHARS_PER_PROVIDER_OUTPUT_TOKEN, 3),
        },
    }


def transport_11_complete_output_range(prefix: Mapping[str, Any]) -> dict[str, Any]:
    ideas_seen = int((prefix.get("kind_key_counts") or {}).get("IDEA") or 0)
    remaining_ideas = max(0, 286 - ideas_seen)
    per_idea = A38_OUTPUT_TOKENS / max(ideas_seen, 1)
    remaining_core = remaining_ideas * per_idea
    examples = 49 * 55
    references = 59 * 45
    uncertainties = 35 * 45
    relations_low, relations_exp, relations_high = 80 * 18, 110 * 22, 140 * 28
    dispositions = 286 * 16
    low = int(A38_OUTPUT_TOKENS + remaining_core + examples * 0.6 + references * 0.6 + uncertainties * 0.6 + relations_low + dispositions)
    expected = int(A38_OUTPUT_TOKENS + remaining_core + examples + references + uncertainties + relations_exp + dispositions)
    high = int(A38_OUTPUT_TOKENS + remaining_core + examples * 1.3 + references * 1.3 + uncertainties * 1.3 + relations_high + dispositions * 1.2)
    return {
        "label": "TRANSPORT_1_1_COMPLETE_OUTPUT_ESTIMATE",
        "raw_prefix_ideas": ideas_seen,
        "implied_tokens_per_emitted_idea": round(per_idea, 1),
        "low": low,
        "expected": expected,
        "high": high,
        "feasibility_32000": "NO",
        "max_output_options": {
            "48000": "YES_BUT_FRAGILE" if low <= 48000 else "NO",
            "64000": "YES_WITH_SAFE_MARGIN" if high <= 64000 * 0.9 else "YES_BUT_FRAGILE",
            "96000": "YES_WITH_SAFE_MARGIN",
            "128000": "YES_WITH_SAFE_MARGIN",
        },
        "do_not_select_by_fit_alone": True,
    }


__all__ = [
    "classify_a38_failures",
    "extract_complete_objects",
    "idea_similarity_forensics",
    "input_estimate_review",
    "inspect_raw_prefix",
    "output_estimate_review",
    "transport_11_complete_output_range",
]
