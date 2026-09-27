"""
Normalisation : ordre canonique, renumérotation, réécriture des références.

Tests unitaires du normalizer, sans moteur IA : la réponse « du modèle » est
fournie directement, ce qui permet d'exercer des cas qu'un fake n'aurait aucune
raison de produire spontanément.
"""

from __future__ import annotations

import pytest

from app.source_analysis.errors import (
    SourceMapEditorialLeakError,
    SourceMapValidationError,
)
from app.source_analysis.models import AnalysisProvenance
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.transcript_input import (
    load_transcript_input,
    transcript_data_file,
)
from app.tests.source_analysis_fixtures import (  # noqa: F401 — fixture pytest
    analysis_env,
    fake_analysis_payload,
)

_PROVENANCE = AnalysisProvenance(
    prompt_version="1.0",
    schema_version="1.0",
    provider="fake",
    model="fake-model",
    strategy="global",
    signature="sig",
)


@pytest.fixture
def transcript(analysis_env):
    return load_transcript_input(
        transcript_data_file(analysis_env.transcripts_dir),
        project_name=analysis_env.project_name,
    )


def _normalize(payload, transcript):
    return normalize_source_map(payload, transcript, provenance=_PROVENANCE)


class TestOrdering:
    """L'ordre vient de la source, pas de la réponse du modèle."""

    def test_les_idees_suivent_leur_premiere_apparition(self, transcript):
        payload = fake_analysis_payload()
        payload["ideas"] = list(reversed(payload["ideas"]))

        source_map = _normalize(payload, transcript)

        assert source_map.ideas[0].source_refs[0] == "SRC000001"
        assert source_map.ideas[1].source_refs[0] == "SRC000004"

    def test_les_source_refs_suivent_l_ordre_canonique(self, transcript):
        payload = fake_analysis_payload()
        payload["ideas"][0]["source_refs"] = [
            "SRC000008",
            "SRC000002",
            "SRC000005",
        ]

        source_map = _normalize(payload, transcript)

        assert source_map.ideas[0].source_refs == (
            "SRC000002",
            "SRC000005",
            "SRC000008",
        )

    def test_les_doublons_de_src_sont_fusionnes(self, transcript):
        payload = fake_analysis_payload()
        payload["ideas"][0]["source_refs"] = [
            "SRC000002",
            "SRC000001",
            "SRC000002",
        ]

        source_map = _normalize(payload, transcript)

        assert source_map.ideas[0].source_refs == ("SRC000001", "SRC000002")

    def test_l_ordre_alphabetique_n_est_pas_employe(self, transcript):
        """
        Trier les thèmes par label détruirait la progression du discours : « Zèle
        du début » doit rester avant « Foi de la fin » s'il est introduit avant.
        """
        payload = fake_analysis_payload()
        payload["topics"] = [
            {
                "topic_id": "z",
                "label": "Zèle initial",
                "summary": "Introduit tôt.",
                "source_refs": ["SRC000001"],
            },
            {
                "topic_id": "a",
                "label": "Aboutissement",
                "summary": "Introduit tard.",
                "source_refs": ["SRC000005"],
            },
        ]
        payload["ideas"][0]["topic_refs"] = ["z"]
        payload["ideas"][1]["topic_refs"] = ["a"]

        source_map = _normalize(payload, transcript)

        assert [topic.label for topic in source_map.topics] == [
            "Zèle initial",
            "Aboutissement",
        ]

    def test_deux_elements_du_meme_segment_gardent_l_ordre_de_la_reponse(
        self, transcript
    ):
        payload = fake_analysis_payload()
        payload["ideas"] = [
            {
                "idea_id": "premiere",
                "summary": "Première idée du segment un.",
                "kind": "claim",
                "importance": "central",
                "source_refs": ["SRC000001"],
            },
            {
                "idea_id": "seconde",
                "summary": "Seconde idée du segment un.",
                "kind": "observation",
                "importance": "minor",
                "source_refs": ["SRC000001"],
            },
        ]
        payload["examples"][0]["supports_idea_refs"] = ["premiere"]
        payload["repetitions"][0]["idea_refs"] = ["premiere", "seconde"]

        source_map = _normalize(payload, transcript)

        assert source_map.ideas[0].summary.startswith("Première")
        assert source_map.ideas[1].summary.startswith("Seconde")


