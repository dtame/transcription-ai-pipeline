"""
Phase 0A — Filet de sécurité autour de la transcription directe (fichiers courts).

Fige le comportement V1 de app.transcription_service.transcribe_audio_to_txt() :

- écriture du transcript, ordre et contenu des segments ;
- format actuel des timestamps ([MM:SS] / [HH:MM:SS], secondes tronquées) ;
- application de timestamp_offset ;
- langue détectée conservée, quelle qu'elle soit (contrat V2, Phase 1 — remplace
  le forçage vers l'anglais des langues hors fr/en) ;
- politique d'erreur actuelle (exception propagée telle quelle).

Aucun modèle Whisper réel n'est chargé.
"""

from __future__ import annotations

import pytest

from app.audio_utils import format_timestamp
from app.config import ALLOWED_LANGUAGES
from app.transcript_capture import read_audio_capture
from app.transcription_service import transcribe_audio_to_txt

from app.tests.whisper_fakes import (
    ExplodingIterationModel,
    FakeWhisperInfo,
    FakeWhisperModel,
    FakeWhisperSegment,
)


@pytest.fixture(autouse=True)
def _quiet_progress(monkeypatch):
    """Neutralise la barre de progression (bruit de sortie uniquement)."""
    import app.transcription_service as transcription_service

    monkeypatch.setattr(transcription_service, "print_progress", lambda **kwargs: None)


@pytest.fixture
def audio_file(tmp_path):
    path = tmp_path / "lesson.mp3"
    path.write_bytes(b"not-real-audio")
    return path


def _lines(path):
    return path.read_text(encoding="utf-8").splitlines()


# ---------------------------------------------------------------------------
# 7.1 — Écriture du transcript
# ---------------------------------------------------------------------------

class TestTranscriptWriting:

    def test_transcript_file_is_created(self, tmp_path, audio_file):
        output = tmp_path / "out.txt"
        model = FakeWhisperModel(segments=[(0.0, 2.0, "Bonjour")], language="fr")

        transcribe_audio_to_txt(
            model=model,
            audio_path=audio_file,
            output_path=output,
            total_duration_seconds=120.0,
        )

        assert output.exists(), "Le fichier transcript doit être créé."

    def test_segments_written_in_order_with_current_format(self, tmp_path, audio_file):
        output = tmp_path / "out.txt"
        model = FakeWhisperModel(
            segments=[
                (0.0, 2.4, "  Première phrase.  "),
                (2.4, 5.9, "Deuxième phrase."),
                (5.9, 9.1, "Troisième phrase."),
            ],
            language="fr",
        )

        transcribe_audio_to_txt(
            model=model,
            audio_path=audio_file,
            output_path=output,
            total_duration_seconds=600.0,
        )

        assert _lines(output) == [
            "[00:00 -> 00:02] Première phrase.",
            "[00:02 -> 00:05] Deuxième phrase.",
            "[00:05 -> 00:09] Troisième phrase.",
        ]

    def test_segment_text_is_stripped(self, tmp_path, audio_file):
        output = tmp_path / "out.txt"
        model = FakeWhisperModel(segments=[(0.0, 1.0, "\t  texte entouré d'espaces  \n")])

        transcribe_audio_to_txt(
            model=model,
            audio_path=audio_file,
            output_path=output,
            total_duration_seconds=60.0,
        )

        assert _lines(output) == ["[00:00 -> 00:01] texte entouré d'espaces"]

    def test_no_segment_produces_empty_transcript(self, tmp_path, audio_file):
        output = tmp_path / "out.txt"
        model = FakeWhisperModel(segments=[])

        transcribe_audio_to_txt(
            model=model,
            audio_path=audio_file,
            output_path=output,
            total_duration_seconds=60.0,
        )

        assert output.exists()
        assert output.read_text(encoding="utf-8") == ""

    def test_existing_output_is_overwritten_not_appended(self, tmp_path, audio_file):
        output = tmp_path / "out.txt"
        output.write_text("ANCIEN CONTENU\n", encoding="utf-8")
        model = FakeWhisperModel(segments=[(0.0, 1.0, "nouveau")])

        transcribe_audio_to_txt(
            model=model,
            audio_path=audio_file,
            output_path=output,
            total_duration_seconds=60.0,
        )

        assert "ANCIEN CONTENU" not in output.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 7.1 — Format des timestamps (comportement V1 : troncature à la seconde)
