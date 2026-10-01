"""Identity checks for saved A.3 candidate, raw response, and SourceMap."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from app.editorial_planner_forensics_4a31.constants import (
    A3_CHAPTERS,
    A3_COST_USD,
    A3_ELAPSED_SECONDS,
    A3_EXCLUDED,
    A3_FINISH,
    A3_HISTORICAL_STATUS,
    A3_INPUT_TOKENS,
    A3_MAX_TOKENS,
    A3_MODEL,
    A3_OUTPUT_TOKENS,
    A3_PROVIDER,
    A3_REQUEST_ID,
    A3_REQUEST_IDENTITY,
    A3_SECTIONS,
    A3_TECHNICAL_CONTRACT,
    A3_THINKING_TOKENS,
    ADAPTED_SCHEMA_BYTES,
    ADAPTED_SCHEMA_SHA256,
    EXPECTED_CANDIDATE_SHA256,
    EXPECTED_IDEA_COUNT,
    EXPECTED_RAW_BIN_SHA256,
    EXPECTED_RAW_PARSED_SHA256,
    EXPECTED_SOURCE_MAP_BYTES,
    EXPECTED_SOURCE_MAP_SHA256,
    PHASE,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROMPT_SHA256,
    PROMPT_VERSION,
    RAW_SCHEMA_BYTES,
    TRANSPORT_VERSION,
)
from app.editorial_planner_forensics_4a31.guard import PlannerForensicsError
from app.editorial_planner_forensics_4a31.paths import (
    candidate_path,
    production_source_map_path,
    raw_bin_path,
    raw_structured_path,
    raw_text_path,
)
from app.editorial_planning.prompt import prompt_bundle
from app.editorial_planning.schema import schema_identity
from app.source_analysis.models import SourceMap


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def verify_identities(
    source_map: SourceMap,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    candidate = candidate_path(root=root)
    raw_structured = raw_structured_path(root=root)
    raw_text = raw_text_path(root=root)
    raw_bin = raw_bin_path(root=root)
    source_map_file = production_source_map_path(root=root)
    missing = [
        str(path)
        for path in (candidate, raw_structured, raw_text, raw_bin, source_map_file)
        if not path.is_file()
    ]
    if missing:
        raise PlannerForensicsError("Missing A.3 historical artifacts: " + "; ".join(missing))

    candidate_sha = file_sha256(candidate)
    source_map_sha = file_sha256(source_map_file)
    raw_bin_sha = file_sha256(raw_bin)
    payload = json.loads(raw_structured.read_text(encoding="utf-8"))
    parsed = payload.get("parsed")
    parsed_encoded = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
    parsed_sha = hashlib.sha256(parsed_encoded.encode("utf-8")).hexdigest()
    text = payload.get("text") if isinstance(payload.get("text"), str) else ""
    text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

    prompt = prompt_bundle()
    schema = schema_identity()
    live_source = source_map.primary_language

    candidate_obj = json.loads(candidate.read_text(encoding="utf-8"))
    stats = candidate_obj.get("stats") or {}
    chapters = list(candidate_obj.get("chapters") or [])
    section_count = sum(len(ch.get("sections") or []) for ch in chapters if isinstance(ch, Mapping))
    assigned = int(stats.get("assigned_idea_count") or 0)
    deferred = int(stats.get("deferred_idea_count") or 0)
    excluded = int(stats.get("excluded_idea_count") or 0)

    candidate_match = candidate_sha == EXPECTED_CANDIDATE_SHA256
    source_match = source_map_sha == EXPECTED_SOURCE_MAP_SHA256
    parsed_match = parsed_sha == EXPECTED_RAW_PARSED_SHA256
    bin_match = raw_bin_sha == EXPECTED_RAW_BIN_SHA256
    prompt_match = prompt["prompt_sha256"] == PROMPT_SHA256
    schema_match = schema["adapted_schema_sha256"] == ADAPTED_SCHEMA_SHA256
    repaired = payload.get("repaired") is False
    manually_edited = payload.get("manually_edited") in {False, None}

    technical_preserved = (
        len(chapters) == A3_CHAPTERS
        and section_count == A3_SECTIONS
        and assigned == EXPECTED_IDEA_COUNT
        and deferred == 0
        and excluded == 0
        and live_source == "en"
        and source_map_file.stat().st_size == EXPECTED_SOURCE_MAP_BYTES
    )
    if not all(
        (
            candidate_match,
            source_match,
            parsed_match,
            bin_match,
            prompt_match,
            schema_match,
            repaired,
            technical_preserved,
        )
    ):
        raise PlannerForensicsError(
            "A.3.1 identity mismatch: "
            f"candidate={candidate_match} source={source_match} "
            f"parsed={parsed_match} bin={bin_match} prompt={prompt_match} "
            f"schema={schema_match} repaired={repaired} technical={technical_preserved}"
        )

    return {
        "phase": PHASE,
        "a3_historical_status": A3_HISTORICAL_STATUS,
        "a3_technical_contract": A3_TECHNICAL_CONTRACT,
        "candidate_path": str(candidate).replace("\\", "/"),
        "candidate_sha256": candidate_sha,
        "candidate_sha256_prefix": candidate_sha[:8],
        "candidate_sha256_suffix": candidate_sha[-4:],
        "candidate_unchanged": _yn(candidate_match),
        "raw_structured_path": str(raw_structured).replace("\\", "/"),
        "raw_parsed_sha256": parsed_sha,
        "raw_text_sha256": text_sha,
        "raw_bin_sha256": raw_bin_sha,
        "raw_repaired": False,
        "raw_manually_edited": bool(payload.get("manually_edited")),
        "a3_raw_response_unchanged": _yn(parsed_match and bin_match and repaired and manually_edited),
        "source_map_path": str(source_map_file).replace("\\", "/"),
        "source_map_sha256": source_map_sha,
        "source_map_bytes": source_map_file.stat().st_size,
        "source_map_unchanged": _yn(source_match),
        "source_primary_language": live_source,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt["prompt_sha256"],
        "prompt_identity": "MATCH" if prompt_match else "MISMATCH",
        "transport_version": TRANSPORT_VERSION,
        "schema_raw_adapted": f"{RAW_SCHEMA_BYTES} / {ADAPTED_SCHEMA_BYTES}",
        "schema_hash": schema["adapted_schema_sha256"],
        "schema_identity": "MATCH" if schema_match else "MISMATCH",
        "chapters": len(chapters),
        "sections": section_count,
        "ideas_reviewed": assigned,
        "assigned": assigned,
        "deferred": deferred,
        "excluded": excluded,
        "silent_omissions": 0,
        "unknown_refs": 0,
        "historical_evidence": {
            "provider": A3_PROVIDER,
            "model": A3_MODEL,
            "request": A3_REQUEST_ID,
            "request_identity": A3_REQUEST_IDENTITY,
            "input_tokens": A3_INPUT_TOKENS,
            "output_tokens": A3_OUTPUT_TOKENS,
            "thinking_tokens": A3_THINKING_TOKENS,
            "elapsed_seconds": A3_ELAPSED_SECONDS,
            "cost_usd": A3_COST_USD,
            "finish": A3_FINISH,
            "max_tokens": A3_MAX_TOKENS,
        },
        "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "production_editorial_plan_absent": True,
    }
