"""
Source de vérité de la Phase 3 : transcript_data.json, et rien d'autre.

Ces tests verrouillent deux choses :

1. le contrat Transcript V2 est lu tel qu'il est publié, sans être modifié ;
2. aucun artefact V1 (merged/, chunks/, processed/, reviewed/, final/,
   publication/) n'alimente l'analyse — pas même document_final.md.
"""

from __future__ import annotations

import json

import pytest

from app.source_analysis.transcript_input import (
    SUBSTANTIAL_WORD_THRESHOLD,
    load_transcript_input,
    transcript_data_file,
)
from app.source_analysis.errors import SourceTranscriptError
from app.tests.source_analysis_fixtures import (  # noqa: F401 — fixture pytest
    analysis_env,
    build_transcript_document,
    write_transcript,
)


def _load(env):
    return load_transcript_input(
        transcript_data_file(env.transcripts_dir),
        project_name=env.project_name,
    )


class TestLoading:
    """Lecture fidèle du contrat V2."""

    def test_les_identifiants_et_la_langue_sont_lus(self, analysis_env):
        transcript = _load(analysis_env)

        assert transcript.transcript_id == "TR001"
        assert transcript.primary_language == "fr"
        assert transcript.detected_languages == ("fr",)
        assert transcript.schema_version == "1.0"

    def test_les_segments_conservent_leurs_src_et_bornes(self, analysis_env):
        transcript = _load(analysis_env)

        assert transcript.segment_count == 8
        assert transcript.segments[0].src_id == "SRC000001"
        assert transcript.segments[0].source_id == "AUDIO001"
        assert transcript.segments[0].start == 0.0
        assert transcript.segments[0].end == 10.0

    def test_l_index_canonique_suit_l_ordre_du_fichier(self, analysis_env):
        index = _load(analysis_env).src_index()

        assert index["SRC000001"] == 0
        assert index["SRC000008"] == 7

    def test_le_hash_du_fichier_est_calcule(self, analysis_env):
        transcript = _load(analysis_env)

        assert len(transcript.content_sha256) == 64

    def test_le_hash_change_avec_le_contenu(self, analysis_env):
        before = _load(analysis_env).content_sha256

        analysis_env.rewrite_transcript(
            build_transcript_document(
                project_name=analysis_env.project_name,
                texts=(
                    "Un texte entièrement différent pour changer le contenu du fichier.",
                    "Une deuxième phrase pour rester au-dessus du seuil de substance.",
                    "Une troisième phrase pour compléter la source de ce test précis.",
                    "Une quatrième phrase afin de dépasser confortablement le seuil.",
                ),
            )
        )

        assert _load(analysis_env).content_sha256 != before

    def test_le_transcript_n_est_jamais_modifie(self, analysis_env):
        before = analysis_env.transcript_path.read_bytes()

        _load(analysis_env)

        assert analysis_env.transcript_path.read_bytes() == before


class TestSubstantiality:
    """Distinguer « rien » de « quelque chose »."""

    def test_le_transcript_de_reference_est_substantiel(self, analysis_env):
        assert _load(analysis_env).is_substantial is True

    def test_un_transcript_de_quelques_mots_ne_l_est_pas(self, analysis_env):
        analysis_env.rewrite_transcript(
            build_transcript_document(
                project_name=analysis_env.project_name,
                texts=("Euh.", "Bon.", "Hmm."),
            )
        )
        transcript = _load(analysis_env)

        assert transcript.word_count == 3
        assert transcript.is_substantial is False

    def test_le_seuil_est_explicite(self):
        assert SUBSTANTIAL_WORD_THRESHOLD == 30

    def test_le_compte_de_mots_suit_les_segments(self, analysis_env):
        transcript = _load(analysis_env)

        assert transcript.word_count == sum(
            len(segment.text.split()) for segment in transcript.segments
        )


