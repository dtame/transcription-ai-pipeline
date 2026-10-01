"""Hardening, schema, validator, and semantic-architecture decisions."""

from __future__ import annotations

from typing import Any, Mapping

from app.ai.pricing import build_default_catalog
from app.book_generation.constants import (
    BOOK_GENERATION_TRANSPORT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION_V10,
    BOOK_GENERATOR_VALIDATOR_VERSION,
    BOOK_GENERATOR_VALIDATOR_VERSION_V10,
    EVIDENCE_STRATEGY_HYDRATED,
)
from app.book_generation.prompt import (
    FROZEN_INSTRUCTIONS_SHA256,
    FROZEN_PROMPT_SHA256,
    FROZEN_SYSTEM_SHA256,
    prompt_bundle as prompt_bundle_v10,
)
from app.book_generation.prompt_v101 import prompt_bundle as prompt_bundle_v101
from app.book_generation.schema import schema_identity
from app.book_generation.validator import validator_contract_dict
from app.book_generator_forensics_4b21.constants import (
    EXPECTED_MAX_OUTPUT,
    FUTURE_MODEL,
    FUTURE_THINKING,
    HISTORICAL_4B2_STATUS,
    HYDRATION_STRATEGY,
    SUCCESSOR_PROMPT_VERSION,
    TRANSPORT_VERSION,
)


def root_cause_matrix(
    empty: Mapping[str, Any],
    connective: Mapping[str, Any],
    illustration: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "EMPTY_PARAGRAPH_ROOT_CAUSE": list(empty.get("root_cause") or []),
        "CONNECTIVE_ARGUMENT_ROOT_CAUSE": list(connective.get("root_cause") or []),
        "INVENTED_ILLUSTRATION_ROOT_CAUSE": list(illustration.get("root_cause") or []),
        "HYDRATION_DEFECT": "NO",
        "GENERATION_GRANULARITY_DEFECT": "NO",
        "OUTPUT_BUDGET_DEFECT": "NO",
        "THINKING_CONFIGURATION_DEFECT": "NOT_DEMONSTRATED",
        "hydration_strategy": HYDRATION_STRATEGY,
        "hydration_frozen": True,
        "chapter_level_generation_frozen": True,
        "ch016_smallest_ample_budget": True,
        "provider_finished_end_turn": True,
        "thinking_remains_disabled": True,
        "do_not_blame_hydration_without_evidence": True,
        "notes": [
            "4B.2 showed all six assigned IDEAs represented and remaining prose source-faithful.",
            "CH016 is the smallest chapter with ample context/output budget.",
            "Provider finished end_turn; max_output is not a demonstrated cause.",
            "Thinking was disabled as configured; enabling it is not evidenced as a fix.",
        ],
    }


def prompt_hardening_decision() -> dict[str, Any]:
    historical = prompt_bundle_v10()
    successor = prompt_bundle_v101()
    return {
        "historical_prompt": BOOK_GENERATOR_PROMPT_VERSION_V10,
        "historical_mutated": False,
        "historical_system_sha256": historical["system_sha256"],
        "historical_instructions_sha256": historical["instructions_sha256"],
        "historical_prompt_sha256": historical["prompt_sha256"],
        "frozen_system_sha256": FROZEN_SYSTEM_SHA256,
        "frozen_instructions_sha256": FROZEN_INSTRUCTIONS_SHA256,
        "frozen_prompt_sha256": FROZEN_PROMPT_SHA256,
        "historical_identity_match": (
            historical["system_sha256"] == FROZEN_SYSTEM_SHA256
            and historical["prompt_sha256"] == FROZEN_PROMPT_SHA256
        ),
        "successor_prompt": SUCCESSOR_PROMPT_VERSION,
        "successor_system_sha256": successor["system_sha256"],
        "successor_instructions_sha256": successor["instructions_sha256"],
        "successor_prompt_sha256": successor["prompt_sha256"],
        "successor_differs": successor["prompt_sha256"] != historical["prompt_sha256"],
        "scope": "narrow hardening release",
        "hardening_areas": [
            "non-empty paragraphs",
            "no unsupported connective claims",
            "no invented examples/illustrations/hypotheticals/anecdotes",
            "evidence-bounded substantive prose",
            "pre-return completeness/fidelity self-check",
        ],
        "ch016_specific_hacks": False,
        "mentions_p9b": False,
        "mentions_funeral": False,
        "chain_of_thought_requested": False,
        "selected_hardening": (
            "book-generator-1.0.1 + existing hard local validator + "
            "hybrid semantic validation strategy"
        ),
    }


def schema_transport_decision() -> dict[str, Any]:
    schema = schema_identity()
    return {
        "transport": TRANSPORT_VERSION,
        "transport_changed": False,
        "schema_changed": False,
        "schema_versioning_identity_preserved": True,
        "raw_schema_sha256": schema["raw_schema_sha256"],
        "adapted_schema_sha256": schema["adapted_schema_sha256"],
        "raw_schema_bytes": schema["raw_schema_bytes"],
        "adapted_schema_bytes": schema["adapted_schema_bytes"],
        "schema_limitation": (
            "Anthropic structured-output subset does not permit minLength. "
            "Empty string remains schema-legal. Local validator + prompt "
            "hardening hold the non-empty invariant."
        ),
        "do_not_add_unsupported_minLength": True,
        "new_grammar_canary_required": "NO",
        "reason_no_grammar_canary": (
            "Transport unchanged, schema bytes unchanged, only prompt semantics changed."
        ),
        "preferred_transport": BOOK_GENERATION_TRANSPORT_VERSION,
    }


