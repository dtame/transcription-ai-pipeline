
from faster_whisper import WhisperModel
from pathlib import Path
from datetime import datetime
from app.project_manager import AudioProject, discover_projects
from app.transcript_merger import merge_project_transcripts
from app.chunk_service import create_project_chunks
from app.ai_processor import process_project_chunks
from app.correction_review_service import generate_review_files
from app.correction_apply_service import apply_corrections
from app.final_document_builder import build_final_document
from app.docx_export_service import export_docx, export_publication_docx
from app.pdf_export_service import export_pdf, export_publication_pdf
from app.publication_template_service import build_publication_markdown
from app.global_editor_service import harmonize_document
from app.report_service import build_project_report
import shutil
import time
import sys
from app.config import ( 
    CHUNK_THRESHOLD_MINUTES,
    CHUNK_DURATION_MINUTES,
    MODEL_NAME,
    SUPPORTED_EXTENSIONS,
    DEVICE
)
from app.file_utils import (
    sanitize_name,
    file_hash,
    unique_path,
    write_json_atomic
)

from app.transcript_models import (
    CAPTURE_MODE_DIRECT,
    AudioCapture,
    CapturedPart,
    CapturedSegment
)

from app.audio_utils import (
    get_audio_duration_seconds,
    format_timestamp,    
    print_progress, 
    split_audio
)

from app.paths import (
    TEMP_DIR, 
    SORTIE_DIR, 
    REJETS_DIR, 
    ARCHIVES_DIR,
    DEPOT_DIR,
    LOGS_DIR
)

from app.logger import log_event

from app.sleep_guard import (
    prevent_sleep,
    allow_sleep_again
)

from app.project_state import (
    load_project_state,
    register_chunk,
    save_project_state,
    is_audio_already_transcribed,
    mark_audio_processing,
    mark_audio_transcribed,
    mark_audio_failed
)

def transcribe_audio_to_txt(
    model: WhisperModel,
    audio_path: Path,
    output_path: Path,
    total_duration_seconds: float,
    timestamp_offset: float = 0,
    progress_prefix: str = "Progression",
    capture_path: Path | None = None
) -> str:
    """
    Transcrit un fichier audio et écrit le transcript texte V1.

    Langue (contrat V2, Phase 1) :
        La langue réellement détectée par Whisper est conservée, ainsi que le
        texte transcrit dans cette langue. Aucune retranscription forcée en
        anglais — le comportement V1 traduisait involontairement le contenu des
        projets non francophones/anglophones.

    Capture structurée (contrat V2, Phase 1) :
        Si `capture_path` est fourni, les segments Whisper (timestamps numériques
        précis, texte, langue détectée) sont enregistrés à cet emplacement avant
        la publication du transcript texte. Un transcript publié possède donc
        toujours sa capture, ce qui rend transcript_data.json indépendant de tout
        reparsing des timestamps textuels.
    """
    start_time = time.time()

    segments, info = model.transcribe(str(audio_path))

    detected_language = info.language

    print(f"Detected language : {detected_language}")
    print("Transcription en cours...")

    # Écriture atomique : tant que la transcription n'est pas complète, rien n'est
    # publié dans output_path. Un transcript final valide déjà présent n'est donc
    # jamais remplacé par une version tronquée.
    output_path = Path(output_path)
    temp_path = output_path.with_name(output_path.name + ".partial")

    captured: list[CapturedSegment] = []

    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            for segment in segments:
                absolute_start = segment.start + timestamp_offset
                absolute_end = segment.end + timestamp_offset

                start = format_timestamp(absolute_start)
                end = format_timestamp(absolute_end)
                text = segment.text.strip()

                f.write(f"[{start} -> {end}] {text}\n")

                captured.append(
                    CapturedSegment(
                        start=absolute_start,
                        end=absolute_end,
                        text=text,
                    )
                )

                print_progress(
                    current_seconds=absolute_end,
                    total_seconds=total_duration_seconds,
                    start_time=start_time,
                    prefix=progress_prefix
                )

        if capture_path is not None:
            _write_direct_capture(
                capture_path=capture_path,
                audio_path=audio_path,
                total_duration_seconds=total_duration_seconds,
                detected_language=detected_language,
                captured=captured,
            )
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise

    # Path.replace() remplace la cible de façon atomique, y compris sur Windows.
    temp_path.replace(output_path)

    print_progress(
        current_seconds=total_duration_seconds,
        total_seconds=total_duration_seconds,
        start_time=start_time,
        prefix=progress_prefix
    )
    print()

    return detected_language


