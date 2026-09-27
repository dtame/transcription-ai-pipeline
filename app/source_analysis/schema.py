"""
Schéma JSON de la réponse du Source Analyzer.

C'est ce qui est passé à `AIRequest.response_schema` : le décodage et la
validation structurelle sont donc faits par la couche Phase 2
(app/ai/structured.py), et le service métier récupère `AIResponse.parsed`. Il
n'y a aucun json.loads() dans analyzer.py — demander du JSON puis le parser à
la main dupliquerait une responsabilité qui existe déjà.

Ce schéma décrit la RÉPONSE DU MODÈLE, pas le fichier publié. Le modèle ne
fournit pas :

    schema_version      décidé par le code
    transcript_id       lu dans le transcript
    project / language  lus dans le transcript
    stats               dérivées par le code
    analysis            provenance calculée par le code

et ses identifiants sont des clés de correspondance jetables, renumérotées par
le normalizer. Rien de ce qui doit être déterministe n'est laissé au modèle.

`additionalProperties` reste permissif volontairement : un champ `chapters`
renvoyé par le modèle doit produire une erreur de FRONTIÈRE ARCHITECTURALE
explicite (SourceMapEditorialLeakError, voir validator.py), pas un message de
schéma générique dans lequel le vrai problème se perdrait.

Règle de « required » sur les identifiants locaux (Phase 3B.2) : un
`*_id` n'est exigé PAR LE SCHÉMA que s'il est la CIBLE d'un champ de
référence ailleurs dans CETTE MÊME réponse — c'est-à-dire s'il est
nécessaire pour reconstruire sans ambiguïté un lien entre deux éléments.

    topic_id         requis — cible de ideas[].topic_refs
    idea_id          requis — cible de ideas[].relations[].to_idea,
                     examples[].supports_idea_refs, repetitions[].idea_refs
    example_id       optionnel — jamais la cible d'aucune référence
    reference_id     optionnel — jamais la cible d'aucune référence
    uncertainty_id   optionnel — jamais la cible d'aucune référence
    repetition_id    optionnel — jamais la cible d'aucune référence

Un identifiant optionnel absent (ou dupliqué par accident) de la réponse
brute n'empêche donc PAS de reconstruire le Source Map : le normalizer lui
substitue une clé de correspondance interne positionnelle avant de
renumeroter l'élément normalement (voir app/source_analysis/normalizer.py,
paramètre `id_required`). Rendre ce champ obligatoire au niveau du contrat
provider rendrait un appel payant fragile pour une donnée dont le programme
est déjà l'autorité déterministe — c'est exactement l'incident réel qui a
fait échouer l'appel Anthropic de la validation `pastoral_retreat_v2` sur
`uncertainty_id`.

En aval, ce relâchement ne change RIEN au contrat final : `ensure_valid_source_map`
(validator.py) exige toujours TOPxxx/IDEAxxx/EXxxx/REFxxx/UNCxxx/REPxxx sur
CHAQUE élément du fichier publié. La souplesse ne concerne que la frontière
réponse-provider → normalizer, jamais le fichier source_map.json final.
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

# Un source_ref est un identifiant de segment du transcript V2. Le motif est
# imposé au modèle pour qu'une faute de frappe grossière soit rejetée tout de
# suite ; l'EXISTENCE réelle du segment est vérifiée par le validateur, qui
# seul connaît le transcript.
_SRC_PATTERN = r"^SRC[0-9]{6}$"

_SOURCE_REFS = {
    "type": "array",
    "minItems": 1,
    "items": {"type": "string", "pattern": _SRC_PATTERN},
    "description": (
        "Identifiants SRC du transcript qui portent cet élément. Au moins un. "
        "Ne jamais inventer un SRC absent du transcript fourni."
    ),
}

_LOCAL_ID = {
    "type": "string",
    "minLength": 1,
    "description": (
        "Identifiant local, libre mais UNIQUE dans sa collection. Il sert "
        "uniquement à référencer cet élément ailleurs dans la réponse ; il sera "
        "renuméroté par le programme."
    ),
}

# Même forme que _LOCAL_ID, mais jamais listé dans « required » : cet
# identifiant n'est la cible d'aucun champ de référence de cette réponse (voir
# la note de « required » en tête de module). Le proposer reste possible — un
# modèle peut s'en servir pour son propre raisonnement interne — mais son
# absence ne rend jamais la réponse invalide : le normalizer sait reconstruire
# un élément qui n'est référencé par rien d'autre.
_OPTIONAL_LOCAL_ID = {
    "type": "string",
    "minLength": 1,
    "description": (
        "Identifiant local facultatif. Rien dans cette réponse n'y fait "
        "référence : le programme numérotera cet élément lui-même. Fournis-le "
        "si cela t'aide à rester cohérent, mais son absence n'est pas une "
        "erreur."
    ),
}

_STRING_LIST = {
    "type": "array",
    "items": {"type": "string", "minLength": 1},
}


def _intent_statement(description: str) -> dict:
    return {
        "type": "object",
        "required": ["summary", "confidence"],
        "properties": {
            "summary": {
                "type": "string",
                "minLength": 1,
                "description": description,
            },
            "confidence": {
                "type": "string",
                "enum": list(CONFIDENCE_LEVELS),
                "description": (
                    "Niveau de certitude fondé sur ce que la source DIT. "
                    "« low » si c'est ambigu : l'incertitude se déclare, "
                    "elle ne se comble pas."
                ),
            },
            "kinds": {
                **_STRING_LIST,
                "description": "Étiquettes courtes, facultatives (l'élément peut être composite).",
            },
        },
    }


def build_response_schema() -> dict:
    """
    Schéma de la réponse attendue du Source Analyzer.

    Reconstruit à chaque appel plutôt que figé dans une constante de module :
    les vocabulaires viennent de models.py, et un schéma dérivé ne doit pas
    pouvoir prendre du retard sur sa source.
    """
    return {
        "type": "object",
        "required": [
            "source_analysis",
            "topics",
            "ideas",
            "examples",
            "references",
            "uncertainties",
            "repetitions",
            "author_voice_profile",
        ],
        "properties": {
            "source_analysis": {
                "type": "object",
                "required": ["main_theme", "author_intent", "target_audience"],
                "properties": {
                    "main_theme": {
                        "type": "string",
                        "minLength": 1,
                        "description": (
                            "Sujet dominant de la source, formulé comme une "
                            "DESCRIPTION. Pas un titre, pas un slogan, pas une "
                            "promesse. Exemple attendu : « Le rôle de la foi dans "
                            "la manière de traverser les épreuves »."
                        ),
                    },
                    "author_intent": _intent_statement(
                        "Intention APPARENTE de l'auteur d'après son discours "
                        "(enseigner, expliquer, témoigner, encourager, former, "
                        "argumenter…). Aucune intention cachée, aucun diagnostic."
                    ),
                    "target_audience": _intent_statement(
                        "Audience raisonnablement inférable du discours lui-même. "
                        "Ne pas inventer de tranche d'âge, de situation "
                        "socio-économique ou de profil absent de la source."
                    ),
                },
            },
            "topics": {
                "type": "array",
                "description": (
                    "Domaines thématiques récurrents ou substantiels. Un topic "
                    "n'est PAS un chapitre et ne porte aucun ordre éditorial."
                ),
                "items": {
                    "type": "object",
                    "required": ["topic_id", "label", "summary", "source_refs"],
                    "properties": {
                        "topic_id": _LOCAL_ID,
                        "label": {"type": "string", "minLength": 1},
                        "summary": {"type": "string", "minLength": 1},
                        "source_refs": _SOURCE_REFS,
                    },
                },
            },
            "ideas": {
                "type": "array",
                "description": (
                    "Cœur du Source Map : les unités de sens substantielles "
                    "réellement exprimées par l'auteur."
                ),
                "items": {
                    "type": "object",
                    "required": [
                        "idea_id",
                        "summary",
                        "kind",
                        "importance",
                        "source_refs",
                    ],
                    "properties": {
                        "idea_id": _LOCAL_ID,
                        "summary": {
                            "type": "string",
                            "minLength": 1,
                            "description": (
                                "Reformulation fidèle de ce que l'auteur dit. "
                                "Ne pas compléter sa pensée, ne pas ajouter "
                                "d'argument, ne pas corriger."
                            ),
                        },
                        "kind": {"type": "string", "enum": list(IDEA_KINDS)},
                        "importance": {
                            "type": "string",
                            "enum": list(IMPORTANCE_LEVELS),
                            "description": (
                                "Poids de l'idée DANS LA SOURCE : temps consacré, "
                                "reprises, mise en évidence par l'orateur, rôle "
                                "dans le raisonnement. Pas l'intérêt que tu y "
                                "trouves."
                            ),
                        },
                        "topic_refs": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1},
                            "description": "topic_id déclarés dans « topics ».",
                        },
                        "relations": {
                            "type": "array",
                            "description": (
                                "Liens vers d'autres idées de cette réponse. "
                                "Rester sobre : seules les relations réellement "
                                "portées par le discours."
                            ),
                            "items": {
                                "type": "object",
                                "required": ["relation", "to_idea"],
                                "properties": {
                                    "relation": {
                                        "type": "string",
                                        "enum": list(RELATION_KINDS),
                                    },
                                    "to_idea": {"type": "string", "minLength": 1},
                                },
                            },
                        },
                        "source_refs": _SOURCE_REFS,
                    },
                },
            },
            "examples": {
                "type": "array",
                "description": (
                    "Exemples, illustrations, analogies, anecdotes, témoignages, "
                    "cas pratiques. Un exemple SERT une idée, il n'en est pas une."
                ),
                "items": {
                    "type": "object",
                    "required": ["kind", "summary", "source_refs"],
                    "properties": {
                        "example_id": _OPTIONAL_LOCAL_ID,
                        "kind": {"type": "string", "enum": list(EXAMPLE_KINDS)},
                        "summary": {"type": "string", "minLength": 1},
                        "supports_idea_refs": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1},
                            "description": "idea_id déclarés dans « ideas ».",
                        },
                        "source_refs": _SOURCE_REFS,
                    },
                },
            },
            "references": {
                "type": "array",
                "description": (
                    "Références EXPLICITEMENT présentes dans la source. Ne jamais "
                    "compléter une référence vague avec tes connaissances : si "
                    "l'auteur dit « Paul dit quelque part », la référence reste "
                    "vague et mérite une incertitude."
                ),
                "items": {
                    "type": "object",
                    "required": [
                        "kind",
                        "raw_reference",
                        "completeness",
                        "source_refs",
                    ],
                    "properties": {
                        "reference_id": _OPTIONAL_LOCAL_ID,
                        "kind": {"type": "string", "enum": list(REFERENCE_KINDS)},
                        "raw_reference": {
                            "type": "string",
                            "minLength": 1,
                            "description": "Ce que l'auteur a dit, tel quel.",
                        },
                        "normalized_reference": {
                            "type": "string",
                            "description": (
                                "Mise en forme de CE QUI A ÉTÉ DIT uniquement. "
                                "Laisser vide si la source ne permet pas de "
                                "normaliser sans ajouter d'information."
                            ),
                        },
                        "completeness": {
                            "type": "string",
                            "enum": list(REFERENCE_COMPLETENESS),
                        },
                        "source_refs": _SOURCE_REFS,
                    },
                },
            },
            "uncertainties": {
                "type": "array",
                "description": (
                    "Zones à signaler SANS les résoudre : transcription ambiguë, "
                    "mot douteux, référence incomplète, attribution incertaine, "
                    "pensée interrompue, contradiction apparente."
                ),
                "items": {
                    "type": "object",
                    "required": [
                        "kind",
                        "description",
                        "severity",
                        "source_refs",
                    ],
                    "properties": {
                        "uncertainty_id": _OPTIONAL_LOCAL_ID,
                        "kind": {"type": "string", "enum": list(UNCERTAINTY_KINDS)},
                        "description": {"type": "string", "minLength": 1},
                        "severity": {"type": "string", "enum": list(SEVERITY_LEVELS)},
                        "source_refs": _SOURCE_REFS,
                    },
                },
            },
            "repetitions": {
                "type": "array",
                "description": (
                    "Reprises sémantiques. Deux passages proches ne sont pas "
                    "forcément des doublons : affirmation, puis développement, "
                    "puis application peuvent être une progression voulue. "
                    "Qualifier le caractère de la reprise plutôt que de la "
                    "déclarer « duplicate »."
                ),
                "items": {
                    "type": "object",
                    "required": [
                        "character",
                        "description",
                        "idea_refs",
                        "source_refs",
                    ],
                    "properties": {
                        "repetition_id": _OPTIONAL_LOCAL_ID,
                        "character": {
                            "type": "string",
                            "enum": list(REPETITION_CHARACTERS),
                        },
                        "description": {"type": "string", "minLength": 1},
                        "idea_refs": {
                            "type": "array",
                            "minItems": 2,
                            "items": {"type": "string", "minLength": 1},
                            "description": (
                                "Au moins deux idea_id : une reprise relie des "
                                "passages, elle n'existe pas seule."
                            ),
                        },
                        "source_refs": _SOURCE_REFS,
                    },
                },
            },
            "author_voice_profile": {
                "type": "object",
                "description": (
                    "DESCRIPTION des caractéristiques orales et textuelles "
                    "observables. Aucun diagnostic psychologique, aucune consigne "
                    "de réécriture : ce n'est pas encore un guide de style."
                ),
                "properties": {
                    "tone": _STRING_LIST,
                    "register": {"type": "string"},
                    "sentence_style": {"type": "string"},
                    "rhetorical_patterns": _STRING_LIST,
                    "use_of_questions": {"type": "string"},
                    "use_of_repetition": {"type": "string"},
                    "use_of_examples": {"type": "string"},
                    "direct_address": {"type": "string"},
                    "teaching_style": {"type": "string"},
                    "distinctive_traits": _STRING_LIST,
                },
            },
        },
    }


def schema_fingerprint(schema: Mapping[str, Any] | None = None) -> str:
    """
    Empreinte stable du schéma de réponse, pour la signature de cache.

    Modifier la FORME attendue sans toucher à SOURCE_MAP_SCHEMA_VERSION change
    malgré tout cette empreinte : le cache s'invalide donc même en cas d'oubli
    de bump de version. C'est exactement la faiblesse relevée par l'audit V1,
    où une signature pouvait survivre à un changement de code.
    """
    payload = build_response_schema() if schema is None else schema

    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))
