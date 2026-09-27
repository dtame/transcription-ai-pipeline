"""
Decoder déterministe : UltraCompactSemanticResponse → raw canonique.

Pure, offline, fail-closed. Aucune réparation, aucune approximation
d'enum, aucun drop silencieux.

    UltraCompactSemanticResponse
        → decode_to_canonical_raw()
        → normalize_source_map()
        → validator canonique
        → SourceMap

Le decoder décide de la STRUCTURE (collections, IDs locaux, rattachement
des relations). Il n'invente aucune décision sémantique : un passage n'est
un topic, une idea, un example, une relation, etc. que si Claude l'a
déclaré par un record de kind correspondant.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from app.source_analysis.errors import (
    SourceMapEditorialLeakError,
    SourceMapValidationError,
)
from app.source_analysis.models import (
    CONFIDENCE_LEVELS,
    EXAMPLE_KINDS,
    IDEA_KINDS,
    IMPORTANCE_LEVELS,
    REFERENCE_COMPLETENESS,
    REFERENCE_KINDS,
    RELATION_KINDS,
    REPETITION_CHARACTERS,
    SEVERITY_LEVELS,
    UNCERTAINTY_KINDS,
    AnalysisProvenance,
    SourceMap,
    forbidden_editorial_fields,
)
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.ultra_compact_schema import (
    ALLOWED_RECORD_KINDS,
    KIND_AUDIENCE_KIND,
    KIND_EXAMPLE,
    KIND_IDEA,
    KIND_INTENT_KIND,
    KIND_REFERENCE,
    KIND_RELATION,
    KIND_REPETITION,
    KIND_TOPIC,
    KIND_UNCERTAINTY,
    KIND_VOICE,
    ULTRA_RECORD_FIELDS,
    ULTRA_ROOT_FIELDS,
    VOICE_FIELDS,
    VOICE_LIST_FIELDS,
    VOICE_SCALAR_FIELDS,
)

_SRC_RE = re.compile(r"^SRC[0-9]{6}$")
_KNOWN_ROOT = frozenset(ULTRA_ROOT_FIELDS) | {"source_analysis", "author_voice_profile"}
_KNOWN_RECORD = frozenset(ULTRA_RECORD_FIELDS)
_ALLOWED_KINDS = frozenset(ALLOWED_RECORD_KINDS)

# Kinds dont l[] doit être vide.
_NO_LINKS = frozenset(
    {
        KIND_TOPIC,
        KIND_REFERENCE,
        KIND_UNCERTAINTY,
        KIND_VOICE,
        KIND_INTENT_KIND,
        KIND_AUDIENCE_KIND,
    }
)

# Kinds qui exigent au moins un SRC.
_REQUIRES_SRC = frozenset(
    {
        KIND_TOPIC,
        KIND_IDEA,
        KIND_EXAMPLE,
        KIND_REFERENCE,
        KIND_UNCERTAINTY,
        KIND_REPETITION,
    }
)


def decode_source_map(
    payload: Mapping[str, Any],
    transcript: TranscriptInput,
    *,
    provenance: AnalysisProvenance,
    allowed_source_refs: set[str] | None = None,
) -> SourceMap:
    """Transport ultra → SourceMap canonique via le normalizer existant."""
    allowed = allowed_source_refs
    if allowed is None:
        allowed = set(transcript.src_ids())
    return normalize_source_map(
        decode_to_canonical_raw(payload, allowed_source_refs=allowed),
        transcript,
        provenance=provenance,
    )


def decode_to_canonical_raw(
    payload: Mapping[str, Any],
    *,
    allowed_source_refs: set[str] | None = None,
) -> dict:
    """
    Transforme le transport ultra-compact en payload de normalize_source_map.

    Lève SourceMapEditorialLeakError ou SourceMapValidationError.
    N'invente jamais un topic, une idea, une relation, un example, une
    référence, une incertitude, une répétition, un voice trait, un kind
    d'intention ou d'audience.
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

    header_extra = payload.get("source_analysis")
    if isinstance(header_extra, Mapping):
        leaked_header = forbidden_editorial_fields(header_extra)
        if leaked_header:
            raise SourceMapEditorialLeakError(
                leaked_header, location="réponse du modèle / source_analysis"
            )
        _reject_unknown(header_extra, frozenset(), "source_analysis")

    voice_extra = payload.get("author_voice_profile")
    if isinstance(voice_extra, Mapping):
        leaked_voice = forbidden_editorial_fields(voice_extra)
        if leaked_voice:
            raise SourceMapEditorialLeakError(
                leaked_voice, location="réponse du modèle / author_voice_profile"
            )
        _reject_unknown(voice_extra, frozenset(VOICE_FIELDS), "author_voice_profile")

    _reject_unknown(payload, _KNOWN_ROOT, "réponse provider")

    errors: list[str] = []
    theme = _required_text(payload.get("theme"), "theme", errors)
    intent_summary = _required_text(payload.get("intent"), "intent", errors)
    intent_confidence = _confidence(payload.get("ic"), "ic", errors)
    audience_summary = _required_text(payload.get("aud"), "aud", errors)
    audience_confidence = _confidence(payload.get("ac"), "ac", errors)

    records_in = _as_list(payload.get("records"), "records", errors)
    parsed_records: list[dict] = []
    for position, item in enumerate(records_in):
        parsed = _parse_record(item, position, errors, allowed_source_refs)
        if parsed is not None:
            parsed_records.append(parsed)

    kinds = [record["k"] for record in parsed_records]
    for position, record in enumerate(parsed_records):
        _validate_links(record, position, kinds, errors)

    _validate_relation_uniqueness(parsed_records, errors)

    if errors:
        raise SourceMapValidationError(errors)

    intent_kinds = [
        record["v"] for record in parsed_records if record["k"] == KIND_INTENT_KIND
    ]
    audience_kinds = [
        record["v"] for record in parsed_records if record["k"] == KIND_AUDIENCE_KIND
    ]

    topic_positions = [i for i, record in enumerate(parsed_records) if record["k"] == KIND_TOPIC]
    idea_positions = [i for i, record in enumerate(parsed_records) if record["k"] == KIND_IDEA]
    topic_local = {index: _local_topic_id(order) for order, index in enumerate(topic_positions)}
    idea_local = {index: _local_idea_id(order) for order, index in enumerate(idea_positions)}

    raw_topics: list[dict] = []
    for order, index in enumerate(topic_positions):
        record = parsed_records[index]
        raw_topics.append(
            {
                "topic_id": _local_topic_id(order),
                "label": record["v"],
                "summary": record["m"][0],
                "source_refs": record["s"],
            }
        )

    raw_ideas: list[dict] = []
    for order, index in enumerate(idea_positions):
        record = parsed_records[index]
        raw_ideas.append(
            {
                "idea_id": _local_idea_id(order),
                "summary": record["v"],
                "kind": record["m"][0],
                "importance": record["m"][1],
                "topic_refs": list(dict.fromkeys(topic_local[link] for link in record["l"])),
                "relations": [],
                "source_refs": record["s"],
            }
        )

    for record in parsed_records:
        if record["k"] != KIND_RELATION:
            continue
        origin = record["l"][0]
        target = record["l"][1]
        origin_order = idea_positions.index(origin)
        raw_ideas[origin_order]["relations"].append(
            {"relation": record["v"], "to_idea": idea_local[target]}
        )

    raw_examples: list[dict] = []
    for record in parsed_records:
        if record["k"] != KIND_EXAMPLE:
            continue
        raw_examples.append(
            {
                "kind": record["m"][0],
                "summary": record["v"],
                "supports_idea_refs": [idea_local[link] for link in record["l"]],
                "source_refs": record["s"],
            }
        )

    raw_references: list[dict] = []
    for record in parsed_records:
        if record["k"] != KIND_REFERENCE:
            continue
        raw_references.append(
            {
                "kind": record["m"][0],
                "raw_reference": record["v"],
                "normalized_reference": record["m"][2],
                "completeness": record["m"][1],
                "source_refs": record["s"],
            }
        )

    raw_uncertainties: list[dict] = []
    for record in parsed_records:
        if record["k"] != KIND_UNCERTAINTY:
            continue
        raw_uncertainties.append(
            {
                "kind": record["m"][0],
                "description": record["v"],
                "severity": record["m"][1],
                "source_refs": record["s"],
            }
        )

    raw_repetitions: list[dict] = []
    for record in parsed_records:
        if record["k"] != KIND_REPETITION:
            continue
        raw_repetitions.append(
            {
                "character": record["m"][0],
                "description": record["v"],
                "idea_refs": [idea_local[link] for link in record["l"]],
                "source_refs": record["s"],
            }
        )

    voice = _assemble_voice(parsed_records)

    return {
        "source_analysis": {
            "main_theme": theme,
            "author_intent": {
                "summary": intent_summary,
                "confidence": intent_confidence,
                "kinds": intent_kinds,
            },
            "target_audience": {
                "summary": audience_summary,
                "confidence": audience_confidence,
                "kinds": audience_kinds,
            },
        },
        "topics": raw_topics,
        "ideas": raw_ideas,
        "examples": raw_examples,
        "references": raw_references,
        "uncertainties": raw_uncertainties,
        "repetitions": raw_repetitions,
        "author_voice_profile": voice,
    }