class TestIdNormalization:
    """Les identifiants du LLM ne sont jamais repris tels quels."""

    def test_des_ids_farfelus_deviennent_une_serie_continue(self, transcript):
        source_map = _normalize(fake_analysis_payload(), transcript)

        assert [idea.idea_id for idea in source_map.ideas] == ["IDEA001", "IDEA002"]
        assert [topic.topic_id for topic in source_map.topics] == ["TOP001"]
        assert [item.example_id for item in source_map.examples] == ["EX001"]

    def test_toutes_les_categories_sont_renumerotees(self, transcript):
        payload = fake_analysis_payload()
        payload["references"] = [
            {
                "reference_id": "ref-bizarre",
                "kind": "biblical",
                "raw_reference": "Paul dit quelque part",
                "normalized_reference": "",
                "completeness": "vague",
                "source_refs": ["SRC000002"],
            }
        ]
        payload["uncertainties"] = [
            {
                "uncertainty_id": "?",
                "kind": "incomplete_reference",
                "description": "Référence non située dans le discours.",
                "severity": "medium",
                "source_refs": ["SRC000002"],
            }
        ]

        source_map = _normalize(payload, transcript)

        assert source_map.references[0].reference_id == "REF001"
        assert source_map.uncertainties[0].uncertainty_id == "UNC001"
        assert source_map.repetitions[0].repetition_id == "REP001"

    def test_les_references_internes_sont_reecrites(self, transcript):
        source_map = _normalize(fake_analysis_payload(), transcript)

        assert source_map.ideas[0].topic_refs == ("TOP001",)
        assert source_map.examples[0].supports_idea_refs == ("IDEA001",)
        assert source_map.repetitions[0].idea_refs == ("IDEA001", "IDEA002")
        assert source_map.ideas[1].relations[0].to_idea == "IDEA001"

    def test_un_id_local_duplique_est_refuse(self, transcript):
        payload = fake_analysis_payload()
        payload["ideas"][1]["idea_id"] = payload["ideas"][0]["idea_id"]

        with pytest.raises(SourceMapValidationError) as excinfo:
            _normalize(payload, transcript)

        assert any("dupliqué" in error for error in excinfo.value.errors)

    def test_un_id_local_absent_est_refuse(self, transcript):
        payload = fake_analysis_payload()
        payload["ideas"][0]["idea_id"] = ""

        with pytest.raises(SourceMapValidationError) as excinfo:
            _normalize(payload, transcript)

        assert any("idea_id absent" in error for error in excinfo.value.errors)

    def test_deux_normalisations_de_la_meme_reponse_sont_identiques(self, transcript):
        first = _normalize(fake_analysis_payload(), transcript)
        second = _normalize(fake_analysis_payload(), transcript)

        assert first.to_dict() == second.to_dict()


