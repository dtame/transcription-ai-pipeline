"""
Tests de nettoyage de la structure éditoriale.

Vérifie que :
- clean_ai_section_headings() supprime les sections à titres parasites IA
- clean_ai_artifacts() intègre le nettoyage de sections
- is_toc_eligible_heading() filtre correctement les titres parasites
- build_table_of_contents() ne produit aucun titre parasite
- extract_headings() avec toc_eligible_only=True exclut les parasites

Usage :
    python -m app.tests.test_structure_cleaner
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.publication_cleaner import (
    clean_ai_section_headings,
    clean_ai_artifacts,
    is_toc_eligible_heading,
    is_publishable_heading,
)
from app.publication_template_service import (
    extract_headings,
    build_table_of_contents,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_PASS = "OK"
_FAIL = "FAIL"
_results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    icon = _PASS if condition else _FAIL
    _results.append((name, condition, detail))
    status = f"[{icon}]"
    msg = f"  {status} {name}"
    if detail:
        msg += f"  ({detail})"
    print(msg)


# ─────────────────────────────────────────────────────────────────────────────
# Données de test
# ─────────────────────────────────────────────────────────────────────────────

_PARASITIC_HEADINGS_EN = [
    "Key Themes",
    "Summary",
    "Questions for Clarification",
    "Possible Interpretations",
    "Translation Notes",
    "Key Takeaways",
    "Final Notes",
    "Cultural Context",
    "Biblical References",
    "Core Themes",
    "Key Points",
    "Unresolved Questions",
    "Language Notes",
    "Final Insight",
    "Structure and Flow",
    "Notable Style and Tone",
    "Possible Context",
    "Analysis",
    "Overview",
    "Notes",
    "Observations",
]

_PARASITIC_HEADINGS_FR = [
    "Résumé",
    "Synthèse",
    "Thèmes principaux",
    "Points clés",
    "Questions de clarification",
    "Interprétations possibles",
    "Notes linguistiques",
    "Traduction",
    "Contexte culturel",
    "Références bibliques",
    "Conclusion provisoire",
    "Éléments clés",
    "À retenir",
]

_EDITORIAL_HEADINGS = [
    "Introduction",
    "Chapitre 1 — La foi",
    "Chapitre 2 — L'espérance",
    "Partie I — Les fondements",
    "La grâce de Dieu",
    "Le chemin de la guérison",
    "Conclusion",
]

_SAMPLE_DOCUMENT = """
# Introduction

Ce document traite de la foi et de l'espérance.

## Chapitre 1 — La foi

Le texte aborde la question de la foi dans le contexte moderne.

## Key Themes

- Faith
- Hope
- Love

## Summary

This chunk covers the main themes of the sermon.

## Chapitre 2 — L'espérance

Un développement sur l'espérance chrétienne.

## Questions for Clarification

1. What does "hope" mean here?
2. Is this doctrinal or experiential?

## Possible Interpretations

The text could be interpreted in multiple ways.

## Translation Notes

The original French uses "espérance" which differs from "espoir".

## Conclusion

Le document se conclut sur une invitation à la confiance.

## Résumé

Ce chapitre résume les points principaux.

## Thèmes principaux

- La foi
- L'espérance

## Points clés

