"""
Phase 0A — Filet de sécurité autour de la transcription segmentée (algorithmique).

Fige le comportement V1 de app.segmented_transcription_service pour :

- should_segment_audio()          → décision court / long ;
- _get_segment_boundaries()       → découpage + overlap ;
- _build_segment_list()           → descripteurs de segments ;
- _transcribe_one_segment()       → overlap entrant + timestamps globaux ;
- _merge_segment_transcripts()    → fusion, ordre, chronologie.

Aucun modèle Whisper réel, aucun appel ffmpeg/ffprobe.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import app.segmented_transcription_service as sts
from app.config import (
    AUDIO_SEGMENT_MINUTES,
    AUDIO_SEGMENT_OVERLAP_SECONDS,
    LONG_AUDIO_THRESHOLD_MINUTES,
)
from app.transcript_capture import read_part_capture

from app.tests.whisper_fakes import FakeWhisperModel

SEGMENT_SECONDS = AUDIO_SEGMENT_MINUTES * 60
OVERLAP = AUDIO_SEGMENT_OVERLAP_SECONDS
THRESHOLD_SECONDS = LONG_AUDIO_THRESHOLD_MINUTES * 60


@pytest.fixture(autouse=True)
def _quiet_progress(monkeypatch):
    monkeypatch.setattr(sts, "print_progress", lambda **kwargs: None)


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _segment(tmp_path, part_id, start, end, effective_start_local):
    """Descripteur de segment minimal, tel que produit par _build_segment_list."""
    return {
        "id": part_id,
        "audio_path": str(tmp_path / f"{part_id}.mp3"),
        "transcript_path": str(tmp_path / f"{part_id}.txt"),
        "start_seconds": start,
        "end_seconds": end,
        "effective_start_local": effective_start_local,
        "status": "pending",
        "updated_at": None,
        "error": None,
    }


# ---------------------------------------------------------------------------
# 8 — Décision de segmentation
# ---------------------------------------------------------------------------

class TestShouldSegmentAudio:

    @pytest.fixture
    def with_duration(self, monkeypatch):
        def _set(duration_seconds):
            monkeypatch.setattr(
                sts, "get_audio_duration_seconds", lambda path: duration_seconds
            )

        monkeypatch.setattr(sts, "LONG_AUDIO_SEGMENTATION_ENABLED", True)
        return _set

    def test_duration_below_threshold_is_not_segmented(self, tmp_path, with_duration):
        with_duration(THRESHOLD_SECONDS - 1)
        assert sts.should_segment_audio(tmp_path / "a.mp3") is False

    def test_duration_exactly_at_threshold_is_not_segmented(self, tmp_path, with_duration):
        """V1 utilise une comparaison stricte : durée == seuil → pas de segmentation."""
        with_duration(THRESHOLD_SECONDS)
        assert sts.should_segment_audio(tmp_path / "a.mp3") is False

    def test_duration_above_threshold_is_segmented(self, tmp_path, with_duration):
        with_duration(THRESHOLD_SECONDS + 1)
        assert sts.should_segment_audio(tmp_path / "a.mp3") is True

    def test_segmentation_disabled_in_config_wins(self, tmp_path, monkeypatch, with_duration):
        with_duration(THRESHOLD_SECONDS * 10)
        monkeypatch.setattr(sts, "LONG_AUDIO_SEGMENTATION_ENABLED", False)

        assert sts.should_segment_audio(tmp_path / "a.mp3") is False

    def test_duration_probe_failure_falls_back_to_no_segmentation(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sts, "LONG_AUDIO_SEGMENTATION_ENABLED", True)

        def _boom(path):
            raise OSError("ffprobe indisponible")

        monkeypatch.setattr(sts, "get_audio_duration_seconds", _boom)

        assert sts.should_segment_audio(tmp_path / "a.mp3") is False


# ---------------------------------------------------------------------------
# 9 — Construction des frontières de segments
# ---------------------------------------------------------------------------

class TestSegmentBoundaries:

    def test_known_layout_for_non_multiple_duration(self):
        """1900 s avec segments de 900 s et overlap 10 s."""
        assert sts._get_segment_boundaries(1900.0) == [
            (0.0, 910.0),
            (900.0, 1810.0),
            (1800.0, 1900.0),
        ]

    def test_first_segment_starts_at_zero(self):
        boundaries = sts._get_segment_boundaries(1900.0)
        assert boundaries[0][0] == 0.0

    def test_first_segment_carries_trailing_overlap(self):
        boundaries = sts._get_segment_boundaries(1900.0)
        assert boundaries[0][1] == SEGMENT_SECONDS + OVERLAP

    def test_intermediate_segment_advances_by_segment_duration(self):
        boundaries = sts._get_segment_boundaries(1900.0)
        assert boundaries[1][0] == SEGMENT_SECONDS
        assert boundaries[1][1] == 2 * SEGMENT_SECONDS + OVERLAP

    def test_last_segment_is_clipped_to_total_duration(self):
        boundaries = sts._get_segment_boundaries(1900.0)
        assert boundaries[-1][1] == 1900.0

    def test_consecutive_segments_overlap_by_configured_amount(self):
        boundaries = sts._get_segment_boundaries(5000.0)
        for (start, end), (next_start, _) in zip(boundaries, boundaries[1:]):
            assert next_start == end - OVERLAP, (
                "Chaque segment suivant doit démarrer OVERLAP secondes avant "
                "la fin du précédent."
            )
            assert next_start > start

    @pytest.mark.parametrize("total", [1.0, 100.0, 899.0, 900.0, 901.0, 1800.0, 1900.0, 5000.0])
    def test_invariants_hold_for_any_duration(self, total):
        boundaries = sts._get_segment_boundaries(total)

        assert boundaries, "Au moins un segment doit être produit."

        starts = [s for s, _ in boundaries]
        assert starts == sorted(starts), "Les segments doivent être ordonnés."

        for start, end in boundaries:
            assert start >= 0.0, "Aucun début négatif."
            assert end > start, "Aucune durée négative ou nulle."
            assert end <= total, "Aucun segment ne dépasse la durée totale."

        assert boundaries[0][0] == 0.0
        assert boundaries[-1][1] == total, "La couverture doit aller jusqu'à la fin."

    def test_duration_shorter_than_one_segment_gives_single_segment(self):
        assert sts._get_segment_boundaries(100.0) == [(0.0, 100.0)]

    def test_duration_exactly_one_segment_gives_single_segment(self):
        assert sts._get_segment_boundaries(float(SEGMENT_SECONDS)) == [
            (0.0, float(SEGMENT_SECONDS))
        ]

    def test_one_second_past_a_segment_creates_no_degenerate_tail(self):
        """
        Correction Phase 1 (KNOWN V1 BUG #1 du rapport Phase 0A) : une durée juste
        au-dessus d'un multiple de la durée de segment ne produit plus de segment
        résiduel entièrement absorbé par l'overlap entrant.

        Le segment précédent atteignant déjà la fin du fichier, la couverture
        audio reste complète et l'appel Whisper inutile disparaît.
        """
        boundaries = sts._get_segment_boundaries(float(SEGMENT_SECONDS) + 1.0)

        assert boundaries == [(0.0, 901.0)]
        assert boundaries[-1][1] == 901.0, "La fin du fichier reste couverte."

    @pytest.mark.parametrize(
        "total",
        [
            float(SEGMENT_SECONDS) + 0.5,
            float(SEGMENT_SECONDS) + 1.0,
            float(SEGMENT_SECONDS) + OVERLAP,
            2 * float(SEGMENT_SECONDS) + 1.0,
        ],
    )
    def test_no_segment_is_fully_absorbed_by_its_incoming_overlap(self, total):
        """Aucun segment technique ne doit être entièrement couvert par le précédent."""
        boundaries = sts._get_segment_boundaries(total)

        for (_, previous_end), (_, end) in zip(boundaries, boundaries[1:]):
            assert end > previous_end, (
                "Un segment technique dont la fin ne dépasse pas celle du précédent "
                "n'apporte aucun contenu nouveau."
            )

        assert boundaries[-1][1] == total, "La couverture doit aller jusqu'à la fin."


# ---------------------------------------------------------------------------
# 9 — Descripteurs de segments
# ---------------------------------------------------------------------------

class TestBuildSegmentList:

    def test_segment_descriptors_match_boundaries(self, tmp_path, isolated_sortie):
        audio = tmp_path / "Retreat 01.mp3"
        segments = sts._build_segment_list("demo", audio, 1900.0)

        assert [s["id"] for s in segments] == ["part_001", "part_002", "part_003"]
        assert [(s["start_seconds"], s["end_seconds"]) for s in segments] == [
            (0.0, 910.0),
            (900.0, 1810.0),
            (1800.0, 1900.0),
        ]

    def test_first_segment_has_no_incoming_overlap(self, tmp_path, isolated_sortie):
        segments = sts._build_segment_list("demo", tmp_path / "a.mp3", 1900.0)

        assert segments[0]["effective_start_local"] == 0.0
        assert all(s["effective_start_local"] == float(OVERLAP) for s in segments[1:])

    def test_segments_start_pending(self, tmp_path, isolated_sortie):
        segments = sts._build_segment_list("demo", tmp_path / "a.mp3", 1900.0)

        for segment in segments:
            assert segment["status"] == "pending"
            assert segment["updated_at"] is None
            assert segment["error"] is None

    def test_paths_are_stable_and_scoped_to_project_and_stem(self, tmp_path, isolated_sortie):
        audio = tmp_path / "a.mp3"
        segments = sts._build_segment_list("demo", audio, 1900.0)

        audio_dir = isolated_sortie / "demo" / "audio_segments" / "a"
        transcript_dir = isolated_sortie / "demo" / "segment_transcripts" / "a"

        assert audio_dir.is_dir()
        assert transcript_dir.is_dir()
        assert Path(segments[0]["audio_path"]) == audio_dir / "part_001.mp3"
        assert Path(segments[0]["transcript_path"]) == transcript_dir / "part_001.txt"

    def test_rebuilding_gives_identical_descriptors(self, tmp_path, isolated_sortie):
        audio = tmp_path / "a.mp3"
        first = sts._build_segment_list("demo", audio, 1900.0)
        second = sts._build_segment_list("demo", audio, 1900.0)

        assert first == second, "Le nommage des segments doit être stable (reprise)."


# ---------------------------------------------------------------------------
# 44 — Segment résiduel et couverture audio (Phase 1)
# ---------------------------------------------------------------------------

class TestResidualSegmentCoverage:
    """
    Le découpage doit couvrir intégralement l'audio sans produire de segment
    technique dont le contenu est déjà entièrement couvert par le précédent.
    """

    DURATIONS = [899.0, 900.0, 901.0, 905.0, 910.0, 911.0, 1800.0, 1801.0, 1810.0, 1811.0]

    @pytest.mark.parametrize("total", DURATIONS)
    def test_coverage_is_contiguous_and_complete(self, total):
        boundaries = sts._get_segment_boundaries(total)

        assert boundaries[0][0] == 0.0, "La couverture commence à zéro."
        assert boundaries[-1][1] == total, "La couverture va jusqu'à la fin du fichier."

        for (_, end), (next_start, _) in zip(boundaries, boundaries[1:]):
            assert next_start <= end, "Aucun trou entre deux segments techniques."

    @pytest.mark.parametrize("total", DURATIONS)
    def test_no_technical_segment_is_useless(self, total):
        boundaries = sts._get_segment_boundaries(total)

        for (_, previous_end), (_, end) in zip(boundaries, boundaries[1:]):
            assert end > previous_end

    @pytest.mark.parametrize("total", DURATIONS)
    def test_every_segment_has_a_positive_duration(self, total):
        for start, end in sts._get_segment_boundaries(total):
            assert end > start

    def test_end_of_file_content_is_not_lost(self, tmp_path, isolated_sortie):
        """
        Avant la Phase 1, une durée de 901 s produisait un segment résiduel
        900-901 s. Le contenu de fin de fichier doit rester transcrit — désormais
        par le segment principal, qui couvre déjà jusqu'à 901 s.
        """
        segments = sts._build_segment_list("demo", tmp_path / "long.mp3", 901.0)

        assert len(segments) == 1
        assert segments[0]["end_seconds"] == 901.0

        sts._transcribe_one_segment(
            model=FakeWhisperModel(segments=[(0.0, 5.0, "début"), (895.0, 900.5, "fin")]),
            segment=segments[0],
            total_duration_seconds=901.0,
            segment_index=1,
            total_segments=1,
            project_name="demo",
        )

        assert _lines(Path(segments[0]["transcript_path"])) == [
            "[00:00 -> 00:05] début",
            "[14:55 -> 15:00] fin",
        ]


# ---------------------------------------------------------------------------
# 26 — Capture structurée d'un segment technique (Phase 1)
# ---------------------------------------------------------------------------

class TestPartCapture:

    def _run(self, segment, model, total=1900.0):
        sts._transcribe_one_segment(
            model=model,
            segment=segment,
            total_duration_seconds=total,
            segment_index=1,
            total_segments=3,
            project_name="demo",
        )
        return read_part_capture(Path(segment["transcript_path"]))

    def test_capture_is_written_next_to_the_segment_transcript(self, tmp_path):
        segment = _segment(tmp_path, "part_001", 0.0, 910.0, 0.0)

        self._run(segment, FakeWhisperModel(segments=[(0.0, 5.0, "x")]))

        assert (tmp_path / "part_001.json").exists()

    def test_capture_keeps_precise_local_timestamps(self, tmp_path):
        segment = _segment(tmp_path, "part_002", 900.0, 1810.0, float(OVERLAP))

        capture = self._run(
            segment, FakeWhisperModel(segments=[(12.37, 18.94, "précis")])
        )

        assert capture.segments[0].start == 12.37
        assert capture.segments[0].end == 18.94

    def test_capture_records_the_technical_offsets(self, tmp_path):
        segment = _segment(tmp_path, "part_002", 900.0, 1810.0, float(OVERLAP))

        capture = self._run(segment, FakeWhisperModel(segments=[(0.0, 1.0, "x")]))

        assert capture.id == "part_002"
        assert capture.start_seconds == 900.0
        assert capture.end_seconds == 1810.0
        assert capture.effective_start_local == float(OVERLAP)

    def test_capture_keeps_raw_segments_including_the_incoming_overlap(self, tmp_path):
        """
        Le filtrage d'overlap n'appartient pas à la capture : la règle d'ownership
        est appliquée une seule fois, dans app.transcript_builder, qui dispose du
        contexte des segments techniques voisins.
        """
        segment = _segment(tmp_path, "part_002", 900.0, 1810.0, float(OVERLAP))
        model = FakeWhisperModel(
            segments=[(0.0, 8.0, "dans overlap"), (20.0, 30.0, "après")]
        )

        capture = self._run(segment, model)

        assert [s.text for s in capture.segments] == ["dans overlap", "après"]
        assert _lines(Path(segment["transcript_path"])) == ["[15:20 -> 15:30] après"], (
            "Le transcript texte V1 filtre toujours l'overlap entrant."
        )

    def test_capture_is_written_before_the_segment_transcript(self, tmp_path):
        """
        Invariant : un transcript de segment présent implique toujours une capture
        exploitable, y compris après reprise.
        """
        segment = _segment(tmp_path, "part_001", 0.0, 910.0, 0.0)
        transcript = Path(segment["transcript_path"])
        capture = tmp_path / "part_001.json"

        seen: list[tuple[bool, bool]] = []

        class _ObservingModel(FakeWhisperModel):
            def transcribe(self, audio_path, **kwargs):
                iterator, info = super().transcribe(audio_path, **kwargs)

                def _observed():
                    for item in iterator:
                        seen.append((capture.exists(), transcript.exists()))
                        yield item

                return _observed(), info

        self._run(segment, _ObservingModel(segments=[(0.0, 1.0, "a"), (1.0, 2.0, "b")]))

        assert seen == [(False, False), (False, False)]
        assert capture.exists() and transcript.exists()

    def test_capture_records_the_detected_language(self, tmp_path):
        segment = _segment(tmp_path, "part_001", 0.0, 910.0, 0.0)

        capture = self._run(
            segment, FakeWhisperModel(segments=[(0.0, 1.0, "x")], language="es")
        )

        assert capture.detected_language == "es"

    def test_a_failed_segment_leaves_no_partial_file(self, tmp_path):
        from app.tests.whisper_fakes import ExplodingIterationModel

        segment = _segment(tmp_path, "part_001", 0.0, 910.0, 0.0)

        with pytest.raises(RuntimeError, match="mid-iteration"):
            sts._transcribe_one_segment(
                model=ExplodingIterationModel(segments_before_error=[(0.0, 2.0, "x")]),
                segment=segment,
                total_duration_seconds=910.0,
                segment_index=1,
                total_segments=1,
                project_name="demo",
            )

        assert not Path(segment["transcript_path"]).exists()
        assert not (tmp_path / "part_001.json").exists()
        assert sorted(p.name for p in tmp_path.iterdir() if p.is_file()) == []


# ---------------------------------------------------------------------------
# 10 — Overlap entrant
# ---------------------------------------------------------------------------

class TestIncomingOverlap:

    def _run(self, segment, model, total=1900.0):
        sts._transcribe_one_segment(
            model=model,
            segment=segment,
            total_duration_seconds=total,
            segment_index=1,
            total_segments=3,
            project_name="demo",
        )
        return Path(segment["transcript_path"])

    def test_first_segment_keeps_everything(self, tmp_path):
        segment = _segment(tmp_path, "part_001", 0.0, 910.0, 0.0)
        model = FakeWhisperModel(
            segments=[(0.0, 5.0, "phrase A"), (900.0, 908.0, "phrase B")]
        )

        transcript = self._run(segment, model)

        assert _lines(transcript) == [
            "[00:00 -> 00:05] phrase A",
            "[15:00 -> 15:08] phrase B",
        ]

    def test_content_entirely_inside_incoming_overlap_is_dropped(self, tmp_path):
        segment = _segment(tmp_path, "part_002", 900.0, 1810.0, float(OVERLAP))
        model = FakeWhisperModel(
            segments=[(0.0, 8.0, "phrase B"), (20.0, 30.0, "phrase C")]
        )

        transcript = self._run(segment, model)

        assert _lines(transcript) == ["[15:20 -> 15:30] phrase C"]

    def test_content_ending_exactly_at_overlap_boundary_is_dropped(self, tmp_path):
        segment = _segment(tmp_path, "part_002", 900.0, 1810.0, float(OVERLAP))
        model = FakeWhisperModel(segments=[(2.0, float(OVERLAP), "pile sur la frontière")])

        transcript = self._run(segment, model)

        assert _lines(transcript) == [], "La comparaison V1 est end <= effective_start_local."

    def test_content_ending_just_after_overlap_boundary_is_kept(self, tmp_path):
        segment = _segment(tmp_path, "part_002", 900.0, 1810.0, float(OVERLAP))
        model = FakeWhisperModel(segments=[(2.0, float(OVERLAP) + 0.5, "juste après")])

        transcript = self._run(segment, model)

        assert _lines(transcript) == ["[15:02 -> 15:10] juste après"]

    def test_segment_straddling_the_overlap_boundary_is_kept(self, tmp_path):
        """
        Comportement V1 ACTUEL : seule une phrase se terminant AVANT la fin de
        l'overlap est écartée. Une phrase à cheval sur la frontière est conservée
        et peut donc apparaître aussi dans le segment précédent.

        Voir KNOWN V1 BUG #2 du rapport Phase 0A.
        """
        segment = _segment(tmp_path, "part_002", 900.0, 1810.0, float(OVERLAP))
        model = FakeWhisperModel(segments=[(5.0, 15.0, "à cheval sur la frontière")])

        transcript = self._run(segment, model)

        assert _lines(transcript) == ["[15:05 -> 15:15] à cheval sur la frontière"]

    def test_no_duplication_across_two_consecutive_segments(self, tmp_path):
        """
        Régression protégée : une future modification de l'overlap ne doit pas
        produire « phrase A / phrase B / phrase B / phrase C » dans le transcript
        fusionné.
        """
        first = _segment(tmp_path, "part_001", 0.0, 910.0, 0.0)
        second = _segment(tmp_path, "part_002", 900.0, 1810.0, float(OVERLAP))

        # « phrase B » est prononcée à 900-908 s (global) : elle est vue par
        # part_001 en fin de segment ET par part_002 dans son overlap entrant.
        self._run(first, FakeWhisperModel(
            segments=[(0.0, 5.0, "phrase A"), (900.0, 908.0, "phrase B")]
        ))
        self._run(second, FakeWhisperModel(
            segments=[(0.0, 8.0, "phrase B"), (20.0, 30.0, "phrase C")]
        ))

        merged = tmp_path / "final.txt"
        sts._merge_segment_transcripts([first, second], merged)

        texts = [line.split("] ", 1)[1] for line in _lines(merged)]
        assert texts == ["phrase A", "phrase B", "phrase C"]
        assert texts.count("phrase B") == 1


# ---------------------------------------------------------------------------
# 11 — Timestamps globaux
# ---------------------------------------------------------------------------

class TestGlobalTimestamps:

    def test_local_timestamps_are_shifted_by_segment_start(self, tmp_path):
        segment = _segment(tmp_path, "part_002", 900.0, 1800.0, float(OVERLAP))
        model = FakeWhisperModel(segments=[(12.0, 18.0, "contenu")])

        sts._transcribe_one_segment(
            model=model,
            segment=segment,
            total_duration_seconds=5400.0,
            segment_index=2,
            total_segments=6,
            project_name="demo",
        )

        assert _lines(Path(segment["transcript_path"])) == ["[15:12 -> 15:18] contenu"]

    def test_timestamps_cross_the_one_hour_format_boundary(self, tmp_path):
        segment = _segment(tmp_path, "part_005", 3600.0, 4510.0, float(OVERLAP))
        model = FakeWhisperModel(segments=[(12.0, 18.0, "après une heure")])

        sts._transcribe_one_segment(
            model=model,
            segment=segment,
            total_duration_seconds=5400.0,
            segment_index=5,
            total_segments=6,
            project_name="demo",
        )

        assert _lines(Path(segment["transcript_path"])) == [
            "[01:00:12 -> 01:00:18] après une heure"
        ]

    def test_chronology_is_monotonic_across_several_segments(self, tmp_path):
        segments = [
            _segment(tmp_path, "part_001", 0.0, 910.0, 0.0),
            _segment(tmp_path, "part_002", 900.0, 1810.0, float(OVERLAP)),
            _segment(tmp_path, "part_003", 1800.0, 2710.0, float(OVERLAP)),
        ]
        payloads = [
            [(10.0, 20.0, "s1a"), (800.0, 810.0, "s1b")],
            [(30.0, 40.0, "s2a"), (700.0, 710.0, "s2b")],
            [(50.0, 60.0, "s3a")],
        ]

        for index, (segment, payload) in enumerate(zip(segments, payloads), start=1):
            sts._transcribe_one_segment(
                model=FakeWhisperModel(segments=payload),
                segment=segment,
                total_duration_seconds=2710.0,
                segment_index=index,
                total_segments=3,
                project_name="demo",
            )

        merged = tmp_path / "final.txt"
        sts._merge_segment_transcripts(segments, merged)

        assert _lines(merged) == [
            "[00:10 -> 00:20] s1a",
            "[13:20 -> 13:30] s1b",
            "[15:30 -> 15:40] s2a",
            "[26:40 -> 26:50] s2b",
            "[30:50 -> 31:00] s3a",
        ]

    def test_transcript_directory_is_created_if_missing(self, tmp_path):
        segment = _segment(tmp_path, "part_001", 0.0, 910.0, 0.0)
        segment["transcript_path"] = str(tmp_path / "nested" / "deep" / "part_001.txt")

        sts._transcribe_one_segment(
            model=FakeWhisperModel(segments=[(0.0, 1.0, "x")]),
            segment=segment,
            total_duration_seconds=910.0,
            segment_index=1,
            total_segments=1,
            project_name="demo",
        )

        assert Path(segment["transcript_path"]).exists()

    def test_language_outside_fr_en_is_preserved(self, tmp_path):
        """
        Contrat V2 (Phase 1) — même politique de langue que la transcription
        directe : la langue détectée est conservée, aucune seconde passe forcée
        en anglais. Remplace volontairement l'assertion figée en Phase 0A.
        """
        segment = _segment(tmp_path, "part_001", 0.0, 910.0, 0.0)
        model = FakeWhisperModel(segments=[(0.0, 1.0, "x")], language="de")

        sts._transcribe_one_segment(
            model=model,
            segment=segment,
            total_duration_seconds=910.0,
            segment_index=1,
            total_segments=1,
            project_name="demo",
        )

        assert model.call_count == 1
        assert model.calls[0][1] == {}
        assert read_part_capture(Path(segment["transcript_path"])).detected_language == "de"


# ---------------------------------------------------------------------------
# 16 — Fusion des transcripts de segments
# ---------------------------------------------------------------------------

class TestMergeSegmentTranscripts:

    def _prepare(self, tmp_path, contents: dict[str, str | None]):
        segments = []
        for index, (part_id, content) in enumerate(contents.items(), start=1):
            segment = _segment(tmp_path, part_id, (index - 1) * 900.0, index * 900.0, 0.0)
            if content is not None:
                Path(segment["transcript_path"]).write_text(content, encoding="utf-8")
            segments.append(segment)
        return segments

    def test_segments_are_concatenated_in_list_order(self, tmp_path, silence_logs):
        segments = self._prepare(tmp_path, {
            "part_001": "[00:00 -> 00:05] un\n",
            "part_002": "[15:00 -> 15:05] deux\n",
            "part_003": "[30:00 -> 30:05] trois\n",
        })
        output = tmp_path / "final.txt"

        sts._merge_segment_transcripts(segments, output)

        assert _lines(output) == [
            "[00:00 -> 00:05] un",
            "[15:00 -> 15:05] deux",
            "[30:00 -> 30:05] trois",
        ]

    def test_no_content_is_lost_and_nothing_is_duplicated(self, tmp_path, silence_logs):
        segments = self._prepare(tmp_path, {
            "part_001": "a\nb\n",
            "part_002": "c\nd\n",
        })
        output = tmp_path / "final.txt"

        sts._merge_segment_transcripts(segments, output)

        assert _lines(output) == ["a", "b", "c", "d"]

    def test_missing_trailing_newline_is_added_between_segments(self, tmp_path, silence_logs):
        segments = self._prepare(tmp_path, {
            "part_001": "sans retour final",
            "part_002": "suite\n",
        })
        output = tmp_path / "final.txt"

        sts._merge_segment_transcripts(segments, output)

        assert _lines(output) == ["sans retour final", "suite"]

    def test_missing_segment_transcript_aborts_the_merge(self, tmp_path, silence_logs):
        """
        Phase 0B (correction 0B.1) : un transcript de segment absent interdit la
        fusion. Ce test échoue si le système recommence un jour à ignorer
        silencieusement un segment manquant.
        """
        segments = self._prepare(tmp_path, {
            "part_001": "[00:00 -> 00:05] un\n",
            "part_002": None,
            "part_003": "[30:00 -> 30:05] trois\n",
        })
        output = tmp_path / "final.txt"

        with pytest.raises(RuntimeError, match="part_002"):
            sts._merge_segment_transcripts(segments, output)

        assert not output.exists(), (
            "Aucun transcript final ne doit être produit quand un segment manque."
        )

    def test_all_missing_segment_ids_are_reported(self, tmp_path, silence_logs):
        segments = self._prepare(tmp_path, {
            "part_001": None,
            "part_002": "[15:00 -> 15:05] deux\n",
            "part_003": None,
        })
        output = tmp_path / "final.txt"

        with pytest.raises(RuntimeError) as excinfo:
            sts._merge_segment_transcripts(segments, output)

        message = str(excinfo.value)
        assert "part_001" in message
        assert "part_003" in message
        assert "part_002" not in message

    def test_existing_final_transcript_is_preserved_when_a_segment_is_missing(
        self, tmp_path, silence_logs
    ):
        """
        La vérification a lieu AVANT toute écriture : un transcript final valide
        issu d'un run précédent ne doit pas être tronqué par une fusion refusée.
        """
        segments = self._prepare(tmp_path, {
            "part_001": "[00:00 -> 00:05] un\n",
            "part_002": None,
        })
        output = tmp_path / "final.txt"
        output.write_text("ANCIEN TRANSCRIPT COMPLET\n", encoding="utf-8")

        with pytest.raises(RuntimeError):
            sts._merge_segment_transcripts(segments, output)

        assert _lines(output) == ["ANCIEN TRANSCRIPT COMPLET"]

    def test_segment_transcript_files_are_not_touched_by_a_refused_merge(
        self, tmp_path, silence_logs
    ):
        """Les segments déjà correctement transcrits restent disponibles."""
        segments = self._prepare(tmp_path, {
            "part_001": "[00:00 -> 00:05] un\n",
            "part_002": None,
        })
        output = tmp_path / "final.txt"

        with pytest.raises(RuntimeError):
            sts._merge_segment_transcripts(segments, output)

        kept = Path(segments[0]["transcript_path"])
        assert kept.exists()
        assert kept.read_text(encoding="utf-8") == "[00:00 -> 00:05] un\n"

    def test_output_is_created_and_parent_directory_too(self, tmp_path, silence_logs):
        segments = self._prepare(tmp_path, {"part_001": "contenu\n"})
        output = tmp_path / "nested" / "transcripts" / "final.txt"

        sts._merge_segment_transcripts(segments, output)

        assert output.exists()

    def test_existing_output_is_overwritten(self, tmp_path, silence_logs):
        segments = self._prepare(tmp_path, {"part_001": "neuf\n"})
        output = tmp_path / "final.txt"
        output.write_text("ANCIEN\n", encoding="utf-8")

        sts._merge_segment_transcripts(segments, output)

        assert _lines(output) == ["neuf"]
