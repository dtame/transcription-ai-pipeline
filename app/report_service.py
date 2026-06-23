from pathlib import Path
from datetime import datetime
import json

from app.paths import SORTIE_DIR
from app.project_state import load_project_state
from app.project_metadata import load_project_metadata


def _build_publication_report(publication_state: dict) -> dict:
    """Construit la section publication du rapport."""
    md_state = publication_state.get("markdown", {})
    docx_state = publication_state.get("docx", {})
    pdf_state = publication_state.get("pdf", {})
    toc_state = publication_state.get("toc", {})

    settings = md_state.get("settings", {})

    return {
        "document_type": settings.get("document_type", ""),
        "template": settings.get("template", ""),
        "theme": settings.get("theme", ""),
        "page_size": settings.get("page_size", ""),
        "font_style": settings.get("font_style", ""),

        "metadata": {
            "title": settings.get("title", ""),
            "subtitle": settings.get("subtitle", ""),
            "author": settings.get("author", ""),
            "organization": settings.get("organization", ""),
            "language": settings.get("language", ""),
            "date": settings.get("date", ""),
            "version": settings.get("version", ""),
        },

        "toc": {
            "enabled": settings.get("include_toc", True),
            "headings_count": toc_state.get("headings_count", 0),
        },

        "markdown": {
            "generated": md_state.get("generated", False),
            "path": md_state.get("path"),
            "updated_at": md_state.get("updated_at"),
        },
        "docx": {
            "generated": docx_state.get("generated", False),
            "path": docx_state.get("path"),
            "updated_at": docx_state.get("updated_at"),
        },
        "pdf": {
            "generated": pdf_state.get("generated", False),
            "path": pdf_state.get("path"),
            "updated_at": pdf_state.get("updated_at"),
        },
    }


def _build_cover_report(cover_state: dict) -> dict:
    """Construit la section cover du rapport."""
    cover_path = cover_state.get("path")
    return {
        "present":           bool(cover_path),
        "generated":         cover_state.get("generated", False),
        "provider":          cover_state.get("provider", ""),
        "style":             cover_state.get("style", ""),
        "type":              cover_state.get("type", ""),
        "source":            cover_state.get("source", ""),
        "path":              cover_path,
        "inserted_into_pdf": cover_state.get("inserted_into_pdf", False),
        "inserted_into_docx": cover_state.get("inserted_into_docx", False),
        "pdf_ready":         cover_state.get("pdf_ready", False),
        "docx_ready":        cover_state.get("docx_ready", False),
        "updated_at":        cover_state.get("updated_at"),
    }


def build_project_report(project_name: str) -> Path:
    state = load_project_state(project_name)

    report_dir = SORTIE_DIR / project_name
    report_path = report_dir / "report.json"

    files_state = state.get("files", {})
    chunks_state = state.get("chunks", {})
    final_state = state.get("final_document", {})
    exports_state = state.get("exports", {})
    publication_state = state.get("publication", {})
    harmonization_state = state.get("harmonization", {})
    cover_state = state.get("cover", {})
    client_export_state = state.get("client_export", {})
    quality_state = publication_state.get("quality", {})

    # Métadonnées actuelles depuis project.yaml (source de vérité)
    try:
        _current_meta = load_project_metadata(project_name)
    except Exception:
        _current_meta = {}

    audio_total = len(files_state)

    audio_transcribed = sum(
        1
        for info in files_state.values()
        if info.get("status") == "transcribed"
    )

    audio_error = sum(
        1
        for info in files_state.values()
        if info.get("status") == "error"
    )

    audio_pending = (
        audio_total
        - audio_transcribed
        - audio_error
    )

    chunks_total = len(chunks_state)

    chunks_processed = sum(
        1
        for info in chunks_state.values()
        if info.get("status") == "done"
    )

    chunks_pending = (
        chunks_total
        - chunks_processed
    )

    report = {
        "project": project_name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),

        "metadata": {
            "title":         _current_meta.get("title", ""),
            "subtitle":      _current_meta.get("subtitle", ""),
            "author":        _current_meta.get("author", ""),
            "organization":  _current_meta.get("organization", ""),
            "language":      _current_meta.get("language", ""),
            "date":          _current_meta.get("date", ""),
            "version":       _current_meta.get("version", ""),
            "document_type": _current_meta.get("document_type", ""),
            "template":      _current_meta.get("template", ""),
            "theme":         _current_meta.get("theme", ""),
        },

        "audio": {
            "total": audio_total,
            "transcribed": audio_transcribed,
            "pending": audio_pending,
            "error": audio_error
        },

        "chunks": {
            "total": chunks_total,
            "processed": chunks_processed,
            "pending": chunks_pending
        },

        "final_document": {
            "generated": (
                final_state.get("status")
                == "generated"
            ),
            "path": final_state.get("path")
        },

        "exports": {
            "docx": {
                "generated": exports_state.get("docx", {}).get("generated", False),
                "path": exports_state.get("docx", {}).get("path"),
                "updated_at": exports_state.get("docx", {}).get("updated_at"),
            },
            "pdf": {
                "generated": exports_state.get("pdf", {}).get("generated", False),
                "path": exports_state.get("pdf", {}).get("path"),
                "updated_at": exports_state.get("pdf", {}).get("updated_at"),
            },
        },

        "publication": _build_publication_report(publication_state),

        "cover": _build_cover_report(cover_state),

        "harmonization": {
            "enabled": harmonization_state.get("enabled", False),
            "mode": harmonization_state.get("mode", ""),
            "generated": harmonization_state.get("generated", False),
            "path": harmonization_state.get("path"),
            "updated_at": harmonization_state.get("updated_at"),
        },

        "client_export": {
            "generated": client_export_state.get("generated", False),
            "path":      client_export_state.get("path"),
            "updated_at": client_export_state.get("updated_at"),
        },

        "publication_quality": {
            "status":   quality_state.get("status", "not_validated"),
            "errors":   quality_state.get("errors", []),
            "warnings": quality_state.get("warnings", []),
        },
    }

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(f"Rapport généré : {report_path}")

    return report_path
