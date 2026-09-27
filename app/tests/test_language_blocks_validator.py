"""
Phase 3A.1.1 — validateur de language_blocks.json (§32, §33 scénarios 15-18).

Chaque test construit un manifeste VALIDE avec build_manifest(), le sérialise,
puis introduit UNE violation ciblée dans le payload avant de vérifier que
validate_blocks_payload() la détecte. Le validateur ne doit jamais lever pour
un manifeste correctement construit.
"""

from __future__ import annotations

import copy

from app.language_blocks.builder import build_manifest
from app.language_blocks.validator import validate_blocks_payload
from app.tests.language_blocks_fixtures import build_sequence, make_combined


def _valid_payload_and_combined():
    segments = build_sequence(
        [
            {"language": "EN", "text": "hello good friend today"},
            {"language": "FR", "text": "bonjour mon ami"},
            {"language": "EN", "text": "welcome back my friend"},
            {"language": "FR", "text": "au revoir"},
        ]
    )
    combined = make_combined(segments)
    manifest = build_manifest(combined)
    return manifest.to_dict(), combined


class TestValidManifestHasNoErrors:
    def test_valid_manifest_passes(self):
        payload, combined = _valid_payload_and_combined()
        assert validate_blocks_payload(payload, combined) == []


class TestValidatorDetectsMissingFrenchRef:
    """Scénario 15 : validator détecte FR manquant."""

    def test_missing_fr_ref_is_detected(self):
        payload, combined = _valid_payload_and_combined()
        payload = copy.deepcopy(payload)

        block = payload["blocks"][0]
        block["fr_source_refs"] = []
        block["all_source_refs"] = []
        block["bridge_source_refs"] = []

        errors = validate_blocks_payload(payload, combined)
        assert any("absent de tout bloc" in error for error in errors)


class TestValidatorDetectsDuplicatedFrenchRef:
    """Scénario 16 : validator détecte FR dupliqué."""

    def test_duplicated_fr_ref_across_blocks_is_detected(self):
        payload, combined = _valid_payload_and_combined()
        payload = copy.deepcopy(payload)

        # Copie la référence FR du second bloc dans le premier bloc, sans la
        # retirer de son bloc d'origine : un doublon net entre deux blocs.
        second_block_fr_ref = payload["blocks"][1]["fr_source_refs"][0]
        payload["blocks"][0]["fr_source_refs"].append(second_block_fr_ref)
        payload["blocks"][0]["all_source_refs"].append(second_block_fr_ref)

        errors = validate_blocks_payload(payload, combined)
        assert any("dupliqué dans fr_source_refs" in error for error in errors)


class TestValidatorDetectsContextCrossingAudio:
    """Scénario 17 : validator détecte contexte traversant AUDIO."""

    def test_context_ref_from_other_audio_is_detected(self):
        segments = build_sequence(
            [
                {"language": "FR", "text": "bonjour mon ami", "audio_id": "AUDIO001"},
                {"language": "EN", "text": "hello good friend today", "audio_id": "AUDIO002"},
            ]
        )
        combined = make_combined(segments)
        manifest = build_manifest(combined)
        payload = copy.deepcopy(manifest.to_dict())

        # Le bloc FR (AUDIO001) est isolé : on lui invente un english_after
        # pointant vers le SRC réel de AUDIO002, un AUDIO différent.
        payload["blocks"][0]["english_after"] = {
            "source_refs": ["SRC000002"],
            "start_seconds": 10.0,
            "end_seconds": 11.0,
            "text": "hello good friend today",
            "word_count": 4,
            "segment_count": 1,
            "distance_segments": 0,
            "distance_seconds": 1.0,
            "truncated": False,
        }
        payload["blocks"][0]["semantic_review_status"] = "NEEDED"
        payload["blocks"][0]["needs_semantic_review"] = True

        errors = validate_blocks_payload(payload, combined)
        assert any("d'un AUDIO différent" in error for error in errors)


class TestValidatorDetectsEnglishInBridge:
    """Scénario 18 : validator détecte EN dans bridge."""

    def test_english_ref_in_bridge_is_detected(self):
        segments = build_sequence(
            [
                {"language": "FR", "text": "bonjour"},
                {
                    "language": "UNKNOWN",
                    "text": "OK.",
                    "duration": 0.3,
                    "gap_before": 0.5,
                },
                {"language": "FR", "text": "au revoir", "gap_before": 0.5},
            ]
        )
        combined = make_combined(segments)
        manifest = build_manifest(combined)
        payload = copy.deepcopy(manifest.to_dict())

        assert payload["blocks"][0]["bridge_source_refs"] == ["SRC000002"]

        # Falsifie la classification lue par le validateur : le SRC du pont
        # devient EN dans la vue « combined » utilisée pour juger le payload.
        mutated_segments = tuple(
            (seg if seg.src_id != "SRC000002" else _as_english(seg))
            for seg in combined.segments
        )
        mutated_combined = make_combined(
            mutated_segments,
            transcript_sha256=combined.transcript_sha256,
            language_cleanup_sha256=combined.language_cleanup_sha256,
        )

        errors = validate_blocks_payload(payload, mutated_combined)
        assert any("classifié EN" in error for error in errors)


def _as_english(segment):
    from dataclasses import replace

    return replace(segment, language="EN")
