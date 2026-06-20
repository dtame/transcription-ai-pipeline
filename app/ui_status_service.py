"""
ui_status_service.py

Service de lecture et résumé des états de projets pour l'interface Streamlit.
Fournit des données propres sans modifier les fichiers existants.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.paths import SORTIE_DIR, LOGS_DIR
from app.project_manager import discover_projects
from app.project_state import load_project_state

# ---------------------------------------------------------------------------
# Constantes de statut
# ---------------------------------------------------------------------------

STATUS_PENDING     = "pending"
STATUS_RUNNING     = "running"
STATUS_SUCCESS     = "success"
STATUS_ERROR       = "error"
STATUS_INTERRUPTED = "paused_or_interrupted"
STATUS_PARTIAL     = "partial"
STATUS_UNKNOWN     = "unknown"


# ---------------------------------------------------------------------------
# Helpers privés
# ---------------------------------------------------------------------------

def _load_report(project_name: str) -> dict:
    """Charge report.json pour un projet (retourne {} si absent ou invalide)."""
    report_path = SORTIE_DIR / project_name / "report.json"
    if report_path.exists():
        try:
            return json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _get_overall_status(state: dict, report: dict) -> str:
    """
    Détermine le statut global d'un projet à partir de project_state.json
    et report.json.
    """
    execution = state.get("execution", {})
    exec_status = execution.get("status")

    if exec_status == STATUS_RUNNING:
        # Le process était en cours mais l'app vient de démarrer → interrompu
        return STATUS_INTERRUPTED

    if exec_status == STATUS_SUCCESS:
        return STATUS_SUCCESS

    if exec_status == STATUS_ERROR:
        return STATUS_ERROR

    # Pas de section execution : inférer depuis les données
    files_state  = state.get("files", {})
    chunks_state = state.get("chunks", {})
    publication  = state.get("publication", {})

    if not files_state and not chunks_state:
        return STATUS_PENDING

    has_audio_errors = any(
        v.get("status") == "failed" for v in files_state.values()
    )
    if has_audio_errors:
        return STATUS_ERROR

    pub_pdf = publication.get("pdf", {}).get("generated", False)
    if pub_pdf:
        return STATUS_SUCCESS

    if files_state or chunks_state:
        return STATUS_PARTIAL

    return STATUS_UNKNOWN


def _get_latest_run_log_for_project(project_name: str) -> dict | None:
    """Cherche dans les run logs le dernier résultat pour ce projet."""
    if not LOGS_DIR.exists():
        return None
    logs = sorted(LOGS_DIR.glob("run_*.json"), reverse=True)
    for log_path in logs[:20]:
        try:
            data = json.loads(log_path.read_text(encoding="utf-8"))
            for proj_result in data.get("projects", []):
                if proj_result.get("project") == project_name:
                    return proj_result
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def get_project_status(project_name: str) -> dict:
    """
    Retourne un dict complet décrivant l'état d'un projet.

    Clés retournées :
      name, status, execution, audio, chunks, corrections,
      harmonized, publication, exports, last_run, errors, error_count
    """
    state  = load_project_state(project_name)
    report = _load_report(project_name)

    files_state   = state.get("files", {})
    chunks_state  = state.get("chunks", {})
    exports_state = state.get("exports", {})
    publication   = state.get("publication", {})
    harmonization = state.get("harmonization", {})
    execution     = state.get("execution", {})

    audio_total       = len(files_state)
    audio_transcribed = sum(1 for v in files_state.values() if v.get("status") == "transcribed")
    audio_errors      = sum(1 for v in files_state.values() if v.get("status") == "failed")

    chunks_total = len(chunks_state)
    chunks_done  = sum(1 for v in chunks_state.values() if v.get("status") == "done")

    reviewed_dir     = SORTIE_DIR / project_name / "reviewed"
    corrections_done = len(list(reviewed_dir.glob("*.md"))) if reviewed_dir.exists() else 0

    pub_md   = publication.get("markdown", {}).get("generated", False)
    pub_docx = publication.get("docx", {}).get("generated", False)
    pub_pdf  = publication.get("pdf", {}).get("generated", False)

    exp_docx = exports_state.get("docx", {}).get("generated", False)
    exp_pdf  = exports_state.get("pdf", {}).get("generated", False)

    harmonized = harmonization.get("generated", False)

    # Dernière exécution : préférence à execution.finished_at > report.execution.last_run
    last_run = (
        execution.get("finished_at")
        or execution.get("last_heartbeat")
        or execution.get("started_at")
        or report.get("execution", {}).get("last_run")
    )

    overall = _get_overall_status(state, report)

    # Collecte des erreurs inline
    errors: list[dict] = []

    for path, info in files_state.items():
        if info.get("status") == "failed" and info.get("error"):
            errors.append({
                "source": "project_state.json",
                "step": "transcription",
                "file": info.get("path", path),
                "message": info.get("error"),
                "date": info.get("updated_at"),
            })

    exec_report = report.get("execution", {})
    if exec_report.get("status") == "error":
        errors.append({
            "source": "report.json",
            "step": "execution",
            "message": "Erreur lors de l'exécution (voir logs)",
            "date": exec_report.get("last_run"),
        })

    latest_run = _get_latest_run_log_for_project(project_name)
    if latest_run and latest_run.get("status") == "error":
        if latest_run.get("fatal_error"):
            errors.append({
                "source": "run_log",
                "step": "pipeline (fatal)",
                "message": latest_run["fatal_error"],
                "date": latest_run.get("started_at"),
            })
        for step_name, step_info in latest_run.get("steps", {}).items():
            if step_info.get("status") == "error":
                errors.append({
                    "source": "run_log",
                    "step": step_name,
                    "message": step_info.get("error"),
                    "date": latest_run.get("started_at"),
                })

    return {
        "name":       project_name,
        "status":     overall,
        "execution":  execution,
        "audio": {
            "total":       audio_total,
            "transcribed": audio_transcribed,
            "errors":      audio_errors,
        },
        "chunks": {
            "total": chunks_total,
            "done":  chunks_done,
        },
        "corrections": corrections_done,
        "harmonized":  harmonized,
        "publication": {
            "markdown": pub_md,
            "docx":     pub_docx,
            "pdf":      pub_pdf,
        },
        "exports": {
            "docx": exp_docx,
            "pdf":  exp_pdf,
        },
        "last_run":    last_run,
        "errors":      errors,
        "error_count": len(errors),
    }


def get_all_projects_status() -> list[dict]:
    """Retourne la liste des statuts de tous les projets détectés dans depot/."""
    projects = discover_projects()
    return [get_project_status(p.name) for p in projects]


def get_incomplete_projects() -> list[str]:
    """Retourne les noms des projets qui ne sont pas encore en statut 'success'."""
    statuses = get_all_projects_status()
    return [s["name"] for s in statuses if s["status"] != STATUS_SUCCESS]


def get_project_errors(project_name: str) -> list[dict]:
    """
    Retourne la liste des erreurs pour un projet, en lisant :
      1. project_state.json
      2. report.json
      3. le dernier run log
    """
    errors: list[dict] = []

    state = load_project_state(project_name)
    for path, info in state.get("files", {}).items():
        if info.get("status") == "failed" and info.get("error"):
            errors.append({
                "source": "project_state.json",
                "step":   "transcription",
                "file":   info.get("path", path),
                "message": info.get("error"),
                "date":   info.get("updated_at"),
            })

    report = _load_report(project_name)
    exec_report = report.get("execution", {})
    if exec_report.get("status") == "error":
        errors.append({
            "source": "report.json",
            "step":   "execution",
            "message": "Erreur lors de l'exécution",
            "date":   exec_report.get("last_run"),
        })

    latest_run = _get_latest_run_log_for_project(project_name)
    if latest_run and latest_run.get("status") == "error":
        if latest_run.get("fatal_error"):
            errors.append({
                "source": "run_log",
                "step":   "pipeline (fatal)",
                "message": latest_run["fatal_error"],
                "date":   latest_run.get("started_at"),
            })
        for step_name, step_info in latest_run.get("steps", {}).items():
            if step_info.get("status") == "error":
                errors.append({
                    "source": "run_log",
                    "step":   step_name,
                    "message": step_info.get("error") or "",
                    "date":   latest_run.get("started_at"),
                })

    return errors


def get_all_errors() -> list[dict]:
    """Retourne toutes les erreurs de tous les projets détectés."""
    all_errors: list[dict] = []
    projects = discover_projects()
    for p in projects:
        errs = get_project_errors(p.name)
        for e in errs:
            e = dict(e)
            e["project"] = p.name
            all_errors.append(e)
    return all_errors


def detect_interrupted_projects() -> list[str]:
    """
    Retourne les projets dont project_state.json contient
    execution.status == 'running' (signe probable d'une interruption).
    """
    interrupted: list[str] = []
    projects = discover_projects()
    for p in projects:
        state = load_project_state(p.name)
        if state.get("execution", {}).get("status") == STATUS_RUNNING:
            interrupted.append(p.name)
    return interrupted


def get_all_run_logs(limit: int = 20) -> list[dict]:
    """
    Retourne les derniers logs d'exécution (logs/run_*.json),
    du plus récent au plus ancien.
    """
    if not LOGS_DIR.exists():
        return []
    log_paths = sorted(LOGS_DIR.glob("run_*.json"), reverse=True)
    result: list[dict] = []
    for log_path in log_paths[:limit]:
        try:
            data = json.loads(log_path.read_text(encoding="utf-8"))
            data["_log_file"] = log_path.name
            result.append(data)
        except Exception:
            pass
    return result
