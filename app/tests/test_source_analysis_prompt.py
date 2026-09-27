"""
Prompt du Source Analyzer : rôle, langue, traçabilité, interdictions.

Le test le plus important de ce fichier est le garde-fou de structure : hors du
bloc qui les interdit, le prompt ne prononce jamais les mots « chapitre »,
« table des matières » ou « titre du livre ». Un prompt qui demanderait, même de
biais, un découpage de livre ferait franchir la frontière Phase 3 / Phase 4 sans
que personne l'ait décidé.

Ce qui est testé ici, ce sont les INSTRUCTIONS GÉNÉRÉES, pas la qualité
linguistique d'une réponse simulée.
"""

from __future__ import annotations

import pytest

from app.source_analysis.prompt import (
    FORBIDDEN_STRUCTURE_BLOCK,
    SOURCE_ANALYZER_PROMPT_VERSION,
    STRUCTURAL_VOCABULARY,
    build_language_directive,
    build_system_prompt,
    build_user_prompt,
    language_label,
    render_segment,
    render_segments,
)
from app.source_analysis.transcript_input import (
    SourceSegment,
    load_transcript_input,
    transcript_data_file,
)
from app.tests.source_analysis_fixtures import (  # noqa: F401 — fixture pytest
    analysis_env,
    build_transcript_document,
    write_transcript,
)


def _load(env) -> "object":
    return load_transcript_input(
        transcript_data_file(env.transcripts_dir),
        project_name=env.project_name,
    )


class TestPromptVersion:
    """Le prompt est un contrat versionné."""

    def test_la_version_est_declaree(self):
        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"

    def test_la_version_est_une_chaine_non_vide(self):
        assert isinstance(SOURCE_ANALYZER_PROMPT_VERSION, str)
        assert SOURCE_ANALYZER_PROMPT_VERSION.strip()


class TestNoChapters:
    """Garde-fou : le prompt ne demande jamais de structure de livre."""

    def test_le_vocabulaire_de_structure_est_confine_au_bloc_d_interdiction(self):
        prompt = build_system_prompt("fr")
        outside = prompt.replace(FORBIDDEN_STRUCTURE_BLOCK, "").lower()

        leaked = [word for word in STRUCTURAL_VOCABULARY if word in outside]

        assert leaked == []

    def test_le_prompt_utilisateur_ne_mentionne_aucune_structure_de_livre(
        self, analysis_env
    ):
        user_prompt = build_user_prompt(_load(analysis_env)).lower()

        leaked = [word for word in STRUCTURAL_VOCABULARY if word in user_prompt]

        assert leaked == []

    def test_le_bloc_d_interdiction_est_bien_present(self):
        assert FORBIDDEN_STRUCTURE_BLOCK in build_system_prompt("fr")

    @pytest.mark.parametrize(
        "phrase",
        [
            "crée des chapitres",
            "propose un découpage en chapitres",
            "génère une table des matières",
            "create chapters",
            "book structure",
            "table of contents:",
            "chapter title",
            "section title",
            "propose un titre",
        ],
    )
    def test_aucune_demande_de_structure(self, analysis_env, phrase):
        prompt = build_system_prompt("fr") + build_user_prompt(_load(analysis_env))

        assert phrase not in prompt.lower()

    def test_le_prompt_dit_explicitement_qu_un_theme_n_est_pas_un_chapitre(self):
        assert "Un thème n'est pas un chapitre" in build_system_prompt("fr")


class TestRole:
    """Analyste de source : ni auteur, ni éditeur, ni vérificateur de faits."""

    def test_le_role_est_annonce(self):
        prompt = build_system_prompt("fr")

        assert "ANALYSTE DE SOURCE" in prompt
        assert "que contient et que signifie cette\nsource" in prompt

    def test_les_trois_casquettes_refusees_sont_nommees(self):
        prompt = build_system_prompt("fr")

        assert "Tu n'es pas :" in prompt
        assert "l'auteur" in prompt
        assert "l'éditeur du livre" in prompt
        assert "vérificateur de faits" in prompt

    def test_la_fidelite_est_posee_comme_regle_principale(self):
        prompt = build_system_prompt("fr")

        assert "Grande liberté d'analyse, liberté sémantique nulle." in prompt
        assert "inventer" in prompt
        assert "corriger silencieusement" in prompt

    def test_l_exemple_de_reference_vague_est_donne(self):
        prompt = build_system_prompt("fr")

        assert "Paul dit quelque part" in prompt
        assert "Romains 8:28" in prompt

    def test_les_horodatages_ne_doivent_pas_structurer_l_analyse(self):
        prompt = build_system_prompt("fr")

        assert "Les horodatages servent uniquement à la provenance." in prompt

    def test_la_comprehension_globale_est_demandee(self):
        assert "COMPRÉHENSION GLOBALE" in build_system_prompt("fr")

    def test_aucune_recherche_externe_n_est_evoquee(self):
        prompt = build_system_prompt("fr").lower()

        for term in ("internet", "wikipédia", "web search", "recherche en ligne"):
            assert term not in prompt