def _parse_record(
    item: Any,
    position: int,
    errors: list[str],
    allowed_source_refs: set[str] | None,
) -> dict | None:
    context = f"records[{position}]"
    if not isinstance(item, Mapping):
        errors.append(f"{context} : un objet est attendu")
        return None

    leaked = forbidden_editorial_fields(item)
    if leaked:
        raise SourceMapEditorialLeakError(
            leaked, location=f"réponse du modèle / {context}"
        )
    try:
        _reject_unknown(item, _KNOWN_RECORD, context)
    except SourceMapValidationError as exc:
        errors.extend(exc.errors)
        return None

    kind = item.get("k")
    if not isinstance(kind, str) or not kind.strip():
        errors.append(f"{context} : k absent ou vide")
        return None
    kind = kind.strip()
    if kind not in _ALLOWED_KINDS:
        errors.append(f"{context} : kind inconnu « {kind} »")
        return None

    value = item.get("v")
    if not isinstance(value, str):
        errors.append(f"{context} : v doit être une chaîne")
        return None
    value = value.strip()

    source_refs = _source_refs(item.get("s"), context, errors, allowed_source_refs)
    links = _link_indexes(item.get("l"), context, errors)
    metadata = _metadata(item.get("m"), context, errors)

    _validate_kind_payload(
        kind=kind,
        value=value,
        source_refs=source_refs,
        links=links,
        metadata=metadata,
        context=context,
        errors=errors,
    )

    return {
        "k": kind,
        "v": value,
        "s": source_refs,
        "l": links,
        "m": metadata,
    }


