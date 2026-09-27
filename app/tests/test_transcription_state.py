"""
Phase 0A — Filet de sécurité autour de project_state.json (volet transcription).

Fige le comportement V1 de app.project_state pour :

- création / sauvegarde / rechargement de l'état ;
- statuts de fichier : processing, transcribed, failed,
  processing_segments, partial_error ;
- statut de segment : pending / transcribed / error ;
- conservation des informations de segments, du hash et du transcript_path ;
- is_audio_already_transcribed() : validité par hash et présence du transcript.

Le schéma n'est pas redessiné : les tests décrivent ce que V1 écrit réellement.
"""

from __future__ import annotations

import json

import pytest

from app.project_state import (
    get_audio_segments_state,
    get_project_state_path,
    is_audio_already_transcribed,
    load_project_state,
    mark_audio_failed,
    mark_audio_partial_error,
    mark_audio_processing,
    mark_audio_processing_segments,
    mark_audio_segmented_transcribed,
    mark_audio_transcribed,
    save_project_state,
    update_segment_in_state,
)

PROJECT = "demo_project"


@pytest.fixture
def audio_file(tmp_path):
    path = tmp_path / "depot" / "lesson_01.mp3"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"contenu-audio-initial")
    return path


@pytest.fixture
def transcript_file(tmp_path):
    path = tmp_path / "transcripts" / "lesson_01.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[00:00 -> 00:05] bonjour\n", encoding="utf-8")
    return path


def _segments(tmp_path):
    return [
        {
            "id": "part_001",
            "audio_path": str(tmp_path / "part_001.mp3"),
            "transcript_path": str(tmp_path / "part_001.txt"),
            "start_seconds": 0.0,
            "end_seconds": 910.0,
            "effective_start_local": 0.0,
            "status": "transcribed",
            "updated_at": "2026-01-01T10:00:00",
            "error": None,
        },
        {
            "id": "part_002",
            "audio_path": str(tmp_path / "part_002.mp3"),
            "transcript_path": str(tmp_path / "part_002.txt"),
            "start_seconds": 900.0,
            "end_seconds": 1810.0,
            "effective_start_local": 10.0,
            "status": "pending",
            "updated_at": None,
            "error": None,
        },
    ]


# ---------------------------------------------------------------------------
# 18 — Création / sauvegarde / rechargement
# ---------------------------------------------------------------------------

class TestStateLifecycle:

    def test_missing_state_returns_empty_but_structured_dict(self, isolated_sortie):
        state = load_project_state(PROJECT)

        assert state["files"] == {}
        for section in ("chunks", "corrections", "exports", "publication"):
            assert section in state

    def test_save_creates_the_file_at_the_expected_location(self, isolated_sortie):
        state = load_project_state(PROJECT)
        save_project_state(PROJECT, state)

        expected = isolated_sortie / PROJECT / "project_state.json"
        assert expected.exists()
        assert get_project_state_path(PROJECT) == expected

    def test_state_is_valid_utf8_json(self, isolated_sortie, audio_file):
        state = load_project_state(PROJECT)
        mark_audio_transcribed(state, audio_file, "abc123", audio_file.with_suffix(".txt"))
        save_project_state(PROJECT, state)

        raw = get_project_state_path(PROJECT).read_text(encoding="utf-8")
        assert json.loads(raw)["files"], "L'état doit être relisible en JSON."

    def test_reload_preserves_file_entry(self, isolated_sortie, audio_file, transcript_file):
        state = load_project_state(PROJECT)
        mark_audio_transcribed(state, audio_file, "hash-1", transcript_file)
        save_project_state(PROJECT, state)

        reloaded = load_project_state(PROJECT)
        entry = reloaded["files"][str(audio_file.resolve())]

        assert entry["status"] == "transcribed"
        assert entry["hash"] == "hash-1"
        assert entry["transcript_path"] == str(transcript_file)

    def test_state_is_keyed_by_resolved_absolute_path(self, isolated_sortie, audio_file):
        state = load_project_state(PROJECT)
        mark_audio_processing(state, audio_file, "hash-1")

        assert list(state["files"]) == [str(audio_file.resolve())]


