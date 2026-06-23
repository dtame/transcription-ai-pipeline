"""
Génération du livrable client : NomProjet_CLIENT.zip

Contenu du ZIP :
    document_publication.pdf
    document_publication.docx
    report.json
    README_CLIENT.txt
    cover.jpg  (optionnel — uniquement si couverture réelle présente)

Emplacement de sortie :
    sortie/<project>/client/
        README_CLIENT.txt
        NomProjet_CLIENT.zip
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime
from pathlib import Path

from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state
from app.project_metadata import load_project_metadata


# ─────────────────────────────────────────────────────────────────────────────
# Chemins
# ─────────────────────────────────────────────────────────────────────────────

def _client_dir(project_name: str) -> Path:
    return SORTIE_DIR / project_name / "client"


def _final_dir(project_name: str) -> Path:
    return SORTIE_DIR / project_name / "final"


def _zip_path(project_name: str) -> Path:
    return _client_dir(project_name) / f"{project_name}_CLIENT.zip"


def _readme_path(project_name: str) -> Path:
    return _client_dir(project_name) / "README_CLIENT.txt"


# ─────────────────────────────────────────────────────────────────────────────
# Détermination de la couverture
# ─────────────────────────────────────────────────────────────────────────────

def _get_real_cover_path(project_name: str, state: dict) -> Path | None:
    """
    Retourne le chemin cover.jpg si une couverture réelle existe.

    Une couverture réelle est : image utilisateur, image générée, couverture
    typographique générée. Le provider "fake" et le type "none" sont exclus.
    """
    cover_state = state.get("cover", {})

    if not cover_state.get("generated", False):
        return None
    if cover_state.get("type", "none") == "none":
        return None
    if cover_state.get("provider", "") == "fake":
        return None

    cover_path_str = cover_state.get("path", "")
    if not cover_path_str:
        return None

    cover_path = Path(cover_path_str)
    if not cover_path.exists():
        # Essai relatif à SORTIE_DIR
        cover_path = SORTIE_DIR / project_name / "cover" / "cover.jpg"

    if cover_path.exists() and cover_path.stat().st_size > 100:
        return cover_path

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Signature de source
# ─────────────────────────────────────────────────────────────────────────────

def _file_md5(path: Path) -> str:
    """MD5 d'un fichier, chaîne vide si absent."""
    if not path.exists():
        return ""
    hasher = hashlib.md5()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _compute_source_signature(
    pdf_path: Path,
    docx_path: Path,
    report_path: Path,
    cover_path: Path | None,
) -> str:
    """MD5 combiné des fichiers sources du ZIP."""
    parts = [
        _file_md5(pdf_path),
        _file_md5(docx_path),
        _file_md5(report_path),
        _file_md5(cover_path) if cover_path else "",
    ]
    return hashlib.md5("|".join(parts).encode()).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# README_CLIENT.txt
# ─────────────────────────────────────────────────────────────────────────────

def build_client_readme(project_name: str, include_cover: bool = False) -> str:
    """Construit le contenu de README_CLIENT.txt à partir des métadonnées."""
    meta = load_project_metadata(project_name)

    title        = meta.get("title", project_name)
    author       = meta.get("author", "")
    organization = meta.get("organization", "")
    doc_type     = meta.get("document_type", "")
    template     = meta.get("template", "")
    date         = meta.get("date", datetime.now().strftime("%Y-%m-%d"))
    version      = meta.get("version", "1.0")

    files_list = (
        "- document_publication.pdf\n"
        "- document_publication.docx\n"
        "- report.json\n"
        "- README_CLIENT.txt"
    )
    if include_cover:
        files_list += "\n- cover.jpg"

    lines = [
        f"Projet : {title}",
        "",
        f"Auteur : {author}",
        "",
        f"Organisation : {organization}",
        "",
        f"Type de document : {doc_type}",
        "",
        f"Template : {template}",
        "",
        f"Date de génération : {date}",
        "",
        f"Version : {version}",
        "",
        "Fichiers inclus :",
        "",
        files_list,
        "",
        "Document généré automatiquement par TranscriptionAI.",
    ]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Création du ZIP
# ─────────────────────────────────────────────────────────────────────────────

