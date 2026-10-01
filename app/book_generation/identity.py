"""Production input identity. SHA mismatch → BLOCKED."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.book_generation.constants import (
    EXPECTED_EDITORIAL_PLAN_SHA256,
    EXPECTED_SOURCE_MAP_SHA256,
    VALIDATION_BLOCKED,
    VALIDATION_PASS,
    VALIDATION_PROJECT_NAME,
)
from app.book_generation.errors import BookGenerationBlocked
from app.editorial_planning.models import EditorialPlan
from app.editorial_planning.pipeline import (
    load_published_editorial_plan,
    load_published_source_map,
)
from app.source_analysis.models import SourceMap


@dataclass(frozen=True)
class ProductionInputs:
    project_name: str
    plan: EditorialPlan
    plan_bytes: bytes
    plan_sha256: str
    plan_path: Path
    source_map: SourceMap
    source_map_bytes: bytes
    source_map_sha256: str
    source_map_path: Path
    status: str
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "editorial_plan_path": str(self.plan_path).replace("\\", "/"),
            "editorial_plan_sha256": self.plan_sha256,
            "editorial_plan_bytes": len(self.plan_bytes),
            "source_map_path": str(self.source_map_path).replace("\\", "/"),
            "source_map_sha256": self.source_map_sha256,
            "source_map_bytes": len(self.source_map_bytes),
            "status": self.status,
            "notes": list(self.notes),
            "reader": "load_published_editorial_plan",
            "source_map_reader": "load_published_source_map",
            "a35_candidate_read": False,
        }


def load_production_inputs(
    project_name: str = VALIDATION_PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    require_expected_identity: bool = True,
) -> ProductionInputs:
    plan, plan_raw, plan_digest, plan_path = load_published_editorial_plan(
        project_name, sortie_dir=sortie_dir
    )
    source_map, map_raw, map_digest, map_path = load_published_source_map(
        project_name, sortie_dir=sortie_dir
    )
    notes: list[str] = []
    status = VALIDATION_PASS
    if require_expected_identity:
        if plan_digest.lower() != EXPECTED_EDITORIAL_PLAN_SHA256.lower():
            status = VALIDATION_BLOCKED
            notes.append(
                f"EditorialPlan SHA-256 mismatch: {plan_digest} ≠ "
                f"{EXPECTED_EDITORIAL_PLAN_SHA256}"
            )
        if map_digest.lower() != EXPECTED_SOURCE_MAP_SHA256.lower():
            status = VALIDATION_BLOCKED
            notes.append(
                f"SourceMap SHA-256 mismatch: {map_digest} ≠ "
                f"{EXPECTED_SOURCE_MAP_SHA256}"
            )
    inputs = ProductionInputs(
        project_name=project_name,
        plan=plan,
        plan_bytes=plan_raw,
        plan_sha256=plan_digest,
        plan_path=plan_path,
        source_map=source_map,
        source_map_bytes=map_raw,
        source_map_sha256=map_digest,
        source_map_path=map_path,
        status=status,
        notes=tuple(notes),
    )
    if status == VALIDATION_BLOCKED:
        raise BookGenerationBlocked("; ".join(notes))
    return inputs
