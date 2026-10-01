"""Normalisation déterministe V3/V3.1 → entrée consolidation. Sans réécriture sémantique."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.file_utils import content_hash
from app.source_analysis.models import IMPORTANCE_LEVELS
from app.source_analysis_local_v3.compatibility import normalize_v3_transport_to_local_lite
from app.source_analysis_local_v3.constants import (
    SEMANTIC_TRANSPORT_VERSION_V3,
    SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
)
from app.source_analysis_local_v3.decoder import (
    decode_v3_transport,
    decode_v31_local_lite_transport,
)
from app.source_analysis_local_v3.source_refs import is_canonical_src
from app.source_analysis_v31_global_preflight.constants import (
    FROZEN_GRANULARITY,
    FROZEN_PROMPT,
    FROZEN_SRC_POLICY,
    FROZEN_TRANSPORT,
    HISTORICAL_V3_TRANSPORT,
    MIXED_PROVENANCE,
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    SRC_POLICY_OLD,
    WIN001_PROMPT,
    WIN007_CANONICAL_SRC,
    WIN007_RAW_SRC,
    WINDOW_SPECS,
)
from app.source_analysis_v31_global_preflight.loaders import (
    load_all_ready_candidates,
    window_short,
)

_KIND_PREFIX = {
    "TOPIC": "T",
    "IDEA": "I",
    "EXAMPLE": "E",
    "REFERENCE": "F",
    "UNCERTAINTY": "U",
    "RELATION": "L",
}


def src_number(token: str) -> int | None:
    if not is_canonical_src(token):
        return None
    return int(token[3:])


def make_input_id(window_id: str, record_index: int, kind: str, handle: str) -> str:
    short = window_short(window_id)
    owner = str(handle or "").strip()
    if owner:
        return f"{short}:{owner}"
    prefix = _KIND_PREFIX.get(kind, kind[:1] or "X")
    return f"{short}:{prefix}{record_index:03d}"


def _importance_and_kind(kind: str, metadata: list[str], *, v3: bool) -> tuple[str, str]:
    if kind != "IDEA":
        return "", ""
    if v3 and len(metadata) == 2:
        return metadata[1], ""
    if len(metadata) == 1 and metadata[0] in IMPORTANCE_LEVELS:
        return metadata[0], ""
    return (metadata[0] if metadata else ""), ""


def _win007_src_provenance(refs: list[str]) -> dict[str, str] | None:
    if WIN007_CANONICAL_SRC not in refs:
        return None
    return {
        "raw_provider_src": WIN007_RAW_SRC,
        "canonical_src": WIN007_CANONICAL_SRC,
        "policy": FROZEN_SRC_POLICY,
        "consumed_by_consolidator": WIN007_CANONICAL_SRC,
    }


def normalize_window_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    window_id = str(candidate["window_id"])
    payload = candidate["payload"]
    metadata = candidate.get("metadata") or {}
    v3 = window_id == "WIN001"
    dropped_subtypes: list[dict[str, str]] = []
    source_transport = HISTORICAL_V3_TRANSPORT if v3 else FROZEN_TRANSPORT
    working = payload
    if v3:
        decode_v3_transport(payload)
        working, provenance = normalize_v3_transport_to_local_lite(
            payload, source_transport_version=SEMANTIC_TRANSPORT_VERSION_V3
        )
        dropped_subtypes = list(provenance.get("dropped_subtypes") or [])
        decoded = decode_v31_local_lite_transport(working)
    else:
        decoded = decode_v31_local_lite_transport(payload)

    handle_to_id: dict[str, str] = {}
    records_out: list[dict[str, Any]] = []
    raw_records = list(decoded.get("records") or [])
    for index, record in enumerate(raw_records):
        kind = str(record.get("k") or "")
        handle = str(record.get("h") or "")
        input_id = make_input_id(window_id, index, kind, handle)
        if handle:
            handle_to_id[handle] = input_id
        refs = [str(item) for item in (record.get("s") or []) if isinstance(item, str)]
        importance, idea_kind = _importance_and_kind(
            kind, list(record.get("m") or []), v3=v3
        )
        item = {
            "input_id": input_id,
            "window_id": window_id,
            "record_index": index,
            "kind": kind,
            "local_handle": handle,
            "value": str(record.get("v") or ""),
            "source_refs": refs,
            "link_handles": [str(item) for item in (record.get("l") or [])],
            "link_input_ids": [],
            "importance": importance,
            "idea_kind": idea_kind,
            "metadata": list(record.get("m") or []),
        }
        if window_id == "WIN007":
            extra = _win007_src_provenance(refs)
            if extra:
                item["src_provenance"] = extra
        records_out.append(item)

    for item in records_out:
        item["link_input_ids"] = [
            handle_to_id[handle]
            for handle in item["link_handles"]
            if handle in handle_to_id
        ]

    src_policy = FROZEN_SRC_POLICY if window_id == "WIN007" else SRC_POLICY_OLD
    if window_id == "WIN001":
        src_policy = SRC_POLICY_OLD
    prompt = WIN001_PROMPT if v3 else FROZEN_PROMPT
    granularity = str(metadata.get("granularity") or FROZEN_GRANULARITY)
    if v3:
        granularity = "historical-v3"

    serialized = json.dumps(
        {"window_id": window_id, "records": records_out},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "window_id": window_id,
        "mixed_provenance": MIXED_PROVENANCE[window_id],
        "source_transport_version": source_transport,
        "normalized_transport_version": SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
        "prompt_version": prompt,
        "granularity_policy": granularity,
        "src_policy": src_policy,
        "candidate_path": candidate.get("path"),
        "request_id": candidate.get("request_id"),
        "analysis_signature": WINDOW_SPECS[window_id]["analysis_signature"],
        "owned_src_range": list(candidate.get("owned_src_range") or []),
        "first_owned_src": candidate.get("first_owned_src"),
        "last_owned_src": candidate.get("last_owned_src"),
        "theme": decoded.get("theme"),
        "intent": decoded.get("intent"),
        "intent_confidence": decoded.get("ic"),
        "audience": decoded.get("aud"),
        "audience_confidence": decoded.get("ac"),
        "records": records_out,
        "dropped_local_idea_subtypes": dropped_subtypes,
        "invented_semantics": False,
        "text_rewritten": False,
        "ideas_merged": False,
        "ideas_split": False,
        "serialized_chars": len(serialized),
        "serialized_bytes": len(serialized.encode("utf-8")),
        "sha256": content_hash(serialized),
        "metadata": {
            key: metadata.get(key)
            for key in (
                "phase",
                "prompt",
                "transport",
                "granularity",
                "thinking_mode",
                "src_reference_policy_version",
                "derived_representation",
                "provenance",
            )
            if key in metadata
        },
    }


def build_normalized_input(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Any = None,
    loaded: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = loaded or load_all_ready_candidates(project_name, sortie_dir=sortie_dir)
    windows: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    for window_id, candidate in (bundle.get("windows") or {}).items():
        if not candidate.get("present"):
            continue
        normalized = normalize_window_candidate(candidate)
        windows[window_id] = normalized
        records.extend(normalized["records"])
    compact = {
        "windows": [
            {
                "id": row["window_id"],
                "theme": row["theme"],
                "intent": row["intent"],
                "ic": row["intent_confidence"],
                "aud": row["audience"],
                "ac": row["audience_confidence"],
                "owned": row["owned_src_range"],
                "records": [
                    {
                        "id": item["input_id"],
                        "k": item["kind"],
                        "v": item["value"],
                        "s": item["source_refs"],
                        "m": [item["importance"]] if item["kind"] == "IDEA" and item["importance"] else item["metadata"],
                        "l": item["link_input_ids"],
                        **(
                            {"p": item["src_provenance"]}
                            if item.get("src_provenance")
                            else {}
                        ),
                    }
                    for item in row["records"]
                ],
            }
            for row in windows.values()
        ]
    }
    compact_text = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    idea_ids = [item["input_id"] for item in records if item["kind"] == "IDEA"]
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "contract": "normalized-consolidation-input-1.0",
        "is_source_map": False,
        "semantic_rewriting": False,
        "deterministic": True,
        "windows": windows,
        "all_records": records,
        "idea_input_ids": idea_ids,
        "compact": compact,
        "compact_chars": len(compact_text),
        "compact_bytes": len(compact_text.encode("utf-8")),
        "compact_sha256": content_hash(compact_text),
        "ready": bundle.get("ready_label"),
        "missing": list(bundle.get("missing") or []),
        "win007_request_id": bundle.get("win007_request_id"),
        "win003_provenance": bundle.get("win003_provenance"),
    }


__all__ = [
    "build_normalized_input",
    "make_input_id",
    "normalize_window_candidate",
    "src_number",
]
