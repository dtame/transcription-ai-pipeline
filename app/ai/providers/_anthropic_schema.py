"""
Adaptateur de schéma provider — frontière Anthropic Structured Outputs.

Phase 3B.3 a démontré que le schéma du Source Analyzer part RÉELLEMENT dans
la requête HTTP (voir anthropic_engine.py), mais Anthropic exige que CHAQUE
noeud `"type": "object"` porte `"additionalProperties": false` (voir la
documentation Anthropic Structured Outputs, section « JSON Schema
limitations » : « required and additionalProperties (must be set to false
for objects) »). Notre schéma canonique (app/source_analysis/schema.py)
reste volontairement permissif : `additionalProperties` n'y vaut jamais
`false`, précisément pour qu'un champ éditorial comme `chapters` produise une
erreur de FRONTIÈRE explicite (SourceMapEditorialLeakError, voir
app/source_analysis/validator.py) plutôt qu'un message de schéma générique.

Ce module ne touche donc JAMAIS au schéma canonique. Il construit, à la
demande, une COPIE dédiée à la frontière Anthropic :

    canonical (build_response_schema())
        ↓  prepare_anthropic_json_schema()
        ↓      (deep copy, fermeture, puis retrait des contraintes
        ↓       non supportées)
    provider (envoyé dans output_config.format.schema)

Phase 3B.3.1 a fermé les objets (`additionalProperties: false`). Phase
3B.3.2 ajoute deux retraits, TOUJOURS sur la copie provider, JAMAIS sur le
canonique :

    minLength   Anthropic liste explicitement les contraintes de longueur
                de chaîne (`minLength`/`maxLength`) comme NON supportées.
                Retiré partout où il apparaît dans la copie provider. La
                valeur n'est jamais transformée ni remplacée par une
                approximation (pas de `pattern` inventé, pas de description
                réécrite) : elle est simplement absente du contrat provider,
                strictement plus PERMISSIF que le canonique — jamais
                l'inverse. La validation locale (app/ai/structured.py,
                appelée par BaseAIEngine.generate() contre le schéma
                CANONIQUE, jamais contre cette copie) reste seule
                responsable de rejeter une chaîne trop courte.

    minItems    Anthropic ne supporte `minItems` que pour les valeurs 0 ou
                1 (documentation Structured Outputs, « Array constraints »).
                Règle explicite retenue ici :

                    si minItems figure sur un noeud ET que sa valeur n'est
                    pas dans {0, 1} : retirer minItems de la copie provider.

                Un `minItems` de 0 ou 1 — supporté et potentiellement utile
                — n'est PAS retiré : seule une valeur hors sous-ensemble
                supporté (ex. `repetitions[].idea_refs.minItems == 2`) l'est.
                Là encore, aucune valeur de repli n'est inventée : la copie
                provider devient simplement plus permissive sur ce point, et
                la validation locale contre le schéma canonique reste seule
                responsable de rejeter une liste trop courte.

Ni l'un ni l'autre retrait ne touche `required` / `properties` / `enum` /
`description` / au schéma canonique lui-même : conformité provider et
conformité applicative restent deux vérifications séparées (défense en
profondeur), exactement comme pour `additionalProperties` en 3B.3.1.

Stratégie Anthropic « strip + append to description » délibérément NON
retenue ici (voir le rapport Phase 3B.3.2, section 6) : injecter la
contrainte perdue dans `description` reviendrait à faire porter par le
prompt une garantie que seule la validation locale peut réellement tenir,
pour un bénéfice incertain (un modèle peut ignorer une description) et une
sémantique nouvelle non testée. Un simple retrait, redondant avec la
validation locale déjà systématique, suffit et reste plus simple à auditer.

`audit_unsupported_features()` est un outil de diagnostic pur : il ne
corrige rien, il inventorie les fonctionnalités JSON Schema que la
documentation Anthropic liste explicitement comme NON supportées (schéma
récursif, `$ref` externe, contraintes numériques, contraintes de longueur de
chaîne, `maxItems`, `minItems` hors {0, 1}, `additionalProperties` différent
de `false`). Appliqué au schéma PROVIDER (déjà transformé), il doit
désormais rapporter zéro incompatibilité connue — voir le rapport
Phase 3B.3.2 pour l'audit complet.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

# Clés de composition/imbrication couvertes par la fermeture récursive et
# par l'audit. `oneOf` est couvert par prudence (couverture minimale demandée
# par le protocole Phase 3B.3.1) même si le schéma canonique actuel n'utilise
# aucune de ces trois clés.
_COMPOSITION_KEYWORDS = ("anyOf", "oneOf", "allOf")
_DEFINITION_KEYWORDS = ("$defs", "definitions")

# Contraintes que la documentation Anthropic liste comme NON supportées et
# qui n'ont pas de traitement dédié par une règle de retrait ciblée
# (contrairement à minLength et minItems, retirés par _transform_node) :
# leur seule présence dans le schéma PROVIDER est une incompatibilité.
_UNSUPPORTED_KEYWORDS = ("minimum", "maximum", "multipleOf", "minLength", "maxLength", "maxItems")

# minItems : seules ces valeurs sont supportées par le sous-ensemble
# Anthropic Structured Outputs documenté (section 5 du protocole 3B.3.2).
# Toute autre valeur (ex. 2) est retirée de la copie provider — jamais du
# canonique, et jamais remplacée par une valeur de repli.
_SUPPORTED_MIN_ITEMS = (0, 1)

# Contraintes retirées inconditionnellement de la copie provider : Anthropic
# les liste comme NON supportées et notre schéma canonique n'a besoin
# d'aucun équivalent provider (pas d'annotation de description, voir le
# module docstring, section « strip + append to description »).
_STRIPPED_KEYWORDS = ("minLength",)


def prepare_anthropic_json_schema(schema: Mapping[str, Any]) -> dict:
    """
    Copie du schéma canonique, adaptée pour Anthropic Structured Outputs.

    Ne mute jamais `schema` : deep-copy d'abord (le résultat ne partage
    aucun conteneur mutable avec l'original), transformation ensuite :
    fermeture des objets (`additionalProperties: false`, Phase 3B.3.1),
    puis retrait de `minLength` et des `minItems` hors {0, 1} (Phase
    3B.3.2). Voir le docstring de ce module pour la justification complète.
    """
    prepared = deepcopy(dict(schema))
    _transform_node(prepared)
    return prepared


def _transform_node(node: Any) -> None:
    """
    Parcours récursif in-place, unique walker de la transformation
    provider (section 7 du protocole 3B.3.2 : centraliser plutôt que
    dupliquer un second parcours indépendant). Pour chaque noeud dict :

        - ajoute `additionalProperties: false` si `"type": "object"` ;
        - retire `minLength` s'il est présent ;
        - retire `minItems` si sa valeur n'est pas dans {0, 1}.

    Couvre au minimum, comme demandé par le protocole : properties, items,
    anyOf, oneOf, allOf, $defs, definitions.
    """
    if isinstance(node, dict):
        if node.get("type") == "object":
            node["additionalProperties"] = False

        for keyword in _STRIPPED_KEYWORDS:
            node.pop(keyword, None)

        # Règle explicite (section 5 du protocole 3B.3.2) : un minItems
        # présent est retiré de la copie provider SEULEMENT si sa valeur
        # est hors du sous-ensemble supporté {0, 1}. Un minItems absent, ou
        # déjà dans {0, 1}, n'est jamais touché.
        if "minItems" in node and node["minItems"] not in _SUPPORTED_MIN_ITEMS:
            node.pop("minItems")

        properties = node.get("properties")
        if isinstance(properties, dict):
            for sub_schema in properties.values():
                _transform_node(sub_schema)

        items = node.get("items")
        if isinstance(items, dict):
            _transform_node(items)
        elif isinstance(items, list):
            for sub_schema in items:
                _transform_node(sub_schema)

        for keyword in _COMPOSITION_KEYWORDS:
            branches = node.get(keyword)
            if isinstance(branches, list):
                for sub_schema in branches:
                    _transform_node(sub_schema)

        for keyword in _DEFINITION_KEYWORDS:
            definitions = node.get(keyword)
            if isinstance(definitions, dict):
                for sub_schema in definitions.values():
                    _transform_node(sub_schema)

    elif isinstance(node, list):
        for sub_schema in node:
            _transform_node(sub_schema)


def audit_unsupported_features(schema: Mapping[str, Any]) -> dict[str, list[str]]:
    """
    Inventaire (fonctionnalité -> chemins) des fonctionnalités JSON Schema
    listées par Anthropic comme NON supportées par Structured Outputs.

    Outil de diagnostic pur, appelé sur le schéma PROVIDER (déjà transformé
    par `prepare_anthropic_json_schema`) : il ne modifie rien, il documente.
    Une clé dont la liste est vide signifie « aucune occurrence détectée ».
    """
    findings: dict[str, list[str]] = {
        "external_ref": [],
        "unsupported_minItems": [],
        "additionalProperties_not_false": [],
        **{keyword: [] for keyword in _UNSUPPORTED_KEYWORDS},
    }

    def _walk(node: Any, path: str) -> None:
        if isinstance(node, list):
            for index, item in enumerate(node):
                _walk(item, f"{path}[{index}]")
            return

        if not isinstance(node, dict):
            return

        ref = node.get("$ref")
        if isinstance(ref, str) and not ref.startswith("#"):
            findings["external_ref"].append(f"{path}.$ref")

        for keyword in _UNSUPPORTED_KEYWORDS:
            if keyword in node:
                findings[keyword].append(path)

        if "minItems" in node and node["minItems"] not in _SUPPORTED_MIN_ITEMS:
            findings["unsupported_minItems"].append(path)

        if node.get("type") == "object" and node.get("additionalProperties") is not False:
            findings["additionalProperties_not_false"].append(path)

        properties = node.get("properties")
        if isinstance(properties, dict):
            for name, sub_schema in properties.items():
                _walk(sub_schema, f"{path}.properties.{name}")

        items = node.get("items")
        if isinstance(items, dict):
            _walk(items, f"{path}.items")
        elif isinstance(items, list):
            for index, sub_schema in enumerate(items):
                _walk(sub_schema, f"{path}.items[{index}]")

        for keyword in _COMPOSITION_KEYWORDS:
            branches = node.get(keyword)
            if isinstance(branches, list):
                for index, sub_schema in enumerate(branches):
                    _walk(sub_schema, f"{path}.{keyword}[{index}]")

        for keyword in _DEFINITION_KEYWORDS:
            definitions = node.get(keyword)
            if isinstance(definitions, dict):
                for name, sub_schema in definitions.items():
                    _walk(sub_schema, f"{path}.{keyword}.{name}")

    _walk(dict(schema), "$")

    return findings
