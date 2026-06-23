"""
Nettoyage des sorties IA parasites et des métadonnées techniques
avant publication.

Fonctions principales :
  clean_ai_artifacts(markdown)         → retire les sorties IA parasites
  remove_technical_metadata(markdown)  → retire les métadonnées techniques
  clean_publication_markdown(markdown) → pipeline complet de nettoyage
"""

from __future__ import annotations

import re


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
    """
    text = markdown

    for pattern in _AI_ARTIFACT_PATTERNS:
        text = pattern.sub("", text)

    # Nettoyage des lignes vides multiples laissées par les suppressions
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    return text.strip()


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

    Retourne False si le titre est une métadonnée technique ou un artefact.
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
