"""
Document Language — Gestion centralisée de la langue documentaire.

Règle métier :
  - Si le document est majoritairement en anglais → langue = "en"
  - Si le document est majoritairement en français → langue = "fr"
  - En cas d'égalité → "en" par défaut

Contraintes :
  - Aucun appel Ollama ou modèle IA
  - Aucune API externe
  - Détection simple, déterministe, par mots fréquents
  - Retourne uniquement "en" ou "fr"
"""

from __future__ import annotations

import re

from app.logger import log_event
from app.project_state import load_project_state, save_project_state


# ---------------------------------------------------------------------------
# Marqueurs linguistiques
# ---------------------------------------------------------------------------

ENGLISH_MARKERS: list[str] = [
    "the", "and", "of", "to", "in", "that", "is", "with",
    "for", "as", "faith", "god", "lord", "church", "spiritual",
    "summary", "chapter", "introduction", "conclusion",
]

FRENCH_MARKERS: list[str] = [
    "le", "la", "les", "des", "de", "du", "et", "à", "que",
    "qui", "dans", "avec", "pour", "foi", "dieu", "seigneur",
    "église", "spirituel", "résumé", "chapitre", "introduction",
    "conclusion",
]

# ---------------------------------------------------------------------------
# Libellés standards par langue
# ---------------------------------------------------------------------------

_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "table_of_contents": "Table of Contents",
        "introduction": "Introduction",
        "conclusion": "Conclusion",
        "chapter": "Chapter",
        "manuscript": "Editorial Manuscript",
        "project": "Project",
    },
    "fr": {
        "table_of_contents": "Table des matières",
        "introduction": "Introduction",
        "conclusion": "Conclusion",
        "chapter": "Chapitre",
        "manuscript": "Manuscrit éditorial",
        "project": "Projet",
    },
}


# ---------------------------------------------------------------------------
# Fonctions publiques
# ---------------------------------------------------------------------------

def detect_dominant_language(text: str) -> str:
    """
    Détecte la langue dominante du texte.

    Algorithme :
      - Tokenise le texte en mots en minuscules.
      - Compte les occurrences des marqueurs anglais et français.
      - Si anglais >= français → "en", sinon → "fr".

    Retourne "en" ou "fr".
    """
    words = re.findall(r"\b\w+\b", text.lower())
    word_set = set(words)

    en_count = sum(words.count(marker) for marker in ENGLISH_MARKERS if marker in word_set)
    fr_count = sum(words.count(marker) for marker in FRENCH_MARKERS if marker in word_set)

    detected = "en" if en_count >= fr_count else "fr"

    log_event({
        "step": "document_language",
        "action": "detect",
        "detected": detected,
        "en_markers": en_count,
        "fr_markers": fr_count,
    })
    print(
        f"[document_language] Langue détectée : {detected} "
        f"(EN={en_count}, FR={fr_count})"
    )

    return detected


def get_language_labels(document_language: str) -> dict[str, str]:
    """
    Retourne les libellés standards selon la langue documentaire.

    Retourne toujours un dict valide ; bascule sur "en" si la langue est inconnue.
    """
    return _LABELS.get(document_language, _LABELS["en"])


def save_document_language(
    project_name: str,
    language: str,
    source: str = "dominant_text",
) -> None:
    """
    Sauvegarde la langue documentaire dans project_state.json.

    Met à jour :
      - state["language"]             → section globale
      - state["editorial"]["document_language"]
    """
    state = load_project_state(project_name)

    state["language"] = {
        "document_language": language,
        "source": source,
    }
    state.setdefault("editorial", {})["document_language"] = language

    save_project_state(project_name, state)

    log_event({
        "step": "document_language",
        "project": project_name,
        "action": "save",
        "language": language,
        "source": source,
    })
    print(
        f"[document_language] Langue sauvegardée : {language} "
        f"(source={source}) → project_state.json"
    )


def get_document_language(
    project_name: str,
    fallback_text: str | None = None,
) -> str:
    """
    Lit la langue documentaire depuis project_state.json.

    Ordre de priorité :
      1. state["language"]["document_language"] (section globale)
      2. state["editorial"]["document_language"] (section éditoriale)
      3. Détection depuis fallback_text (si fourni)
      4. "en" par défaut

    Retourne "en" ou "fr".
    """
    state = load_project_state(project_name)

    # Vérifier la section globale
    lang = state.get("language", {}).get("document_language")
    if lang in ("en", "fr"):
        print(f"[document_language] Langue lue depuis project_state (global) : {lang}")
        return lang

    # Vérifier la section éditoriale
    lang = state.get("editorial", {}).get("document_language")
    if lang in ("en", "fr"):
        print(f"[document_language] Langue lue depuis project_state (editorial) : {lang}")
        return lang

    # Détection depuis le texte de secours
    if fallback_text and fallback_text.strip():
        print("[document_language] Langue absente du state — détection depuis le texte")
        return detect_dominant_language(fallback_text)

    # Valeur par défaut
    print("[document_language] Langue non trouvée — défaut : en")
    return "en"


# ---------------------------------------------------------------------------
# Helpers booléens
# ---------------------------------------------------------------------------

def is_english(language: str) -> bool:
    return language == "en"


def is_french(language: str) -> bool:
    return language == "fr"
