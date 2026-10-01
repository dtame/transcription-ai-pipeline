"""
Successor prompt editorial-planner-1.0.1.

Does not mutate editorial-planner-1.0. Adds a deterministic canonical-language
rule. Language code is supplied by the request, never hard-coded here.
"""

from __future__ import annotations

from app.editorial_planning.language_policy import (
    SUCCESSOR_PROMPT_VERSION,
    normalize_language_code,
)
from app.editorial_planning.prompt import (
    instruction_prompt as instruction_prompt_v10,
    prompt_fingerprint,
    system_prompt as system_prompt_v10,
)
from app.file_utils import content_hash
from app.source_analysis.prompt import language_label

EDITORIAL_PLANNER_PROMPT_VERSION_V101 = SUCCESSOR_PROMPT_VERSION

_LANGUAGE_RULE_GENERIC = """LANGUE DOCUMENTAIRE CANONIQUE.

Génère toute la prose éditoriale et les libellés dans la langue documentaire
canonique fournie dans la requête (canonical_document_language).
Préserve exactement les références de source et les identifiants canoniques
(IDEA, TOP, EX, REF, UNC, SRC, CH, SEC et autres identifiants machine).
Ne traduis pas le projet dans une autre langue.
"""


def language_rule(canonical_document_language: str) -> str:
    code = normalize_language_code(canonical_document_language)
    if not code:
        raise ValueError("canonical_document_language is required for prompt 1.0.1")
    label = language_label(code)
    return (
        f"LANGUE DE SORTIE OBLIGATOIRE : {label} (code « {code} »).\n"
        f"Toute la prose éditoriale et les libellés (titres candidats, titre "
        f"de travail, sous-titre, angle, lecteur, concept, titres et propos "
        f"de chapitres et de sections, motifs defer/exclude textuels) sont "
        f"rédigés en {label}.\n"
        "Préserve exactement les références de source et les identifiants "
        "canoniques. Tu ne traduis pas le projet dans une autre langue."
    )


def system_prompt(canonical_document_language: str) -> str:
    return (
        system_prompt_v10().rstrip()
        + "\n\n"
        + language_rule(canonical_document_language)
        + "\n"
    )


def instruction_prompt(canonical_document_language: str | None = None) -> str:
    extra = _LANGUAGE_RULE_GENERIC.strip()
    if canonical_document_language:
        extra = extra + "\n\n" + language_rule(canonical_document_language)
    return instruction_prompt_v10().rstrip() + "\n\n" + extra + "\n"


def prompt_bundle(canonical_document_language: str) -> dict[str, str]:
    system = system_prompt(canonical_document_language)
    instructions = instruction_prompt(canonical_document_language)
    return {
        "version": EDITORIAL_PLANNER_PROMPT_VERSION_V101,
        "system": system,
        "instructions": instructions,
        "system_sha256": content_hash(system),
        "instructions_sha256": content_hash(instructions),
        "prompt_sha256": prompt_fingerprint(system, instructions),
        "historical_prompt_version": "editorial-planner-1.0",
        "historical_prompt_mutated": False,
    }


def render_user_prompt(
    digest_json: str,
    *,
    canonical_document_language: str,
) -> str:
    code = normalize_language_code(canonical_document_language)
    return (
        instruction_prompt(code)
        + "\nCANONICAL_DOCUMENT_LANGUAGE\n"
        + code
        + "\n\nSOURCEMAP_DIGEST_JSON\n"
        + digest_json
        + "\n"
    )


__all__ = [
    "EDITORIAL_PLANNER_PROMPT_VERSION_V101",
    "instruction_prompt",
    "language_rule",
    "prompt_bundle",
    "prompt_fingerprint",
    "render_user_prompt",
    "system_prompt",
]
