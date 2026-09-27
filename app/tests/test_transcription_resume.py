"""
Phase 0A — Filet de sécurité autour de la reprise de la transcription segmentée.

Couvre la coopération réelle entre :
    project_state  +  segment_transcripts  +  segmented_transcription_service

sans modèle Whisper, sans ffmpeg, sans réseau.

Comportements figés :
- _restore_transcribed_segments() : restauration conditionnée au hash ;
- reprise segment par segment après interruption brutale ;
- sauvegarde de project_state.json après CHAQUE segment ;
- erreur partielle : préservation des segments déjà transcrits ;
- idempotence : un second lancement ne retranscrit rien.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import app.segmented_transcription_service as sts
from app.file_utils import file_hash
from app.project_state import load_project_state

from app.tests.whisper_fakes import FakeWhisperModel

PROJECT = "demo_project"

# 3600 s produit exactement 4 segments (900 s de pas, overlap 10 s) :
#   part_001 0→910, part_002 900→1810, part_003 1800→2710, part_004 2700→3600
FOUR_SEGMENTS_DURATION = 3600.0

# 2700 s produit exactement 3 segments :
#   part_001 0→910, part_002 900→1810, part_003 1800→2700
THREE_SEGMENTS_DURATION = 2700.0

FOUR_SEGMENT_PAYLOAD = {
    "part_001.mp3": [(30.0, 40.0, "contenu un")],
    "part_002.mp3": [(30.0, 40.0, "contenu deux")],
    "part_003.mp3": [(30.0, 40.0, "contenu trois")],
    "part_004.mp3": [(30.0, 40.0, "contenu quatre")],
}


@pytest.fixture
def long_audio(tmp_path, isolated_sortie):
    """Fichier source factice + chemin de transcript final, tous deux dans tmp_path."""
    audio = tmp_path / "depot" / "Retreat 01.mp3"
    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(b"contenu-audio-original")

    output = isolated_sortie / PROJECT / "transcripts" / f"{audio.stem}.txt"
    output.parent.mkdir(parents=True, exist_ok=True)

    return audio, output


def _run(model, audio, output):
    return sts.transcribe_long_audio_with_segments(
        model=model,
        project_name=PROJECT,
        audio_path=audio,
        output_path=output,
    )


def _file_entry(audio: Path) -> dict:
    return load_project_state(PROJECT)["files"][str(audio.resolve())]


def _texts(path: Path) -> list[str]:
    return [
        line.split("] ", 1)[1]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# 12 — Restauration depuis project_state.json (unitaire)
# ---------------------------------------------------------------------------

class TestRestoreTranscribedSegments:

    def _state_with(self, audio, audio_hash, segments_payload):
        return {
            "files": {
                str(audio.resolve()): {
                    "hash": audio_hash,
                    "segments": segments_payload,
                }
            }
        }

    def _fresh_segments(self, tmp_path):
        return [
            {
                "id": "part_001",
                "audio_path": str(tmp_path / "part_001.mp3"),
                "transcript_path": str(tmp_path / "part_001.txt"),
                "start_seconds": 0.0,
                "end_seconds": 910.0,
                "effective_start_local": 0.0,
                "status": "pending",
                "updated_at": None,
                "error": None,
            }
        ]

    def test_restores_when_hash_matches_and_transcript_exists(self, tmp_path):
        audio = tmp_path / "a.mp3"
        audio.write_bytes(b"x")
        done_transcript = tmp_path / "done.txt"
        done_transcript.write_text("[00:00 -> 00:05] déjà fait\n", encoding="utf-8")

        segments = self._fresh_segments(tmp_path)
        state = self._state_with(audio, "hash-1", {
            "part_001": {
                "status": "transcribed",
                "transcript_path": str(done_transcript),
                "updated_at": "2026-01-01T10:00:00",
            }
        })

        sts._restore_transcribed_segments(state, audio, "hash-1", segments)

        assert segments[0]["status"] == "transcribed"
        assert segments[0]["transcript_path"] == str(done_transcript)
        assert segments[0]["updated_at"] == "2026-01-01T10:00:00"

    def test_different_hash_invalidates_everything(self, tmp_path):
        audio = tmp_path / "a.mp3"
        audio.write_bytes(b"x")
        done_transcript = tmp_path / "done.txt"
        done_transcript.write_text("contenu\n", encoding="utf-8")

        segments = self._fresh_segments(tmp_path)
        state = self._state_with(audio, "ancien-hash", {
            "part_001": {
                "status": "transcribed",
                "transcript_path": str(done_transcript),
            }
        })

        sts._restore_transcribed_segments(state, audio, "nouveau-hash", segments)

        assert segments[0]["status"] == "pending"

    def test_missing_transcript_file_prevents_restoration(self, tmp_path):
        audio = tmp_path / "a.mp3"
        audio.write_bytes(b"x")

        segments = self._fresh_segments(tmp_path)
        state = self._state_with(audio, "hash-1", {
            "part_001": {
                "status": "transcribed",
                "transcript_path": str(tmp_path / "disparu.txt"),
            }
        })

        sts._restore_transcribed_segments(state, audio, "hash-1", segments)

        assert segments[0]["status"] == "pending"

    def test_segment_in_error_is_not_restored(self, tmp_path):
        audio = tmp_path / "a.mp3"
        audio.write_bytes(b"x")
        partial = tmp_path / "part.txt"
        partial.write_text("contenu\n", encoding="utf-8")

        segments = self._fresh_segments(tmp_path)
        state = self._state_with(audio, "hash-1", {
            "part_001": {"status": "error", "transcript_path": str(partial)},
        })

        sts._restore_transcribed_segments(state, audio, "hash-1", segments)

        assert segments[0]["status"] == "pending"

    def test_unknown_file_leaves_segments_pending(self, tmp_path):
        audio = tmp_path / "a.mp3"
        audio.write_bytes(b"x")
        segments = self._fresh_segments(tmp_path)

        sts._restore_transcribed_segments({"files": {}}, audio, "hash-1", segments)

        assert segments[0]["status"] == "pending"


# ---------------------------------------------------------------------------
# 12 / 13 — Reprise après interruption brutale
# ---------------------------------------------------------------------------

class TestResumeAfterInterruption:

    def test_state_on_disk_survives_a_hard_interruption(self, segmented_env, long_audio):
        """
        Propriété protégée : un segment terminé doit être récupérable même si le
        processus s'arrête avant le segment suivant.

        KeyboardInterrupt n'est pas rattrapé par le service : il traverse la
        boucle, exactement comme un arrêt brutal.
        """
        audio, output = long_audio
        segmented_env.duration = FOUR_SEGMENTS_DURATION

        model = FakeWhisperModel(
            segments_by_name=FOUR_SEGMENT_PAYLOAD,
            interrupt_on={"part_003.mp3"},
        )

        with pytest.raises(KeyboardInterrupt):
            _run(model, audio, output)

        entry = _file_entry(audio)
        statuses = {sid: seg["status"] for sid, seg in entry["segments"].items()}

        assert statuses["part_001"] == "transcribed"
        assert statuses["part_002"] == "transcribed"
        assert statuses["part_003"] == "pending"
        assert statuses["part_004"] == "pending"

        for part_id in ("part_001", "part_002"):
            transcript = Path(entry["segments"][part_id]["transcript_path"])
            assert transcript.exists() and transcript.read_text(encoding="utf-8").strip()

        assert not output.exists(), "Aucun transcript final avant la fin de tous les segments."

    def test_second_run_only_transcribes_the_missing_segments(self, segmented_env, long_audio):
        audio, output = long_audio
        segmented_env.duration = FOUR_SEGMENTS_DURATION

        with pytest.raises(KeyboardInterrupt):
            _run(
                FakeWhisperModel(
                    segments_by_name=FOUR_SEGMENT_PAYLOAD,
                    interrupt_on={"part_003.mp3"},
                ),
                audio,
                output,
            )

        resumed = FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD)
        _run(resumed, audio, output)

        assert resumed.names_called == ["part_003.mp3", "part_004.mp3"], (
            "La reprise doit repartir du premier segment non transcrit."
        )

    def test_resume_preserves_previous_results_and_merges_in_order(
        self, segmented_env, long_audio
    ):
        audio, output = long_audio
        segmented_env.duration = FOUR_SEGMENTS_DURATION

        with pytest.raises(KeyboardInterrupt):
            _run(
                FakeWhisperModel(
                    segments_by_name=FOUR_SEGMENT_PAYLOAD,
                    interrupt_on={"part_003.mp3"},
                ),
                audio,
                output,
            )

        _run(FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD), audio, output)

        assert _texts(output) == [
            "contenu un",
            "contenu deux",
            "contenu trois",
            "contenu quatre",
        ]
        assert _file_entry(audio)["status"] == "transcribed"

    def test_existing_audio_segments_are_reused_not_recreated(self, segmented_env, long_audio):
        audio, output = long_audio
        segmented_env.duration = FOUR_SEGMENTS_DURATION

        with pytest.raises(KeyboardInterrupt):
            _run(
                FakeWhisperModel(
                    segments_by_name=FOUR_SEGMENT_PAYLOAD,
                    interrupt_on={"part_003.mp3"},
                ),
                audio,
                output,
            )

        created_after_run_1 = list(segmented_env.created_segments)
        _run(FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD), audio, output)

        assert len(created_after_run_1) == 4
        assert segmented_env.created_segments == created_after_run_1, (
            "Les fichiers audio de segments déjà découpés doivent être réutilisés."
        )

    def test_changing_the_source_file_discards_previous_segments(self, segmented_env, long_audio):
        audio, output = long_audio
        segmented_env.duration = FOUR_SEGMENTS_DURATION

        first_hash = file_hash(audio)
        _run(FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD), audio, output)

        audio.write_bytes(b"contenu-audio-completement-different")
        assert file_hash(audio) != first_hash

        retried = FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD)
        _run(retried, audio, output)

        assert retried.names_called == [
            "part_001.mp3",
            "part_002.mp3",
            "part_003.mp3",
            "part_004.mp3",
        ]


# ---------------------------------------------------------------------------
# 13 — Sauvegarde après chaque segment
# ---------------------------------------------------------------------------

class TestSaveAfterEachSegment:

    def test_one_save_per_segment_plus_opening_and_closing_saves(
        self, segmented_env, long_audio
    ):
        audio, output = long_audio
        segmented_env.duration = FOUR_SEGMENTS_DURATION

        _run(FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD), audio, output)

        # 1 (mark_audio_processing_segments) + 4 (un par segment) + 1 (final)
        assert segmented_env.save_count == 6, (
            "Une régression repoussant la sauvegarde à la fin du fichier serait "
            "détectée ici."
        )

    def test_each_save_reflects_exactly_the_segments_done_so_far(
        self, segmented_env, long_audio
    ):
        audio, output = long_audio
        segmented_env.duration = FOUR_SEGMENTS_DURATION

        _run(FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD), audio, output)

        assert segmented_env.transcribed_ids_at_save(0, audio) == []
        assert segmented_env.transcribed_ids_at_save(1, audio) == ["part_001"]
        assert segmented_env.transcribed_ids_at_save(2, audio) == ["part_001", "part_002"]
        assert segmented_env.transcribed_ids_at_save(3, audio) == [
            "part_001", "part_002", "part_003",
        ]
        assert segmented_env.transcribed_ids_at_save(4, audio) == [
            "part_001", "part_002", "part_003", "part_004",
        ]

    def test_save_happens_before_the_next_segment_is_transcribed(
        self, segmented_env, long_audio, monkeypatch
    ):
        """L'ordre réel est : transcrire N → sauvegarder N → transcrire N+1."""
        audio, output = long_audio
        segmented_env.duration = FOUR_SEGMENTS_DURATION

        timeline: list[str] = []

        real_transcribe_one = sts._transcribe_one_segment

        def _traced(**kwargs):
            timeline.append(f"transcribe:{kwargs['segment']['id']}")
            return real_transcribe_one(**kwargs)

        real_save = sts.save_project_state

        def _traced_save(project_name, state):
            timeline.append("save")
            return real_save(project_name, state)

        monkeypatch.setattr(sts, "_transcribe_one_segment", _traced)
        monkeypatch.setattr(sts, "save_project_state", _traced_save)

        _run(FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD), audio, output)

        assert timeline == [
            "save",
            "transcribe:part_001", "save",
            "transcribe:part_002", "save",
            "transcribe:part_003", "save",
            "transcribe:part_004", "save",
            "save",
        ]

    def test_state_file_on_disk_is_rewritten_at_each_segment(self, segmented_env, long_audio):
        audio, output = long_audio
        segmented_env.duration = FOUR_SEGMENTS_DURATION
        state_path = segmented_env.sortie / PROJECT / "project_state.json"

        seen: list[int] = []
        original_payload = FOUR_SEGMENT_PAYLOAD

        class _ObservingModel(FakeWhisperModel):
            def transcribe(self, audio_path, **kwargs):
                if state_path.exists():
                    data = json.loads(state_path.read_text(encoding="utf-8"))
                    segments = data["files"][str(audio.resolve())]["segments"]
                    seen.append(
                        sum(1 for s in segments.values() if s["status"] == "transcribed")
                    )
                return super().transcribe(audio_path, **kwargs)

        _run(_ObservingModel(segments_by_name=original_payload), audio, output)

        assert seen == [0, 1, 2, 3], (
            "Avant de transcrire le segment N, le disque doit déjà contenir N-1 "
            "segments terminés."
        )


