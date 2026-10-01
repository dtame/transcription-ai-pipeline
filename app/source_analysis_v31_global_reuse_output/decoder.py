"""Decoder global-consolidation-transport-3.0. Aucune réparation JSON."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.ai.structured import parse_structured_output
from app.source_analysis_v31_global_preflight.transport import GM_FIELDS
from app.source_analysis_v31_global_reuse_output.transport_v30 import (
    DROP_FIELDS,
    EXAMPLE_FIELDS,
    IDEA_REQUIRED_FIELDS,
    REF_FIELDS,
    ROOT_FIELDS,
    TOPIC_FIELDS,
    UNC_FIELDS,
    build_global_consolidation_schema_v30,
)
from app.source_analysis_v31_global_v20_grammar_canary.decoder import (
    raw_transport_inventory_v20,
)


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def decode_global_transport_v30(
    payload: Mapping[str, Any] | None,
    *,
    raw_text: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    structured = "FAIL"
    working: Mapping[str, Any] | None = payload if isinstance(payload, Mapping) else None
    schema = build_global_consolidation_schema_v30()
    if working is None and raw_text:
        try:
            parsed = parse_structured_output(raw_text, schema)
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
                json.dumps(dict(working), ensure_ascii=False), schema
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
            "inventory": raw_transport_inventory_v20(None),
            "repaired": False,
        }

    extra = [key for key in working if key not in ROOT_FIELDS]
    if extra:
        errors.append(f"unknown root fields: {extra}")
    if "r" in working:
        errors.append("r[] is not part of transport 3.0")
    if "d" in working:
        errors.append("d[] disposition ledger is not part of transport 3.0")
    if "n" in working:
        errors.append("n[] is not part of transport 3.0")
    gm = working.get("gm")
    if not isinstance(gm, Mapping):
        errors.append("gm missing")
    else:
        missing_gm = [field for field in GM_FIELDS if field not in gm]
        if missing_gm:
            errors.append(f"gm missing {missing_gm}")
    for index, topic in enumerate(_as_list(working.get("t"))):
        if not isinstance(topic, Mapping):
            errors.append(f"t[{index}] not an object")
            continue
        missing = [field for field in TOPIC_FIELDS if field not in topic]
        if missing:
            errors.append(f"t[{index}] missing {missing}")
    for index, idea in enumerate(_as_list(working.get("i"))):
        if not isinstance(idea, Mapping):
            errors.append(f"i[{index}] not an object")
            continue
        missing = [field for field in IDEA_REQUIRED_FIELDS if field not in idea]
        if missing:
            errors.append(f"i[{index}] missing {missing}")
        if "s" in idea:
            errors.append(f"i[{index}]: provider must not emit SRC arrays")
    for index, row in enumerate(_as_list(working.get("x"))):
        if not isinstance(row, Mapping):
            errors.append(f"x[{index}] not an object")
            continue
        missing = [field for field in EXAMPLE_FIELDS if field not in row]
        if missing:
            errors.append(f"x[{index}] missing {missing}")
    for index, row in enumerate(_as_list(working.get("f"))):
        if not isinstance(row, Mapping):
            errors.append(f"f[{index}] not an object")
            continue
        missing = [field for field in REF_FIELDS if field not in row]
        if missing:
            errors.append(f"f[{index}] missing {missing}")
    for index, row in enumerate(_as_list(working.get("u"))):
        if not isinstance(row, Mapping):
            errors.append(f"u[{index}] not an object")
            continue
        missing = [field for field in UNC_FIELDS if field not in row]
        if missing:
            errors.append(f"u[{index}] missing {missing}")
    for index, row in enumerate(_as_list(working.get("drop"))):
        if not isinstance(row, Mapping):
            errors.append(f"drop[{index}] not an object")
            continue
        missing = [field for field in DROP_FIELDS if field not in row]
        if missing:
            errors.append(f"drop[{index}] missing {missing}")

    inventory = raw_transport_inventory_v20(working)
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


__all__ = ["decode_global_transport_v30"]
