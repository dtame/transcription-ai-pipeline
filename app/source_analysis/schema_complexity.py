"""
Métriques déterministes de complexité d'un JSON Schema.

Ces chiffres servent à comparer deux schémas (ancien provider vs DTO compact)
et à détecter une régression de compaction. Ils ne prétendent PAS connaître
la formule interne utilisée par Anthropic pour compiler une grammaire, ni
prédire l'acceptation serveur.

    analyze_schema_complexity(schema)  →  dict de compteurs, ordre stable
"""

from __future__ import annotations

import json
from typing import Any, Mapping

# Mots-clés de contrainte JSON Schema inventoriés. Ce n'est pas une liste
# « officielle Anthropic » : c'est un dénombrement local comparable.
_CONSTRAINT_KEYWORDS = (
    "const",
    "enum",
    "exclusiveMaximum",
    "exclusiveMinimum",
    "format",
    "maxItems",
    "maxLength",
    "maxProperties",
    "maximum",
    "minItems",
    "minLength",
    "minProperties",
    "minimum",
    "multipleOf",
    "pattern",
    "uniqueItems",
)

_COMPOSITION_KEYWORDS = ("anyOf", "oneOf", "allOf")
_DEFINITION_KEYWORDS = ("$defs", "definitions")
_ID_FIELD_SUFFIXES = ("_id",)


def analyze_schema_complexity(schema: Mapping[str, Any] | None) -> dict[str, int]:
    """
    Parcourt le schéma tel qu'écrit (les $ref ne sont pas expansés) et
    retourne un dictionnaire d'entiers, clés triées pour le JSON déterministe.
    """
    payload = dict(schema) if isinstance(schema, Mapping) else {}
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    metrics = {
        "additional_properties_keywords": 0,
        "all_of": 0,
        "any_of": 0,
        "array_nodes": 0,
        "arrays_of_objects": 0,
        "constraints": 0,
        "distinct_object_shapes": 0,
        "enum_count": 0,
        "id_pattern_like_structures": 0,
        "maximum_nesting_depth": 0,
        "nested_arrays": 0,
        "object_nodes": 0,
        "one_of": 0,
        "optional_properties": 0,
        "ref_count": 0,
        "relation_related_structures": 0,
        "required_properties": 0,
        "serialized_json_bytes": len(serialized.encode("utf-8")),
        "source_refs_occurrences": 0,
        "total_enum_values": 0,
        "total_properties": 0,
        "total_schema_nodes": 0,
        "union_count": 0,
    }
    object_shapes: set[tuple[str, ...]] = set()

    def _walk(node: Any, depth: int) -> None:
        if isinstance(node, list):
            metrics["total_schema_nodes"] += 1
            if depth > metrics["maximum_nesting_depth"]:
                metrics["maximum_nesting_depth"] = depth
            for item in node:
                _walk(item, depth + 1)
            return

        if not isinstance(node, dict):
            return

        metrics["total_schema_nodes"] += 1
        if depth > metrics["maximum_nesting_depth"]:
            metrics["maximum_nesting_depth"] = depth

        node_type = node.get("type")
        if node_type == "object":
            metrics["object_nodes"] += 1
        elif node_type == "array":
            metrics["array_nodes"] += 1

        if "additionalProperties" in node:
            metrics["additional_properties_keywords"] += 1

        if "$ref" in node:
            metrics["ref_count"] += 1

        for keyword in _CONSTRAINT_KEYWORDS:
            if keyword in node:
                metrics["constraints"] += 1

        enum_values = node.get("enum")
        if isinstance(enum_values, list):
            metrics["enum_count"] += 1
            metrics["total_enum_values"] += len(enum_values)

        for keyword in _COMPOSITION_KEYWORDS:
            branches = node.get(keyword)
            if isinstance(branches, list):
                metrics["union_count"] += 1
                if keyword == "anyOf":
                    metrics["any_of"] += 1
                elif keyword == "oneOf":
                    metrics["one_of"] += 1
                elif keyword == "allOf":
                    metrics["all_of"] += 1

        pattern = node.get("pattern")
        if isinstance(pattern, str) and any(
            token in pattern for token in ("TOP", "IDEA", "EX", "REF", "UNC", "REP")
        ):
            metrics["id_pattern_like_structures"] += 1

        properties = node.get("properties")
        required = node.get("required")
        required_names = (
            {str(name) for name in required} if isinstance(required, list) else set()
        )

        if isinstance(properties, dict):
            metrics["total_properties"] += len(properties)
            metrics["required_properties"] += len(required_names & set(properties))
            metrics["optional_properties"] += len(set(properties) - required_names)
            if node_type == "object":
                object_shapes.add(tuple(sorted(str(name) for name in properties)))

            for name, sub_schema in properties.items():
                lowered = str(name).lower()
                if lowered == "source_refs":
                    metrics["source_refs_occurrences"] += 1
                if any(lowered.endswith(suffix) for suffix in _ID_FIELD_SUFFIXES):
                    metrics["id_pattern_like_structures"] += 1
                if lowered in {"relation", "relations", "from", "to", "to_idea"}:
                    metrics["relation_related_structures"] += 1
                _walk(sub_schema, depth + 1)

        items = node.get("items")
        if isinstance(items, dict):
            item_type = items.get("type")
            if node_type == "array" and (
                item_type == "object" or isinstance(items.get("properties"), dict)
            ):
                metrics["arrays_of_objects"] += 1
            if node_type == "array" and item_type == "array":
                metrics["nested_arrays"] += 1
            _walk(items, depth + 1)
        elif isinstance(items, list):
            for sub_schema in items:
                _walk(sub_schema, depth + 1)

        for keyword in _COMPOSITION_KEYWORDS:
            branches = node.get(keyword)
            if isinstance(branches, list):
                for sub_schema in branches:
                    _walk(sub_schema, depth + 1)

        for keyword in _DEFINITION_KEYWORDS:
            definitions = node.get(keyword)
            if isinstance(definitions, dict):
                for sub_schema in definitions.values():
                    _walk(sub_schema, depth + 1)

    _walk(payload, 1)
    metrics["distinct_object_shapes"] = len(object_shapes)
    return {key: metrics[key] for key in sorted(metrics)}


def reduction_percents(
    old: Mapping[str, int],
    new: Mapping[str, int],
) -> dict[str, float]:
    """
    Réduction (old → new) en pourcent, arrondie à 2 décimales.

    Une valeur positive signifie que le nouveau schéma est plus petit.
    Aucun seuil n'est une limite officielle Anthropic.
    """
    percents: dict[str, float] = {}
    keys = sorted(set(old) | set(new))

    for key in keys:
        before = int(old.get(key, 0) or 0)
        after = int(new.get(key, 0) or 0)
        if before == 0:
            percents[key] = 0.0 if after == 0 else -100.0
        else:
            percents[key] = round(100.0 * (before - after) / before, 2)

    return percents
