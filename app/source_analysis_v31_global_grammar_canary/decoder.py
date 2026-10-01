"""Decoder global-consolidation-transport-1.0. Aucune réparation JSON."""

from __future__ import annotations

from typing import Any, Mapping

from app.ai.structured import parse_structured_output
from app.source_analysis_v31_global_grammar_canary.constants import NODE_KINDS
from app.source_analysis_v31_global_preflight.transport import (
    DISP_FIELDS,
    GM_FIELDS,
    NODE_FIELDS,
    REL_FIELDS,
    ROOT_FIELDS,
    build_global_consolidation_schema,
)


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def raw_transport_inventory(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {
            "gm": 0,
            "nodes": 0,
            "relations": 0,
            "dispositions": 0,
            "by_kind": {kind: 0 for kind in NODE_KINDS},
        }
    nodes = [item for item in _as_list(payload.get("n")) if isinstance(item, Mapping)]
    by_kind = {kind: 0 for kind in NODE_KINDS}
    for node in nodes:
        kind = str(node.get("k") or "")
        if kind in by_kind:
            by_kind[kind] += 1
    gm = payload.get("gm")
    return {
        "gm": 1 if isinstance(gm, Mapping) else 0,
        "nodes": len(nodes),
        "relations": len(_as_list(payload.get("r"))),
        "dispositions": len(_as_list(payload.get("d"))),
        "by_kind": by_kind,
        "TOPIC": by_kind["TOPIC"],
        "IDEA": by_kind["IDEA"],
        "EXAMPLE": by_kind["EXAMPLE"],
        "REFERENCE": by_kind["REFERENCE"],
        "UNCERTAINTY": by_kind["UNCERTAINTY"],
        "REPETITION": by_kind["REPETITION"],
    }


def decode_global_transport(
    payload: Mapping[str, Any] | None,
    *,
    raw_text: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    structured = "FAIL"
    working: Mapping[str, Any] | None = payload if isinstance(payload, Mapping) else None
    if working is None and raw_text:
        try:
            parsed = parse_structured_output(
                raw_text, build_global_consolidation_schema()
            )
            if isinstance(parsed, dict):
                working = parsed
                structured = "PASS"
            else:
                errors.append("parsed payload is not an object")
        except Exception as exc:  # noqa: BLE001 — forensic, no repair
            errors.append(str(exc))
    elif working is not None:
        try:
            parse_structured_output(
                json_dumps(working), build_global_consolidation_schema()
            )
            structured = "PASS"
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

    if not isinstance(working, Mapping):
        return {
            "ok": False,
            "structured_parse": structured,
            "decoder": "FAIL",
            "errors": errors or ["transport missing"],
            "transport": None,
            "inventory": raw_transport_inventory(None),
        }

    extra = [key for key in working if key not in ROOT_FIELDS]
    if extra:
        errors.append(f"unknown root fields: {extra}")
    gm = working.get("gm")
    if not isinstance(gm, Mapping):
        errors.append("gm missing")
    else:
        missing_gm = [field for field in GM_FIELDS if field not in gm]
        if missing_gm:
            errors.append(f"gm missing {missing_gm}")
    for index, node in enumerate(_as_list(working.get("n"))):
        if not isinstance(node, Mapping):
            errors.append(f"n[{index}] not an object")
            continue
        missing = [field for field in NODE_FIELDS if field not in node]
        if missing:
            errors.append(f"n[{index}] missing {missing}")
    for index, rel in enumerate(_as_list(working.get("r"))):
        if not isinstance(rel, Mapping):
            errors.append(f"r[{index}] not an object")
            continue
        missing = [field for field in REL_FIELDS if field not in rel]
        if missing:
            errors.append(f"r[{index}] missing {missing}")
    for index, row in enumerate(_as_list(working.get("d"))):
        if not isinstance(row, Mapping):
            errors.append(f"d[{index}] not an object")
            continue
        missing = [field for field in DISP_FIELDS if field not in row]
        if missing:
            errors.append(f"d[{index}] missing {missing}")

    inventory = raw_transport_inventory(working)
    ok = not errors
    return {
        "ok": ok,
        "structured_parse": structured,
        "decoder": "PASS" if ok else "FAIL",
        "errors": errors,
        "transport": dict(working),
        "inventory": inventory,
        "repaired": False,
    }


def json_dumps(payload: Mapping[str, Any]) -> str:
    import json

    return json.dumps(dict(payload), ensure_ascii=False)


__all__ = [
    "decode_global_transport",
    "raw_transport_inventory",
]
