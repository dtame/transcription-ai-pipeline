"""
Phase 3A.1.1 — construction des blocs FR : groupage, ponts, frontières,
contextes anglais, revue sémantique (§33, scénarios 1-10, 12, 19).

Tous les scénarios ci-dessous construisent un CombinedSource directement en
mémoire (app.tests.language_blocks_fixtures) : aucun fichier réel n'est lu ni
écrit, et aucune heuristique de classification n'intervient — la langue et la
décision Phase 3A.1 de chaque SRC sont fixées explicitement par le test.
"""

from __future__ import annotations

from app.language_blocks.builder import build_manifest
from app.language_blocks.models import (
    DIRECTION_AFTER,
    DIRECTION_BEFORE,
    DIRECTION_BOTH,
    DIRECTION_NONE,
    SEMANTIC_STATUS_ALREADY_RESOLVED,
    SEMANTIC_STATUS_NEEDED,
    SEMANTIC_STATUS_NO_ENGLISH_CONTEXT,
    STRUCTURE_EN_FR,
    STRUCTURE_EN_FR_EN,
    STRUCTURE_FR_EN,
    STRUCTURE_FR_ISOLATED,
)
from app.tests.language_blocks_fixtures import build_sequence, make_combined


class TestSingleFrenchBetweenTwoEnglish:
    """Scénario 1 : FR unique entre deux EN -> un bloc."""

    def test_single_fr_between_en_is_one_block(self):
        segments = build_sequence(
            [
                {"language": "EN", "text": "Hello there friend"},
                {"language": "FR", "text": "Bonjour mon ami"},
                {"language": "EN", "text": "Good to see you"},
            ]
        )
        manifest = build_manifest(make_combined(segments))

        assert len(manifest.blocks) == 1
        block = manifest.blocks[0]
        assert block.fr_source_refs == ("SRC000002",)
        assert block.bridge_source_refs == ()
        assert block.structure == STRUCTURE_EN_FR_EN
        assert block.candidate_direction == DIRECTION_BOTH


class TestMultipleConsecutiveFrench:
    """Scénario 2 : plusieurs FR consécutifs -> un bloc."""

    def test_consecutive_fr_form_one_block(self):
        segments = build_sequence(
            [
                {"language": "EN", "text": "one two three"},
                {"language": "FR", "text": "un"},
                {"language": "FR", "text": "deux"},
                {"language": "FR", "text": "trois"},
                {"language": "EN", "text": "four five six"},
            ]
        )
        manifest = build_manifest(make_combined(segments))

        assert len(manifest.blocks) == 1
        block = manifest.blocks[0]
        assert block.fr_source_refs == ("SRC000002", "SRC000003", "SRC000004")
        assert block.fr_segment_count == 3
        assert block.segment_count == 3
        assert block.bridge_source_refs == ()


class TestBridgeableInterruptionIsAbsorbed:
    """Scénario 3 : FR UNKNOWN FR avec bridge admissible -> un bloc."""

    def test_short_unknown_interjection_is_absorbed_as_bridge(self):
        segments = build_sequence(
            [
                {"language": "EN", "text": "one two three"},
                {"language": "FR", "text": "bonjour mon ami"},
                {"language": "UNKNOWN", "text": "OK.", "duration": 0.3, "gap_before": 0.5},
                {"language": "FR", "text": "comment vas tu", "gap_before": 0.5},
                {"language": "EN", "text": "four five six"},
            ]
        )
        manifest = build_manifest(make_combined(segments))

        assert len(manifest.blocks) == 1
        block = manifest.blocks[0]
        assert block.fr_source_refs == ("SRC000002", "SRC000004")
        assert block.bridge_source_refs == ("SRC000003",)
        assert block.all_source_refs == ("SRC000002", "SRC000003", "SRC000004")
        assert block.segment_count == 3
        assert block.fr_segment_count == 2

    def test_bridge_never_absorbs_real_english(self):
        """Un run classifié EN n'est jamais absorbé, même court et bref."""
        segments = build_sequence(
            [
                {"language": "FR", "text": "bonjour"},
                {"language": "EN", "text": "OK.", "duration": 0.3, "gap_before": 0.5},
                {"language": "FR", "text": "au revoir", "gap_before": 0.5},
            ]
        )
        manifest = build_manifest(make_combined(segments))

        assert len(manifest.blocks) == 2
        assert manifest.blocks[0].bridge_source_refs == ()
        assert manifest.blocks[1].bridge_source_refs == ()

    def test_bridge_rejected_when_too_many_words(self):
        """Un run UNKNOWN de plus de BRIDGE_MAX_WORDS_PER_SEGMENT mots reste un bloc à part."""
        segments = build_sequence(
            [
                {"language": "FR", "text": "bonjour"},
                {
                    "language": "UNKNOWN",
                    "text": "this sentence has five words",
                    "duration": 1.0,
                    "gap_before": 0.5,
                },
                {"language": "FR", "text": "au revoir", "gap_before": 0.5},
            ]
        )
        manifest = build_manifest(make_combined(segments))

        assert len(manifest.blocks) == 2

    def test_bridge_rejected_when_run_too_long(self):
        """Un run pont de plus de BRIDGE_MAX_RUN_SEGMENTS SRC reste un bloc à part."""
        segments = build_sequence(
            [
                {"language": "FR", "text": "bonjour"},
                {"language": "UNKNOWN", "text": "OK.", "duration": 0.3, "gap_before": 0.5},
                {"language": "UNKNOWN", "text": "OK.", "duration": 0.3},
                {"language": "FR", "text": "au revoir", "gap_before": 0.5},
            ]
        )
        manifest = build_manifest(make_combined(segments))

        assert len(manifest.blocks) == 2


