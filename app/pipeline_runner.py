from __future__ import annotations

import time
import traceback
from datetime import datetime
from pathlib import Path

from app.project_manager import AudioProject
from app.project_state import (
    load_project_state,
    register_chunk,
    save_project_state,
    is_audio_already_transcribed,
    mark_audio_processing,
    mark_audio_transcribed,
    mark_audio_failed,
)
from app.file_utils import file_hash
from app.audio_utils import get_audio_duration_seconds
from app.logger import log_event


STEP_NAMES = [
    "transcription",
    "merge_transcripts",
    "chunk_generation",
    "ai_processing",
    "correction_review",
    "correction_apply",
    "final_document",
    "harmonization",
    "publication_markdown",
    "export_docx",
    "export_pdf",
    "publication_docx",
    "publication_pdf",
    "report",
]


def _fmt_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _step_result(ok: bool, error: str | None = None) -> dict:
    return {
        "status": "success" if ok else "error",
        "error": error,
    }


def _run_transcription(model, project: AudioProject) -> dict:
    """Transcrit tous les fichiers audio du projet (avec reprise)."""
    state = load_project_state(project)
    errors = []

    for audio_path in project.audio_files:
        transcript_path = project.transcripts_dir / f"{audio_path.stem}.txt"
        audio_hash = file_hash(audio_path)

        if is_audio_already_transcribed(state, audio_path, audio_hash, transcript_path):
            log_event(f"SKIP déjà transcrit : {audio_path.name}")
            continue

        try:
            mark_audio_processing(state, audio_path, audio_hash)
            save_project_state(project, state)

            total_duration = get_audio_duration_seconds(audio_path)

            from app.transcription_service import transcribe_audio_to_txt
            transcribe_audio_to_txt(
                model=model,
                audio_path=audio_path,
                output_path=transcript_path,
                total_duration_seconds=total_duration,
            )

            mark_audio_transcribed(state, audio_path, audio_hash, transcript_path)
            save_project_state(project, state)

        except Exception as exc:
            mark_audio_failed(state, audio_path, audio_hash, exc)
            save_project_state(project, state)
            errors.append(str(exc))
            log_event(f"ERREUR transcription {audio_path.name} : {exc}")

    if errors:
        return _step_result(False, "; ".join(errors))
    return _step_result(True)


def run_project_pipeline(project: AudioProject, model=None) -> dict:
    """
    Exécute le pipeline complet pour un projet.

    Retourne :
    {
        "project": "demo_conference",
        "status": "success" | "error",
        "duration_seconds": 123,
        "steps": { <step_name>: {"status": ..., "error": ...}, ... }
    }
    """
    started_at = datetime.now()
    t0 = time.time()

    steps: dict[str, dict] = {}
    project_status = "success"

    print(f"\n{'=' * 50}")
    print(f"  Projet : {project.name}")
    print(f"  Début  : {started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 50}")

    def run_step(name: str, fn):
        nonlocal project_status
        print(f"\n[{name}] ...", end=" ", flush=True)
        t = time.time()
        try:
            fn()
            elapsed = time.time() - t
            steps[name] = _step_result(True)
            print(f"OK ({elapsed:.1f}s)")
        except Exception as exc:
            elapsed = time.time() - t
            err = traceback.format_exc()
            steps[name] = _step_result(False, str(exc))
            project_status = "error"
            print(f"ERREUR ({elapsed:.1f}s)")
            print(f"  → {exc}")
            log_event(f"ERREUR étape {name} / {project.name} : {exc}\n{err}")

    # ------------------------------------------------------------------
    # Étape 1 – Transcription (nécessite le modèle Whisper)
    # ------------------------------------------------------------------
    if model is not None:
        print(f"\n[transcription] ...", end=" ", flush=True)
        t = time.time()
        result = _run_transcription(model, project)
        elapsed = time.time() - t
        steps["transcription"] = result
        if result["status"] == "error":
            project_status = "error"
            print(f"ERREUR ({elapsed:.1f}s) → {result['error']}")
        else:
            print(f"OK ({elapsed:.1f}s)")
    else:
        steps["transcription"] = _step_result(True)
        print("\n[transcription] IGNORÉE (pas de modèle Whisper fourni)")

    # ------------------------------------------------------------------
    # Étapes 2-14
    # ------------------------------------------------------------------
    from app.transcript_merger import merge_project_transcripts
    from app.chunk_service import create_project_chunks
    from app.ai_processor import process_project_chunks
    from app.correction_review_service import generate_review_files
    from app.correction_apply_service import apply_corrections
    from app.final_document_builder import build_final_document
    from app.global_editor_service import harmonize_document
    from app.publication_template_service import build_publication_markdown
    from app.docx_export_service import export_docx, export_publication_docx
    from app.pdf_export_service import export_pdf, export_publication_pdf
    from app.report_service import build_project_report

    def step_merge():
        merge_project_transcripts(project)

    def step_chunks():
        chunk_paths = create_project_chunks(project)
        state = load_project_state(project)
        for chunk_path in chunk_paths:
            register_chunk(state, chunk_path.name)
        save_project_state(project, state)

    def step_ai():
        process_project_chunks(project)

    def step_review():
        generate_review_files(project)

    def step_apply():
        apply_corrections(project.name)

    def step_final():
        build_final_document(project.name)

    def step_harmonize():
        harmonize_document(project.name)

    def step_pub_md():
        build_publication_markdown(project.name)

    def step_export_docx():
        export_docx(project.name)

    def step_export_pdf():
        export_pdf(project.name)

    def step_pub_docx():
        export_publication_docx(project.name)

    def step_pub_pdf():
        export_publication_pdf(project.name)

    def step_report():
        _build_report_with_execution(project.name, started_at, time.time() - t0)

    remaining_steps = [
        ("merge_transcripts",    step_merge),
        ("chunk_generation",     step_chunks),
        ("ai_processing",        step_ai),
        ("correction_review",    step_review),
        ("correction_apply",     step_apply),
        ("final_document",       step_final),
        ("harmonization",        step_harmonize),
        ("publication_markdown", step_pub_md),
        ("export_docx",          step_export_docx),
        ("export_pdf",           step_export_pdf),
        ("publication_docx",     step_pub_docx),
        ("publication_pdf",      step_pub_pdf),
        ("report",               step_report),
    ]

    for step_name, step_fn in remaining_steps:
        run_step(step_name, step_fn)

    duration = time.time() - t0
    finished_at = datetime.now()

    print(f"\n{'-' * 50}")
    symbol = "OK" if project_status == "success" else "ERREUR"
    print(f"  [{symbol}] Projet {project.name} termine en {_fmt_duration(duration)}")
    print(f"{'-' * 50}")

    log_event(f"Projet {project.name} terminé : {project_status} en {_fmt_duration(duration)}")

    return {
        "project": project.name,
        "status": project_status,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round(duration, 1),
        "steps": steps,
    }