# ---------------------------------------------------------------------------
# 14 — Erreur partielle
# ---------------------------------------------------------------------------

class TestPartialError:

    @pytest.fixture
    def failing_run(self, segmented_env, long_audio):
        audio, output = long_audio
        segmented_env.duration = THREE_SEGMENTS_DURATION

        model = FakeWhisperModel(
            segments_by_name=FOUR_SEGMENT_PAYLOAD,
            fail_on={"part_003.mp3"},
        )

        with pytest.raises(RuntimeError) as excinfo:
            _run(model, audio, output)

        return audio, output, model, excinfo.value

    def test_runtime_error_names_the_failing_segment(self, failing_run):
        _, _, _, error = failing_run
        assert "part_003" in str(error)

    def test_successful_segments_remain_on_disk(self, failing_run):
        audio, _, _, _ = failing_run
        entry = _file_entry(audio)

        for part_id, expected in (("part_001", "contenu un"), ("part_002", "contenu deux")):
            transcript = Path(entry["segments"][part_id]["transcript_path"])
            assert transcript.exists()
            assert expected in transcript.read_text(encoding="utf-8")

    def test_state_reflects_the_partial_failure(self, failing_run):
        audio, _, _, _ = failing_run
        entry = _file_entry(audio)

        assert entry["status"] == "partial_error"
        assert entry["transcript_path"] is None
        assert "part_003" in entry["error"]
        assert entry["segments"]["part_001"]["status"] == "transcribed"
        assert entry["segments"]["part_002"]["status"] == "transcribed"
        assert entry["segments"]["part_003"]["status"] == "error"
        assert entry["segments"]["part_003"]["error"]

    def test_file_is_not_marked_as_correctly_transcribed(self, failing_run):
        audio, output, _, _ = failing_run

        assert _file_entry(audio)["status"] != "transcribed"
        assert not output.exists(), "Aucun transcript final ne doit être produit."

    def test_all_remaining_segments_are_still_attempted(self, failing_run):
        """V1 ne s'arrête pas au premier segment en erreur : la boucle va au bout."""
        _, _, model, _ = failing_run
        assert model.names_called == ["part_001.mp3", "part_002.mp3", "part_003.mp3"]

    def test_next_run_reuses_completed_segments_and_finishes(self, failing_run, segmented_env):
        audio, output, _, _ = failing_run

        retried = FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD)
        _run(retried, audio, output)

        assert retried.names_called == ["part_003.mp3"]
        assert _texts(output) == ["contenu un", "contenu deux", "contenu trois"]
        assert _file_entry(audio)["status"] == "transcribed"


