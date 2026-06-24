"""
Publication Builder — Couche intermédiaire avant génération DOCX/PDF.

Transforme un manuscrit éditorial en un document structuré prêt à publier,
en appliquant la structure propre au mode de publication choisi.

Entrée  : sortie/<project_name>/final/manuscript_rewritten.md
Fallback : sortie/<project_name>/final/manuscript_structured.md
Sortie  : sortie/<project_name>/publication/publication.md
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from app.document_language import get_document_language
from app.logger import log_event
from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state
from app.publication_metadata import get_publication_metadata
from app.publication_mode_engine import get_publication_structure


# ─────────────────────────────────────────────────────────────────────────────
# Libellés divers par langue (couverture, page de titre)
# ─────────────────────────────────────────────────────────────────────────────

_LANG_MISC: dict[str, dict[str, str]] = {
    "en": {
        "generated_on": "Generated on",
        "project":      "Project",
    },
    "fr": {
        "generated_on": "Généré le",
        "project":      "Projet",
    },
}

_INTRO_KEYS = {"introduction", "intro"}
_CONCL_KEYS = {"conclusion", "conclusions", "closing", "épilogue", "epilogue"}

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


# ─────────────────────────────────────────────────────────────────────────────
# Mots-clés de correspondance section → contenu du manuscrit
# ─────────────────────────────────────────────────────────────────────────────

_SECTION_KEYWORDS: dict[str, list[str]] = {
    "preface":                ["préface", "preface", "avant-propos", "foreword"],
    "introduction":           ["introduction", "intro"],
    "conclusion":             ["conclusion", "conclusions", "closing", "épilogue", "epilogue"],
    "prayer_conclusion":      ["prière", "prayer", "amen", "intercession", "fermeture"],
    "main_message":           ["message", "texte principal", "sermon", "prédication", "predication", "homélie"],
    "key_points":             ["points clés", "key points", "point clé", "idée principale", "grande idée"],
    "biblical_references":    ["bible", "biblique", "écriture", "scripture", "verset", "passage", "référence biblique"],
    "practical_applications": ["application", "pratique", "mise en pratique", "practical"],
    "objectives":             ["objectif", "objective", "but", "goal", "compétence", "résultat attendu"],
    "modules":                ["module", "unité", "unit", "session", "leçon", "cours"],
    "exercises":              ["exercice", "exercise", "activité", "activity", "travaux pratiques"],
    "reflection_questions":   ["question", "réflexion", "reflection", "discussion"],
    "executive_summary":      ["résumé exécutif", "executive summary", "résumé", "summary", "synthèse", "sommaire"],
    "context":                ["contexte", "context", "background", "mise en contexte", "cadre"],
    "diagnosis":              ["diagnostic", "diagnosis", "situation actuelle", "enjeu", "état des lieux"],
    "recommendations":        ["recommandation", "recommendation", "préconisation", "suggestion", "piste"],
    "action_plan":            ["plan d'action", "action plan", "prochaines étapes", "next steps", "mise en oeuvre"],
    "analysis":               ["analyse", "analysis", "étude", "examen", "exploration"],
    "findings":               ["résultats", "résultat", "finding", "constat", "observation", "bilan"],
    "episode_summary":        ["résumé", "summary", "présentation", "épisode", "à propos"],
    "highlights":             ["temps fort", "highlight", "moment fort", "saillant", "faits saillants"],
    "key_quotes":             ["citation", "quote", "parole", "extrait", "verbatim"],
    "resources":              ["ressource", "resource", "lien", "référence", "bibliographie", "pour aller plus loin"],
}

# Clés qui consomment systématiquement TOUS les chapitres non attribués
_BULK_STYLE_KEYS = frozenset({
    "chapters", "sections", "modules", "highlights",
    "main_message", "diagnosis", "analysis",
})


# ─────────────────────────────────────────────────────────────────────────────
# Parsing du manuscrit source
# ─────────────────────────────────────────────────────────────────────────────

def _parse_sections(text: str) -> list[dict]:
    """Découpe un manuscrit markdown en sections {level, title, content}."""
    sections: list[dict] = []
    matches = list(_HEADING_RE.finditer(text))

    for i, m in enumerate(matches):
        level   = len(m.group(1))
        title   = m.group(2).strip()
        start   = m.end()
        end     = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        sections.append({"level": level, "title": title, "content": content})

    return sections


def _detect_title(sections: list[dict], project_name: str) -> str:
    """Détecte le titre principal. Priorité : premier H1 → nom formaté."""
    for s in sections:
        if s["level"] == 1 and s["title"]:
            return s["title"]
    formatted = project_name.replace("_", " ").replace("-", " ").title()
    return formatted if formatted else "Publication"


def _classify_sections(sections: list[dict]) -> dict:
    """
    Classe les sections en intro, chapitres de corps, conclusion.
    Ignore les marqueurs structurels connus (cover, title page, toc).
    """
    _structural = {
        "cover", "couverture",
        "title page", "page de titre",
        "table of contents", "table des matières",
    }

    intro:      dict | None = None
    chapters:   list[dict] = []
    conclusion: dict | None = None

    for s in sections:
        key = s["title"].lower().strip()

        if key in _structural:
            continue
        if any(k in key for k in _INTRO_KEYS):
            intro = s
        elif any(k in key for k in _CONCL_KEYS):
            conclusion = s
        elif s["level"] <= 2 and s["title"]:
            chapters.append(s)

    return {"intro": intro, "chapters": chapters, "conclusion": conclusion}


# ─────────────────────────────────────────────────────────────────────────────
# Assignation du contenu aux sections du mode
# ─────────────────────────────────────────────────────────────────────────────

def _assign_content(structure: dict, classified: dict) -> dict[str, str | None]:
    """
    Pré-calcule le contenu à affecter à chaque section-clé du mode.

    Stratégie en trois passes :
      1. Correspondance explicite pour intro et conclusion.
      2. Correspondance par mots-clés sur les chapitres restants.
      3. La bulk_key reçoit tous les chapitres non encore attribués.
         Si la structure ne comporte pas de section "introduction",
         la bulk_key intègre aussi le contenu de l'intro.
    """
    all_keys = (
        structure["front_matter"]
        + structure["main_sections"]
        + structure["back_matter"]
    )
    # Clés de contenu (hors structurelles pures)
    content_keys = [k for k in all_keys if k not in ("cover", "title_page", "toc")]

    bulk_key          = structure.get("bulk_key")
    has_intro_section = "introduction" in content_keys
    has_concl_section = "conclusion"   in content_keys

    used_chapters: set[int] = set()
    result: dict[str, str | None] = {}

    # ── Passe 1 : intro et conclusion explicites ──────────────────────────────
    if has_intro_section:
        intro = classified.get("intro")
        result["introduction"] = intro["content"] if intro and intro.get("content") else None

    if has_concl_section:
        concl = classified.get("conclusion")
        result["conclusion"] = concl["content"] if concl and concl.get("content") else None

    # ── Passe 2 : correspondance par mots-clés ────────────────────────────────
    skip = {"introduction", "conclusion", bulk_key} | _BULK_STYLE_KEYS
    for key in content_keys:
        if key in result or key in skip:
            continue

        # prayer_conclusion peut aussi utiliser la conclusion classifiée
        if key == "prayer_conclusion":
            found = False
            for i, ch in enumerate(classified["chapters"]):
                if i in used_chapters:
                    continue
                kws = _SECTION_KEYWORDS.get("prayer_conclusion", [])
                if any(kw in ch["title"].lower() for kw in kws):
                    result[key] = ch["content"] or ""
                    used_chapters.add(i)
                    found = True
                    break
            if not found:
                concl = classified.get("conclusion")
                result[key] = concl["content"] if concl and concl.get("content") else None
            continue

        # Correspondance générale par mots-clés
        keywords = _SECTION_KEYWORDS.get(key, [])
        found = False
        if keywords:
            for i, ch in enumerate(classified["chapters"]):
                if i in used_chapters:
                    continue
                if any(kw in ch["title"].lower() for kw in keywords):
                    result[key] = ch["content"] or ""
                    used_chapters.add(i)
                    found = True
                    break

        if not found:
            # Fallback intro pour certaines clés "résumé"
            if key in ("executive_summary", "episode_summary") and not has_intro_section:
                intro = classified.get("intro")
                result[key] = intro["content"] if intro and intro.get("content") else None
            else:
                result[key] = None

    # ── Passe 3 : bulk_key ────────────────────────────────────────────────────
    if bulk_key and bulk_key not in result:
        chunks: list[str] = []

        # Si la structure n'a pas de section "introduction",
        # la bulk_key hérite du contenu de l'intro.
        if not has_intro_section:
            intro = classified.get("intro")
            if intro and intro.get("content"):
                chunks.append(intro["content"])

        # Tous les chapitres non encore utilisés
        for i, ch in enumerate(classified["chapters"]):
            if i not in used_chapters:
                used_chapters.add(i)
                if ch.get("content"):
                    chunks.append(f"## {ch['title']}\n\n{ch['content']}")
                else:
                    chunks.append(f"## {ch['title']}")

        result[bulk_key] = "\n\n".join(chunks) if chunks else None

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Table des matières structurée
# ─────────────────────────────────────────────────────────────────────────────

def _build_structured_toc(
    main_sections: list[str],
    labels: dict[str, str],
    classified: dict,
) -> str:
    """
    Construit la table des matières depuis les sections principales du mode.
    Pour la bulk_key (clés multi-chapitres), liste les titres individuels.
    """
    lines: list[str] = []
    idx = 1

    for key in main_sections:
        label = labels.get(key, key)

        if key in _BULK_STYLE_KEYS:
            for ch in classified["chapters"]:
                lines.append(f"{idx}. {ch['title']}")
                idx += 1
        else:
            lines.append(f"{idx}. {label}")
            idx += 1

    return "\n".join(lines) if lines else "_Aucune section détectée._"


# ─────────────────────────────────────────────────────────────────────────────
# Assemblage structuré de publication.md
# ─────────────────────────────────────────────────────────────────────────────

def _misc_label(key: str, lang: str) -> str:
    return _LANG_MISC.get(lang, _LANG_MISC["en"]).get(key, key)


def _assemble_structured_publication(
    title: str,
    project_name: str,
    lang: str,
    classified: dict,
    structure: dict,
    metadata: dict | None = None,
) -> str:
    """
    Assemble publication.md selon la structure du mode de publication.

    Le contenu existant du manuscrit est préservé intégralement.
    Les sections sans contenu reçoivent un marqueur HTML invisible :
      <!-- Section à enrichir ultérieurement -->
    Ce marqueur sera ignoré par les moteurs DOCX et PDF.
    """
    meta     = metadata or {}
    pub_date = meta.get("publication_date") or date.today().isoformat()
    subtitle = meta.get("subtitle", "")
    author   = meta.get("author", "")
    org      = meta.get("organization", "")

    labels       = structure["section_labels"]
    front_matter = structure["front_matter"]
    main_sections = structure["main_sections"]
    back_matter  = structure["back_matter"]

    # Pré-calcul du contenu par section
    content_map = _assign_content(structure, classified)

    parts: list[str] = []

    def _render_section(key: str, sep: bool = True) -> None:
        """Ajoute une section au rendu final."""
        label   = labels.get(key, key)
        content = content_map.get(key)
        if sep:
            parts.append(f"\n\n---\n\n# {label}\n")
        else:
            parts.append(f"# {label}\n")
        if content:
            parts.append(content)
        else:
            parts.append("<!-- Section à enrichir ultérieurement -->")

    # ── Front Matter ──────────────────────────────────────────────────────────
    for i, key in enumerate(front_matter):
        label = labels.get(key, key)

        if key == "cover":
            parts.append(f"# {label}\n")
            parts.append(f"**{title}**\n")
            if subtitle:
                parts.append(f"\n_{subtitle}_")
            parts.append(f"\n{_misc_label('generated_on', lang)} : {pub_date}")
            parts.append(f"\n{_misc_label('project', lang)} : {project_name}")
            if author:
                parts.append(f"\n{author}")
            if org:
                parts.append(f"\n{org}")

        elif key == "title_page":
            parts.append(f"\n\n---\n\n# {label}\n")
            parts.append(f"## {title}\n")
            if subtitle:
                parts.append(f"\n_{subtitle}_\n")
            if author:
                parts.append(f"\n{author}")
            if org:
                parts.append(f"\n_{org}_")
            parts.append(f"\n_{_misc_label('generated_on', lang)} : {pub_date}_")

        elif key == "toc":
            parts.append(f"\n\n---\n\n# {label}\n")
            parts.append(_build_structured_toc(main_sections, labels, classified))

        else:
            # Sections front matter comme "preface"
            _render_section(key, sep=(i > 0))

    # ── Main Sections ─────────────────────────────────────────────────────────
    for key in main_sections:
        _render_section(key)

    # ── Back Matter ───────────────────────────────────────────────────────────
    for key in back_matter:
        _render_section(key)

    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée public
# ─────────────────────────────────────────────────────────────────────────────

def build_publication(project_name: str) -> Path | None:
    """
    Construit publication.md depuis le manuscrit éditorial,
    en appliquant la structure du mode de publication actif.

    Sélection de la source :
      1. manuscript_rewritten.md  (prioritaire)
      2. manuscript_structured.md (fallback)

    Retourne le chemin de publication.md généré, ou None si aucune source.
    """
    final_dir = SORTIE_DIR / project_name / "final"
    pub_dir   = SORTIE_DIR / project_name / "publication"
    pub_path  = pub_dir / "publication.md"

    # ── Sélection de la source ────────────────────────────────────────────────
    rewritten_path  = final_dir / "manuscript_rewritten.md"
    structured_path = final_dir / "manuscript_structured.md"

    if rewritten_path.exists():
        source_path = rewritten_path
        source_name = "manuscript_rewritten.md"
    elif structured_path.exists():
        source_path = structured_path
        source_name = "manuscript_structured.md"
        print(
            f"[publication_builder] manuscript_rewritten.md absent — "
            f"fallback sur {source_name}"
        )
    else:
        print(
            f"[publication_builder] ERREUR : aucun manuscrit source trouvé "
            f"pour le projet « {project_name} »."
        )
        log_event({
            "step":    "publication_builder",
            "project": project_name,
            "action":  "error",
            "error":   "no_source_manuscript",
        })
        return None

    print(f"[publication_builder] Construction publication — source : {source_name}")
    log_event({
        "step":    "publication_builder",
        "project": project_name,
        "action":  "start",
        "source":  source_name,
    })

    # ── Lecture ───────────────────────────────────────────────────────────────
    text = source_path.read_text(encoding="utf-8")

    # ── Langue documentaire ───────────────────────────────────────────────────
    lang = get_document_language(project_name, fallback_text=text)
    print(f"[publication_builder] Langue documentaire : {lang}")
    log_event({
        "step":     "publication_builder",
        "project":  project_name,
        "action":   "language_detected",
        "language": lang,
    })

    # ── Mode de publication ───────────────────────────────────────────────────
    state            = load_project_state(project_name)
    publication_mode = (state.get("publication_mode") or "BOOK").strip().upper()
    structure        = get_publication_structure(publication_mode, lang)

    print(f"[publication_builder] Mode de publication : {publication_mode}")
    print(
        f"[publication_builder] Structure chargée : "
        f"front={structure['front_matter']} | "
        f"main={structure['main_sections']} | "
        f"back={structure['back_matter']}"
    )
    log_event({
        "step":          "publication_builder",
        "project":       project_name,
        "action":        "structure_loaded",
        "mode":          publication_mode,
        "front_matter":  structure["front_matter"],
        "main_sections": structure["main_sections"],
    })

    # ── Métadonnées de publication ────────────────────────────────────────────
    metadata = get_publication_metadata(project_name)
    print(
        f"[publication_builder] Métadonnées chargées — "
        f"titre={metadata['title']!r} | auteur={metadata['author']!r}"
    )
    log_event({
        "step":    "publication_builder",
        "project": project_name,
        "action":  "metadata_loaded",
        "title":   metadata["title"],
        "author":  metadata["author"],
    })

    # ── Parsing et classification ─────────────────────────────────────────────
    sections   = _parse_sections(text)
    classified = _classify_sections(sections)

    title_from_meta = metadata.get("title", "").strip()
    title_from_ms   = _detect_title(sections, project_name)
    title           = title_from_meta if title_from_meta else title_from_ms

    n_chapters = len(classified["chapters"])
    print(
        f"[publication_builder] Titre : « {title} » | "
        f"intro={'oui' if classified['intro'] else 'non'} | "
        f"chapitres={n_chapters} | "
        f"conclusion={'oui' if classified['conclusion'] else 'non'}"
    )

    # ── Assemblage structuré ──────────────────────────────────────────────────
    content = _assemble_structured_publication(
        title, project_name, lang, classified, structure, metadata
    )

    # ── Écriture ──────────────────────────────────────────────────────────────
    pub_dir.mkdir(parents=True, exist_ok=True)
    pub_path.write_text(content, encoding="utf-8")

    print(f"[publication_builder] Publication structurée générée : {pub_path}")
    log_event({
        "step":             "publication_builder",
        "project":          project_name,
        "action":           "generated",
        "publication_path": str(pub_path),
        "mode":             publication_mode,
    })

    # ── Mise à jour du project_state ──────────────────────────────────────────
    now = datetime.now().isoformat(timespec="seconds")
    state["publication"].update({
        "generated":          True,
        "publication_path":   str(pub_path),
        "publication_mode":   publication_mode,
        "structure_applied":  True,
        "source":             source_name,
        "language":           lang,
        "title":              title,
        "generated_at":       now,
    })
    save_project_state(project_name, state)

    print(f"[publication_builder] project_state.json mis à jour.")
    return pub_path
