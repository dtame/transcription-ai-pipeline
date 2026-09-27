"""
Phase 3A.2C — contrats SOURCE / DERIVED et provenance.

SOURCE reste le défaut : un trou de SRC est INVALIDE.
DERIVED n'accepte les trous qu'avec cleanup_application.json vérifiée.
Un clean trafiqué est toujours rejeté (fail-closed).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.source_analysis.errors import (
    SourceTranscriptError,
    SourceTranscriptProvenanceError,
)
from app.source_analysis.transcript_input import (
    TranscriptInputMode,
    load_transcript_input,
    resolve_original_transcript_path,
)
from app.tests.source_analysis_fixtures import (
    analysis_env,  # noqa: F401
    drop_segments,
    write_cleanup_provenance,
    write_transcript,
)
from app.semantic_canary.integrity import sha256_of_file
from app.transcript_writer import TRANSCRIPT_JSON_NAME


def _refresh_clean_hash(clean_path: Path, provenance_path: Path) -> None:
    audit = json.loads(provenance_path.read_text(encoding="utf-8"))
    audit["clean_hashes"]["clean_transcript_data_sha256"] = sha256_of_file(clean_path)
    provenance_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


REMOVED_ID = "SRC000002"


def _prepare_derived(env):
    """Original + clean à trous + provenance dans l'environnement isolé."""
    original = env.document
    removed = [segment for segment in original.segments if segment.id == REMOVED_ID]
    clean = drop_segments(original, {REMOVED_ID})

    clean_dir = env.transcripts_dir / "clean"
    clean_path = write_transcript(clean_dir, clean)
    provenance_path = env.sortie / env.project_name / "audit" / "cleanup_application.json"
    write_cleanup_provenance(
        provenance_path,
        original_path=env.transcript_path,
        clean_path=clean_path,
        original=original,
        clean=clean,
        removed=removed,
    )
    return clean, clean_path, provenance_path, removed


class TestSourceModeAtLoader:
    def test_source_contiguous_passes(self, analysis_env):
        transcript = load_transcript_input(
            analysis_env.transcript_path, project_name=analysis_env.project_name
        )
        assert transcript.mode is TranscriptInputMode.SOURCE
        assert transcript.segment_count == 8
        assert transcript.src_ids()[0] == "SRC000001"

    def test_source_is_the_default(self, analysis_env):
        transcript = load_transcript_input(
            analysis_env.transcript_path, project_name=analysis_env.project_name
        )
        assert transcript.mode is TranscriptInputMode.SOURCE

    def test_source_gap_fails(self, analysis_env):
        clean, clean_path, _, _ = _prepare_derived(analysis_env)

        with pytest.raises(SourceTranscriptError, match="non continu"):
            load_transcript_input(
                clean_path, project_name=analysis_env.project_name
            )

    def test_source_duplicate_fails(self, analysis_env):
        payload = json.loads(analysis_env.transcript_path.read_text(encoding="utf-8"))
        payload["segments"][1]["id"] = payload["segments"][0]["id"]
        analysis_env.transcript_path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

        with pytest.raises(SourceTranscriptError, match="dupliqué"):
            load_transcript_input(
                analysis_env.transcript_path, project_name=analysis_env.project_name
            )

    def test_source_out_of_order_fails(self, analysis_env):
        payload = json.loads(analysis_env.transcript_path.read_text(encoding="utf-8"))
        payload["segments"][1]["id"] = "SRC000003"
        payload["segments"][2]["id"] = "SRC000002"
        analysis_env.transcript_path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

        with pytest.raises(SourceTranscriptError, match="non continu"):
            load_transcript_input(
                analysis_env.transcript_path, project_name=analysis_env.project_name
            )

    def test_path_containing_clean_does_not_switch_mode(self, analysis_env):
        clean, clean_path, provenance_path, _ = _prepare_derived(analysis_env)
        assert "clean" in clean_path.as_posix()

        with pytest.raises(SourceTranscriptError, match="non continu"):
            load_transcript_input(
                clean_path, project_name=analysis_env.project_name
            )