class TestRejections:
    """Un contrat absent ou abîmé n'est pas deviné."""

    def test_un_fichier_absent_est_refuse(self, tmp_path):
        with pytest.raises(SourceTranscriptError) as excinfo:
            load_transcript_input(
                transcript_data_file(tmp_path), project_name="demo"
            )

        assert "introuvable" in str(excinfo.value)
        assert "artefacts V1" in str(excinfo.value)

    def test_un_json_invalide_est_refuse(self, tmp_path):
        path = transcript_data_file(tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)
        path.write_text("{ cassé", encoding="utf-8")

        with pytest.raises(SourceTranscriptError) as excinfo:
            load_transcript_input(path, project_name="demo")

        assert "illisible" in str(excinfo.value)

    def test_une_version_de_contrat_inconnue_est_refusee(self, analysis_env):
        payload = json.loads(
            analysis_env.transcript_path.read_text(encoding="utf-8")
        )
        payload["schema_version"] = "2.0"
        analysis_env.transcript_path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

        with pytest.raises(SourceTranscriptError) as excinfo:
            _load(analysis_env)

        assert "Version de contrat Transcript inattendue" in str(excinfo.value)

    def test_un_transcript_sans_segment_est_refuse(self, analysis_env):
        payload = json.loads(
            analysis_env.transcript_path.read_text(encoding="utf-8")
        )
        payload["segments"] = []
        analysis_env.transcript_path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

        with pytest.raises(SourceTranscriptError) as excinfo:
            _load(analysis_env)

        assert "aucun segment source" in str(excinfo.value)

    def test_une_langue_principale_absente_est_refusee(self, analysis_env):
        payload = json.loads(
            analysis_env.transcript_path.read_text(encoding="utf-8")
        )
        payload["language"]["primary"] = ""
        analysis_env.transcript_path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

        with pytest.raises(SourceTranscriptError) as excinfo:
            _load(analysis_env)

        assert "language.primary absent" in str(excinfo.value)

    def test_un_transcript_id_absent_est_refuse(self, analysis_env):
        payload = json.loads(
            analysis_env.transcript_path.read_text(encoding="utf-8")
        )
        payload["transcript_id"] = ""
        analysis_env.transcript_path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

        with pytest.raises(SourceTranscriptError) as excinfo:
            _load(analysis_env)

        assert "transcript_id absent" in str(excinfo.value)

    def test_des_src_dupliques_sont_refuses(self, analysis_env):
        payload = json.loads(
            analysis_env.transcript_path.read_text(encoding="utf-8")
        )
        payload["segments"][1]["id"] = payload["segments"][0]["id"]
        analysis_env.transcript_path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

        with pytest.raises(SourceTranscriptError) as excinfo:
            _load(analysis_env)

        assert "dupliqué" in str(excinfo.value)


class TestNoV1Contamination:
    """Les artefacts V1 ne doivent jamais alimenter l'analyse."""

    def test_aucun_repertoire_v1_n_est_reference_dans_le_paquet(self):
        import inspect
        import pkgutil

        import app.source_analysis as package

        offenders: list[str] = []

        for module_info in pkgutil.iter_modules(package.__path__):
            module = __import__(
                f"app.source_analysis.{module_info.name}",
                fromlist=["_"],
            )
            source = inspect.getsource(module)
            body = source.replace(module.__doc__ or "", "")

            for artefact in (
                '"merged"',
                '"chunks"',
                '"processed"',
                '"reviewed"',
                '"final"',
                '"publication"',
                "document_final.md",
                "document_clean.md",
            ):
                if artefact in body:
                    offenders.append(f"{module_info.name}: {artefact}")

        assert offenders == []

    def test_un_document_final_v1_present_est_ignore(
        self, analysis_env, no_ai_network
    ):
        """
        Un projet peut très bien porter des artefacts V1 : ils ne doivent avoir
        aucun effet sur l'analyse.
        """
        from app.source_analysis.analyzer import analyze_source
        from app.tests.source_analysis_fixtures import fake_engine

        final_dir = analysis_env.sortie / analysis_env.project_name / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        (final_dir / "document_final.md").write_text(
            "# Chapitre 1\n\nContenu V1 sans rapport avec la source.\n",
            encoding="utf-8",
        )

        engine = fake_engine()
        analyze_source(analysis_env.project_name, engine=engine)

        prompt = engine.last_request.prompt

        assert "Contenu V1" not in prompt
        assert "Chapitre 1" not in prompt

    def test_l_analyse_ne_lit_que_le_transcript(self, analysis_env, no_ai_network):
        from app.source_analysis.analyzer import analyze_source
        from app.tests.source_analysis_fixtures import fake_engine

        engine = fake_engine()
        analyze_source(analysis_env.project_name, engine=engine)

        prompt = engine.last_request.prompt

        for segment in _load(analysis_env).segments:
            assert segment.text in prompt
