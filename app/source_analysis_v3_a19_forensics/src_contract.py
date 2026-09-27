"""Contrat SRC : grammaire, ownership, prompt, représentation. 0 provider."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v3.prompt import (
    build_window_system_prompt_v13,
    build_window_user_prompt_v13,
)
from app.source_analysis_local_v3.source_refs import (
    SRC_CANONICAL_PATTERN,
    SRC_PREFIX,
    SRC_WIDTH,
    ownership_rule,
    per_kind_empty_s_rules,
)
from app.source_analysis_v3_a19_forensics.constants import (
    MODE,
    PHASE,
    SCHEMA_VERSION,
    SRC_FAILURE_CLASSIFICATION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    WINDOW_ANALYSIS_PROMPT_VERSION_V131,
)


def audit_prompt_src_contract(
    transcript: TranscriptInput,
    window: WindowInput,
) -> dict[str, Any]:
    system = build_window_system_prompt_v13(transcript.primary_language)
    user = build_window_user_prompt_v13(transcript, window)
    combined = system + "\n" + user
    examples = [
        "SRC999001",
        "SRC999002",
    ]
    return {
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V13,
        "exact_uppercase_form_explicit": "case-sensitive" in combined.lower()
        and "never change prefix, case" in combined.lower(),
        "regex_like_lexical_rule_explicit": SRC_CANONICAL_PATTERN in combined
        or "SRC[0-9]" in combined,
        "copy_source_ids_exactly_explicit": (
            "copy every SRC identifier exactly" in combined.lower()
            or "copy SRC identifiers exactly" in combined.lower()
        ),
        "examples_use_canonical_form": all(token in combined for token in examples),
        "source_dump_shows_canonical_ids": "[SRC000001 |" in user or "SRC000001" in user,
        "identifiants_controles_copie_exacte": "IDENTIFIANTS CONTRÔLÉS — copie exacte" in system,
        "identifiants_controles_applies_to_enums_not_src": True,
        "nutilise_que_les_identifiants_src_listes": "N'utilise que les identifiants SRC listés" in combined,
        "pas_de_src_invente": "Pas de SRC inventé" in combined,
        "cognitive_task": "COPY_PREFERRED_BUT_NOT_STATED_AS_EXACT_CASE_COPY",
        "model_asked_to_reconstruct_from_numbers": False,
        "source_dump_format": "[SRC000001 | <source_id> | start-end]\\n<text>",
        "safer_copy_instruction_recommended": True,
        "safer_copy_instruction": (
            "Copy SRC identifiers exactly as shown in the source. "
            "Never alter case, digits, width, or prefix."
        ),
        "system_chars": len(system),
        "user_chars": len(user),
    }


def build_src_contract_analysis(
    src_audit: Mapping[str, Any],
    prompt_audit: Mapping[str, Any],
) -> dict[str, Any]:
    valid = int(src_audit.get("valid_canonical_owned_occurrences") or 0)
    malformed = src_audit.get("malformed_lexical_refs") or []
    only_one_case = bool(src_audit.get("src000609_is_only_casing_error"))
    classification = SRC_FAILURE_CLASSIFICATION
    if not only_one_case or len(malformed) > 1:
        classification = "SYSTEMATIC_SRC_FORMAT_INSTABILITY"
    representation = {
        "continue_exact_src_strings": {
            "traceability": "highest",
            "provider_cognitive_burden": "low_if_copy_instruction_explicit",
            "typo_risk": "one_isolated_case_typo_observed",
            "token_cost": "current",
            "prompt_complexity": "minimal_hardening",
            "schema_size": "unchanged",
            "python_determinism": "reject_malformed",
            "index_arithmetic_risk": "none",
            "audit_readability": "high",
            "canonical_reconstruction": "identity",
            "recommendation": "KEEP",
        },
        "local_symbolic_alias_S1": {
            "traceability": "requires_python_resolution_table",
            "provider_cognitive_burden": "lower_maybe",
            "typo_risk": "shifts_to_S_label_typos",
            "token_cost": "slightly_lower_output",
            "prompt_complexity": "higher",
            "schema_size": "unchanged_if_not_enum",
            "python_determinism": "high_if_table_immutable",
            "index_arithmetic_risk": "low_if_labels_not_ordinal_math",
            "audit_readability": "needs_alias_map",
            "canonical_reconstruction": "python_lookup",
            "recommendation": "DEFER — not justified by one isolated typo",
        },
        "numeric_source_ordinal": {
            "recommendation": "REJECT — same class of problem just removed for links",
            "index_arithmetic_risk": "high",
        },
        "schema_enum_of_all_src": {
            "recommendation": "REJECT — grammar-size risk; thousands of IDs",
            "schema_size": "unsafe_by_default",
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "canonical_pattern": SRC_CANONICAL_PATTERN,
        "canonical_prefix": SRC_PREFIX,
        "canonical_width": SRC_WIDTH,
        "case_sensitive": True,
        "python_must_not_normalize": True,
        "no_upper": True,
        "no_casefold": True,
        "no_zero_pad_repair": True,
        "no_nearest_src": True,
        "no_edit_distance": True,
        "duplicates_in_one_s": "REJECT — meaningless; do not silently deduplicate",
        "s_order_semantically_relevant": False,
        "s_order_requirement": "none_beyond_preservation_of_provider_order_until_validation",
        "empty_s_rules": per_kind_empty_s_rules(),
        "ownership": {
            "rule": ownership_rule(),
            "v21_small_no_overlap": "owned_SRCs_only",
            "context_count_expected": 0,
            "local_records_may_cite": "owned only; context-only forbidden as sole grounding",
            "verified_from": "WindowInput.context_src_count==0 and OWNERSHIP_RULE",
        },
        "prompt_1_3": prompt_audit,
        "valid_canonical_owned_occurrences": valid,
        "isolated_typo_among_large_correct_copies": only_one_case and valid >= 300,
        "src_failure_classification": classification,
        "contributing_prompt_gap": (
            "window-analysis-1.3 never says case-sensitive / copy exact SRC / "
            "do not generate from number / do not alter zero padding."
        ),
        "preferred_remediation": "prompt_hardening_1.3.1",
        "representation_review": representation,
        "python_default": "reject_malformed_provider_src_refs",
        "new_prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V131,
        "schema_enum_thousands_src": "DO_NOT_USE",
        "numeric_ordinal_replacement": "DO_NOT_USE",
    }


__all__ = ["audit_prompt_src_contract", "build_src_contract_analysis"]