# ---------------------------------------------------------------------------

class TestTimestampFormat:

    @pytest.mark.parametrize(
        "seconds, expected",
        [
            (0.0, "00:00"),
            (2.4, "00:02"),      # troncature, pas d'arrondi
            (2.9, "00:02"),      # troncature, pas d'arrondi
            (59.999, "00:59"),
            (60.0, "01:00"),
            (599.0, "09:59"),
            (3599.0, "59:59"),   # < 1 h → MM:SS
            (3600.0, "01:00:00"),  # ≥ 1 h → HH:MM:SS
            (3725.5, "01:02:05"),
        ],
    )
    def test_format_timestamp_v1_contract(self, seconds, expected):
        assert format_timestamp(seconds) == expected

    def test_transcript_switches_to_hours_format_past_one_hour(self, tmp_path, audio_file):
        output = tmp_path / "out.txt"
        model = FakeWhisperModel(segments=[(3599.0, 3661.0, "franchit une heure")])

        transcribe_audio_to_txt(
            model=model,
            audio_path=audio_file,
            output_path=output,
            total_duration_seconds=7200.0,
        )

        assert _lines(output) == ["[59:59 -> 01:01:01] franchit une heure"]

    def test_timestamp_offset_is_added_to_local_timestamps(self, tmp_path, audio_file):
        output = tmp_path / "out.txt"
        model = FakeWhisperModel(
            segments=[
                (12.0, 18.0, "premier"),
                (30.0, 42.0, "second"),
            ]
        )

        transcribe_audio_to_txt(
            model=model,
            audio_path=audio_file,
            output_path=output,
            total_duration_seconds=3600.0,
            timestamp_offset=900.0,
        )

        assert _lines(output) == [
            "[15:12 -> 15:18] premier",
            "[15:30 -> 15:42] second",
        ]


# ---------------------------------------------------------------------------
# 7.2 — Langue détectée
# ---------------------------------------------------------------------------

class TestLanguageDetection:

    @pytest.mark.parametrize("language", sorted(ALLOWED_LANGUAGES))
    def test_allowed_language_is_returned_and_transcribes_once(
        self, tmp_path, audio_file, language
    ):
        output = tmp_path / "out.txt"
        model = FakeWhisperModel(segments=[(0.0, 1.0, "texte")], language=language)

        detected = transcribe_audio_to_txt(
            model=model,
            audio_path=audio_file,
            output_path=output,
            total_duration_seconds=60.0,
        )

        assert detected == language
        assert model.call_count == 1, "Une langue autorisée ne doit pas déclencher de seconde passe."
        assert model.calls[0][1] == {}, "Aucun forçage de langue ne doit être appliqué."

    @pytest.mark.parametrize("language", ["de", "es", "sw"])
    def test_language_outside_fr_en_is_preserved(self, tmp_path, audio_file, language):
        """
        Contrat V2 (Phase 1) — remplace volontairement le comportement V1 figé en
        Phase 0A, qui retranscrivait intégralement le fichier en anglais dès que
        la langue détectée sortait de ALLOWED_LANGUAGES.

        La langue réellement détectée est désormais retournée telle quelle et
        aucune seconde passe n'est déclenchée.
        """
        output = tmp_path / "out.txt"
        model = FakeWhisperModel(segments=[(0.0, 1.0, "texte")], language=language)

        detected = transcribe_audio_to_txt(
            model=model,
            audio_path=audio_file,
            output_path=output,
            total_duration_seconds=60.0,
        )

        assert detected == language
        assert model.call_count == 1, "Aucune retranscription forcée ne doit avoir lieu."
        assert model.calls[0][1] == {}, "Aucun forçage de langue ne doit être appliqué."

    def test_transcript_keeps_the_detected_language_content(self, tmp_path, audio_file):
        """Le texte écrit est celui de la langue détectée, jamais une traduction."""

        class _TwoPassModel:
            def __init__(self):
                self.calls = []

            def transcribe(self, audio_path, **kwargs):
                self.calls.append(kwargs)
                if kwargs.get("language") == "en":
                    return (
                        iter([FakeWhisperSegment(0.0, 1.0, "english pass")]),
                        FakeWhisperInfo("en"),
                    )
                return (
                    iter([FakeWhisperSegment(0.0, 1.0, "german pass")]),
                    FakeWhisperInfo("de"),
                )

        output = tmp_path / "out.txt"
        model = _TwoPassModel()

        transcribe_audio_to_txt(
            model=model,
            audio_path=audio_file,
            output_path=output,
            total_duration_seconds=60.0,
        )

        content = output.read_text(encoding="utf-8")
        assert "german pass" in content
        assert "english pass" not in content
        assert model.calls == [{}]


