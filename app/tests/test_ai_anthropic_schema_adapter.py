"""
Phase 3B.3.1 / 3B.3.2 — adaptateur de schéma provider Anthropic.

Anthropic Structured Outputs exige `"additionalProperties": false` sur
chaque noeud `"type": "object"` (Phase 3B.3.1), et ne supporte ni
`minLength`/`maxLength`, ni `minItems` hors {0, 1} (Phase 3B.3.2). Le
schéma canonique du Source Analyzer (app/source_analysis/schema.py) reste
volontairement permissif et strict à la fois — permissif sur
`additionalProperties` (frontière éditoriale), strict sur `minLength` et le
`minItems` de `repetitions[].idea_refs` (contrat métier) : ces tests
vérifient que la transformation dédiée à la frontière Anthropic
(`prepare_anthropic_json_schema`) ferme tous les objets, retire `minLength`
et le `minItems` incompatible de la COPIE provider uniquement, sans jamais
muter le schéma canonique, et sans en changer le reste du contrat métier
(required, properties, enum...).

Aucun réseau : ce module teste des fonctions pures sur des dictionnaires,
mais hérite quand même de `no_ai_network` par cohérence avec le reste de la
suite IA.
"""

from __future__ import annotations

import copy
import json

import pytest

from app.ai.errors import AIStructuredOutputError
from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.ai.structured import parse_structured_output
from app.source_analysis.schema import build_response_schema
from app.tests.source_analysis_fixtures import fake_analysis_payload


@pytest.fixture(autouse=True)
def _reseau_interdit(no_ai_network):
    """Aucun test de ce module n'a de raison de toucher le réseau."""


# ---------------------------------------------------------------------------
# Walker de test — indépendant de l'implémentation de _close_objects()
# ---------------------------------------------------------------------------

def _walk_nodes(node, path="$"):
    """Générateur (path, node) de chaque noeud dict rencontré, récursivement."""
    if isinstance(node, dict):
        yield path, node

        properties = node.get("properties")
        if isinstance(properties, dict):
            for key, sub in properties.items():
                yield from _walk_nodes(sub, f"{path}.properties.{key}")

        items = node.get("items")
        if isinstance(items, dict):
            yield from _walk_nodes(items, f"{path}.items")
        elif isinstance(items, list):
            for index, sub in enumerate(items):
                yield from _walk_nodes(sub, f"{path}.items[{index}]")

        for keyword in ("anyOf", "oneOf", "allOf"):
            branches = node.get(keyword)
            if isinstance(branches, list):
                for index, sub in enumerate(branches):
                    yield from _walk_nodes(sub, f"{path}.{keyword}[{index}]")

        for keyword in ("$defs", "definitions"):
            definitions = node.get(keyword)
            if isinstance(definitions, dict):
                for key, sub in definitions.items():
                    yield from _walk_nodes(sub, f"{path}.{keyword}.{key}")

    elif isinstance(node, list):
        for index, sub in enumerate(node):
            yield from _walk_nodes(sub, f"{path}[{index}]")


def _object_nodes(schema):
    return [
        (path, node)
        for path, node in _walk_nodes(schema)
        if isinstance(node, dict) and node.get("type") == "object"
    ]


def _strip_additional_properties(node):
    """Copie de `node` sans aucune clé `additionalProperties`, récursivement."""
    if isinstance(node, dict):
        return {
            key: _strip_additional_properties(value)
            for key, value in node.items()
            if key != "additionalProperties"
        }

    if isinstance(node, list):
        return [_strip_additional_properties(item) for item in node]

    return node


def _strip_provider_only_diffs(node):
    """
    Copie de `node` sans les trois seules différences que la frontière
    Anthropic est autorisée à introduire (Phase 3B.3.1 + 3B.3.2) :
    `additionalProperties`, `minLength`, et un `minItems` hors {0, 1}.

    Réimplémentation volontairement INDÉPENDANTE de
    `app.ai.providers._anthropic_schema._transform_node` : ce test doit
    détecter une régression de l'implémentation, pas la reproduire.
    """
    if isinstance(node, dict):
        stripped = {
            key: _strip_provider_only_diffs(value)
            for key, value in node.items()
            if key not in ("additionalProperties", "minLength")
        }

        if "minItems" in stripped and stripped["minItems"] not in (0, 1):
            del stripped["minItems"]

        return stripped

    if isinstance(node, list):
        return [_strip_provider_only_diffs(item) for item in node]

    return node


def _count_keyword(schema, keyword):
    """Nombre d'occurrences de `keyword` (clé de dict), récursivement."""
    return sum(1 for _, node in _walk_nodes(schema) if keyword in node)