def _validate_kind_payload(
    *,
    kind: str,
    value: str,
    source_refs: list[str],
    links: list[int],
    metadata: list[str],
    context: str,
    errors: list[str],
) -> None:
    if kind in _REQUIRES_SRC and not source_refs:
        errors.append(f"{context} : s (source_refs) requis et non vide")

    if kind in _NO_LINKS and links:
        errors.append(f"{context} : l doit être vide pour {kind}")

    if kind in {KIND_INTENT_KIND, KIND_AUDIENCE_KIND, KIND_RELATION}:
        if source_refs:
            errors.append(f"{context} : s doit être vide pour {kind}")
        if metadata:
            errors.append(f"{context} : m doit être vide pour {kind}")

    if kind == KIND_TOPIC:
        if not value:
            errors.append(f"{context} : label TOPIC vide")
        if len(metadata) != 1 or not metadata[0]:
            errors.append(f"{context} : TOPIC exige m=[summary] non vide")

    elif kind == KIND_IDEA:
        if not value:
            errors.append(f"{context} : summary IDEA vide")
        if len(metadata) != 2:
            errors.append(f"{context} : IDEA exige m=[kind, importance]")
        else:
            if metadata[0] not in IDEA_KINDS:
                errors.append(f"{context} : idea kind invalide « {metadata[0]} »")
            if metadata[1] not in IMPORTANCE_LEVELS:
                errors.append(f"{context} : importance invalide « {metadata[1]} »")

    elif kind == KIND_RELATION:
        if value not in RELATION_KINDS:
            errors.append(f"{context} : relation type invalide « {value} »")
        if len(links) != 2:
            errors.append(f"{context} : RELATION exige l=[from, to]")

    elif kind == KIND_EXAMPLE:
        if not value:
            errors.append(f"{context} : summary EXAMPLE vide")
        if len(metadata) != 1 or metadata[0] not in EXAMPLE_KINDS:
            errors.append(
                f"{context} : EXAMPLE exige m=[kind] parmi {', '.join(EXAMPLE_KINDS)}"
            )

    elif kind == KIND_REFERENCE:
        if not value:
            errors.append(f"{context} : raw_reference vide")
        if len(metadata) != 3:
            errors.append(
                f"{context} : REFERENCE exige m=[kind, completeness, normalized]"
            )
        else:
            if metadata[0] not in REFERENCE_KINDS:
                errors.append(f"{context} : reference kind invalide « {metadata[0]} »")
            if metadata[1] not in REFERENCE_COMPLETENESS:
                errors.append(
                    f"{context} : completeness invalide « {metadata[1]} »"
                )

    elif kind == KIND_UNCERTAINTY:
        if not value:
            errors.append(f"{context} : description UNCERTAINTY vide")
        if len(metadata) != 2:
            errors.append(f"{context} : UNCERTAINTY exige m=[kind, severity]")
        else:
            if metadata[0] not in UNCERTAINTY_KINDS:
                errors.append(f"{context} : uncertainty kind invalide « {metadata[0]} »")
            if metadata[1] not in SEVERITY_LEVELS:
                errors.append(f"{context} : severity invalide « {metadata[1]} »")

    elif kind == KIND_REPETITION:
        if not value:
            errors.append(f"{context} : description REPETITION vide")
        if len(metadata) != 1 or metadata[0] not in REPETITION_CHARACTERS:
            errors.append(
                f"{context} : REPETITION exige m=[character] parmi "
                f"{', '.join(REPETITION_CHARACTERS)}"
            )
        if len(links) < 2:
            errors.append(f"{context} : REPETITION exige au moins deux liens IDEA")

    elif kind == KIND_VOICE:
        if len(metadata) != 1 or metadata[0] not in VOICE_FIELDS:
            errors.append(
                f"{context} : VOICE exige m=[champ] parmi {', '.join(VOICE_FIELDS)}"
            )
        elif metadata[0] in VOICE_LIST_FIELDS and not value:
            errors.append(f"{context} : VOICE liste « {metadata[0]} » : v vide")

    elif kind in {KIND_INTENT_KIND, KIND_AUDIENCE_KIND}:
        if not value:
            errors.append(f"{context} : kind {kind} vide")


