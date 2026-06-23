from pathlib import Path
from datetime import datetime
import hashlib

from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state
from app.publication_cleaner import clean_publication_markdown


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


def get_clean_document_path(project_name: str) -> Path:
    """Retourne le chemin de la version nettoyée du document final."""
    return get_final_dir(project_name) / "document_clean.md"


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


def _is_chunk_meaningful(content: str) -> bool:
    """
    Retourne True si le chunk contient du contenu réel (non vide après nettoyage).
    """
    cleaned = clean_publication_markdown(content)
    # Retire les titres et séparateurs pour estimer le contenu textuel
    import re
    body = re.sub(r"^#{1,6}\s.*$", "", cleaned, flags=re.MULTILINE)
    body = re.sub(r"^---\s*$", "", body, flags=re.MULTILINE)
    return len(body.strip()) >= 50


def build_final_document(project_name: str) -> Path | None:
    """
    Fusionne les chunks en deux documents :
    - document_final.md   : version interne complète (avec structure de chunks)
    - document_clean.md   : version nettoyée publiable (sans artefacts ni métadonnées)

    Priorité des sources par chunk :
      1. reviewed/chunk_XXX.md  (si existe)
      2. processed/chunk_XXX.md (sinon)

    Ne reconstruit pas si les fichiers effectivement utilisés n'ont pas changé.

    Raises:
        RuntimeError: si aucun chunk traité n'est disponible ou si des chunks
                      sont encore en attente/échec.
    """
    effective_chunks = list_effective_chunks(project_name)

    if not effective_chunks:
        raise RuntimeError(
            f"[final_document] ERREUR : aucun chunk traité disponible pour le projet "
            f"'{project_name}'. "
            "Le traitement IA a échoué en amont — vérifiez sortie/<projet>/errors/ "
            "pour les détails."
        )

    state = load_project_state(project_name)

    pending_chunks = [
        name
        for name, info in state.get("chunks", {}).items()
        if info.get("status") not in ("done",)
    ]

    if pending_chunks:
        failed = [
            name for name in pending_chunks
            if state["chunks"][name].get("status") == "failed"
        ]
        pending = [
            name for name in pending_chunks
            if state["chunks"][name].get("status") != "failed"
        ]

        parts = []
        if failed:
            parts.append(f"{len(failed)} chunk(s) en échec : {failed}")
        if pending:
            parts.append(f"{len(pending)} chunk(s) non traité(s) : {pending}")

        raise RuntimeError(
            f"[final_document] ERREUR : {'; '.join(parts)}. "
            "Corrigez les erreurs IA avant de relancer le pipeline."
        )

    final_dir = get_final_dir(project_name)
    final_dir.mkdir(parents=True, exist_ok=True)

    final_path = get_final_document_path(project_name)
    clean_path = get_clean_document_path(project_name)
    current_signature = compute_effective_signature(effective_chunks)

    if not should_rebuild_final_document(state, final_path, current_signature):
        print(f"Document final déjà à jour : {final_path}")
        return final_path

    generated_at = datetime.now().isoformat(timespec="seconds")

    reviewed_count = sum(1 for _, src in effective_chunks if src == "reviewed")
    processed_count = len(effective_chunks) - reviewed_count

    # ------------------------------------------------------------------
    # document_final.md — version interne (structure visible pour debug)
    # ------------------------------------------------------------------
    internal_parts: list[str] = []

    internal_parts.append(f"# Document final — {project_name}")
    internal_parts.append("")
    internal_parts.append(f"- Projet : `{project_name}`")
    internal_parts.append(f"- Généré le : `{generated_at}`")
    internal_parts.append(f"- Nombre de chunks fusionnés : `{len(effective_chunks)}`")
    if reviewed_count:
        internal_parts.append(f"- Chunks avec corrections appliquées : `{reviewed_count}`")
    if processed_count:
        internal_parts.append(f"- Chunks sans corrections : `{processed_count}`")
    internal_parts.append("")
    internal_parts.append("---")
    internal_parts.append("")

    # ------------------------------------------------------------------
    # document_clean.md — version publiable (sans métadonnées ni artefacts)
    # ------------------------------------------------------------------
    clean_parts: list[str] = []
    skipped_chunks: list[str] = []

    for index, (chunk_path, source) in enumerate(effective_chunks, start=1):
        raw_content = chunk_path.read_text(encoding="utf-8").strip()
        cleaned_content = clean_publication_markdown(raw_content)

        source_label = " *(révisé)*" if source == "reviewed" else ""

        # Version interne : conserver structure visible
        internal_parts.append(
            f"## Partie {index} — {chunk_path.name}{source_label}"
        )
        internal_parts.append("")
        internal_parts.append(raw_content)
        internal_parts.append("")
        internal_parts.append("---")
        internal_parts.append("")

        # Version publication : ignorer les chunks vides après nettoyage
        if not _is_chunk_meaningful(cleaned_content):
            skipped_chunks.append(chunk_path.name)
            print(
                f"[final_document] Chunk ignoré (vide après nettoyage) : "
                f"{chunk_path.name}"
            )
            continue

        clean_parts.append(cleaned_content)
        clean_parts.append("")

    final_path.write_text(
        "\n".join(internal_parts),
        encoding="utf-8",
    )

    clean_path.write_text(
        "\n\n".join(p for p in clean_parts if p.strip()),
        encoding="utf-8",
    )

    state["final_document"] = {
        "status": "generated",
        "path": str(final_path),
        "clean_path": str(clean_path),
        "generated_at": generated_at,
        "chunks_count": len(effective_chunks),
        "reviewed_chunks_count": reviewed_count,
        "skipped_chunks": skipped_chunks,
        "chunks_signature": current_signature,
    }

    save_project_state(project_name, state)

    print(f"Document final généré : {final_path}")
    print(f"Document clean généré  : {clean_path}")

    if skipped_chunks:
        print(
            f"[final_document] {len(skipped_chunks)} chunk(s) ignoré(s) "
            f"car vides : {skipped_chunks}"
        )

    return final_path
