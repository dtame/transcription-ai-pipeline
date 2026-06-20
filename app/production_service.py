from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from app.project_manager import discover_projects, create_project, AudioProject
from app.pipeline_runner import (
    run_project_pipeline,
    run_exports_only,
    run_report_only,
    _fmt_duration,
)
from app.paths import LOGS_DIR
from app.logger import log_event
from app.sleep_guard import prevent_sleep, allow_sleep_again


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_run_log(summary: dict) -> Path:
    """Enregistre le résumé d'exécution dans logs/run_YYYYMMDD_HHMMSS.json."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOGS_DIR / f"run_{ts}.json"
    log_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return log_path


def _print_summary(summary: dict, log_path: Path) -> None:
    total = summary["projects_total"]
    success = summary["projects_success"]
    errors = summary["projects_error"]
    duration = summary["duration_seconds"]

    print(f"\n{'=' * 50}")
    print("  Traitement terminé")
    print(f"{'=' * 50}")
    print(f"  Projets   : {total}")
    print(f"  Succès    : {success}")
    print(f"  Erreurs   : {errors}")
    print(f"  Temps total : {_fmt_duration(duration)}")
    print(f"\n  Rapport   : {log_path}")
    print(f"{'=' * 50}\n")


def _build_summary(
    started_at: datetime,
    project_results: list[dict],
) -> dict:
    finished_at = datetime.now()
    duration = (finished_at - started_at).total_seconds()

    successes = [r for r in project_results if r["status"] == "success"]
    errors    = [r for r in project_results if r["status"] != "success"]

    return {
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "projects_total": len(project_results),
        "projects_success": len(successes),
        "projects_error": len(errors),
        "duration_seconds": round(duration, 1),
        "projects": project_results,
    }


def _load_whisper_model():
    """Charge le modèle Whisper (import différé pour éviter le délai si inutile)."""
    from faster_whisper import WhisperModel
    from app.config import MODEL_NAME, DEVICE

    print(f"Chargement du modèle Whisper ({MODEL_NAME} / {DEVICE})...")
    return WhisperModel(MODEL_NAME, device=DEVICE)


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def process_all_projects() -> dict:
    """
    Traite tous les projets détectés dans depot/.
    Retourne le résumé d'exécution.
    """
    prevent_sleep()
    started_at = datetime.now()
    results: list[dict] = []

    try:
        projects = discover_projects()

        if not projects:
            print("Aucun projet détecté dans depot/.")
            summary = _build_summary(started_at, [])
            log_path = _save_run_log(summary)
            _print_summary(summary, log_path)
            return summary

        print(f"\n{len(projects)} projet(s) détecté(s) :")
        for p in projects:
            print(f"  - {p.name}  ({len(p.audio_files)} fichier(s) audio)")

        model = _load_whisper_model()

        for project in projects:
            try:
                result = run_project_pipeline(project, model=model)
            except Exception as exc:
                result = {
                    "project": project.name,
                    "status": "error",
                    "started_at": datetime.now().isoformat(timespec="seconds"),
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                    "duration_seconds": 0,
                    "steps": {},
                    "fatal_error": str(exc),
                }
                log_event(f"ERREUR fatale projet {project.name} : {exc}")
                print(f"\nERREUR fatale — {project.name} : {exc}")

            results.append(result)

    finally:
        allow_sleep_again()

    summary = _build_summary(started_at, results)
    log_path = _save_run_log(summary)
    _print_summary(summary, log_path)
    return summary


def process_project(project_name: str) -> dict:
    """
    Traite un projet unique par son nom.
    """
    prevent_sleep()
    started_at = datetime.now()

    try:
        projects = discover_projects()
        project = next((p for p in projects if p.name == project_name), None)

        if project is None:
            print(f"Projet introuvable : {project_name}")
            result = {
                "project": project_name,
                "status": "error",
                "started_at": started_at.isoformat(timespec="seconds"),
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "duration_seconds": 0,
                "steps": {},
                "fatal_error": f"Projet '{project_name}' introuvable dans depot/",
            }
            summary = _build_summary(started_at, [result])
            log_path = _save_run_log(summary)
            _print_summary(summary, [log_path][0])
            return summary

        model = _load_whisper_model()
        result = run_project_pipeline(project, model=model)

    except Exception as exc:
        result = {
            "project": project_name,
            "status": "error",
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "duration_seconds": 0,
            "steps": {},
            "fatal_error": str(exc),
        }
        log_event(f"ERREUR fatale projet {project_name} : {exc}")

    finally:
        allow_sleep_again()

    summary = _build_summary(started_at, [result])
    log_path = _save_run_log(summary)
    _print_summary(summary, log_path)
    return summary


def process_exports_only() -> dict:
    """
    Génère uniquement publication + DOCX + PDF pour tous les projets existants.
    N'exécute pas la transcription ni l'IA.
    """
    started_at = datetime.now()
    results: list[dict] = []

    projects = discover_projects()

    if not projects:
        print("Aucun projet détecté dans depot/.")
        summary = _build_summary(started_at, [])
        log_path = _save_run_log(summary)
        _print_summary(summary, log_path)
        return summary

    for project in projects:
        try:
            result = run_exports_only(project)
        except Exception as exc:
            result = {
                "project": project.name,
                "status": "error",
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "duration_seconds": 0,
                "steps": {},
                "fatal_error": str(exc),
            }
            log_event(f"ERREUR export {project.name} : {exc}")

        results.append(result)

    summary = _build_summary(started_at, results)
    log_path = _save_run_log(summary)
    _print_summary(summary, log_path)
    return summary


def process_reports_only() -> dict:
    """Régénère uniquement les rapports pour tous les projets existants."""
    from app.paths import SORTIE_DIR

    started_at = datetime.now()
    results: list[dict] = []

    project_dirs = [
        d for d in SORTIE_DIR.iterdir()
        if d.is_dir() and (d / "project_state.json").exists()
    ]

    if not project_dirs:
        print("Aucun projet existant trouvé dans sortie/.")
        summary = _build_summary(started_at, [])
        log_path = _save_run_log(summary)
        _print_summary(summary, log_path)
        return summary

    for project_dir in sorted(project_dirs):
        result = run_report_only(project_dir.name)
        results.append(result)

    summary = _build_summary(started_at, results)
    log_path = _save_run_log(summary)
    _print_summary(summary, log_path)
    return summary


def resume_project(project_name: str) -> dict:
    """
    Reprend un projet incomplet (même logique que process_project,
    mais ignore les projets déjà en 'success').
    """
    from app.ui_status_service import get_project_status, STATUS_SUCCESS

    status = get_project_status(project_name)
    if status["status"] == STATUS_SUCCESS:
        return {
            "project": project_name,
            "status": "skipped",
            "message": "Projet déjà terminé avec succès.",
            "projects_total": 1,
            "projects_success": 1,
            "projects_error": 0,
            "duration_seconds": 0,
            "projects": [],
        }

    return process_project(project_name)


def resume_incomplete_projects() -> dict:
    """
    Traite uniquement les projets dont le statut n'est pas 'success'.
    Utile pour reprendre après une interruption sans relancer les projets terminés.
    """
    from app.ui_status_service import get_all_projects_status, STATUS_SUCCESS

    prevent_sleep()
    started_at = datetime.now()
    results: list[dict] = []

    try:
        statuses = get_all_projects_status()
        incomplete_names = {s["name"] for s in statuses if s["status"] != STATUS_SUCCESS}

        if not incomplete_names:
            print("Tous les projets sont déjà terminés avec succès.")
            summary = _build_summary(started_at, [])
            log_path = _save_run_log(summary)
            _print_summary(summary, log_path)
            return summary

        projects = discover_projects()
        to_run = [p for p in projects if p.name in incomplete_names]

        print(f"\n{len(to_run)} projet(s) incomplet(s) à reprendre :")
        for p in to_run:
            print(f"  - {p.name}")

        model = _load_whisper_model()

        for project in to_run:
            try:
                result = run_project_pipeline(project, model=model)
            except Exception as exc:
                result = {
                    "project": project.name,
                    "status": "error",
                    "started_at": datetime.now().isoformat(timespec="seconds"),
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                    "duration_seconds": 0,
                    "steps": {},
                    "fatal_error": str(exc),
                }
                log_event(f"ERREUR fatale projet {project.name} : {exc}")
                print(f"\nERREUR fatale — {project.name} : {exc}")
            results.append(result)

    finally:
        allow_sleep_again()

    summary = _build_summary(started_at, results)
    log_path = _save_run_log(summary)
    _print_summary(summary, log_path)
    return summary


def process_exports_only_project(project_name: str) -> dict:
    """
    Génère uniquement publication + DOCX + PDF pour un projet spécifique.
    N'exécute pas la transcription ni l'IA.
    """
    prevent_sleep()
    started_at = datetime.now()

    try:
        projects = discover_projects()
        project = next((p for p in projects if p.name == project_name), None)

        if project is None:
            result = {
                "project": project_name,
                "status": "error",
                "started_at": started_at.isoformat(timespec="seconds"),
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "duration_seconds": 0,
                "steps": {},
                "fatal_error": f"Projet '{project_name}' introuvable dans depot/",
            }
        else:
            result = run_exports_only(project)

    except Exception as exc:
        result = {
            "project": project_name,
            "status": "error",
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "duration_seconds": 0,
            "steps": {},
            "fatal_error": str(exc),
        }
        log_event(f"ERREUR export {project_name} : {exc}")

    finally:
        allow_sleep_again()

    summary = _build_summary(started_at, [result])
    log_path = _save_run_log(summary)
    _print_summary(summary, log_path)
    return summary


def process_reports_only_project(project_name: str) -> dict:
    """Régénère uniquement le rapport JSON d'un projet spécifique."""
    started_at = datetime.now()
    result = run_report_only(project_name)
    summary = _build_summary(started_at, [result])
    log_path = _save_run_log(summary)
    _print_summary(summary, log_path)
    return summary


