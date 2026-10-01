"""Sérialisation déterministe. Publication production bloquée en Phase 4A."""

from __future__ import annotations

import json
from pathlib import Path

from app.editorial_planning.constants import (
    EDITORIAL_PLAN_FILENAME,
    PUBLICATION_AUTHORIZED,
)
from app.editorial_planning.errors import EditorialPlanPublicationBlocked
from app.editorial_planning.models import EditorialPlan
from app.file_utils import content_hash, write_text_atomic
from app.source_analysis.writer import analysis_dir

_JSON_INDENT = 2


def editorial_plan_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return analysis_dir(project_name, sortie_dir=sortie_dir) / EDITORIAL_PLAN_FILENAME


def render_editorial_plan(payload: dict) -> str:
    """Pas de sort_keys : l'ordre est celui de EditorialPlan.to_dict()."""
    return json.dumps(payload, ensure_ascii=False, indent=_JSON_INDENT) + "\n"


def plan_sha256(plan: EditorialPlan) -> str:
    return content_hash(render_editorial_plan(plan.to_dict()))


def write_editorial_plan(path: Path, payload: dict) -> Path:
    if not PUBLICATION_AUTHORIZED:
        raise EditorialPlanPublicationBlocked(
            f"Refus d'écrire {path} : PUBLICATION_AUTHORIZED=False (Phase 4A)."
        )
    return write_text_atomic(Path(path), render_editorial_plan(payload))


def write_plan_bytes_for_tests(path: Path, payload: dict) -> Path:
    """Écriture autorisée seulement vers un répertoire de test isolé."""
    path = Path(path)
    if path.name == EDITORIAL_PLAN_FILENAME and "analysis" in path.parts:
        parent = path.parent.parent.name if path.parent.name == "analysis" else ""
        if parent and "tmp" not in str(path).lower() and "pytest" not in str(path).lower():
            raise EditorialPlanPublicationBlocked(
                "write_plan_bytes_for_tests refuse une cible d'apparence production."
            )
    return write_text_atomic(path, render_editorial_plan(payload))
