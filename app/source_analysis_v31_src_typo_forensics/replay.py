"""Replay offline exact WIN007 sous contrat A.31. Ne répare pas. Ne promeut pas."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from app.source_analysis_v31_real_win004.validate import interpret_local_lite_response
from app.source_analysis_v31_remaining_windows.window import load_candidate_plan
from app.source_analysis_v31_src_typo_forensics.classify import forensic_token_class
from app.source_analysis_v31_src_typo_forensics.constants import (
    A31_VALIDATOR_ERROR,
    EXPECTED_CANONICAL,
    MALFORMED_TOKEN,
    MODE,
    PHASE,
    PROJECT_NAME,
    RECORD_INDEX,
    RECORD_S_POSITION,
    SCHEMA_VERSION,
    WIN007_COST_USD,
    WIN007_ELAPSED_MS,
    WIN007_FINISH,
    WIN007_FORENSIC,
    WIN007_HTTP,
    WIN007_INPUT_TOKENS,
    WIN007_OUTPUT_TOKENS,
    WIN007_RAW_SHA256,
    WIN007_RAW_SIZE,
    WIN007_REQUEST_ID,
    WIN007_SIGNATURE,
    WIN007_THINKING,
    WINDOW_ID,
)
from app.source_analysis_v31_src_typo_forensics.evidence import (
    extract_text_from_raw,
    read_json,
    read_win007_raw_bytes,
    win007_envelope_path,
)


def extract_win007_structured_text(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> tuple[str, dict[str, Any], bytes]:
    raw = read_win007_raw_bytes(project_name, sortie_dir=sortie_dir)
    text, data = extract_text_from_raw(raw)
    return text, data, raw


def _payload_from_text(text: str) -> dict[str, Any] | None:
    import json

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def inventory_payload_src(
    payload: dict[str, Any] | None,
    *,
    allowed: set[str],
    owned: set[str],
) -> dict[str, Any]:
    records = []
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        records = [item for item in payload["records"] if isinstance(item, dict)]
    occurrences: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for index, item in enumerate(records):
        refs = item.get("s")
        if not isinstance(refs, list):
            continue
        seen: set[str] = set()
        for pos, token in enumerate(refs):
            klass = forensic_token_class(
                token, allowed=allowed, owned=owned, seen_in_record=seen
            )
            if isinstance(token, str):
                seen.add(token)
            row = {
                "record_index": index,
                "kind": str(item.get("k") or ""),
                "handle": item.get("h"),
                "position": pos,
                "token": token if isinstance(token, str) else None,
                "forensic_class": klass,
                "normalized": False,
            }
            occurrences.append(row)
            counts[klass] = counts.get(klass, 0) + 1
    malformed = [
        row for row in occurrences if row["forensic_class"] != "VALID_EXACT"
    ]
    return {
        "total_src_occurrences": len(occurrences),
        "exact_valid_occurrences": counts.get("VALID_EXACT", 0),
        "malformed_occurrences": len(malformed),
        "class_counts": counts,
        "occurrences": occurrences,
        "malformed_rows": malformed,
        "unknown": counts.get("UNKNOWN_CANONICAL_ID", 0),
        "out_of_window": counts.get("OUT_OF_WINDOW", 0),
        "wrong_case": counts.get("WRONG_CASE", 0),
        "wrong_prefix": counts.get("WRONG_PREFIX", 0),
        "inserted_character": counts.get("INSERTED_CHARACTER", 0),
        "other": counts.get("OTHER", 0),
        "srec007337_is_only_root": (
            len(malformed) == 1
            and malformed[0].get("token") == MALFORMED_TOKEN
        ),
    }


def replay_win007_offline(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    text, raw_json, raw = extract_win007_structured_text(
        project_name, sortie_dir=sortie_dir
    )
    envelope = read_json(win007_envelope_path(project_name, sortie_dir=sortie_dir))
    bundle = load_candidate_plan(project_name, sortie_dir=sortie_dir)
    window = bundle["windows"][WINDOW_ID]
    transcript = bundle["transcript"]
    validation = interpret_local_lite_response(None, window=window, raw_text=text)
    payload = validation.get("transport")
    if not isinstance(payload, dict):
        payload = _payload_from_text(text)
    allowed = set(window.owned_src_refs) | set(window.context_src_refs)
    owned = set(window.owned_src_refs)
    inventory = inventory_payload_src(payload, allowed=allowed, owned=owned)
    records = list((payload or {}).get("records") or [])
    record = records[RECORD_INDEX] if len(records) > RECORD_INDEX else {}
    refs = list(record.get("s") or [])
    observed = refs[RECORD_S_POSITION] if len(refs) > RECORD_S_POSITION else None
    errors = list(validation.get("errors") or [])
    reproduced = (
        observed == MALFORMED_TOKEN
        and any(A31_VALIDATOR_ERROR in err or MALFORMED_TOKEN in err for err in errors)
    )
    headers = envelope.get("headers_subset") or envelope.get("headers") or {}
    request_id = (
        envelope.get("request_id")
        or headers.get("request-id")
        or WIN007_REQUEST_ID
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "window_id": WINDOW_ID,
        "request_id": request_id,
        "expected_request_id": WIN007_REQUEST_ID,
        "request_id_match": request_id == WIN007_REQUEST_ID,
        "prompt": "window-analysis-1.4.0",
        "transport": "semantic-transport-v3.1-local-lite",
        "granularity": "window-granularity-1.2-kind-specific",
        "thinking": WIN007_THINKING,
        "finish": envelope.get("finish_reason") or WIN007_FINISH,
        "http": envelope.get("http_status") or WIN007_HTTP,
        "raw_sha256": WIN007_RAW_SHA256,
        "raw_size": WIN007_RAW_SIZE,
        "input_tokens": WIN007_INPUT_TOKENS,
        "output_tokens": WIN007_OUTPUT_TOKENS,
        "elapsed_ms": WIN007_ELAPSED_MS,
        "cost_usd": WIN007_COST_USD,
        "analysis_signature": WIN007_SIGNATURE,
        "forensic_identity": WIN007_FORENSIC,
        "structured_parse": validation.get("structured_parse"),
        "v31_decoder": validation.get("v31_decoder"),
        "handle_registry": validation.get("handle_registry"),
        "handle_resolution": validation.get("handle_resolution"),
        "v31_validator": validation.get("v31_validator"),
        "validation_errors": errors,
        "reproduced": reproduced,
        "observed_token": observed,
        "expected_canonical": EXPECTED_CANONICAL,
        "record_index": RECORD_INDEX,
        "record_kind": str(record.get("k") or ""),
        "record_handle": record.get("h"),
        "record_value": str(record.get("v") or ""),
        "record_refs": refs,
        "src_inventory": inventory,
        "src_audit": validation.get("src_audit"),
        "src_forensic": validation.get("src_forensic"),
        "handles": validation.get("handles"),
        "handle_gate": validation.get("handle_gate"),
        "normalized": False,
        "repaired": False,
        "response_repaired": False,
        "raw_mutated": False,
        "window": window,
        "transcript": transcript,
        "payload": payload,
        "validation": validation,
        "raw_text": text,
        "raw_json": raw_json,
        "raw_bytes": raw,
    }


def derived_single_correction(payload: dict[str, Any]) -> dict[str, Any]:
    derived = copy.deepcopy(payload)
    records = derived.get("records")
    if not isinstance(records, list) or len(records) <= RECORD_INDEX:
        raise ValueError("derived payload missing records[13]")
    record = records[RECORD_INDEX]
    refs = record.get("s")
    if not isinstance(refs, list) or len(refs) <= RECORD_S_POSITION:
        raise ValueError("derived payload missing records[13].s[1]")
    if refs[RECORD_S_POSITION] != MALFORMED_TOKEN:
        raise ValueError(
            f"derived source token drift: {refs[RECORD_S_POSITION]!r}"
        )
    refs[RECORD_S_POSITION] = EXPECTED_CANONICAL
    return derived


__all__ = [
    "derived_single_correction",
    "extract_win007_structured_text",
    "inventory_payload_src",
    "replay_win007_offline",
]
