"""
Validateur du Source Map : liste des invariants refusés.

Le validateur juge, il ne répare pas. Chaque test ci-dessous construit un Source
Map volontairement cassé — souvent d'une manière que le normalizer ne produirait
jamais — et vérifie que la violation est bien détectée plutôt que corrigée en
douce.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.source_analysis.errors import (
    SourceMapEditorialLeakError,
    SourceMapValidationError,
)
from app.source_analysis.models import AnalysisProvenance, IdeaRelation
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.transcript_input import (
    load_transcript_input,
    transcript_data_file,
)
from app.source_analysis.validator import (
    ensure_no_editorial_fields,
    ensure_valid_source_map,
    validate_published_payload,
    validate_source_map,
)
from app.tests.source_analysis_fixtures import (  # noqa: F401 — fixture pytest
    analysis_env,
    build_transcript_document,
    fake_analysis_payload,
    write_transcript,
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


@pytest.fixture
def source_map(transcript):
    return normalize_source_map(
        fake_analysis_payload(), transcript, provenance=_PROVENANCE
    )


def _errors(source_map, transcript) -> list[str]:
    return validate_source_map(source_map, transcript)


class TestNominal:
    """Un Source Map normalisé passe le validateur."""

    def test_aucune_violation(self, source_map, transcript):
        assert _errors(source_map, transcript) == []

    def test_la_publication_est_autorisee(self, source_map, transcript):
        ensure_valid_source_map(source_map, transcript)

    def test_le_validateur_ne_leve_jamais_de_lui_meme(self, source_map, transcript):
        assert isinstance(validate_source_map(source_map, transcript), list)


class TestHeaderInvariants:
    """En-tête : version, identité, langue, thème dominant."""

    def test_une_version_de_schema_inattendue_est_refusee(self, source_map, transcript):
        broken = dataclasses.replace(source_map, schema_version="0.9")

        assert any("schema_version" in error for error in _errors(broken, transcript))

    def test_un_transcript_id_incoherent_est_refuse(self, source_map, transcript):
        broken = dataclasses.replace(source_map, transcript_id="TR999")

        assert any("transcript_id" in error for error in _errors(broken, transcript))

    def test_une_langue_incoherente_est_refusee(self, source_map, transcript):
        broken = dataclasses.replace(source_map, primary_language="en")

        assert any(
            "langue principale" in error for error in _errors(broken, transcript)
        )

    def test_un_nom_de_projet_vide_est_refuse(self, source_map, transcript):
        broken = dataclasses.replace(source_map, project_name="")

        assert any("nom de projet" in error for error in _errors(broken, transcript))

    def test_un_main_theme_vide_est_refuse(self, source_map, transcript):
        header = dataclasses.replace(source_map.source_analysis, main_theme="")
        broken = dataclasses.replace(source_map, source_analysis=header)

        assert any("main_theme vide" in error for error in _errors(broken, transcript))

    def test_une_intention_sans_resume_est_refusee(self, source_map, transcript):
        intent = dataclasses.replace(source_map.source_analysis.author_intent, summary="")
        header = dataclasses.replace(source_map.source_analysis, author_intent=intent)
        broken = dataclasses.replace(source_map, source_analysis=header)

        assert any(
            "author_intent.summary vide" in error
            for error in _errors(broken, transcript)
        )

    def test_une_confiance_hors_vocabulaire_est_refusee(self, source_map, transcript):
        audience = dataclasses.replace(
            source_map.source_analysis.target_audience, confidence="peut-être"
        )
        header = dataclasses.replace(
            source_map.source_analysis, target_audience=audience
        )
        broken = dataclasses.replace(source_map, source_analysis=header)

        assert any(
            "target_audience.confidence invalide" in error
            for error in _errors(broken, transcript)
        )


class TestIdInvariants:
    """Identifiants uniques, continus, conformes à leur préfixe."""

    def test_un_identifiant_non_conforme_est_refuse(self, source_map, transcript):
        ideas = (
            dataclasses.replace(source_map.ideas[0], idea_id="IDEA042"),
            source_map.ideas[1],
        )
        broken = dataclasses.replace(source_map, ideas=ideas)

        assert any(
            "numérotation non déterministe" in error
            for error in _errors(broken, transcript)
        )

    def test_une_numerotation_discontinue_est_refusee(self, source_map, transcript):
        ideas = (
            source_map.ideas[0],
            dataclasses.replace(source_map.ideas[1], idea_id="IDEA003"),
        )
        broken = dataclasses.replace(source_map, ideas=ideas)

        assert any("IDEA003" in error for error in _errors(broken, transcript))

    def test_des_identifiants_dupliques_sont_refuses(self, source_map, transcript):
        ideas = (
            source_map.ideas[0],
            dataclasses.replace(source_map.ideas[1], idea_id="IDEA001"),
        )
        broken = dataclasses.replace(source_map, ideas=ideas)

        assert any("dupliqués" in error for error in _errors(broken, transcript))

    def test_un_prefixe_etranger_est_refuse(self, source_map, transcript):
        topics = (dataclasses.replace(source_map.topics[0], topic_id="CH001"),)
        broken = dataclasses.replace(source_map, topics=topics)

        assert any("CH001" in error for error in _errors(broken, transcript))


class TestVocabularyInvariants:
    """Les catégories fermées sont réellement fermées."""

    def test_un_kind_d_idee_inconnu_est_refuse(self, source_map, transcript):
        ideas = (
            dataclasses.replace(source_map.ideas[0], kind="brillante"),
            source_map.ideas[1],
        )
        broken = dataclasses.replace(source_map, ideas=ideas)

        assert any("kind invalide" in error for error in _errors(broken, transcript))

    def test_une_importance_inconnue_est_refusee(self, source_map, transcript):
        ideas = (
            dataclasses.replace(source_map.ideas[0], importance="essentielle"),
            source_map.ideas[1],
        )
        broken = dataclasses.replace(source_map, ideas=ideas)

        assert any(
            "importance invalide" in error for error in _errors(broken, transcript)
        )

    def test_un_kind_d_exemple_inconnu_est_refuse(self, source_map, transcript):
        examples = (dataclasses.replace(source_map.examples[0], kind="histoire"),)
        broken = dataclasses.replace(source_map, examples=examples)

        assert any("kind invalide" in error for error in _errors(broken, transcript))

    def test_un_caractere_de_repetition_inconnu_est_refuse(
        self, source_map, transcript
    ):
        repetitions = (
            dataclasses.replace(source_map.repetitions[0], character="duplicate"),
        )
        broken = dataclasses.replace(source_map, repetitions=repetitions)

        assert any(
            "character invalide" in error for error in _errors(broken, transcript)
        )

    def test_une_relation_inconnue_est_refusee(self, source_map, transcript):
        ideas = (
            source_map.ideas[0],
            dataclasses.replace(
                source_map.ideas[1],
                relations=(IdeaRelation(relation="inspire", to_idea="IDEA001"),),
            ),
        )
        broken = dataclasses.replace(source_map, ideas=ideas)

        assert any(
            "relation invalide" in error for error in _errors(broken, transcript)
        )

    def test_une_relation_sur_soi_meme_est_refusee(self, source_map, transcript):
        ideas = (
            dataclasses.replace(
                source_map.ideas[0],
                relations=(IdeaRelation(relation="supports", to_idea="IDEA001"),),
            ),
            source_map.ideas[1],
        )
        broken = dataclasses.replace(source_map, ideas=ideas)

        assert any(
            "relation sur elle-même" in error for error in _errors(broken, transcript)
        )


class TestReferenceInvariants:
    """Une référence doit conserver ce que l'auteur a dit."""

    def test_une_reference_sans_texte_brut_est_refusee(self, transcript):
        payload = fake_analysis_payload()
        payload["references"] = [
            {
                "reference_id": "r1",
                "kind": "biblical",
                "raw_reference": "Romains 8",
                "normalized_reference": "Romains 8",
                "completeness": "complete",
                "source_refs": ["SRC000002"],
            }
        ]
        source_map = normalize_source_map(
            payload, transcript, provenance=_PROVENANCE
        )
        references = (
            dataclasses.replace(source_map.references[0], raw_reference=""),
        )
        broken = dataclasses.replace(source_map, references=references)

        assert any(
            "raw_reference vide" in error for error in _errors(broken, transcript)
        )

    def test_une_completude_inconnue_est_refusee(self, transcript):
        payload = fake_analysis_payload()
        payload["references"] = [
            {
                "reference_id": "r1",
                "kind": "biblical",
                "raw_reference": "Paul dit quelque part",
                "normalized_reference": "",
                "completeness": "vague",
                "source_refs": ["SRC000002"],
            }
        ]
        source_map = normalize_source_map(
            payload, transcript, provenance=_PROVENANCE
        )
        references = (
            dataclasses.replace(source_map.references[0], completeness="à vérifier"),
        )
        broken = dataclasses.replace(source_map, references=references)

        assert any(
            "completeness invalide" in error for error in _errors(broken, transcript)
        )

    def test_une_reference_vague_est_acceptee_telle_quelle(self, transcript):
        payload = fake_analysis_payload()
        payload["references"] = [
            {
                "reference_id": "r1",
                "kind": "biblical",
                "raw_reference": "Paul dit quelque part",
                "normalized_reference": "",
                "completeness": "vague",
                "source_refs": ["SRC000002"],
            }
        ]
        source_map = normalize_source_map(
            payload, transcript, provenance=_PROVENANCE
        )

        assert _errors(source_map, transcript) == []
        assert source_map.references[0].normalized_reference == ""


