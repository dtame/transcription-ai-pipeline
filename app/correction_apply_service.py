"""
Application automatique des corrections humaines.

Pour chaque chunk traité (processed/chunk_XXX.md) :
  1. Lit le fichier corrections/chunk_XXX.corrections.md
  2. Parse les blocs de correction valides (Texte corrigé non vide / non [À COMPLÉTER])
  3. Applique les remplacements dans le contenu du fichier processed (première occurrence)
  4. Génère reviewed/chunk_XXX.md
  5. Met à jour project_state.json (section "corrections")

Ne modifie jamais :
  - processed/*.md
  - corrections/*.corrections.md

Reprise après interruption :
  - Si reviewed/chunk_XXX.md existe et est plus récent que les sources, ignoré.
"""

import re
from pathlib import Path
from datetime import datetime

from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state


def _parse_corrections(corrections_path: Path) -> tuple[list[dict], int]:
    """
    Parse les blocs de correction d'un fichier .corrections.md.

    Retourne :
        (corrections_valides, total_blocks)

    corrections_valides : liste de dicts {"index": int, "current": str, "corrected": str}
    total_blocks        : nombre total de blocs ## Correction trouvés dans le fichier
    """
    content = corrections_path.read_text(encoding="utf-8")

    block_header_re = re.compile(r"^## Correction\s+(\d+)", re.MULTILINE)
    headers = list(block_header_re.finditer(content))
    total_blocks = len(headers)

    valid_corrections: list[dict] = []

    for i, header in enumerate(headers):
        block_start = header.start()
        block_end = headers[i + 1].start() if i + 1 < len(headers) else len(content)
        block_content = content[block_start:block_end]

        current_match = re.search(
            r"### Texte actuel\s*\n+(.*?)(?=###|---|\Z)",
            block_content,
            re.DOTALL,
        )
        corrected_match = re.search(
            r"### Texte corrigé\s*\n+(.*?)(?=###|---|\Z)",
            block_content,
            re.DOTALL,
        )

        if not current_match or not corrected_match:
            continue

        current_text = current_match.group(1).strip()
        corrected_text = corrected_match.group(1).strip()

        if not corrected_text or corrected_text == "[À COMPLÉTER]":
            continue

        valid_corrections.append(
            {
                "index": int(header.group(1)),
                "current": current_text,
                "corrected": corrected_text,
            }
        )

    return valid_corrections, total_blocks


def _apply_corrections_to_content(
    content: str,
    corrections: list[dict],
) -> tuple[str, list[str]]:
    """
    Applique une liste de corrections à un contenu textuel (première occurrence).

    Returns:
        (contenu_modifié, erreurs)
    """
    errors: list[str] = []

    for correction in corrections:
        current = correction["current"]
        corrected = correction["corrected"]
        idx = correction["index"]

        if current not in content:
            errors.append(f"Correction {idx} : texte actuel introuvable")
            continue

        content = content.replace(current, corrected, 1)

    return content, errors


def _needs_regeneration(
    reviewed_path: Path,
    processed_path: Path,
    corrections_path: Path | None,
) -> bool:
    """Retourne True si reviewed doit être (re)généré."""
    if not reviewed_path.exists():
        return True

    reviewed_mtime = reviewed_path.stat().st_mtime

    if processed_path.exists() and processed_path.stat().st_mtime > reviewed_mtime:
        return True

    if (
        corrections_path is not None
        and corrections_path.exists()
        and corrections_path.stat().st_mtime > reviewed_mtime
    ):
        return True

    return False


def apply_corrections(project_name: str) -> None:
    """
    Applique les corrections humaines pour tous les chunks traités d'un projet.

    - Lit sortie/<projet>/corrections/chunk_XXX.corrections.md
    - Applique les remplacements sur sortie/<projet>/processed/chunk_XXX.md
    - Écrit sortie/<projet>/reviewed/chunk_XXX.md
    - Met à jour project_state.json (section "corrections")

    Ne modifie jamais processed/*.md ni corrections/*.corrections.md.
    Respecte la reprise après interruption.
    """
    project_output_dir = SORTIE_DIR / project_name
    corrections_dir = project_output_dir / "corrections"
    processed_dir = project_output_dir / "processed"
    reviewed_dir = project_output_dir / "reviewed"

    reviewed_dir.mkdir(parents=True, exist_ok=True)

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

        base = chunk_name.replace(".txt", "")
        corrections_path = corrections_dir / f"{base}.corrections.md"
        processed_path = processed_dir / f"{base}.md"
        reviewed_path = reviewed_dir / f"{base}.md"

        if not processed_path.exists():
            print(f"Fichier processed introuvable, ignoré : {base}.md")
            continue

        has_corrections_file = corrections_path.exists()

        if not _needs_regeneration(reviewed_path, processed_path,
                                   corrections_path if has_corrections_file else None):
            print(f"Reviewed déjà à jour : {base}.md")
            continue

        if not has_corrections_file:
            reviewed_path.write_text(
                processed_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            state["corrections"][chunk_name] = {
                "status": "no_corrections",
                "corrections_path": None,
                "reviewed_path": str(reviewed_path),
                "applied_count": 0,
                "skipped_count": 0,
                "errors": [],
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            any_change = True
            print(f"Reviewed généré (pas de fichier corrections) : {reviewed_path}")
            continue

        valid_corrections, total_blocks = _parse_corrections(corrections_path)
        skipped_count = total_blocks - len(valid_corrections)

        content = processed_path.read_text(encoding="utf-8")

        if not valid_corrections:
            reviewed_path.write_text(content, encoding="utf-8")
            state["corrections"][chunk_name] = {
                "status": "no_corrections",
                "corrections_path": str(corrections_path),
                "reviewed_path": str(reviewed_path),
                "applied_count": 0,
                "skipped_count": skipped_count,
                "errors": [],
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            any_change = True
            print(f"Reviewed généré (aucune correction valide) : {reviewed_path}")
            continue

        modified_content, errors = _apply_corrections_to_content(content, valid_corrections)
        applied_count = len(valid_corrections) - len(errors)
        status = "applied" if not errors else "partial_error"

        reviewed_path.write_text(modified_content, encoding="utf-8")

        state["corrections"][chunk_name] = {
            "status": status,
            "corrections_path": str(corrections_path),
            "reviewed_path": str(reviewed_path),
            "applied_count": applied_count,
            "skipped_count": skipped_count,
            "errors": errors,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        any_change = True

        if errors:
            print(
                f"Reviewed généré avec {len(errors)} erreur(s) "
                f"({applied_count} correction(s) appliquée(s)) : {reviewed_path}"
            )
            for err in errors:
                print(f"  - {err}")
        else:
            print(
                f"Reviewed généré ({applied_count} correction(s) appliquée(s)) : {reviewed_path}"
            )

    if any_change:
        save_project_state(project_name, state)
