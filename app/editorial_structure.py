"""
Editorial Structure Builder — Construit une structure éditoriale cohérente
à partir des chunks traités, sans aucun appel IA.

Contraintes :
  - Aucun appel Ollama ou modèle IA
  - Déterministe et reproductible
  - Rapide (lecture seule des fichiers processed/)
  - Compatible avec le pipeline existant
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.document_language import get_document_language, get_language_labels
from app.editorial_cleanup import clean_editorial_artifacts
from app.logger import log_event
from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state


# ---------------------------------------------------------------------------
# Dataclasses publiques
# ---------------------------------------------------------------------------

@dataclass
class EditorialSection:
    title: str
    content: str


@dataclass
class EditorialStructure:
    title: str
    introduction: str
    sections: list[EditorialSection] = field(default_factory=list)
    conclusion: str = ""


# ---------------------------------------------------------------------------
# Titres génériques à absorber dans le contenu (ne deviennent pas chapitres)
# ---------------------------------------------------------------------------

_GENERIC_TITLES: frozenset[str] = frozenset({
    "summary",
    "conclusion",
    "key themes",
    "key themes & narrative overview",
    "key takeaways",
    "notes",
    "possible interpretations",
    "possible contexts",
    "questions",
    "reflection",
    "overview",
    "introduction",
    "background",
    "core themes",
    "core themes and biblical references",
    "biblical references",
    "cultural context",
    "theological context",
    "theological implications",
    "possible next steps",
    "summary and implications",
    "cultural and theological context",
    "potential confusions and questions",
    "translation nuances",
    "spiritual lessons",
    "spiritual lessons from tradition",
    "summary in english",
    "summary in french",
    "biblical and theological connections",
    "narrative overview",
    "key themes and narrative overview",
    "notable quotes",
    "références bibliques",
    "references bibliques",
    "key theological concepts",
    "theological concepts",
    "discours ou conversation",
    "conversation",
    "transcript",
    "transcription",
    "lecture notes",
})

# Titres qui méritent d'être reformulés plutôt que supprimés — géré dans _clean_title

# Préfixes qui rendent automatiquement un titre générique (insensible à la casse)
_GENERIC_PREFIXES: tuple[str, ...] = (
    "summary of",
    "résumé de",
    "resume de",
    "overview of",
    "analysis of",
    "breakdown of",
    "discussion of",
    "structured breakdown",
    "structured summary",
    "summary and",
    "key themes",
    "résumé de la",
    "résumé du",
    "notes on",
    "themes in",
    "quote",
    "biblical ref",
    "reference",
)

# Plage cible de sections dans le document final
_TARGET_MIN = 5
_TARGET_MAX = 15

# Regex : titres Markdown  (#, ##, ###)
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$")

# Regex : ligne bold-only  **Titre** ou *Titre*
_BOLD_TITLE_RE = re.compile(r"^\*{1,2}([^*]{3,80})\*{1,2}\s*$")

# Regex : titres avec préfixe numéroté  "1. Core Themes…", "### **2. …**"
_NUMBERED_HEADING_RE = re.compile(
    r"^(?:#{1,3}\s+)?(?:\*{0,2})?\d+[.)]\s+.+$"
)


# ---------------------------------------------------------------------------
# Helpers : normalisation et détection de titres
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Normalise un titre pour la comparaison : minuscules, sans ponctuation."""
    text = re.sub(r"[*#`]", "", text)
    text = re.sub(r"^\d+[.)]\s*", "", text)
    text = text.strip().rstrip(":").strip()
    return text.lower()


def _is_generic(title: str) -> bool:
    """Retourne True si le titre est générique (doit être absorbé dans le contenu)."""
    norm = _normalize(title)
    if norm in _GENERIC_TITLES:
        return True
    # Préfixes génériques (ex. "Summary of the sermon", "Résumé de la séance")
    for prefix in _GENERIC_PREFIXES:
        if norm.startswith(prefix):
            return True
    return False


_META_LABEL_WORDS: frozenset[str] = frozenset({
    "transcript", "transcription", "recap", "notes", "summary",
    "overview", "analysis", "breakdown", "service",
})


