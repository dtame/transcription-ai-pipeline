"""
Phase 3A.1 — Classification linguistique EN / FR / MIXED / UNKNOWN.

Couvre les scénarios §26 du cahier des charges qui relèvent strictement de la
classification (les scénarios de décision KEEP/REMOVE/REVIEW sont couverts par
test_language_cleanup_auditor.py, qui exerce le pipeline complet).
"""

from __future__ import annotations

from app.language_cleanup.language_detector import classify_text
from app.language_cleanup.models import (
    LANGUAGE_EN,
    LANGUAGE_FR,
    LANGUAGE_MIXED,
    LANGUAGE_UNKNOWN,
)


class TestClearEnglish:
    """Scénario 1 : anglais clair -> EN."""

    def test_simple_sentence(self):
        result = classify_text(
            "God wants you to understand the authority he has given you."
        )
        assert result.language == LANGUAGE_EN
        assert result.confidence >= 0.7

    def test_contraction_reinforces_english(self):
        result = classify_text("We don't need to be afraid of this.")
        assert result.language == LANGUAGE_EN


class TestClearFrench:
    """Scénario 2 : français clair -> FR (la décision KEEP/REVIEW est testée
    au niveau de l'auditeur, pas ici)."""

    def test_simple_sentence(self):
        result = classify_text(
            "Ceci est important pour votre vie et pour votre avenir."
        )
        assert result.language == LANGUAGE_FR
        assert result.confidence >= 0.7

    def test_elision_reinforces_french(self):
        result = classify_text("Il n'est pas possible qu'il l'ait fait ainsi.")
        assert result.language == LANGUAGE_FR

    def test_diacritics_alone_are_a_moderate_signal(self):
        result = classify_text("Alléluia, gloire à Dieu.")
        assert result.language == LANGUAGE_FR


class TestMixed:
    """Scénario 7 : signaux FR et EN comparables -> MIXED."""

    def test_comparable_signals_both_languages(self):
        result = classify_text(
            "The Lord and the King is with us and for us, il est avec nous "
            "et il est pour nous aussi."
        )
        assert result.language == LANGUAGE_MIXED


class TestUnknown:
    """Scénario 8 : aucun signal grammatical fiable -> UNKNOWN."""

    def test_single_interjection(self):
        assert classify_text("Amen.").language == LANGUAGE_UNKNOWN

    def test_numbers_only(self):
        assert classify_text("2019").language == LANGUAGE_UNKNOWN

    def test_empty_text(self):
        result = classify_text("   ")
        assert result.language == LANGUAGE_UNKNOWN
        assert result.confidence == 0.0


class TestProperNounsAndBiblicalReferences:
    """
    Scénario 9 : un nom propre ou une référence biblique isolée ne doit jamais
    déclencher une fausse classification FR ou EN — faute de mot grammatical,
    le résultat reste UNKNOWN.
    """

    def test_isolated_proper_noun(self):
        assert classify_text("Paul").language == LANGUAGE_UNKNOWN

    def test_isolated_biblical_reference(self):
        # Aucun mot grammatical dans une référence biblique nue : ni FR ni EN
        # n'est fabriqué à partir des seuls noms propres et nombres.
        assert classify_text("Jean chapitre trois verset seize").language == (
            LANGUAGE_UNKNOWN
        )
        assert classify_text("Jean 3:16").language == LANGUAGE_UNKNOWN

    def test_acronym_alone(self):
        assert classify_text("USA").language == LANGUAGE_UNKNOWN


class TestConfidenceIsBounded:
    def test_confidence_never_exceeds_cap(self):
        result = classify_text(
            "The Lord and the King and the Word and the Truth and the Life "
            "and the Way and the Light and the Church and the Kingdom."
        )
        assert result.confidence <= 0.97

    def test_confidence_never_negative(self):
        result = classify_text("Amen.")
        assert result.confidence >= 0.0
