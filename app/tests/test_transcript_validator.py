"""
Phase 1 — Validation du contrat Transcript V2 (§29, §46).

Chaque invariant est vérifié par un document délibérément invalide : la
validation doit le refuser. Un transcript_data.json ne doit jamais être publié
puis déclaré valide sans avoir satisfait l'ensemble de ces règles.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.transcript_models import (
    TranscriptDocument,
    TranscriptSegment,
    TranscriptSource,
    TranscriptStats,
)
from app.transcript_validator import (
    TranscriptValidationError,
    ensure_valid_transcript_document,
    validate_transcript_document,
)


def _stats_for(sources, segments):
    return TranscriptStats(
        source_count=len(sources),
        segment_count=len(segments),
        duration_seconds=round(sum(s.duration_seconds for s in sources), 3),
        word_count=sum(len(s.text.split()) for s in segments),
    )


def valid_document() -> TranscriptDocument:
    sources = [
        TranscriptSource("AUDIO001", 1, "a.mp3", 300.0, "fr"),
        TranscriptSource("AUDIO002", 2, "b.mp3", 600.0, "en"),
    ]
    segments = [
        TranscriptSegment("SRC000001", "AUDIO001", 1, 0.0, 5.0, "premier segment"),
        TranscriptSegment("SRC000002", "AUDIO001", 1, 5.0, 9.5, "deuxième segment"),
        TranscriptSegment("SRC000003", "AUDIO002", 2, 0.0, 4.0, "third segment"),
    ]

    return TranscriptDocument(
        project_name="demo",
        sources=sources,
        segments=segments,
        stats=_stats_for(sources, segments),
        primary_language="fr",
        detected_languages=["en", "fr"],
    )


def _with(document: TranscriptDocument, **changes) -> TranscriptDocument:
    return dataclasses.replace(document, **changes)


def _errors(document) -> str:
    return " | ".join(validate_transcript_document(document))


# ---------------------------------------------------------------------------
# Document valide
# ---------------------------------------------------------------------------

class TestValidDocument:

    def test_a_correct_document_has_no_violation(self):
        assert validate_transcript_document(valid_document()) == []

    def test_ensure_does_not_raise_on_a_correct_document(self):
        ensure_valid_transcript_document(valid_document())

    def test_a_single_source_single_segment_document_is_valid(self):
        sources = [TranscriptSource("AUDIO001", 1, "a.mp3", 10.0, "fr")]
        segments = [TranscriptSegment("SRC000001", "AUDIO001", 1, 0.0, 1.0, "ok")]

        document = TranscriptDocument(
            project_name="demo",
            sources=sources,
            segments=segments,
            stats=_stats_for(sources, segments),
            primary_language="fr",
            detected_languages=["fr"],
        )

        assert validate_transcript_document(document) == []


# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------

class TestHeaderInvariants:

    def test_missing_schema_version_is_refused(self):
        assert "schema_version absent" in _errors(
            _with(valid_document(), schema_version="")
        )

    def test_unexpected_schema_version_is_refused(self):
        assert "schema_version inattendu" in _errors(
            _with(valid_document(), schema_version="0.9")
        )

    def test_missing_transcript_id_is_refused(self):
        assert "transcript_id absent" in _errors(
            _with(valid_document(), transcript_id="")
        )

    def test_missing_project_name_is_refused(self):
        assert "nom de projet absent" in _errors(
            _with(valid_document(), project_name="")
        )


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

class TestSourceInvariants:

    def test_empty_sources_are_refused(self):
        document = valid_document()
        document.sources = []

        assert "aucune source audio" in _errors(document)

    def test_duplicated_source_id_is_refused(self):
        document = valid_document()
        document.sources[1] = TranscriptSource("AUDIO001", 2, "b.mp3", 600.0, "en")

        assert "source_id dupliqué : AUDIO001" in _errors(document)

    def test_duplicated_source_order_is_refused(self):
        document = valid_document()
        document.sources[1] = TranscriptSource("AUDIO002", 1, "b.mp3", 600.0, "en")

        assert "source_order dupliqué : 1" in _errors(document)

    def test_non_continuous_source_order_is_refused(self):
        document = valid_document()
        document.sources[1] = TranscriptSource("AUDIO003", 3, "b.mp3", 600.0, "en")
        document.segments[2] = TranscriptSegment(
            "SRC000003", "AUDIO003", 3, 0.0, 4.0, "third segment"
        )

        assert "source_order non continu" in _errors(document)

    def test_source_id_inconsistent_with_its_order_is_refused(self):
        document = valid_document()
        document.sources[1] = TranscriptSource("AUDIO007", 2, "b.mp3", 600.0, "en")

        assert "source_id incohérent avec son ordre" in _errors(document)

    def test_missing_filename_is_refused(self):
        document = valid_document()
        document.sources[0] = TranscriptSource("AUDIO001", 1, "", 300.0, "fr")

        assert "filename absent" in _errors(document)

    @pytest.mark.parametrize(
        "filename",
        [r"C:\TranscriptionAI\depot\a.mp3", "depot/retreat/a.mp3"],
    )
    def test_absolute_or_relative_path_as_filename_is_refused(self, filename):
        document = valid_document()
        document.sources[0] = TranscriptSource("AUDIO001", 1, filename, 300.0, "fr")

        assert "filename doit rester portable" in _errors(document)

    def test_negative_source_duration_is_refused(self):
        document = valid_document()
        document.sources[0] = TranscriptSource("AUDIO001", 1, "a.mp3", -1.0, "fr")

        assert "duration_seconds négative" in _errors(document)

    def test_missing_source_language_is_refused(self):
        document = valid_document()
        document.sources[0] = TranscriptSource("AUDIO001", 1, "a.mp3", 300.0, "")

        assert "detected_language absente" in _errors(document)


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------

class TestSegmentInvariants:

    def test_duplicated_src_id_is_refused(self):
        document = valid_document()
        document.segments[1] = TranscriptSegment(
            "SRC000001", "AUDIO001", 1, 5.0, 9.5, "deuxième segment"
        )

        errors = _errors(document)
        assert "identifiant SRC dupliqué : SRC000001" in errors

    def test_non_continuous_src_id_is_refused(self):
        document = valid_document()
        document.segments[1] = TranscriptSegment(
            "SRC000009", "AUDIO001", 1, 5.0, 9.5, "deuxième segment"
        )

        assert "identifiant SRC non continu en position 2" in _errors(document)

    def test_unknown_audio_reference_is_refused(self):
        document = valid_document()
        document.segments[2] = TranscriptSegment(
            "SRC000003", "AUDIO404", 2, 0.0, 4.0, "third segment"
        )

        assert "référence une source inconnue : AUDIO404" in _errors(document)

    def test_source_order_inconsistent_with_the_source_is_refused(self):
        document = valid_document()
        document.segments[2] = TranscriptSegment(
            "SRC000003", "AUDIO002", 1, 0.0, 4.0, "third segment"
        )

        assert "incohérent avec AUDIO002" in _errors(document)

    def test_negative_start_is_refused(self):
        document = valid_document()
        document.segments[0] = TranscriptSegment(
            "SRC000001", "AUDIO001", 1, -0.5, 5.0, "premier segment"
        )

        assert "start négatif" in _errors(document)

    def test_end_before_start_is_refused(self):
        document = valid_document()
        document.segments[0] = TranscriptSegment(
            "SRC000001", "AUDIO001", 1, 10.0, 4.0, "premier segment"
        )

        assert "antérieur à start" in _errors(document)

    def test_empty_text_is_refused(self):
        document = valid_document()
        document.segments[0] = TranscriptSegment(
            "SRC000001", "AUDIO001", 1, 0.0, 5.0, "   "
        )

        assert "text vide" in _errors(document)

    def test_non_string_text_is_refused_without_crashing_the_validator(self):
        document = valid_document()
        document.segments[0] = TranscriptSegment(
            "SRC000001", "AUDIO001", 1, 0.0, 5.0, 42
        )

        assert "text n'est pas une chaîne" in _errors(document)

    def test_decreasing_chronology_within_a_source_is_refused(self):
        document = valid_document()
        document.segments[1] = TranscriptSegment(
            "SRC000002", "AUDIO001", 1, 0.0, 9.5, "deuxième segment"
        )
        document.segments[1] = TranscriptSegment(
            "SRC000002", "AUDIO001", 1, -0.0, 9.5, "deuxième segment"
        )
        document.segments[0] = TranscriptSegment(
            "SRC000001", "AUDIO001", 1, 5.0, 9.0, "premier segment"
        )

        assert "chronologie décroissante" in _errors(document)

    def test_interleaved_sources_are_refused(self):
        """Les segments d'une source doivent être contigus et dans l'ordre."""
        document = valid_document()
        document.segments = [
            TranscriptSegment("SRC000001", "AUDIO001", 1, 0.0, 5.0, "un"),
            TranscriptSegment("SRC000002", "AUDIO002", 2, 0.0, 4.0, "deux"),
            TranscriptSegment("SRC000003", "AUDIO001", 1, 5.0, 9.0, "trois"),
        ]
        document.stats = _stats_for(document.sources, document.segments)

        assert "ne sont pas contigus" in _errors(document)

    def test_sources_out_of_canonical_order_are_refused(self):
        document = valid_document()
        document.segments = [
            TranscriptSegment("SRC000001", "AUDIO002", 2, 0.0, 4.0, "deux"),
            TranscriptSegment("SRC000002", "AUDIO001", 1, 0.0, 5.0, "un"),
        ]
        document.stats = _stats_for(document.sources, document.segments)

        assert "ne suivent pas l'ordre canonique" in _errors(document)


# ---------------------------------------------------------------------------
# Statistiques
# ---------------------------------------------------------------------------

class TestStatsInvariants:

    def test_wrong_source_count_is_refused(self):
        document = valid_document()
        document.stats = dataclasses.replace(document.stats, source_count=99)

        assert "stats.source_count 99" in _errors(document)

    def test_wrong_segment_count_is_refused(self):
        document = valid_document()
        document.stats = dataclasses.replace(document.stats, segment_count=1)

        assert "stats.segment_count 1" in _errors(document)

    def test_wrong_duration_is_refused(self):
        document = valid_document()
        document.stats = dataclasses.replace(document.stats, duration_seconds=12.0)

        assert "stats.duration_seconds 12.0" in _errors(document)

    def test_wrong_word_count_is_refused(self):
        document = valid_document()
        document.stats = dataclasses.replace(document.stats, word_count=0)

        assert "stats.word_count 0" in _errors(document)


# ---------------------------------------------------------------------------
# Langues
# ---------------------------------------------------------------------------

class TestLanguageInvariants:

    def test_missing_primary_language_is_refused(self):
        assert "language.primary absente" in _errors(
            _with(valid_document(), primary_language="")
        )

    def test_empty_detected_languages_is_refused(self):
        assert "language.detected vide" in _errors(
            _with(valid_document(), detected_languages=[])
        )

    def test_primary_outside_detected_is_refused(self):
        assert "absente de language.detected" in _errors(
            _with(valid_document(), primary_language="de")
        )

    def test_unsorted_detected_languages_is_refused(self):
        assert "language.detected non triée" in _errors(
            _with(valid_document(), detected_languages=["fr", "en"])
        )

    def test_duplicated_detected_language_is_refused(self):
        assert "contient des doublons" in _errors(
            _with(valid_document(), detected_languages=["en", "en", "fr"])
        )

    def test_detected_languages_inconsistent_with_sources_is_refused(self):
        assert "incohérente avec les langues des sources" in _errors(
            _with(valid_document(), detected_languages=["de", "en", "fr"])
        )


# ---------------------------------------------------------------------------
# Levée d'erreur
# ---------------------------------------------------------------------------

class TestEnsureValid:

    def test_ensure_raises_and_lists_every_violation(self):
        document = valid_document()
        document.sources[1] = TranscriptSource("AUDIO001", 1, "b.mp3", 600.0, "en")

        with pytest.raises(TranscriptValidationError) as excinfo:
            ensure_valid_transcript_document(document)

        assert len(excinfo.value.errors) >= 2
        assert "source_id dupliqué" in str(excinfo.value)

    def test_error_reports_the_number_of_violations(self):
        with pytest.raises(TranscriptValidationError, match="violation"):
            ensure_valid_transcript_document(
                _with(valid_document(), schema_version="")
            )


# ---------------------------------------------------------------------------
# Contrats SOURCE / vue dérivée (Phase 3A.2C)
# ---------------------------------------------------------------------------

class TestSourceTranscriptContract:
    """SOURCE : SRC continus obligatoires. Les trous restent INVALIDES."""

    def test_source_contiguous_passes(self):
        assert validate_transcript_document(valid_document()) == []

    def test_source_gap_fails(self):
        document = valid_document()
        document.segments[1] = TranscriptSegment(
            "SRC000003", "AUDIO001", 1, 5.0, 9.5, "deuxième segment"
        )
        document.segments[2] = TranscriptSegment(
            "SRC000004", "AUDIO002", 2, 0.0, 4.0, "third segment"
        )

        errors = _errors(document)
        assert "identifiant SRC non continu" in errors

    def test_source_duplicate_fails(self):
        document = valid_document()
        document.segments[1] = TranscriptSegment(
            "SRC000001", "AUDIO001", 1, 5.0, 9.5, "deuxième segment"
        )

        assert "identifiant SRC dupliqué : SRC000001" in _errors(document)

    def test_source_out_of_order_fails(self):
        document = valid_document()
        document.segments[1] = TranscriptSegment(
            "SRC000003", "AUDIO001", 1, 5.0, 9.5, "troisième"
        )
        document.segments[2] = TranscriptSegment(
            "SRC000002", "AUDIO002", 2, 0.0, 4.0, "deuxième"
        )

        assert "identifiant SRC non continu" in _errors(document)


class TestDerivedTranscriptStructuralGaps:
    """
    Vue dérivée : trous structurellement acceptés par le validateur Phase 1
    UNIQUEMENT via allow_source_id_gaps=True (usage interne, jamais le défaut).
    """

    def test_default_still_rejects_a_gap(self):
        document = valid_document()
        document.segments = [
            document.segments[0],
            TranscriptSegment("SRC000003", "AUDIO002", 2, 0.0, 4.0, "third segment"),
        ]
        document.stats = _stats_for(document.sources, document.segments)

        errors = validate_transcript_document(document)
        assert any("non continu" in error for error in errors)

    def test_derived_valid_gaps_pass_with_explicit_flag(self):
        document = valid_document()
        document.segments = [
            document.segments[0],
            TranscriptSegment("SRC000003", "AUDIO002", 2, 0.0, 4.0, "third segment"),
        ]
        document.stats = _stats_for(document.sources, document.segments)

        assert validate_transcript_document(document, allow_source_id_gaps=True) == []

    def test_derived_duplicate_fails_even_with_flag(self):
        document = valid_document()
        document.segments[1] = TranscriptSegment(
            "SRC000001", "AUDIO001", 1, 5.0, 9.5, "deuxième segment"
        )

        errors = validate_transcript_document(document, allow_source_id_gaps=True)
        assert any("dupliqué" in error for error in errors)

    def test_derived_out_of_order_fails_even_with_flag(self):
        document = valid_document()
        document.segments = [
            document.segments[0],
            TranscriptSegment("SRC000007", "AUDIO002", 2, 0.0, 4.0, "third segment"),
            TranscriptSegment("SRC000003", "AUDIO002", 2, 4.0, 8.0, "encore"),
        ]
        document.stats = _stats_for(document.sources, document.segments)

        errors = validate_transcript_document(document, allow_source_id_gaps=True)
        assert any("hors ordre croissant" in error for error in errors)