class TestOptionalLocalIds:
    """
    Phase 3B.2 — topic_id et idea_id sont la CIBLE de références internes
    (topic_refs, to_idea, supports_idea_refs, idea_refs) : leur absence
    rendrait une réécriture ambiguë et reste refusée. example_id,
    reference_id, uncertainty_id et repetition_id ne sont la cible d'AUCUNE
    référence dans ce schéma : leur absence n'empêche pas de reconstruire le
    Source Map, qui les renumérote comme n'importe quel autre élément.

    `test_uncertainty_id_absent_est_tolere` reproduit exactement l'incident
    réel de la validation `pastoral_retreat_v2` : un appel Anthropic rejeté
    localement pour `uncertainties[7].uncertainty_id` absent.
    """

    def test_uncertainty_id_absent_est_tolere(self, transcript):
        payload = fake_analysis_payload()
        payload["uncertainties"] = [
            {
                # uncertainty_id volontairement absent.
                "kind": "incomplete_reference",
                "description": "Référence non située dans le discours.",
                "severity": "medium",
                "source_refs": ["SRC000002"],
            }
        ]

        source_map = _normalize(payload, transcript)

        assert [item.uncertainty_id for item in source_map.uncertainties] == ["UNC001"]
        assert source_map.uncertainties[0].description == (
            "Référence non située dans le discours."
        )

    def test_example_id_absent_est_tolere(self, transcript):
        payload = fake_analysis_payload()
        del payload["examples"][0]["example_id"]

        source_map = _normalize(payload, transcript)

        assert [item.example_id for item in source_map.examples] == ["EX001"]
        # Rien ne cible example_id : son absence n'affecte aucune relation.
        assert source_map.examples[0].supports_idea_refs == ("IDEA001",)

    def test_reference_id_absent_est_tolere(self, transcript):
        payload = fake_analysis_payload()
        payload["references"] = [
            {
                # reference_id volontairement absent.
                "kind": "biblical",
                "raw_reference": "Paul dit quelque part",
                "normalized_reference": "",
                "completeness": "vague",
                "source_refs": ["SRC000002"],
            }
        ]

        source_map = _normalize(payload, transcript)

        assert [item.reference_id for item in source_map.references] == ["REF001"]

    def test_repetition_id_absent_est_tolere(self, transcript):
        payload = fake_analysis_payload()
        del payload["repetitions"][0]["repetition_id"]

        source_map = _normalize(payload, transcript)

        assert [item.repetition_id for item in source_map.repetitions] == ["REP001"]
        assert source_map.repetitions[0].idea_refs == ("IDEA001", "IDEA002")

    def test_topic_id_absent_reste_refuse(self, transcript):
        """topic_id EST la cible de ideas[].topic_refs : son absence reste une erreur."""
        payload = fake_analysis_payload()
        payload["topics"][0]["topic_id"] = ""

        with pytest.raises(SourceMapValidationError) as excinfo:
            _normalize(payload, transcript)

        assert any("topic_id absent" in error for error in excinfo.value.errors)

    def test_idea_id_absent_reste_refuse(self, transcript):
        """idea_id EST la cible de relations/supports_idea_refs/idea_refs."""
        payload = fake_analysis_payload()
        payload["ideas"][0]["idea_id"] = ""

        with pytest.raises(SourceMapValidationError) as excinfo:
            _normalize(payload, transcript)

        assert any("idea_id absent" in error for error in excinfo.value.errors)

    def test_example_id_duplique_par_accident_n_est_pas_une_erreur(self, transcript):
        """
        example_id n'étant la cible d'aucune référence, un doublon fortuit ne
        crée aucune ambiguïté relationnelle — à la différence d'un idea_id ou
        d'un topic_id dupliqué (voir test_un_id_local_duplique_est_refuse).
        """
        payload = fake_analysis_payload()
        payload["examples"].append(
            {
                "example_id": payload["examples"][0]["example_id"],
                "kind": "illustration",
                "summary": "Une seconde illustration, avec le même identifiant local.",
                "supports_idea_refs": ["idea_7"],
                "source_refs": ["SRC000004"],
            }
        )

        source_map = _normalize(payload, transcript)

        assert [item.example_id for item in source_map.examples] == ["EX001", "EX002"]

    def test_les_quatre_identifiants_optionnels_peuvent_manquer_ensemble(
        self, transcript
    ):
        payload = fake_analysis_payload()
        del payload["examples"][0]["example_id"]
        del payload["repetitions"][0]["repetition_id"]
        payload["references"] = [
            {
                "kind": "biblical",
                "raw_reference": "Paul dit quelque part",
                "normalized_reference": "",
                "completeness": "vague",
                "source_refs": ["SRC000002"],
            }
        ]
        payload["uncertainties"] = [
            {
                "kind": "ambiguous_meaning",
                "description": "Sens ambigu du passage.",
                "severity": "low",
                "source_refs": ["SRC000001"],
            }
        ]

        source_map = _normalize(payload, transcript)

        assert source_map.examples[0].example_id == "EX001"
        assert source_map.references[0].reference_id == "REF001"
        assert source_map.uncertainties[0].uncertainty_id == "UNC001"
        assert source_map.repetitions[0].repetition_id == "REP001"


class TestSourceRefValidation:
    """Une référence inventée est une erreur, jamais un champ retiré."""

    def test_un_src_inexistant_est_signale(self, transcript):
        payload = fake_analysis_payload()
        payload["ideas"][0]["source_refs"] = ["SRC000001", "SRC999999"]

        with pytest.raises(SourceMapValidationError) as excinfo:
            _normalize(payload, transcript)

        assert any(
            "SRC999999" in error and "inventée" in error
            for error in excinfo.value.errors
        )

    def test_un_element_sans_src_est_refuse(self, transcript):
        payload = fake_analysis_payload()
        payload["ideas"][0]["source_refs"] = []

        with pytest.raises(SourceMapValidationError) as excinfo:
            _normalize(payload, transcript)

        assert any("traçable" in error for error in excinfo.value.errors)

    def test_toutes_les_erreurs_sont_collectees_d_un_coup(self, transcript):
        payload = fake_analysis_payload()
        payload["topics"][0]["source_refs"] = ["SRC999998"]
        payload["ideas"][0]["source_refs"] = ["SRC999999"]

        with pytest.raises(SourceMapValidationError) as excinfo:
            _normalize(payload, transcript)

        assert len(excinfo.value.errors) >= 2


class TestInternalRefValidation:
    """Aucune référence interne pendante."""

    @pytest.mark.parametrize(
        "path, value",
        [
            (("ideas", 0, "topic_refs"), ["inexistant"]),
            (("examples", 0, "supports_idea_refs"), ["inexistant"]),
            (("repetitions", 0, "idea_refs"), ["idea_7", "inexistant"]),
        ],
    )
    def test_une_reference_pendante_est_signalee(self, transcript, path, value):
        payload = fake_analysis_payload()
        collection, index, field = path
        payload[collection][index][field] = value

        with pytest.raises(SourceMapValidationError) as excinfo:
            _normalize(payload, transcript)

        assert any("pendante" in error for error in excinfo.value.errors)

    def test_une_relation_vers_une_idee_absente_est_signalee(self, transcript):
        payload = fake_analysis_payload()
        payload["ideas"][1]["relations"] = [
            {"relation": "supports", "to_idea": "fantome"}
        ]

        with pytest.raises(SourceMapValidationError) as excinfo:
            _normalize(payload, transcript)

        assert any("fantome" in error for error in excinfo.value.errors)

    def test_les_relations_dupliquees_sont_fusionnees(self, transcript):
        payload = fake_analysis_payload()
        payload["ideas"][1]["relations"] = [
            {"relation": "supports", "to_idea": "idea_7"},
            {"relation": "supports", "to_idea": "idea_7"},
        ]

        source_map = _normalize(payload, transcript)

        assert len(source_map.ideas[1].relations) == 1