class TestDerivedModeAtLoader:
    def test_derived_valid_gaps_pass_with_provenance(self, analysis_env):
        clean, clean_path, provenance_path, _ = _prepare_derived(analysis_env)

        transcript = load_transcript_input(
            clean_path,
            project_name=analysis_env.project_name,
            mode=TranscriptInputMode.DERIVED,
            provenance_path=provenance_path,
        )

        assert transcript.mode is TranscriptInputMode.DERIVED
        assert REMOVED_ID not in transcript.src_ids()
        assert transcript.segment_count == 7
        assert transcript.src_ids() == (
            "SRC000001",
            "SRC000003",
            "SRC000004",
            "SRC000005",
            "SRC000006",
            "SRC000007",
            "SRC000008",
        )

    def test_derived_without_provenance_fails(self, analysis_env):
        _, clean_path, _, _ = _prepare_derived(analysis_env)

        with pytest.raises(SourceTranscriptProvenanceError, match="provenance_path"):
            load_transcript_input(
                clean_path,
                project_name=analysis_env.project_name,
                mode=TranscriptInputMode.DERIVED,
            )

    def test_derived_provenance_missing_original_fails(self, analysis_env, tmp_path):
        clean, clean_path, provenance_path, _ = _prepare_derived(analysis_env)
        missing_original = tmp_path / "nowhere" / TRANSCRIPT_JSON_NAME

        with pytest.raises(SourceTranscriptProvenanceError, match="original"):
            load_transcript_input(
                clean_path,
                project_name=analysis_env.project_name,
                mode=TranscriptInputMode.DERIVED,
                provenance_path=provenance_path,
                original_transcript_path=missing_original,
            )

    def test_derived_duplicate_fails(self, analysis_env):
        _, clean_path, provenance_path, _ = _prepare_derived(analysis_env)
        payload = json.loads(clean_path.read_text(encoding="utf-8"))
        payload["segments"][1]["id"] = payload["segments"][0]["id"]
        clean_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        _refresh_clean_hash(clean_path, provenance_path)

        with pytest.raises(SourceTranscriptProvenanceError):
            load_transcript_input(
                clean_path,
                project_name=analysis_env.project_name,
                mode=TranscriptInputMode.DERIVED,
                provenance_path=provenance_path,
            )

    def test_derived_out_of_order_fails(self, analysis_env):
        _, clean_path, provenance_path, _ = _prepare_derived(analysis_env)
        payload = json.loads(clean_path.read_text(encoding="utf-8"))
        payload["segments"][0], payload["segments"][1] = (
            payload["segments"][1],
            payload["segments"][0],
        )
        clean_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        _refresh_clean_hash(clean_path, provenance_path)

        with pytest.raises((SourceTranscriptError, SourceTranscriptProvenanceError)):
            load_transcript_input(
                clean_path,
                project_name=analysis_env.project_name,
                mode=TranscriptInputMode.DERIVED,
                provenance_path=provenance_path,
            )


