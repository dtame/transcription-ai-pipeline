"""
Phase 3A.1 — Validation de language_cleanup.json (validator.py).

Scénarios 15-17 du cahier des charges, plus quelques invariants structurels
supplémentaires listés au §25.
"""

from __future__ import annotations

import copy

from app.language_cleanup.auditor import run_audit
from app.language_cleanup.transcript_source import load_audit_transcript
from app.language_cleanup.validator import validate_manifest_payload
from app.tests.source_analysis_fixtures import build_transcript_document, write_transcript

PROJECT = "validator_demo"


def _valid_setup(tmp_path):
    texts = (
        "God wants you to understand the authority he has given you.",
        "Dieu veut que vous compreniez l'autorité qu'il vous a donnée.",
    )
    document = build_transcript_document(project_name=PROJECT, texts=texts)
    transcripts_dir = tmp_path / "sortie" / PROJECT / "transcripts"
    write_transcript(transcripts_dir, document)

    result = run_audit(PROJECT, sortie_dir=tmp_path / "sortie", write=False)
    transcript = load_audit_transcript(transcripts_dir / "transcript_data.json", project_name=PROJECT)

    return result.manifest.to_dict(), transcript


class TestValidManifestPassesCleanly:
    def test_no_errors_on_a_freshly_produced_manifest(self, tmp_path):
        payload, transcript = _valid_setup(tmp_path)
        errors = validate_manifest_payload(payload, transcript)
        assert errors == []


class TestValidatorDetectsTextMismatch:
    """Scénario 15 : le validateur détecte un texte manifeste différent de la source."""

    def test_altered_text_is_rejected(self, tmp_path):
        payload, transcript = _valid_setup(tmp_path)
        payload = copy.deepcopy(payload)
        payload["segments"][0]["text"] = "God wants you to obey his authority."

        errors = validate_manifest_payload(payload, transcript)

        assert any("texte du manifeste différent" in error for error in errors)


class TestValidatorDetectsInventedMatchedRef:
    """Scénario 16 : le validateur détecte un matched ref inexistant."""

    def test_invented_matched_ref_is_rejected(self, tmp_path):
        payload, transcript = _valid_setup(tmp_path)
        payload = copy.deepcopy(payload)

        for segment in payload["segments"]:
            if segment["decision"] == "REMOVE_TRANSLATION":
                segment["matched_english_source_refs"] = ["SRC999999"]

        errors = validate_manifest_payload(payload, transcript)

        assert any("SRC999999" in error for error in errors)


class TestValidatorForbidsRemoveWithoutMatch:
    """Scénario 17 : le validateur interdit REMOVE_TRANSLATION sans EN correspondant."""

    def test_remove_translation_without_matched_ref_is_rejected(self, tmp_path):
        payload, transcript = _valid_setup(tmp_path)
        payload = copy.deepcopy(payload)

        for segment in payload["segments"]:
            if segment["decision"] == "REMOVE_TRANSLATION":
                segment["matched_english_source_refs"] = []
                segment["match_direction"] = None

        errors = validate_manifest_payload(payload, transcript)

        assert any(
            "REMOVE_TRANSLATION sans aucun matched_english_source_ref" in error
            for error in errors
        )


class TestValidatorForbidsRemoveOnEnglish:
    def test_remove_translation_on_english_segment_is_rejected(self, tmp_path):
        payload, transcript = _valid_setup(tmp_path)
        payload = copy.deepcopy(payload)

        english_entry = payload["segments"][0]
        assert english_entry["language"] == "EN"
        english_entry["decision"] = "REMOVE_TRANSLATION"
        english_entry["matched_english_source_refs"] = ["SRC000002"]
        english_entry["match_direction"] = "AFTER"

        errors = validate_manifest_payload(payload, transcript)

        assert any("réservé aux segments FR" in error for error in errors)
        assert any("ne doit jamais cibler l'anglais" in error for error in errors)


class TestValidatorDetectsDuplicateSourceRef:
    def test_duplicate_source_ref_is_rejected(self, tmp_path):
        payload, transcript = _valid_setup(tmp_path)
        payload = copy.deepcopy(payload)
        payload["segments"].append(copy.deepcopy(payload["segments"][0]))

        errors = validate_manifest_payload(payload, transcript)

        assert any("dupliqué" in error for error in errors)


class TestValidatorDetectsUnknownSourceRef:
    def test_invented_source_ref_is_rejected(self, tmp_path):
        payload, transcript = _valid_setup(tmp_path)
        payload = copy.deepcopy(payload)
        payload["segments"][0]["source_ref"] = "SRC999999"

        errors = validate_manifest_payload(payload, transcript)

        assert any("inventé" in error for error in errors)


class TestValidatorRejectsInvalidVocabulary:
    def test_invalid_decision_is_rejected(self, tmp_path):
        payload, transcript = _valid_setup(tmp_path)
        payload = copy.deepcopy(payload)
        payload["segments"][0]["decision"] = "DELETE_NOW"

        errors = validate_manifest_payload(payload, transcript)

        assert any("decision invalide" in error for error in errors)

    def test_invalid_language_is_rejected(self, tmp_path):
        payload, transcript = _valid_setup(tmp_path)
        payload = copy.deepcopy(payload)
        payload["segments"][0]["language"] = "ES"

        errors = validate_manifest_payload(payload, transcript)

        assert any("language invalide" in error for error in errors)


class TestValidatorChecksTranscriptShaConsistency:
    def test_stale_sha_is_rejected(self, tmp_path):
        payload, transcript = _valid_setup(tmp_path)
        payload = copy.deepcopy(payload)
        payload["transcript_sha256"] = "0" * 64

        errors = validate_manifest_payload(payload, transcript)

        assert any("transcript_sha256 incohérent" in error for error in errors)