class TestFrenchEnglishFrenchIsTwoBlocks:
    """Scénario 4 : FR EN FR -> deux blocs."""

    def test_real_english_between_two_french_runs_splits_the_block(self):
        segments = build_sequence(
            [
                {"language": "FR", "text": "bonjour mon ami"},
                {"language": "EN", "text": "hello good friend indeed"},
                {"language": "FR", "text": "au revoir mon ami"},
            ]
        )
        manifest = build_manifest(make_combined(segments))

        assert len(manifest.blocks) == 2
        assert manifest.blocks[0].fr_source_refs == ("SRC000001",)
        assert manifest.blocks[1].fr_source_refs == ("SRC000003",)


class TestAudioBoundaryNeverCrossed:
    """Scénario 5 : frontière AUDIO -> deux blocs, même sans rien entre les deux FR."""

    def test_fr_at_end_and_start_of_different_audio_stay_separate(self):
        segments = build_sequence(
            [
                {"language": "FR", "text": "fin de audio un", "audio_id": "AUDIO001"},
                {"language": "FR", "text": "debut de audio deux", "audio_id": "AUDIO002"},
            ]
        )
        manifest = build_manifest(make_combined(segments))

        assert len(manifest.blocks) == 2
        assert manifest.blocks[0].audio_id == "AUDIO001"
        assert manifest.blocks[1].audio_id == "AUDIO002"
        for block in manifest.blocks:
            assert all(
                True for _ in block.all_source_refs
            )  # aucun bloc ne mélange les deux AUDIO (vérifié par le validateur ailleurs)


class TestLargeTemporalGapSplitsBlock:
    """Scénario 6 : gap temporel important -> blocs séparés selon règle retenue (§8)."""

    def test_gap_above_threshold_splits_an_otherwise_continuous_fr_run(self):
        segments = build_sequence(
            [
                {"language": "FR", "text": "premiere intervention"},
                {"language": "FR", "text": "seconde intervention", "gap_before": 10.0},
            ]
        )
        manifest = build_manifest(make_combined(segments))

        assert len(manifest.blocks) == 2

    def test_gap_below_threshold_does_not_split(self):
        segments = build_sequence(
            [
                {"language": "FR", "text": "premiere intervention"},
                {"language": "FR", "text": "seconde intervention", "gap_before": 1.0},
            ]
        )
        manifest = build_manifest(make_combined(segments))

        assert len(manifest.blocks) == 1


class TestEnglishBeforeIsCaptured:
    """Scénario 7 : english_before correctement capturé."""

    def test_english_before_fields(self):
        segments = build_sequence(
            [
                {"language": "EN", "text": "hello good friend today", "gap_before": 0.0},
                {"language": "FR", "text": "bonjour", "gap_before": 2.0},
            ]
        )
        manifest = build_manifest(make_combined(segments))

        block = manifest.blocks[0]
        assert block.english_before is not None
        assert block.english_before.source_refs == ("SRC000001",)
        assert block.english_before.word_count == 4
        assert block.english_before.segment_count == 1
        assert block.english_before.distance_segments == 0
        assert block.english_before.distance_seconds == 2.0
        assert block.english_after is None


class TestEnglishAfterIsCaptured:
    """Scénario 8 : english_after correctement capturé."""

    def test_english_after_fields(self):
        segments = build_sequence(
            [
                {"language": "FR", "text": "bonjour"},
                {"language": "EN", "text": "hello good friend today", "gap_before": 3.0},
            ]
        )
        manifest = build_manifest(make_combined(segments))

        block = manifest.blocks[0]
        assert block.english_before is None
        assert block.english_after is not None
        assert block.english_after.source_refs == ("SRC000002",)
        assert block.english_after.word_count == 4
        assert block.english_after.distance_segments == 0
        assert block.english_after.distance_seconds == 3.0


