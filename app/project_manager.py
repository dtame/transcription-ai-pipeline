from dataclasses import dataclass
from pathlib import Path

from app.config import SUPPORTED_EXTENSIONS
from app.file_utils import sanitize_name
from app.paths import DEPOT_DIR, SORTIE_DIR, TEMP_DIR, ARCHIVES_DIR, REJETS_DIR


@dataclass
class AudioProject:
    name: str
    source_dir: Path
    audio_files: list[Path]
    output_dir: Path
    transcripts_dir: Path
    merged_dir: Path
    book_dir: Path
    pdf_dir: Path
    temp_dir: Path
    archives_dir: Path
    rejects_dir: Path


def discover_projects() -> list[AudioProject]:
    """
    Détecte les projets dans le dossier depot.

    Deux cas supportés :
    1. depot/audio.mp3
       => projet automatique nommé "default"

    2. depot/nom_du_projet/01_intro.mp3
       depot/nom_du_projet/02_suite.mp3
       => projet nommé "nom_du_projet"
    """

    DEPOT_DIR.mkdir(exist_ok=True)

    projects: list[AudioProject] = []

    root_audio_files = sorted(
        file
        for file in DEPOT_DIR.iterdir()
        if file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if root_audio_files:
        projects.append(
            create_project(
                project_name="default",
                source_dir=DEPOT_DIR,
                audio_files=root_audio_files,
            )
        )

    for directory in sorted(DEPOT_DIR.iterdir()):
        if not directory.is_dir():
            continue

        audio_files = sorted(
            file
            for file in directory.iterdir()
            if file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS
        )

        if not audio_files:
            continue

        projects.append(
            create_project(
                project_name=directory.name,
                source_dir=directory,
                audio_files=audio_files,
            )
        )

    return projects


def create_project(
    project_name: str,
    source_dir: Path,
    audio_files: list[Path],
) -> AudioProject:
    safe_name = sanitize_name(project_name)

    output_dir = SORTIE_DIR / safe_name

    project = AudioProject(
        name=safe_name,
        source_dir=source_dir,
        audio_files=sorted(audio_files),
        output_dir=output_dir,
        transcripts_dir=output_dir / "transcripts",
        merged_dir=output_dir / "merged",
        book_dir=output_dir / "book",
        pdf_dir=output_dir / "pdf",
        temp_dir=TEMP_DIR / safe_name,
        archives_dir=ARCHIVES_DIR / safe_name,
        rejects_dir=REJETS_DIR / safe_name,
    )

    ensure_project_directories(project)

    return project


def ensure_project_directories(project: AudioProject) -> None:
    directories = [
        project.output_dir,
        project.transcripts_dir,
        project.merged_dir,
        project.book_dir,
        project.pdf_dir,
        project.temp_dir,
        project.archives_dir,
        project.rejects_dir,
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)