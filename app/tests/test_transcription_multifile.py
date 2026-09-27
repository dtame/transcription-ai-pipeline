"""
Phase 0A — Filet de sécurité autour de la transcription multi-fichiers.

Couvre l'étape « transcription » telle qu'elle est réellement exécutée par le
pipeline : app.pipeline_runner._run_transcription().

Comportements figés :
- ordre dans lequel les fichiers audio sont considérés (tri alphabétique V1) ;
- un transcript par audio, sans écrasement entre fichiers ;
- reprise indépendante par fichier après échec ;
- invalidation par hash fichier par fichier ;
- idempotence : un second passage ne relance aucune transcription ;
- aiguillage court / long vers la transcription segmentée.

Aucun modèle Whisper réel, aucun ffmpeg, aucun accès aux projets réels.
"""

from __future__ import annotations

import pytest

import app.pipeline_runner as pipeline_runner
import app.project_manager as project_manager
import app.segmented_transcription_service as sts
import app.transcription_service as transcription_service
from app.file_utils import file_hash
from app.project_state import load_project_state

from app.tests.whisper_fakes import FakeWhisperModel


@pytest.fixture
def direct_transcription_env(monkeypatch, isolated_sortie, silence_logs):
    """Tout est court : pas de segmentation, durée audio simulée, pas de ffprobe."""
    monkeypatch.setattr(sts, "should_segment_audio", lambda audio_path: False)
    monkeypatch.setattr(pipeline_runner, "get_audio_duration_seconds", lambda path: 600.0)
    monkeypatch.setattr(transcription_service, "print_progress", lambda **kwargs: None)


def _entry(project, audio_path) -> dict:
    return load_project_state(project).get("files", {}).get(str(audio_path.resolve()), {})


# ---------------------------------------------------------------------------
# 17 — Ordre de découverte des fichiers
# ---------------------------------------------------------------------------

class TestProjectDiscoveryOrder:

    @pytest.fixture
    def isolated_depot(self, tmp_path, monkeypatch):
        depot = tmp_path / "depot"
        depot.mkdir()

        monkeypatch.setattr(project_manager, "DEPOT_DIR", depot)
        monkeypatch.setattr(project_manager, "SORTIE_DIR", tmp_path / "sortie")
        monkeypatch.setattr(project_manager, "TEMP_DIR", tmp_path / "temp")
        monkeypatch.setattr(project_manager, "ARCHIVES_DIR", tmp_path / "archives")
        monkeypatch.setattr(project_manager, "REJETS_DIR", tmp_path / "rejets")

        return depot

    def test_audio_files_are_ordered_alphabetically_not_numerically(self, isolated_depot):
        """
        Comportement V1 ACTUEL (KNOWN V1 BUG #5 du rapport Phase 0A) :
        le tri est lexicographique, donc « Retreat 10 » passe avant « Retreat 2 ».

        Ce test documente l'existant ; la correction est prévue pour une phase
        ultérieure et changera volontairement cette assertion.
        """
        folder = isolated_depot / "retreat"
        folder.mkdir()
        for name in ("Retreat 1.mp3", "Retreat 2.mp3", "Retreat 10.mp3"):
            (folder / name).write_bytes(b"audio")

        projects = project_manager.discover_projects()

        assert [p.name for p in projects] == ["retreat"]
        assert [f.name for f in projects[0].audio_files] == [
            "Retreat 1.mp3",
            "Retreat 10.mp3",
            "Retreat 2.mp3",
        ]

    def test_unsupported_extensions_are_ignored(self, isolated_depot):
        folder = isolated_depot / "retreat"
        folder.mkdir()
        (folder / "a.mp3").write_bytes(b"audio")
        (folder / "notes.txt").write_text("pas de l'audio", encoding="utf-8")

        projects = project_manager.discover_projects()

        assert [f.name for f in projects[0].audio_files] == ["a.mp3"]

    def test_projects_are_ordered_alphabetically(self, isolated_depot):
        for project_name in ("zeta", "alpha", "milieu"):
            folder = isolated_depot / project_name
            folder.mkdir()
            (folder / "a.mp3").write_bytes(b"audio")

        projects = project_manager.discover_projects()

        assert [p.name for p in projects] == ["alpha", "milieu", "zeta"]


