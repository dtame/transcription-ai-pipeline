"""
Phase 3A.1 — Correspondance locale FR -> EN (translation_matcher.py).

Ces tests exercent le SCORE brut (score_translation) et la fenêtre de
recherche (find_candidate_en_blocks), sans passer par les seuils de décision
de l'auditeur (voir test_language_cleanup_auditor.py pour KEEP/REVIEW/
REMOVE_TRANSLATION de bout en bout).
"""

from __future__ import annotations

from app.language_cleanup.blocks import Block
from app.language_cleanup.models import LANGUAGE_EN, LANGUAGE_FR, LANGUAGE_MIXED, LANGUAGE_UNKNOWN
from app.language_cleanup.translation_matcher import (
    find_candidate_en_blocks,
    score_translation,
)


class TestScoreTranslation:
    def test_clear_translation_scores_high(self):
        en = "God wants you to understand the authority he has given you."
        fr = "Dieu veut que vous compreniez l'autorité qu'il vous a donnée."

        score = score_translation(fr, en)

        assert score.coverage >= 0.55
        assert score.matched_tokens >= 2
        assert score.confidence >= 0.60

    def test_unrelated_text_scores_low(self):
        en = "God wants you to understand the authority he has given you."
        fr = "Nous allons maintenant lire Jean chapitre trois."

        score = score_translation(fr, en)

        assert score.coverage == 0.0
        assert score.matched_tokens == 0

    def test_glossary_covers_core_theological_vocabulary(self):
        en = "The Lord wants to save your soul and give you life."
        fr = "Le Seigneur veut sauver votre âme et vous donner la vie."

        score = score_translation(fr, en)

        assert score.coverage >= 0.55

    def test_cognate_detection(self):
        en = "This is an important example of his authority and ministry."
        fr = "Voici un exemple important de son autorité et de son ministère."

        score = score_translation(fr, en)

        assert score.matched_tokens >= 3


def _block(index: int, language: str, ref: str) -> Block:
    return Block(
        index=index,
        language=language,
        source_refs=(ref,),
        start_seconds=float(index) * 10.0,
        end_seconds=float(index) * 10.0 + 9.0,
        text=f"texte du bloc {ref}",
        word_count=4,
    )


class TestWindowSearch:
    """
    §11 : priorité au bloc adjacent, une fenêtre supplémentaire d'un bloc
    maximum si le bloc adjacent n'est ni EN ni FR (MIXED/UNKNOWN), jamais plus.
    """

    def test_immediate_adjacent_english_blocks_both_sides(self):
        blocks = (
            _block(0, LANGUAGE_EN, "SRC000001"),
            _block(1, LANGUAGE_FR, "SRC000002"),
            _block(2, LANGUAGE_EN, "SRC000003"),
        )
        before, after = find_candidate_en_blocks(blocks, 1)
        assert before.source_refs == ("SRC000001",)
        assert after.source_refs == ("SRC000003",)

    def test_skips_a_single_unknown_block(self):
        blocks = (
            _block(0, LANGUAGE_EN, "SRC000001"),
            _block(1, LANGUAGE_UNKNOWN, "SRC000002"),
            _block(2, LANGUAGE_FR, "SRC000003"),
        )
        before, _after = find_candidate_en_blocks(blocks, 2)
        assert before.source_refs == ("SRC000001",)

    def test_skips_a_single_mixed_block(self):
        blocks = (
            _block(0, LANGUAGE_FR, "SRC000001"),
            _block(1, LANGUAGE_MIXED, "SRC000002"),
            _block(2, LANGUAGE_EN, "SRC000003"),
        )
        _before, after = find_candidate_en_blocks(blocks, 0)
        assert after.source_refs == ("SRC000003",)

    def test_does_not_skip_beyond_the_documented_window(self):
        blocks = (
            _block(0, LANGUAGE_EN, "SRC000001"),
            _block(1, LANGUAGE_UNKNOWN, "SRC000002"),
            _block(2, LANGUAGE_UNKNOWN, "SRC000003"),
            _block(3, LANGUAGE_FR, "SRC000004"),
        )
        before, _after = find_candidate_en_blocks(blocks, 3)
        assert before is None

    def test_does_not_cross_another_french_block(self):
        blocks = (
            _block(0, LANGUAGE_EN, "SRC000001"),
            _block(1, LANGUAGE_FR, "SRC000002"),
            _block(2, LANGUAGE_UNKNOWN, "SRC000003"),
            _block(3, LANGUAGE_FR, "SRC000004"),
        )
        before, _after = find_candidate_en_blocks(blocks, 3)
        assert before is None

    def test_no_candidate_at_transcript_boundary(self):
        blocks = (_block(0, LANGUAGE_FR, "SRC000001"),)
        before, after = find_candidate_en_blocks(blocks, 0)
        assert before is None
        assert after is None
