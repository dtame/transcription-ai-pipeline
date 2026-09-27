"""
Comparateur d'équivalence sémantique SourceMap.

Ignore uniquement les métadonnées de transport / prompt / signature.
Ne ignore PAS : topics, ideas, relations, examples, references,
uncertainties, repetitions, voice profile, source refs.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.models import SourceMap


def semantic_source_map_view(source_map: SourceMap) -> dict[str, Any]:
    """Vue déterministe du contenu métier, hors provenance de transport."""
    return {
        "transcript_id": source_map.transcript_id,
        "project_name": source_map.project_name,
        "primary_language": source_map.primary_language,
        "schema_version": source_map.schema_version,
        "source_analysis": source_map.source_analysis.to_dict(),
        "topics": [topic.to_dict() for topic in source_map.topics],
        "ideas": [idea.to_dict() for idea in source_map.ideas],
        "examples": [example.to_dict() for example in source_map.examples],
        "references": [item.to_dict() for item in source_map.references],
        "uncertainties": [item.to_dict() for item in source_map.uncertainties],
        "repetitions": [item.to_dict() for item in source_map.repetitions],
        "author_voice_profile": source_map.author_voice_profile.to_dict(),
        "stats": source_map.stats.to_dict(),
    }


def compare_semantic_source_maps(left: SourceMap, right: SourceMap) -> list[str]:
    """Différences sémantiques, clés stables. Vide = équivalent."""
    return _diff(semantic_source_map_view(left), semantic_source_map_view(right), "")


def source_maps_semantically_equal(left: SourceMap, right: SourceMap) -> bool:
    return compare_semantic_source_maps(left, right) == []


def _diff(left: Any, right: Any, path: str) -> list[str]:
    if type(left) is not type(right):
        return [f"{path or '$'} : types {type(left).__name__} ≠ {type(right).__name__}"]

    if isinstance(left, Mapping):
        errors: list[str] = []
        keys = sorted(set(left) | set(right))
        for key in keys:
            child = f"{path}.{key}" if path else key
            if key not in left:
                errors.append(f"{child} absent à gauche")
            elif key not in right:
                errors.append(f"{child} absent à droite")
            else:
                errors.extend(_diff(left[key], right[key], child))
        return errors

    if isinstance(left, list):
        if len(left) != len(right):
            return [f"{path} : longueurs {len(left)} ≠ {len(right)}"]
        errors = []
        for index, (a, b) in enumerate(zip(left, right)):
            errors.extend(_diff(a, b, f"{path}[{index}]"))
        return errors

    if left != right:
        return [f"{path} : {left!r} ≠ {right!r}"]
    return []