# ---------------------------------------------------------------------------
# 17 — Un transcript par audio
# ---------------------------------------------------------------------------

class TestMultipleAudioFiles:

    @pytest.fixture
    def project(self, make_audio_project):
        return make_audio_project(
            name="retreat",
            audio_files={
                "lesson_01.mp3": b"audio-un",
                "lesson_02.mp3": b"audio-deux",
                "lesson_03.mp3": b"audio-trois",
            },
        )

    @pytest.fixture
    def model(self):
        return FakeWhisperModel(
            segments_by_name={
                "lesson_01.mp3": [(0.0, 5.0, "texte un")],
                "lesson_02.mp3": [(0.0, 5.0, "texte deux")],
                "lesson_03.mp3": [(0.0, 5.0, "texte trois")],
            }
        )

    def test_every_audio_gets_its_own_transcript(
        self, direct_transcription_env, project, model
    ):
        result = pipeline_runner._run_transcription(model, project)

        assert result["status"] == "success"
        for index, word in enumerate(("un", "deux", "trois"), start=1):
            transcript = project.transcripts_dir / f"lesson_0{index}.txt"
            assert transcript.exists()
            assert f"texte {word}" in transcript.read_text(encoding="utf-8")

    def test_files_are_processed_in_project_order(
        self, direct_transcription_env, project, model
    ):
        pipeline_runner._run_transcription(model, project)

        assert model.names_called == ["lesson_01.mp3", "lesson_02.mp3", "lesson_03.mp3"]

    def test_transcripts_do_not_overwrite_each_other(
        self, direct_transcription_env, project, model
    ):
        pipeline_runner._run_transcription(model, project)

        contents = [
            (project.transcripts_dir / f"lesson_0{i}.txt").read_text(encoding="utf-8")
            for i in (1, 2, 3)
        ]
        assert len(set(contents)) == 3, "Chaque audio doit produire un contenu distinct."
        assert len(list(project.transcripts_dir.glob("*.txt"))) == 3

    def test_state_tracks_each_file_independently(
        self, direct_transcription_env, project, model
    ):
        pipeline_runner._run_transcription(model, project)

        for audio_path in project.audio_files:
            entry = _entry(project, audio_path)
            assert entry["status"] == "transcribed"
            assert entry["hash"] == file_hash(audio_path)
            assert entry["transcript_path"].endswith(f"{audio_path.stem}.txt")


# ---------------------------------------------------------------------------
# 17 / 19 — Reprise indépendante et idempotence
# ---------------------------------------------------------------------------