def _optional_parameter_count(schema):
    """Propriétés déclarées dans un `properties` mais absentes de `required`."""
    return sum(
        1
        for _, node in _walk_nodes(schema)
        if node.get("type") == "object"
        for key in (node.get("properties") or {})
        if key not in (node.get("required") or [])
    )


def _union_parameter_count(schema):
    """Propriétés utilisant `anyOf` ou un `type` en liste (union de types)."""
    count = 0
    for _, node in _walk_nodes(schema):
        if node.get("type") != "object":
            continue
        for sub_schema in (node.get("properties") or {}).values():
            if not isinstance(sub_schema, dict):
                continue
            if "anyOf" in sub_schema or isinstance(sub_schema.get("type"), list):
                count += 1
    return count


# ---------------------------------------------------------------------------
# Section 5 — ne jamais muter le schéma canonique
# ---------------------------------------------------------------------------

class TestNeMutePasLeCanonique:

    def test_canonical_inchange_et_provider_est_un_objet_distinct(self):
        canonical = build_response_schema()
        snapshot = copy.deepcopy(canonical)

        provider = prepare_anthropic_json_schema(canonical)

        assert canonical == snapshot
        assert provider is not canonical

    def test_deux_appels_successifs_ne_partagent_aucun_conteneur_mutable(self):
        """Muter le résultat d'un appel ne doit jamais affecter un autre appel."""
        canonical = build_response_schema()

        first = prepare_anthropic_json_schema(canonical)
        second = prepare_anthropic_json_schema(canonical)

        first["properties"]["topics"]["items"]["additionalProperties"] = "muté"

        assert second["properties"]["topics"]["items"]["additionalProperties"] is False
        assert canonical["properties"]["topics"]["items"].get("additionalProperties") is not False

    def test_un_dict_simple_sans_objet_ni_contrainte_retiree_n_est_pas_mute(self):
        """
        Un noeud non-objet, sans `minLength` ni `minItems` incompatible,
        traverse la transformation sans aucune différence : la copie reste
        néanmoins un objet distinct (pas d'alias).
        """
        canonical = {"type": "string", "maxLength": 5}
        snapshot = copy.deepcopy(canonical)

        provider = prepare_anthropic_json_schema(canonical)

        assert canonical == snapshot
        assert provider == canonical
        assert provider is not canonical

    def test_minlength_est_retire_meme_hors_de_tout_objet(self):
        """
        Le retrait de `minLength` (Phase 3B.3.2) ne dépend pas de
        `_close_objects` (Phase 3B.3.1, limité à `"type": "object"`) : un
        simple noeud `string` racine doit lui aussi perdre son `minLength`.
        """
        canonical = {"type": "string", "minLength": 1}
        snapshot = copy.deepcopy(canonical)

        provider = prepare_anthropic_json_schema(canonical)

        assert canonical == snapshot  # le canonique n'a pas bougé
        assert provider == {"type": "string"}

    def test_minitems_supporte_0_ou_1_n_est_jamais_retire(self):
        """
        Seule une valeur HORS {0, 1} est retirée (section 5 du protocole) :
        un `minItems` déjà supporté reste intact dans la copie provider.
        """
        canonical_zero = {"type": "array", "minItems": 0, "items": {"type": "string"}}
        canonical_one = {"type": "array", "minItems": 1, "items": {"type": "string"}}

        assert prepare_anthropic_json_schema(canonical_zero)["minItems"] == 0
        assert prepare_anthropic_json_schema(canonical_one)["minItems"] == 1

    def test_minitems_hors_0_1_est_retire_de_la_copie_uniquement(self):
        canonical = {"type": "array", "minItems": 2, "items": {"type": "string"}}
        snapshot = copy.deepcopy(canonical)

        provider = prepare_anthropic_json_schema(canonical)

        assert canonical == snapshot  # le canonique conserve minItems: 2
        assert "minItems" not in provider


# ---------------------------------------------------------------------------
# Section 6 — tous les objets fermés (walker de test)
# ---------------------------------------------------------------------------