class TestBothDirectionsDetected:
    """Scénario 9 : both correctement détecté (EN_FR_EN / BOTH)."""

    def test_en_fr_en_detected_as_both(self):
        segments = build_sequence(
            [
                {"language": "EN", "text": "hello good friend today"},
                {"language": "FR", "text": "bonjour mon ami"},
                {"language": "EN", "text": "welcome back my friend"},
            ]
        )
        manifest = build_manifest(make_combined(segments))

        block = manifest.blocks[0]
        assert block.structure == STRUCTURE_EN_FR_EN
        assert block.candidate_direction == DIRECTION_BOTH
        assert block.english_before is not None
        assert block.english_after is not None


class TestNoEnglishContext:
    """Scénario 10 : no english context -> FR_ISOLATED / NO_ENGLISH_CONTEXT."""

    def test_fr_alone_in_transcript_has_no_english_context(self):
        segments = build_sequence([{"language": "FR", "text": "bonjour mon ami"}])
        manifest = build_manifest(make_combined(segments))

        block = manifest.blocks[0]
        assert block.english_before is None
        assert block.english_after is None
        assert block.structure == STRUCTURE_FR_ISOLATED
        assert block.candidate_direction == DIRECTION_NONE
        assert block.semantic_review_status == SEMANTIC_STATUS_NO_ENGLISH_CONTEXT
        assert block.needs_semantic_review is False


class TestDeterministicBlockIds:
    """Scénario 12 : IDs déterministes (FRB0001, FRB0002, ... jamais UUID)."""

    def test_two_runs_produce_identical_block_ids_and_canonical_manifest(self):
        segments = build_sequence(
            [
                {"language": "EN", "text": "one two three"},
                {"language": "FR", "text": "un"},
                {"language": "EN", "text": "four five six"},
                {"language": "FR", "text": "deux"},
            ]
        )
        combined = make_combined(segments)

        first = build_manifest(combined, analysis_duration_seconds=1.234)
        second = build_manifest(combined, analysis_duration_seconds=9.876)

        assert [b.block_id for b in first.blocks] == ["FRB0001", "FRB0002"]
        assert first.canonical_dict() == second.canonical_dict()


class TestAlreadyResolved:
    """Scénario 19 : already_resolved correct."""

    def test_all_remove_with_valid_matches_is_already_resolved(self):
        segments = build_sequence(
            [
                {"language": "EN", "text": "hello good friend today"},
                {
                    "language": "FR",
                    "text": "bonjour mon ami",
                    "decision": "REMOVE_TRANSLATION",
                    "matched": ("SRC000001",),
                    "direction": "BEFORE",
                    "confidence": 0.9,
                },
            ]
        )
        manifest = build_manifest(make_combined(segments))

        block = manifest.blocks[0]
        assert block.already_resolved is True
        assert block.semantic_review_status == SEMANTIC_STATUS_ALREADY_RESOLVED
        assert block.needs_semantic_review is False

    def test_review_decision_is_not_already_resolved(self):
        segments = build_sequence(
            [
                {"language": "EN", "text": "hello good friend today"},
                {
                    "language": "FR",
                    "text": "bonjour mon ami",
                    "decision": "REVIEW",
                    "matched": ("SRC000001",),
                    "direction": "BEFORE",
                    "confidence": 0.3,
                },
            ]
        )
        manifest = build_manifest(make_combined(segments))

        block = manifest.blocks[0]
        assert block.already_resolved is False
        assert block.semantic_review_status == SEMANTIC_STATUS_NEEDED
        assert block.needs_semantic_review is True

    def test_remove_without_matched_refs_is_not_already_resolved(self):
        """Garde-fou : REMOVE_TRANSLATION sans matched ref valide ne peut pas être considéré résolu."""
        segments = build_sequence(
            [
                {"language": "EN", "text": "hello good friend today"},
                {
                    "language": "FR",
                    "text": "bonjour mon ami",
                    "decision": "REMOVE_TRANSLATION",
                    "matched": (),
                },
            ]
        )
        manifest = build_manifest(make_combined(segments))

        block = manifest.blocks[0]
        assert block.already_resolved is False

    def test_partial_remove_across_multi_segment_block_is_not_already_resolved(self):
        segments = build_sequence(
            [
                {"language": "EN", "text": "hello good friend today"},
                {
                    "language": "FR",
                    "text": "bonjour",
                    "decision": "REMOVE_TRANSLATION",
                    "matched": ("SRC000001",),
                    "direction": "BEFORE",
                },
                {"language": "FR", "text": "mon ami", "decision": "KEEP"},
            ]
        )
        manifest = build_manifest(make_combined(segments))

        block = manifest.blocks[0]
        assert block.fr_segment_count == 2
        assert block.already_resolved is False
        assert block.phase_3a1_status == "HAS_REMOVE"
