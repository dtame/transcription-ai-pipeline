"""
Phase 3A.1 — Auditeur bout en bout : transcript_data.json -> language_cleanup.json.

Réutilise les fixtures de app.tests.source_analysis_fixtures pour construire de
VRAIS contrats Transcript V2 (validés par app.transcript_validator), comme le
fait déjà la suite Phase 3. Aucun test ici ne touche à un projet réel : tout
vit dans tmp_path.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.language_cleanup.auditor import run_audit
from app.language_cleanup.models import (
    DECISION_KEEP,
    DECISION_REMOVE_TRANSLATION,
    DECISION_REVIEW,
    LANGUAGE_EN,
    LANGUAGE_FR,
    LANGUAGE_MIXED,
    LANGUAGE_UNKNOWN,
    MATCH_AFTER,
    MATCH_BEFORE,
    MATCH_BOTH,
)
from app.language_cleanup.transcript_source import compute_file_sha256
from app.tests.source_analysis_fixtures import build_transcript_document, write_transcript

PROJECT = "audit_demo"


def _run(tmp_path, texts, *, language="en"):
    document = build_transcript_document(
        project_name=PROJECT, texts=texts, language=language
    )
    transcripts_dir = tmp_path / "sortie" / PROJECT / "transcripts"
    write_transcript(transcripts_dir, document)

    result = run_audit(
        PROJECT,
        sortie_dir=tmp_path / "sortie",
        write=True,
    )
    return result, transcripts_dir


def _by_ref(result):
    return {segment.source_ref: segment for segment in result.manifest.segments}


class TestClearEnglishKept:
    """Scénario 1 : anglais clair -> EN / KEEP."""

    def test_english_segments_are_kept(self, tmp_path):
        result, _ = _run(
            tmp_path,
            (
                "God wants you to understand the authority he has given you.",
                "This is important for your life and for your ministry.",
            ),
        )
        for segment in result.manifest.segments:
            assert segment.language == LANGUAGE_EN
            assert segment.decision == DECISION_KEEP
            assert segment.matched_english_source_refs == ()
            assert segment.match_direction is None


class TestClearFrenchWithoutDemonstratedTranslation:
    """Scénario 2 : français clair sans traduction démontrée -> jamais REMOVE."""

    def test_never_removed_without_relation(self, tmp_path):
        result, _ = _run(
            tmp_path,
            (
                "God wants you to understand the authority he has given you.",
                "Nous allons maintenant lire Jean chapitre trois pour commencer.",
            ),
        )
        by_ref = _by_ref(result)
        fr_segment = by_ref["SRC000002"]
        assert fr_segment.language == LANGUAGE_FR
        assert fr_segment.decision != DECISION_REMOVE_TRANSLATION
        assert fr_segment.decision in (DECISION_KEEP, DECISION_REVIEW)


class TestEnglishThenFrenchTranslation:
    """Scénario 3 : EN puis traduction FR claire -> FR / REMOVE_TRANSLATION / BEFORE."""

    def test_translation_after_english_is_flagged_before(self, tmp_path):
        result, _ = _run(
            tmp_path,
            (
                "God wants you to understand the authority he has given you.",
                "Dieu veut que vous compreniez l'autorité qu'il vous a donnée.",
            ),
        )
        by_ref = _by_ref(result)

        assert by_ref["SRC000001"].decision == DECISION_KEEP
        fr_segment = by_ref["SRC000002"]
        assert fr_segment.language == LANGUAGE_FR
        assert fr_segment.decision == DECISION_REMOVE_TRANSLATION
        assert fr_segment.match_direction == MATCH_BEFORE
        assert "SRC000001" in fr_segment.matched_english_source_refs
        assert fr_segment.translation_confidence >= 0.60


class TestFrenchTranslationThenEnglish:
    """Scénario 4 : traduction FR puis EN clair -> FR / REMOVE_TRANSLATION / AFTER."""

    def test_translation_before_english_is_flagged_after(self, tmp_path):
        result, _ = _run(
            tmp_path,
            (
                "Dieu veut que vous compreniez l'autorité qu'il vous a donnée.",
                "God wants you to understand the authority he has given you.",
            ),
        )
        by_ref = _by_ref(result)

        fr_segment = by_ref["SRC000001"]
        assert fr_segment.language == LANGUAGE_FR
        assert fr_segment.decision == DECISION_REMOVE_TRANSLATION
        assert fr_segment.match_direction == MATCH_AFTER
        assert "SRC000002" in fr_segment.matched_english_source_refs


class TestMultipleEnglishThenMultipleFrenchTranslation:
    """Scénario 5 : plusieurs EN puis plusieurs FR correspondants -> groupe reconnu."""

    def test_group_is_recognised_as_one_block(self, tmp_path):
        result, _ = _run(
            tmp_path,
            (
                "God wants you to understand the authority he has given you.",
                "This is important for your life and for your ministry.",
                "Dieu veut que vous compreniez l'autorité qu'il vous a donnée.",
                "Ceci est important pour votre vie et pour votre ministère.",
            ),
        )
        by_ref = _by_ref(result)

        for ref in ("SRC000003", "SRC000004"):
            segment = by_ref[ref]
            assert segment.language == LANGUAGE_FR
            assert segment.decision == DECISION_REMOVE_TRANSLATION
            assert segment.match_direction == MATCH_BEFORE
            # Le bloc EN entier (les deux SRC) est référencé, pas un seul SRC.
            assert set(segment.matched_english_source_refs) == {
                "SRC000001",
                "SRC000002",
            }


class TestFrenchNotMatchingNeighbour:
    """Scénario 6 : FR ne correspondant pas à l'anglais voisin -> pas REMOVE."""

    def test_unrelated_french_between_two_unrelated_english_blocks(self, tmp_path):
        result, _ = _run(
            tmp_path,
            (
                "This is important for your life and for your ministry.",
                "Nous allons maintenant lire Jean chapitre trois pour commencer.",
                "The weather today is quite pleasant for our outdoor session.",
            ),
        )
        by_ref = _by_ref(result)
        fr_segment = by_ref["SRC000002"]
        assert fr_segment.decision != DECISION_REMOVE_TRANSLATION


