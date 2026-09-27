"""Décomposition I44. Diagnostic only. Ne répare pas le payload historique."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.models import IDEA_KINDS
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v3_a22_forensics.replay import replay_a22_offline
from app.source_analysis_v3_a25_forensics.constants import (
    I44_CLASSIFICATION,
    INVALID_IDEA_HANDLE,
    INVALID_IDEA_INDEX,
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
)


def _records(transport: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(transport, Mapping):
        return []
    return [item for item in (transport.get("records") or []) if isinstance(item, Mapping)]


def _src_index(transcript: TranscriptInput, window: WindowInput) -> dict[str, str]:
    wanted = set(window.owned_src_refs)
    return {
        segment.src_id: segment.text
        for segment in transcript.segments
        if segment.src_id in wanted
    }


def _overlap_score(left: str, right: str) -> float:
    a = {tok for tok in left.lower().split() if len(tok) > 3}
    b = {tok for tok in right.lower().split() if len(tok) > 3}
    if not a or not b:
        return 0.0
    return round(len(a & b) / len(a | b), 3)


def _neighbors(
    records: list[Mapping[str, Any]],
    index: int,
    kinds: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for other_idx, other in enumerate(records):
        if str(other.get("k") or "") not in kinds:
            continue
        if abs(other_idx - index) > 4 and str(other.get("h") or "") not in {
            "I43",
            "I44",
            "I45",
        }:
            continue
        if other_idx == index:
            continue
        rows.append(
            {
                "index": other_idx,
                "k": other.get("k"),
                "h": other.get("h"),
                "l": other.get("l"),
                "m": other.get("m"),
                "v": other.get("v"),
                "s": other.get("s"),
            }
        )
    return rows


def decompose_i44(
    transport: Mapping[str, Any] | None,
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    project_name: str = PROJECT_NAME,
    sortie_dir: Any = None,
) -> dict[str, Any]:
    records = _records(transport)
    item = records[INVALID_IDEA_INDEX] if INVALID_IDEA_INDEX < len(records) else {}
    handle = str(item.get("h") or "")
    value = str(item.get("v") or "")
    refs = [str(ref) for ref in (item.get("s") or []) if isinstance(ref, str)]
    src_index = _src_index(transcript, window)
    examples = [
        (idx, row)
        for idx, row in enumerate(records)
        if str(row.get("k") or "") == "EXAMPLE"
    ]
    overlapping = []
    for ex_idx, example in examples:
        score = _overlap_score(value, str(example.get("v") or ""))
        linked = handle in [str(raw) for raw in (example.get("l") or [])]
        blob = f"{example.get('v') or ''} {' '.join(example.get('m') or [])}".lower()
        same_material = any(
            token in blob for token in ("economy", "biya", "cameroonian president")
        )
        src_overlap = sorted(
            set(refs)
            & {str(ref) for ref in (example.get("s") or []) if isinstance(ref, str)}
        )
        if linked or same_material or score >= 0.15 or src_overlap:
            overlapping.append(
                {
                    "example_index": ex_idx,
                    "example_v": example.get("v"),
                    "example_m": example.get("m"),
                    "example_l": example.get("l"),
                    "example_s": example.get("s"),
                    "links_to_i44": linked,
                    "value_overlap": score,
                    "shared_src": src_overlap,
                    "same_national_leader_economy_material": same_material,
                }
            )
    a22 = replay_a22_offline(project_name, sortie_dir=sortie_dir)
    a22_records = _records(a22.get("transport") if isinstance(a22, dict) else None)
    a22_hits = []
    for idx, row in enumerate(a22_records):
        blob = f"{row.get('v') or ''} {' '.join(row.get('m') or [])}".lower()
        if any(token in blob for token in ("economy", "biya", "national leader")):
            a22_hits.append(
                {
                    "index": idx,
                    "k": row.get("k"),
                    "h": row.get("h"),
                    "m": row.get("m"),
                    "l": row.get("l"),
                    "v": row.get("v"),
                }
            )
    has_valid_example = any(
        row.get("same_national_leader_economy_material") for row in overlapping
    )
    classification = (
        I44_CLASSIFICATION if has_valid_example else "COLLAPSED_WITHOUT_SEPARATE_EXAMPLE"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "diagnostic_only": True,
        "mutated_payload": False,
        "normalized_metadata": False,
        "converted_to_example": False,
        "index": INVALID_IDEA_INDEX,
        "expected_handle": INVALID_IDEA_HANDLE,
        "raw": {
            "k": item.get("k"),
            "v": item.get("v"),
            "s": refs,
            "h": handle,
            "l": item.get("l"),
            "m": item.get("m"),
        },
        "resolved_topic": item.get("l"),
        "clean_segments": [
            {"src": ref, "text": src_index.get(ref, "")} for ref in refs
        ],
        "neighboring_idea_records": _neighbors(records, INVALID_IDEA_INDEX, {"IDEA"}),
        "neighboring_example_records": [
            {
                "index": idx,
                "k": row.get("k"),
                "l": row.get("l"),
                "m": row.get("m"),
                "v": row.get("v"),
                "s": row.get("s"),
            }
            for idx, row in examples
            if abs(idx - INVALID_IDEA_INDEX) <= 40
        ],
        "neighboring_relation_records": [
            {
                "index": idx,
                "k": row.get("k"),
                "v": row.get("v"),
                "l": row.get("l"),
                "m": row.get("m"),
            }
            for idx, row in enumerate(records)
            if str(row.get("k") or "") == "RELATION"
            and handle in [str(raw) for raw in (row.get("l") or [])]
        ],
        "a22_representation": {
            "do_not_infer_a24_from_a22": True,
            "a22_rows": a22_hits,
            "a23_forensic_class_for_i53": "ILLUSTRATION_EMITTED_AS_IDEA",
            "a23_note": (
                "A.22 I53 was the collapsed national-leader IDEA; I54 held the "
                "domain-knowledge proposition; EXAMPLE 112 isolated Biya."
            ),
        },
        "a24_representation": {
            "i43": "valid IDEA instruction — remain relevant (Davos / own people)",
            "i44": "invalid IDEA kind=example — proposition + illustration collapsed",
            "example_88": (
                "valid EXAMPLE case_study of Cameroonian president / economy, "
                "linked to I44"
            ),
            "relation_78": "illustrates I44 → I43",
        },
        "semantic_decomposition": {
            "proposition": (
                "A person sent for a purpose must have relevant knowledge of "
                "the domain they are meant to serve."
            ),
            "illustration": (
                "A national leader (Paul Biya / Cameroonian president) "
                "consistently addresses the economy in every public discourse."
            ),
            "supporting_relation": (
                "The illustration supports I43 (remain relevant to one's people "
                "and domain). RELATION 78 encodes illustrates(I44, I43)."
            ),
            "not_repaired": True,
        },
        "duplicate_example_check": {
            "valid_example_for_same_material": has_valid_example,
            "overlapping_examples": overlapping,
            "classification": classification,
            "inferred_from_a22": False,
        },
        "why_kind_example_after_1_3_2": {
            "prompt_forbids_idea_kind_example": True,
            "passage_is_inherently_illustrative": True,
            "model_named_the_speech_act": (
                "I44.v itself says the leader 'illustrates the principle'."
            ),
            "m0_overloaded": (
                "m[0] means IDEA semantic kind here and EXAMPLE kind elsewhere. "
                "The token 'example' is legal for EXAMPLE.m[0] and adjacent in "
                "the prompt vocabulary."
            ),
            "not_a_missing_example": (
                "EXAMPLE 88 already isolates the same material. I44 is not a "
                "fallback for a missing EXAMPLE."
            ),
            "q1_answer": (
                "I44 received kind 'example' because the model classified the "
                "record by its illustrative surface rather than by record kind. "
                "Prompt 1.3.2 forbids that token but cannot structurally stop "
                "m[0] leakage on a passage whose own wording is 'illustrates'."
            ),
        },
        "metadata_kind_valid": (
            isinstance(item.get("m"), list)
            and item.get("m")
            and item["m"][0] in IDEA_KINDS
        ),
        "classification": classification,
        "handle_matches_expected": handle == INVALID_IDEA_HANDLE,
    }


__all__ = ["decompose_i44"]
