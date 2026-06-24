"""
Client Package Builder — Paquet livrable client final.

Crée un ZIP propre contenant uniquement les livrables finaux du projet,
prêts à être envoyés au client.

Sources :
    sortie/<project>/publication/publication.pdf   (obligatoire)
    sortie/<project>/publication/publication.docx  (recommandé)
    sortie/<project>/publication/publication.md    (recommandé)
    sortie/<project>/final/editorial_quality_report.md  (recommandé)

Sortie :
    sortie/<project>/client/<project_name>_package.zip
    sortie/<project>/client/project_summary.json
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

from app.logger import log_event
from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state
from app.publication_metadata import get_publication_metadata


# ─────────────────────────────────────────────────────────────────────────────
# Chemins internes
# ─────────────────────────────────────────────────────────────────────────────

def _client_dir(project_name: str) -> Path:
    return SORTIE_DIR / project_name / "client"


def _publication_dir(project_name: str) -> Path:
    return SORTIE_DIR / project_name / "publication"


def _final_dir(project_name: str) -> Path:
    return SORTIE_DIR / project_name / "final"


def _zip_path(project_name: str) -> Path:
    return _client_dir(project_name) / f"{project_name}_package.zip"


def _summary_path(project_name: str) -> Path:
    return _client_dir(project_name) / "project_summary.json"


# ─────────────────────────────────────────────────────────────────────────────
# Lecture des métadonnées depuis project_state.json
# ─────────────────────────────────────────────────────────────────────────────

def _extract_state_meta(state: dict) -> tuple[str, str, str]:
    """
    Extrait document_language, publication_mode, quality_status depuis l'état.

    Retourne (document_language, publication_mode, quality_status).
    """
    pub = state.get("publication", {})

    document_language = (
        pub.get("language")
        or state.get("document_language")
        or "unknown"
    )

    publication_mode = (
        pub.get("mode")
        or state.get("publication_mode")
        or "BOOK"
    )

    quality_status = (
        pub.get("quality", {}).get("status")
        or state.get("quality_status")
        or "unknown"
    )

    return document_language, publication_mode, quality_status


# ─────────────────────────────────────────────────────────────────────────────
# Génération de project_summary.json
# ─────────────────────────────────────────────────────────────────────────────

def _build_project_summary(
    project_name: str,
    included_files: list[str],
    state: dict,
) -> dict:
    """Construit le dictionnaire project_summary à sérialiser en JSON."""
    document_language, publication_mode, quality_status = _extract_state_meta(state)

    # Métadonnées de publication centralisées
    pub_meta = get_publication_metadata(project_name)
    metadata_block = {
        "title":            pub_meta.get("title", ""),
        "subtitle":         pub_meta.get("subtitle", ""),
        "author":           pub_meta.get("author", ""),
        "organization":     pub_meta.get("organization", ""),
        "publication_date": pub_meta.get("publication_date", ""),
    }

    print(
        f"[client_package] Métadonnées ajoutées au ZIP summary — "
        f"titre={metadata_block['title']!r}"
    )

    return {
        "project":           project_name,
        "generated_at":      datetime.now().isoformat(timespec="seconds"),
        "included_files":    included_files,
        "document_language": document_language,
        "publication_mode":  publication_mode,
        "quality_status":    quality_status,
        "metadata":          metadata_block,
    }


def _write_project_summary(summary_file: Path, summary: dict) -> None:
    summary_file.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Mise à jour de project_state.json
# ─────────────────────────────────────────────────────────────────────────────

def _update_state_success(
    project_name: str,
    zip_out: Path,
    included_files: list[str],
) -> None:
    state = load_project_state(project_name)
    state["client_package"] = {
        "generated": True,
        "path": str(zip_out),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "included_files": included_files,
    }
    save_project_state(project_name, state)


def _update_state_error(project_name: str, error: str) -> None:
    state = load_project_state(project_name)
    state["client_package"] = {
        "generated": False,
        "error": error,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_project_state(project_name, state)


# ─────────────────────────────────────────────────────────────────────────────
# Création du ZIP
# ─────────────────────────────────────────────────────────────────────────────

def _build_zip(
    zip_out: Path,
    candidates: list[tuple[Path, str]],
    summary_content: str,
) -> list[str]:
    """
    Crée le ZIP client.

    candidates : liste de (source_path, archive_name) — seuls les fichiers
                 existants sont inclus.
    summary_content : contenu JSON de project_summary.json.

    Retourne la liste des noms d'archive effectivement inclus.
    """
    included: list[str] = []

    zip_tmp = zip_out.with_suffix(".tmp")
    try:
        with zipfile.ZipFile(zip_tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for src, arc_name in candidates:
                if src.exists():
                    zf.write(src, arc_name)
                    included.append(arc_name)

            zf.writestr("project_summary.json", summary_content.encode("utf-8"))
            included.append("project_summary.json")

    except Exception:
        zip_tmp.unlink(missing_ok=True)
        raise

    if zip_out.exists():
        zip_out.unlink()
    zip_tmp.rename(zip_out)

    return included


# ─────────────────────────────────────────────────────────────────────────────
# Informations ZIP (pour l'interface Streamlit)
# ─────────────────────────────────────────────────────────────────────────────

def get_package_info(project_name: str) -> dict:
    """
    Retourne les informations sur le package ZIP client généré.

    Clés :
        exists          bool
        zip_path        Path | None
        zip_name        str
        size_bytes      int
        size_human      str
        generated_at    str
        included_files  list[str]
        summary_path    Path | None
        pdf_ready       bool
    """
    zip_out = _zip_path(project_name)
    pub_dir = _publication_dir(project_name)
    state = load_project_state(project_name)
    pkg_state = state.get("client_package", {})

    files: list[str] = []
    if zip_out.exists():
        try:
            with zipfile.ZipFile(zip_out, "r") as zf:
                files = zf.namelist()
        except Exception:
            pass

    size_bytes = zip_out.stat().st_size if zip_out.exists() else 0

    return {
        "exists": zip_out.exists(),
        "zip_path": zip_out if zip_out.exists() else None,
        "zip_name": zip_out.name,
        "size_bytes": size_bytes,
        "size_human": _human_size(size_bytes),
        "generated_at": pkg_state.get("generated_at", ""),
        "included_files": files,
        "summary_path": _summary_path(project_name) if _summary_path(project_name).exists() else None,
        "pdf_ready": (pub_dir / "publication.pdf").exists(),
    }


def _human_size(size_bytes: int) -> str:
    for unit in ("o", "Ko", "Mo", "Go"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} To"


# ─────────────────────────────────────────────────────────────────────────────
# Fonction principale
# ─────────────────────────────────────────────────────────────────────────────

def build_client_package(project_name: str) -> Path | None:
    """
    Crée un ZIP client contenant les livrables finaux du projet.

    Entrées recherchées :
        sortie/<project>/publication/publication.pdf   (obligatoire)
        sortie/<project>/publication/publication.docx  (recommandé)
        sortie/<project>/publication/publication.md    (recommandé)
        sortie/<project>/final/editorial_quality_report.md  (recommandé)

    Sortie :
        sortie/<project>/client/<project_name>_package.zip

    Retourne le Path du ZIP généré, ou None si le PDF est absent.
    """
    pub_dir   = _publication_dir(project_name)
    final_dir = _final_dir(project_name)
    client_dir = _client_dir(project_name)
    zip_out    = _zip_path(project_name)

    pdf_path        = pub_dir / "publication.pdf"
    docx_path       = pub_dir / "publication.docx"
    md_path         = pub_dir / "publication.md"
    sanitized_path  = pub_dir / "publication_sanitized.md"
    report_path     = final_dir / "editorial_quality_report.md"

    # ── Vérification PDF (obligatoire) ────────────────────────────────────────
    if not pdf_path.exists():
        msg = f"publication.pdf absent dans {pub_dir}"
        log_event({"stage": "client_package", "status": "error", "project": project_name, "message": msg})
        print(f"[client_package] ERREUR : {msg}")
        _update_state_error(project_name, msg)
        return None

    log_event({"stage": "client_package", "status": "start", "project": project_name, "message": "Création ZIP client"})
    print(f"[client_package] Création ZIP client — projet : {project_name}")
    print(f"[client_package] PDF trouvé : {pdf_path}")

    if docx_path.exists():
        print(f"[client_package] DOCX trouvé : {docx_path}")
    else:
        print(f"[client_package] DOCX absent (non bloquant) : {docx_path}")

    # Sélectionner la meilleure version MD pour le ZIP :
    # publication_sanitized.md est toujours préférée à publication.md
    if sanitized_path.exists():
        effective_md      = sanitized_path
        effective_md_name = "publication_sanitized.md"
        print(f"[client_package] MD sanitized utilisé : {sanitized_path}")
    elif md_path.exists():
        effective_md      = md_path
        effective_md_name = "publication.md"
        print(f"[client_package] MD (non sanitized) utilisé : {md_path}")
    else:
        effective_md      = md_path      # sera ignoré (n'existe pas)
        effective_md_name = "publication.md"
        print(f"[client_package] MD absent (non bloquant) : {md_path}")

    if report_path.exists():
        print(f"[client_package] Rapport qualité trouvé : {report_path}")
    else:
        print(f"[client_package] Rapport qualité absent (non bloquant) : {report_path}")

    # ── Création du dossier client ─────────────────────────────────────────────
    client_dir.mkdir(parents=True, exist_ok=True)

    # ── Lecture état projet ────────────────────────────────────────────────────
    state = load_project_state(project_name)

    # ── Candidats à inclure (ordre déterministe, PDF en premier) ──────────────
    candidates: list[tuple[Path, str]] = [
        (pdf_path,       "publication.pdf"),
        (docx_path,      "publication.docx"),
        (effective_md,   effective_md_name),
        (report_path,    "editorial_quality_report.md"),
    ]

    # ── project_summary.json ──────────────────────────────────────────────────
    # On calcule d'abord les noms de fichiers qui seront inclus
    included_names = [arc for src, arc in candidates if src.exists()]
    included_names.append("project_summary.json")

    summary = _build_project_summary(project_name, included_names, state)
    summary_content = json.dumps(summary, ensure_ascii=False, indent=2)

    # Écriture du fichier summary standalone dans client/
    summary_file = _summary_path(project_name)
    _write_project_summary(summary_file, summary)

    # ── Construction du ZIP ────────────────────────────────────────────────────
    try:
        included = _build_zip(zip_out, candidates, summary_content)
    except Exception as exc:
        msg = f"Erreur lors de la création du ZIP : {exc}"
        log_event({"stage": "client_package", "status": "error", "project": project_name, "message": msg})
        print(f"[client_package] ERREUR : {msg}")
        _update_state_error(project_name, str(exc))
        return None

    # ── Mise à jour project_state.json ─────────────────────────────────────────
    _update_state_success(project_name, zip_out, included)

    log_event({"stage": "client_package", "status": "done", "project": project_name, "message": f"ZIP généré : {zip_out}"})
    print(f"[client_package] ZIP généré : {zip_out}")

    return zip_out
