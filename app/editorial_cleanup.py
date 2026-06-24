"""
Editorial Cleanup — Nettoyage des artefacts techniques et traces IA
d'un texte éditorial issu du pipeline de traitement automatique.

Ce module est indépendant du pipeline principal. Il n'accède à aucun
fichier, n'appelle aucun modèle IA, et ne modifie aucun état projet.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Lignes à supprimer si elles *contiennent* l'un de ces sous-chaînes
# (comparaison insensible à la casse)
# ---------------------------------------------------------------------------

_LINE_BLACKLIST: list[str] = [
    # Marqueurs techniques internes
    "Document final",
    "Projet :",
    "Généré le",
    "Nombre de chunks",
    "Chunks avec corrections",
    "chunk_",
    "Partie ",
    "*(révisé)*",
    "*(revisé)*",
    "*(revise)*",
    "révisé",
    "processed/",
    "corrections/",
    # Phrases IA parasites
    "Let me know if",
    "This structured format preserves",
    "This structured summary preserves",
    "Here is",
    "Below is",
    "I hope this helps",
    "As an AI",
    "Possible Interpretations",
    "Possible Contexts",
    "Questions for Further Clarity",
    "Questions for Further Exploration",
    "Possible Next Steps",
    "Translation Summary",
    "Summary in English",
    "Summary in French",
    "For clarity",
    "This summary",
    "This overview",
    "further refinements",
]

# Séparateurs techniques : lignes composées uniquement de ─ ═ = - _ *
# Minimum 8 caractères pour ne pas supprimer le --- Markdown légitime (3 tirets).
_SEPARATOR_RE = re.compile(r"^[\-─═=_*]{8,}\s*$")

# Timestamps : [MM:SS -> MM:SS] ou [HH:MM:SS -> HH:MM:SS], avec ou sans **
# Exemples : [13:14 -> 13:15]  **[00:01:22 -> 00:01:45]**
_TIMESTAMP_RE = re.compile(
    r"\*{0,2}"
    r"\[\d{1,2}:\d{2}(?::\d{2})?\s*->\s*\d{1,2}:\d{2}(?::\d{2})?\]"
    r"\*{0,2}"
)

# Résidus **  ** vides laissés après suppression du timestamp
_EMPTY_BOLD_RE = re.compile(r"\*\*\s*\*\*")


# ---------------------------------------------------------------------------
# Fonction publique
# ---------------------------------------------------------------------------

def clean_editorial_artifacts(text: str, remove_timestamps: bool = True) -> str:
    """
    Nettoie les artefacts techniques et les traces IA d'un texte éditorial.
    Retourne uniquement le texte nettoyé.

    Opérations appliquées dans l'ordre :
      1. Suppression des lignes contenant des marqueurs techniques.
      2. Suppression des séparateurs techniques (─────, ═════, -----, etc.).
      3. Suppression des timestamps (si remove_timestamps=True) ;
         si une ligne contient aussi du texte utile, seul le timestamp
         est retiré.
      4. Nettoyage des résidus **  ** et des espaces multiples après
         suppression des timestamps.
      5. Normalisation générale des espaces (doubles espaces, espaces avant
         ponctuation, strip de chaque ligne).
      6. Réduction des blocs de lignes vides consécutives à une seule.
    """
    lines = text.splitlines()
    cleaned: list[str] = []

    for line in lines:
        # ── 1. Séparateurs techniques → ligne entière supprimée ──────────────
        if _SEPARATOR_RE.match(line):
            continue

        # ── 2. Mot-clé blacklisté → ligne entière supprimée ─────────────────
        if any(kw.lower() in line.lower() for kw in _LINE_BLACKLIST):
            continue

        # ── 3. Timestamps → suppression partielle (texte utile conservé) ─────
        if remove_timestamps:
            line = _TIMESTAMP_RE.sub("", line)
            # Résidus **  ** laissés par la suppression
            line = _EMPTY_BOLD_RE.sub("", line)

        # ── 4–5. Normalisation des espaces (toujours, pas seulement timestamps)
        # Puce suivie de plusieurs espaces : •   texte → • texte
        line = re.sub(r"•\s{2,}", "• ", line)
        # Doubles espaces résiduels
        line = re.sub(r"  +", " ", line)
        # Espaces avant ponctuation
        line = re.sub(r" ([,.:;!?»])", r"\1", line)
        # Strip début/fin de ligne
        line = line.strip()

        cleaned.append(line)

    # ── 6. Max 1 ligne vide consécutive ──────────────────────────────────────
    result: list[str] = []
    blank_count = 0
    for line in cleaned:
        if line == "":
            blank_count += 1
            if blank_count <= 1:
                result.append("")
        else:
            blank_count = 0
            result.append(line)

    return "\n".join(result)
