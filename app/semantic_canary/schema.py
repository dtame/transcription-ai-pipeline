"""
Schéma JSON de la réponse du canary (§18).

Passé à `AIRequest.response_schema` : le décodage et la validation
structurelle générique sont donc faits par app/ai/structured.py, exactement
comme le Source Analyzer (voir app/source_analysis/schema.py). La
validation SPÉCIFIQUE au canary (20 résultats exacts, aucun block_id
inconnu/dupliqué/manquant, cohérence classification/matched_direction) vit
dans validator.py — ce schéma ne peut pas l'exprimer complètement (un
schéma JSON ne sait pas dire « exactement ces 20 identifiants »).

Le schéma canonique ici reste strict par construction (§10 du cahier des
charges : « le schéma canonique local reste plus strict que le schéma
provider si nécessaire ») : la frontière Anthropic (additionalProperties,
minLength, minItems) est gérée par prepare_anthropic_json_schema(), jamais
recréée ici (§11).
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.file_utils import content_hash
from app.semantic_canary.models import CLASSIFICATIONS, MATCHED_DIRECTIONS, SCHEMA_VERSION

RESPONSE_SCHEMA_VERSION = SCHEMA_VERSION


def build_response_schema() -> dict:
    """Schéma de la réponse attendue du canary — reconstruit à chaque appel."""
    return {
        "type": "object",
        "required": ["schema_version", "results"],
        "properties": {
            "schema_version": {
                "type": "string",
                "minLength": 1,
                "description": "Doit valoir exactement la valeur demandée dans le prompt.",
            },
            "results": {
                "type": "array",
                "minItems": 1,
                "description": (
                    "Une entrée par bloc soumis, dans l'ordre ou le désordre — "
                    "chaque block_id doit apparaître exactement une fois."
                ),
                "items": {
                    "type": "object",
                    "required": [
                        "block_id",
                        "classification",
                        "matched_direction",
                        "confidence",
                        "reason",
                    ],
                    "properties": {
                        "block_id": {
                            "type": "string",
                            "minLength": 1,
                            "description": "Doit correspondre exactement à un block_id soumis.",
                        },
                        "classification": {
                            "type": "string",
                            "enum": list(CLASSIFICATIONS),
                        },
                        "matched_direction": {
                            "type": "string",
                            "enum": list(MATCHED_DIRECTIONS),
                        },
                        "confidence": {
                            "type": "number",
                            "description": (
                                "Nombre entre 0 et 1 inclus. Les contraintes "
                                "numériques (minimum/maximum) NE sont PAS "
                                "exprimées dans ce schéma : Anthropic "
                                "Structured Outputs ne les supporte pas (voir "
                                "app/ai/providers/_anthropic_schema.py, "
                                "_UNSUPPORTED_KEYWORDS). La borne [0, 1] est "
                                "vérifiée localement par validator.py, jamais "
                                "par le schéma JSON."
                            ),
                        },
                        "reason": {
                            "type": "string",
                            "minLength": 1,
                            "description": "Courte justification factuelle, fondée sur les textes fournis.",
                        },
                    },
                },
            },
        },
    }


def schema_fingerprint(schema: Mapping[str, Any] | None = None) -> str:
    """Empreinte stable du schéma — pour la provenance de l'artefact publié."""
    payload = build_response_schema() if schema is None else schema

    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))