def _clean_title(raw: str) -> str:
    """Nettoie un titre : retire les marqueurs Markdown, le colon final et normalise la casse.

    Si le titre est de la forme "Label méta: Vrai titre", extrait "Vrai titre".
    Exemple : "Religious Service Transcript: Birthday Celebration & Sermon"
              → "Birthday Celebration & Sermon"
    """
    title = re.sub(r"[*#`]", "", raw)
    title = re.sub(r"^\d+[.)]\s*", "", title)
    title = title.strip().rstrip(":")

    # Détecter le pattern "Texte méta: Vrai titre" (séparé par ": ")
    if ": " in title:
        left, right = title.split(": ", 1)
        left_words = set(left.lower().split())
        if left_words & _META_LABEL_WORDS and len(right.strip()) >= 4:
            title = right.strip()

    # Si le titre commence directement par un mot méta suivi de ":", extraire la suite
    for meta in ("transcript:", "recap:", "transcription:", "notes:"):
        if title.lower().startswith(meta):
            after = title[len(meta):].strip()
            if len(after) >= 4:
                title = after
                break

    title = title.strip()
    if title:
        title = title[0].upper() + title[1:]
    return title


def _is_valid_title(raw: str) -> bool:
    """
    Retourne True si la chaîne peut devenir un titre de chapitre.
    Rejette : titres génériques, citations (commençant par "), titres se
    terminant par ':' qui sonnent comme des en-têtes IA, et titres trop courts.
    """
    title = _clean_title(raw)
    if len(title) < 4:
        return False
    if _is_generic(raw):
        return False
    # Titres commençant par une citation ou un guillemet
    if title.startswith(('"', '"', "'")):
        return False
    # Titres purement numériques
    if re.match(r"^\d+\.?\s*$", title):
        return False
    return True