class TestRepetitionInvariants:
    """Une reprise relie des passages : elle n'existe pas seule."""

    def test_une_repetition_avec_une_seule_idee_est_refusee(
        self, source_map, transcript
    ):
        repetitions = (
            dataclasses.replace(source_map.repetitions[0], idea_refs=("IDEA001",)),
        )
        broken = dataclasses.replace(source_map, repetitions=repetitions)

        assert any(
            "relie au moins deux" in error for error in _errors(broken, transcript)
        )

    def test_un_developpement_n_est_pas_traite_comme_un_doublon(
        self, source_map, transcript
    ):
        assert source_map.repetitions[0].character == "development"
        assert _errors(source_map, transcript) == []


class TestSourceRefInvariants:
    """Traçabilité et ordre canonique des SRC."""

    def test_un_src_inexistant_est_refuse(self, source_map, transcript):
        ideas = (
            dataclasses.replace(source_map.ideas[0], source_refs=("SRC999999",)),
            source_map.ideas[1],
        )
        broken = dataclasses.replace(source_map, ideas=ideas)

        assert any("SRC999999" in error for error in _errors(broken, transcript))

    def test_un_ordre_non_canonique_est_refuse(self, source_map, transcript):
        ideas = (
            dataclasses.replace(
                source_map.ideas[0], source_refs=("SRC000002", "SRC000001")
            ),
            source_map.ideas[1],
        )
        broken = dataclasses.replace(source_map, ideas=ideas)

        assert any(
            "ordre non canonique" in error for error in _errors(broken, transcript)
        )

    def test_des_src_dupliques_sont_refuses(self, source_map, transcript):
        ideas = (
            dataclasses.replace(
                source_map.ideas[0], source_refs=("SRC000001", "SRC000001")
            ),
            source_map.ideas[1],
        )
        broken = dataclasses.replace(source_map, ideas=ideas)

        assert any(
            "références dupliquées" in error for error in _errors(broken, transcript)
        )

    def test_un_element_sans_src_est_refuse(self, source_map, transcript):
        topics = (dataclasses.replace(source_map.topics[0], source_refs=()),)
        broken = dataclasses.replace(source_map, topics=topics)

        assert any("aucun source_ref" in error for error in _errors(broken, transcript))


