"""Canonical, benchmark, prompt, schema, and historical identities."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b23.identity import (
    canonical_json_sha256,
    file_identity,
    load_json,
    snapshot_identities,
    verify_canonical_inputs,
)
from app.book_semantic_gate_4b23.prompt import prompt_identity
from app.book_semantic_gate_4b23.schema import schema_identity
from app.book_semantic_gate_4b23.transport import transport_identity
from app.book_semantic_gate_4b24.constants import (
    EXPECTED_BENCHMARK_ARTIFACT_CASES,
    EXPECTED_BENCHMARK_DATASET_SHA256,
    EXPECTED_BENCHMARK_FILE_BYTES,
    EXPECTED_BENCHMARK_FILE_SHA256,
    EXPECTED_NEGATIVE_CASES,
    EXPECTED_POSITIVE_CASES,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
    EXPECTED_SCHEMA_BYTES,
    EXPECTED_SCHEMA_SHA256,
    EXPECTED_SCORED_CASES,
    EXCLUDED_FROM_SCORE,
    NEGATIVE_CASE_IDS,
    P9B_STATUS,
    PHASE,
    POSITIVE_CASE_IDS,
    PROMPT_VERSION,
    TRANSPORT_VERSION,
)
from app.book_semantic_gate_4b24.paths import frozen_benchmark_path


def load_frozen_benchmark(*, root: Path | None = None) -> dict[str, Any]:
    path = frozen_benchmark_path(root=root)
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError("frozen 4B.2.3 benchmark is not an object")
    return payload


def scored_cases(benchmark: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in benchmark.get("cases") or []:
        if not isinstance(item, Mapping):
            continue
        case_id = str(item.get("case_id") or "")
        if case_id in EXCLUDED_FROM_SCORE:
            continue
        if str(item.get("role") or "") == "positive_or_non_substantive":
            continue
        rows.append(dict(item))
    return rows


def benchmark_identity(*, root: Path | None = None) -> dict[str, Any]:
    path = frozen_benchmark_path(root=root)
    file_meta = file_identity(path)
    payload = load_frozen_benchmark(root=root) if file_meta["exists"] else {}
    cases = list(payload.get("cases") or [])
    scored = scored_cases(payload)
    positives = [item["case_id"] for item in scored if item.get("role") == "positive"]
    negatives = [item["case_id"] for item in scored if item.get("role") == "negative"]
    match = (
        file_meta["exists"]
        and file_meta["sha256"] == EXPECTED_BENCHMARK_FILE_SHA256
        and file_meta["bytes"] == EXPECTED_BENCHMARK_FILE_BYTES
        and str(payload.get("dataset_sha256") or "") == EXPECTED_BENCHMARK_DATASET_SHA256
        and len(cases) == EXPECTED_BENCHMARK_ARTIFACT_CASES
        and len(scored) == EXPECTED_SCORED_CASES
        and positives == list(POSITIVE_CASE_IDS)
        and negatives == list(NEGATIVE_CASE_IDS)
        and payload.get("terra_called") is False
        and payload.get("original_candidates_modified") is False
        and payload.get("human_labels_are_ground_truth") is True
    )
    p9b = dict(payload.get("structural_empty_p9b") or {})
    return {
        "phase": PHASE,
        "path": file_meta["path"],
        "exists": file_meta["exists"],
        "sha256": file_meta["sha256"],
        "bytes": file_meta["bytes"],
        "dataset_sha256": payload.get("dataset_sha256"),
        "artifact_case_count": len(cases),
        "scored_case_count": len(scored),
        "positive_count": len(positives),
        "negative_count": len(negatives),
        "positive_case_ids": positives,
        "negative_case_ids": negatives,
        "excluded_case_ids": list(EXCLUDED_FROM_SCORE),
        "p9b": {
            "status": P9B_STATUS,
            "semantic_benchmark_case": False,
            "raw_present": p9b.get("raw_present"),
            "reason": p9b.get("reason"),
        },
        "human_labels_are_ground_truth": payload.get("human_labels_are_ground_truth"),
        "original_candidates_modified": payload.get("original_candidates_modified"),
        "terra_called_in_artifact": payload.get("terra_called"),
        "expected": {
            "sha256": EXPECTED_BENCHMARK_FILE_SHA256,
            "bytes": EXPECTED_BENCHMARK_FILE_BYTES,
            "dataset_sha256": EXPECTED_BENCHMARK_DATASET_SHA256,
            "artifact_cases": EXPECTED_BENCHMARK_ARTIFACT_CASES,
            "scored_cases": EXPECTED_SCORED_CASES,
            "positives": EXPECTED_POSITIVE_CASES,
            "negatives": EXPECTED_NEGATIVE_CASES,
        },
        "identity_match": match,
    }


def contract_identities() -> dict[str, Any]:
    prompt = prompt_identity()
    schema = schema_identity()
    transport = transport_identity()
    prompt_match = (
        prompt.get("version") == PROMPT_VERSION
        and prompt.get("prompt_sha256") == EXPECTED_PROMPT_SHA256
        and prompt.get("system_sha256") == EXPECTED_PROMPT_SYSTEM_SHA256
        and prompt.get("instructions_sha256") == EXPECTED_PROMPT_INSTRUCTIONS_SHA256
    )
    schema_match = (
        schema.get("raw_schema_sha256") == EXPECTED_SCHEMA_SHA256
        and int(schema.get("raw_schema_bytes") or 0) == EXPECTED_SCHEMA_BYTES
        and schema.get("transport_version") == TRANSPORT_VERSION
        and schema.get("engine_mode") == "json_object"
        and schema.get("native_json_schema_response_format") is False
    )
    transport_match = transport.get("version") == TRANSPORT_VERSION
    return {
        "prompt": prompt,
        "schema": schema,
        "transport": transport,
        "prompt_match": prompt_match,
        "schema_match": schema_match,
        "transport_match": transport_match,
        "contract_match": prompt_match and schema_match and transport_match,
    }


def post_input_hashes(*, root: Path | None = None) -> dict[str, Any]:
    return verify_canonical_inputs(root=root)


__all__ = [
    "benchmark_identity",
    "canonical_json_sha256",
    "contract_identities",
    "file_identity",
    "load_frozen_benchmark",
    "load_json",
    "post_input_hashes",
    "scored_cases",
    "snapshot_identities",
    "verify_canonical_inputs",
]
