"""
Service de validation qualité de publication — TranscriptionAI.

Vérifie qu'un projet est vraiment publiable avant de le marquer comme succès.

Usage :
    from app.publication_quality_service import validate_publication

    result = validate_publication("pastoral_retreat")
    # → {"status": "passed" | "warning" | "failed", "errors": [...], "warnings": [...]}
"""

from __future__ import annotations

import re
from pathlib import Path

from app.paths import SORTIE_DIR
from app.project_state import load_project_state
from app.project_metadata import load_project_metadata


# ---------------------------------------------------------------------------
# Patterns d'artefacts IA à détecter
# ---------------------------------------------------------------------------

_AI_ARTIFACT_RE = re.compile(
    r"(<think>|</think>|/think\b|"
    r"\\boxed\{|"
    r"\bFinal Answer\b|"
    r"If you need|"
    r"Let me know|"
    r"The provided text|"
    r"Here('s| is) (a |the )?(structured )?summary|"
    r"This text appears)",
    re.IGNORECASE,
)

_TECHNICAL_METADATA_RE = re.compile(
    r"(# Document final —|"
    r"Projet\s*:|"
    r"Chunk\s*:|"
    r"Généré le\s*:|"
    r"Nombre de chunks fusionnés|"
    r"Chunks avec corrections|"
    r"chunk_\d{3}\.md)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Validation principale
# ---------------------------------------------------------------------------

def validate_publication(project_name: str) -> dict:
    """
    Valide la qualité d'une publication générée.

    Vérifie :
    - document_publication.md existe et a du contenu
    - Pas d'artefacts IA parasites
    - Pas de métadonnées techniques dans le contenu
    - Table des matières non vide si include_toc = true
    - Couverture réelle présente si include_cover = true
    - PDF généré
    - DOCX généré
    - ZIP client généré

    Retourne :
    {
        "status": "passed" | "warning" | "failed",
        "errors": [...],
        "warnings": [...]
    }
    """
    errors: list[str] = []
    warnings: list[str] = []

    final_dir   = SORTIE_DIR / project_name / "final"
    pub_md_path = final_dir / "document_publication.md"
    pub_pdf_path = final_dir / "document_publication.pdf"
    pub_docx_path = final_dir / "document_publication.docx"
    clean_md_path = final_dir / "document_clean.md"
    cover_path = SORTIE_DIR / project_name / "cover" / "cover.jpg"
    zip_dir    = SORTIE_DIR / project_name / "client"

    state = load_project_state(project_name)

    try:
        meta = load_project_metadata(project_name)
    except Exception:
        meta = {}

    # ── 1. document_publication.md ────────────────────────────────────────
    if not pub_md_path.exists():
        errors.append("document_publication.md absent")
    else:
        content = pub_md_path.read_text(encoding="utf-8")
        if len(content.strip()) < 200:
            errors.append(
                f"document_publication.md trop court ({len(content.strip())} caractères)"
            )

        # Détection artefacts IA
        ai_matches = _AI_ARTIFACT_RE.findall(content)
        if ai_matches:
            unique = list(dict.fromkeys(m if isinstance(m, str) else m[0] for m in ai_matches))
            warnings.append(
                f"Artefacts IA détectés dans document_publication.md : "
                f"{unique[:5]}"
            )

        # Détection métadonnées techniques
        tech_matches = _TECHNICAL_METADATA_RE.findall(content)
        if tech_matches:
            unique_tech = list(dict.fromkeys(tech_matches))
            warnings.append(
                f"Métadonnées techniques dans document_publication.md : "
                f"{unique_tech[:5]}"
            )

    # ── 2. document_clean.md (optionnel mais recommandé) ──────────────────
    if not clean_md_path.exists():
        warnings.append(
            "document_clean.md absent — la source propre n'a pas été générée"
        )

    # ── 3. Table des matières ─────────────────────────────────────────────
    include_toc = meta.get("include_toc", True)
    if include_toc:
        toc_state = state.get("publication", {}).get("toc", {})
        headings_count = toc_state.get("headings_count", 0)
        if headings_count == 0:
            warnings.append(
                "Table des matières vide alors que include_toc = true"
            )

    # ── 4. Couverture ─────────────────────────────────────────────────────
    include_cover = meta.get("include_cover", True)
    if include_cover:
        if not cover_path.exists():
            warnings.append("Couverture absente (cover.jpg)")
        elif cover_path.stat().st_size < 2_000:
            warnings.append(
                "Couverture cover.jpg trop petite — probablement un placeholder"
            )

    # ── 5. PDF publication ────────────────────────────────────────────────
    if not pub_pdf_path.exists():
        errors.append("document_publication.pdf absent")
    elif pub_pdf_path.stat().st_size < 5_000:
        warnings.append(
            f"document_publication.pdf suspect — taille très faible "
            f"({pub_pdf_path.stat().st_size} octets)"
        )

    # ── 6. DOCX publication ───────────────────────────────────────────────
    if not pub_docx_path.exists():
        warnings.append("document_publication.docx absent")

    # ── 7. ZIP client ─────────────────────────────────────────────────────
    zip_files = list(zip_dir.glob("*.zip")) if zip_dir.exists() else []
    if not zip_files:
        client_state = state.get("client_export", {})
        if not client_state.get("generated"):
            warnings.append("ZIP client absent")

    # ── 8. Statut global ──────────────────────────────────────────────────
    if errors:
        status = "failed"
    elif warnings:
        status = "warning"
    else:
        status = "passed"

    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
    }


def validate_and_update_state(project_name: str) -> dict:
    """
    Valide la publication et met à jour project_state.json avec le résultat.

    Retourne le résultat de validate_publication().
    """
    from app.project_state import save_project_state

    result = validate_publication(project_name)

    state = load_project_state(project_name)

    if "publication" not in state:
        state["publication"] = {}

    state["publication"]["quality"] = result
    save_project_state(project_name, state)

    emoji = {"passed": "✓", "warning": "⚠", "failed": "✗"}.get(result["status"], "?")
    print(
        f"[quality] {emoji} Validation publication {project_name} : "
        f"{result['status']}"
    )
    if result["errors"]:
        for e in result["errors"]:
            print(f"  [ERREUR] {e}")
    if result["warnings"]:
        for w in result["warnings"]:
            print(f"  [AVERT.] {w}")

    return result