# ---------------------------------------------------------------------------
# 18 — Statuts de fichier
# ---------------------------------------------------------------------------

class TestFileStatuses:

    def test_processing(self, audio_file):
        state = {"files": {}}
        mark_audio_processing(state, audio_file, "hash-1")
        entry = state["files"][str(audio_file.resolve())]

        assert entry["status"] == "processing"
        assert entry["hash"] == "hash-1"
        assert entry["transcript_path"] is None
        assert entry["error"] is None
        assert entry["started_at"] and entry["updated_at"]

    def test_transcribed(self, audio_file, transcript_file):
        state = {"files": {}}
        mark_audio_transcribed(state, audio_file, "hash-1", transcript_file)
        entry = state["files"][str(audio_file.resolve())]

        assert entry["status"] == "transcribed"
        assert entry["transcript_path"] == str(transcript_file)
        assert entry["error"] is None

    def test_failed_keeps_the_error_message(self, audio_file):
        state = {"files": {}}
        mark_audio_failed(state, audio_file, "hash-1", RuntimeError("whisper a planté"))
        entry = state["files"][str(audio_file.resolve())]

        assert entry["status"] == "failed"
        assert entry["transcript_path"] is None
        assert entry["error"] == "whisper a planté"

    def test_processing_segments_stores_every_segment(self, tmp_path, audio_file):
        state = {"files": {}}
        segments = _segments(tmp_path)
        mark_audio_processing_segments(state, audio_file, "hash-1", segments)
        entry = state["files"][str(audio_file.resolve())]

        assert entry["status"] == "processing_segments"
        assert entry["transcript_path"] is None
        assert sorted(entry["segments"]) == ["part_001", "part_002"]
        assert entry["segments"]["part_002"]["status"] == "pending"
        assert entry["segments"]["part_002"]["effective_start_local"] == 10.0

    def test_partial_error_preserves_completed_segments(self, tmp_path, audio_file):
        state = {"files": {}}
        segments = _segments(tmp_path)
        segments[1]["status"] = "error"
        segments[1]["error"] = "boom"

        mark_audio_partial_error(state, audio_file, "hash-1", "part_002: boom", segments)
        entry = state["files"][str(audio_file.resolve())]

        assert entry["status"] == "partial_error"
        assert entry["transcript_path"] is None
        assert entry["error"] == "part_002: boom"
        assert entry["segments"]["part_001"]["status"] == "transcribed"
        assert entry["segments"]["part_002"]["status"] == "error"

    def test_segmented_transcribed_keeps_segments_for_audit(
        self, tmp_path, audio_file, transcript_file
    ):
        state = {"files": {}}
        segments = _segments(tmp_path)
        segments[1]["status"] = "transcribed"

        mark_audio_segmented_transcribed(
            state, audio_file, "hash-1", transcript_file, segments
        )
        entry = state["files"][str(audio_file.resolve())]

        assert entry["status"] == "transcribed"
        assert entry["transcript_path"] == str(transcript_file)
        assert sorted(entry["segments"]) == ["part_001", "part_002"]

    def test_started_at_survives_a_status_transition(self, tmp_path, audio_file, transcript_file):
        state = {"files": {}}
        segments = _segments(tmp_path)

        mark_audio_processing_segments(state, audio_file, "hash-1", segments)
        started_at = state["files"][str(audio_file.resolve())]["started_at"]

        mark_audio_segmented_transcribed(
            state, audio_file, "hash-1", transcript_file, segments
        )

        assert state["files"][str(audio_file.resolve())]["started_at"] == started_at


# ---------------------------------------------------------------------------
# 18 — Informations nécessaires à la reprise
# ---------------------------------------------------------------------------