class TestDerivedTampering:
    def test_invented_src_fails(self, analysis_env):
        _, clean_path, provenance_path, _ = _prepare_derived(analysis_env)
        payload = json.loads(clean_path.read_text(encoding="utf-8"))
        payload["segments"][-1]["id"] = "SRC000099"
        clean_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        _refresh_clean_hash(clean_path, provenance_path)

        with pytest.raises(SourceTranscriptProvenanceError, match="inventé"):
            load_transcript_input(
                clean_path,
                project_name=analysis_env.project_name,
                mode=TranscriptInputMode.DERIVED,
                provenance_path=provenance_path,
            )

    def test_modified_text_fails(self, analysis_env):
        _, clean_path, provenance_path, _ = _prepare_derived(analysis_env)
        payload = json.loads(clean_path.read_text(encoding="utf-8"))
        payload["segments"][0]["text"] = "texte survivant trafiqué pour le test."
        payload["stats"]["word_count"] = sum(
            len(str(entry["text"]).split()) for entry in payload["segments"]
        )
        clean_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        _refresh_clean_hash(clean_path, provenance_path)

        with pytest.raises(SourceTranscriptProvenanceError, match="text"):
            load_transcript_input(
                clean_path,
                project_name=analysis_env.project_name,
                mode=TranscriptInputMode.DERIVED,
                provenance_path=provenance_path,
            )

    def test_modified_timestamp_fails(self, analysis_env):
        _, clean_path, provenance_path, _ = _prepare_derived(analysis_env)
        payload = json.loads(clean_path.read_text(encoding="utf-8"))
        payload["segments"][0]["start"] = 99.0
        clean_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        _refresh_clean_hash(clean_path, provenance_path)

        with pytest.raises(SourceTranscriptProvenanceError, match="start"):
            load_transcript_input(
                clean_path,
                project_name=analysis_env.project_name,
                mode=TranscriptInputMode.DERIVED,
                provenance_path=provenance_path,
            )

    def test_modified_audio_id_fails(self, analysis_env):
        _, clean_path, provenance_path, _ = _prepare_derived(analysis_env)
        payload = json.loads(clean_path.read_text(encoding="utf-8"))
        payload["segments"][0]["source_id"] = "AUDIO099"
        clean_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        _refresh_clean_hash(clean_path, provenance_path)

        with pytest.raises(SourceTranscriptProvenanceError):
            load_transcript_input(
                clean_path,
                project_name=analysis_env.project_name,
                mode=TranscriptInputMode.DERIVED,
                provenance_path=provenance_path,
            )

    def test_extra_undeclared_removal_fails(self, analysis_env):
        clean, clean_path, provenance_path, _ = _prepare_derived(analysis_env)
        extra = drop_segments(clean, {"SRC000003"})
        write_transcript(clean_path.parent, extra)
        _refresh_clean_hash(clean_path, provenance_path)

        with pytest.raises(SourceTranscriptProvenanceError, match="sans être déclarés"):
            load_transcript_input(
                clean_path,
                project_name=analysis_env.project_name,
                mode=TranscriptInputMode.DERIVED,
                provenance_path=provenance_path,
            )

    def test_removed_src_still_present_fails(self, analysis_env):
        original = analysis_env.document
        clean_path = write_transcript(analysis_env.transcripts_dir / "clean", original)
        provenance_path = analysis_env.sortie / analysis_env.project_name / "audit" / "cleanup_application.json"
        removed = [segment for segment in original.segments if segment.id == REMOVED_ID]
        fake_clean = drop_segments(original, {REMOVED_ID})
        write_cleanup_provenance(
            provenance_path,
            original_path=analysis_env.transcript_path,
            clean_path=clean_path,
            original=original,
            clean=fake_clean,
            removed=removed,
        )

        with pytest.raises(SourceTranscriptProvenanceError):
            load_transcript_input(
                clean_path,
                project_name=analysis_env.project_name,
                mode=TranscriptInputMode.DERIVED,
                provenance_path=provenance_path,
            )

    def test_tampered_removed_audit_fails(self, analysis_env):
        _, clean_path, provenance_path, _ = _prepare_derived(analysis_env)
        audit = json.loads(provenance_path.read_text(encoding="utf-8"))
        audit["removed"][0]["source_ref"] = "SRC000007"
        provenance_path.write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")

        with pytest.raises(SourceTranscriptProvenanceError):
            load_transcript_input(
                clean_path,
                project_name=analysis_env.project_name,
                mode=TranscriptInputMode.DERIVED,
                provenance_path=provenance_path,
            )

    def test_source_hash_mismatch_fails(self, analysis_env):
        _, clean_path, provenance_path, _ = _prepare_derived(analysis_env)
        audit = json.loads(provenance_path.read_text(encoding="utf-8"))
        audit["source_hashes"]["transcript_data"] = "0" * 64
        provenance_path.write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")

        with pytest.raises(SourceTranscriptProvenanceError, match="Hash"):
            load_transcript_input(
                clean_path,
                project_name=analysis_env.project_name,
                mode=TranscriptInputMode.DERIVED,
                provenance_path=provenance_path,
            )

    def test_clean_hash_mismatch_fails(self, analysis_env):
        _, clean_path, provenance_path, _ = _prepare_derived(analysis_env)
        audit = json.loads(provenance_path.read_text(encoding="utf-8"))
        audit["clean_hashes"]["clean_transcript_data_sha256"] = "1" * 64
        provenance_path.write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")

        with pytest.raises(SourceTranscriptProvenanceError, match="Hash"):
            load_transcript_input(
                clean_path,
                project_name=analysis_env.project_name,
                mode=TranscriptInputMode.DERIVED,
                provenance_path=provenance_path,
            )


class TestOriginalResolution:
    def test_clean_sibling_resolves_to_transcripts(self, tmp_path):
        clean = tmp_path / "transcripts" / "clean" / TRANSCRIPT_JSON_NAME
        clean.parent.mkdir(parents=True)
        clean.write_text("{}", encoding="utf-8")

        resolved = resolve_original_transcript_path(clean)
        assert resolved == tmp_path / "transcripts" / TRANSCRIPT_JSON_NAME

    def test_non_clean_parent_is_refused(self, tmp_path):
        other = tmp_path / "transcripts" / TRANSCRIPT_JSON_NAME
        other.parent.mkdir(parents=True)
        other.write_text("{}", encoding="utf-8")

        with pytest.raises(SourceTranscriptProvenanceError, match="clean"):
            resolve_original_transcript_path(other)