class TestLanguage:
    """La langue de sortie suit language.primary du transcript."""

    def test_un_transcript_francais_demande_une_analyse_en_francais(
        self, analysis_env
    ):
        transcript = _load(analysis_env)
        prompt = build_system_prompt(transcript.primary_language)

        assert "LANGUE DE SORTIE OBLIGATOIRE : français" in prompt
        assert "anglais" not in prompt

    def test_un_transcript_anglais_demande_une_analyse_en_anglais(
        self, analysis_env
    ):
        analysis_env.rewrite_transcript(
            build_transcript_document(
                project_name=analysis_env.project_name,
                language="en",
            )
        )
        transcript = _load(analysis_env)
        prompt = build_system_prompt(transcript.primary_language)

        assert "LANGUE DE SORTIE OBLIGATOIRE : anglais" in prompt
        assert "français" not in prompt

    def test_la_consigne_interdit_la_traduction_de_la_source(self):
        directive = build_language_directive("fr")

        assert "Tu ne traduis pas la source." in directive
        assert "restent dans leur langue d'origine" in directive

    def test_une_langue_inconnue_est_citee_par_son_code(self):
        assert language_label("pt-BR") == "« pt-BR »"
        assert "« pt-BR »" in build_language_directive("pt-BR")

    def test_les_langues_courantes_sont_nommees(self):
        assert language_label("fr") == "français"
        assert language_label("en") == "anglais"
        assert language_label("es") == "espagnol"

    def test_la_consigne_de_langue_est_presente_dans_les_deux_prompts(
        self, analysis_env
    ):
        transcript = _load(analysis_env)

        assert "LANGUE DE SORTIE OBLIGATOIRE" in build_system_prompt(
            transcript.primary_language
        )
        assert "LANGUE DE SORTIE OBLIGATOIRE" in build_user_prompt(transcript)


class TestTranscriptRendering:
    """La représentation envoyée au modèle conserve les identifiants SRC."""

    def test_un_segment_porte_son_src_sa_source_et_ses_bornes(self):
        segment = SourceSegment(
            src_id="SRC000001",
            source_id="AUDIO001",
            start=0.0,
            end=11.42,
            text="Texte du segment.",
        )

        assert render_segment(segment) == (
            "[SRC000001 | AUDIO001 | 0.000-11.420]\nTexte du segment."
        )

    def test_tous_les_src_du_transcript_sont_presents(self, analysis_env):
        transcript = _load(analysis_env)
        rendered = render_segments(transcript.segments)

        for segment in transcript.segments:
            assert f"[{segment.src_id} |" in rendered

    def test_les_segments_sont_separes_par_une_ligne_vide(self, analysis_env):
        transcript = _load(analysis_env)

        assert "\n\n[SRC000002 |" in render_segments(transcript.segments)

    def test_le_prompt_utilisateur_contient_la_transcription_complete(
        self, analysis_env
    ):
        transcript = _load(analysis_env)
        prompt = build_user_prompt(transcript)

        assert "TRANSCRIPTION — TR001 — 8 segment(s) source" in prompt

        for segment in transcript.segments:
            assert segment.text in prompt

    def test_le_json_canonique_n_est_pas_envoye_tel_quel(self, analysis_env):
        prompt = build_user_prompt(_load(analysis_env))

        assert '"schema_version"' not in prompt
        assert '"source_order"' not in prompt

    def test_une_fenetre_de_segments_peut_etre_soumise_seule(self, analysis_env):
        transcript = _load(analysis_env)
        prompt = build_user_prompt(transcript, transcript.segments[:2])

        assert "2 segment(s) source" in prompt
        assert "SRC000003" not in prompt

    def test_la_tache_enumere_les_sections_attendues(self, analysis_env):
        prompt = build_user_prompt(_load(analysis_env))

        for section in (
            "main_theme",
            "author_intent",
            "target_audience",
            "topics",
            "ideas",
            "examples",
            "references",
            "uncertainties",
            "repetitions",
            "author_voice_profile",
        ):
            assert section in prompt

    def test_les_questions_ont_une_seule_representation(self, analysis_env):
        prompt = build_user_prompt(_load(analysis_env))

        assert 'kind="question"' in prompt
        assert "Il n'existe pas d'autre emplacement pour elles." in prompt

    def test_aucun_conseil_de_reecriture_pour_le_profil_de_voix(self, analysis_env):
        prompt = build_user_prompt(_load(analysis_env)).lower()

        for phrase in ("improve by", "should avoid", "rewrite as", "réécris"):
            assert phrase not in prompt

    def test_aucun_diagnostic_psychologique_n_est_demande(self, analysis_env):
        prompt = build_user_prompt(_load(analysis_env))

        assert "Aucune hypothèse sur la" in prompt
        assert "personnalité" in prompt