class TestSegmentBookkeeping:

    def test_update_segment_in_state_touches_only_that_segment(self, tmp_path, audio_file):
        state = {"files": {}}
        segments = _segments(tmp_path)
        mark_audio_processing_segments(state, audio_file, "hash-1", segments)

        segments[1]["status"] = "transcribed"
        segments[1]["updated_at"] = "2026-01-01T11:00:00"
        update_segment_in_state(state, audio_file, segments[1])

        stored = get_audio_segments_state(state, audio_file)
        assert stored["part_002"]["status"] == "transcribed"
        assert stored["part_002"]["updated_at"] == "2026-01-01T11:00:00"
        assert stored["part_001"]["status"] == "transcribed"

    def test_resume_information_survives_a_full_save_reload_cycle(
        self, isolated_sortie, tmp_path, audio_file
    ):
        state = load_project_state(PROJECT)
        segments = _segments(tmp_path)
        mark_audio_processing_segments(state, audio_file, "hash-1", segments)
        save_project_state(PROJECT, state)

        reloaded = load_project_state(PROJECT)
        stored = get_audio_segments_state(reloaded, audio_file)

        assert stored["part_001"]["transcript_path"] == segments[0]["transcript_path"]
        assert stored["part_001"]["start_seconds"] == 0.0
        assert stored["part_002"]["start_seconds"] == 900.0
        assert stored["part_002"]["end_seconds"] == 1810.0
        assert stored["part_002"]["effective_start_local"] == 10.0
        assert reloaded["files"][str(audio_file.resolve())]["hash"] == "hash-1"

    def test_segments_are_empty_for_an_unknown_file(self, tmp_path, audio_file):
        assert get_audio_segments_state({"files": {}}, audio_file) == {}


# ---------------------------------------------------------------------------
# 15 — Invalidation par hash
# ---------------------------------------------------------------------------

class TestIsAudioAlreadyTranscribed:

    def test_case_a_same_hash_and_existing_transcript(self, audio_file, transcript_file):
        """Cas A : rien à refaire."""
        state = {"files": {}}
        mark_audio_transcribed(state, audio_file, "hash-1", transcript_file)

        assert is_audio_already_transcribed(state, audio_file, "hash-1", transcript_file) is True

    def test_case_b_source_content_changed_invalidates(self, audio_file, transcript_file):
        """Cas B : le contenu source a changé → hash différent → non valide."""
        from app.file_utils import file_hash

        original_hash = file_hash(audio_file)
        state = {"files": {}}
        mark_audio_transcribed(state, audio_file, original_hash, transcript_file)

        audio_file.write_bytes(b"contenu-audio-modifie")
        new_hash = file_hash(audio_file)

        assert new_hash != original_hash
        assert is_audio_already_transcribed(state, audio_file, new_hash, transcript_file) is False

    def test_case_c_transcribed_but_transcript_file_is_gone(self, audio_file, transcript_file):
        """Cas C : état 'transcribed' mais transcript absent → non terminé."""
        state = {"files": {}}
        mark_audio_transcribed(state, audio_file, "hash-1", transcript_file)

        transcript_file.unlink()

        assert is_audio_already_transcribed(state, audio_file, "hash-1", transcript_file) is False

    def test_unknown_file_is_not_transcribed(self, audio_file, transcript_file):
        assert is_audio_already_transcribed({"files": {}}, audio_file, "hash-1", transcript_file) is False

    @pytest.mark.parametrize(
        "mark",
        ["processing", "failed", "partial_error", "processing_segments"],
    )
    def test_non_terminal_statuses_are_not_considered_transcribed(
        self, tmp_path, audio_file, transcript_file, mark
    ):
        state = {"files": {}}
        segments = _segments(tmp_path)

        if mark == "processing":
            mark_audio_processing(state, audio_file, "hash-1")
        elif mark == "failed":
            mark_audio_failed(state, audio_file, "hash-1", RuntimeError("boom"))
        elif mark == "partial_error":
            mark_audio_partial_error(state, audio_file, "hash-1", "boom", segments)
        else:
            mark_audio_processing_segments(state, audio_file, "hash-1", segments)

        assert state["files"][str(audio_file.resolve())]["status"] == mark
        assert is_audio_already_transcribed(state, audio_file, "hash-1", transcript_file) is False
