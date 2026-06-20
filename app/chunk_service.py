from pathlib import Path
from datetime import datetime


CHUNKS_DIR_NAME = "chunks"


def split_text_into_chunks(
    text: str,
    max_chars: int = 8000
) -> list[str]:
    paragraphs = text.split("\n\n")

    chunks = []
    current_chunk = ""

    for paragraph in paragraphs:
        paragraph = paragraph.strip()

        if not paragraph:
            continue

        if len(current_chunk) + len(paragraph) + 2 <= max_chars:
            current_chunk += paragraph + "\n\n"
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())

            current_chunk = paragraph + "\n\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def create_project_chunks(
    project,
    max_chars: int = 8000
) -> list[Path]:
    merged_transcript_path = (
        project.merged_dir /
        "transcript_complet.txt"
    )

    if not merged_transcript_path.exists():
        raise FileNotFoundError(
            f"Transcript fusionné introuvable : {merged_transcript_path}"
        )

    chunks_dir = project.output_dir / CHUNKS_DIR_NAME
    chunks_dir.mkdir(parents=True, exist_ok=True)

    text = merged_transcript_path.read_text(encoding="utf-8")

    chunks = split_text_into_chunks(
        text=text,
        max_chars=max_chars
    )

    chunk_paths = []

    for index, chunk in enumerate(chunks, start=1):
        chunk_path = chunks_dir / f"chunk_{index:03}.txt"

        header = (
            f"# Projet : {project.name}\n"
            f"# Chunk : {index:03}/{len(chunks):03}\n"
            f"# Généré le : {datetime.now().isoformat(timespec='seconds')}\n\n"
        )

        chunk_path.write_text(
            header + chunk,
            encoding="utf-8"
        )

        chunk_paths.append(chunk_path)

    return chunk_paths