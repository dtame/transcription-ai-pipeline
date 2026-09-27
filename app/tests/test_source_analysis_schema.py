"""
Sortie structurée : schéma de réponse et empreinte de schéma.

Le schéma est passé à `AIRequest.response_schema`, donc le décodage et la
validation structurelle appartiennent à la couche Phase 2. Aucun json.loads()
dans le service métier : ces tests vérifient que le schéma est exploitable par
cette couche et qu'il décrit bien ce que le normalizer attend.
"""

from __future__ import annotations

import json
import re

import pytest

from app.ai.errors import AIStructuredOutputError
from app.ai.structured import parse_structured_output
from app.source_analysis.models import (
    EXAMPLE_KINDS,
    IDEA_KINDS,
    IMPORTANCE_LEVELS,
    REPETITION_CHARACTERS,
)
from app.source_analysis.schema import build_response_schema, schema_fingerprint
from app.tests.source_analysis_fixtures import fake_analysis_payload

STRUCTURE_DE_LIVRE = (
    "chapter",
    "chapitre",
    "table_of_contents",
    "table des matières",
    "book_title",
    "titre du livre",
    "outline",
)

NEGATIONS = ("n'est pas", "ne sont pas", "ne pas", "aucun", "jamais", "interdit")


def _vocabulaire_du_schema(noeud, demande=None, descriptions=None):
    """
    Sépare ce que le schéma DEMANDE (noms de champs, valeurs de vocabulaire)
    de ce qu'il DÉCRIT (descriptions en prose).
    """
    demande = [] if demande is None else demande
    descriptions = [] if descriptions is None else descriptions

    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            if cle == "description" and isinstance(valeur, str):
                descriptions.append(valeur)
                continue

            if cle in {"properties", "patternProperties"} and isinstance(valeur, dict):
                demande.extend(nom.lower() for nom in valeur)

            if cle in {"required", "enum"} and isinstance(valeur, list):
                demande.extend(str(item).lower() for item in valeur)

            _vocabulaire_du_schema(valeur, demande, descriptions)

    elif isinstance(noeud, list):
        for item in noeud:
            _vocabulaire_du_schema(item, demande, descriptions)

    return demande, descriptions


class TestSchemaShape:
    """Le schéma décrit exactement les sections attendues."""

    def test_le_schema_est_un_json_schema_valide(self):
        jsonschema = pytest.importorskip("jsonschema")

        jsonschema.Draft7Validator.check_schema(build_response_schema())

    def test_les_sections_obligatoires_sont_declarees(self):
        assert build_response_schema()["required"] == [
            "source_analysis",
            "topics",
            "ideas",
            "examples",
            "references",
            "uncertainties",
            "repetitions",
            "author_voice_profile",
        ]

    def test_le_modele_ne_fournit_ni_stats_ni_provenance(self):
        """
        Ce qui doit être déterministe n'est pas demandé au modèle : compteurs,
        couverture, identité du transcript et provenance sont calculés par le
        code.
        """
        properties = build_response_schema()["properties"]

        for computed in (
            "stats",
            "analysis",
            "schema_version",
            "transcript_id",
            "project",
            "language",
        ):
            assert computed not in properties

    def test_les_vocabulaires_viennent_des_modeles(self):
        properties = build_response_schema()["properties"]
        idea = properties["ideas"]["items"]["properties"]

        assert idea["kind"]["enum"] == list(IDEA_KINDS)
        assert idea["importance"]["enum"] == list(IMPORTANCE_LEVELS)
        assert properties["examples"]["items"]["properties"]["kind"]["enum"] == list(
            EXAMPLE_KINDS
        )
        assert properties["repetitions"]["items"]["properties"]["character"][
            "enum"
        ] == list(REPETITION_CHARACTERS)

    def test_un_source_ref_doit_ressembler_a_un_src(self):
        refs = build_response_schema()["properties"]["ideas"]["items"]["properties"][
            "source_refs"
        ]

        assert refs["items"]["pattern"] == r"^SRC[0-9]{6}$"
        assert refs["minItems"] == 1

    def test_une_repetition_exige_au_moins_deux_idees(self):
        idea_refs = build_response_schema()["properties"]["repetitions"]["items"][
            "properties"
        ]["idea_refs"]

        assert idea_refs["minItems"] == 2

    def test_un_champ_editorial_n_est_pas_bloque_par_le_schema(self):
        """
        Volontaire : `chapters` doit produire une erreur de FRONTIÈRE explicite
        (SourceMapEditorialLeakError) et non un message de schéma générique dans
        lequel le vrai problème se perdrait.
        """
        assert build_response_schema().get("additionalProperties") is not False

    def test_le_schema_ne_demande_aucune_structure_de_livre(self):
        """
        Le schéma ne doit RIEN demander qui relève du livre : aucun nom de
        champ, aucune valeur de vocabulaire. Une description peut nommer un
        chapitre, mais seulement pour l'interdire (« un topic n'est PAS un
        chapitre ») — c'est précisément la frontière que Phase 3 défend.
        """
        demande, descriptions = _vocabulaire_du_schema(build_response_schema())

        for forbidden in STRUCTURE_DE_LIVRE:
            assert not [mot for mot in demande if forbidden in mot], forbidden

        for description in descriptions:
            for phrase in re.split(r"[.;]", description.lower()):
                if any(forbidden in phrase for forbidden in STRUCTURE_DE_LIVRE):
                    assert any(negation in phrase for negation in NEGATIONS), phrase


