"""
Reconstruction déterministe : DTO compact → payload brut du normalizer.

Aucune sémantique ajoutée. Le reconstructor :

    attribue des IDs locaux positionnels
    réécrit les index en références internes
    rattache les relations aplaties aux ideas
    préserve les vrais SRC
    refuse les index hors plage et les champs inconnus

puis délègue ORDRE / IDs canoniques / stats à normalizer.normalize_source_map.

    CompactProviderResponse
        → reconstruct_to_canonical_raw()
        → normalize_source_map()
        → SourceMap
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.source_analysis.compact_schema import COMPACT_REQUIRED_FIELDS
from app.source_analysis.errors import (
    SourceMapEditorialLeakError,
    SourceMapValidationError,
)
from app.source_analysis.models import (
    AnalysisProvenance,
    SourceMap,
    forbidden_editorial_fields,
)
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.transcript_input import TranscriptInput

_KNOWN_TOP_LEVEL = frozenset(COMPACT_REQUIRED_FIELDS)
_KNOWN_HEADER = frozenset({"main_theme", "author_intent", "target_audience"})
_KNOWN_VOICE = frozenset(
    {
        "tone",
        "register",
        "sentence_style",
        "rhetorical_patterns",
        "use_of_questions",
        "use_of_repetition",
        "use_of_examples",
        "direct_address",
        "teaching_style",
        "distinctive_traits",
    }
)


def reconstruct_source_map(
    payload: Mapping[str, Any],
    transcript: TranscriptInput,
    *,
    provenance: AnalysisProvenance,
) -> SourceMap:
    """DTO compact → SourceMap canonique via le normalizer existant."""
    return normalize_source_map(
        reconstruct_to_canonical_raw(payload),
        transcript,
        provenance=provenance,
    )


def reconstruct_to_canonical_raw(payload: Mapping[str, Any]) -> dict:
    """
    Transforme un DTO compact en payload que normalize_source_map comprend.

    Lève SourceMapEditorialLeakError ou SourceMapValidationError. N'invente
    jamais un topic, une idea, une relation, un example, une référence,
    une incertitude ou une répétition.
    """
    if not isinstance(payload, Mapping):
        raise SourceMapValidationError(
            [
                "réponse provider inattendue : "
                f"{type(payload).__name__} au lieu d'un objet"
            ]
        )

    leaked = forbidden_editorial_fields(payload)
    if leaked:
        raise SourceMapEditorialLeakError(leaked, location="réponse du modèle")

    header_payload = payload.get("source_analysis")
    if isinstance(header_payload, Mapping):
        leaked_header = forbidden_editorial_fields(header_payload)
        if leaked_header:
            raise SourceMapEditorialLeakError(
                leaked_header, location="réponse du modèle / source_analysis"
            )
        _reject_unknown(header_payload, _KNOWN_HEADER, "source_analysis")

    voice_payload = payload.get("author_voice_profile")
    if isinstance(voice_payload, Mapping):
        leaked_voice = forbidden_editorial_fields(voice_payload)
        if leaked_voice:
            raise SourceMapEditorialLeakError(
                leaked_voice, location="réponse du modèle / author_voice_profile"
            )
        _reject_unknown(voice_payload, _KNOWN_VOICE, "author_voice_profile")

    _reject_unknown(payload, _KNOWN_TOP_LEVEL, "réponse provider")

    errors: list[str] = []
    topics_in = _as_list(payload.get("topics"), "topics", errors)
    ideas_in = _as_list(payload.get("ideas"), "ideas", errors)
    relations_in = _as_list(payload.get("relations"), "relations", errors)
    examples_in = _as_list(payload.get("examples"), "examples", errors)
    references_in = _as_list(payload.get("references"), "references", errors)
    uncertainties_in = _as_list(payload.get("uncertainties"), "uncertainties", errors)
    repetitions_in = _as_list(payload.get("repetitions"), "repetitions", errors)

    topic_count = len(topics_in)
    idea_count = len(ideas_in)

    raw_topics: list[dict] = []
    for position, item in enumerate(topics_in):
        if not isinstance(item, Mapping):
            errors.append(f"topics[{position}] : un objet est attendu")
            continue
        raw_topics.append(
            {
                "topic_id": _local_topic_id(position),
                "label": item.get("label"),
                "summary": item.get("summary"),
                "source_refs": item.get("source_refs"),
            }
        )

    raw_ideas: list[dict] = []
    for position, item in enumerate(ideas_in):
        if not isinstance(item, Mapping):
            errors.append(f"ideas[{position}] : un objet est attendu")
            continue
        topic_indexes = _indexes(
            item.get("topic_indexes"),
            bound=topic_count,
            context=f"ideas[{position}].topic_indexes",
            errors=errors,
        )
        raw_ideas.append(
            {
                "idea_id": _local_idea_id(position),
                "summary": item.get("summary"),
                "kind": item.get("kind"),
                "importance": item.get("importance"),
                "topic_refs": [_local_topic_id(index) for index in topic_indexes],
                "relations": [],
                "source_refs": item.get("source_refs"),
            }
        )

    seen_relations: set[tuple[int, int, str]] = set()
    for position, item in enumerate(relations_in):
        if not isinstance(item, Mapping):
            errors.append(f"relations[{position}] : un objet est attendu")
            continue
        origin = _one_index(
            item.get("from"),
            bound=idea_count,
            context=f"relations[{position}].from",
            errors=errors,
        )
        target = _one_index(
            item.get("to"),
            bound=idea_count,
            context=f"relations[{position}].to",
            errors=errors,
        )
        relation = item.get("relation")
        if not isinstance(relation, str) or not relation.strip():
            errors.append(f"relations[{position}] : relation absente")
            continue
        if origin is None or target is None:
            continue
        key = (origin, target, relation.strip())
        if key in seen_relations:
            continue
        seen_relations.add(key)
        if origin < len(raw_ideas):
            raw_ideas[origin]["relations"].append(
                {"relation": relation.strip(), "to_idea": _local_idea_id(target)}
            )

    raw_examples: list[dict] = []
    for position, item in enumerate(examples_in):
        if not isinstance(item, Mapping):
            errors.append(f"examples[{position}] : un objet est attendu")
            continue
        idea_indexes = _indexes(
            item.get("idea_indexes"),
            bound=idea_count,
            context=f"examples[{position}].idea_indexes",
            errors=errors,
        )
        raw_examples.append(
            {
                "kind": item.get("kind"),
                "summary": item.get("summary"),
                "supports_idea_refs": [_local_idea_id(index) for index in idea_indexes],
                "source_refs": item.get("source_refs"),
            }
        )

    raw_references: list[dict] = []
    for position, item in enumerate(references_in):
        if not isinstance(item, Mapping):
            errors.append(f"references[{position}] : un objet est attendu")
            continue
        raw_references.append(
            {
                "kind": item.get("kind"),
                "raw_reference": item.get("raw_reference"),
                "normalized_reference": item.get("normalized_reference") or "",
                "completeness": item.get("completeness"),
                "source_refs": item.get("source_refs"),
            }
        )

    raw_uncertainties: list[dict] = []
    for position, item in enumerate(uncertainties_in):
        if not isinstance(item, Mapping):
            errors.append(f"uncertainties[{position}] : un objet est attendu")
            continue
        raw_uncertainties.append(
            {
                "kind": item.get("kind"),
                "description": item.get("description"),
                "severity": item.get("severity"),
                "source_refs": item.get("source_refs"),
            }
        )

    raw_repetitions: list[dict] = []
    for position, item in enumerate(repetitions_in):
        if not isinstance(item, Mapping):
            errors.append(f"repetitions[{position}] : un objet est attendu")
            continue
        idea_indexes = _indexes(
            item.get("idea_indexes"),
            bound=idea_count,
            context=f"repetitions[{position}].idea_indexes",
            errors=errors,
        )
        raw_repetitions.append(
            {
                "character": item.get("character"),
                "description": item.get("description"),
                "idea_refs": [_local_idea_id(index) for index in idea_indexes],
                "source_refs": item.get("source_refs"),
            }
        )

    if errors:
        raise SourceMapValidationError(errors)

    header = header_payload if isinstance(header_payload, Mapping) else {}
    voice = voice_payload if isinstance(voice_payload, Mapping) else {}

    return {
        "source_analysis": {
            "main_theme": header.get("main_theme"),
            "author_intent": _copy_intent(header.get("author_intent")),
            "target_audience": _copy_intent(header.get("target_audience")),
        },
        "topics": raw_topics,
        "ideas": raw_ideas,
        "examples": raw_examples,
        "references": raw_references,
        "uncertainties": raw_uncertainties,
        "repetitions": raw_repetitions,
        "author_voice_profile": {
            key: voice.get(key, [] if key in {"tone", "rhetorical_patterns", "distinctive_traits"} else "")
            for key in _KNOWN_VOICE
        },
    }


def looks_like_canonical_raw(payload: Mapping[str, Any] | None) -> bool:
    """True si le payload ressemble à l'ancien contrat modèle (IDs locaux)."""
    if not isinstance(payload, Mapping):
        return False

    topics = payload.get("topics")
    if isinstance(topics, list) and topics and isinstance(topics[0], Mapping):
        if "topic_id" in topics[0]:
            return True

    ideas = payload.get("ideas")
    if isinstance(ideas, list) and ideas and isinstance(ideas[0], Mapping):
        first = ideas[0]
        if "idea_id" in first or "topic_refs" in first or "relations" in first:
            return True

    return False


