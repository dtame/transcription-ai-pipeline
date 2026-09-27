"""Delta sémantique A.22 vs A.24. Ne promeut pas A.24. 0 provider."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v3_a22_forensics.coverage import _AUDIT_OUTLINE, _blob
from app.source_analysis_v3_a22_forensics.replay import replay_a22_offline
from app.source_analysis_v3_a25_forensics.constants import (
    A22_EXAMPLE,
    A22_IDEA,
    A22_RECORDS,
    A22_REFERENCE,
    A22_RELATION,
    A22_UNCERTAINTY,
    A24_EXAMPLE,
    A24_IDEA,
    A24_RECORDS,
    A24_REFERENCE,
    A24_RELATION,
    A24_UNCERTAINTY,
    MISSING_IDEA_AUTOMATED,
    MISSING_IDEA_INDEPENDENT,
    MISSING_IDEA_MATERIALITY,
    MODE,
    PARTIAL_IDEA,
    PARTIAL_IDEA_VS_A23,
    PHASE,
    PROJECT_NAME,
    PROMPT_132_EFFECT,
    SCHEMA_VERSION,
)


def _records(transport: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(transport, Mapping):
        return []
    return [item for item in (transport.get("records") or []) if isinstance(item, Mapping)]


def _hits(blob: str, needles: tuple[str, ...]) -> list[str]:
    return [needle for needle in needles if needle in blob]


def _status(hits: list[str], needles: tuple[str, ...]) -> str:
    if not hits:
        return "missing"
    if len(hits) < len(needles):
        return "partial"
    return "represented"


def _outline_rows(blob: str) -> list[dict[str, Any]]:
    rows = []
    for index, (label, needles, expected) in enumerate(_AUDIT_OUTLINE, start=1):
        found = _hits(blob, needles)
        rows.append(
            {
                "outline_item": index,
                "label": label,
                "needles": list(needles),
                "hits": found,
                "needle_status": _status(found, needles),
                "expected_from_clean_read": expected,
            }
        )
    return rows


def _independent_fall(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    rows = []
    for index, item in enumerate(records):
        blob = f"{item.get('v') or ''} {' '.join(item.get('m') or [])}".lower()
        if any(
            token in blob
            for token in (
                "sinned",
                "tree of life",
                "dying you shall die",
                "life (not a body part) was cut",
                "life was cut",
                "before sin",
            )
        ):
            rows.append(
                {
                    "index": index,
                    "k": item.get("k"),
                    "h": item.get("h"),
                    "v": item.get("v"),
                }
            )
    return {
        "automated_missing_label": MISSING_IDEA_AUTOMATED,
        "independent_class": MISSING_IDEA_INDEPENDENT,
        "completely_absent": False,
        "merged_or_compressed": True,
        "nearest_related_records": rows,
        "clean_src_ranges": [
            "SRC004322–SRC004361 (TOPIC T9 / death as separation)",
            "I28–I31 cite SRC around the Fall / tree of life / dying you shall die",
        ],
        "short_neutral_description": (
            "The Fall: life cut off from the tree of life; death as a process; "
            "inherited corruption of the soul."
        ),
        "a22_representation": "partial (needle hit: good and evil only)",
        "a24_needle_hits": [],
        "materiality": MISSING_IDEA_MATERIALITY,
        "note": (
            "A.24 automated needles required 'committed sin' / 'life was cut' / "
            "'good and evil'. I29 says 'When man sinned, life (not a body part) "
            "was cut off' — a paraphrase the needle missed. 'good and evil' is "
            "absent as a phrase. The teaching is present, not omitted."
        ),
    }


def _independent_partial(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    rows = []
    for index, item in enumerate(records):
        blob = f"{item.get('v') or ''} {' '.join(item.get('m') or [])}".lower()
        if any(
            token in blob
            for token in ("fingerprint", "father sent", "fasting", "no explicit condition")
        ):
            rows.append(
                {
                    "index": index,
                    "k": item.get("k"),
                    "h": item.get("h"),
                    "v": item.get("v"),
                }
            )
    return {
        "label": PARTIAL_IDEA,
        "same_as_a23_partial": False,
        "a23_partial_was": MISSING_IDEA_AUTOMATED,
        "vs_a23": PARTIAL_IDEA_VS_A23,
        "nearest_related_records": rows,
        "note": (
            "I7 covers 'no explicit condition / fasting'. 'unique spiritual "
            "fingerprint' and 'father sent' are not lexicalized. Different "
            "partial item than A.23's Fall partial."
        ),
    }


def build_semantic_delta(
    transport: Mapping[str, Any] | None,
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    coverage: Mapping[str, Any],
    project_name: str = PROJECT_NAME,
    sortie_dir: Any = None,
) -> dict[str, Any]:
    a24_records = _records(transport)
    a22 = replay_a22_offline(project_name, sortie_dir=sortie_dir)
    a22_records = _records(a22.get("transport") if isinstance(a22, dict) else None)
    a24_blob = _blob(a24_records)
    a22_blob = _blob(a22_records)
    a24_outline = _outline_rows(a24_blob)
    a22_outline = _outline_rows(a22_blob)
    fall = _independent_fall(a24_records)
    partial = _independent_partial(a24_records)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "a22_not_gold_truth": True,
        "a24_not_repaired": True,
        "record_distribution": {
            "a22": {
                "records": A22_RECORDS,
                "IDEA": A22_IDEA,
                "RELATION": A22_RELATION,
                "EXAMPLE": A22_EXAMPLE,
                "REFERENCE": A22_REFERENCE,
                "UNCERTAINTY": A22_UNCERTAINTY,
            },
            "a24": {
                "records": A24_RECORDS,
                "IDEA": A24_IDEA,
                "RELATION": A24_RELATION,
                "EXAMPLE": A24_EXAMPLE,
                "REFERENCE": A24_REFERENCE,
                "UNCERTAINTY": A24_UNCERTAINTY,
            },
            "delta": {
                "records": A24_RECORDS - A22_RECORDS,
                "IDEA": A24_IDEA - A22_IDEA,
                "RELATION": A24_RELATION - A22_RELATION,
                "EXAMPLE": 0,
                "REFERENCE": 0,
                "UNCERTAINTY": 0,
            },
            "reduction_analysis": {
                "better_deduplication": (
                    "Plausible. A.22 had four invalid IDEA/example rows plus "
                    "matching EXAMPLEs; A.24 kept EXAMPLE count at 9 and cut "
                    "invalid IDEA/example from 4 to 1."
                ),
                "under_extraction": (
                    "Partial evidence: unique spiritual fingerprint / father "
                    "sent is thinner than A.22."
                ),
                "prompt_side_effect": (
                    "Possible but not proven. 1.3.2 added IDEA/EXAMPLE "
                    "separation rules; EXAMPLE/REFERENCE/UNCERTAINTY counts "
                    "are identical."
                ),
                "normal_stochastic_variation": (
                    "Likely a contributor. Two thinking-disabled runs of the "
                    "same window need not match record counts."
                ),
                "overall": "MIXED_DEDUP_PLUS_STOCHASTIC_PLUS_SOME_UNDER_EXTRACTION",
            },
        },
        "prompt_1_3_2_effectiveness": {
            "invalid_idea_example": {"a22": 4, "a24": 1},
            "three_known_patterns_corrected": [
                "colonial_tutors_shirt",
                "minister_testimony_formula",
                "pig_heart_liver",
            ],
            "one_pattern_persisted": "national_leader_economy",
            "descriptive": "IMPROVED",
            "reliably_enforced": False,
            "conclusion": PROMPT_132_EFFECT,
            "do_not_call_reliable_because_count_fell": True,
        },
        "major_idea_delta": {
            "a23_forensic_reference": "15 represented / 1 partial / 0 missing",
            "a24_automated_needles": {
                "represented": coverage.get("major_ideas_represented"),
                "partial": coverage.get("major_ideas_partial"),
                "missing": coverage.get("major_ideas_missing"),
            },
            "a24_outline_needles": a24_outline,
            "a22_outline_needles": a22_outline,
            "missing_idea_automated": fall,
            "partial_idea": partial,
            "do_not_blame_transport_failure_for_missing_idea": True,
            "cause_of_reported_missing": "LIKELY_STOCHASTIC_EXTRACTION_VARIANCE",
            "cause_note": (
                "The reported miss is a needle false negative plus absence of "
                "the phrase 'good and evil'. Output truncation is unsupported "
                "(10559/32000, finish=end_turn, capacity absent). Local input "
                "22957 <= 35000 is not a cause. Not a taxonomy-side-effect: "
                "I28–I31 have valid IDEA kinds."
            ),
            "output_pressure": False,
            "input_pressure": False,
        },
        "window": {
            "window_id": window.window_id,
            "owned": len(window.owned_src_refs),
            "transcript_id": transcript.transcript_id,
        },
    }


__all__ = ["build_semantic_delta"]