class TestTousLesObjetsFermes:

    def test_walker_ferme_tous_les_objets_du_schema_source_analyzer(self):
        canonical = build_response_schema()
        provider = prepare_anthropic_json_schema(canonical)

        objets = _object_nodes(provider)
        fermes = [node for _, node in objets if node.get("additionalProperties") is False]
        restants = [
            path for path, node in objets if node.get("additionalProperties") is not False
        ]

        # Rapport (section 6 du protocole) : objets rencontrés / fermés / restants.
        assert len(objets) == 12
        assert len(fermes) == len(objets)
        assert restants == []

    def test_le_schema_canonique_lui_meme_n_a_aucun_objet_ferme(self):
        """Contraste : le canonique reste permissif, seul le provider est fermé."""
        canonical = build_response_schema()

        objets = _object_nodes(canonical)
        fermes = [node for _, node in objets if node.get("additionalProperties") is False]

        assert len(objets) == 12
        assert fermes == []

    def test_couverture_recursive_properties_items_anyof_oneof_allof_defs(self):
        """
        Couverture minimale exigée par le protocole (section 4) : properties,
        items, anyOf, oneOf, allOf, $defs, definitions.
        """
        schema = {
            "type": "object",
            "properties": {
                "variante_anyof": {
                    "anyOf": [
                        {"type": "object", "properties": {"a": {"type": "string"}}},
                        {"type": "object", "properties": {"b": {"type": "string"}}},
                    ]
                },
                "variante_oneof": {
                    "oneOf": [{"type": "object", "properties": {"e": {"type": "string"}}}]
                },
                "variante_allof": {
                    "allOf": [{"type": "object", "properties": {"f": {"type": "string"}}}]
                },
                "liste": {
                    "type": "array",
                    "items": {"type": "object", "properties": {"c": {"type": "string"}}},
                },
                "liste_de_variantes": {
                    "type": "array",
                    "items": [
                        {"type": "object", "properties": {"g": {"type": "string"}}},
                        {"type": "string"},
                    ],
                },
            },
            "$defs": {
                "brique": {"type": "object", "properties": {"d": {"type": "string"}}}
            },
            "definitions": {
                "brique_legacy": {"type": "object", "properties": {"h": {"type": "string"}}}
            },
        }

        provider = prepare_anthropic_json_schema(schema)

        objets = _object_nodes(provider)
        # racine + anyOf(2) + oneOf(1) + allOf(1) + items(array) + items[0] (liste
        # de variantes) + $defs.brique + definitions.brique_legacy = 9
        assert len(objets) == 9
        assert all(node.get("additionalProperties") is False for _, node in objets)


# ---------------------------------------------------------------------------
# Section 7/13 — contrat canonique inchangé
# ---------------------------------------------------------------------------

class TestContratCanoniqueInchange:

    def test_provider_ne_differe_du_canonique_que_par_additionalProperties_minlength_et_minitems(
        self,
    ):
        """
        Aucune suppression de required/properties/enum/description : le
        schéma provider est identique au canonique une fois retirés, des
        deux côtés, les trois seules différences autorisées par la
        frontière Anthropic : `additionalProperties` (3B.3.1), `minLength`
        et le `minItems` incompatible (3B.3.2).
        """
        canonical = build_response_schema()
        provider = prepare_anthropic_json_schema(canonical)

        assert _strip_provider_only_diffs(provider) == _strip_provider_only_diffs(canonical)

    def test_aucun_additionalProperties_prealable_dans_le_canonique(self):
        """
        Précondition du test précédent : si le canonique en portait déjà un,
        la comparaison ci-dessus serait trompeuse (elle retirerait aussi les
        additionalProperties canoniques). Ce n'est pas le cas ici (voir
        app/source_analysis/schema.py, doctrine « additionalProperties
        volontairement permissif »).
        """
        canonical = build_response_schema()

        assert not any(
            "additionalProperties" in node for _, node in _walk_nodes(canonical)
        )

    def test_le_normalizer_et_le_validator_ne_sont_pas_affectes(self):
        """
        Le contrat de frontière éditoriale (fuite `chapters`) dépend du
        schéma CANONIQUE, jamais du schéma provider Anthropic : cette
        transformation ne le touche pas.
        """
        canonical = build_response_schema()

        assert canonical.get("additionalProperties") is not False


# ---------------------------------------------------------------------------
# Section 10 — comptage optional/union inchangé après transformation
# ---------------------------------------------------------------------------

class TestOptionalEtUnionParameterCounts:

    def test_les_comptages_sont_identiques_avant_apres_transformation(self):
        canonical = build_response_schema()
        provider = prepare_anthropic_json_schema(canonical)

        assert _optional_parameter_count(canonical) == _optional_parameter_count(provider)
        assert _union_parameter_count(canonical) == _union_parameter_count(provider)

    def test_les_comptages_restent_dans_les_limites_anthropic_connues(self):
        """
        Limites documentées par Anthropic (section 1 du protocole) :
        24 paramètres optionnels, 16 paramètres de type union, au total sur
        l'ensemble des schémas stricts d'une requête. Un seul schéma est
        envoyé ici (celui du Source Analyzer) : ses propres comptages
        doivent donc déjà rester sous ces plafonds.
        """
        provider = prepare_anthropic_json_schema(build_response_schema())

        optional = _optional_parameter_count(provider)
        union = _union_parameter_count(provider)

        assert optional == 20
        assert optional <= 24
        assert union == 0
        assert union <= 16