def to_compact_provider_payload(payload: Mapping[str, Any]) -> dict:
    """
    Adaptateur de test : ancienne réponse brute → DTO compact.

    Préserve les clés inconnues (y compris éditoriales) pour que les tests
    historiques de fuite restent significatifs. N'est PAS un chemin de
    production : le modèle produit directement le DTO.
    """
    compact: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in _KNOWN_TOP_LEVEL and key != "relations":
            compact[key] = value

    header = payload.get("source_analysis")
    if isinstance(header, Mapping):
        compact["source_analysis"] = dict(header)
    elif "source_analysis" in payload:
        compact["source_analysis"] = header

    topic_ids: dict[str, int] = {}
    topics_out: list[dict] = []
    for index, item in enumerate(payload.get("topics") or []):
        if not isinstance(item, Mapping):
            continue
        local = _text(item.get("topic_id"))
        if local:
            topic_ids[local] = index
        topics_out.append(
            {
                "label": item.get("label", ""),
                "summary": item.get("summary", ""),
                "source_refs": list(item.get("source_refs") or []),
            }
        )
    compact["topics"] = topics_out

    idea_ids: dict[str, int] = {}
    ideas_out: list[dict] = []
    relations_out: list[dict] = []
    raw_ideas = payload.get("ideas") or []
    for index, item in enumerate(raw_ideas):
        if not isinstance(item, Mapping):
            continue
        local = _text(item.get("idea_id"))
        if local:
            idea_ids[local] = index
        topic_indexes = _map_id_list(item.get("topic_refs"), topic_ids, len(topics_out))
        ideas_out.append(
            {
                "summary": item.get("summary", ""),
                "kind": item.get("kind", ""),
                "importance": item.get("importance", ""),
                "topic_indexes": topic_indexes,
                "source_refs": list(item.get("source_refs") or []),
            }
        )
    compact["ideas"] = ideas_out

    for from_index, item in enumerate(raw_ideas):
        if not isinstance(item, Mapping):
            continue
        for relation in item.get("relations") or []:
            if not isinstance(relation, Mapping):
                continue
            target_local = _text(relation.get("to_idea"))
            to_index = idea_ids.get(target_local)
            if to_index is None:
                to_index = len(ideas_out) + 1000
            relations_out.append(
                {
                    "from": from_index,
                    "to": to_index,
                    "relation": relation.get("relation", ""),
                }
            )
    compact["relations"] = relations_out

    examples_out: list[dict] = []
    for item in payload.get("examples") or []:
        if not isinstance(item, Mapping):
            continue
        examples_out.append(
            {
                "kind": item.get("kind", ""),
                "summary": item.get("summary", ""),
                "idea_indexes": _map_id_list(
                    item.get("supports_idea_refs"), idea_ids, len(ideas_out)
                ),
                "source_refs": list(item.get("source_refs") or []),
            }
        )
    compact["examples"] = examples_out

    references_out: list[dict] = []
    for item in payload.get("references") or []:
        if not isinstance(item, Mapping):
            continue
        references_out.append(
            {
                "kind": item.get("kind", ""),
                "raw_reference": item.get("raw_reference", ""),
                "normalized_reference": item.get("normalized_reference") or "",
                "completeness": item.get("completeness", ""),
                "source_refs": list(item.get("source_refs") or []),
            }
        )
    compact["references"] = references_out

    uncertainties_out: list[dict] = []
    for item in payload.get("uncertainties") or []:
        if not isinstance(item, Mapping):
            continue
        uncertainties_out.append(
            {
                "kind": item.get("kind", ""),
                "description": item.get("description", ""),
                "severity": item.get("severity", ""),
                "source_refs": list(item.get("source_refs") or []),
            }
        )
    compact["uncertainties"] = uncertainties_out

    repetitions_out: list[dict] = []
    for item in payload.get("repetitions") or []:
        if not isinstance(item, Mapping):
            continue
        repetitions_out.append(
            {
                "character": item.get("character", ""),
                "description": item.get("description", ""),
                "idea_indexes": _map_id_list(
                    item.get("idea_refs"), idea_ids, len(ideas_out)
                ),
                "source_refs": list(item.get("source_refs") or []),
            }
        )
    compact["repetitions"] = repetitions_out

    voice = payload.get("author_voice_profile")
    if isinstance(voice, Mapping):
        compact["author_voice_profile"] = {
            "tone": list(voice.get("tone") or []),
            "register": voice.get("register") or "",
            "sentence_style": voice.get("sentence_style") or "",
            "rhetorical_patterns": list(voice.get("rhetorical_patterns") or []),
            "use_of_questions": voice.get("use_of_questions") or "",
            "use_of_repetition": voice.get("use_of_repetition") or "",
            "use_of_examples": voice.get("use_of_examples") or "",
            "direct_address": voice.get("direct_address") or "",
            "teaching_style": voice.get("teaching_style") or "",
            "distinctive_traits": list(voice.get("distinctive_traits") or []),
        }
        for key, value in voice.items():
            if key not in _KNOWN_VOICE:
                compact["author_voice_profile"][key] = value
    elif "author_voice_profile" in payload:
        compact["author_voice_profile"] = voice

    return compact