class TestStatsInvariants:
    """Les statistiques sont recalculées et comparées."""

    def test_un_compteur_faux_est_refuse(self, source_map, transcript):
        stats = dataclasses.replace(source_map.stats, idea_count=99)
        broken = dataclasses.replace(source_map, stats=stats)

        assert any(
            "stats.idea_count incohérent" in error
            for error in _errors(broken, transcript)
        )

    def test_un_nombre_de_segments_faux_est_refuse(self, source_map, transcript):
        stats = dataclasses.replace(source_map.stats, source_segment_count=3)
        broken = dataclasses.replace(source_map, stats=stats)

        assert any(
            "stats.source_segment_count incohérent" in error
            for error in _errors(broken, transcript)
        )

    def test_une_couverture_fausse_est_refusee(self, source_map, transcript):
        stats = dataclasses.replace(source_map.stats, source_coverage_ratio=1.0)
        broken = dataclasses.replace(source_map, stats=stats)

        assert any(
            "source_coverage_ratio incohérent" in error
            for error in _errors(broken, transcript)
        )

    def test_un_nombre_de_segments_references_faux_est_refuse(
        self, source_map, transcript
    ):
        stats = dataclasses.replace(source_map.stats, referenced_source_segments=8)
        broken = dataclasses.replace(source_map, stats=stats)

        assert any(
            "referenced_source_segments incohérent" in error
            for error in _errors(broken, transcript)
        )