# ---------------------------------------------------------------------------
# Section 11 — audit des fonctionnalités Anthropic non supportées
# ---------------------------------------------------------------------------

class TestAuditFonctionnalitesNonSupportees:
    """
    Ce test ne corrige rien : il DOCUMENTE l'état réel du schéma provider
    (schéma canonique + fermeture additionalProperties + retrait minLength
    / minItems incompatible). D'après la documentation Anthropic Structured
    Outputs (section « Not supported » : schéma récursif, `$ref` externe,
    `minimum`/`maximum`/`multipleOf`, `minLength`/`maxLength`, contraintes
    de tableau au-delà de `minItems` 0/1, `additionalProperties` != false),
    le schéma du Source Analyzer portait, au 3B.3.1, deux incompatibilités
    connues :

        - `minLength` sur les champs texte (25 occurrences) ;
        - un `minItems` de 2 sur `repetitions[].idea_refs` (1 occurrence).

    La Phase 3B.3.2 les résout toutes les deux, uniquement sur la COPIE
    provider (voir app/ai/providers/_anthropic_schema.py, section 4 et 5 du
    protocole) : ce test vérifie maintenant l'absence de TOUTE
    incompatibilité connue sur le schéma réellement transmis à Anthropic.
    """

    def test_additionalProperties_est_ferme_partout_apres_transformation(self):
        provider = prepare_anthropic_json_schema(build_response_schema())

        findings = audit_unsupported_features(provider)

        assert findings["additionalProperties_not_false"] == []

    def test_aucun_ref_recursion_minimum_maximum_multipleof_maxitems(self):
        """
        Fonctionnalités listées par Anthropic comme non supportées et NON
        présentes dans notre schéma : aucune occurrence, donc aucune
        transformation supplémentaire n'a été inventée pour elles (section
        11 du protocole : « ne pas inventer de transformation supplémentaire
        si aucune occurrence n'existe »).
        """
        provider = prepare_anthropic_json_schema(build_response_schema())

        findings = audit_unsupported_features(provider)

        assert findings["external_ref"] == []
        assert findings["minimum"] == []
        assert findings["maximum"] == []
        assert findings["multipleOf"] == []
        assert findings["maxLength"] == []
        assert findings["maxItems"] == []

    def test_minlength_est_desormais_absent_du_schema_provider(self):
        """
        `minLength` est explicitement listé par Anthropic comme NON
        supporté (« String constraints (minLength, maxLength) ») — rejeté
        par une erreur 400 côté API réelle. Phase 3B.3.2 le retire de la
        copie provider (jamais du canonique, voir
        TestCanonicalMinLengthEtMinItemsPreserves ci-dessous) : l'audit du
        schéma réellement transmis ne doit plus en trouver aucune trace.
        """
        provider = prepare_anthropic_json_schema(build_response_schema())

        findings = audit_unsupported_features(provider)

        assert findings["minLength"] == []

    def test_minitems_hors_0_1_est_desormais_absent_du_schema_provider(self):
        """
        `minItems` n'est supporté par Anthropic que pour les valeurs 0 ou 1.
        `repetitions[].idea_refs` exigeait `minItems: 2` (« une reprise
        relie AU MOINS deux idées ») dans le schéma transmis : Phase 3B.3.2
        retire cette contrainte de la copie provider (jamais du canonique).
        """
        provider = prepare_anthropic_json_schema(build_response_schema())

        findings = audit_unsupported_features(provider)

        assert findings["unsupported_minItems"] == []

    def test_audit_complet_zero_incompatibilite_connue(self):
        """
        Section 10 du protocole 3B.3.2 : réexécuter l'audit complet sur le
        schéma PROVIDER final et constater zéro incompatibilité connue,
        toutes catégories confondues (aucune régression silencieuse sur une
        catégorie non testée individuellement ci-dessus).
        """
        provider = prepare_anthropic_json_schema(build_response_schema())

        findings = audit_unsupported_features(provider)

        assert all(occurrences == [] for occurrences in findings.values()), findings


# ---------------------------------------------------------------------------
# Section 19 (items 1-6) — comptages figés minLength / minItems, canonique
# vs provider, avant/après transformation.
# ---------------------------------------------------------------------------