def run_exports_only(project: AudioProject) -> dict:
    """
    Exécute uniquement publication → docx → pdf sur un projet existant.
    """
    started_at = datetime.now()
    t0 = time.time()
    steps: dict[str, dict] = {}
    project_status = "success"

    print(f"\n{'=' * 50}")
    print(f"  Exports : {project.name}")
    print(f"{'=' * 50}")

    from app.publication_template_service import build_publication_markdown
    from app.docx_export_service import export_publication_docx
    from app.pdf_export_service import export_publication_pdf
    from app.report_service import build_project_report

    export_steps = [
        ("publication_markdown", lambda: build_publication_markdown(project.name)),
        ("publication_docx",     lambda: export_publication_docx(project.name)),
        ("publication_pdf",      lambda: export_publication_pdf(project.name)),
        ("report",               lambda: build_project_report(project.name)),
    ]

    for step_name, fn in export_steps:
        print(f"\n[{step_name}] ...", end=" ", flush=True)
        t = time.time()
        try:
            fn()
            elapsed = time.time() - t
            steps[step_name] = _step_result(True)
            print(f"OK ({elapsed:.1f}s)")
        except Exception as exc:
            elapsed = time.time() - t
            steps[step_name] = _step_result(False, str(exc))
            project_status = "error"
            print(f"ERREUR ({elapsed:.1f}s) → {exc}")
            log_event(f"ERREUR export {step_name} / {project.name} : {exc}")

    duration = time.time() - t0

    return {
        "project": project.name,
        "status": project_status,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "duration_seconds": round(duration, 1),
        "steps": steps,
    }


def run_report_only(project_name: str) -> dict:
    """Régénère uniquement le rapport d'un projet."""
    t0 = time.time()
    started_at = datetime.now()
    steps: dict[str, dict] = {}
    project_status = "success"

    print(f"\n[report] {project_name} ...", end=" ", flush=True)
    try:
        _build_report_with_execution(project_name, started_at, time.time() - t0)
        steps["report"] = _step_result(True)
        print(f"OK ({time.time() - t0:.1f}s)")
    except Exception as exc:
        steps["report"] = _step_result(False, str(exc))
        project_status = "error"
        print(f"ERREUR → {exc}")

    return {
        "project": project_name,
        "status": project_status,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "duration_seconds": round(time.time() - t0, 1),
        "steps": steps,
    }


def _build_report_with_execution(
    project_name: str,
    started_at: datetime,
    duration_seconds: float,
) -> None:
    """Génère le rapport et y injecte la section execution."""
    import json
    from app.report_service import build_project_report
    from app.paths import SORTIE_DIR

    report_path = build_project_report(project_name)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["execution"] = {
        "last_run": started_at.isoformat(timespec="seconds"),
        "duration_seconds": round(duration_seconds, 1),
        "status": "success",
    }
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