class TestOptionalLocalIdsContract:
    """
    Phase 3B.2 — topic_id et idea_id sont la cible de références internes
    (topic_refs, to_idea, supports_idea_refs, idea_refs) : ils restent requis
    par le schéma envoyé au provider. example_id, reference_id,
    uncertainty_id et repetition_id ne sont la cible d'AUCUNE référence : le
    schéma ne les exige plus, pour qu'un oubli du modèle sur une donnée que
    le normalizer sait reconstruire de façon déterministe ne fasse plus
    échouer — et perdre — un appel payant.
    """

    def test_topic_id_et_idea_id_restent_requis(self):
        properties = build_response_schema()["properties"]

        assert "topic_id" in properties["topics"]["items"]["required"]
        assert "idea_id" in properties["ideas"]["items"]["required"]

    @pytest.mark.parametrize(
        "collection, id_field",
        [
            ("examples", "example_id"),
            ("references", "reference_id"),
            ("uncertainties", "uncertainty_id"),
            ("repetitions", "repetition_id"),
        ],
    )
    def test_les_quatre_identifiants_non_relationnels_ne_sont_plus_requis(
        self, collection, id_field
    ):
        properties = build_response_schema()["properties"]

        assert id_field not in properties[collection]["items"]["required"]
        # Le champ reste proposable : ce n'est pas une suppression, seulement
        # un relâchement de l'obligation.
        assert id_field in properties[collection]["items"]["properties"]

    def test_une_incertitude_sans_uncertainty_id_est_acceptee_par_le_schema(self):
        """Reproduit exactement l'incident réel de la validation pastoral_retreat_v2."""
        payload = fake_analysis_payload()
        payload["uncertainties"] = [
            {
                "kind": "incomplete_reference",
                "description": "Référence non située dans le discours.",
                "severity": "medium",
                "source_refs": ["SRC000002"],
            }
        ]

        parsed = parse_structured_output(
            json.dumps(payload, ensure_ascii=False), build_response_schema()
        )

        assert "uncertainty_id" not in parsed["uncertainties"][0]

    @pytest.mark.parametrize(
        "collection, entry",
        [
            (
                "examples",
                {
                    "kind": "anecdote",
                    "summary": "Un exemple sans identifiant local.",
                    "source_refs": ["SRC000003"],
                },
            ),
            (
                "references",
                {
                    "kind": "biblical",
                    "raw_reference": "Paul dit quelque part",
                    "completeness": "vague",
                    "source_refs": ["SRC000002"],
                },
            ),
            (
                "repetitions",
                {
                    "character": "development",
                    "description": "Reprise sans identifiant local.",
                    "idea_refs": ["idea_7", "banana"],
                    "source_refs": ["SRC000002"],
                },
            ),
        ],
    )
    def test_les_autres_collections_optionnelles_sont_aussi_tolerees(
        self, collection, entry
    ):
        payload = fake_analysis_payload()
        payload[collection] = [entry]

        parsed = parse_structured_output(
            json.dumps(payload, ensure_ascii=False), build_response_schema()
        )

        assert len(parsed[collection]) == 1

    def test_topic_id_absent_reste_refuse_par_le_schema(self):
        payload = fake_analysis_payload()
        del payload["topics"][0]["topic_id"]

        with pytest.raises(AIStructuredOutputError):
            parse_structured_output(
                json.dumps(payload, ensure_ascii=False), build_response_schema()
            )

    def test_idea_id_absent_reste_refuse_par_le_schema(self):
        payload = fake_analysis_payload()
        del payload["ideas"][0]["idea_id"]

        with pytest.raises(AIStructuredOutputError):
            parse_structured_output(
                json.dumps(payload, ensure_ascii=False), build_response_schema()
            )


