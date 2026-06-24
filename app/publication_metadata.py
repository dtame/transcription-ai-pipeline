"""
Publication Metadata — Gestion centralisée des métadonnées de publication.

Stocke et restitue les informations affichées sur :
  - couverture
  - page titre
  - DOCX (propriétés internes)
  - PDF (propriétés internes)
  - ZIP client (project_summary.json)

Les données sont persistées dans project_state.json sous la clé
"publication_metadata".
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from app.document_language import get_document_language
from app.logger import log_event
from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state


# ─────────────────────────────────────────────────────────────────────────────
# Schéma des métadonnées
# ─────────────────────────────────────────────────────────────────────────────

_METADATA_FIELDS: tuple[str, ...] = (
    "title",
    "subtitle",
    "author",
    "organization",
    "publication_date",
    "document_language",
    "publication_mode",
    "project_name",
)

_EMPTY_METADATA: dict = {
    "title":            "",
    "subtitle":         "",
    "author":           "",
    "organization":     "",
    "publication_date": "",
    "document_language": "",
    "publication_mode": "",
    "project_name":     "",
}


# ─────────────────────────────────────────────────────────────────────────────
# Détection du titre depuis publication.md
# ─────────────────────────────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
_BOLD_RE    = re.compile(r"^\*\*(.+?)\*\*$")

_STRUCTURAL_KEYS: frozenset[str] = frozenset({
    "cover", "couverture",
    "title page", "page de titre",
    "table of contents", "table des matières",
})


def _extract_title_from_publication_md(project_name: str) -> str | None:
    """
    Lit publication.md et extrait le titre de la section Cover/Couverture.

    Retourne None si le fichier est absent ou si aucun titre n'est détecté.
    """
    md_path = SORTIE_DIR / project_name / "publication" / "publication.md"
    if not md_path.exists():
        return None

    try:
        lines = md_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None

    in_cover = False
    for line in lines:
        stripped = line.strip()
        m = _HEADING_RE.match(stripped)
        if m:
            key = m.group(2).strip().lower()
            if key in ("cover", "couverture"):
                in_cover = True
                continue
            if key in _STRUCTURAL_KEYS:
                in_cover = False
                continue
        if in_cover:
            bm = _BOLD_RE.match(stripped)
            if bm:
                return bm.group(1).strip()

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Fonctions publiques
# ─────────────────────────────────────────────────────────────────────────────

def infer_default_metadata(project_name: str) -> dict:
    """
    Déduit des métadonnées par défaut si l'utilisateur n'a rien saisi.

    Ordre de priorité pour le titre :
      1. Titre extrait de publication.md (section Cover)
      2. Nom du projet formaté proprement

    Autres champs :
      - subtitle         : vide
      - author           : vide
      - organization     : vide
      - publication_date : date du jour (ISO)
      - document_language: via get_document_language()
      - publication_mode : depuis project_state["publication_mode"], sinon "BOOK"
      - project_name     : nom du projet
    """
    state = load_project_state(project_name)

    title = _extract_title_from_publication_md(project_name)
    if not title:
        title = project_name.replace("_", " ").replace("-", " ").title()

    document_language = get_document_language(project_name)

    publication_mode = (
        state.get("publication_mode")
        or state.get("publication", {}).get("mode")
        or "BOOK"
    )

    return {
        "title":             title,
        "subtitle":          "",
        "author":            "",
        "organization":      "",
        "publication_date":  date.today().isoformat(),
        "document_language": document_language,
        "publication_mode":  publication_mode,
        "project_name":      project_name,
    }


def get_publication_metadata(project_name: str) -> dict:
    """
    Retourne les métadonnées de publication du projet.

    Lit project_state.json["publication_metadata"].
    Applique des valeurs par défaut inférées pour les champs absents ou vides.
    """
    state    = load_project_state(project_name)
    stored   = state.get("publication_metadata", {})
    defaults = infer_default_metadata(project_name)

    metadata: dict = {}
    for field in _METADATA_FIELDS:
        stored_val = stored.get(field, "")
        metadata[field] = stored_val if stored_val else defaults.get(field, "")

    log_event({
        "step":    "publication_metadata",
        "project": project_name,
        "action":  "loaded",
        "title":   metadata["title"],
        "lang":    metadata["document_language"],
        "mode":    metadata["publication_mode"],
    })
    print(
        f"[publication_metadata] Métadonnées chargées — "
        f"titre={metadata['title']!r} | "
        f"lang={metadata['document_language']} | "
        f"mode={metadata['publication_mode']}"
    )

    return metadata


def save_publication_metadata(project_name: str, metadata: dict) -> None:
    """
    Sauvegarde les métadonnées de publication dans project_state.json.

    Seuls les champs déclarés dans _METADATA_FIELDS sont persistés.
    project_name est toujours forcé à la valeur du paramètre.
    """
    clean: dict = {}
    for field in _METADATA_FIELDS:
        clean[field] = str(metadata.get(field, "")).strip()
    clean["project_name"] = project_name

    state = load_project_state(project_name)
    state["publication_metadata"] = clean
    save_project_state(project_name, state)

    log_event({
        "step":    "publication_metadata",
        "project": project_name,
        "action":  "saved",
        "title":   clean["title"],
        "author":  clean["author"],
    })
    print(
        f"[publication_metadata] Métadonnées sauvegardées — "
        f"titre={clean['title']!r} | auteur={clean['author']!r}"
    )
