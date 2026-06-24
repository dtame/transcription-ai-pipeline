"""
Publication Mode Engine — Structures éditoriales par mode de publication.

Fournit la structure attendue (sections et libellés) selon le mode de
publication choisi.  Le moteur influence la *structure* du livrable ;
l'apparence visuelle reste gérée par publication_theme.py.

Modes supportés :
    BOOK, BOOKLET, SERMON, TRAINING,
    CONSULTING_REPORT, CORPORATE_REPORT, PODCAST
"""

from __future__ import annotations

VALID_MODES: frozenset[str] = frozenset({
    "BOOK",
    "BOOKLET",
    "SERMON",
    "TRAINING",
    "CONSULTING_REPORT",
    "CORPORATE_REPORT",
    "PODCAST",
})

DEFAULT_MODE = "BOOK"


# ─────────────────────────────────────────────────────────────────────────────
# Définitions de structures par mode
#
# Chaque mode contient :
#   front_matter   — sections avant le corps (couverture, titre, TOC…)
#   main_sections  — sections du corps principal
#   back_matter    — sections après le corps
#   bulk_key       — clé qui recevra tout le contenu non attribué
#   labels.fr / labels.en — libellés traduits pour chaque clé
# ─────────────────────────────────────────────────────────────────────────────

_STRUCTURES: dict[str, dict] = {
    "BOOK": {
        "front_matter":  ["cover", "title_page", "toc", "preface"],
        "main_sections": ["introduction", "chapters", "conclusion"],
        "back_matter":   [],
        "bulk_key":      "chapters",
        "labels": {
            "fr": {
                "cover":        "Couverture",
                "title_page":   "Page de titre",
                "toc":          "Table des matières",
                "preface":      "Préface",
                "introduction": "Introduction",
                "chapters":     "Chapitres",
                "conclusion":   "Conclusion",
            },
            "en": {
                "cover":        "Cover",
                "title_page":   "Title Page",
                "toc":          "Table of Contents",
                "preface":      "Preface",
                "introduction": "Introduction",
                "chapters":     "Chapters",
                "conclusion":   "Conclusion",
            },
        },
    },

    "BOOKLET": {
        "front_matter":  ["cover", "toc"],
        "main_sections": ["introduction", "sections", "conclusion"],
        "back_matter":   [],
        "bulk_key":      "sections",
        "labels": {
            "fr": {
                "cover":        "Couverture",
                "toc":          "Table des matières",
                "introduction": "Introduction",
                "sections":     "Sections",
                "conclusion":   "Conclusion",
            },
            "en": {
                "cover":        "Cover",
                "toc":          "Table of Contents",
                "introduction": "Introduction",
                "sections":     "Sections",
                "conclusion":   "Conclusion",
            },
        },
    },

    "SERMON": {
        "front_matter":  ["cover"],
        "main_sections": [
            "main_message",
            "key_points",
            "biblical_references",
            "practical_applications",
            "prayer_conclusion",
        ],
        "back_matter":   [],
        "bulk_key":      "main_message",
        "labels": {
            "fr": {
                "cover":                  "Couverture",
                "main_message":           "Texte principal",
                "key_points":             "Points clés",
                "biblical_references":    "Références bibliques",
                "practical_applications": "Applications pratiques",
                "prayer_conclusion":      "Prière / Conclusion",
            },
            "en": {
                "cover":                  "Cover",
                "main_message":           "Main Message",
                "key_points":             "Key Points",
                "biblical_references":    "Biblical References",
                "practical_applications": "Practical Applications",
                "prayer_conclusion":      "Prayer / Conclusion",
            },
        },
    },

    "TRAINING": {
        "front_matter":  ["cover", "title_page", "toc"],
        "main_sections": [
            "objectives",
            "modules",
            "exercises",
            "reflection_questions",
            "conclusion",
        ],
        "back_matter":   [],
        "bulk_key":      "modules",
        "labels": {
            "fr": {
                "cover":               "Couverture",
                "title_page":          "Page de titre",
                "toc":                 "Table des matières",
                "objectives":          "Objectifs",
                "modules":             "Modules",
                "exercises":           "Exercices",
                "reflection_questions": "Questions de réflexion",
                "conclusion":          "Conclusion",
            },
            "en": {
                "cover":               "Cover",
                "title_page":          "Title Page",
                "toc":                 "Table of Contents",
                "objectives":          "Objectives",
                "modules":             "Modules",
                "exercises":           "Exercises",
                "reflection_questions": "Reflection Questions",
                "conclusion":          "Conclusion",
            },
        },
    },

    "CONSULTING_REPORT": {
        "front_matter":  ["cover", "title_page", "toc"],
        "main_sections": [
            "executive_summary",
            "context",
            "diagnosis",
            "recommendations",
            "action_plan",
            "conclusion",
        ],
        "back_matter":   [],
        "bulk_key":      "diagnosis",
        "labels": {
            "fr": {
                "cover":             "Couverture",
                "title_page":        "Page de titre",
                "toc":               "Table des matières",
                "executive_summary": "Résumé exécutif",
                "context":           "Contexte",
                "diagnosis":         "Diagnostic",
                "recommendations":   "Recommandations",
                "action_plan":       "Plan d'action",
                "conclusion":        "Conclusion",
            },
            "en": {
                "cover":             "Cover",
                "title_page":        "Title Page",
                "toc":               "Table of Contents",
                "executive_summary": "Executive Summary",
                "context":           "Context",
                "diagnosis":         "Diagnosis",
                "recommendations":   "Recommendations",
                "action_plan":       "Action Plan",
                "conclusion":        "Conclusion",
            },
        },
    },

    "CORPORATE_REPORT": {
        "front_matter":  ["cover", "title_page", "toc"],
        "main_sections": [
            "executive_summary",
            "context",
            "analysis",
            "findings",
            "recommendations",
            "conclusion",
        ],
        "back_matter":   [],
        "bulk_key":      "analysis",
        "labels": {
            "fr": {
                "cover":             "Couverture",
                "title_page":        "Page de titre",
                "toc":               "Table des matières",
                "executive_summary": "Résumé exécutif",
                "context":           "Contexte",
                "analysis":          "Analyse",
                "findings":          "Résultats",
                "recommendations":   "Recommandations",
                "conclusion":        "Conclusion",
            },
            "en": {
                "cover":             "Cover",
                "title_page":        "Title Page",
                "toc":               "Table of Contents",
                "executive_summary": "Executive Summary",
                "context":           "Context",
                "analysis":          "Analysis",
                "findings":          "Findings",
                "recommendations":   "Recommendations",
                "conclusion":        "Conclusion",
            },
        },
    },

    "PODCAST": {
        "front_matter":  ["cover"],
        "main_sections": [
            "episode_summary",
            "highlights",
            "key_quotes",
            "resources",
            "conclusion",
        ],
        "back_matter":   [],
        "bulk_key":      "highlights",
        "labels": {
            "fr": {
                "cover":           "Couverture",
                "episode_summary": "Résumé de l'épisode",
                "highlights":      "Temps forts",
                "key_quotes":      "Citations clés",
                "resources":       "Ressources",
                "conclusion":      "Conclusion",
            },
            "en": {
                "cover":           "Cover",
                "episode_summary": "Episode Summary",
                "highlights":      "Highlights",
                "key_quotes":      "Key Quotes",
                "resources":       "Resources",
                "conclusion":      "Conclusion",
            },
        },
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée public
# ─────────────────────────────────────────────────────────────────────────────

def get_publication_structure(
    publication_mode: str,
    document_language: str = "en",
) -> dict:
    """
    Retourne la structure éditoriale attendue selon le mode de publication.

    Args:
        publication_mode:  Mode parmi VALID_MODES. Fallback sur DEFAULT_MODE.
        document_language: Code langue ("fr" ou "en"). Fallback sur "en".

    Returns:
        Dictionnaire avec :
          mode, front_matter, main_sections, back_matter,
          bulk_key, section_labels.
    """
    mode = (publication_mode or "").strip().upper()
    if mode not in VALID_MODES:
        mode = DEFAULT_MODE

    lang = (document_language or "").strip().lower()
    if lang not in ("fr", "en"):
        lang = "en"

    struct = _STRUCTURES[mode]
    labels = struct["labels"].get(lang, struct["labels"]["en"])

    return {
        "mode":           mode,
        "front_matter":   list(struct["front_matter"]),
        "main_sections":  list(struct["main_sections"]),
        "back_matter":    list(struct["back_matter"]),
        "bulk_key":       struct.get("bulk_key"),
        "section_labels": dict(labels),
    }