class TestStats:
    """Les statistiques sont dérivées, jamais déclarées par le modèle."""

    def test_les_compteurs_sont_calcules(self, transcript):
        stats = _normalize(fake_analysis_payload(), transcript).stats

        assert stats.topic_count == 1
        assert stats.idea_count == 2
        assert stats.example_count == 1
        assert stats.reference_count == 0
        assert stats.uncertainty_count == 0
        assert stats.repetition_count == 1

    def test_la_couverture_est_calculee(self, transcript):
        stats = _normalize(fake_analysis_payload(), transcript).stats

        assert stats.source_segment_count == 8
        assert stats.referenced_source_segments == 5
        assert stats.source_coverage_ratio == pytest.approx(0.625)

    def test_la_couverture_est_arrondie_de_facon_deterministe(self, transcript):
        payload = fake_analysis_payload()
        payload["topics"][0]["source_refs"] = ["SRC000001", "SRC000002", "SRC000003"]
        payload["ideas"][0]["source_refs"] = ["SRC000001"]
        payload["ideas"][1]["source_refs"] = ["SRC000002"]
        payload["examples"][0]["source_refs"] = ["SRC000003"]
        payload["repetitions"][0]["source_refs"] = ["SRC000001", "SRC000002"]

        stats = _normalize(payload, transcript).stats

        # 3 / 8 exactement : la valeur doit être stable d'une exécution à l'autre.
        assert stats.source_coverage_ratio == 0.375

    def test_des_compteurs_annonces_par_le_modele_sont_ignores(self, transcript):
        payload = fake_analysis_payload()
        payload["stats"] = {"idea_count": 999}

        stats = _normalize(payload, transcript).stats

        assert stats.idea_count == 2


class TestEditorialLeak:
    """Le normalizer refuse immédiatement une structure de livre."""

    def test_un_champ_de_premier_niveau_interdit_est_refuse(self, transcript):
        payload = fake_analysis_payload()
        payload["chapters"] = [{"title": "Chapitre 1"}]

        with pytest.raises(SourceMapEditorialLeakError) as excinfo:
            _normalize(payload, transcript)

        assert excinfo.value.fields == ("chapters",)
        assert "réponse du modèle" in excinfo.value.location

    def test_un_champ_interdit_dans_source_analysis_est_refuse(self, transcript):
        payload = fake_analysis_payload()
        payload["source_analysis"]["table_of_contents"] = []

        with pytest.raises(SourceMapEditorialLeakError) as excinfo:
            _normalize(payload, transcript)

        assert excinfo.value.fields == ("table_of_contents",)

    def test_le_message_explique_la_frontiere(self, transcript):
        payload = fake_analysis_payload()
        payload["sections"] = []

        with pytest.raises(SourceMapEditorialLeakError) as excinfo:
            _normalize(payload, transcript)

        assert "Editorial Planner" in str(excinfo.value)


class TestMalformedResponse:
    """Une réponse mal formée est refusée, pas devinée."""

    def test_une_reponse_qui_n_est_pas_un_objet_est_refusee(self, transcript):
        with pytest.raises(SourceMapValidationError):
            _normalize(["pas un objet"], transcript)

    def test_une_collection_qui_n_est_pas_une_liste_est_refusee(self, transcript):
        payload = fake_analysis_payload()
        payload["ideas"] = {"idea_id": "x"}

        with pytest.raises(SourceMapValidationError) as excinfo:
            _normalize(payload, transcript)

        assert any("liste est attendue" in error for error in excinfo.value.errors)

    def test_un_element_qui_n_est_pas_un_objet_est_refuse(self, transcript):
        payload = fake_analysis_payload()
        payload["topics"] = ["Foi"]

        with pytest.raises(SourceMapValidationError) as excinfo:
            _normalize(payload, transcript)

        assert any("objet est attendu" in error for error in excinfo.value.errors)

    def test_un_profil_de_voix_absent_donne_un_profil_vide(self, transcript):
        payload = fake_analysis_payload()
        del payload["author_voice_profile"]

        source_map = _normalize(payload, transcript)

        assert source_map.author_voice_profile.tone == ()
        assert source_map.author_voice_profile.register == ""
