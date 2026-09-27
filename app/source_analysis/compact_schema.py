"""
Schéma provider compact du Source Analyzer — DTO de transport.

Distinct du contrat SourceMap canonique (models.py + validator.py) et
distinct de l'ancien schéma de réponse (schema.build_response_schema()).

    canonical_source_map   models.py / validator.py     (métier, inchangé)
    compact DTO            CE MODULE                    (ce que Claude produit)
    prepare_anthropic…     app/ai/providers/_anthropic_schema.py

Le DTO ne demande au modèle QUE ce qu'il doit décider. IDs canoniques,
stats, provenance, signature, provider/model : reconstruits localement.

Les $ref internes ($defs) partagent src_refs et intent : une seule
production pour des structures répétées, sans schéma récursif.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.file_utils import content_hash
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
)

COMPACT_SCHEMA_VERSION = "1.0"

_SRC_PATTERN = r"^SRC[0-9]{6}$"

# Classifications (section 13). Ordre stable pour l'artefact déterministe.
#
# A MODEL_SEMANTIC_REQUIRED      le modèle décide la valeur
# B MODEL_SEMANTIC_COMPACTABLE   le modèle fournit l'info sous forme simple
# C DETERMINISTIC_RECONSTRUCTABLE  le code reconstruit sans décision
# D METADATA_LOCAL               configuration / transcript / pipeline
# E DERIVED_STATS                calculé depuis le résultat normalisé

FIELD_CLASSIFICATION: tuple[dict[str, str], ...] = (
    {
        "field": "schema_version",
        "classification": "METADATA_LOCAL",
        "provider": "absent",
        "canonical": "SOURCE_MAP_SCHEMA_VERSION",
    },
    {
        "field": "transcript_id",
        "classification": "METADATA_LOCAL",
        "provider": "absent",
        "canonical": "transcript.transcript_id",
    },
    {
        "field": "project.name",
        "classification": "METADATA_LOCAL",
        "provider": "absent",
        "canonical": "transcript.project_name",
    },
    {
        "field": "language.primary",
        "classification": "METADATA_LOCAL",
        "provider": "absent",
        "canonical": "transcript.primary_language",
    },
    {
        "field": "analysis.prompt_version",
        "classification": "METADATA_LOCAL",
        "provider": "absent",
        "canonical": "SOURCE_ANALYZER_PROMPT_VERSION",
    },
    {
        "field": "analysis.schema_version",
        "classification": "METADATA_LOCAL",
        "provider": "absent",
        "canonical": "SOURCE_MAP_SCHEMA_VERSION",
    },
    {
        "field": "analysis.provider",
        "classification": "METADATA_LOCAL",
        "provider": "absent",
        "canonical": "AIResponse.provider",
    },
    {
        "field": "analysis.model",
        "classification": "METADATA_LOCAL",
        "provider": "absent",
        "canonical": "AIResponse.model",
    },
    {
        "field": "analysis.strategy",
        "classification": "METADATA_LOCAL",
        "provider": "absent",
        "canonical": "ContextPlan.strategy",
    },
    {
        "field": "analysis.signature",
        "classification": "METADATA_LOCAL",
        "provider": "absent",
        "canonical": "cache.build_signature",
    },
    {
        "field": "stats.*",
        "classification": "DERIVED_STATS",
        "provider": "absent",
        "canonical": "normalizer._build_stats",
    },
    {
        "field": "topics[].topic_id",
        "classification": "DETERMINISTIC_RECONSTRUCTABLE",
        "provider": "absent — index de liste",
        "canonical": "TOP001… selon première apparition SRC",
    },
    {
        "field": "ideas[].idea_id",
        "classification": "DETERMINISTIC_RECONSTRUCTABLE",
        "provider": "absent — index de liste",
        "canonical": "IDEA001… selon première apparition SRC",
    },
    {
        "field": "examples[].example_id",
        "classification": "DETERMINISTIC_RECONSTRUCTABLE",
        "provider": "absent",
        "canonical": "EX001…",
    },
    {
        "field": "references[].reference_id",
        "classification": "DETERMINISTIC_RECONSTRUCTABLE",
        "provider": "absent",
        "canonical": "REF001…",
    },
    {
        "field": "uncertainties[].uncertainty_id",
        "classification": "DETERMINISTIC_RECONSTRUCTABLE",
        "provider": "absent",
        "canonical": "UNC001…",
    },
    {
        "field": "repetitions[].repetition_id",
        "classification": "DETERMINISTIC_RECONSTRUCTABLE",
        "provider": "absent",
        "canonical": "REP001…",
    },
    {
        "field": "source_analysis.main_theme",
        "classification": "MODEL_SEMANTIC_REQUIRED",
        "provider": "source_analysis.main_theme",
        "canonical": "identique",
    },
    {
        "field": "source_analysis.author_intent",
        "classification": "MODEL_SEMANTIC_COMPACTABLE",
        "provider": "$ref #/$defs/intent (summary, confidence, kinds)",
        "canonical": "IntentStatement",
    },
    {
        "field": "source_analysis.target_audience",
        "classification": "MODEL_SEMANTIC_COMPACTABLE",
        "provider": "$ref #/$defs/intent (même forme)",
        "canonical": "IntentStatement",
    },
    {
        "field": "topics[].label",
        "classification": "MODEL_SEMANTIC_REQUIRED",
        "provider": "topics[].label",
        "canonical": "identique",
    },
    {
        "field": "topics[].summary",
        "classification": "MODEL_SEMANTIC_REQUIRED",
        "provider": "topics[].summary",
        "canonical": "identique",
    },
    {
        "field": "topics[].source_refs",
        "classification": "MODEL_SEMANTIC_COMPACTABLE",
        "provider": "$ref #/$defs/src_refs — vrais SRC",
        "canonical": "triés, dédupliqués",
    },
    {
        "field": "ideas[].summary",
        "classification": "MODEL_SEMANTIC_REQUIRED",
        "provider": "ideas[].summary",
        "canonical": "identique",
    },
    {
        "field": "ideas[].kind",
        "classification": "MODEL_SEMANTIC_REQUIRED",
        "provider": "ideas[].kind",
        "canonical": "identique",
    },
    {
        "field": "ideas[].importance",
        "classification": "MODEL_SEMANTIC_REQUIRED",
        "provider": "ideas[].importance",
        "canonical": "identique",
    },
    {
        "field": "ideas[].topic_refs",
        "classification": "MODEL_SEMANTIC_COMPACTABLE",
        "provider": "ideas[].topic_indexes (entiers 0-based)",
        "canonical": "TOP001… via index → ID local → ID canonique",
    },
    {
        "field": "ideas[].relations",
        "classification": "MODEL_SEMANTIC_COMPACTABLE",
        "provider": "relations[] {from, to, relation}",
        "canonical": "rattachées à ideas[].relations avec IDEA…",
    },
    {
        "field": "ideas[].source_refs",
        "classification": "MODEL_SEMANTIC_COMPACTABLE",
        "provider": "$ref #/$defs/src_refs — vrais SRC",
        "canonical": "triés, dédupliqués",
    },
    {
        "field": "examples[].kind",
        "classification": "MODEL_SEMANTIC_REQUIRED",
        "provider": "examples[].kind",
        "canonical": "identique",
    },
    {
        "field": "examples[].summary",
        "classification": "MODEL_SEMANTIC_REQUIRED",
        "provider": "examples[].summary",
        "canonical": "identique",
    },
    {
        "field": "examples[].supports_idea_refs",
        "classification": "MODEL_SEMANTIC_COMPACTABLE",
        "provider": "examples[].idea_indexes",
        "canonical": "IDEA001…",
    },
    {
        "field": "examples[].source_refs",
        "classification": "MODEL_SEMANTIC_COMPACTABLE",
        "provider": "$ref #/$defs/src_refs",
        "canonical": "triés, dédupliqués",
    },
    {
        "field": "references[].kind",
        "classification": "MODEL_SEMANTIC_REQUIRED",
        "provider": "references[].kind",
        "canonical": "identique",
    },
    {
        "field": "references[].raw_reference",
        "classification": "MODEL_SEMANTIC_REQUIRED",
        "provider": "references[].raw_reference",
        "canonical": "identique",
    },
    {
        "field": "references[].normalized_reference",
        "classification": "MODEL_SEMANTIC_REQUIRED",
        "provider": "references[].normalized_reference (chaîne, éventuellement vide)",
        "canonical": "identique",
    },
    {
        "field": "references[].completeness",
        "classification": "MODEL_SEMANTIC_REQUIRED",
        "provider": "references[].completeness",
        "canonical": "identique",
    },
    {
        "field": "references[].source_refs",
        "classification": "MODEL_SEMANTIC_COMPACTABLE",
        "provider": "$ref #/$defs/src_refs",
        "canonical": "triés, dédupliqués",
    },
    {
        "field": "uncertainties[].kind",
        "classification": "MODEL_SEMANTIC_REQUIRED",
        "provider": "uncertainties[].kind",
        "canonical": "identique",
    },
    {
        "field": "uncertainties[].description",
        "classification": "MODEL_SEMANTIC_REQUIRED",
        "provider": "uncertainties[].description",
        "canonical": "identique",
    },
    {
        "field": "uncertainties[].severity",
        "classification": "MODEL_SEMANTIC_REQUIRED",
        "provider": "uncertainties[].severity",
        "canonical": "identique",
    },
    {
        "field": "uncertainties[].source_refs",
        "classification": "MODEL_SEMANTIC_COMPACTABLE",
        "provider": "$ref #/$defs/src_refs",
        "canonical": "triés, dédupliqués",
    },
    {
        "field": "repetitions[].character",
        "classification": "MODEL_SEMANTIC_REQUIRED",
        "provider": "repetitions[].character",
        "canonical": "identique",
    },
    {
        "field": "repetitions[].description",
        "classification": "MODEL_SEMANTIC_REQUIRED",
        "provider": "repetitions[].description",
        "canonical": "identique",
    },
    {
        "field": "repetitions[].idea_refs",
        "classification": "MODEL_SEMANTIC_COMPACTABLE",
        "provider": "repetitions[].idea_indexes",
        "canonical": "IDEA001… (≥ 2)",
    },
    {
        "field": "repetitions[].source_refs",
        "classification": "MODEL_SEMANTIC_COMPACTABLE",
        "provider": "$ref #/$defs/src_refs",
        "canonical": "triés, dédupliqués",
    },
    {
        "field": "author_voice_profile",
        "classification": "MODEL_SEMANTIC_COMPACTABLE",
        "provider": "objet plat, tous les champs requis (listes/chaînes vides autorisées)",
        "canonical": "AuthorVoiceProfile",
    },
)

COMPACT_REQUIRED_FIELDS: tuple[str, ...] = (
    "source_analysis",
    "topics",
    "ideas",
    "relations",
    "examples",
    "references",
    "uncertainties",
    "repetitions",
    "author_voice_profile",
)

COMPACT_ID_FIELDS_ABSENT: tuple[str, ...] = (
    "topic_id",
    "idea_id",
    "example_id",
    "reference_id",
    "uncertainty_id",
    "repetition_id",
)

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


def _src_refs_def() -> dict:
    return {
        "type": "array",
        "minItems": 1,
        "items": {"type": "string", "pattern": _SRC_PATTERN},
    }


def _intent_def() -> dict:
    return {
        "type": "object",
        "required": ["summary", "confidence", "kinds"],
        "properties": {
            "summary": {"type": "string"},
            "confidence": {"type": "string", "enum": list(CONFIDENCE_LEVELS)},
            "kinds": {"type": "array", "items": {"type": "string"}},
        },
    }


def _string_list_def() -> dict:
    return {"type": "array", "items": {"type": "string"}}


def build_compact_response_schema() -> dict:
    """
    Schéma JSON du DTO provider. Reconstruit à chaque appel : les vocabulaires
    viennent de models.py.
    """
    return {
        "$defs": {
            "src_refs": _src_refs_def(),
            "intent": _intent_def(),
            "string_list": _string_list_def(),
        },
        "type": "object",
        "required": list(COMPACT_REQUIRED_FIELDS),
        "properties": {
            "source_analysis": {
                "type": "object",
                "required": ["main_theme", "author_intent", "target_audience"],
                "properties": {
                    "main_theme": {"type": "string"},
                    "author_intent": {"$ref": "#/$defs/intent"},
                    "target_audience": {"$ref": "#/$defs/intent"},
                },
            },
            "topics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["label", "summary", "source_refs"],
                    "properties": {
                        "label": {"type": "string"},
                        "summary": {"type": "string"},
                        "source_refs": {"$ref": "#/$defs/src_refs"},
                    },
                },
            },
            "ideas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "summary",
                        "kind",
                        "importance",
                        "topic_indexes",
                        "source_refs",
                    ],
                    "properties": {
                        "summary": {"type": "string"},
                        "kind": {"type": "string", "enum": list(IDEA_KINDS)},
                        "importance": {
                            "type": "string",
                            "enum": list(IMPORTANCE_LEVELS),
                        },
                        "topic_indexes": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "source_refs": {"$ref": "#/$defs/src_refs"},
                    },
                },
            },
            "relations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["from", "to", "relation"],
                    "properties": {
                        "from": {"type": "integer"},
                        "to": {"type": "integer"},
                        "relation": {
                            "type": "string",
                            "enum": list(RELATION_KINDS),
                        },
                    },
                },
            },
            "examples": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kind", "summary", "idea_indexes", "source_refs"],
                    "properties": {
                        "kind": {"type": "string", "enum": list(EXAMPLE_KINDS)},
                        "summary": {"type": "string"},
                        "idea_indexes": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "source_refs": {"$ref": "#/$defs/src_refs"},
                    },
                },
            },
            "references": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "kind",
                        "raw_reference",
                        "normalized_reference",
                        "completeness",
                        "source_refs",
                    ],
                    "properties": {
                        "kind": {"type": "string", "enum": list(REFERENCE_KINDS)},
                        "raw_reference": {"type": "string"},
                        "normalized_reference": {"type": "string"},
                        "completeness": {
                            "type": "string",
                            "enum": list(REFERENCE_COMPLETENESS),
                        },
                        "source_refs": {"$ref": "#/$defs/src_refs"},
                    },
                },
            },
            "uncertainties": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kind", "description", "severity", "source_refs"],
                    "properties": {
                        "kind": {"type": "string", "enum": list(UNCERTAINTY_KINDS)},
                        "description": {"type": "string"},
                        "severity": {
                            "type": "string",
                            "enum": list(SEVERITY_LEVELS),
                        },
                        "source_refs": {"$ref": "#/$defs/src_refs"},
                    },
                },
            },
            "repetitions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "character",
                        "description",
                        "idea_indexes",
                        "source_refs",
                    ],
                    "properties": {
                        "character": {
                            "type": "string",
                            "enum": list(REPETITION_CHARACTERS),
                        },
                        "description": {"type": "string"},
                        "idea_indexes": {
                            "type": "array",
                            "minItems": 2,
                            "items": {"type": "integer"},
                        },
                        "source_refs": {"$ref": "#/$defs/src_refs"},
                    },
                },
            },
            "author_voice_profile": {
                "type": "object",
                "required": [
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
                ],
                "properties": {
                    "tone": {"$ref": "#/$defs/string_list"},
                    "register": {"type": "string"},
                    "sentence_style": {"type": "string"},
                    "rhetorical_patterns": {"$ref": "#/$defs/string_list"},
                    "use_of_questions": {"type": "string"},
                    "use_of_repetition": {"type": "string"},
                    "use_of_examples": {"type": "string"},
                    "direct_address": {"type": "string"},
                    "teaching_style": {"type": "string"},
                    "distinctive_traits": {"$ref": "#/$defs/string_list"},
                },
            },
        },
    }


def compact_schema_fingerprint(schema: Mapping[str, Any] | None = None) -> str:
    """Empreinte stable du contrat provider compact, pour la signature."""
    payload = build_compact_response_schema() if schema is None else schema
    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))