def _write_direct_capture(
    capture_path: Path,
    audio_path: Path,
    total_duration_seconds: float,
    detected_language: str,
    captured: list[CapturedSegment],
) -> None:
    """
    Enregistre la capture structurée d'un fichier audio transcrit d'une traite.

    Un fichier court ne comporte qu'une seule partie technique, de décalage 0 :
    les timestamps capturés sont déjà relatifs au fichier audio source.
    """
    capture = AudioCapture(
        filename=Path(audio_path).name,
        duration_seconds=total_duration_seconds,
        mode=CAPTURE_MODE_DIRECT,
        parts=[
            CapturedPart(
                id="part_001",
                start_seconds=0.0,
                end_seconds=total_duration_seconds,
                effective_start_local=0.0,
                detected_language=detected_language,
                segments=list(captured),
            )
        ],
    )

    write_json_atomic(Path(capture_path), capture.to_dict())


def transcribe_file(model: WhisperModel, original_file: Path, project: AudioProject) -> None:
    original_hash = file_hash(original_file)
    safe_stem = sanitize_name(original_file.stem)    
    work_dir = project.temp_dir / f"{safe_stem}_{original_hash[:8]}"
    work_dir.mkdir(parents=True, exist_ok=True)

    final_output = project.transcripts_dir / f"{safe_stem}.txt"    

    try:
        print("\n" + "=" * 70)
        print(f"Fichier : {original_file.name}")
        print(f"Taille : {round(original_file.stat().st_size / (1024*1024), 2)} MB")
        print(f"Début : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        if original_file.stat().st_size == 0:
            reject_path = unique_path(project.rejets_dir, original_file.stem, original_file.suffix)
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

        archive_path = unique_path(project.archives_dir, original_file.stem, original_file.suffix)
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


def run_transcription_pipeline():
    prevent_sleep()

    try:
        model = WhisperModel(
            MODEL_NAME,
            device=DEVICE
        )

        projects = discover_projects()

        for project in projects:
            log_event(f"Projet détecté : {project.name}")

            state = load_project_state(project)

            for audio_path in project.audio_files:
                transcript_path = (
                    project.transcripts_dir /
                    f"{audio_path.stem}.txt"
                )

                audio_hash = file_hash(audio_path)

                if is_audio_already_transcribed(
                    state,
                    audio_path,
                    audio_hash,
                    transcript_path
                ):
                    log_event(f"SKIP déjà transcrit : {audio_path.name}")
                    continue

                try:
                    mark_audio_processing(
                        state,
                        audio_path,
                        audio_hash
                    )
                    save_project_state(project, state)

                    total_duration_seconds = get_audio_duration_seconds(audio_path)
                    transcribe_audio_to_txt(
                        model=model,
                        audio_path=audio_path,
                        output_path=transcript_path,
                        total_duration_seconds=total_duration_seconds
                    )

                    mark_audio_transcribed(
                        state,
                        audio_path,
                        audio_hash,
                        transcript_path
                    )
                    save_project_state(project, state)

                except Exception as e:
                    mark_audio_failed(
                        state,
                        audio_path,
                        audio_hash,
                        e
                    )
                    save_project_state(project, state)

                    log_event(
                        f"ERREUR transcription {audio_path.name} : {e}"
                    )

            merge_project_transcripts(project)
            chunk_results = create_project_chunks(project)

            for result in chunk_results:
                register_chunk(state, result["name"])

            save_project_state(
                project,
                state
            )

            process_project_chunks(project)
            generate_review_files(project)
            apply_corrections(project.name)
            build_final_document(project.name)
            harmonize_document(project.name)
            export_docx(project.name)
            export_pdf(project.name)
            build_publication_markdown(project.name)
            export_publication_docx(project.name)
            export_publication_pdf(project.name)
            build_project_report(project.name)
            log_event(
                f"Chunks IA générés pour {project.name} : {len(chunk_paths)}"
            )
    finally:
        allow_sleep_again()