- Point A
- Point B
"""


# ─────────────────────────────────────────────────────────────────────────────
# Tests : is_toc_eligible_heading
# ─────────────────────────────────────────────────────────────────────────────

def test_toc_eligible_parasitic_headings() -> None:
    print("\n[Test] is_toc_eligible_heading — titres parasites refusés")
    all_parasitic = _PARASITIC_HEADINGS_EN + _PARASITIC_HEADINGS_FR
    for heading in all_parasitic:
        result = is_toc_eligible_heading(heading, level=2)
        check(
            f"Refusé : '{heading}'",
            not result,
            "attendu False" if result else "",
        )


def test_toc_eligible_editorial_headings() -> None:
    print("\n[Test] is_toc_eligible_heading — titres éditoriaux acceptés")
    for heading in _EDITORIAL_HEADINGS:
        result = is_toc_eligible_heading(heading, level=2)
        check(
            f"Accepté : '{heading}'",
            result,
            "attendu True" if not result else "",
        )


def test_toc_eligible_h3_rejected() -> None:
    print("\n[Test] is_toc_eligible_heading — H3 rejeté par défaut")
    result = is_toc_eligible_heading("Sous-section importante", level=3)
    check("H3 rejeté", not result, "H3 ne doit pas être en TOC par défaut")


def test_toc_eligible_h1_accepted() -> None:
    print("\n[Test] is_toc_eligible_heading — H1 éditorial accepté")
    result = is_toc_eligible_heading("Introduction", level=1)
    check("H1 'Introduction' accepté", result)


# ─────────────────────────────────────────────────────────────────────────────
# Tests : clean_ai_section_headings
# ─────────────────────────────────────────────────────────────────────────────

def test_clean_section_removes_parasitic() -> None:
    print("\n[Test] clean_ai_section_headings — sections parasites supprimées")
    result = clean_ai_section_headings(_SAMPLE_DOCUMENT)

    for parasitic in _PARASITIC_HEADINGS_EN + _PARASITIC_HEADINGS_FR:
        heading_marker = f"## {parasitic}"
        present = heading_marker in result
        check(
            f"Section supprimée : '## {parasitic}'",
            not present,
            "encore présent" if present else "",
        )


def test_clean_section_keeps_editorial() -> None:
    print("\n[Test] clean_ai_section_headings — sections éditoriales conservées")
    result = clean_ai_section_headings(_SAMPLE_DOCUMENT)

    editorial_sections = [
        "## Chapitre 1 — La foi",
        "## Chapitre 2 — L'espérance",
        "## Conclusion",
        "# Introduction",
    ]
    for section in editorial_sections:
        present = section in result
        check(
            f"Section conservée : '{section}'",
            present,
            "manquant" if not present else "",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Tests : extract_headings avec toc_eligible_only=True
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_headings_toc_eligible() -> None:
    print("\n[Test] extract_headings(toc_eligible_only=True) — seuls les titres éditoriaux")
    headings = extract_headings(_SAMPLE_DOCUMENT, toc_eligible_only=True)
    titles = [h["title"] for h in headings]

    all_parasitic = _PARASITIC_HEADINGS_EN + _PARASITIC_HEADINGS_FR
    for parasitic in all_parasitic:
        present = any(t.lower() == parasitic.lower() for t in titles)
        check(
            f"Exclu de la TOC : '{parasitic}'",
            not present,
            f"trouvé dans {titles}" if present else "",
        )

    editorial_expected = ["Introduction", "Chapitre 1 — La foi", "Chapitre 2 — L'espérance", "Conclusion"]
    for ed in editorial_expected:
        present = any(t == ed for t in titles)
        check(
            f"Inclus dans la TOC : '{ed}'",
            present,
            "absent" if not present else "",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Tests : build_table_of_contents
# ─────────────────────────────────────────────────────────────────────────────

def test_build_toc_no_parasitic() -> None:
    print("\n[Test] build_table_of_contents — aucun titre parasite dans le résultat")
    headings = extract_headings(_SAMPLE_DOCUMENT, toc_eligible_only=True)
    toc = build_table_of_contents(headings)

    all_parasitic = _PARASITIC_HEADINGS_EN + _PARASITIC_HEADINGS_FR
    for parasitic in all_parasitic:
        present = parasitic.lower() in toc.lower()
        check(
            f"Absent de la TOC générée : '{parasitic}'",
            not present,
            "présent dans la TOC" if present else "",
        )


def test_build_toc_contains_editorial() -> None:
    print("\n[Test] build_table_of_contents — titres éditoriaux présents")
    headings = extract_headings(_SAMPLE_DOCUMENT, toc_eligible_only=True)
    toc = build_table_of_contents(headings)

    editorial_expected = ["Introduction", "Chapitre 1", "Chapitre 2", "Conclusion"]
    for ed in editorial_expected:
        present = ed in toc
        check(
            f"Présent dans la TOC : '{ed}'",
            present,
            "absent" if not present else "",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Tests : is_publishable_heading mis à jour
# ─────────────────────────────────────────────────────────────────────────────

def test_publishable_heading_rejects_parasitic() -> None:
    print("\n[Test] is_publishable_heading — rejette les parasites IA")
    for heading in _PARASITIC_HEADINGS_EN[:5]:
        result = is_publishable_heading(heading)
        check(
            f"is_publishable_heading rejette '{heading}'",
            not result,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Tests : Prompts IA n'incluent pas les titres parasites interdits
# ─────────────────────────────────────────────────────────────────────────────

def test_prompts_contain_parasitic_prohibition() -> None:
    print("\n[Test] Prompts IA — prohibitions des titres parasites présentes")
    from app.prompt_manager import PROMPT_TEMPLATES

    for task in ("clean_transcript", "book_chapter"):
        template = PROMPT_TEMPLATES[task]
        check(
            f"Prompt '{task}' interdit 'Summary'",
            "Summary" in template,
        )
        check(
            f"Prompt '{task}' interdit 'Key Themes'",
            "Key Themes" in template,
        )
        check(
            f"Prompt '{task}' interdit 'Questions for Clarification'",
            "Questions for Clarification" in template,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Rapport final
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 70)
    print("Tests de nettoyage structurel — PublishForge")
    print("=" * 70)

    test_toc_eligible_parasitic_headings()
    test_toc_eligible_editorial_headings()
    test_toc_eligible_h3_rejected()
    test_toc_eligible_h1_accepted()
    test_clean_section_removes_parasitic()
    test_clean_section_keeps_editorial()
    test_extract_headings_toc_eligible()
    test_build_toc_no_parasitic()
    test_build_toc_contains_editorial()
    test_publishable_heading_rejects_parasitic()
    test_prompts_contain_parasitic_prohibition()

    print("\n" + "=" * 70)
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    total = len(_results)
    print(f"Résultats : {passed}/{total} réussis, {failed} échoués")

    if failed:
        print("\nEchecs détaillés :")
        for name, ok, detail in _results:
            if not ok:
                print(f"  [FAIL] {name}  {detail}")
        return 1

    print("Tous les tests ont réussi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
