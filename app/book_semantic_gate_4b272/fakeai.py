"""Offline FakeAI for the P3 freeze. Not Terra quality. No network."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_semantic_gate_4b23.fakeai import run_fakeai_catalog
from app.book_semantic_gate_4b24.constants import (
    CONNECTIVE_CASE_ID,
    FUNERAL_CASE_ID,
    P3_CASE_ID,
    P8_CASE_ID,
)
from app.book_semantic_gate_4b261.complexity import extract_gate_paragraphs
from app.book_semantic_gate_4b261.evidence import load_4b26_bundle
from app.book_semantic_gate_4b262.contract import unnecessary_duplication_absent
from app.book_semantic_gate_4b262.fakeai import interpret_ten_case_compact
from app.book_semantic_gate_4b271.coverage import validate_compact_payload_111
from app.book_semantic_gate_4b272.constants import (
    CLASS_QUESTIONABLE,
    PHASE,
    SELECTED_CASE_HANDLE,
)
from app.book_semantic_gate_4b272.coverage import (
    claims_from_propositions,
    p3_local_propositions,
)


def simulated_p3_compact(payload: Mapping[str, Any]) -> dict[str, Any]:
    paragraphs = extract_gate_paragraphs(payload)
    para = next(
        item for item in paragraphs if str(item.get("handle") or "") == SELECTED_CASE_HANDLE
    )
    text = str(para.get("text") or "")
    claims = claims_from_propositions(p3_local_propositions(text))
    supported = sum(1 for item in claims if item["k"] != CLASS_QUESTIONABLE)
    questionable = sum(1 for item in claims if item["k"] == CLASS_QUESTIONABLE)
    return {
        "ch": "CH016",
        "v": "REVIEW",
        "pr": [
            {
                "h": SELECTED_CASE_HANDLE,
                "v": CLASS_QUESTIONABLE,
                "c": claims,
                "ev": list(para.get("src") or [])[:2],
                "r": ["NEW_CAUSAL_LINK"],
            }
        ],
        "sc": {
            "supported": supported,
            "questionable": questionable,
            "unsupported": 0,
            "non_substantive": 0,
        },
        "uh": [],
        "rr": True,
    }


def interpret_p3_simulation(
    payload: Mapping[str, Any],
    *,
    root=None,
) -> dict[str, Any]:
    compact = simulated_p3_compact(payload)
    paragraphs = extract_gate_paragraphs(payload)
    texts = {
        str(item.get("handle") or ""): str(item.get("text") or "") for item in paragraphs
    }
    validation = validate_compact_payload_111(
        compact,
        paragraph_texts=texts,
        required_handles=[SELECTED_CASE_HANDLE],
        paragraph_kinds={SELECTED_CASE_HANDLE: "substantive"},
    )
    para = (compact.get("pr") or [{}])[0]
    causal = next(
        (item for item in para.get("c") or [] if "NEW_CAUSAL_LINK" in (item.get("r") or [])),
        None,
    )
    return {
        "compact": compact,
        "validation": validation,
        "p3_blocked": para.get("v") in {"QUESTIONABLE", "UNSUPPORTED"},
        "causal_claim_flagged": causal is not None,
        "global_verdict_blocks_acceptance": compact.get("v") in {"REVIEW", "FAIL"},
        "no_unnecessary_duplication": unnecessary_duplication_absent(compact),
        "fakeai_not_terra_quality": True,
    }


def historical_ten_case_protection(*, root=None) -> dict[str, Any]:
    bundle = load_4b26_bundle(root=root)
    ten = interpret_ten_case_compact(dict(bundle.get("payload") or {}), root=root)
    score = dict(ten.get("score") or {})
    return {
        "phase": PHASE,
        "positives_accepted": score.get("positives_accepted"),
        "negatives_blocked": score.get("negatives_blocked"),
        "funeral_blocked": score.get("funeral_blocked"),
        "connective_blocked": score.get("connective_blocked"),
        "p3_blocked": score.get("p3_blocked"),
        "p8_blocked": score.get("p8_blocked"),
        "protected": {
            FUNERAL_CASE_ID: bool(score.get("funeral_blocked")),
            CONNECTIVE_CASE_ID: bool(score.get("connective_blocked")),
            P3_CASE_ID: bool(score.get("p3_blocked")),
            P8_CASE_ID: bool(score.get("p8_blocked")),
        },
        "historical_catalog_passed": bool(run_fakeai_catalog().get("passed")),
        "validation_status": (ten.get("validation") or {}).get("status"),
        "fakeai_not_terra_quality": True,
        "labels_unmodified": True,
        "does_not_prove_terra_verdicts": True,
    }


__all__ = [
    "historical_ten_case_protection",
    "interpret_p3_simulation",
    "simulated_p3_compact",
]
