import subprocess
import shutil
import time
from pathlib import Path

from app.config import CHUNK_DURATION_MINUTES


def get_required_executable(name: str) -> str:
    path = shutil.which(name)

    if path is None:
        raise RuntimeError(
            f"{name} introuvable. Vérifie que FFmpeg est bien ajouté au PATH."
        )

    return path


FFMPEG_EXE = get_required_executable("ffmpeg")
FFPROBE_EXE = get_required_executable("ffprobe")


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"


def format_elapsed(seconds: float) -> str:
    return format_timestamp(seconds)


def get_audio_duration_seconds(file_path: Path) -> float:
    result = subprocess.run(
        [
            FFPROBE_EXE,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    return float(result.stdout.strip())


def print_progress(
    current_seconds: float,
    total_seconds: float,
    start_time: float,
    prefix: str = "Progression",
) -> None:
    percent = min(100, int((current_seconds / total_seconds) * 100))
    bar_length = 30
    filled_length = int(bar_length * percent / 100)
    bar = "#" * filled_length + "-" * (bar_length - filled_length)
    elapsed = format_elapsed(time.time() - start_time)

    print(
        f"\r{prefix} : [{bar}] {percent}% | Temps écoulé : {elapsed}",
        end="",
        flush=True,
    )


def split_audio(file_path: Path, work_dir: Path) -> list[Path]:
    chunk_pattern = work_dir / "chunk_%03d.wav"

    subprocess.run(
        [
            FFMPEG_EXE,
            "-i",
            str(file_path),
            "-f",
            "segment",
            "-segment_time",
            str(CHUNK_DURATION_MINUTES * 60),
            "-c:a",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(chunk_pattern),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return sorted(work_dir.glob("chunk_*.wav"))