class TestPerFileResumeAndIdempotence:

    @pytest.fixture
    def project(self, make_audio_project):
        return make_audio_project(
            name="retreat",
            audio_files={
                "lesson_01.mp3": b"audio-un",
                "lesson_02.mp3": b"audio-deux",
                "lesson_03.mp3": b"audio-trois",
            },
        )

    def _model(self, **kwargs):
        return FakeWhisperModel(segments=[(0.0, 5.0, "texte")], **kwargs)

    def test_second_run_transcribes_nothing(self, direct_transcription_env, project):
        pipeline_runner._run_transcription(self._model(), project)

        second = self._model()
        result = pipeline_runner._run_transcription(second, project)

        assert second.call_count == 0
        assert result["status"] == "success"

    def test_a_failing_file_does_not_block_the_others(self, direct_transcription_env, project):
        model = self._model(fail_on={"lesson_02.mp3"})

        result = pipeline_runner._run_transcription(model, project)

        assert result["status"] == "error"
        assert model.names_called == ["lesson_01.mp3", "lesson_02.mp3", "lesson_03.mp3"]
        assert _entry(project, project.audio_files[0])["status"] == "transcribed"
        assert _entry(project, project.audio_files[1])["status"] == "failed"
        assert _entry(project, project.audio_files[2])["status"] == "transcribed"

    def test_failed_file_is_retried_alone_on_the_next_run(
        self, direct_transcription_env, project
    ):
        pipeline_runner._run_transcription(self._model(fail_on={"lesson_02.mp3"}), project)

        retried = self._model()
        result = pipeline_runner._run_transcription(retried, project)

        assert retried.names_called == ["lesson_02.mp3"]
        assert result["status"] == "success"
        assert _entry(project, project.audio_files[1])["status"] == "transcribed"

    def test_modifying_one_source_file_invalidates_only_that_file(
        self, direct_transcription_env, project
    ):
        pipeline_runner._run_transcription(self._model(), project)

        project.audio_files[2].write_bytes(b"audio-trois-version-corrigee")

        rerun = self._model()
        pipeline_runner._run_transcription(rerun, project)

        assert rerun.names_called == ["lesson_03.mp3"]

    def test_deleting_a_transcript_forces_only_that_file_again(
        self, direct_transcription_env, project
    ):
        pipeline_runner._run_transcription(self._model(), project)

        (project.transcripts_dir / "lesson_01.txt").unlink()

        rerun = self._model()
        pipeline_runner._run_transcription(rerun, project)

        assert rerun.names_called == ["lesson_01.mp3"]
        assert (project.transcripts_dir / "lesson_01.txt").exists()

    def test_crash_mid_transcription_is_not_reported_as_success(
        self, direct_transcription_env, project, monkeypatch
    ):
        """
        Une exception levée pendant l'écriture ne laisse aucun transcript sur le
        disque (écriture atomique, cf. test_transcription_service.py) et l'état
        passe à "failed" : le fichier est retranscrit au lancement suivant.
        """
        from app.tests.whisper_fakes import ExplodingIterationModel

        class _CrashOnSecond(ExplodingIterationModel):
            def transcribe(self, audio_path, **kwargs):
                if "lesson_02" in str(audio_path):
                    return super().transcribe(audio_path, **kwargs)
                return FakeWhisperModel(segments=[(0.0, 5.0, "ok")]).transcribe(
                    audio_path, **kwargs
                )

        model = _CrashOnSecond(segments_before_error=[(0.0, 2.0, "partiel")])
        result = pipeline_runner._run_transcription(model, project)

        assert result["status"] == "error"
        assert not (project.transcripts_dir / "lesson_02.txt").exists()
        assert _entry(project, project.audio_files[1])["status"] == "failed"

        rerun = self._model()
        pipeline_runner._run_transcription(rerun, project)
        assert rerun.names_called == ["lesson_02.mp3"]


# ---------------------------------------------------------------------------
# 17 — Aiguillage court / long au sein d'un même projet
# ---------------------------------------------------------------------------

class TestShortAndLongFilesInTheSameProject:

    def test_long_file_uses_segmentation_and_short_file_does_not(
        self, monkeypatch, segmented_env, make_audio_project
    ):
        project = make_audio_project(
            name="retreat",
            audio_files={
                "long_talk.mp3": b"audio-long",
                "short_intro.mp3": b"audio-court",
            },
        )

        segmented_env.duration = 2700.0  # 3 segments pour le fichier long
        monkeypatch.setattr(
            sts,
            "should_segment_audio",
            lambda audio_path: audio_path.name == "long_talk.mp3",
        )
        monkeypatch.setattr(pipeline_runner, "get_audio_duration_seconds", lambda path: 600.0)
        monkeypatch.setattr(transcription_service, "print_progress", lambda **kwargs: None)

        model = FakeWhisperModel(
            segments_by_name={
                "short_intro.mp3": [(0.0, 5.0, "intro courte")],
                "part_001.mp3": [(30.0, 40.0, "long un")],
                "part_002.mp3": [(30.0, 40.0, "long deux")],
                "part_003.mp3": [(30.0, 40.0, "long trois")],
            }
        )

        result = pipeline_runner._run_transcription(model, project)

        assert result["status"] == "success"
        # project.audio_files est trié : long_talk.mp3 avant short_intro.mp3
        assert model.names_called == [
            "part_001.mp3",
            "part_002.mp3",
            "part_003.mp3",
            "short_intro.mp3",
        ]

        long_transcript = project.transcripts_dir / "long_talk.txt"
        short_transcript = project.transcripts_dir / "short_intro.txt"

        assert "long un" in long_transcript.read_text(encoding="utf-8")
        assert "long trois" in long_transcript.read_text(encoding="utf-8")
        assert short_transcript.read_text(encoding="utf-8").strip() == (
            "[00:00 -> 00:05] intro courte"
        )

        assert "segments" in _entry(project, project.audio_files[0])
        assert "segments" not in _entry(project, project.audio_files[1])
