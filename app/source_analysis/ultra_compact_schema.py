"""
Transport sémantique ultra-compact — Generation C (Phase 3B.4.2).

Langage intermédiaire entre Claude et le SourceMap canonique.
Distinct du DTO compact 3B.4 (compact_schema.py) et du contrat métier
(models.py / validator.py). Ceux-ci ne sont PAS simplifiés.

    TRANSCRIPT
        ↓
    Claude  →  UltraCompactSemanticResponse
        ↓
    semantic_transport_decoder
        ↓
    canonical raw  →  normalize_source_map  →  validator

Forme volontairement plate :

    1 objet racine
    + 1 array `records`
    + 1 forme de record unique {k, v, s, l, m}

Aucune enum provider, aucun pattern, aucun minItems, aucun $ref,
aucun anyOf/oneOf. Le decoder local est strict ; le schéma provider
est permissif. additionalProperties=false est ajouté par l'adaptateur
Anthropic, qui ne connaît pas le métier SourceMap.

Version : semantic-transport-v1
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from app.file_utils import content_hash
from app.source_analysis.compact_reconstructor import (
    looks_like_canonical_raw,
    to_compact_provider_payload,
)
from app.source_analysis.compact_schema import COMPACT_REQUIRED_FIELDS
from app.source_analysis.models import forbidden_editorial_fields

SEMANTIC_TRANSPORT_VERSION = "semantic-transport-v1"
ULTRA_COMPACT_SCHEMA_VERSION = "1.0"

# Profondeur de l'instance JSON (racine → records[] → record). Distincte
# de maximum_nesting_depth du schéma (mots-clés JSON Schema).
ULTRA_INSTANCE_MAX_DEPTH = 3

KIND_TOPIC = "TOPIC"
KIND_IDEA = "IDEA"
KIND_RELATION = "RELATION"
KIND_EXAMPLE = "EXAMPLE"
KIND_REFERENCE = "REFERENCE"
KIND_UNCERTAINTY = "UNCERTAINTY"
KIND_REPETITION = "REPETITION"
KIND_VOICE = "VOICE"
KIND_INTENT_KIND = "INTENT_KIND"
KIND_AUDIENCE_KIND = "AUDIENCE_KIND"

ALLOWED_RECORD_KINDS = (
    KIND_TOPIC,
    KIND_IDEA,
    KIND_RELATION,
    KIND_EXAMPLE,
    KIND_REFERENCE,
    KIND_UNCERTAINTY,
    KIND_REPETITION,
    KIND_VOICE,
    KIND_INTENT_KIND,
    KIND_AUDIENCE_KIND,
)

# Champs racine — tous requis, 0 optionnel.
ULTRA_ROOT_FIELDS = (
    "theme",
    "intent",
    "ic",
    "aud",
    "ac",
    "records",
)

# Record uniforme — tous requis. [] / "" = non applicable.
ULTRA_RECORD_FIELDS = (
    "k",  # kind
    "v",  # valeur sémantique principale
    "s",  # vrais SRC (jamais des index 0,1,2 comme identité)
    "l",  # index globaux de records
    "m",  # métadonnées compactes, interprétées selon k
)

VOICE_LIST_FIELDS = (
    "tone",
    "rhetorical_patterns",
    "distinctive_traits",
)

VOICE_SCALAR_FIELDS = (
    "register",
    "sentence_style",
    "use_of_questions",
    "use_of_repetition",
    "use_of_examples",
    "direct_address",
    "teaching_style",
)

VOICE_FIELDS = VOICE_LIST_FIELDS + VOICE_SCALAR_FIELDS

# Sémantique de m[] / l[] / v selon k. Documentée pour le prompt et le decoder.
#
# TOPIC            v=label  m=[summary]              s=SRC     l=[]
# IDEA             v=summary m=[kind, importance]    s=SRC     l=index TOPIC
# RELATION         v=type    m=[]                    s=[]      l=[from IDEA, to IDEA]
# EXAMPLE          v=summary m=[kind]                s=SRC     l=index IDEA
# REFERENCE        v=raw     m=[kind, completeness, normalized] s=SRC  l=[]
# UNCERTAINTY      v=desc    m=[kind, severity]      s=SRC     l=[]
# REPETITION       v=desc    m=[character]           s=SRC     l=≥2 IDEA
# VOICE            v=valeur  m=[champ]               s=[]      l=[]
# INTENT_KIND      v=kind    m=[]                    s=[]      l=[]
# AUDIENCE_KIND    v=kind    m=[]                    s=[]      l=[]

RECORD_KIND_SEMANTICS: dict[str, str] = {
    KIND_TOPIC: "v=label ; m=[summary] ; s=SRC",
    KIND_IDEA: "v=summary ; m=[kind, importance] ; l=TOPIC ; s=SRC",
    KIND_RELATION: "v=relationType ; l=[from IDEA, to IDEA]",
    KIND_EXAMPLE: "v=summary ; m=[kind] ; l=IDEA ; s=SRC",
    KIND_REFERENCE: "v=raw_reference ; m=[kind, completeness, normalized] ; s=SRC",
    KIND_UNCERTAINTY: "v=description ; m=[kind, severity] ; s=SRC",
    KIND_REPETITION: "v=description ; m=[character] ; l=≥2 IDEA ; s=SRC",
    KIND_VOICE: "v=valeur observée ; m=[champ voice]",
    KIND_INTENT_KIND: "v=étiquette author_intent.kinds",
    KIND_AUDIENCE_KIND: "v=étiquette target_audience.kinds",
}

SEMANTIC_DIMENSIONS_PRESERVED: tuple[str, ...] = (
    "main_theme",
    "author_intent.summary",
    "author_intent.confidence",
    "author_intent.kinds",
    "target_audience.summary",
    "target_audience.confidence",
    "target_audience.kinds",
    "topics",
    "ideas",
    "idea.kind",
    "idea.importance",
    "idea.topic_relationships",
    "idea.relationships",
    "idea.source_refs",
    "examples",
    "example.supports_idea_relationships",
    "example.source_refs",
    "references",
    "reference.source_refs",
    "uncertainties",
    "uncertainty.source_refs",
    "repetitions",
    "repetition.idea_relationships",
    "repetition.source_refs",
    "author_voice_profile",
)

# Index compact hors plage → index global définitivement hors plage.
_DANGLING_INDEX_BASE = 1_000_000


def build_ultra_compact_response_schema() -> dict:
    """
    Schéma JSON du transport ultra-compact.

    Reconstruit à chaque appel. Aucune enum, aucune contrainte numérique,
    aucun pattern : le decoder local valide le vocabulaire canonique.
    """
    return {
        "type": "object",
        "required": list(ULTRA_ROOT_FIELDS),
        "properties": {
            "theme": {"type": "string"},
            "intent": {"type": "string"},
            "ic": {"type": "string"},
            "aud": {"type": "string"},
            "ac": {"type": "string"},
            "records": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": list(ULTRA_RECORD_FIELDS),
                    "properties": {
                        "k": {"type": "string"},
                        "v": {"type": "string"},
                        "s": {"type": "array", "items": {"type": "string"}},
                        "l": {"type": "array", "items": {"type": "integer"}},
                        "m": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
    }


def build_provider_response_schema() -> dict:
    """Schéma réellement sélectionné pour le futur AIRequest (Generation C)."""
    return build_ultra_compact_response_schema()


def ultra_compact_schema_fingerprint(schema: Mapping[str, Any] | None = None) -> str:
    """Empreinte stable du contrat provider ultra-compact, pour la signature."""
    payload = build_ultra_compact_response_schema() if schema is None else schema
    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def looks_like_ultra_transport(payload: Mapping[str, Any] | None) -> bool:
    """True si le payload porte la forme racine du transport C."""
    if not isinstance(payload, Mapping):
        return False
    return "theme" in payload and "records" in payload


def looks_like_compact_dto(payload: Mapping[str, Any] | None) -> bool:
    """True si le payload ressemble au DTO compact 3B.4."""
    if not isinstance(payload, Mapping):
        return False
    if looks_like_ultra_transport(payload) and "topics" not in payload:
        return False
    return "source_analysis" in payload and "topics" in payload and "ideas" in payload


def to_ultra_transport_payload(payload: Mapping[str, Any]) -> dict:
    """
    Adaptateur de test : DTO compact ou raw canonique → transport ultra.

    Préserve les clés inconnues (y compris éditoriales) pour que les tests
    historiques de fuite restent significatifs. N'est PAS un chemin de
    production : le modèle produit directement le transport.
    """
    if looks_like_ultra_transport(payload) and not looks_like_compact_dto(payload):
        return dict(payload)

    compact = (
        to_compact_provider_payload(payload)
        if looks_like_canonical_raw(payload)
        else dict(payload)
    )

    header = compact.get("source_analysis")
    header_map = header if isinstance(header, Mapping) else {}
    intent = header_map.get("author_intent")
    intent_map = intent if isinstance(intent, Mapping) else {}
    audience = header_map.get("target_audience")
    audience_map = audience if isinstance(audience, Mapping) else {}

    records: list[dict] = []

    for kind in _text_list(intent_map.get("kinds")):
        records.append(_record(KIND_INTENT_KIND, kind))
    for kind in _text_list(audience_map.get("kinds")):
        records.append(_record(KIND_AUDIENCE_KIND, kind))

    topic_globals: list[int] = []
    for item in compact.get("topics") or []:
        if not isinstance(item, Mapping):
            continue
        topic_globals.append(len(records))
        records.append(
            _record(
                KIND_TOPIC,
                _text(item.get("label")),
                source_refs=_text_list(item.get("source_refs")),
                metadata=[_text(item.get("summary"))],
            )
        )

    idea_globals: list[int] = []
    for item in compact.get("ideas") or []:
        if not isinstance(item, Mapping):
            continue
        idea_globals.append(len(records))
        records.append(
            _record(
                KIND_IDEA,
                _text(item.get("summary")),
                source_refs=_text_list(item.get("source_refs")),
                links=_map_compact_indexes(item.get("topic_indexes"), topic_globals),
                metadata=[_text(item.get("kind")), _text(item.get("importance"))],
            )
        )

    for item in compact.get("relations") or []:
        if not isinstance(item, Mapping):
            continue
        records.append(
            _record(
                KIND_RELATION,
                _text(item.get("relation")),
                links=[
                    _map_one_compact_index(item.get("from"), idea_globals),
                    _map_one_compact_index(item.get("to"), idea_globals),
                ],
            )
        )

    for item in compact.get("examples") or []:
        if not isinstance(item, Mapping):
            continue
        records.append(
            _record(
                KIND_EXAMPLE,
                _text(item.get("summary")),
                source_refs=_text_list(item.get("source_refs")),
                links=_map_compact_indexes(item.get("idea_indexes"), idea_globals),
                metadata=[_text(item.get("kind"))],
            )
        )

    for item in compact.get("references") or []:
        if not isinstance(item, Mapping):
            continue
        records.append(
            _record(
                KIND_REFERENCE,
                _text(item.get("raw_reference")),
                source_refs=_text_list(item.get("source_refs")),
                metadata=[
                    _text(item.get("kind")),
                    _text(item.get("completeness")),
                    _text(item.get("normalized_reference")),
                ],
            )
        )

    for item in compact.get("uncertainties") or []:
        if not isinstance(item, Mapping):
            continue
        records.append(
            _record(
                KIND_UNCERTAINTY,
                _text(item.get("description")),
                source_refs=_text_list(item.get("source_refs")),
                metadata=[_text(item.get("kind")), _text(item.get("severity"))],
            )
        )

    for item in compact.get("repetitions") or []:
        if not isinstance(item, Mapping):
            continue
        records.append(
            _record(
                KIND_REPETITION,
                _text(item.get("description")),
                source_refs=_text_list(item.get("source_refs")),
                links=_map_compact_indexes(item.get("idea_indexes"), idea_globals),
                metadata=[_text(item.get("character"))],
            )
        )

    voice = compact.get("author_voice_profile")
    if isinstance(voice, Mapping):
        for field in VOICE_LIST_FIELDS:
            for value in _text_list(voice.get(field)):
                records.append(_record(KIND_VOICE, value, metadata=[field]))
        for field in VOICE_SCALAR_FIELDS:
            value = _text(voice.get(field))
            if value:
                records.append(_record(KIND_VOICE, value, metadata=[field]))

    ultra: dict[str, Any] = {
        "theme": _text(header_map.get("main_theme")),
        "intent": _text(intent_map.get("summary")),
        "ic": _text(intent_map.get("confidence")),
        "aud": _text(audience_map.get("summary")),
        "ac": _text(audience_map.get("confidence")),
        "records": records,
    }

    known_compact = set(COMPACT_REQUIRED_FIELDS) | {"relations"}
    for key, value in compact.items():
        if key not in known_compact:
            ultra[key] = value

    if isinstance(header_map, Mapping):
        extra_header = {
            key: value
            for key, value in header_map.items()
            if key not in {"main_theme", "author_intent", "target_audience"}
        }
        leaked_header = forbidden_editorial_fields(header_map)
        if extra_header or leaked_header:
            carried = dict(extra_header)
            for name in leaked_header:
                carried[name] = header_map[name]
            ultra["source_analysis"] = carried

    if isinstance(voice, Mapping):
        extra_voice = {key: value for key, value in voice.items() if key not in VOICE_FIELDS}
        leaked_voice = forbidden_editorial_fields(voice)
        if extra_voice or leaked_voice:
            carried = dict(extra_voice)
            for name in leaked_voice:
                carried[name] = voice[name]
            ultra["author_voice_profile"] = carried

    return ultra


def _record(
    kind: str,
    value: str,
    *,
    source_refs: Sequence[str] | None = None,
    links: Sequence[int] | None = None,
    metadata: Sequence[str] | None = None,
) -> dict:
    return {
        "k": kind,
        "v": value,
        "s": list(source_refs or []),
        "l": list(links or []),
        "m": list(metadata or []),
    }


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _text_list(raw: Any) -> list[str]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    values: list[str] = []
    for item in raw:
        text = _text(item)
        if text:
            values.append(text)
    return values


def _map_compact_indexes(raw: Any, mapping: Sequence[int]) -> list[int]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    return [_map_one_compact_index(value, mapping) for value in raw]


def _map_one_compact_index(value: Any, mapping: Sequence[int]) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return _DANGLING_INDEX_BASE
    if 0 <= value < len(mapping):
        return mapping[value]
    return _DANGLING_INDEX_BASE + value
