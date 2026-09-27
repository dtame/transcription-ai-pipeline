"""
Phase 3A.1.1 — bout en bout : transcript_data.json + language_cleanup.json
réels (produits par Phase 3A.1) -> language_blocks.json (§33 scénarios 13,
14, 21).

Contrairement à test_language_blocks_builder.py, ces tests font tourner le
VRAI audit Phase 3A.1 (app.language_cleanup.auditor.run_audit) sur un VRAI
Transcript V2 avant d'analyser son résultat : ils vérifient l'intégration
complète, pas seulement la logique de groupage.
"""

from __future__ import annotations

from app.language_blocks.builder import run_block_analysis
from app.language_cleanup.auditor import run_audit
from app.language_cleanup.transcript_source import compute_file_sha256
from app.tests.source_analysis_fixtures import build_transcript_document, write_transcript

PROJECT = "language_blocks_pipeline_demo"

TEXTS = (
    "God wants you to understand the authority he has given you.",
    "Dieu veut que vous compreniez l'autorité qu'il vous a donnée.",
    "This is important for your life and for your ministry.",
    "Nous allons maintenant lire Jean chapitre trois pour commencer.",
    "The weather today is quite pleasant for our outdoor session.",
)


def _prepare_project(tmp_path):
    document = build_transcript_document(project_name=PROJECT, texts=TEXTS, language="en")
    transcripts_dir = tmp_path / "sortie" / PROJECT / "transcripts"
    write_transcript(transcripts_dir, document)

    run_audit(PROJECT, sortie_dir=tmp_path / "sortie", write=True)

    return transcripts_dir


class TestTranscriptNeverMutated:
    """Scénario 13 : aucune mutation transcript."""

    def test_transcript_data_json_untouched_after_block_analysis(self, tmp_path):
        transcripts_dir = _prepare_project(tmp_path)
        transcript_path = transcripts_dir / "transcript_data.json"
        sha_before = compute_file_sha256(transcript_path)

        result = run_block_analysis(PROJECT, sortie_dir=tmp_path / "sortie", write=True)

        sha_after = compute_file_sha256(transcript_path)
        assert sha_after == sha_before
        assert sha_after == result.combined.transcript_sha256


class TestLanguageCleanupNeverMutated:
    """Scénario 14 : aucune mutation language_cleanup.json."""

    def test_language_cleanup_json_untouched_after_block_analysis(self, tmp_path):
        _prepare_project(tmp_path)
        cleanup_path = tmp_path / "sortie" / PROJECT / "audit" / "language_cleanup.json"
        sha_before = compute_file_sha256(cleanup_path)

        result = run_block_analysis(PROJECT, sortie_dir=tmp_path / "sortie", write=True)

        sha_after = compute_file_sha256(cleanup_path)
        assert sha_after == sha_before
        assert sha_after == result.combined.language_cleanup_sha256


class TestNoNetworkCallsInPipeline:
    """Scénario 21 : aucune API appelée, de bout en bout."""

    def test_full_pipeline_reports_zero_network_calls(self, tmp_path, no_ai_network):
        _prepare_project(tmp_path)

        result = run_block_analysis(PROJECT, sortie_dir=tmp_path / "sortie", write=True)

        assert result.anthropic_calls == 0
        assert result.openai_calls == 0
        assert result.whisper_calls == 0
        assert result.other_network_calls == 0


class TestManifestWrittenUnderAuditDirectory:
    def test_manifest_is_written_next_to_language_cleanup(self, tmp_path):
        _prepare_project(tmp_path)

        result = run_block_analysis(PROJECT, sortie_dir=tmp_path / "sortie", write=True)

        assert result.output_path is not None
        assert result.output_path.parent.name == "audit"
        assert result.output_path.name == "language_blocks.json"
        assert result.output_path.exists()
        assert (result.output_path.parent / "language_cleanup.json").exists()


class TestPipelineIsDeterministic:
    def test_two_runs_produce_identical_canonical_manifest(self, tmp_path):
        _prepare_project(tmp_path)

        first = run_block_analysis(PROJECT, sortie_dir=tmp_path / "sortie", write=False)
        second = run_block_analysis(PROJECT, sortie_dir=tmp_path / "sortie", write=False)

        assert first.manifest.canonical_dict() == second.manifest.canonical_dict()


class TestPipelineCoversAllFrenchExactlyOnce:
    def test_every_fr_src_appears_in_exactly_one_block(self, tmp_path):
        _prepare_project(tmp_path)

        result = run_block_analysis(PROJECT, sortie_dir=tmp_path / "sortie", write=False)

        fr_refs_in_transcript = {
            segment.src_id
            for segment in result.combined.segments
            if segment.language == "FR"
        }
        fr_refs_in_blocks = [
            ref for block in result.manifest.blocks for ref in block.fr_source_refs
        ]

        assert sorted(fr_refs_in_blocks) == sorted(fr_refs_in_transcript)
        assert len(fr_refs_in_blocks) == len(set(fr_refs_in_blocks))