def get_projects_status() -> list[dict]:
    """
    Retourne l'état de chaque projet (audio, chunks, corrections, publication, exports).
    """
    from app.paths import SORTIE_DIR
    from app.project_state import load_project_state

    projects = discover_projects()
    statuses = []

    for project in projects:
        state = load_project_state(project.name)

        files_state  = state.get("files", {})
        chunks_state = state.get("chunks", {})
        exports_state = state.get("exports", {})
        pub_state = state.get("publication", {})

        audio_total       = len(project.audio_files)
        audio_transcribed = sum(1 for v in files_state.values() if v.get("status") == "transcribed")

        chunks_total     = len(chunks_state)
        chunks_done      = sum(1 for v in chunks_state.values() if v.get("status") == "done")

        corrections_dir = project.output_dir / "reviewed"
        corrections_done = len(list(corrections_dir.glob("*.md"))) if corrections_dir.exists() else 0

        pub_md  = pub_state.get("markdown", {}).get("generated", False)
        pub_docx = pub_state.get("docx", {}).get("generated", False)
        pub_pdf  = pub_state.get("pdf", {}).get("generated", False)

        exp_docx = exports_state.get("docx", {}).get("generated", False)
        exp_pdf  = exports_state.get("pdf", {}).get("generated", False)

        statuses.append({
            "name": project.name,
            "audio": {"total": audio_total, "transcribed": audio_transcribed},
            "chunks": {"total": chunks_total, "done": chunks_done},
            "corrections": corrections_done,
            "publication": {
                "markdown": pub_md,
                "docx": pub_docx,
                "pdf": pub_pdf,
            },
            "exports": {
                "docx": exp_docx,
                "pdf": exp_pdf,
            },
        })

    return statuses


def print_projects_status() -> None:
    """Affiche l'état des projets dans la console."""
    statuses = get_projects_status()

    if not statuses:
        print("Aucun projet détecté.")
        return

    for s in statuses:
        print(f"\n{'-' * 40}")
        print(f"  {s['name']}")
        print(f"{'-' * 40}")

        audio = s["audio"]
        print(f"  Audio        : {audio['transcribed']}/{audio['total']}")

        chunks = s["chunks"]
        print(f"  Chunks       : {chunks['done']}/{chunks['total']}")

        print(f"  Corrections  : {s['corrections']}")

        pub = s["publication"]
        pub_md   = "OK" if pub["markdown"] else "-"
        pub_docx = "OK" if pub["docx"]     else "-"
        pub_pdf  = "OK" if pub["pdf"]      else "-"
        print(f"  Publication  : MD={pub_md}  DOCX={pub_docx}  PDF={pub_pdf}")

        exp = s["exports"]
        exp_docx = "OK" if exp["docx"] else "-"
        exp_pdf  = "OK" if exp["pdf"]  else "-"
        print(f"  Exports      : DOCX={exp_docx}  PDF={exp_pdf}")

    print()