class TestMixedIsAlwaysReview:
    """Scénario 7 : MIXED -> REVIEW."""

    def test_mixed_segment_is_review(self, tmp_path):
        result, _ = _run(
            tmp_path,
            (
                "God wants you to understand the authority he has given you.",
                "The Lord and the King is with us and for us, il est avec "
                "nous et il est pour nous aussi.",
            ),
        )
        by_ref = _by_ref(result)
        mixed_segment = by_ref["SRC000002"]
        assert mixed_segment.language == LANGUAGE_MIXED
        assert mixed_segment.decision == DECISION_REVIEW


class TestUnknownIsNeverRemoved:
    """Scénario 8 : UNKNOWN -> jamais REMOVE_TRANSLATION."""

    def test_unknown_segment_between_translations_is_kept(self, tmp_path):
        result, _ = _run(
            tmp_path,
            (
                "God wants you to understand the authority he has given you.",
                "Amen.",
                "Dieu veut que vous compreniez l'autorité qu'il vous a donnée.",
            ),
        )
        by_ref = _by_ref(result)
        unknown_segment = by_ref["SRC000002"]
        assert unknown_segment.language == LANGUAGE_UNKNOWN
        assert unknown_segment.decision != DECISION_REMOVE_TRANSLATION
        assert unknown_segment.decision == DECISION_KEEP


class TestProperNounsDoNotCreateFalsePositives:
    """Scénario 9 : nom propre / référence biblique -> pas de faux FR/EN."""

    def test_bare_reference_between_english_segments_stays_unknown_and_kept(
        self, tmp_path
    ):
        result, _ = _run(
            tmp_path,
            (
                "This is important for your life and for your ministry.",
                "Jean 3:16.",
                "The weather today is quite pleasant for our outdoor session.",
            ),
        )
        by_ref = _by_ref(result)
        reference_segment = by_ref["SRC000002"]
        assert reference_segment.language == LANGUAGE_UNKNOWN
        assert reference_segment.decision == DECISION_KEEP


