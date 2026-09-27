"""
Sorties structurées : demande, extraction, décodage, validation.

Deux chemins selon le fournisseur :

    natif       le provider sait contraindre sa sortie (JSON mode / schema)
    par prompt  on annexe une consigne JSON, puis on décode et valide ici

Dans les deux cas, le décodage et la validation passent par ce module :
c'est le seul endroit où un texte devient `AIResponse.parsed`.

Phase 2 ne définit AUCUN schéma métier. Les schémas de source_map.json,
editorial_plan.json et book.json appartiennent aux phases suivantes ; ici
on ne fournit que le mécanisme.

En cas de JSON invalide, on lève AIStructuredOutputError. Aucune tentative
de « réparation » par un second appel LLM : une sortie cassée doit se voir.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

from app.ai.errors import AIStructuredOutputError

# Longueur maximale d'extrait reproduit dans un message d'erreur.
# Assez pour diagnostiquer, trop court pour déverser du contenu utilisateur.
_EXCERPT_CHARS = 200

_FENCE_PATTERN = re.compile(
    r"^\s*```(?:json|JSON)?\s*\n(?P<body>.*?)\n?\s*```\s*$",
    re.DOTALL,
)


def build_json_instruction(schema: Mapping[str, Any] | None) -> str:
    """
    Consigne annexée au prompt pour les fournisseurs sans mode JSON natif.

    Volontairement courte et impérative : les consignes longues dérivent vers
    du commentaire et produisent du texte autour du JSON.
    """
    lines = [
        "Réponds UNIQUEMENT avec un objet JSON valide.",
        "N'ajoute ni texte d'introduction, ni commentaire, ni bloc de code.",
    ]

    if schema:
        lines.append("Le JSON doit respecter ce schéma :")
        lines.append(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True))

    return "\n".join(lines)


def strip_code_fences(text: str) -> str:
    """Retire un éventuel bloc ```json … ``` autour de la réponse."""
    match = _FENCE_PATTERN.match(text or "")

    if match:
        return match.group("body").strip()

    return (text or "").strip()


def _excerpt(text: str) -> str:
    cleaned = (text or "").strip().replace("\n", " ")

    if len(cleaned) <= _EXCERPT_CHARS:
        return cleaned

    return cleaned[:_EXCERPT_CHARS] + "…"


def parse_json_payload(text: str) -> Any:
    """
    Décode le JSON d'une réponse, en tolérant un encadrement Markdown.

    Lève AIStructuredOutputError avec un extrait tronqué si le décodage échoue.
    """
    candidate = strip_code_fences(text)

    if not candidate:
        error = AIStructuredOutputError(
            "Sortie structurée demandée mais la réponse du modèle est vide."
        )
        error.parse_failure_kind = "empty"
        error.classification = "STRUCTURED_JSON_DECODE"
        raise error

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        error = AIStructuredOutputError(
            f"Réponse JSON invalide ({exc.msg} ligne {exc.lineno} "
            f"colonne {exc.colno}). Début de la réponse : {_excerpt(candidate)}"
        )
        error.parse_failure_kind = "json_decode"
        error.classification = "STRUCTURED_JSON_DECODE"
        error.json_decode_msg = exc.msg
        error.json_decode_lineno = exc.lineno
        error.json_decode_colno = exc.colno
        raise error from exc


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_JSON_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "null": (type(None),),
}


def _minimal_validate(payload: Any, schema: Mapping[str, Any], path: str = "$") -> None:
    """
    Validation structurelle minimale : type, required, properties, items.

    Utilisée lorsque `jsonschema` n'est pas installé. Volontairement partielle
    et documentée comme telle : elle attrape les erreurs grossières de forme,
    pas les contraintes fines (formats, enum, bornes).
    """
    expected = schema.get("type")

    if expected:
        allowed = _JSON_TYPES.get(str(expected))

        if allowed is None:
            return

        # En JSON, True n'est pas un nombre : bool est un sous-type de int en Python.
        if isinstance(payload, bool) and str(expected) in ("number", "integer"):
            error = AIStructuredOutputError(
                f"Champ {path} : booléen reçu, {expected} attendu."
            )
            error.parse_failure_kind = "schema"
            error.classification = "STRUCTURED_SCHEMA_VALIDATION"
            raise error

        if not isinstance(payload, allowed):
            error = AIStructuredOutputError(
                f"Champ {path} : type {type(payload).__name__} reçu, "
                f"{expected} attendu."
            )
            error.parse_failure_kind = "schema"
            error.classification = "STRUCTURED_SCHEMA_VALIDATION"
            raise error

    if isinstance(payload, dict):
        for key in schema.get("required", []) or []:
            if key not in payload:
                error = AIStructuredOutputError(
                    f"Champ obligatoire absent de la réponse : {path}.{key}"
                )
                error.parse_failure_kind = "schema"
                error.classification = "STRUCTURED_SCHEMA_VALIDATION"
                raise error

        properties = schema.get("properties", {}) or {}

        for key, sub_schema in properties.items():
            if key in payload and isinstance(sub_schema, dict):
                _minimal_validate(payload[key], sub_schema, f"{path}.{key}")

    if isinstance(payload, list):
        item_schema = schema.get("items")

        if isinstance(item_schema, dict):
            for index, item in enumerate(payload):
                _minimal_validate(item, item_schema, f"{path}[{index}]")


def validate_payload(payload: Any, schema: Mapping[str, Any] | None) -> None:
    """
    Valide un objet décodé contre un schéma.

    Emploie `jsonschema` s'il est importable, sinon la validation minimale
    ci-dessus. Dans les deux cas l'échec produit une AIStructuredOutputError.
    """
    if not schema:
        return

    try:
        import jsonschema  # type: ignore
    except ImportError:
        _minimal_validate(payload, schema)
        return

    try:
        jsonschema.validate(instance=payload, schema=dict(schema))
    except jsonschema.ValidationError as exc:  # type: ignore[attr-defined]
        location = "$" + "".join(f"[{part!r}]" for part in exc.absolute_path)
        error = AIStructuredOutputError(
            f"La réponse ne respecte pas le schéma en {location} : {exc.message}"
        )
        error.parse_failure_kind = "schema"
        error.classification = "STRUCTURED_SCHEMA_VALIDATION"
        raise error from exc
    except jsonschema.SchemaError as exc:  # type: ignore[attr-defined]
        error = AIStructuredOutputError(
            f"Schéma de sortie structurée invalide : {exc.message}"
        )
        error.parse_failure_kind = "schema"
        error.classification = "STRUCTURED_SCHEMA_VALIDATION"
        raise error from exc


def parse_structured_output(
    text: str,
    schema: Mapping[str, Any] | None = None,
) -> Any:
    """Décode puis valide une réponse structurée. Point d'entrée unique."""
    payload = parse_json_payload(text)
    validate_payload(payload, schema)

    return payload
