"""Load validated upstream language metadata and resolve the document language."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.cleanup_application.writer import clean_json_path
from app.editorial_planner_language_policy_4a32.constants import PROJECT_NAME
from app.editorial_planner_language_policy_4a32.guard import PlannerLanguagePolicyError
from app.editorial_planner_language_policy_4a32.paths import repo_root
from app.editorial_planning.errors import DocumentLanguageBlocked
from app.editorial_planning.language_policy import (
    DOCUMENT_LANGUAGE_POLICY,
    DOCUMENT_LANGUAGE_POLICY_VERSION,
    FIELD_SOURCE_MAP_PRIMARY,
    FIELD_TRANSCRIPT_PRIMARY,
    resolve_document_language,
)
from app.source_analysis.models import SourceMap
from app.source_analysis.writer import transcripts_dir


def _read_json_language(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path).replace("\\", "/"), "present": False, "primary": ""}
    payload = json.loads(path.read_text(encoding="utf-8"))
    language = payload.get("language") if isinstance(payload, dict) else {}
    if not isinstance(language, dict):
        language = {}
    return {
        "path": str(path).replace("\\", "/"),
        "present": True,
        "primary": str(language.get("primary") or "").strip(),
        "detected": list(language.get("detected") or []),
        "transcript_id": str(payload.get("transcript_id") or ""),
    }


def load_language_provenance(
    source_map: SourceMap,
    *,
    project_name: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    project = project_name or source_map.project_name or PROJECT_NAME
    base = root or repo_root()
    original = _read_json_language(
        transcripts_dir(project, sortie_dir=base / "sortie") / "transcript_data.json"
    )
    clean = _read_json_language(clean_json_path(project, sortie_dir=base / "sortie"))
    transcript_primary = original.get("primary") or clean.get("primary") or ""
    extras: dict[str, str] = {}
    if original.get("present") and clean.get("present"):
        extras["transcript_data.clean.language.primary"] = str(clean.get("primary") or "")

    resolution = resolve_document_language(
        transcript_primary_language=transcript_primary or None,
        source_map_primary_language=source_map.primary_language,
        extra_validated_languages=extras or None,
    )
    if resolution.blocked:
        raise DocumentLanguageBlocked(
            f"{resolution.status}: " + "; ".join(resolution.notes)
        )
    return {
        "policy": DOCUMENT_LANGUAGE_POLICY,
        "policy_version": DOCUMENT_LANGUAGE_POLICY_VERSION,
        "authoritative_field": FIELD_TRANSCRIPT_PRIMARY,
        "carried_field": FIELD_SOURCE_MAP_PRIMARY,
        "chain": [
            "transcription language.primary",
            "transcript_data.language.primary",
            "Source Analyzer copies to SourceMap.language.primary",
            "Source Analyzer validator requires transcript/source_map match",
            "planner digest.language + canonical_document_language",
            "editorial-planner-1.0.1 request",
        ],
        "transcription": original,
        "transcript_clean": clean,
        "source_map_primary_language": source_map.primary_language,
        "source_map_rewritten": False,
        "resolution": resolution.to_dict(),
        "canonical_document_language": resolution.canonical_document_language,
        "blocked": resolution.blocked,
        "multilingual_primary_used": True,
        "translation_not_applied": True,
    }


def require_document_language(
    source_map: SourceMap,
    *,
    project_name: str | None = None,
    root: Path | None = None,
) -> str:
    provenance = load_language_provenance(
        source_map, project_name=project_name, root=root
    )
    language = str(provenance.get("canonical_document_language") or "")
    if not language:
        raise PlannerLanguagePolicyError("Canonical document language unresolved")
    return language


__all__ = ["load_language_provenance", "require_document_language"]
