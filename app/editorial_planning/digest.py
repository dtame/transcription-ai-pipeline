"""
Digest compact du SourceMap pour le planner.

Le SourceMap canonique reste l'autorité. Le digest omet les tableaux SRC
et les relations non autoritatives pour ne pas gonfler le transport d'entrée.
Aucun contenu sémantique n'est inventé.
"""

from __future__ import annotations

import json
from typing import Any

from app.source_analysis.models import SourceMap


def build_planner_digest(source_map: SourceMap) -> dict[str, Any]:
    header = source_map.source_analysis
    return {
        "schema_version": source_map.schema_version,
        "project": source_map.project_name,
        "language": source_map.primary_language,
        "source_analysis": {
            "main_theme": header.main_theme,
            "author_intent": header.author_intent.to_dict(),
            "target_audience": header.target_audience.to_dict(),
        },
        "topics": [
            {
                "id": topic.topic_id,
                "label": topic.label,
                "summary": topic.summary,
            }
            for topic in source_map.topics
        ],
        "ideas": [
            {
                "id": idea.idea_id,
                "summary": idea.summary,
                "kind": idea.kind,
                "importance": idea.importance,
                "topic_refs": list(idea.topic_refs),
            }
            for idea in source_map.ideas
        ],
        "examples": [
            {
                "id": example.example_id,
                "kind": example.kind,
                "summary": example.summary,
                "supports_idea_refs": list(example.supports_idea_refs),
            }
            for example in source_map.examples
        ],
        "references": [
            {
                "id": item.reference_id,
                "kind": item.kind,
                "raw": item.raw_reference,
                "completeness": item.completeness,
            }
            for item in source_map.references
        ],
        "uncertainties": [
            {
                "id": item.uncertainty_id,
                "kind": item.kind,
                "summary": item.description,
                "severity": item.severity,
            }
            for item in source_map.uncertainties
        ],
        "repetitions": [
            {
                "id": item.repetition_id,
                "character": item.character,
                "summary": item.description,
                "idea_refs": list(item.idea_refs),
            }
            for item in source_map.repetitions
        ],
        "counts": {
            "topics": len(source_map.topics),
            "ideas": len(source_map.ideas),
            "examples": len(source_map.examples),
            "references": len(source_map.references),
            "uncertainties": len(source_map.uncertainties),
            "repetitions": len(source_map.repetitions),
        },
    }


def render_digest(source_map: SourceMap) -> str:
    return json.dumps(
        build_planner_digest(source_map),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def build_planner_digest_v101(
    source_map: SourceMap,
    *,
    canonical_document_language: str,
) -> dict[str, Any]:
    """
    Digest 1.0 plus the explicit canonical language field.

    SourceMap remains read-only. The extra field is planner request context.
    """
    from app.editorial_planning.language_policy import normalize_language_code

    digest = build_planner_digest(source_map)
    digest["canonical_document_language"] = normalize_language_code(
        canonical_document_language
    )
    return digest


def render_digest_v101(
    source_map: SourceMap,
    *,
    canonical_document_language: str,
) -> str:
    return json.dumps(
        build_planner_digest_v101(
            source_map,
            canonical_document_language=canonical_document_language,
        ),
        ensure_ascii=False,
        separators=(",", ":"),
    )
