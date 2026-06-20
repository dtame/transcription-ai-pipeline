from pathlib import Path

from app.project_manager import AudioProject
from app.logger import log_event


def merge_project_transcripts(project: AudioProject) -> Path | None:
    """
    Fusionne toutes les transcriptions .txt d'un projet dans l'ordre alphabétique.

    Entrée :
        sortie/nom_du_projet/transcripts/*.txt

    Sortie :
        sortie/nom_du_projet/merged/transcript_complet.txt
    """

    transcript_files = sorted(project.transcripts_dir.glob("*.txt"))

    if not transcript_files:
        log_event({
            "type": "merge",
            "project": project.name,
            "status": "skipped",
            "reason": "no_transcript_found"
        })
        return None

    project.merged_dir.mkdir(parents=True, exist_ok=True)

    output_file = project.merged_dir / "transcript_complet.txt"

    parts: list[str] = []

    for index, transcript_file in enumerate(transcript_files, start=1):
        content = transcript_file.read_text(encoding="utf-8").strip()

        if not content:
            log_event({
                "type": "merge",
                "project": project.name,
                "file": transcript_file.name,
                "status": "skipped",
                "reason": "empty_transcript"
            })
            continue

        section_title = (
            transcript_file.stem
            .replace("_", " ")
            .replace("-", " ")
        )

        parts.append(
            f"{'=' * 80}\n"
            f"PARTIE {index} — {section_title}\n"
            f"{'=' * 80}\n\n"
            f"{content}"
        )

    if not parts:
        log_event({
            "type": "merge",
            "project": project.name,
            "status": "skipped",
            "reason": "all_transcripts_empty"
        })
        return None

    merged_content = "\n\n".join(parts).strip()

    output_file.write_text(
        merged_content,
        encoding="utf-8"
    )

    log_event({
        "type": "merge",
        "project": project.name,
        "status": "completed",
        "output_file": str(output_file),
        "files_merged": len(parts)
    })

    return output_file