def _local_topic_id(index: int) -> str:
    return f"t{index}"


def _local_idea_id(index: int) -> str:
    return f"i{index}"


def _reject_unknown(payload: Mapping, known: frozenset[str], location: str) -> None:
    from app.source_analysis.models import FORBIDDEN_EDITORIAL_FIELDS

    stray = [
        name
        for name in payload
        if name not in known and name not in FORBIDDEN_EDITORIAL_FIELDS
    ]
    if stray:
        raise SourceMapValidationError(
            [f"champ provider inconnu dans {location} : « {name} »" for name in stray]
        )


def _as_list(raw: Any, name: str, errors: list[str]) -> list:
    if raw is None:
        return []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        errors.append(f"{name} : une liste est attendue")
        return []
    return list(raw)


def _indexes(
    raw: Any,
    *,
    bound: int,
    context: str,
    errors: list[str],
) -> list[int]:
    if raw is None:
        return []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        errors.append(f"{context} : une liste d'entiers est attendue")
        return []

    resolved: list[int] = []
    seen: set[int] = set()
    for position, value in enumerate(raw):
        index = _one_index(
            value,
            bound=bound,
            context=f"{context}[{position}]",
            errors=errors,
        )
        if index is None or index in seen:
            continue
        seen.add(index)
        resolved.append(index)
    return resolved


def _one_index(
    value: Any,
    *,
    bound: int,
    context: str,
    errors: list[str],
) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{context} : un entier est attendu")
        return None
    if bound <= 0 or value < 0 or value >= bound:
        errors.append(
            f"{context} : index {value} hors plage "
            f"[0, {max(bound - 1, 0)}]"
        )
        return None
    return value


def _copy_intent(raw: Any) -> dict:
    data = raw if isinstance(raw, Mapping) else {}
    return {
        "summary": data.get("summary"),
        "confidence": data.get("confidence"),
        "kinds": list(data.get("kinds") or []),
    }


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _map_id_list(raw: Any, mapping: Mapping[str, int], bound: int) -> list[int]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    indexes: list[int] = []
    seen: set[int] = set()
    for value in raw:
        local = _text(value)
        if local in mapping:
            index = mapping[local]
        else:
            index = bound + 1000
        if index in seen:
            continue
        seen.add(index)
        indexes.append(index)
    return indexes