class TestCanonicalMinLengthEtMinItemsPreserves:
    """
    Pins explicites demandés par le protocole 3B.3.2 (section 19) : ces
    compteurs rendent visible toute variation future du schéma canonique
    ou toute régression de la transformation provider.
    """

    def test_1_canonical_a_25_minLength_avant_transformation(self):
        canonical = build_response_schema()

        assert _count_keyword(canonical, "minLength") == 25

    def test_2_provider_a_zero_minLength_apres_transformation(self):
        provider = prepare_anthropic_json_schema(build_response_schema())

        assert _count_keyword(provider, "minLength") == 0

    def test_3_canonical_conserve_ses_25_minLength_apres_transformation(self):
        canonical = build_response_schema()

        prepare_anthropic_json_schema(canonical)  # résultat ignoré : effet de bord seul testé

        assert _count_keyword(canonical, "minLength") == 25

    def test_4_canonical_a_bien_minItems_2_sur_repetitions_idea_refs(self):
        canonical = build_response_schema()

        idea_refs_schema = canonical["properties"]["repetitions"]["items"]["properties"][
            "idea_refs"
        ]

        assert idea_refs_schema["minItems"] == 2

    def test_5_provider_retire_le_minItems_de_repetitions_idea_refs(self):
        provider = prepare_anthropic_json_schema(build_response_schema())

        idea_refs_schema = provider["properties"]["repetitions"]["items"]["properties"][
            "idea_refs"
        ]

        assert "minItems" not in idea_refs_schema

    def test_6_canonical_conserve_minItems_2_apres_transformation(self):
        canonical = build_response_schema()

        prepare_anthropic_json_schema(canonical)  # résultat ignoré : effet de bord seul testé

        idea_refs_schema = canonical["properties"]["repetitions"]["items"]["properties"][
            "idea_refs"
        ]

        assert idea_refs_schema["minItems"] == 2


# ---------------------------------------------------------------------------
# Section 19 (items 7-8) — validation locale : la copie provider (permissive
# sur minLength/minItems) ne doit JAMAIS être ce qui protège le contrat
# métier. C'est le schéma CANONIQUE, via parse_structured_output(), qui doit
# rejeter une violation — même quand le schéma provider laisserait passer.
# ---------------------------------------------------------------------------

class TestValidationLocaleMinLengthEtMinItems:

    def test_7_violation_minlength_acceptee_par_le_schema_provider_mais_rejetee_localement(
        self,
    ):
        jsonschema = pytest.importorskip("jsonschema")

        canonical = build_response_schema()
        provider = prepare_anthropic_json_schema(canonical)

        payload = fake_analysis_payload()
        payload["source_analysis"]["main_theme"] = ""  # viole minLength: 1 du canonique

        # Le schéma PROVIDER (adapté pour Anthropic) ne porte plus le
        # minLength : une chaîne vide lui est structurellement conforme.
        jsonschema.validate(instance=payload, schema=provider)

        # La validation locale, elle, s'appuie sur le schéma CANONIQUE
        # (c'est exactement ce que fait BaseAIEngine.generate(), jamais sur
        # le schéma provider) : la même réponse y est rejetée.
        with pytest.raises(AIStructuredOutputError):
            parse_structured_output(json.dumps(payload, ensure_ascii=False), canonical)

    def test_8_violation_minitems_acceptee_par_le_schema_provider_mais_rejetee_localement(
        self,
    ):
        jsonschema = pytest.importorskip("jsonschema")

        canonical = build_response_schema()
        provider = prepare_anthropic_json_schema(canonical)

        payload = fake_analysis_payload()
        # Une seule idea_id au lieu des deux exigées par le canonique
        # (minItems: 2) : une reprise ne peut pas relier une seule idée.
        payload["repetitions"][0]["idea_refs"] = ["idea_7"]

        # Le schéma PROVIDER (minItems incompatible retiré) accepte cette
        # liste d'un seul élément.
        jsonschema.validate(instance=payload, schema=provider)

        # Le schéma CANONIQUE, seul utilisé par la validation locale, la
        # rejette toujours.
        with pytest.raises(AIStructuredOutputError):
            parse_structured_output(json.dumps(payload, ensure_ascii=False), canonical)


# ---------------------------------------------------------------------------
# Section 16/17 — défense en profondeur, redondant avec test_ai_providers.py
# mais vérifié ici directement sur les fonctions pures du module.
# ---------------------------------------------------------------------------

class TestDefenseEnProfondeur:

    def test_le_schema_provider_reste_un_json_schema_valide(self):
        jsonschema = pytest.importorskip("jsonschema")

        provider = prepare_anthropic_json_schema(build_response_schema())

        jsonschema.Draft7Validator.check_schema(provider)