# ---------------------------------------------------------------------------
# 7.3 — Erreur du modèle
# ---------------------------------------------------------------------------

class TestStructuredCapture:
    """Phase 1 — capture structurée d'un fichier audio court (contrat V2)."""

    def _capture(self, tmp_path, audio_file, segments, language="fr", duration=600.0):
        capture_path = tmp_path / "transcript_capture" / "lesson.json"

        transcribe_audio_to_txt(
            model=FakeWhisperModel(segments=segments, language=language),
            audio_path=audio_file,
            output_path=tmp_path / "out.txt",
            total_duration_seconds=duration,
            capture_path=capture_path,
        )

        return read_audio_capture(capture_path)

    def test_no_capture_is_written_without_an_explicit_path(self, tmp_path, audio_file):
        """Le chemin legacy (chunks V1) n'écrit aucune capture."""
        transcribe_audio_to_txt(
            model=FakeWhisperModel(segments=[(0.0, 2.0, "x")]),
            audio_path=audio_file,
            output_path=tmp_path / "out.txt",
            total_duration_seconds=60.0,
        )

        assert list(tmp_path.glob("**/*.json")) == []

    def test_a_short_file_produces_a_single_technical_part(self, tmp_path, audio_file):
        capture = self._capture(tmp_path, audio_file, [(0.0, 2.0, "x")])

        assert capture.mode == "direct"
        assert [part.id for part in capture.parts] == ["part_001"]
        assert capture.parts[0].start_seconds == 0.0
        assert capture.parts[0].effective_start_local == 0.0

    def test_capture_keeps_the_precise_timestamps_and_text(self, tmp_path, audio_file):
        capture = self._capture(
            tmp_path, audio_file, [(12.37, 18.94, "  texte entouré  ")]
        )

        assert capture.parts[0].segments[0].start == 12.37
        assert capture.parts[0].segments[0].end == 18.94
        assert capture.parts[0].segments[0].text == "texte entouré"

    def test_capture_records_filename_duration_and_language(self, tmp_path, audio_file):
        capture = self._capture(
            tmp_path, audio_file, [(0.0, 2.0, "x")], language="sw", duration=321.5
        )

        assert capture.filename == "lesson.mp3"
        assert capture.duration_seconds == 321.5
        assert capture.parts[0].detected_language == "sw"

    def test_capture_applies_the_timestamp_offset(self, tmp_path, audio_file):
        capture_path = tmp_path / "capture.json"

        transcribe_audio_to_txt(
            model=FakeWhisperModel(segments=[(12.0, 18.0, "décalé")]),
            audio_path=audio_file,
            output_path=tmp_path / "out.txt",
            total_duration_seconds=3600.0,
            timestamp_offset=900.0,
            capture_path=capture_path,
        )

        segment = read_audio_capture(capture_path).parts[0].segments[0]
        assert (segment.start, segment.end) == (912.0, 918.0)

    def test_capture_is_empty_for_a_silent_file(self, tmp_path, audio_file):
        capture = self._capture(tmp_path, audio_file, [])

        assert capture.parts[0].segments == []


