"""Comparaison d'options A–G et sélection. Design only. 0 activation."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_local_v3.schema import measure_v3_schema_pair
from app.source_analysis_v3_a25_forensics.constants import (
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
    IMPLEMENTATION_SCOPE,
    MODE,
    NEW_PROMPT_ACTIVATED,
    NEW_PROMPT_DESIGNED,
    NEW_TRANSPORT_ACTIVATED,
    NEW_TRANSPORT_DESIGNED,
    PHASE,
    SCHEMA_CHANGED,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    SERVER_GRAMMAR_STATUS,
    V3_HANDLE_ARCHITECTURE,
)


def _option(
    name: str,
    selected: bool,
    *,
    lost: str,
    material: bool,
    recoverable: bool,
    global_can_classify: bool,
    classification_necessary: str,
    risk: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "selected": selected,
        "information_loss": lost,
        "loss_material": material,
        "recoverable_deterministically": recoverable,
        "global_llm_can_classify_later": global_can_classify,
        "classification_necessary": classification_necessary,
        "risk": risk,
    }


def build_architecture_decision(
    *,
    metadata: Mapping[str, Any],
    i44: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    measured = measure_v3_schema_pair()
    options = {
        "A_KEEP_V3_PROMPT_1_3_3": _option(
            "KEEP_V3_PROMPT_1_3_3",
            False,
            lost="none immediately",
            material=False,
            recoverable=False,
            global_can_classify=False,
            classification_necessary="still asked locally",
            risk=(
                "Prompt whack-a-mole. A.24 already added an explicit prohibition "
                "and I44 persisted. Stochastic taxonomy leakage continues. "
                "Larger prompt. Another paid WIN004 retry. Not the default path."
            ),
        ),
        "B_V3_SIMPLIFIED_METADATA": _option(
            "V3_SIMPLIFIED_METADATA",
            False,
            lost="local IDEA kind vocabulary shrinks or disappears",
            material=False,
            recoverable=True,
            global_can_classify=True,
            classification_necessary="not locally",
            risk=(
                "Same destination as C if kind is removed. If vocabulary is only "
                "narrowed, 'example' leakage can still occur because the schema "
                "does not enum m[0]."
            ),
        ),
        "C_REMOVE_LOCAL_IDEA_SUBTYPE": _option(
            "GLOBALIZE_IDEA_SUBTYPE",
            True,
            lost="local IDEA.m[0] kind token",
            material=False,
            recoverable=True,
            global_can_classify=True,
            classification_necessary=(
                "Canonical field exists; not required for local extraction; "
                "can be filled globally or left until a later classifier"
            ),
            risk=(
                "Reconstructor currently copies local kind. Consolidation does "
                "not classify kinds today. Implementation is a follow-up, not "
                "A.25 activation."
            ),
        ),
        "D_KIND_SPECIFIC_COMPACT_FIELDS": _option(
            "KIND_SPECIFIC_FIELDS",
            False,
            lost="none",
            material=False,
            recoverable=True,
            global_can_classify=True,
            classification_necessary="still local",
            risk="Schema bytes and branching grow. Grammar-too-large history.",
        ),
        "E_DISCRIMINATED_UNION": _option(
            "SEPARATE_RECORD_FORMS",
            False,
            lost="none",
            material=False,
            recoverable=True,
            global_can_classify=True,
            classification_necessary="still local",
            risk="oneOf / union cost. SERVER_GRAMMAR_UNVERIFIED. Not measured.",
        ),
        "F_MOVE_SUBTYPE_TO_GLOBAL": _option(
            "GLOBALIZE_IDEA_SUBTYPE",
            True,
            lost="same as C",
            material=False,
            recoverable=True,
            global_can_classify=True,
            classification_necessary="global / later",
            risk="Same selected path as C. F is the placement of C.",
        ),
        "G_OTHER": _option(
            "OTHER",
            False,
            lost="n/a",
            material=False,
            recoverable=False,
            global_can_classify=False,
            classification_necessary="n/a",
            risk="No other evidence-supported design is required.",
        ),
    }
    local_vs_global = {
        "hybrid": (
            "Local windows extract source-grounded semantic units. "
            "Global consolidation reconstructs the source map."
        ),
        "local_should_identify": [
            "idea text",
            "source grounding (strict SRC)",
            "topic association (T handles)",
        ],
        "local_need_not_classify": [
            "claim / explanation / principle / instruction / "
            "observation / question / testimony"
        ],
        "fine_grained_subtype_belongs": "global consolidation or a later deterministic/LLM classifier",
        "enough_for_source_analyzer_local_stage": True,
    }
    selected_spec = {
        "architecture": SELECTED_ARCHITECTURE,
        "implementation_scope": IMPLEMENTATION_SCOPE,
        "local_representation": {
            "k": "IDEA",
            "v": "idea text",
            "s": "strict SRC refs",
            "h": "I handle",
            "l": "T topic handles",
            "m": "[importance] only — kind omitted locally",
        },
        "global_consolidation_responsibility": (
            "Classify Idea.kind when publishing a canonical node, or leave "
            "classification to a dedicated later step. MERGE must not require "
            "identical local kinds."
        ),
        "canonical_reconstruction_behavior": (
            "Read kind from the consolidation node when present. Do not invent "
            "a local kind. Do not copy an absent local m[0]. Source_map "
            "validator still requires a valid kind at publication if the field "
            "is populated; publication may defer kind until classified."
        ),
        "validation_implications": (
            "New local decoder must accept IDEA.m=[importance]. Historical V3 "
            "decoder stays fail-fast on kind. Do not mutate semantic-transport-v3 "
            "or window-analysis-1.3.2."
        ),
        "new_prompt": NEW_PROMPT_DESIGNED,
        "new_prompt_activated": NEW_PROMPT_ACTIVATED,
        "new_transport": NEW_TRANSPORT_DESIGNED,
        "new_transport_activated": NEW_TRANSPORT_ACTIVATED,
        "schema_changed": SCHEMA_CHANGED,
        "raw_schema_bytes": EXPECTED_RAW_SCHEMA_BYTES,
        "adapted_schema_bytes": EXPECTED_ADAPTED_SCHEMA_BYTES,
        "measured_v3_schema": {
            "raw_bytes": measured.get("raw_bytes"),
            "adapted_bytes": measured.get("adapted_bytes"),
            "server_grammar_acceptance": measured.get("server_grammar_acceptance"),
        },
        "server_grammar_status": SERVER_GRAMMAR_STATUS,
        "preserve_v3_successes": [
            "symbolic T/I handles",
            "strict SRC refs",
            "no numeric semantic-link indexes",
            "deterministic Python resolution",
            "no repair",
            "source traceability",
            "compact schema (588/650)",
        ],
        "must_not_become_final_source_map": True,
        "v3_handle_architecture_unchanged": V3_HANDLE_ARCHITECTURE,
        "why_not_v4_structural": (
            "V3 can be simplified safely by dropping local IDEA kind. "
            "A new structural transport is not required to stop m[0] leakage."
        ),
        "why_not_prompt_1_3_3": (
            "A.24's persistent I44 violation after an explicit prohibition "
            "indicates structural fragility of overloaded m[], not a missing "
            "sentence in the prompt."
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "q6_lowest_risk_before_another_real_call": SELECTED_ARCHITECTURE,
        "selected": SELECTED_ARCHITECTURE,
        "options": options,
        "local_vs_global": local_vs_global,
        "selected_spec": selected_spec,
        "option_a_whack_a_mole_risk": True,
        "i44_persisted_after_1_3_2": i44.get("classification"),
        "root_violations": inventory.get("total_latent_root_violations"),
        "idea_subtype_required_locally": metadata.get("idea_subtype_necessity", {}).get(
            "required_locally"
        ),
        "v4_design_written": False,
        "v4_activated": False,
        "historical_v3_unmutated": True,
        "historical_prompt_1_3_2_unmutated": True,
    }


__all__ = ["build_architecture_decision"]