class TestSchemaValidation:
    """La couche Phase 2 valide réellement contre ce schéma."""

    def test_une_reponse_conforme_est_acceptee(self):
        payload = fake_analysis_payload()

        parsed = parse_structured_output(
            json.dumps(payload, ensure_ascii=False), build_response_schema()
        )

        assert parsed["source_analysis"]["main_theme"]
        assert len(parsed["ideas"]) == 2

    def test_une_section_manquante_est_refusee(self):
        payload = fake_analysis_payload()
        del payload["ideas"]

        with pytest.raises(AIStructuredOutputError):
            parse_structured_output(
                json.dumps(payload, ensure_ascii=False), build_response_schema()
            )

    def test_un_kind_hors_vocabulaire_est_refuse(self):
        payload = fake_analysis_payload()
        payload["ideas"][0]["kind"] = "brillante"

        with pytest.raises(AIStructuredOutputError):
            parse_structured_output(
                json.dumps(payload, ensure_ascii=False), build_response_schema()
            )

    def test_un_src_mal_forme_est_refuse(self):
        payload = fake_analysis_payload()
        payload["ideas"][0]["source_refs"] = ["SRC1"]

        with pytest.raises(AIStructuredOutputError):
            parse_structured_output(
                json.dumps(payload, ensure_ascii=False), build_response_schema()
            )

    def test_un_json_invalide_est_refuse(self):
        with pytest.raises(AIStructuredOutputError):
            parse_structured_output("{ cassé", build_response_schema())

    def test_une_reponse_encadree_de_balises_markdown_est_toleree(self):
        payload = json.dumps(fake_analysis_payload(), ensure_ascii=False)

        parsed = parse_structured_output(
            f"```json\n{payload}\n```", build_response_schema()
        )

        assert len(parsed["topics"]) == 1


class TestSchemaFingerprint:
    """L'empreinte du schéma entre dans la signature de cache."""

    def test_l_empreinte_est_stable(self):
        assert schema_fingerprint() == schema_fingerprint()

    def test_l_empreinte_change_avec_la_forme(self):
        modified = build_response_schema()
        modified["required"].append("questions")

        assert schema_fingerprint(modified) != schema_fingerprint()

    def test_l_empreinte_ignore_l_ordre_des_cles(self):
        schema = build_response_schema()
        reordered = {key: schema[key] for key in reversed(list(schema))}

        assert schema_fingerprint(reordered) == schema_fingerprint(schema)

    def test_l_empreinte_est_un_sha256(self):
        assert len(schema_fingerprint()) == 64