def _extract_section_heading(text: str) -> str | None:
    """
    Extrait le premier titre utilisable d'un texte de chunk.

    Priorité :
      1. H1 ou H2 Markdown valide (# ou ##)
      2. Ligne bold-only valide (**Titre**)

    Retourne None si aucun titre utilisable n'est trouvé.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Titres numérotés génériques ("### 1. Core Themes…") → toujours ignorés
        if _NUMBERED_HEADING_RE.match(stripped):
            continue

        # Titres Markdown H1/H2
        m = _HEADING_RE.match(stripped)
        if m:
            level, raw_title = len(m.group(1)), m.group(2)
            if level <= 2 and _is_valid_title(raw_title):
                return _clean_title(raw_title)
            continue

        # Lignes bold-only
        m = _BOLD_TITLE_RE.match(stripped)
        if m:
            raw_title = m.group(1)
            if _is_valid_title(raw_title):
                return _clean_title(raw_title)

    return None


def _derive_main_title(project_name: str, first_chunks: list[str]) -> str:
    """
    Détermine le titre principal du document.

    Ordre de priorité :
      1. Premier H1 non-générique trouvé dans les 3 premiers chunks.
      2. Nom du projet humanisé.
      3. "Manuscrit".
    """
    for chunk_text in first_chunks[:3]:
        for line in chunk_text.splitlines():
            m = _HEADING_RE.match(line.strip())
            if m and len(m.group(1)) == 1 and not _is_generic(m.group(2)):
                return _clean_title(m.group(2))

    if project_name:
        return project_name.replace("_", " ").replace("-", " ").title()

    return "Manuscrit"


# ---------------------------------------------------------------------------
# Nettoyage du contenu de section
# ---------------------------------------------------------------------------

def _clean_section_content(text: str, section_title: str | None) -> str:
    """
    Nettoie le corps d'une section :
      - Supprime les lignes H1 (elles deviennent le titre du document).
      - Supprime la ligne du titre de section lui-même (déjà dans le header).
      - Supprime les titres numérotés génériques de l'IA.
      - Supprime les lignes bold-only génériques.
      - Conserve les H2/H3 non-génériques (structure légitime).
    """
    normalized_section = _normalize(section_title) if section_title else ""
    lines = text.splitlines()
    result: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Titres numérotés IA ("### 1. Core Themes…")
        if _NUMBERED_HEADING_RE.match(stripped):
            continue

        # H1 → supprimé (titre document)
        m = _HEADING_RE.match(stripped)
        if m:
            level, raw_title = len(m.group(1)), m.group(2)
            if level == 1:
                continue
            # H2/H3 génériques → supprimés
            if _is_generic(raw_title):
                continue
            # H2/H3 identiques au titre de section → supprimés
            if _normalize(raw_title) == normalized_section:
                continue
            # H2/H3 non-génériques → conservés
            result.append(line)
            continue

        # Lignes bold-only
        m = _BOLD_TITLE_RE.match(stripped)
        if m:
            raw_title = m.group(1)
            # Si c'est le titre de la section ou un titre générique → supprimé
            if _is_generic(raw_title) or _normalize(raw_title) == normalized_section:
                continue
            # Sinon : c'est un sous-titre légitime → conserver sans les astérisques
            result.append(_clean_title(raw_title))
            continue

        result.append(line)

    # Réduire les lignes vides consécutives
    deduplicated: list[str] = []
    prev_blank = False
    for line in result:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        deduplicated.append(line)
        prev_blank = is_blank

    return "\n".join(deduplicated).strip()


# ---------------------------------------------------------------------------
# Algorithme de regroupement des chunks en sections
# ---------------------------------------------------------------------------

def _group_chunks_into_sections(
    cleaned_chunks: list[str],
) -> list[tuple[str | None, list[str]]]:
    """
    Regroupe les chunks nettoyés en sections éditoriales.

    Algorithme :
      1. Étiqueter chaque chunk avec son premier titre non-générique.
      2. Démarrer une nouvelle section quand un nouveau titre distinct apparaît.
      3. Les chunks sans titre rejoignent la section en cours.
      4. Fusionner les sections consécutives pour rester dans [_TARGET_MIN, _TARGET_MAX].
    """
    # Étape 1 : étiqueter
    labeled: list[tuple[str | None, str]] = [
        (_extract_section_heading(text), text)
        for text in cleaned_chunks
    ]

    # Étape 2 : regrouper par changement de titre
    groups: list[tuple[str | None, list[str]]] = []
    for heading, text in labeled:
        if not text.strip():
            continue
        if heading is not None and groups:
            # Nouveau titre différent du groupe courant → nouvelle section
            current_title = groups[-1][0]
            if _normalize(heading) != _normalize(current_title or ""):
                groups.append((heading, [text]))
                continue
        if groups:
            groups[-1][1].append(text)
        else:
            groups.append((heading, [text]))

    # Étape 3 : fusionner si trop de sections
    if len(groups) > _TARGET_MAX:
        groups = _merge_to_target(groups, _TARGET_MAX)

    return groups


def _merge_to_target(
    groups: list[tuple[str | None, list[str]]],
    target: int,
) -> list[tuple[str | None, list[str]]]:
    """
    Fusionne les groupes par fenêtre glissante pour atteindre `target` sections.
    Le titre retenu est le premier titre non-None de la fenêtre.
    """
    window = max(2, round(len(groups) / target))
    merged: list[tuple[str | None, list[str]]] = []

    for i in range(0, len(groups), window):
        batch = groups[i : i + window]
        title = next((g[0] for g in batch if g[0] is not None), None)
        texts = [t for g in batch for t in g[1]]
        merged.append((title, texts))

    return merged


# ---------------------------------------------------------------------------
# Table des matières
# ---------------------------------------------------------------------------

def _build_toc(sections: list[EditorialSection], labels: dict[str, str]) -> str:
    """Génère la table des matières en texte Markdown (libellés selon la langue)."""
    toc_title = labels["table_of_contents"]
    intro_label = labels["introduction"]
    conclusion_label = labels["conclusion"]

    lines = [f"# {toc_title}", ""]
    lines.append(f"1. {intro_label}")
    for idx, section in enumerate(sections, start=2):
        lines.append(f"{idx}. {section.title}")
    lines.append(f"{len(sections) + 2}. {conclusion_label}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def build_editorial_structure(
    project_name: str,
    cleaned_text: str,
    chunks_texts: list[str] | None = None,
    document_language: str | None = None,
) -> EditorialStructure:
    """
    Construit une EditorialStructure cohérente à partir du texte nettoyé.

    Args:
        project_name:       Nom du projet (utilisé pour le titre si non détecté).
        cleaned_text:       Texte complet nettoyé (concaténation des chunks).
        chunks_texts:       Liste des textes bruts par chunk (avant nettoyage éditorial).
                            Si None, le texte complet est traité comme un bloc unique.
        document_language:  Langue documentaire ("en" ou "fr").
                            Si None, elle est détectée depuis cleaned_text.

    Returns:
        EditorialStructure prête à être sérialisée en Markdown.
    """
    print("[editorial_structure] Construction de la structure éditoriale...")

    # ── 0. Résoudre la langue documentaire ────────────────────────────────
    if document_language is None:
        document_language = get_document_language(
            project_name, fallback_text=cleaned_text
        )
    labels = get_language_labels(document_language)
    print(f"[editorial_structure] Langue documentaire : {document_language}")

    # ── 1. Nettoyer chaque chunk individuellement ──────────────────────────
    if chunks_texts:
        cleaned_chunks = [
            clean_editorial_artifacts(t, remove_timestamps=True).strip()
            for t in chunks_texts
        ]
        cleaned_chunks = [c for c in cleaned_chunks if c]
    else:
        cleaned_chunks = [cleaned_text] if cleaned_text.strip() else []

    if not cleaned_chunks:
        return EditorialStructure(
            title=project_name.replace("_", " ").title() or labels["manuscript"],
            introduction=(
                "This document is empty."
                if document_language == "en"
                else "Ce document est vide."
            ),
            sections=[],
            conclusion="",
        )

    # ── 2. Titre principal ─────────────────────────────────────────────────
    main_title = _derive_main_title(project_name, cleaned_chunks)
    print(f"[editorial_structure] Titre détecté : {main_title}")

    # ── 3. Regroupement en sections ────────────────────────────────────────
    groups = _group_chunks_into_sections(cleaned_chunks)

    # ── 4. Construire les EditorialSection ─────────────────────────────────
    sections: list[EditorialSection] = []
    chapter_counter = 0
    normalized_main = _normalize(main_title)
    chapter_label = labels["chapter"]

    for idx, (title_hint, chunk_list) in enumerate(groups, start=1):
        combined_raw = "\n\n".join(c.strip() for c in chunk_list if c.strip())
        if not combined_raw:
            continue

        # Si le titre de la section est identique au titre principal du document,
        # on génère un titre de chapitre numéroté plutôt que de dupliquer.
        if title_hint and _normalize(title_hint) == normalized_main:
            title_hint = None

        if title_hint:
            section_title = title_hint
        else:
            chapter_counter += 1
            section_title = f"{chapter_label} {chapter_counter}"

        body = _clean_section_content(combined_raw, section_title)

        if body:
            sections.append(EditorialSection(title=section_title, content=body))

    print(f"[editorial_structure] Nombre de sections créées : {len(sections)}")

    # ── 5. Introduction et conclusion selon la langue ──────────────────────
    project_label = project_name.replace("_", " ").replace("-", " ").title()
    if document_language == "en":
        introduction = (
            f"This document brings together the teachings, reflections, and content "
            f"from the *{project_label}* project."
        )
        conclusion = (
            "This manuscript provides a structured synthesis of the content "
            "processed in this project."
        )
    else:
        introduction = (
            f"Ce document rassemble les enseignements, réflexions et contenus "
            f"issus du projet *{project_label}*."
        )
        conclusion = (
            "Ce manuscrit constitue une synthèse structurée "
            "du contenu traité dans ce projet."
        )

    return EditorialStructure(
        title=main_title,
        introduction=introduction,
        sections=sections,
        conclusion=conclusion,
    )


# ---------------------------------------------------------------------------
# Sérialisation Markdown
# ---------------------------------------------------------------------------

def render_structured_manuscript(
    structure: EditorialStructure,
    labels: dict[str, str] | None = None,
) -> str:
    """
    Sérialise une EditorialStructure en Markdown bien formé.

    Format produit :
      # TITRE
      # Table of Contents / Table des matières
      # Introduction
      # Chapter 1 … N  /  # Chapitre 1 … N
      # Conclusion
    """
    if labels is None:
        labels = get_language_labels("en")

    lines: list[str] = []

    # Titre principal
    lines += [f"# {structure.title}", ""]

    # Table des matières
    lines += [_build_toc(structure.sections, labels), ""]

    # Séparateur + Introduction
    intro_label = labels["introduction"]
    conclusion_label = labels["conclusion"]

    lines += ["---", "", f"# {intro_label}", "", structure.introduction, ""]

    # Sections
    for section in structure.sections:
        lines += ["---", "", f"# {section.title}", "", section.content, ""]

    # Conclusion
    lines += ["---", "", f"# {conclusion_label}", "", structure.conclusion, ""]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Point d'entrée public (utilisé par editorial_finalizer)
# ---------------------------------------------------------------------------

def generate_structured_manuscript(
    project_name: str,
    chunks_texts: list[str],
    document_language: str | None = None,
) -> tuple[EditorialStructure, str]:
    """
    Construit la structure éditoriale et retourne (structure, texte_markdown).

    Args:
        project_name:       Nom du projet.
        chunks_texts:       Textes bruts des fichiers processed/chunk_*.md.
        document_language:  Langue documentaire ("en" ou "fr"). Si None, détectée
                            automatiquement depuis le texte nettoyé.

    Returns:
        Tuple (EditorialStructure, str contenant le Markdown complet).
    """
    full_cleaned = "\n\n".join(
        clean_editorial_artifacts(t, remove_timestamps=True).strip()
        for t in chunks_texts
        if t.strip()
    )

    structure = build_editorial_structure(
        project_name=project_name,
        cleaned_text=full_cleaned,
        chunks_texts=chunks_texts,
        document_language=document_language,
    )
    labels = get_language_labels(document_language or "en")
    rendered = render_structured_manuscript(structure, labels=labels)
    return structure, rendered


# ---------------------------------------------------------------------------
# Écriture du fichier + mise à jour de l'état (appelé depuis le finalizer)
# ---------------------------------------------------------------------------

def write_structured_manuscript(
    project_name: str,
    chunks_texts: list[str],
    document_language: str | None = None,
) -> Path | None:
    """
    Génère `sortie/<project_name>/final/manuscript_structured.md`.

    Met à jour project_state.json avec les métadonnées de la structure.
    Retourne le chemin du fichier généré, ou None en cas d'erreur.
    """
    log_event({
        "step": "editorial_structure",
        "project": project_name,
        "action": "start",
        "message": "Début construction structure éditoriale",
    })

    state = load_project_state(project_name)
    now_iso = datetime.now().isoformat(timespec="seconds")

    try:
        structure, rendered = generate_structured_manuscript(
            project_name, chunks_texts, document_language=document_language
        )

        final_dir = SORTIE_DIR / project_name / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        output_path = final_dir / "manuscript_structured.md"
        output_path.write_text(rendered, encoding="utf-8")

        print(f"[editorial_structure] Fichier généré : {output_path}")
        log_event({
            "step": "editorial_structure",
            "project": project_name,
            "action": "success",
            "message": f"Manuscrit structuré généré : {output_path}",
            "sections_count": len(structure.sections),
            "title": structure.title,
        })

        # Mise à jour de project_state.json
        state.setdefault("editorial", {}).update({
            "structure_built": True,
            "structured_manuscript_path": str(output_path),
            "structure_title": structure.title,
            "structure_sections_count": len(structure.sections),
            "generated_at": now_iso,
        })
        save_project_state(project_name, state)

        return output_path

    except Exception as exc:
        err_msg = str(exc)
        print(f"[editorial_structure] ERREUR : {err_msg}")
        log_event({
            "step": "editorial_structure",
            "project": project_name,
            "action": "error",
            "message": err_msg,
        })
        state.setdefault("editorial", {}).update({
            "structure_built": False,
            "structure_error": err_msg,
            "generated_at": now_iso,
        })
        save_project_state(project_name, state)
        return None
