"""Préflight SourceMap réel. Lecture seule. Hash mismatch = BLOCKED."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.editorial_planning.constants import (
    EXPECTED_EXAMPLE_COUNT,
    EXPECTED_IDEA_COUNT,
    EXPECTED_REFERENCE_COUNT,
    EXPECTED_REPETITION_COUNT,
    EXPECTED_SOURCE_MAP_BYTES,
    EXPECTED_SOURCE_MAP_SHA256,
    EXPECTED_TOPIC_COUNT,
    EXPECTED_UNCERTAINTY_COUNT,
    VALIDATION_PROJECT_NAME,
)
from app.editorial_planning.errors import EditorialPlanSourceMapIntegrityError
from app.editorial_planning.models import SourceMapIdentity, scan_forbidden_plan_structure
from app.source_analysis.models import SourceMap, forbidden_editorial_fields
from app.source_analysis.writer import source_map_path
from app.source_analysis.validator import validate_source_map
from app.source_analysis_execution_strategy.windows import load_clean_transcript


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_source_map_file(path: Path) -> tuple[SourceMap, bytes, str]:
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise EditorialPlanSourceMapIntegrityError("source_map.json n'est pas un objet")
    return SourceMap.from_dict(payload), raw, digest


def source_map_identity_from_file(path: Path, source_map: SourceMap, raw: bytes, digest: str) -> SourceMapIdentity:
    return SourceMapIdentity(
        sha256=digest,
        bytes=len(raw),
        schema_version=source_map.schema_version,
        project=source_map.project_name,
        topic_count=len(source_map.topics),
        idea_count=len(source_map.ideas),
        example_count=len(source_map.examples),
        reference_count=len(source_map.references),
        uncertainty_count=len(source_map.uncertainties),
        repetition_count=len(source_map.repetitions),
    )


def run_real_source_map_preflight(
    *,
    project_name: str = VALIDATION_PROJECT_NAME,
    sortie_dir: Path | None = None,
    expected_sha256: str = EXPECTED_SOURCE_MAP_SHA256,
    expected_bytes: int = EXPECTED_SOURCE_MAP_BYTES,
) -> dict[str, Any]:
    path = source_map_path(project_name, sortie_dir=sortie_dir)
    if not path.is_file():
        raise EditorialPlanSourceMapIntegrityError(f"SourceMap absent : {path}")
    source_map, raw, digest = load_source_map_file(path)
    identity = source_map_identity_from_file(path, source_map, raw, digest)
    hash_ok = digest == expected_sha256
    bytes_ok = len(raw) == expected_bytes
    inventory = {
        "topics": len(source_map.topics),
        "ideas": len(source_map.ideas),
        "examples": len(source_map.examples),
        "references": len(source_map.references),
        "uncertainties": len(source_map.uncertainties),
        "repetitions": len(source_map.repetitions),
    }
    expected_inventory = {
        "topics": EXPECTED_TOPIC_COUNT,
        "ideas": EXPECTED_IDEA_COUNT,
        "examples": EXPECTED_EXAMPLE_COUNT,
        "references": EXPECTED_REFERENCE_COUNT,
        "uncertainties": EXPECTED_UNCERTAINTY_COUNT,
        "repetitions": EXPECTED_REPETITION_COUNT,
    }
    inventory_ok = inventory == expected_inventory
    payload = json.loads(raw.decode("utf-8"))
    editorial = forbidden_editorial_fields(payload)
    editorial_scan = scan_forbidden_plan_structure(payload)
    validation_errors: list[str] = []
    validation_status = "SKIPPED"
    try:
        transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
        validation_errors = validate_source_map(source_map, transcript)
        validation_status = "PASS" if not validation_errors else "FAIL"
    except FileNotFoundError:
        validation_status = "SKIPPED"
    relations_present = any(idea.relations for idea in source_map.ideas)
    blocked = not (hash_ok and bytes_ok)
    status = "BLOCKED" if blocked else "PASS"
    if not inventory_ok or editorial or editorial_scan or validation_status == "FAIL":
        status = "BLOCKED" if blocked else "FAIL"
    return {
        "status": status,
        "path": str(path).replace("\\", "/"),
        "sha256": digest,
        "expected_sha256": expected_sha256,
        "hash_match": hash_ok,
        "bytes": len(raw),
        "expected_bytes": expected_bytes,
        "bytes_match": bytes_ok,
        "chars": len(raw.decode("utf-8")),
        "inventory": inventory,
        "expected_inventory": expected_inventory,
        "inventory_match": inventory_ok,
        "source_map_validation": validation_status,
        "source_map_validation_errors": validation_errors[:20],
        "forbidden_editorial_fields": list(editorial),
        "forbidden_editorial_structure": "NO" if not editorial else "YES",
        "traceability": validation_status,
        "relations_present": relations_present,
        "relation_quality_debt": "PRESERVED",
        "identity": identity.to_dict(),
        "source_map_not_modified": True,
    }