def validator_hardening_decision() -> dict[str, Any]:
    contract = validator_contract_dict()
    return {
        "historical_validator": BOOK_GENERATOR_VALIDATOR_VERSION_V10,
        "successor_validator": BOOK_GENERATOR_VALIDATOR_VERSION,
        "local_validator_changed": True,
        "strengthened": [
            "empty text after whitespace normalization",
            "whitespace-only text",
            "missing substantive evidence",
            "unknown evidence",
            "structure",
            "coverage",
        ],
        "not_implemented_as_deterministic": [
            "new arguments in connective prose",
            "invented examples",
            "semantic drift",
        ],
        "empty_paragraph_never_dropped": True,
        "validator_defect": "NO",
        "contract": contract,
        "historical_replay_still_fail": True,
    }


def semantic_validation_architecture() -> dict[str, Any]:
    catalog = build_default_catalog()
    terra = catalog.get("openai", "gpt-5.6-terra")
    return {
        "evaluated_options": {
            "A": "human-only review during canary/rollout",
            "B": "future Phase 5 Book Validator only",
            "C": "dedicated automated chapter-level semantic validator before cache accept",
            "D": "hybrid approach",
        },
        "selected": "D_HYBRID",
        "book_generation_validator": (
            "deterministic structural/provenance/coverage/language checks"
        ),
        "future_semantic_gate": (
            "unsupported claims, invented examples, evidence fidelity "
            "before a chapter cache entry is accepted for final assembly"
        ),
        "next_hardened_canary_gate": "human semantic review + hardened local validator",
        "production_19_chapter_problem": (
            "Manual exhaustive paragraph review is possible but expensive. "
            "Phase 4B must not silently accept chapters because structure passed."
        ),
        "phase_5_boundary": {
            "implement_wholesale_here": False,
            "chapter_level_semantic_validation": (
                "remain Phase 5 / later 4B acceptance work, but prevent book "
                "publication until validated"
            ),
            "trade_offs": [
                "Implementing now would start Phase 5 and likely need a Terra call.",
                "Deferring without a gate would let structural PASS publish unsupported prose.",
                "Hybrid keeps 4B.2.1 offline while making the next canary depend on human review.",
            ],
        },
        "independence_principle": (
            "Do not use Sonnet to validate Sonnet. Frozen Book Validator "
            "production model is OpenAI gpt-5.6-terra."
        ),
        "future_model_if_automated": "openai / gpt-5.6-terra",
        "no_semantic_validator_provider_call_this_phase": True,
        "terra_pricing": {
            "verified": bool(terra.verified) if terra else False,
            "input_cost_per_1m_tokens": (
                float(terra.input_cost_per_1m_tokens) if terra else None
            ),
            "output_cost_per_1m_tokens": (
                float(terra.output_cost_per_1m_tokens) if terra else None
            ),
            "unmodeled_regimes": (
                getattr(terra, "unmodeled_regimes", None) if terra else None
            ),
            "cost_status": "base_estimate",
        },
        "future_call_count_if_per_chapter": 19,
        "future_cost_not_spent": True,
        "phase_5_not_started": True,
    }


def readiness_payload(
    *,
    result: str,
    future_request: Mapping[str, Any],
    tests: Mapping[str, Any],
    ready_for_hardened_canary: bool,
) -> dict[str, Any]:
    return {
        "phase": "4B.2.1",
        "result": result,
        "historical_4b2_status": HISTORICAL_4B2_STATUS,
        "real_provider_calls": 0,
        "selected_hardening": (
            f"{SUCCESSOR_PROMPT_VERSION} + local validator "
            f"{BOOK_GENERATOR_VALIDATOR_VERSION} + hybrid semantic strategy"
        ),
        "successor_prompt": SUCCESSOR_PROMPT_VERSION,
        "transport": TRANSPORT_VERSION,
        "schema_changed": False,
        "future_model": FUTURE_MODEL,
        "future_thinking": FUTURE_THINKING,
        "future_max_output": EXPECTED_MAX_OUTPUT,
        "future_hydration": HYDRATION_STRATEGY,
        "future_request_sha256": future_request.get("request_sha256"),
        "future_request_determinism": future_request.get("determinism"),
        "READY_FOR_ONE_HARDENED_CH016_CANARY": "YES" if ready_for_hardened_canary else "NO",
        "READY_FOR_PRODUCTION_PREFLIGHT": "NO",
        "READY_FOR_FULL_REAL_BOOK_GENERATION": "NO",
        "retry_rule": (
            "A later hardened CH016 call is a new explicitly authorized "
            "canary phase. It is not an automatic retry."
        ),
        "book_json": "NOT PUBLISHED",
        "tests": tests,
        "next_action": "HUMAN REVIEW",
    }
