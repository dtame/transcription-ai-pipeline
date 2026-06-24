"""
Editorial Finalizer — Génère un manuscrit éditorial propre à partir
des chunks déjà traités par l'IA (dossier processed/).

Pipeline en 5 étapes :
  A. Lecture des chunks traités (processed/chunk_*.md)
  B. Nettoyage éditorial (suppression artefacts IA, timestamps, etc.)
  C. Construction de la structure éditoriale (sans IA)
  D. Génération de manuscript_structured.md
  E. Transformation éditoriale fidèle → manuscript_rewritten.md

Ne relance PAS :
  - la transcription
  - la fusion audio
  - la création des chunks
  - le traitement IA initial des chunks
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.document_language import get_document_language, get_language_labels, save_document_language
from app.editorial_cleanup import clean_editorial_artifacts
from app.editorial_structure import generate_structured_manuscript, render_structured_manuscript
from app.editorial_transformer import transform_editorial_manuscript
from app.logger import log_event
from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state


# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------

def list_processed_chunks(project_name: str) -> list[Path]:
    """
    Retourne la liste triée des fichiers processed/chunk_*.md pour un projet.
    La liste est vide si le dossier n'existe pas ou ne contient aucun chunk.
    """
    processed_dir = SORTIE_DIR / project_name / "processed"
    if not processed_dir.is_dir():
        return []
    return sorted(processed_dir.glob("chunk_*.md"))


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def generate_editorial_manuscript(project_name: str) -> Path | None:
    """
    Génère le manuscrit éditorial final à partir des chunks déjà traités.

    Étapes :
      A. Lecture des chunks (processed/chunk_*.md)
      B. Nettoyage éditorial (clean_editorial_artifacts)
      C. Construction de la structure éditoriale (editorial_structure)
      D. Écriture de manuscript_structured.md

    Retourne le chemin de manuscript_structured.md, ou None en cas d'erreur.
    """
    print(f"[editorial_finalizer] Début — projet : {project_name}")
    log_event({
        "step": "editorial_finalizer",
        "project": project_name,
        "action": "start",
        "message": f"Début génération manuscrit éditorial pour {project_name}",
    })

    state = load_project_state(project_name)
    now_iso = datetime.now().isoformat(timespec="seconds")

    try:
        # ── Étape A : Lire les chunks traités ─────────────────────────────
        chunks = list_processed_chunks(project_name)
        print(f"[editorial_finalizer] Étape A — {len(chunks)} fichier(s) processed trouvé(s)")

        if not chunks:
            msg = (
                f"Aucun chunk traité trouvé dans "
                f"sortie/{project_name}/processed/. "
                "Lancez d'abord le traitement IA des chunks."
            )
            print(f"[editorial_finalizer] ERREUR : {msg}")
            log_event({
                "step": "editorial_finalizer",
                "project": project_name,
                "action": "error",
                "message": msg,
            })
            state["editorial"] = {
                "manuscript_generated": False,
                "structure_built": False,
                "error": msg,
                "generated_at": now_iso,
            }
            save_project_state(project_name, state)
            return None

        # ── Étape B : Lire les textes bruts des chunks ────────────────────
        print("[editorial_finalizer] Étape B — Lecture et nettoyage des chunks")
        raw_chunks: list[str] = [
            chunk_path.read_text(encoding="utf-8")
            for chunk_path in chunks
        ]

        # Nettoyage préalable pour le manuscript.md de compatibilité
        cleaned_parts: list[str] = []
        for raw in raw_chunks:
            cleaned = clean_editorial_artifacts(raw, remove_timestamps=True).strip()
            if cleaned:
                cleaned_parts.append(cleaned)

        # ── Détection de la langue documentaire ───────────────────────────
        full_cleaned_text = "\n\n".join(cleaned_parts)
        document_language = get_document_language(
            project_name, fallback_text=full_cleaned_text
        )
        save_document_language(project_name, document_language, source="dominant_text")
        log_event({
            "step": "editorial_finalizer",
            "project": project_name,
            "action": "language_detected",
            "document_language": document_language,
            "source": "dominant_text",
        })
        print(
            f"[editorial_finalizer] Langue documentaire : {document_language} "
            f"(source=dominant_text)"
        )

        # ── Compatibilité : conserver manuscript.md ───────────────────────
        final_dir = SORTIE_DIR / project_name / "final"
        final_dir.mkdir(parents=True, exist_ok=True)

        manuscript_path = final_dir / "manuscript.md"
        labels = get_language_labels(document_language)
        header = f"# {labels['manuscript']}\n\n---\n"
        body = full_cleaned_text
        manuscript_path.write_text(header + "\n" + body + "\n", encoding="utf-8")
        print(f"[editorial_finalizer] manuscript.md conservé : {manuscript_path}")

        # ── Étape C : Construction de la structure éditoriale ─────────────
        print("[editorial_finalizer] Étape C — Construction structure éditoriale")
        structure, rendered_md = generate_structured_manuscript(
            project_name=project_name,
            chunks_texts=raw_chunks,
            document_language=document_language,
        )
        print(f"[editorial_finalizer] Nombre de sections créées : {len(structure.sections)}")
        print(f"[editorial_finalizer] Titre détecté : {structure.title}")

        # ── Étape D : Écriture de manuscript_structured.md ────────────────
        print("[editorial_finalizer] Étape D — Génération manuscript_structured.md")
        structured_path = final_dir / "manuscript_structured.md"
        structured_path.write_text(rendered_md, encoding="utf-8")
        print(f"[editorial_finalizer] Fichier généré : {structured_path}")

        log_event({
            "step": "editorial_finalizer",
            "project": project_name,
            "action": "success",
            "message": f"Manuscrit structuré généré : {structured_path}",
            "chunks_count": len(chunks),
            "sections_count": len(structure.sections),
            "title": structure.title,
        })

        # ── Mise à jour de project_state.json ────────────────────────────
        state["editorial"] = {
            "manuscript_generated": True,
            "manuscript_path": str(manuscript_path),
            "structure_built": True,
            "structured_manuscript_path": str(structured_path),
            "structure_title": structure.title,
            "structure_sections_count": len(structure.sections),
            "generated_at": now_iso,
            "source": "processed_chunks",
            "chunks_count": len(chunks),
            "cleanup_done": True,
            "document_language": document_language,
        }
        state["language"] = {
            "document_language": document_language,
            "source": "dominant_text",
        }
        save_project_state(project_name, state)

        # ── Étape E : Transformation éditoriale fidèle ────────────────────
        print("[editorial_finalizer] Étape E — Transformation éditoriale fidèle")
        rewritten_path = transform_editorial_manuscript(project_name)
        if rewritten_path:
            print(f"[editorial_finalizer] Manuscrit transformé : {rewritten_path}")
        else:
            print(
                "[editorial_finalizer] Avertissement : la transformation éditoriale "
                "a échoué — manuscript_structured.md reste disponible."
            )

        return structured_path

    except Exception as exc:
        err_msg = str(exc)
        print(f"[editorial_finalizer] ERREUR inattendue : {err_msg}")
        log_event({
            "step": "editorial_finalizer",
            "project": project_name,
            "action": "error",
            "message": err_msg,
        })
        state["editorial"] = {
            "manuscript_generated": False,
            "structure_built": False,
            "error": err_msg,
            "generated_at": now_iso,
        }
        save_project_state(project_name, state)
        return None