def _validate_links(
    record: Mapping[str, Any],
    position: int,
    kinds: Sequence[str],
    errors: list[str],
) -> None:
    kind = record["k"]
    context = f"records[{position}]"
    bound = len(kinds)
    for link in record["l"]:
        if link < 0 or link >= bound:
            errors.append(f"{context} : index {link} hors plage [0, {max(bound - 1, 0)}]")
            continue
        target = kinds[link]
        if kind == KIND_IDEA and target != KIND_TOPIC:
            errors.append(f"{context} : IDEA ne peut lier que TOPIC, pas {target}")
        elif kind == KIND_RELATION and target != KIND_IDEA:
            errors.append(f"{context} : RELATION ne peut lier que IDEA, pas {target}")
        elif kind == KIND_EXAMPLE and target != KIND_IDEA:
            errors.append(f"{context} : EXAMPLE ne peut lier que IDEA, pas {target}")
        elif kind == KIND_REPETITION and target != KIND_IDEA:
            errors.append(f"{context} : REPETITION ne peut lier que IDEA, pas {target}")

    if kind == KIND_RELATION and len(record["l"]) == 2:
        origin, target = record["l"]
        if origin == target:
            errors.append(f"{context} : RELATION auto-lien interdit")
        if origin == position or target == position:
            errors.append(f"{context} : RELATION ne peut pas se lier elle-même")


