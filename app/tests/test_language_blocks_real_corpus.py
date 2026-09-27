"""
Phase 3A.1.1 — corpus réel pastoral_retreat_v2_validation (§33 scénario 11).

« si test corpus autorisé » (cahier des charges §33.11) : ce test lit le VRAI
transcript_data.json et language_cleanup.json déjà publiés dans sortie/, en
LECTURE SEULE (write=False, aucun fichier écrit). Il est ignoré automatiquement
si ce projet n'est pas présent sur la machine qui exécute les tests (portable
CI, clone frais sans données de validation).
"""

from __future__ import annotations

import pytest

from app.language_blocks.builder import run_block_analysis
from app.language_cleanup.transcript_source import compute_file_sha256
from app.language_cleanup.writer import manifest_path as cleanup_manifest_path
from app.language_cleanup.transcript_source import transcript_data_file

PROJECT = "pastoral_retreat_v2_validation"

_transcript_path = transcript_data_file(PROJECT)
_cleanup_path = cleanup_manifest_path(PROJECT)

pytestmark = pytest.mark.skipif(
    not (_transcript_path.exists() and _cleanup_path.exists()),
    reason=f"corpus réel {PROJECT} absent de cette machine",
)


class TestRealCorpusFrenchCoverage:
    def test_all_828_fr_segments_covered_exactly_once(self):
        sha_transcript_before = compute_file_sha256(_transcript_path)
        sha_cleanup_before = compute_file_sha256(_cleanup_path)

        result = run_block_analysis(PROJECT, write=False)

        fr_refs_in_transcript = {
            segment.src_id
            for segment in result.combined.segments
            if segment.language == "FR"
        }
        fr_refs_in_blocks = [
            ref for block in result.manifest.blocks for ref in block.fr_source_refs
        ]

        assert len(fr_refs_in_transcript) == 828
        assert sorted(fr_refs_in_blocks) == sorted(fr_refs_in_transcript)
        assert len(fr_refs_in_blocks) == len(set(fr_refs_in_blocks))

        # §38 : les deux sources restent byte-identiques après l'analyse.
        assert compute_file_sha256(_transcript_path) == sha_transcript_before
        assert compute_file_sha256(_cleanup_path) == sha_cleanup_before

    def test_no_block_crosses_an_audio_boundary(self):
        result = run_block_analysis(PROJECT, write=False)
        audio_by_ref = {
            segment.src_id: segment.audio_id for segment in result.combined.segments
        }

        for block in result.manifest.blocks:
            audios = {audio_by_ref[ref] for ref in block.all_source_refs}
            assert audios == {block.audio_id}

    def test_manifest_validates_against_its_own_validator(self):
        from app.language_blocks.validator import validate_blocks_payload

        result = run_block_analysis(PROJECT, write=False)
        payload = result.manifest.to_dict()

        errors = validate_blocks_payload(payload, result.combined)
        assert errors == []
