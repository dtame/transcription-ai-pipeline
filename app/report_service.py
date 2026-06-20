from pathlib import Path
from datetime import datetime
import json

from app.paths import SORTIE_DIR
from app.project_state import load_project_state


def _build_publication_report(publication_state: dict) -> dict:
    """Construit la section publication du rapport."""
    md_state = publication_state.get("markdown", {})
    docx_state = publication_state.get("docx", {})
    pdf_state = publication_state.get("pdf", {})

    settings = md_state.get("settings", {})

    return {
        "document_type": settings.get("document_type", ""),
        "template": settings.get("template", ""),
        "theme": settings.get("theme", ""),
        "page_size": settings.get("page_size", ""),
        "font_style": settings.get("font_style", ""),
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


def build_project_report(project_name: str) -> Path:
    state = load_project_state(project_name)

    report_dir = SORTIE_DIR / project_name
    report_path = report_dir / "report.json"

    files_state = state.get("files", {})
    chunks_state = state.get("chunks", {})
    final_state = state.get("final_document", {})
    exports_state = state.get("exports", {})
    publication_state = state.get("publication", {})

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