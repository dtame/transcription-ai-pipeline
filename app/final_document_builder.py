from pathlib import Path
from datetime import datetime
import hashlib

from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state


def file_hash(path: Path) -> str:
    hasher = hashlib.md5()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            hasher.update(block)
    return hasher.hexdigest()


def get_processed_dir(project_name: str) -> Path:
    return SORTIE_DIR / project_name / "processed"


def get_reviewed_dir(project_name: str) -> Path:
    return SORTIE_DIR / project_name / "reviewed"


def get_final_dir(project_name: str) -> Path:
    return SORTIE_DIR / project_name / "final"


def get_final_document_path(project_name: str) -> Path:
    return get_final_dir(project_name) / "document_final.md"


def list_processed_chunks(project_name: str) -> list[Path]:
    """Retourne les fichiers processed/chunk_*.md triés par nom."""
    processed_dir = get_processed_dir(project_name)

    if not processed_dir.exists():
        return []

    return sorted(
        processed_dir.glob("chunk_*.md"),
        key=lambda p: p.name,
    )


def list_effective_chunks(project_name: str) -> list[tuple[Path, str]]:
    """
    Retourne la liste des chunks à utiliser pour la fusion finale,
    en priorisant reviewed/ sur processed/.

    Returns:
        Liste de tuples (path, source) où source vaut "reviewed" ou "processed".
    """
    processed_dir = get_processed_dir(project_name)
    reviewed_dir = get_reviewed_dir(project_name)

    if not processed_dir.exists():
        return []

    effective: list[tuple[Path, str]] = []

    for processed_path in sorted(processed_dir.glob("chunk_*.md"), key=lambda p: p.name):
        reviewed_path = reviewed_dir / processed_path.name
        if reviewed_path.exists():
            effective.append((reviewed_path, "reviewed"))
        else:
            effective.append((processed_path, "processed"))

    return effective


def compute_chunks_signature(chunk_files: list[Path]) -> dict:
    return {
        chunk.name: file_hash(chunk)
        for chunk in chunk_files
    }


def compute_effective_signature(effective_chunks: list[tuple[Path, str]]) -> dict:
    """
    Calcule la signature à partir des fichiers effectivement utilisés
    (reviewed en priorité, processed sinon).
    La clé inclut la source pour détecter les changements de priorité.
    """
    return {
        f"{source}/{path.name}": file_hash(path)
        for path, source in effective_chunks
    }


def should_rebuild_final_document(
    state: dict,
    final_path: Path,
    current_signature: dict,
) -> bool:
    final_state = state.get("final_document")

    if not final_path.exists():
        return True

    if not final_state:
        return True

    if final_state.get("status") != "generated":
        return True

    previous_signature = final_state.get("chunks_signature", {})

    if previous_signature != current_signature:
        return True

    return False


def build_final_document(project_name: str) -> Path | None:
    """
    Fusionne les chunks dans un document final.

    Priorité des sources par chunk :
      1. reviewed/chunk_XXX.md  (si existe)
      2. processed/chunk_XXX.md (sinon)

    Ne reconstruit pas si les fichiers effectivement utilisés n'ont pas changé.
    """
    effective_chunks = list_effective_chunks(project_name)

    if not effective_chunks:
        print(f"Aucun fichier processed/*.md trouvé pour le projet : {project_name}")
        return None

    state = load_project_state(project_name)

    pending_chunks = [
        name
        for name, info in state.get("chunks", {}).items()
        if info.get("status") != "done"
    ]

    if pending_chunks:
        print(
            f"Document final non généré : "
            f"{len(pending_chunks)} chunk(s) non terminé(s)."
        )
        return None

    final_dir = get_final_dir(project_name)
    final_dir.mkdir(parents=True, exist_ok=True)

    final_path = get_final_document_path(project_name)
    current_signature = compute_effective_signature(effective_chunks)

    if not should_rebuild_final_document(state, final_path, current_signature):
        print(f"Document final déjà à jour : {final_path}")
        return final_path

    generated_at = datetime.now().isoformat(timespec="seconds")

    reviewed_count = sum(1 for _, src in effective_chunks if src == "reviewed")
    processed_count = len(effective_chunks) - reviewed_count

    content_parts: list[str] = []

    content_parts.append(f"# Document final — {project_name}")
    content_parts.append("")
    content_parts.append(f"- Projet : `{project_name}`")
    content_parts.append(f"- Généré le : `{generated_at}`")
    content_parts.append(f"- Nombre de chunks fusionnés : `{len(effective_chunks)}`")
    if reviewed_count:
        content_parts.append(f"- Chunks avec corrections appliquées : `{reviewed_count}`")
    if processed_count:
        content_parts.append(f"- Chunks sans corrections : `{processed_count}`")
    content_parts.append("")
    content_parts.append("---")
    content_parts.append("")

    for index, (chunk_path, source) in enumerate(effective_chunks, start=1):
        source_label = " *(révisé)*" if source == "reviewed" else ""
        content_parts.append(
            f"## Partie {index} — {chunk_path.name}{source_label}"
        )
        content_parts.append("")
        content_parts.append(chunk_path.read_text(encoding="utf-8").strip())
        content_parts.append("")
        content_parts.append("---")
        content_parts.append("")

    final_path.write_text(
        "\n".join(content_parts),
        encoding="utf-8",
    )

    state["final_document"] = {
        "status": "generated",
        "path": str(final_path),
        "generated_at": generated_at,
        "chunks_count": len(effective_chunks),
        "reviewed_chunks_count": reviewed_count,
        "chunks_signature": current_signature,
    }

    save_project_state(project_name, state)

    print(f"Document final généré : {final_path}")

    return final_path
