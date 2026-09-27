"""
Nettoyage des sorties IA parasites et des métadonnées techniques
avant publication.

Fonctions principales :
  clean_ai_artifacts(markdown)         → retire les sorties IA parasites (phrases + sections)
  clean_ai_section_headings(markdown)  → retire les sections à titres parasites IA
  remove_technical_metadata(markdown)  → retire les métadonnées techniques
  is_toc_eligible_heading(h, level)    → vérifie si un titre peut figurer en table des matières
  clean_publication_markdown(markdown) → pipeline complet de nettoyage
"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Titres de sections IA parasites (anglais + français)
# Ces titres appartiennent à des rapports d'analyse IA, pas à des documents éditoriaux.
# ---------------------------------------------------------------------------

_PARASITIC_HEADING_TITLES: frozenset[str] = frozenset({
    # --- Anglais ---
    "summary",
    "summaries",
    "key themes",
    "key theme",
    "key themes and points",
    "key takeaways",
    "key takeaway",
    "key points",
    "key point",
    "key concepts",
    "key concept",
    "key ideas",
    "key findings",
    "final notes",
    "final note",
    "final insight",
    "final insights",
    "final thoughts",
    "final remarks",
    "questions for clarification",
    "questions for further exploration",
    "questions for reflection",
    "clarification questions",
    "possible interpretations",
    "possible interpretation",
    "possible context",
    "unresolved questions",
    "unresolved issues",
    "language notes",
    "translation notes",
    "translation note",
    "french to english translation",
    "translation and summary",
    "translation",
    "cultural context",
    "cultural notes",
    "cultural note",
    "biblical references",
    "biblical reference",
    "religious references",
    "religious reference",
    "core themes",
    "core theme",
    "structure and flow",
    "notable style and tone",
    "style and tone",
    "overview",
    "interim conclusion",
    "overall summary",
    "analysis",
    "context",
    "background",
    "notes",
    "observations",
    "additional notes",
    "additional observations",
    "further notes",
    "commentary",
    "remarks",
    # --- Français ---
    "résumé",
    "résumés",
    "synthèse",
    "thèmes principaux",
    "thème principal",
    "thèmes clés",
    "thème clé",
    "points clés",
    "point clé",
    "éléments clés",
    "élément clé",
    "à retenir",
    "idées clés",
    "idée clé",
    "concepts clés",
    "concept clé",
    "notes finales",
    "note finale",
    "remarques finales",
    "remarque finale",
    "réflexions finales",
    "réflexion finale",
    "questions de clarification",
    "questions d'exploration",
    "questions pour aller plus loin",
    "interprétations possibles",
    "interprétation possible",
    "questions non résolues",
    "problèmes non résolus",
    "notes linguistiques",
    "note linguistique",
    "notes de traduction",
    "note de traduction",
    "traduction",
    "contexte culturel",
    "notes culturelles",
    "note culturelle",
    "références bibliques",
    "référence biblique",
    "références religieuses",
    "référence religieuse",
    "conclusion provisoire",
    "vue d'ensemble",
    "analyse",
    "contexte",
    "observations",
    "remarques",
    "notes complémentaires",
    "observations complémentaires",
})

# Préfixes parasites : le titre commence par l'un de ces mots (insensible à la casse)
_PARASITIC_HEADING_PREFIXES: tuple[str, ...] = (
    "key ",
    "summary of",
    "overview of",
    "analysis of",
    "résumé de",
    "synthèse de",
    "analyse de",
)

# ---------------------------------------------------------------------------
# Patterns de sorties IA parasites
# ---------------------------------------------------------------------------

_AI_ARTIFACT_PATTERNS: list[re.Pattern] = [
    # Blocs <think>...</think> (qwen3, deepseek, etc.)
    re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE),
    # /think en début de ligne ou inline
    re.compile(r"^/think\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"\s*/think\s*", re.IGNORECASE),
    # Blocs \boxed{...}
    re.compile(r"\\boxed\{[^}]*\}", re.DOTALL),
    # Lignes "Final Answer:" ou "**Final Answer:**"
    re.compile(
        r"^\*{0,2}Final Answer[\s:]*\*{0,2}.*$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # Phrases d'introduction analytiques
    re.compile(
        r"^(The provided text|This text (is|appears|seems)|"
        r"Here('?s| is) (a |the )(structured |brief |complete )?summary|"
        r"Here('?s| is) (the |a |an )?analysis|"
        r"I('ve| have) (analyzed|reviewed|processed)|"
        r"Below (is|you will find)|"
        r"The following (is|are)|"
        r"Based on (the|this) (text|transcript|content)).*$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # Phrases d'offre d'aide
    re.compile(
        r"^(If you need|Let me know|Feel free to (ask|contact)|"
        r"Don't hesitate|Please (let me|feel free)|"
        r"I hope this helps|Is there anything else).*$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # Note: / Remarque: en début de paragraphe (si suivi de banalités)
    re.compile(
        r"^(Note\s*:|Remarque\s*:|N\.B\.\s*:)\s*"
        r"(This is a transcript|The text (above|below|provided)).*$",
        re.MULTILINE | re.IGNORECASE,
    ),
]

# ---------------------------------------------------------------------------
# Patterns de métadonnées techniques
# ---------------------------------------------------------------------------

_TECHNICAL_METADATA_PATTERNS: list[re.Pattern] = [
    # En-tête de document final
    re.compile(
        r"^#\s*Document final\s*[—–-].*$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # Lignes "- Projet :", "- Chunk :", "- Généré le :" (avec ou sans backticks)
    re.compile(
        r"^[-*]\s*(Projet|Chunk|Généré le)\s*:.*$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # Lignes inline "Projet : nom", "Chunk : 001/008", "Généré le : ..."
    re.compile(
        r"^(Projet|Chunk|Généré le)\s*:\s*.+$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # Lignes "# Projet :", "# Chunk :", "# Généré le :"
    re.compile(
        r"^#\s*(Projet|Chunk|Généré le)\s*:.*$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # Lignes "- Nombre de chunks fusionnés :", "- Chunks avec corrections"
    re.compile(
        r"^[-*]\s*(Nombre de chunks|Chunks avec corrections|Chunks sans corrections).*$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # Titres de section "## Partie X — chunk_XXX.md" (em-dash, en-dash, ou tiret(s))
    re.compile(
        r"^#{1,3}\s*Partie\s+\d+\s*[-—–]+\s*chunk_\d+\.md.*$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # Noms de fichiers chunk_XXX.md seuls sur une ligne ou dans un titre
    re.compile(
        r"^#{0,3}\s*chunk_\d{3}(?:\.(?:md|txt))?\s*(\*\(.*?\)\*)?\s*$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # Longues lignes de séparateurs bruts (===, ---) de 10+ caractères répétés
    re.compile(
        r"^[=\-_*]{10,}\s*$",
        re.MULTILINE,
    ),
    # Longues lignes de caractères décoratifs (═══, ───)
    re.compile(
        r"^[═─━┄┅·•▪■]{5,}\s*$",
        re.MULTILINE,
    ),
    # Lignes "Document final — nom_projet" comme paragraphe normal
    re.compile(
        r"^Document final\s*[—–-]\s*\w+\s*$",
        re.MULTILINE | re.IGNORECASE,
    ),
]

# Titres techniques dans les H1/H2/H3
_TECHNICAL_HEADING_TITLES = re.compile(
    r"^#{1,3}\s*(Document final|Projet\s*:|Chunk\s*:|Généré le|"
    r"Nombre de chunks|Chunks avec corrections|"
    r"Traitement IA simulé|Contenu original)\s*",
    re.MULTILINE | re.IGNORECASE,
)


def _is_parasitic_heading_title(title: str) -> bool:
    """
    Retourne True si le titre d'un heading correspond à une section IA parasite.
    Vérifie la liste exacte et les préfixes parasites connus.
    """
    normalized = title.strip().lower()
    # Retirer le gras/italique markdown éventuel
    normalized = re.sub(r"^\*{1,2}|\*{1,2}$", "", normalized).strip()
    # Retirer la numérotation de début (ex. "1. Summary", "I. Key Themes")
    normalized = re.sub(r"^[\dIVXivx]+[.)]\s*", "", normalized).strip()

    if normalized in _PARASITIC_HEADING_TITLES:
        return True

    for prefix in _PARASITIC_HEADING_PREFIXES:
        if normalized.startswith(prefix):
            return True

    return False


def clean_ai_section_headings(markdown: str) -> str:
    """
    Supprime les sections dont le titre est un artefact d'analyse IA.

    Stratégie :
    - Découpe le document en blocs délimités par les titres Markdown (H1-H3).
    - Supprime tout bloc dont le titre est dans la liste parasite.
    - Conserve le contenu du bloc si le titre est éditorial.

    Logs :
        [structure] Titres parasites supprimés : N
    """
    lines = markdown.splitlines(keepends=True)
    heading_re = re.compile(r"^(#{1,3})\s+(.+)$")

    # Découper en sections : liste de (is_heading, heading_level, heading_title, [lignes])
    sections: list[tuple[bool, int, str, list[str]]] = []
    current_lines: list[str] = []
    current_heading: tuple[int, str] | None = None  # (level, title)

    for line in lines:
        m = heading_re.match(line.rstrip("\n"))
        if m:
            # Sauvegarder la section précédente
            sections.append((current_heading is not None, current_heading, current_lines))
            current_heading = (len(m.group(1)), m.group(2).strip())
            current_lines = [line]
        else:
            current_lines.append(line)

    # Dernière section
    sections.append((current_heading is not None, current_heading, current_lines))

    removed = 0
    kept_parts: list[str] = []

    for has_heading, heading, section_lines in sections:
        if not has_heading or heading is None:
            kept_parts.append("".join(section_lines))
            continue

        level, title = heading
        if _is_parasitic_heading_title(title):
            removed += 1
            continue

        kept_parts.append("".join(section_lines))

    if removed:
        print(f"[structure] Titres parasites supprimés : {removed}")

    result = "".join(kept_parts)
    result = re.sub(r"\n{4,}", "\n\n\n", result)
    return result.strip()


def clean_ai_artifacts(markdown: str) -> str:
    """
    Supprime les sorties IA parasites d'un texte Markdown.

    Retire :
    - Blocs <think>...</think>
    - /think
    - \\boxed{...}
    - "Final Answer:"
    - Phrases analytiques introductives
    - Offres d'aide ("If you need...")
    - Sections entières à titres parasites IA (Summary, Key Themes, etc.)
    """
    text = markdown

    for pattern in _AI_ARTIFACT_PATTERNS:
        text = pattern.sub("", text)

    # Suppression des sections à titres parasites
    text = clean_ai_section_headings(text)

    # Nettoyage des lignes vides multiples laissées par les suppressions
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    return text.strip()


def is_toc_eligible_heading(heading: str, level: int) -> bool:
    """
    Retourne True si un titre peut figurer dans la table des matières.

    Règles :
    - Seuls H1 et H2 sont éligibles par défaut (level ≤ 2).
    - Les titres parasites IA sont exclus.
    - Les titres techniques (chunk_, Projet :, etc.) sont exclus.
    - Les titres en gras inline (**texte**) sans préfixe # sont exclus.
    - Les titres trop courts (< 2 caractères) ou purement numériques sont exclus.
    - Les titres dupliqués sont gérés en amont par extract_headings.

    Args:
        heading: texte du titre (sans les # du préfixe Markdown).
        level:   niveau Markdown (1 = H1, 2 = H2, 3 = H3, ...).

    Returns:
        True si le titre est éligible à la table des matières.
    """
    if level > 2:
        return False

    stripped = heading.strip()

    if len(stripped) < 2:
        return False

    # Titre purement numérique ou composé uniquement de tirets/chiffres
    if re.match(r"^[\d\s\-—–.]+$", stripped):
        return False

    # Titre en gras seul sans niveau Markdown (ne devrait pas arriver ici, mais sécurité)
    if re.match(r"^\*{1,2}.+\*{1,2}$", stripped) and not stripped.startswith("#"):
        return False

    # Titre parasite IA
    if _is_parasitic_heading_title(stripped):
        return False

    # Titre technique (chunk_, Projet :, etc.)
    if not is_publishable_heading(stripped):
        return False

    return True


def remove_technical_metadata(markdown: str) -> str:
    """
    Supprime les métadonnées techniques d'un Markdown de publication.

    Retire :
    - En-têtes "# Document final — projet"
    - Lignes "- Projet :", "- Chunk :", "- Généré le :"
    - Lignes "- Nombre de chunks fusionnés :"
    - Titres "## Partie X — chunk_XXX.md"
    - Noms de fichiers chunk_XXX.md
    - Longues lignes de séparateurs bruts
    """
    text = markdown

    for pattern in _TECHNICAL_METADATA_PATTERNS:
        text = pattern.sub("", text)

    # Titres techniques H1-H3
    text = _TECHNICAL_HEADING_TITLES.sub("", text)

    # Nettoyage des lignes vides multiples
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    return text.strip()


def is_publishable_heading(title: str) -> bool:
    """
    Retourne True si le titre est un vrai titre éditorial publiable.

    Retourne False si le titre est une métadonnée technique, un artefact IA,
    ou un titre parasite d'analyse.
    """
    lower = title.lower().strip()

    technical_keywords = [
        "chunk_",
        "projet :",
        "chunk :",
        "généré le",
        "généré",
        "document final",
        "document final —",
        "nombre de chunks",
        "chunks avec corrections",
        "chunks sans corrections",
        "traitement ia simulé",
        "contenu original",
        "partie x —",
        "séparateur de section",
    ]

    for kw in technical_keywords:
        if kw in lower:
            return False

    # Titre qui ressemble à "Partie N — chunk_XXX.md"
    if re.match(r"^partie\s+\d+\s*[-—–]+\s*chunk_", lower):
        return False

    # Titre purement numérique ou très court sans sens
    if re.match(r"^[\d\s\-—–]+$", lower):
        return False

    # Titre parasite d'analyse IA
    if _is_parasitic_heading_title(lower):
        return False

    return True


def clean_publication_markdown(markdown: str) -> str:
    """
    Pipeline complet de nettoyage pour publication.

    Étapes :
    1. Suppression des artefacts IA parasites
    2. Suppression des métadonnées techniques
    3. Nettoyage des espaces/lignes vides excessifs
    4. Nettoyage final des bords

    Ne supprime pas les vrais titres éditoriaux ni le contenu religieux/pédagogique.
    """
    text = markdown

    text = clean_ai_artifacts(text)
    text = remove_technical_metadata(text)

    # Séparateurs horizontaux Markdown "---" : garder un seul par série
    text = re.sub(r"(\n---\n){2,}", "\n---\n", text)

    # Lignes vides multiples → max 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