# ---------------------------------------------------------------------------
# 14 bis — Phase 0B : fusion refusée quand un transcript de segment manque
# ---------------------------------------------------------------------------

class TestMergeRefusedOnMissingSegmentTranscript:
    """
    Correction 0B.1 — un transcript de segment attendu qui disparaît (écriture
    perdue, nettoyage externe) ne doit jamais produire un transcript final
    prétendument complet ni un statut "transcribed".
    """

    @pytest.fixture
    def lost_writes(self, monkeypatch) -> set[str]:
        """
        Segments dont le transcript n'est jamais écrit alors que la boucle les
        déclare réussis. Le set est mutable : un test peut le vider pour simuler
        un lancement suivant qui se déroule normalement.
        """
        lost: set[str] = set()
        real_transcribe_one = sts._transcribe_one_segment

        def _maybe_lose(**kwargs):
            if kwargs["segment"]["id"] in lost:
                return
            real_transcribe_one(**kwargs)

        monkeypatch.setattr(sts, "_transcribe_one_segment", _maybe_lose)
        return lost

    @pytest.fixture
    def refused_run(self, segmented_env, long_audio, lost_writes):
        audio, output = long_audio
        segmented_env.duration = THREE_SEGMENTS_DURATION
        lost_writes.add("part_002")

        model = FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD)

        with pytest.raises(RuntimeError) as excinfo:
            _run(model, audio, output)

        return audio, output, model, excinfo.value

    def test_error_names_the_missing_segment(self, refused_run):
        _, _, _, error = refused_run
        assert "part_002" in str(error)

    def test_no_final_transcript_is_produced(self, refused_run):
        _, output, _, _ = refused_run
        assert not output.exists(), (
            "Un transcript final ne doit pas exister quand un segment manque."
        )

    def test_file_is_not_marked_transcribed(self, refused_run):
        audio, _, _, _ = refused_run
        entry = _file_entry(audio)

        assert entry["status"] == "partial_error"
        assert entry["transcript_path"] is None
        assert "part_002" in entry["error"]

    def test_completed_segments_are_preserved(self, refused_run):
        audio, _, _, _ = refused_run
        entry = _file_entry(audio)

        for part_id, expected in (("part_001", "contenu un"), ("part_003", "contenu trois")):
            transcript = Path(entry["segments"][part_id]["transcript_path"])
            assert transcript.exists()
            assert expected in transcript.read_text(encoding="utf-8")

    def test_next_run_retranscribes_only_the_missing_segment_and_finishes(
        self, refused_run, lost_writes
    ):
        audio, output, _, _ = refused_run
        lost_writes.clear()

        retried = FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD)
        _run(retried, audio, output)

        assert retried.names_called == ["part_002.mp3"]
        assert _texts(output) == ["contenu un", "contenu deux", "contenu trois"]
        assert _file_entry(audio)["status"] == "transcribed"

    def test_existing_valid_transcript_survives_a_refused_merge(
        self, segmented_env, long_audio, lost_writes
    ):
        """Un transcript final valide d'un run précédent n'est pas tronqué."""
        audio, output = long_audio
        segmented_env.duration = THREE_SEGMENTS_DURATION

        _run(FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD), audio, output)
        previous = output.read_text(encoding="utf-8")

        # Le transcript de part_002 disparaît : la reprise le retranscrit, mais
        # l'écriture est à nouveau perdue.
        state = load_project_state(PROJECT)
        segments = state["files"][str(audio.resolve())]["segments"]
        Path(segments["part_002"]["transcript_path"]).unlink()
        lost_writes.add("part_002")

        with pytest.raises(RuntimeError):
            _run(FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD), audio, output)

        assert output.read_text(encoding="utf-8") == previous