def _validate_relation_uniqueness(records: Sequence[Mapping], errors: list[str]) -> None:
    seen: set[tuple[int, int, str]] = set()
    for position, record in enumerate(records):
        if record["k"] != KIND_RELATION or len(record["l"]) != 2:
            continue
        key = (record["l"][0], record["l"][1], record["v"])
        if key in seen:
            errors.append(f"records[{position}] : relation dupliquée")
        seen.add(key)


def _assemble_voice(records: Sequence[Mapping[str, Any]]) -> dict:
    voice: dict[str, Any] = {
        field: [] if field in VOICE_LIST_FIELDS else "" for field in VOICE_FIELDS
    }
    for record in records:
        if record["k"] != KIND_VOICE or not record["m"]:
            continue
        field = record["m"][0]
        if field in VOICE_LIST_FIELDS:
            voice[field].append(record["v"])
        elif field in VOICE_SCALAR_FIELDS:
            voice[field] = record["v"]
    return voice


def _source_refs(
    raw: Any,
    context: str,
    errors: list[str],
    allowed: set[str] | None,
) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        errors.append(f"{context}.s : une liste de chaînes est attendue")
        return []
    refs: list[str] = []
    seen: set[str] = set()
    for position, value in enumerate(raw):
        if not isinstance(value, str):
            errors.append(f"{context}.s[{position}] : une chaîne SRC est attendue")
            continue
        ref = value.strip()
        if not _SRC_RE.match(ref):
            errors.append(f"{context}.s[{position}] : source_ref mal formé « {ref} »")
            continue
        if allowed is not None and ref not in allowed:
            errors.append(f"{context}.s[{position}] : source_ref inconnu « {ref} »")
            continue
        if ref in seen:
            continue
        seen.add(ref)
        refs.append(ref)
    return refs


def _link_indexes(raw: Any, context: str, errors: list[str]) -> list[int]:
    if raw is None:
        return []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        errors.append(f"{context}.l : une liste d'entiers est attendue")
        return []
    links: list[int] = []
    for position, value in enumerate(raw):
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"{context}.l[{position}] : un entier est attendu")
            continue
        links.append(value)
    return links


def _metadata(raw: Any, context: str, errors: list[str]) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        errors.append(f"{context}.m : une liste de chaînes est attendue")
        return []
    values: list[str] = []
    for position, value in enumerate(raw):
        if not isinstance(value, str):
            errors.append(f"{context}.m[{position}] : une chaîne est attendue")
            continue
        values.append(value.strip())
    return values


def _confidence(raw: Any, name: str, errors: list[str]) -> str:
    if isinstance(raw, bool) or isinstance(raw, (int, float)):
        errors.append(f"{name} : une chaîne de confiance est attendue")
        return ""
    if not isinstance(raw, str):
        errors.append(f"{name} : une chaîne de confiance est attendue")
        return ""
    value = raw.strip()
    if value not in CONFIDENCE_LEVELS:
        errors.append(
            f"{name} : confidence invalide « {value} » "
            f"(attendu parmi {', '.join(CONFIDENCE_LEVELS)})"
        )
    return value


def _required_text(raw: Any, name: str, errors: list[str]) -> str:
    if not isinstance(raw, str) or not raw.strip():
        errors.append(f"{name} vide")
        return ""
    return raw.strip()


def _as_list(raw: Any, name: str, errors: list[str]) -> list:
    if raw is None:
        errors.append(f"{name} : une liste est attendue")
        return []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        errors.append(f"{name} : une liste est attendue")
        return []
    return list(raw)


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


def _local_topic_id(index: int) -> str:
    return f"t{index}"


def _local_idea_id(index: int) -> str:
    return f"i{index}"
