from faster_whisper import WhisperModel
from pathlib import Path
from datetime import datetime
import subprocess
import shutil
import hashlib
import json
import re
import sys
import time
import ctypes
import platform
import shutil


BASE_DIR = Path(__file__).resolve().parent

DEPOT_DIR = BASE_DIR / "depot"
SORTIE_DIR = BASE_DIR / "sortie"
TEMP_DIR = BASE_DIR / "temp"
ARCHIVES_DIR = BASE_DIR / "archives"
LOGS_DIR = BASE_DIR / "logs"
REJETS_DIR = BASE_DIR / "rejets"

SUPPORTED_EXTENSIONS = {".ogg", ".mp3", ".wav", ".m4a"}

MODEL_NAME = "large-v3"
DEVICE = "cpu"

CHUNK_THRESHOLD_MINUTES = 60
CHUNK_DURATION_MINUTES = 10


def get_required_executable(name: str) -> str:
    path = shutil.which(name)

    if path is None:
        raise RuntimeError(
            f"{name} introuvable. Vérifie que FFmpeg est bien ajouté au PATH."
        )

    return path


FFMPEG_EXE = get_required_executable("ffmpeg")
FFPROBE_EXE = get_required_executable("ffprobe")


def prevent_sleep():
    if platform.system() == "Windows":
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )


def allow_sleep_again():
    if platform.system() == "Windows":
        ES_CONTINUOUS = 0x80000000
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)


def log_event(event: dict) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    log_path = LOGS_DIR / "transcription_log.jsonl"
    event["timestamp"] = datetime.now().isoformat(timespec="seconds")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def sanitize_name(name: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "audio"


def file_hash(file_path: Path) -> str:
    hasher = hashlib.md5()

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


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
            str(file_path)
        ],
        capture_output=True,
        text=True,
        check=True
    )

    return float(result.stdout.strip())


def unique_path(directory: Path, stem: str, suffix: str) -> Path:
    path = directory / f"{stem}{suffix}"
    counter = 2

    while path.exists():
        path = directory / f"{stem}_{counter}{suffix}"
        counter += 1

    return path


def print_progress(
    current_seconds: float,
    total_seconds: float,
    start_time: float,
    prefix: str = "Progression"
) -> None:
    percent = min(100, int((current_seconds / total_seconds) * 100))
    bar_length = 30
    filled_length = int(bar_length * percent / 100)
    bar = "#" * filled_length + "-" * (bar_length - filled_length)
    elapsed = format_elapsed(time.time() - start_time)

    print(
        f"\r{prefix} : [{bar}] {percent}% | Temps écoulé : {elapsed}",
        end="",
        flush=True
    )