class TestCompletenessGuard:
    """Une source substantielle ne produit pas zéro idée."""

    def test_zero_idee_est_refuse(self, source_map, transcript):
        broken = dataclasses.replace(
            source_map,
            ideas=(),
            examples=(),
            repetitions=(),
            stats=dataclasses.replace(
                source_map.stats,
                idea_count=0,
                example_count=0,
                repetition_count=0,
                referenced_source_segments=3,
                source_coverage_ratio=0.375,
            ),
        )

        assert any("aucune idée" in error for error in _errors(broken, transcript))

    def test_aucune_densite_minimale_n_est_imposee(self, transcript):
        """
        Une seule idée pour huit segments est acceptable : la densité dépend du
        contenu, et « une idée pour trois SRC » serait une règle inventée.
        """
        payload = fake_analysis_payload()
        payload["ideas"] = payload["ideas"][:1]
        payload["examples"][0]["supports_idea_refs"] = ["idea_7"]
        payload["repetitions"] = []

        source_map = normalize_source_map(
            payload, transcript, provenance=_PROVENANCE
        )

        assert _errors(source_map, transcript) == []


class TestEditorialGuard:
    """Barrière Phase 3 / Phase 4 appliquée aussi au fichier publié."""

    def test_un_dictionnaire_sain_passe(self, source_map):
        ensure_no_editorial_fields(source_map.to_dict())

    def test_un_champ_interdit_leve(self):
        with pytest.raises(SourceMapEditorialLeakError) as excinfo:
            ensure_no_editorial_fields({"chapters": []}, location="test")

        assert excinfo.value.location == "test"

    def test_la_publication_refuse_un_source_map_invalide(
        self, source_map, transcript
    ):
        broken = dataclasses.replace(
            source_map,
            source_analysis=dataclasses.replace(
                source_map.source_analysis, main_theme=""
            ),
        )

        with pytest.raises(SourceMapValidationError):
            ensure_valid_source_map(broken, transcript)


class TestPublishedPayload:
    """Un fichier relu est validé par le même validateur."""

    def test_un_payload_nominal_est_valide(self, source_map, transcript):
        assert validate_published_payload(source_map.to_dict(), transcript) == []

    def test_un_payload_non_objet_est_refuse(self, transcript):
        errors = validate_published_payload(["pas un objet"], transcript)

        assert errors
        assert "illisible" in errors[0]

    def test_un_payload_avec_champ_editorial_est_refuse(self, source_map, transcript):
        payload = source_map.to_dict()
        payload["chapters"] = []

        errors = validate_published_payload(payload, transcript)

        assert any("chapters" in error for error in errors)

    def test_un_payload_altere_est_refuse(self, source_map, transcript):
        payload = source_map.to_dict()
        payload["ideas"][0]["source_refs"] = ["SRC999999"]

        errors = validate_published_payload(payload, transcript)

        assert any("SRC999999" in error for error in errors)

    def test_un_payload_vide_est_refuse(self, transcript):
        assert validate_published_payload({}, transcript)
