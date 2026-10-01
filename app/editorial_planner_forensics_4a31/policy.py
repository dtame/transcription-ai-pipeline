"""Language-contract forensics and future-policy recommendation. No prompt mutation."""

from __future__ import annotations

from typing import Any, Mapping

from app.editorial_planner_canary_4a1.constants import (
    PHASE_4A_INSTRUCTIONS_SHA256,
    PHASE_4A_PROMPT_SHA256,
    PHASE_4A_SYSTEM_SHA256,
)
from app.editorial_planning.language_policy import (
    ACTIVE_PROMPT_VERSION,
    CONCEPT_AUTHOR_ORIGINAL,
    CONCEPT_EDITORIAL_PLANNING,
    CONCEPT_FINAL_BOOK,
    CONCEPT_PROMPT_INSTRUCTION,
    CONCEPT_SOURCE_PRIMARY,
    CONCEPT_UI_PROJECT,
    CONTRACT_UNSPECIFIED,
    INHERIT_REQUIRE_EXPLICIT,
    LANGUAGE_CONCEPTS,
    RECOMMENDED_ALIGNMENT,
    RECOMMENDED_SETTING_NAME,
    STATUS_UNRESOLVED,
    SUCCESSOR_PROMPT_VERSION,
    languages_differ,
    plan_must_match_book_language,
    resolve_book_language,
)
from app.editorial_planning.prompt import instruction_prompt, system_prompt
from app.source_analysis.models import SourceMap
from app.source_analysis.prompt import build_language_directive


def inspect_frozen_language_contract() -> dict[str, Any]:
    system = system_prompt()
    instructions = instruction_prompt()
    analyzer_directive_present = "LANGUE DE SORTIE OBLIGATOIRE" in build_language_directive("en")
    planner_has_output_rule = (
        "LANGUE DE SORTIE" in system
        or "LANGUE DE SORTIE" in instructions
        or "output language" in system.lower()
        or "output language" in instructions.lower()
        or "book_language" in system
        or "book_language" in instructions
    )
    return {
        "active_prompt_version": ACTIVE_PROMPT_VERSION,
        "system_sha256": PHASE_4A_SYSTEM_SHA256,
        "instructions_sha256": PHASE_4A_INSTRUCTIONS_SHA256,
        "prompt_sha256": PHASE_4A_PROMPT_SHA256,
        "prompt_instruction_language_evidence": "French system and instruction prose (Tu es / Organise / Réponds).",
        "planner_explicit_output_language_rule": planner_has_output_rule,
        "analyzer_has_output_language_directive": analyzer_directive_present,
        "validator_checks_plan_language": False,
        "transport_has_language_field": False,
        "schema_has_language_field": False,
        "models_have_book_language": False,
        "phase_4a_4a1_4a2_declared_output_language_rule": False,
        "explicit_pre_a3_language_contract": False,
        "do_not_mutate_prompt_in_place": True,
    }


