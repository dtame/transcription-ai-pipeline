"""
Phase 0A — Micro-test d'intégration ffmpeg (SÉPARÉ des tests unitaires).

Vérifie que le découpage audio réel fonctionne toujours :
    audio_utils.get_audio_duration_seconds()
    segmented_transcription_service._create_audio_segment()

Contraintes respectées :
- aucun modèle Whisper, aucune transcription ;
- aucune ressource externe : le fichier audio (6 s de silence) est généré
  localement par ffmpeg puis détruit avec tmp_path ;
- ignoré automatiquement si ffmpeg/ffprobe sont absents du PATH.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe absents du PATH",
)

SOURCE_SECONDS = 6.0
TOLERANCE_SECONDS = 0.3


@pytest.fixture
def tiny_wav(tmp_path):
    """6 secondes de silence en WAV mono 8 kHz (quelques dizaines de kilo-octets)."""
    path = tmp_path / "silence.wav"
    subprocess.run(
        [
            shutil.which("ffmpeg"),
            "-y",
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=mono:sample_rate=8000",
            "-t", str(SOURCE_SECONDS),
            str(path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return path


def test_ffprobe_reports_the_real_duration(tiny_wav):
    from app.audio_utils import get_audio_duration_seconds

    assert get_audio_duration_seconds(tiny_wav) == pytest.approx(
        SOURCE_SECONDS, abs=TOLERANCE_SECONDS
    )


def test_create_audio_segment_extracts_the_requested_window(tmp_path, tiny_wav):
    from app.audio_utils import get_audio_duration_seconds
    from app.segmented_transcription_service import _create_audio_segment

    output = tmp_path / "part_001.mp3"
    _create_audio_segment(audio_path=tiny_wav, output_path=output, start=2.0, end=5.0)

    assert output.exists() and output.stat().st_size > 0
    assert get_audio_duration_seconds(output) == pytest.approx(3.0, abs=TOLERANCE_SECONDS)


def test_short_real_file_is_not_segmented(tiny_wav):
    from app.segmented_transcription_service import should_segment_audio

    assert should_segment_audio(tiny_wav) is False
