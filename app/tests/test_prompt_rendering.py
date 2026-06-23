"""
Tests de rendu de prompts IA.

Vérifie que render_prompt() :
- remplace correctement les placeholders {{VARIABLE}}
- ne plante pas sur des accolades JSON {"key": "value"}
- ne plante pas sur des accolades LaTeX \\boxed{}
- ne plante pas sur des accolades vides {}
- ne plante pas sur des accolades positionnelles {0}
- ne plante pas sur les vrais templates PROMPT_TEMPLATES

Usage :
    python -m app.tests.test_prompt_rendering
"""

import sys
from pathlib import Path

# Assure que le répertoire racine du projet est dans sys.path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.prompt_utils import render_prompt
from app.prompt_manager import PROMPT_TEMPLATES, build_prompt


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(f"ÉCHEC : {message}")
    print(f"  OK  {message}")


def _test(name: str):
    print(f"\n[TEST] {name}")


# ─────────────────────────────────────────────────────────────────────────────
# Tests render_prompt()
# ─────────────────────────────────────────────────────────────────────────────

def test_basic_replacement():
    _test("render_prompt — remplacement de base")

    result = render_prompt("Texte : {{TEXT}}", {"TEXT": "bonjour"})
    _assert("bonjour" in result, "{{TEXT}} remplacé par 'bonjour'")
    _assert("{{TEXT}}" not in result, "placeholder {{TEXT}} absent du résultat")


def test_json_braces_not_crash():
    _test("render_prompt — accolades JSON ne causent pas d'erreur")

    template = '''
Retourne ce JSON :
{
  "title": "Titre",
  "summary": "Résumé"
}

Texte :
{{TEXT}}
'''
    result = render_prompt(template, {"TEXT": "Bonjour"})
    _assert("Bonjour" in result, "{{TEXT}} remplacé")
    _assert('"title"' in result, 'accolades JSON {"title": ...} préservées')
    _assert('"summary"' in result, 'accolades JSON {"summary": ...} préservées')


def test_empty_braces_not_crash():
    _test("render_prompt — accolades vides {} ne causent pas d'erreur")

    template = "Exemple de liste vide : {} et texte : {{TEXT}}"
    result = render_prompt(template, {"TEXT": "hello"})
    _assert("hello" in result, "{{TEXT}} remplacé")
    _assert("{}" in result, "accolades vides {} préservées")


def test_positional_braces_not_crash():
    _test("render_prompt — accolades positionnelles {0} ne causent pas d'erreur")

    template = "Arg positionnel : {0} — texte : {{TEXT}}"
    result = render_prompt(template, {"TEXT": "world"})
    _assert("world" in result, "{{TEXT}} remplacé")
    _assert("{0}" in result, "accolade positionnelle {0} préservée")


def test_latex_boxed_not_crash():
    _test("render_prompt — \\boxed{} LaTeX ne cause pas d'erreur")

    template = "N'utilise JAMAIS \\boxed{} ni aucun format mathématique.\n\n{{TEXT}}"
    result = render_prompt(template, {"TEXT": "contenu"})
    _assert("contenu" in result, "{{TEXT}} remplacé")
    _assert("\\boxed{}" in result, "\\boxed{} préservé")


def test_multiple_variables():
    _test("render_prompt — plusieurs variables")

    template = "Projet : {{PROJECT}}\nLangue : {{LANGUAGE}}\nTexte : {{TEXT}}"
    result = render_prompt(template, {
        "PROJECT": "pastoral_retreat",
        "LANGUAGE": "fr",
        "TEXT": "contenu du chunk",
    })
    _assert("pastoral_retreat" in result, "{{PROJECT}} remplacé")
    _assert("fr" in result, "{{LANGUAGE}} remplacé")
    _assert("contenu du chunk" in result, "{{TEXT}} remplacé")


