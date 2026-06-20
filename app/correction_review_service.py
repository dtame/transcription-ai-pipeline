"""
Génération automatique des fichiers de correction pour la révision humaine.

Pour chaque chunk traité (processed/chunk_XXX.md), ce module :
  1. Lit le chunk source (chunks/chunk_XXX.txt) pour extraire les segments
     avec leurs timestamps.
  2. Génère un fichier corrections/chunk_XXX.corrections.md contenant
     un bloc de correction par segment.
  3. N'écrase jamais un fichier existant (reprise après interruption).
  4. Met à jour la section "corrections" de project_state.json.

Format d'un segment source attendu :
    [HH:MM -> HH:MM] Texte du segment.
ou  [HH:MM:SS -> HH:MM:SS] Texte du segment.
"""

import re
from pathlib import Path
from datetime import datetime

from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state


# Regex : capture le timestamp de début, de fin et le texte
_SEGMENT_RE = re.compile(
    r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\s*->\s*(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.+)$"
)


def _parse_segments(chunk_txt_path: Path) -> list[dict]:
    """
    Extrait la liste des segments d'un fichier chunk source.

    Retourne une liste de dicts :
        {"start": "00:09", "end": "00:23", "text": "..."}
    """
    segments = []
    for line in chunk_txt_path.read_text(encoding="utf-8").splitlines():
        match = _SEGMENT_RE.match(line.strip())
        if match:
            segments.append({
                "start": match.group(1),
                "end": match.group(2),
                "text": match.group(3).strip(),
            })
    return segments


def _build_correction_file_content(chunk_name: str, segments: list[dict]) -> str:
    """
    Construit le contenu Markdown du fichier de corrections.
    """
    base_name = chunk_name.replace(".corrections.md", "").replace(".md", "")

    lines = [
        f"# Corrections du {base_name}",
        "",
        "Document généré automatiquement.",
        "",
        "Compléter uniquement les sections nécessaires.",
        "Les sections laissées vides seront ignorées.",
        "",
    ]

    for index, seg in enumerate(segments, start=1):
        lines += [
            "---",
            "",
            f"## Correction {index}",
            "",
            "### Timestamp",
            "",
            f"{seg['start']} → {seg['end']}",
            "",
            "### Texte actuel",
            "",
            seg["text"],
            "",
            "### Texte corrigé",
            "",
            "[À COMPLÉTER]",
            "",
        ]

    return "\n".join(lines)


def generate_review_files(project) -> None:
    """
    Génère les fichiers de correction pour tous les chunks traités du projet.

    - Lit sortie/<projet>/chunks/chunk_XXX.txt  (segments source)
    - Écrit sortie/<projet>/corrections/chunk_XXX.corrections.md
    - Ignore les fichiers déjà existants
    - Met à jour project_state.json (section "corrections")

    Args:
        project: objet projet avec attribut .name (str ou Path)
    """
    project_name = project.name if hasattr(project, "name") else str(project)

    project_output_dir = SORTIE_DIR / project_name
    chunks_dir = project_output_dir / "chunks"
    corrections_dir = project_output_dir / "corrections"

    corrections_dir.mkdir(parents=True, exist_ok=True)

    state = load_project_state(project_name)
    chunks_state = state.get("chunks", {})

    if not chunks_state:
        print(f"Aucun chunk enregistré pour le projet : {project_name}")
        return

    if "corrections" not in state:
        state["corrections"] = {}

    any_change = False

    for chunk_name, chunk_info in chunks_state.items():
        if chunk_info.get("status") != "done":
            continue

        # chunk_001.txt  →  chunk_001.corrections.md
        base = chunk_name.replace(".txt", "")
        correction_filename = f"{base}.corrections.md"
        correction_path = corrections_dir / correction_filename

        if correction_path.exists():
            print(f"Fichier de correction déjà présent, ignoré : {correction_filename}")
            if chunk_name not in state["corrections"]:
                state["corrections"][chunk_name] = {
                    "status": "generated",
                    "path": str(correction_path),
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                }
                any_change = True
            continue

        chunk_txt_path = chunks_dir / chunk_name
        if not chunk_txt_path.exists():
            print(f"Chunk source introuvable, ignoré : {chunk_txt_path}")
            continue

        segments = _parse_segments(chunk_txt_path)

        if not segments:
            print(f"Aucun segment détecté dans {chunk_name}, fichier de correction vide généré.")

        content = _build_correction_file_content(base, segments)
        correction_path.write_text(content, encoding="utf-8")

        state["corrections"][chunk_name] = {
            "status": "generated",
            "path": str(correction_path),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

        any_change = True
        print(f"Fichier de correction généré : {correction_path}")

    if any_change:
        save_project_state(project_name, state)