# ---------------------------------------------------------------------------
# 19 — Idempotence
# ---------------------------------------------------------------------------

class TestIdempotence:

    def test_second_run_does_not_call_whisper_again(self, segmented_env, long_audio):
        audio, output = long_audio
        segmented_env.duration = THREE_SEGMENTS_DURATION

        first = FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD)
        _run(first, audio, output)
        assert first.call_count == 3

        second = FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD)
        _run(second, audio, output)

        assert second.call_count == 0, (
            "Tous les segments sont déjà transcrits : aucun appel Whisper attendu."
        )

    def test_second_run_produces_an_identical_transcript(self, segmented_env, long_audio):
        audio, output = long_audio
        segmented_env.duration = THREE_SEGMENTS_DURATION

        _run(FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD), audio, output)
        after_first = output.read_text(encoding="utf-8")

        _run(FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD), audio, output)

        assert output.read_text(encoding="utf-8") == after_first

    def test_second_run_keeps_the_state_consistent(self, segmented_env, long_audio):
        audio, output = long_audio
        segmented_env.duration = THREE_SEGMENTS_DURATION

        _run(FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD), audio, output)
        started_at = _file_entry(audio)["started_at"]

        _run(FakeWhisperModel(segments_by_name=FOUR_SEGMENT_PAYLOAD), audio, output)
        entry = _file_entry(audio)

        assert entry["status"] == "transcribed"
        assert entry["transcript_path"] == str(output)
        assert entry["started_at"] == started_at
        assert all(seg["status"] == "transcribed" for seg in entry["segments"].values())
