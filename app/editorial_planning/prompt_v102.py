"""
Successor prompt editorial-planner-1.0.2.

Does not mutate editorial-planner-1.0 or 1.0.1.
Adds a generic exhaustive IDEA-accountability rule and a pre-return
completeness self-check. Language rule is inherited unchanged from 1.0.1.
"""

from __future__ import annotations

from app.editorial_planning.language_policy import normalize_language_code
from app.editorial_planning.prompt import prompt_fingerprint
from app.editorial_planning.prompt_v101 import (
    instruction_prompt as instruction_prompt_v101,
    language_rule,
    system_prompt as system_prompt_v101,
)
from app.file_utils import content_hash

EDITORIAL_PLANNER_PROMPT_VERSION_V102 = "editorial-planner-1.0.2"

_COVERAGE_HARDENING = """COMPLETUDE EXHAUSTIVE DES IDEA — REGLE DE HAUTE PRIORITE.

Chaque identifiant IDEA fourni dans l'entrée doit apparaître dans le
mécanisme explicite de disposition / reddition de comptes du plan.
N'omets aucune IDEA silencieusement. Si une IDEA ne doit pas être
assignée à une section, marque-la DEFERRED ou EXCLUDED selon le contrat,
plutôt que de l'omettre.

Chaque IDEA d'entrée a exactement une disposition primaire :
ASSIGNED, DEFERRED ou EXCLUDED.
Une réutilisation dans une autre section est un placement auditable
supplémentaire ; elle ne remplace pas la disposition primaire.

AUTO-VERIFICATION DE SORTIE (sans raisonnement exposé) :
Avant de renvoyer la réponse structurée finale, vérifie que chaque IDEA ID
d'entrée a une disposition explicite et qu'aucune n'est absente.
N'expose pas de chaîne de pensée. Contrôle de complétude uniquement.
"""


def coverage_hardening_rule() -> str:
    return _COVERAGE_HARDENING.strip() + "\n"


def system_prompt(canonical_document_language: str) -> str:
    return (
        system_prompt_v101(canonical_document_language).rstrip()
        + "\n\n"
        + coverage_hardening_rule()
    )


def instruction_prompt(canonical_document_language: str | None = None) -> str:
    return (
        instruction_prompt_v101(canonical_document_language).rstrip()
        + "\n\n"
        + coverage_hardening_rule()
    )


def prompt_bundle(canonical_document_language: str) -> dict[str, str]:
    system = system_prompt(canonical_document_language)
    instructions = instruction_prompt(canonical_document_language)
    return {
        "version": EDITORIAL_PLANNER_PROMPT_VERSION_V102,
        "system": system,
        "instructions": instructions,
        "system_sha256": content_hash(system),
        "instructions_sha256": content_hash(instructions),
        "prompt_sha256": prompt_fingerprint(system, instructions),
        "historical_prompt_version": "editorial-planner-1.0.1",
        "base_prompt_version": "editorial-planner-1.0",
        "historical_prompt_mutated": False,
        "language_rule_unchanged": True,
        "coverage_hardening": True,
    }


def render_user_prompt(
    digest_json: str,
    *,
    canonical_document_language: str,
    expected_idea_count: int,
) -> str:
    code = normalize_language_code(canonical_document_language)
    count = int(expected_idea_count)
    if count < 1:
        raise ValueError("expected_idea_count must be derived from the input IDEA set")
    return (
        instruction_prompt(code)
        + "\nEXPECTED_IDEA_COUNT\n"
        + str(count)
        + "\n\nCANONICAL_DOCUMENT_LANGUAGE\n"
        + code
        + "\n\nSOURCEMAP_DIGEST_JSON\n"
        + digest_json
        + "\n"
    )


__all__ = [
    "EDITORIAL_PLANNER_PROMPT_VERSION_V102",
    "coverage_hardening_rule",
    "instruction_prompt",
    "language_rule",
    "prompt_bundle",
    "prompt_fingerprint",
    "render_user_prompt",
    "system_prompt",
]