def language_forensics(
    *,
    plan: Mapping[str, Any],
    source_map: SourceMap,
    plan_language_audit: Mapping[str, Any],
    project_language: str,
    contract,
) -> dict[str, Any]:
    frozen = inspect_frozen_language_contract()
    source_primary = source_map.primary_language
    plan_language = str(plan_language_audit.get("editorial_plan_language") or "")
    current = resolve_book_language(
        book_language=None,
        project_language=project_language,
        source_primary_language=source_primary,
        inherit_missing=INHERIT_REQUIRE_EXPLICIT,
    )
    why_french = [
        "editorial-planner-1.0 system and instructions are written in French.",
        "No planner output-language directive existed before A.3 (unlike Source Analyzer).",
        "Digest includes language=SourceMap.primary_language (en) as metadata only.",
        "Validator, transport 1.0, and schema 3661/3909 do not constrain plan language.",
        "A.1 used the same prompt with an English synthetic digest and produced an English plan, so French prompt prose does not deterministically force French plans.",
        "A.3 French editorial prose is therefore an unspecified provider choice under missing policy, not a proven contract command.",
    ]
    return {
        "concepts": {
            CONCEPT_SOURCE_PRIMARY: source_primary,
            CONCEPT_AUTHOR_ORIGINAL: (
                "English teaching corpus as captured by SourceMap summaries; "
                "author/audience metadata are English. Not a planner output rule."
            ),
            CONCEPT_EDITORIAL_PLANNING: plan_language,
            CONCEPT_FINAL_BOOK: "UNRESOLVED — no explicit book_language consumed by the planner.",
            CONCEPT_UI_PROJECT: project_language or "",
            CONCEPT_PROMPT_INSTRUCTION: "fr",
        },
        "language_concepts_are_not_the_same": list(LANGUAGE_CONCEPTS),
        "source_primary_language": source_primary,
        "editorial_plan_language": plan_language,
        "plan_language_audit": plan_language_audit,
        "explicit_pre_a3_language_contract": "NO",
        "language_contract_result": CONTRACT_UNSPECIFIED,
        "do_not_declare_french_invalid_because_primary_is_en": True,
        "why_french_may_have_occurred": why_french,
        "speculation_beyond_evidence": False,
        "frozen_contract": frozen,
        "project_yaml_language": project_language,
        "project_yaml_wired_into_planner": False,
        "current_resolution": current.to_dict(),
        "validator_status": getattr(contract, "status", None),
        "book_language_requires_human_decision": True,
        "publication_without_translation_if_french_plan_accepted": (
            "YES — the unchanged candidate can remain a French editorial plan "
            "if a human explicitly accepts French as planning language. "
            "That is not the same as choosing the final book language."
        ),
        "plan_vs_book_mismatch_risk": plan_must_match_book_language(),
        "source_differs_from_plan": languages_differ(source_primary, "fr"),
    }


def language_policy_recommendation(
    *,
    source_primary: str,
    project_language: str,
    plan_language: str,
) -> dict[str, Any]:
    current = resolve_book_language(
        book_language=None,
        project_language=project_language,
        source_primary_language=source_primary,
        inherit_missing=INHERIT_REQUIRE_EXPLICIT,
    )
    return {
        "recommended_generic_language_policy": RECOMMENDED_ALIGNMENT,
        "recommended_setting": RECOMMENDED_SETTING_NAME,
        "setting_aliases_considered": ["book_language", "output_language", "editorial_language"],
        "preferred_name": "book_language",
        "do_not_assume_source_primary_equals_book": True,
        "evaluated_defaults": {
            "A_inherit_source_primary": (
                "Deterministic, generic, and useful as an optional mode. "
                "Rejected as the recommended default because this forensics "
                "shows source language and desired book language can diverge."
            ),
            "B_inherit_dominant_author_source": (
                "Not separately stored from SourceMap.primary_language today. "
                "Would duplicate A unless a distinct author_original_language is added."
            ),
            "C_require_explicit_before_planner": (
                "Recommended default. Forces a human/project choice. Does not "
                "hard-code English or French."
            ),
        },
        "recommended_default_when_missing": INHERIT_REQUIRE_EXPLICIT,
        "current_project": {
            "source_primary_language": source_primary,
            "project_yaml_language": project_language,
            "editorial_plan_language": plan_language,
            "planner_consumed_project_language": False,
            "book_language_requires_human_decision": current.requires_human_decision,
            "resolution": current.to_dict(),
        },
        "human_decision_required": (
            "Choose book_language for this project explicitly. "
            "depot project.yaml language=en is document-identity metadata and "
            "was not an Editorial Planner input; do not treat it as a silent "
            "book-language decision, and do not treat the French plan as one either. "
            "If French planning language is accepted, the unchanged A.3 candidate "
            "may remain untranslated as a plan, and that plan language should be "
            "the book language. If English or another language is required for "
            "the plan, do not repair or translate this candidate; a later phase "
            "would need editorial-planner-1.0.1 and a new provider call."
        ),
        "successor_prompt": SUCCESSOR_PROMPT_VERSION,
        "mutate_editorial_planner_1_0": False,
        "future_prompt_change_required": True,
        "new_grammar_canary_required": False,
        "grammar_vs_prompt_semantics": (
            "Adding a deterministic language instruction is prompt semantics. "
            "Transport grammar and JSON schema stay editorial-plan-transport-1.0 "
            "and schema 3661/3909. No new grammar canary is required for that "
            "instruction alone."
        ),
        "transport_change_required": False,
        "schema_change_required": False,
        "alignment": plan_must_match_book_language(),
        "status": STATUS_UNRESOLVED,
    }