class TestModelErrors:

    def test_model_exception_is_propagated_unchanged(self, tmp_path, audio_file):
        output = tmp_path / "out.txt"
        model = FakeWhisperModel(fail_on={audio_file.name})

        with pytest.raises(RuntimeError, match="fake whisper failure"):
            transcribe_audio_to_txt(
                model=model,
                audio_path=audio_file,
                output_path=output,
                total_duration_seconds=60.0,
            )

    def test_no_transcript_created_when_transcribe_fails(self, tmp_path, audio_file):
        output = tmp_path / "out.txt"
        model = FakeWhisperModel(fail_on={audio_file.name})

        with pytest.raises(RuntimeError):
            transcribe_audio_to_txt(
                model=model,
                audio_path=audio_file,
                output_path=output,
                total_duration_seconds=60.0,
            )

        assert not output.exists(), "Aucun faux succès : pas de transcript en cas d'échec."

    def test_crash_during_iteration_propagates_without_partial_file(
        self, tmp_path, audio_file
    ):
        """
        Correction 0B.2 : si Whisper casse pendant l'itération des segments,
        l'exception est toujours propagée telle quelle, mais aucun transcript
        partiel ne subsiste sur le disque.
        """
        output = tmp_path / "out.txt"
        model = ExplodingIterationModel(
            segments_before_error=[(0.0, 2.0, "avant le crash")]
        )

        with pytest.raises(RuntimeError, match="mid-iteration"):
            transcribe_audio_to_txt(
                model=model,
                audio_path=audio_file,
                output_path=output,
                total_duration_seconds=60.0,
            )

        assert not output.exists()


# ---------------------------------------------------------------------------
# Phase 0B — Écriture atomique du transcript direct (correction 0B.2)
# ---------------------------------------------------------------------------

