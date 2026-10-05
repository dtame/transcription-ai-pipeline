"""Offline FakeAI for the synthetic canary. Not Terra quality. No network."""

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
from app.book_semantic_gate_4b262.contract import unnecessary_duplication_absent
from app.book_semantic_gate_4b275.coverage import validate_compact_payload_113
from app.book_semantic_gate_4b275.fakeai import run_offline_fixtures
from app.book_semantic_gate_4b276.constants import (
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    DISPUTED_CLAUSE,
    P4_EVIDENCE_HANDLES,
    PHASE,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_REASON_CODES_AUDIT_ONLY,
)
from app.book_semantic_gate_4b276.identity import clause_offsets


def _prefix_end(text: str, clause_start: int) -> int:
    end = clause_start
    while end > 0 and text[end - 1] in " ,":
        end -= 1
    return end


def simulated_selected_compact(payload: Mapping[str, Any]) -> dict[str, Any]:
    paragraphs = extract_gate_paragraphs(payload)
    para = next(
        item for item in paragraphs if str(item.get("handle") or "") == SELECTED_CASE_HANDLE
    )
    text = str(para.get("text") or "")
    offsets = clause_offsets(text)
    start = int(offsets["start"])
    end = int(offsets["end"])
    prefix_end = _prefix_end(text, start)
    evidence = list(P4_EVIDENCE_HANDLES)
    claims = [
        {
            "i": 0,
            "s": 0,
            "e": prefix_end,
            "k": CLASS_SUPPORTED,
            "ev": evidence,
            "r": [],
        },
        {
            "i": 1,
            "s": start,
            "e": end,
            "k": CLASS_UNSUPPORTED,
            "ev": [],
            "r": list(SELECTED_CASE_REASON_CODES_AUDIT_ONLY),
            "n": "The which-means guarantee is not attested.",
        },
    ]
    return {
        "ch": "CH016",
        "v": "FAIL",
        "pr": [
            {
                "h": SELECTED_CASE_HANDLE,
                "v": CLASS_UNSUPPORTED,
                "c": claims,
                "ev": evidence,
                "r": list(SELECTED_CASE_REASON_CODES_AUDIT_ONLY),
            }
        ],
        "sc": {
            "supported": 1,
            "questionable": 0,
            "unsupported": 1,
            "non_substantive": 0,
        },
        "uh": [],
        "rr": False,
    }


def interpret_selected_simulation(
    payload: Mapping[str, Any],
    *,
    root=None,
) -> dict[str, Any]:
    compact = simulated_selected_compact(payload)
    paragraphs = extract_gate_paragraphs(payload)
    texts = {
        str(item.get("handle") or ""): str(item.get("text") or "") for item in paragraphs
    }
    validation = validate_compact_payload_113(
        compact,
        paragraph_texts=texts,
        required_handles=[SELECTED_CASE_HANDLE],
        paragraph_kinds={SELECTED_CASE_HANDLE: "substantive"},
    )
    para = (compact.get("pr") or [{}])[0]
    flagged = next(
        (
            item
            for item in para.get("c") or []
            if "NEW_IMPLICATION" in (item.get("r") or [])
        ),
        None,
    )
    text = texts.get(SELECTED_CASE_HANDLE) or ""
    recovered = ""
    if flagged is not None:
        recovered = text[int(flagged["s"]) : int(flagged["e"])]
    return {
        "compact": compact,
        "validation": validation,
        "implication_blocked": para.get("v") in {"QUESTIONABLE", "UNSUPPORTED"},
        "implication_claim_flagged": flagged is not None,
        "flagged_span_is_disputed_clause": recovered == DISPUTED_CLAUSE,
        "supported_prefix_accepted": any(
            item.get("k") == CLASS_SUPPORTED for item in para.get("c") or []
        ),
        "global_verdict_blocks_acceptance": compact.get("v") in {"REVIEW", "FAIL"},
        "no_unnecessary_duplication": unnecessary_duplication_absent(compact),
        "fakeai_not_terra_quality": True,
    }


def historical_ten_case_protection(*, root=None) -> dict[str, Any]:
    fixtures = run_offline_fixtures(root=root)
    historical = dict(fixtures.get("historical") or {})
    return {
        "phase": PHASE,
        "positives_accepted": fixtures.get("fakeai_positives"),
        "negatives_blocked": fixtures.get("fakeai_negatives"),
        "funeral_blocked": (historical.get("protected") or {}).get(FUNERAL_CASE_ID),
        "connective_blocked": (historical.get("protected") or {}).get(CONNECTIVE_CASE_ID),
        "p3_blocked": (historical.get("protected") or {}).get(P3_CASE_ID),
        "p8_blocked": (historical.get("protected") or {}).get(P8_CASE_ID),
        "protected": historical.get("protected"),
        "historical_catalog_passed": bool(run_fakeai_catalog().get("passed")),
        "fixtures_passed": fixtures.get("passed"),
        "fakeai_not_terra_quality": True,
        "labels_unmodified": True,
        "historical_ten_cases_preserved": True,
        "does_not_prove_terra_verdicts": True,
    }


__all__ = [
    "historical_ten_case_protection",
    "interpret_selected_simulation",
    "simulated_selected_compact",
]