def _build_zip(
    zip_out: Path,
    pdf_path: Path,
    docx_path: Path,
    report_path: Path,
    readme_content: str,
    cover_path: Path | None,
) -> list[str]:
    """
    Crée le ZIP client.  Retourne la liste des noms de fichiers inclus.
    """
    included: list[str] = []

    with zipfile.ZipFile(zip_out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(pdf_path,    "document_publication.pdf")
        included.append("document_publication.pdf")

        zf.write(docx_path,   "document_publication.docx")
        included.append("document_publication.docx")

        zf.write(report_path, "report.json")
        included.append("report.json")

        zf.writestr("README_CLIENT.txt", readme_content.encode("utf-8"))
        included.append("README_CLIENT.txt")

        if cover_path is not None:
            zf.write(cover_path, "cover.jpg")
            included.append("cover.jpg")

    return included


# ─────────────────────────────────────────────────────────────────────────────
# Mise à jour de project_state.json
# ─────────────────────────────────────────────────────────────────────────────

def _update_project_state(
    project_name: str,
    zip_out: Path,
    signature: str,
) -> None:
    state = load_project_state(project_name)
    state["client_export"] = {
        "generated":        True,
        "path":             str(zip_out),
        "updated_at":       datetime.now().isoformat(timespec="seconds"),
        "source_signature": signature,
    }
    save_project_state(project_name, state)


# ─────────────────────────────────────────────────────────────────────────────
# Fonction principale
# ─────────────────────────────────────────────────────────────────────────────

def export_client_zip(project_name: str, force: bool = False) -> Path | None:
    """
    Génère le ZIP client pour un projet.

    Retourne le Path vers le ZIP généré, ou None en cas d'échec.
    Utilise un cache basé sur la signature des fichiers sources.
    """
    final_dir   = _final_dir(project_name)
    pdf_path    = final_dir / "document_publication.pdf"
    docx_path   = final_dir / "document_publication.docx"
    report_path = SORTIE_DIR / project_name / "report.json"
    client_dir  = _client_dir(project_name)
    zip_out     = _zip_path(project_name)

    # ── Vérifications préalables ──────────────────────────────────────────────
    missing = []
    if not pdf_path.exists():
        missing.append("document_publication.pdf")
    if not docx_path.exists():
        missing.append("document_publication.docx")

    if missing:
        for m in missing:
            print(f"[client_export] MANQUANT : {m}")
        raise RuntimeError(
            f"[client_export] Fichiers manquants pour le projet '{project_name}' : "
            f"{', '.join(missing)}. "
            "Assurez-vous que les étapes publication_docx et publication_pdf ont réussi."
        )

    # ── Couverture ────────────────────────────────────────────────────────────
    state       = load_project_state(project_name)
    cover_path  = _get_real_cover_path(project_name, state)

    # ── Signature + cache ─────────────────────────────────────────────────────
    signature = _compute_source_signature(pdf_path, docx_path, report_path, cover_path)

    if not force and zip_out.exists():
        cached_sig = state.get("client_export", {}).get("source_signature", "")
        if cached_sig == signature:
            print(f"[client_export] À jour, pas de reconstruction : {zip_out.name}")
            return zip_out

    # ── Création du dossier client ────────────────────────────────────────────
    client_dir.mkdir(parents=True, exist_ok=True)

    # ── README_CLIENT.txt ─────────────────────────────────────────────────────
    include_cover = cover_path is not None
    readme_content = build_client_readme(project_name, include_cover=include_cover)
    readme_out = _readme_path(project_name)
    readme_out.write_text(readme_content, encoding="utf-8")

    # ── ZIP ───────────────────────────────────────────────────────────────────
    # Écriture atomique : on écrit d'abord dans un fichier temporaire
    zip_tmp = zip_out.with_suffix(".tmp")
    try:
        included = _build_zip(
            zip_tmp,
            pdf_path,
            docx_path,
            report_path,
            readme_content,
            cover_path,
        )
    except Exception as exc:
        print(f"[client_export] ERREUR création ZIP : {exc}")
        zip_tmp.unlink(missing_ok=True)
        return None

    # Remplacement atomique
    if zip_out.exists():
        zip_out.unlink()
    zip_tmp.rename(zip_out)

    # ── Mise à jour project_state.json ────────────────────────────────────────
    _update_project_state(project_name, zip_out, signature)

    # ── Mise à jour report.json ───────────────────────────────────────────────
    _update_report(project_name, zip_out, included)

    print(f"[client_export] ZIP généré : {zip_out}")
    return zip_out


# ─────────────────────────────────────────────────────────────────────────────
# Mise à jour de report.json
# ─────────────────────────────────────────────────────────────────────────────

def _update_report(
    project_name: str,
    zip_out: Path,
    included_files: list[str],
) -> None:
    """Injecte la section client_export dans report.json si présent."""
    report_path = SORTIE_DIR / project_name / "report.json"
    if not report_path.exists():
        return

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["client_export"] = {
            "generated": True,
            "path":      str(zip_out),
            "files":     included_files,
        }
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[client_export] Impossible de mettre à jour report.json : {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Utilitaires Streamlit
# ─────────────────────────────────────────────────────────────────────────────

def get_client_export_info(project_name: str) -> dict:
    """
    Retourne les informations sur le ZIP client généré.

    Clés :
        exists          bool
        zip_path        Path | None
        zip_name        str
        size_bytes      int
        size_human      str
        generated_at    str
        files_count     int
        files           list[str]
        readme_path     Path | None
    """
    zip_out     = _zip_path(project_name)
    readme_out  = _readme_path(project_name)
    state       = load_project_state(project_name)
    ce_state    = state.get("client_export", {})

    files: list[str] = []
    if zip_out.exists():
        try:
            with zipfile.ZipFile(zip_out, "r") as zf:
                files = zf.namelist()
        except Exception:
            pass

    size_bytes = zip_out.stat().st_size if zip_out.exists() else 0
    size_human = _human_size(size_bytes)

    return {
        "exists":       zip_out.exists(),
        "zip_path":     zip_out if zip_out.exists() else None,
        "zip_name":     zip_out.name,
        "size_bytes":   size_bytes,
        "size_human":   size_human,
        "generated_at": ce_state.get("updated_at", ""),
        "files_count":  len(files),
        "files":        files,
        "readme_path":  readme_out if readme_out.exists() else None,
    }


def _human_size(size_bytes: int) -> str:
    for unit in ("o", "Ko", "Mo", "Go"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} To"