def test_unknown_placeholder_preserved():
    _test("render_prompt — placeholder inconnu conservé tel quel")

    template = "Connu : {{TEXT}} — Inconnu : {{UNKNOWN}}"
    result = render_prompt(template, {"TEXT": "val"})
    _assert("val" in result, "{{TEXT}} remplacé")
    _assert("{{UNKNOWN}}" in result, "{{UNKNOWN}} préservé (non fourni)")


# ─────────────────────────────────────────────────────────────────────────────
# Tests PROMPT_TEMPLATES — aucun template ne doit planter
# ─────────────────────────────────────────────────────────────────────────────

def test_all_templates_render():
    _test("PROMPT_TEMPLATES — tous les templates se rendent sans erreur")

    sample_text = "Ceci est un texte de test pour le traitement IA."

    for task_name, template in PROMPT_TEMPLATES.items():
        try:
            result = render_prompt(template, {"TEXT": sample_text})
            _assert(
                sample_text in result,
                f"Template '{task_name}' : {{{{TEXT}}}} remplacé correctement",
            )
        except Exception as e:
            raise AssertionError(
                f"ÉCHEC sur le template '{task_name}' : {e}"
            ) from e


def test_build_prompt_clean_transcript():
    _test("build_prompt — clean_transcript sans erreur")

    chunk_text = "Voici une transcription brute avec des hésitations euh... voilà."
    result = build_prompt("clean_transcript", chunk_text)
    _assert(chunk_text in result, "Texte du chunk présent dans le prompt final")
    _assert("éditeur professionnel" in result, "Template clean_transcript chargé")


def test_build_prompt_does_not_raise_on_format_chars():
    _test("build_prompt — accolades dans le texte du chunk ne plantent pas")

    chunk_text = 'Texte avec du JSON : {"key": "value"} et des {} vides.'
    try:
        result = build_prompt("clean_transcript", chunk_text)
        _assert(chunk_text in result, "Texte avec accolades JSON injecté sans erreur")
    except Exception as e:
        raise AssertionError(
            f"build_prompt a planté sur un texte avec accolades JSON : {e}"
        ) from e


def test_original_bug_scenario():
    _test("Scénario original — 'Replacement index 0 out of range' ne doit plus se produire")

    template_with_json = '''
Tu es un assistant éditorial.

Retourne une structure JSON comme ceci :
{
  "title": "Titre du document",
  "summary": "Résumé court"
}

N'utilise JAMAIS \\boxed{} ni de format mathématique.

Texte à traiter :
{{TEXT}}
'''
    try:
        result = render_prompt(template_with_json, {"TEXT": "Texte de test"})
        _assert("Texte de test" in result, "{{TEXT}} remplacé")
        _assert('"title"' in result, "Accolades JSON préservées")
        _assert("\\boxed{}" in result, "\\boxed{} préservé")
        print("  >> Aucune erreur 'Replacement index 0 out of range'. Bug corrigé.")
    except Exception as e:
        raise AssertionError(
            f"Bug non corrigé — erreur inattendue : {e}"
        ) from e


# ─────────────────────────────────────────────────────────────────────────────
# Runner principal
# ─────────────────────────────────────────────────────────────────────────────

def run_all_tests():
    tests = [
        test_basic_replacement,
        test_json_braces_not_crash,
        test_empty_braces_not_crash,
        test_positional_braces_not_crash,
        test_latex_boxed_not_crash,
        test_multiple_variables,
        test_unknown_placeholder_preserved,
        test_all_templates_render,
        test_build_prompt_clean_transcript,
        test_build_prompt_does_not_raise_on_format_chars,
        test_original_bug_scenario,
    ]

    passed = 0
    failed = 0

    print("\n" + "=" * 60)
    print("  Tests de rendu de prompts — TranscriptionAI")
    print("=" * 60)

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"\n  *** {e}")
            failed += 1
        except Exception as e:
            print(f"\n  *** ERREUR INATTENDUE dans {test_fn.__name__}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"  Résultat : {passed} réussi(s) / {failed} échoué(s) / {len(tests)} total")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    else:
        print("\n  Tous les tests sont passés. Le bug est corrigé.")
        sys.exit(0)


if __name__ == "__main__":
    run_all_tests()
