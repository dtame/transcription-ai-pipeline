"""FakeAI for contract 2.0. Simulated responses only. Not Terra quality."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
)
from app.book_semantic_gate_4b29.constants import (
    FAKEAI_SOURCE,
    MODEL_VERDICT_FAIL,
    MODEL_VERDICT_PASS,
    MODEL_VERDICT_REVIEW,
    NOT_TERRA,
    PHASE,
)
from app.book_semantic_gate_4b29.preparation import prepare_paragraph_units
from app.book_semantic_gate_4b29.request import build_model_request

_COUNT_KEYS = {
    CLASS_SUPPORTED: "supported",
    CLASS_QUESTIONABLE: "questionable",
    CLASS_UNSUPPORTED: "unsupported",
    CLASS_NON_SUBSTANTIVE: "non_substantive",
}


def _counts(kinds: list[str]) -> dict[str, int]:
    result = {
        "supported": 0,
        "questionable": 0,
        "unsupported": 0,
        "non_substantive": 0,
    }
    for kind in kinds:
        result[_COUNT_KEYS[kind]] += 1
    return result


def _worst(kinds: list[str]) -> str:
    if CLASS_UNSUPPORTED in kinds:
        return CLASS_UNSUPPORTED
    if CLASS_QUESTIONABLE in kinds:
        return CLASS_QUESTIONABLE
    if CLASS_NON_SUBSTANTIVE in kinds and CLASS_SUPPORTED not in kinds:
        return CLASS_NON_SUBSTANTIVE
    return CLASS_SUPPORTED


def _global_from_kinds(kinds: list[str]) -> tuple[str, bool]:
    if CLASS_UNSUPPORTED in kinds:
        return MODEL_VERDICT_FAIL, True
    if CLASS_QUESTIONABLE in kinds:
        return MODEL_VERDICT_REVIEW, True
    return MODEL_VERDICT_PASS, False


def _unit_row(
    unit_id: str,
    kind: str,
    *,
    evidence: list[str] | None = None,
    reasons: list[str] | None = None,
    note: str = "",
) -> dict[str, Any]:
    row = {
        "id": unit_id,
        "k": kind,
        "ev": list(evidence or []),
        "r": list(reasons or []),
    }
    if note:
        row["n"] = note
    return row


def _payload(
    *,
    chapter: str,
    handle: str,
    rows: list[dict[str, Any]],
    global_verdict: str | None = None,
    review: bool | None = None,
    unknown: list[str] | None = None,
    counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    kinds = [str(row.get("k") or "") for row in rows]
    computed_global, computed_review = _global_from_kinds(kinds)
    return {
        "ch": chapter,
        "v": computed_global if global_verdict is None else global_verdict,
        "pr": [
            {
                "h": handle,
                "v": _worst(kinds) if kinds else CLASS_SUPPORTED,
                "u": rows,
            }
        ],
        "sc": counts if counts is not None else _counts(kinds),
        "uh": list(unknown or []),
        "rr": computed_review if review is None else review,
    }


def _ids(prepared: Mapping[str, Any]) -> list[str]:
    return [str(unit.get("unit_id") or "") for unit in prepared.get("units") or []]


def _evidence(prepared: Mapping[str, Any]) -> list[str]:
    return list(prepared.get("evidence_handles") or [])


def _supported_rows(prepared: Mapping[str, Any]) -> list[dict[str, Any]]:
    ev = _evidence(prepared)[:1]
    return [_unit_row(uid, CLASS_SUPPORTED, evidence=ev) for uid in _ids(prepared)]


def _target_unit(prepared: Mapping[str, Any], needle: str) -> str:
    for unit in prepared.get("units") or []:
        if needle and needle in str(unit.get("text") or ""):
            return str(unit.get("unit_id") or "")
    ids = _ids(prepared)
    return ids[-1] if ids else "u00"


def build_scenario_payload(
    name: str,
    prepared: Mapping[str, Any],
    *,
    chapter: str = "CH016",
) -> Any:
    handle = str(prepared.get("paragraph_id") or "")
    ev = _evidence(prepared)[:1]
    ids = _ids(prepared)
    supported = _supported_rows(prepared)
    if name == "all_supported":
        return _payload(chapter=chapter, handle=handle, rows=supported)
    if name == "legitimate_paraphrase":
        return _payload(chapter=chapter, handle=handle, rows=supported)
    if name == "invented_causality":
        target = _target_unit(prepared, "because")
        rows = []
        for uid in ids:
            if uid == target:
                rows.append(
                    _unit_row(
                        uid,
                        CLASS_UNSUPPORTED,
                        evidence=ev,
                        reasons=["NEW_CAUSAL_LINK"],
                        note="Invented causality is not in the supplied evidence.",
                    )
                )
            else:
                rows.append(_unit_row(uid, CLASS_SUPPORTED, evidence=ev))
        return _payload(chapter=chapter, handle=handle, rows=rows)
    if name == "invented_implication":
        target = _target_unit(prepared, "which means")
        rows = []
        for uid in ids:
            if uid == target:
                rows.append(
                    _unit_row(
                        uid,
                        CLASS_UNSUPPORTED,
                        evidence=ev,
                        reasons=["NEW_IMPLICATION"],
                        note="Implication is not demonstrated by the evidence.",
                    )
                )
            else:
                rows.append(_unit_row(uid, CLASS_SUPPORTED, evidence=ev))
        return _payload(chapter=chapter, handle=handle, rows=rows)
    if name == "universal_guarantee":
        target = _target_unit(prepared, "guaranteed")
        rows = []
        for uid in ids:
            if uid == target:
                rows.append(
                    _unit_row(
                        uid,
                        CLASS_UNSUPPORTED,
                        evidence=ev,
                        reasons=["NEW_CONCLUSION", "UNCERTAINTY_STRENGTHENED"],
                        note="Universal guarantee is not supported.",
                    )
                )
            else:
                rows.append(_unit_row(uid, CLASS_SUPPORTED, evidence=ev))
        return _payload(chapter=chapter, handle=handle, rows=rows)
    if name == "missing_unit":
        return _payload(chapter=chapter, handle=handle, rows=supported[:-1] or [])
    if name == "duplicate_unit":
        rows = list(supported)
        if rows:
            rows.append(dict(rows[0]))
        return _payload(chapter=chapter, handle=handle, rows=rows)
    if name == "unknown_unit":
        rows = list(supported)
        rows.append(_unit_row("u99", CLASS_SUPPORTED, evidence=ev))
        return _payload(chapter=chapter, handle=handle, rows=rows)
    if name == "unknown_reason_code":
        target = ids[0] if ids else "u00"
        rows = []
        for uid in ids:
            if uid == target:
                rows.append(
                    _unit_row(
                        uid,
                        CLASS_UNSUPPORTED,
                        evidence=ev,
                        reasons=["MADE_UP_CODE"],
                        note="Unknown reason code fixture.",
                    )
                )
            else:
                rows.append(_unit_row(uid, CLASS_SUPPORTED, evidence=ev))
        return _payload(chapter=chapter, handle=handle, rows=rows)
    if name == "unknown_evidence_handle":
        target = ids[0] if ids else "u00"
        rows = []
        for uid in ids:
            if uid == target:
                rows.append(_unit_row(uid, CLASS_SUPPORTED, evidence=["SRC999999"]))
            else:
                rows.append(_unit_row(uid, CLASS_SUPPORTED, evidence=ev))
        return _payload(chapter=chapter, handle=handle, rows=rows)
    if name == "incoherent_global_verdict":
        return _payload(
            chapter=chapter,
            handle=handle,
            rows=supported,
            global_verdict=MODEL_VERDICT_FAIL,
            review=False,
        )
    if name == "invalid_json":
        return "{not json"
    if name == "truncated_response":
        return '{"ch":"CH016","v":"PASS"'
    if name == "questionable":
        target = ids[0] if ids else "u00"
        rows = []
        for uid in ids:
            if uid == target:
                rows.append(
                    _unit_row(
                        uid,
                        CLASS_QUESTIONABLE,
                        evidence=ev,
                        reasons=["OTHER"],
                        note="Reservation requires human review.",
                    )
                )
            else:
                rows.append(_unit_row(uid, CLASS_SUPPORTED, evidence=ev))
        return _payload(chapter=chapter, handle=handle, rows=rows)
    if name == "abusive_non_substantive":
        target = ids[0] if ids else "u00"
        rows = []
        for uid in ids:
            if uid == target:
                rows.append(_unit_row(uid, CLASS_NON_SUBSTANTIVE, evidence=[]))
            else:
                rows.append(_unit_row(uid, CLASS_SUPPORTED, evidence=ev))
        return _payload(chapter=chapter, handle=handle, rows=rows)
    raise KeyError(name)


SCENARIO_NAMES = (
    "all_supported",
    "legitimate_paraphrase",
    "invented_causality",
    "invented_implication",
    "universal_guarantee",
    "missing_unit",
    "duplicate_unit",
    "unknown_unit",
    "unknown_reason_code",
    "unknown_evidence_handle",
    "incoherent_global_verdict",
    "invalid_json",
    "truncated_response",
    "questionable",
    "abusive_non_substantive",
)


class FakeAITransport:
    """Scripted local transport. Identified as FakeAI. Never Terra."""

    source = FAKEAI_SOURCE
    not_terra = NOT_TERRA

    def __init__(self, scenario: str, prepared: Mapping[str, Any], *, chapter: str = "CH016") -> None:
        if scenario not in SCENARIO_NAMES:
            raise KeyError(scenario)
        self.scenario = scenario
        self.prepared = prepared
        self.chapter = chapter

    def evaluate(self, request: Mapping[str, Any]) -> Any:
        return build_scenario_payload(self.scenario, self.prepared, chapter=self.chapter)


def wrap_simulated(payload: Any, scenario: str) -> dict[str, Any]:
    return {
        "source": FAKEAI_SOURCE,
        "not_terra": True,
        "not_a_terra_response": True,
        "scenario": scenario,
        "payload": payload,
        "raw_preserved": payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False),
    }


def run_fakeai_scenarios(
    text: str,
    *,
    paragraph_id: str = "demo",
    evidence_handles: list[str] | None = None,
    chapter: str = "CH016",
) -> dict[str, Any]:
    prepared = prepare_paragraph_units(
        paragraph_id,
        text,
        evidence_handles=evidence_handles or ["IDEA000"],
    )
    request = build_model_request(prepared, chapter_handle=chapter)
    rows = []
    for name in SCENARIO_NAMES:
        payload = build_scenario_payload(name, prepared, chapter=chapter)
        wrapped = wrap_simulated(payload, name)
        rows.append(
            {
                "scenario": name,
                "source": FAKEAI_SOURCE,
                "not_terra": True,
                "payload_type": type(payload).__name__,
            }
        )
        _ = wrapped
    return {
        "phase": PHASE,
        "source": FAKEAI_SOURCE,
        "not_terra": True,
        "not_a_terra_validation": True,
        "scenario_count": len(rows),
        "scenarios": rows,
        "request_omits_human_labels": request.get("human_labels_included") is False,
        "passed": len(rows) == len(SCENARIO_NAMES),
        "secrets_included": False,
    }


__all__ = [
    "FakeAITransport",
    "SCENARIO_NAMES",
    "build_scenario_payload",
    "run_fakeai_scenarios",
    "wrap_simulated",
]