class TestEnglishTextNeverModified:
    """Scénario 10 : aucun texte anglais n'est modifié, réécrit ou fusionné."""

    def test_english_text_is_recopied_byte_identical(self, tmp_path):
        texts = (
            "God wants you to understand the authority he has given you.",
            "This is important for your life and for your ministry.",
        )
        result, _ = _run(tmp_path, texts)

        for segment, original_text in zip(result.manifest.segments, texts):
            assert segment.language == LANGUAGE_EN
            assert segment.text == original_text


class TestNoSrcRenumbered:
    """Scénario 11 : aucun SRC n'est renuméroté, créé ou fusionné."""

    def test_source_refs_match_original_transcript_exactly(self, tmp_path):
        texts = (
            "God wants you to understand the authority he has given you.",
            "Dieu veut que vous compreniez l'autorité qu'il vous a donnée.",
            "This is important for your life and for your ministry.",
        )
        result, _ = _run(tmp_path, texts)

        expected_refs = [f"SRC{i:06d}" for i in range(1, len(texts) + 1)]
        actual_refs = [segment.source_ref for segment in result.manifest.segments]

        assert actual_refs == expected_refs


class TestMatchedRefsAreValid:
    """Scénario 12 : les matched refs pointent toujours vers un SRC existant local."""

    def test_matched_refs_exist_in_transcript(self, tmp_path):
        texts = (
            "God wants you to understand the authority he has given you.",
            "Dieu veut que vous compreniez l'autorité qu'il vous a donnée.",
        )
        result, _ = _run(tmp_path, texts)

        valid_refs = {segment.source_ref for segment in result.manifest.segments}

        for segment in result.manifest.segments:
            for ref in segment.matched_english_source_refs:
                assert ref in valid_refs


class TestManifestIsDeterministic:
    """Scénario 13 : deux audits successifs produisent le même contenu canonique."""

    def test_two_runs_produce_identical_canonical_manifest(self, tmp_path):
        texts = (
            "God wants you to understand the authority he has given you.",
            "Dieu veut que vous compreniez l'autorité qu'il vous a donnée.",
            "Nous allons maintenant lire Jean chapitre trois pour commencer.",
            "Amen.",
        )
        document = build_transcript_document(project_name=PROJECT, texts=texts)
        transcripts_dir = tmp_path / "sortie" / PROJECT / "transcripts"
        write_transcript(transcripts_dir, document)

        first = run_audit(PROJECT, sortie_dir=tmp_path / "sortie", write=False)
        second = run_audit(PROJECT, sortie_dir=tmp_path / "sortie", write=False)

        assert first.manifest.canonical_dict() == second.manifest.canonical_dict()


class TestTranscriptSourceUnchanged:
    """Scénario 14 : le transcript source n'est jamais modifié par l'audit."""

    def test_transcript_data_json_untouched(self, tmp_path):
        texts = (
            "God wants you to understand the authority he has given you.",
            "Dieu veut que vous compreniez l'autorité qu'il vous a donnée.",
        )
        result, transcripts_dir = _run(tmp_path, texts)

        transcript_path = transcripts_dir / "transcript_data.json"
        sha_after = compute_file_sha256(transcript_path)

        assert sha_after == result.transcript.content_sha256

    def test_no_txt_file_is_created_by_the_audit(self, tmp_path):
        texts = ("God wants you to understand the authority he has given you.",)
        _result, transcripts_dir = _run(tmp_path, texts)

        assert not (transcripts_dir / "transcript.txt").exists()


class TestAuditWritesOnlyUnderAuditDirectory:
    def test_manifest_is_written_under_audit_dir(self, tmp_path):
        texts = ("God wants you to understand the authority he has given you.",)
        result, _ = _run(tmp_path, texts)

        assert result.output_path is not None
        assert result.output_path.parent.name == "audit"
        assert result.output_path.name == "language_cleanup.json"
        assert result.output_path.exists()


class TestNoNetworkCalls:
    def test_result_reports_zero_network_calls(self, tmp_path):
        texts = ("God wants you to understand the authority he has given you.",)
        result, _ = _run(tmp_path, texts)

        assert result.anthropic_calls == 0
        assert result.openai_calls == 0
        assert result.whisper_calls == 0
        assert result.other_network_calls == 0
