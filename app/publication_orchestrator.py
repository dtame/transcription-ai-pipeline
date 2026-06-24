"""
Publication Orchestrator — Pipeline complet éditorial → livraison client.

Enchaîne automatiquement :
  1. Editorial Transformer
  2. Quality Guard
  3. Publication Builder
  4. Publication Sanitizer
  5. Cover Builder
  6. DOCX Engine
  7. PDF Engine
  8. ZIP Client

Produit un rapport : sortie/<project>/orchestrator_report.md
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.paths import SORTIE_DIR


# ─────────────────────────────────────────────────────────────────────────────
# Étapes critiques : leur échec stoppe le pipeline
# ─────────────────────────────────────────────────────────────────────────────

_CRITICAL_STEPS = {"editorial_transformer", "publication_builder", "pdf_engine"}


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée principal
# ─────────────────────────────────────────────────────────────────────────────

def generate_complete_client_package(
    project_name: str,
    progress_callback: Callable[[str, str], None] | None = None,
) -> dict:
    """
    Exécute le pipeline complet de publication pour un projet.

    Args:
        project_name: Nom du projet (dossier dans sortie/).
        progress_callback: Appelée à chaque étape avec (label, status).
                           status ∈ {"running", "success", "error", "skipped"}.

    Returns:
        Dict avec steps, status global, durée et chemin du rapport.
    """

    def _notify(label: str, status: str) -> None:
        if progress_callback:
            progress_callback(label, status)

    steps_def = [
        ("editorial_transformer", "Transformation éditoriale",  _run_editorial_transformer),
        ("quality_guard",         "Contrôle qualité",           _run_quality_guard),
        ("publication_builder",   "Publication Builder",         _run_publication_builder),
        ("publication_sanitizer", "Publication Sanitizer",       _run_publication_sanitizer),
        ("cover_builder",         "Cover Builder",               _run_cover_builder),
        ("docx_engine",           "Génération DOCX",             _run_docx_engine),
        ("pdf_engine",            "Génération PDF",              _run_pdf_engine),
        ("client_package",        "Package Client ZIP",          _run_client_package),
    ]

    results: dict = {
        "project":      project_name,
        "started_at":   datetime.now().isoformat(),
        "steps":        {},
        "status":       "pending",
    }

    report_lines: list[str] = [
        f"# Rapport d'orchestration — {project_name}",
        "",
        f"**Date** : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Étapes",
        "",
    ]

    t_global = time.time()
    aborted  = False

    for step_key, step_label, step_fn in steps_def:
        if aborted:
            results["steps"][step_key] = {"status": "skipped"}
            report_lines.append(f"- ⏭ **{step_label}** — ignorée (pipeline arrêté)")
            _notify(step_label, "skipped")
            continue

        _notify(step_label, "running")
        t0 = time.time()
        try:
            step_fn(project_name)
            duration = time.time() - t0
            results["steps"][step_key] = {
                "status":           "success",
                "duration_seconds": duration,
            }
            report_lines.append(f"- ✅ **{step_label}** — {duration:.1f}s")
            _notify(step_label, "success")
        except Exception as exc:
            duration = time.time() - t0
            results["steps"][step_key] = {
                "status":           "error",
                "error":            str(exc),
                "duration_seconds": duration,
            }
            report_lines.append(
                f"- ❌ **{step_label}** — ÉCHEC ({duration:.1f}s) : {exc}"
            )
            _notify(step_label, "error")

            if step_key in _CRITICAL_STEPS:
                report_lines.append("")
                report_lines.append("> ⛔ Arrêt : étape critique échouée.")
                aborted = True

    total_duration = time.time() - t_global
    overall_ok     = all(
        v.get("status") == "success"
        for v in results["steps"].values()
        if v.get("status") != "skipped"
    )

    results["status"]           = "success" if overall_ok else "error"
    results["duration_seconds"] = total_duration
    results["finished_at"]      = datetime.now().isoformat()

    report_lines += [
        "",
        "## Résultat global",
        "",
        f"- **Statut** : {'✅ Succès' if overall_ok else '❌ Échec'}",
        f"- **Durée totale** : {total_duration:.1f}s",
        f"- **Terminé le** : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]

    report_path = SORTIE_DIR / project_name / "orchestrator_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    results["report_path"] = str(report_path)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Fonctions d'exécution des étapes individuelles
# ─────────────────────────────────────────────────────────────────────────────

def _run_editorial_transformer(project_name: str) -> None:
    from app.editorial_transformer import transform_editorial_manuscript
    transform_editorial_manuscript(project_name)


def _run_quality_guard(project_name: str) -> None:
    from app.editorial_quality_guard import run_editorial_quality_guard
    run_editorial_quality_guard(project_name)


def _run_publication_builder(project_name: str) -> None:
    from app.publication_builder import build_publication
    build_publication(project_name)


def _run_publication_sanitizer(project_name: str) -> None:
    from app.publication_sanitizer import generate_sanitized_publication
    result = generate_sanitized_publication(project_name)
    if result is None:
        raise RuntimeError("Publication Sanitizer n'a retourné aucun résultat.")


def _run_cover_builder(project_name: str) -> None:
    from app.cover_builder import generate_cover
    generate_cover(project_name)


def _run_docx_engine(project_name: str) -> None:
    from app.publication_docx_engine import generate_publication_docx
    result = generate_publication_docx(project_name)
    if result is None:
        raise RuntimeError("DOCX Engine n'a retourné aucun résultat.")


def _run_pdf_engine(project_name: str) -> None:
    from app.publication_pdf_engine import generate_publication_pdf
    result = generate_publication_pdf(project_name)
    if result is None:
        raise RuntimeError("PDF Engine n'a retourné aucun résultat.")


def _run_client_package(project_name: str) -> None:
    from app.client_package import build_client_package
    build_client_package(project_name)