class TestAtomicTranscriptWriting:

    def _leftovers(self, directory, output):
        """Fichiers présents dans le répertoire de sortie, hors transcript final."""
        return sorted(
            p.name for p in directory.iterdir()
            if p.is_file() and p != output
        )

    def test_success_writes_the_complete_file_without_leftovers(self, tmp_path, audio_file):
        """Cas A — transcription complète : fichier final créé, aucun résidu."""
        out_dir = tmp_path / "transcripts"
        out_dir.mkdir()
        output = out_dir / "out.txt"

        model = FakeWhisperModel(
            segments=[(0.0, 2.0, "une"), (2.0, 4.0, "deux")],
            language="fr",
        )

        transcribe_audio_to_txt(
            model=model,
            audio_path=audio_file,
            output_path=output,
            total_duration_seconds=60.0,
        )

        assert _lines(output) == [
            "[00:00 -> 00:02] une",
            "[00:02 -> 00:04] deux",
        ]
        assert self._leftovers(out_dir, output) == []

    def test_crash_before_the_first_line_leaves_nothing(self, tmp_path, audio_file):
        """Cas B — crash avant la première ligne : ni final, ni temporaire."""
        out_dir = tmp_path / "transcripts"
        out_dir.mkdir()
        output = out_dir / "out.txt"

        model = ExplodingIterationModel(segments_before_error=[])

        with pytest.raises(RuntimeError, match="mid-iteration"):
            transcribe_audio_to_txt(
                model=model,
                audio_path=audio_file,
                output_path=output,
                total_duration_seconds=60.0,
            )

        assert not output.exists()
        assert self._leftovers(out_dir, output) == []

    def test_crash_after_several_segments_leaves_nothing(self, tmp_path, audio_file):
        """Cas C — crash après plusieurs segments : aucun transcript partiel."""
        out_dir = tmp_path / "transcripts"
        out_dir.mkdir()
        output = out_dir / "out.txt"

        model = ExplodingIterationModel(
            segments_before_error=[
                (0.0, 2.0, "une"),
                (2.0, 4.0, "deux"),
                (4.0, 6.0, "trois"),
            ]
        )

        with pytest.raises(RuntimeError, match="mid-iteration"):
            transcribe_audio_to_txt(
                model=model,
                audio_path=audio_file,
                output_path=output,
                total_duration_seconds=60.0,
            )

        assert not output.exists()
        assert self._leftovers(out_dir, output) == []

    def test_previous_transcript_survives_a_failed_retry(self, tmp_path, audio_file):
        """Cas D — un transcript final valide n'est pas détruit par un échec."""
        out_dir = tmp_path / "transcripts"
        out_dir.mkdir()
        output = out_dir / "out.txt"
        output.write_text("[00:00 -> 00:09] ancien transcript complet\n", encoding="utf-8")

        model = ExplodingIterationModel(
            segments_before_error=[(0.0, 2.0, "nouvelle tentative")]
        )

        with pytest.raises(RuntimeError, match="mid-iteration"):
            transcribe_audio_to_txt(
                model=model,
                audio_path=audio_file,
                output_path=output,
                total_duration_seconds=60.0,
            )

        assert _lines(output) == ["[00:00 -> 00:09] ancien transcript complet"]
        assert self._leftovers(out_dir, output) == []

    def test_previous_transcript_survives_a_transcribe_call_failure(self, tmp_path, audio_file):
        """Échec dès l'appel à transcribe() : le fichier final reste intact."""
        out_dir = tmp_path / "transcripts"
        out_dir.mkdir()
        output = out_dir / "out.txt"
        output.write_text("ancien\n", encoding="utf-8")

        model = FakeWhisperModel(fail_on={audio_file.name})

        with pytest.raises(RuntimeError, match="fake whisper failure"):
            transcribe_audio_to_txt(
                model=model,
                audio_path=audio_file,
                output_path=output,
                total_duration_seconds=60.0,
            )

        assert _lines(output) == ["ancien"]
        assert self._leftovers(out_dir, output) == []

    def test_keyboard_interrupt_also_cleans_up(self, tmp_path, audio_file):
        """Un arrêt brutal ne doit pas non plus laisser de fichier temporaire."""
        out_dir = tmp_path / "transcripts"
        out_dir.mkdir()
        output = out_dir / "out.txt"

        class _InterruptedModel(ExplodingIterationModel):
            def transcribe(self, audio_path, **kwargs):
                self.calls.append((audio_path, kwargs))

                def _generator():
                    yield FakeWhisperSegment(0.0, 2.0, "avant l'arrêt")
                    raise KeyboardInterrupt("process interrupted")

                return _generator(), FakeWhisperInfo(self.language)

        with pytest.raises(KeyboardInterrupt):
            transcribe_audio_to_txt(
                model=_InterruptedModel(),
                audio_path=audio_file,
                output_path=output,
                total_duration_seconds=60.0,
            )

        assert not output.exists()
        assert self._leftovers(out_dir, output) == []

    def test_capture_is_written_before_the_transcript(self, tmp_path, audio_file):
        """
        Phase 1 — invariant de la couche V2 : un transcript publié possède
        toujours sa capture structurée.
        """
        output = tmp_path / "out.txt"
        capture = tmp_path / "capture" / "lesson.json"

        seen: list[tuple[bool, bool]] = []

        class _ObservingModel(FakeWhisperModel):
            def transcribe(self, audio_path, **kwargs):
                segments, info = super().transcribe(audio_path, **kwargs)

                def _observed():
                    for segment in segments:
                        seen.append((capture.exists(), output.exists()))
                        yield segment

                return _observed(), info

        transcribe_audio_to_txt(
            model=_ObservingModel(segments=[(0.0, 2.0, "une"), (2.0, 4.0, "deux")]),
            audio_path=audio_file,
            output_path=output,
            total_duration_seconds=60.0,
            capture_path=capture,
        )

        assert seen == [(False, False), (False, False)]
        assert capture.exists() and output.exists()

    def test_a_failed_transcription_publishes_neither_artifact(self, tmp_path, audio_file):
        output = tmp_path / "out.txt"
        capture = tmp_path / "capture" / "lesson.json"

        model = ExplodingIterationModel(segments_before_error=[(0.0, 2.0, "avant")])

        with pytest.raises(RuntimeError, match="mid-iteration"):
            transcribe_audio_to_txt(
                model=model,
                audio_path=audio_file,
                output_path=output,
                total_duration_seconds=60.0,
                capture_path=capture,
            )

        assert not output.exists()
        assert not capture.exists()

    def test_final_file_is_only_published_after_full_success(self, tmp_path, audio_file):
        """Le fichier final n'apparaît pas pendant l'itération des segments."""
        out_dir = tmp_path / "transcripts"
        out_dir.mkdir()
        output = out_dir / "out.txt"

        seen_during_iteration = []

        class _ObservingModel(FakeWhisperModel):
            def transcribe(self, audio_path, **kwargs):
                segments, info = super().transcribe(audio_path, **kwargs)

                def _observed():
                    for segment in segments:
                        seen_during_iteration.append(output.exists())
                        yield segment

                return _observed(), info

        transcribe_audio_to_txt(
            model=_ObservingModel(segments=[(0.0, 2.0, "une"), (2.0, 4.0, "deux")]),
            audio_path=audio_file,
            output_path=output,
            total_duration_seconds=60.0,
        )

        assert seen_during_iteration == [False, False]
        assert output.exists()