def split_audio(file_path: Path, work_dir: Path) -> list[Path]:
    chunk_pattern = work_dir / "chunk_%03d.wav"

    subprocess.run(
        [
            FFPROBE_EXE,
            "-i", str(file_path),
            "-f", "segment",
            "-segment_time", str(CHUNK_DURATION_MINUTES * 60),
            "-c:a", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(chunk_pattern)
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    return sorted(work_dir.glob("chunk_*.wav"))


def transcribe_audio_to_txt(
    model: WhisperModel,
    audio_path: Path,
    output_path: Path,
    total_duration_seconds: float,
    timestamp_offset: float = 0,
    progress_prefix: str = "Progression"
) -> str:
    start_time = time.time()

    segments, info = model.transcribe(str(audio_path))

    detected_language = info.language
    ALLOWED_LANGUAGES = {"en", "fr"}
    if detected_language not in ALLOWED_LANGUAGES:
        print(
            f"Langue détectée inattendue : {detected_language}. "
            "Forçage vers anglais."
        )

        detected_language = "en"

        segments, info = model.transcribe(
            str(audio_path),
            language="en"
        )

    print(f"Detected language : {detected_language}")
    print("Transcription en cours...")

    with open(output_path, "w", encoding="utf-8") as f:
        for segment in segments:
            start = format_timestamp(segment.start + timestamp_offset)
            end = format_timestamp(segment.end + timestamp_offset)
            f.write(f"[{start} -> {end}] {segment.text.strip()}\n")

            current_position = segment.end + timestamp_offset
            print_progress(
                current_seconds=current_position,
                total_seconds=total_duration_seconds,
                start_time=start_time,
                prefix=progress_prefix
            )

    print_progress(
        current_seconds=total_duration_seconds,
        total_seconds=total_duration_seconds,
        start_time=start_time,
        prefix=progress_prefix
    )
    print()

    return detected_language


def transcribe_file(model: WhisperModel, original_file: Path) -> None:
    original_hash = file_hash(original_file)
    safe_stem = sanitize_name(original_file.stem)
    work_dir = TEMP_DIR / f"{safe_stem}_{original_hash[:8]}"
    work_dir.mkdir(parents=True, exist_ok=True)

    final_output = unique_path(SORTIE_DIR, safe_stem, ".txt")

    try:
        print("\n" + "=" * 70)
        print(f"Fichier : {original_file.name}")
        print(f"Taille : {round(original_file.stat().st_size / (1024*1024), 2)} MB")
        print(f"Début : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        if original_file.stat().st_size == 0:
            reject_path = unique_path(REJETS_DIR, original_file.stem, original_file.suffix)
            shutil.move(str(original_file), str(reject_path))

            log_event({
                "event": "rejected_empty_file",
                "file": original_file.name,
                "reason": "File size is 0 bytes",
                "moved_to": reject_path.name
            })

            print(f"Fichier ignoré : {original_file.name} est vide.")
            return

        duration = get_audio_duration_seconds(original_file)
        duration_minutes = duration / 60

        log_event({
            "event": "start_file",
            "file": original_file.name,
            "duration_minutes": round(duration_minutes, 2),
            "hash": original_hash
        })

        if duration_minutes <= CHUNK_THRESHOLD_MINUTES:
            temp_audio = work_dir / f"{safe_stem}{original_file.suffix.lower()}"
            shutil.copy2(original_file, temp_audio)

            partial_txt = work_dir / f"{safe_stem}_transcription.txt"

            if not partial_txt.exists():
                transcribe_audio_to_txt(
                    model=model,
                    audio_path=temp_audio,
                    output_path=partial_txt,
                    total_duration_seconds=duration
                )

                log_event({
                    "event": "completed_full_transcription",
                    "file": original_file.name
                })

            shutil.copy2(partial_txt, final_output)

        else:
            chunks_dir = work_dir / "chunks"
            chunks_dir.mkdir(exist_ok=True)

            chunk_files = sorted(chunks_dir.glob("chunk_*.wav"))

            if not chunk_files:
                print("Découpage du fichier en segments...")
                chunk_files = split_audio(original_file, chunks_dir)

            partial_outputs = []

            for index, chunk_file in enumerate(chunk_files):
                chunk_txt = work_dir / f"{safe_stem}_chunk_{index:03d}.txt"
                partial_outputs.append(chunk_txt)

                if chunk_txt.exists():
                    continue

                offset_seconds = index * CHUNK_DURATION_MINUTES * 60

                print(f"Traitement du segment {index + 1}/{len(chunk_files)}...")

                transcribe_audio_to_txt(
                    model=model,
                    audio_path=chunk_file,
                    output_path=chunk_txt,
                    total_duration_seconds=duration,
                    timestamp_offset=offset_seconds,
                    progress_prefix=f"Progression segment {index + 1}/{len(chunk_files)}"
                )

                log_event({
                    "event": "completed_chunk",
                    "file": original_file.name,
                    "chunk": index,
                    "chunk_file": chunk_file.name
                })

            with open(final_output, "w", encoding="utf-8") as final:
                for partial in partial_outputs:
                    if partial.exists():
                        final.write(partial.read_text(encoding="utf-8"))
                        final.write("\n")

        archive_path = unique_path(ARCHIVES_DIR, original_file.stem, original_file.suffix)
        shutil.move(str(original_file), str(archive_path))

        log_event({
            "event": "completed_file",
            "file": original_file.name,
            "output": final_output.name,
            "archived_as": archive_path.name
        })

        print("Transcription complétée.")

    except Exception as e:
        log_event({
            "event": "error",
            "file": original_file.name,
            "error": str(e)
        })

        print(f"ERREUR : {original_file.name} : {e}")


def main() -> None:
    if not DEPOT_DIR.exists():
        print(f"ERREUR : le répertoire depot n'existe pas : {DEPOT_DIR}")
        sys.exit(1)

    SORTIE_DIR.mkdir(exist_ok=True)
    TEMP_DIR.mkdir(exist_ok=True)
    ARCHIVES_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)
    REJETS_DIR.mkdir(exist_ok=True)

    audio_files = [
        file for file in DEPOT_DIR.iterdir()
        if file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not audio_files:
        print("Aucun fichier .ogg, .mp3 ou .wav trouvé dans depot.")
        return

    prevent_sleep()

    try:
        model = WhisperModel(MODEL_NAME, device=DEVICE)

        for audio_file in audio_files:
            transcribe_file(model, audio_file)
    
    except KeyboardInterrupt:
        print("\nArrêt demandé par l'utilisateur avec CTRL+C.")

        log_event({
            "event": "manual_stop",
            "message": "Traitement interrompu par l'utilisateur avec CTRL+C"
        })

    finally:
        allow_sleep_again()


if __name__ == "__main__":
    main()