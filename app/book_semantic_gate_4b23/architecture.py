"""Independent semantic-gate architecture. Offline contract only."""

from __future__ import annotations

from typing import Any

from app.ai.thinking import resolve_thinking_capabilities
from app.book_semantic_gate_4b23.constants import (
    CLASSIFICATIONS,
    DETERMINISTIC_VALIDATOR_VERSION,
    EVIDENCE_SCOPE,
    GENERATOR_MODEL_NAME,
    GENERATOR_PROMPT_VERSION,
    GENERATOR_PROVIDER_NAME,
    GRANULARITY,
    SEMANTIC_GATE_MODEL,
    SEMANTIC_GATE_PROVIDER,
    SEMANTIC_GATE_STAGE,
    SEMANTIC_VALIDATION_TRANSPORT_VERSION,
    SEMANTIC_VALIDATOR_PROMPT_VERSION,
    STRUCTURED_OUTPUT_MODE,
    TEMPERATURE_POLICY,
    THINKING_MODE,
)


def architecture_payload() -> dict[str, Any]:
    thinking = resolve_thinking_capabilities(
        SEMANTIC_GATE_PROVIDER, SEMANTIC_GATE_MODEL
    )
    return {
        "phase": "4B.2.3",
        "central_finding": "STRUCTURAL_TRACEABILITY_IS_NOT_SEMANTIC_SUPPORT",
        "central_finding_text": (
            "A paragraph may reference valid IDEA/SRC handles and still contain "
            "an unsupported clause. Valid source_refs are necessary but not "
            "sufficient evidence of semantic fidelity."
        ),
        "second_finding": "REFERENCE_PRESENCE_IS_NOT_LICENSE_TO_COMPLETE_REFERENCE_CONTENT",
        "second_finding_text": (
            "If canonical evidence contains a partial biblical, literary, "
            "historical, or other reference, the generator may not complete or "
            "expand its content from model knowledge."
        ),
        "third_finding": "PLAUSIBILITY_IS_NOT_SUPPORT",
        "third_finding_text": (
            "A claim may be reasonable, theologically familiar, logically "
            "plausible, and stylistically natural, and still be unsupported "
            "by canonical evidence."
        ),
        "responsibilities": {
            "book_generator": {
                "identity": f"{GENERATOR_PROVIDER_NAME} / {GENERATOR_MODEL_NAME}",
                "prompt": GENERATOR_PROMPT_VERSION,
                "role": "creates manuscript prose",
            },
            "book_generation_validator": {
                "identity": DETERMINISTIC_VALIDATOR_VERSION,
                "role": "deterministic structural/provenance validation",
                "owns_empty_paragraph": True,
            },
            "independent_semantic_gate": {
                "identity": f"{SEMANTIC_GATE_PROVIDER} / {SEMANTIC_GATE_MODEL}",
                "prompt": SEMANTIC_VALIDATOR_PROMPT_VERSION,
                "transport": SEMANTIC_VALIDATION_TRANSPORT_VERSION,
                "role": "tests whether generated substantive meaning is actually "
                "supported by canonical evidence",
            },
        },
        "why_independent": {
            "generator": f"{GENERATOR_PROVIDER_NAME} / {GENERATOR_MODEL_NAME}",
            "semantic_validator": f"{SEMANTIC_GATE_PROVIDER} / {SEMANTIC_GATE_MODEL}",
            "goal": "reduce correlated self-validation failure",
            "do_not_use_sonnet_to_validate_sonnet": True,
        },
        "gate_placement": [
            "Sonnet chapter candidate",
            "deterministic BookGenerationValidator",
            "independent semantic gate",
            "production chapter cache acceptance",
        ],
        "gate_order_rule": (
            "Deterministic validator must PASS before the semantic provider "
            "gate may run. Do not spend semantic-validation calls on "
            "structurally invalid chapters."
        ),
        "cache_requires_both_gates": True,
        "phase_5_relationship": {
            "chapter_gate_replaces_phase_5": False,
            "chapter_gate": (
                "local evidence fidelity before cache acceptance"
            ),
            "phase_5": (
                "whole-book semantic validation, coherence, completeness, "
                "redundancy, cross-chapter consistency, unsupported claims "
                "at assembled-book level"
            ),
            "phase_5_started": False,
        },
        "no_whole_book": True,
        "no_whole_transcript": True,
        "validator_role": "evidence-bounded semantic auditor",
        "validator_is_not": [
            "fact checker",
            "theologian",
            "Bible commentator",
            "editor improving prose",
            "co-author",
        ],
        "core_question": (
            "Is every substantive proposition in this text supported by the "
            "supplied canonical evidence?"
        ),
        "evidence_authority": (
            "Judge ONLY against supplied canonical evidence. Do not use own "
            "knowledge to justify generated claims."
        ),
        "granularity": GRANULARITY,
        "granularity_rationale": {
            "paragraph_alone_too_coarse": True,
            "p3_lesson": (
                "One paragraph can contain supported core content plus an "
                "unsupported subordinate causal clause."
            ),
            "p8_lesson": (
                "Supported reference context plus unsupported semantic "
                "completion of a partial REF."
            ),
            "selected": GRANULARITY,
            "rejected_as_sole_unit": ["paragraph", "sentence"],
            "why_not_sentence_only": (
                "A sentence may still hide a subordinate unsupported clause; "
                "claim decomposition with paragraph anchoring is finer and "
                "still locally checkable via text spans."
            ),
        },
        "evidence_scope": EVIDENCE_SCOPE,
        "evidence_scope_decision": {
            "option_a": "only evidence handles declared by the paragraph",
            "option_b": "all canonical evidence assigned to the section/chapter",
            "selected": EVIDENCE_SCOPE,
            "declared_handles": "hints, never proof of support",
            "verification_scope": "bounded canonical section evidence",
            "do_not_rescue_with_other_chapters": True,
            "cross_section_reuse": (
                "only if explicitly authorized by EditorialPlan"
            ),
            "hydrated_src_authority": "primary wording/context evidence",
            "source_map_authority": "semantic organization and traceability",
        },
        "partial_reference_rule": (
            "A partial REF permits only what the supplied REF/SRC evidence "
            "actually contains. The validator must not infer the omitted "
            "remainder from its own knowledge."
        ),
        "not_bible_specific": True,
        "quotations": (
            "A model-generated quotation must be supported by supplied "
            "canonical wording. Do not accept a remembered quotation merely "
            "because the reference is correct."
        ),
        "paraphrase_allowed": True,
        "paraphrase_test": "semantic entailment, not lexical equality",
        "synthesis_allowed": (
            "Synthesis across multiple supplied evidence items is allowed if "
            "the result does not exceed their combined support."
        ),
        "causality": {
            "connectors": [
                "because",
                "therefore",
                "thus",
                "so that",
                "which means",
                "as a result",
            ],
            "risk": "may create claims stronger than source evidence",
            "keyword_matching_final": False,
        },
        "temporal_intensity_strengthening": [
            "sometimes → always",
            "may → will",
            "associated with → causes",
            "possible → certain",
            "partial → complete",
        ],
        "uncertainty": "preserve canonical uncertainty; reject unjustified certainty",
        "connective_prose": (
            "Inspect connective prose if it contains substantive meaning. "
            "Provider label con is not authoritative."
        ),
        "non_substantive": (
            "Purely rhetorical/structural transitions may classify "
            "NON_SUBSTANTIVE."
        ),
        "classifications": list(CLASSIFICATIONS),
        "no_chain_of_thought": True,
        "no_automatic_repair": True,
        "no_generator_feedback_loop": True,
        "future_repair_options_not_implemented": [
            "human correction",
            "explicit controlled regeneration",
            "versioned prompt change",
            "chapter rejection",
        ],
        "structured_output": {
            "engine_mode": STRUCTURED_OUTPUT_MODE,
            "native_json_schema_response_format": False,
            "reason": (
                "Existing OpenAIEngine uses response_format=json_object. "
                "Do not invent unverified json_schema request features."
            ),
        },
        "thinking": {
            "proposed_mode": THINKING_MODE,
            "effort": None,
            "terra_capabilities_known": thinking.known,
            "terra_thinking_disabled_supported": thinking.thinking_disabled_supported,
            "terra_adaptive_supported": thinking.adaptive_thinking_supported,
            "terra_effort_supported": thinking.effort_supported,
            "do_not_copy_sonnet_or_planner": True,
            "rationale": (
                "resolve_thinking_capabilities(openai, gpt-5.6-terra) is "
                "unverified. thinking_mode=disabled and effort would be "
                "rejected locally. provider_default omits thinking fields."
            ),
        },
        "temperature": {
            "policy": TEMPERATURE_POLICY,
            "terra_supports_temperature": False,
            "rationale": (
                "Phase 2B capabilities do not claim Terra temperature control. "
                "Offline payloads must omit temperature."
            ),
        },
        "stage": SEMANTIC_GATE_STAGE,
        "empty_paragraph": "deterministic_validator_blocks_before_semantic_gate",
        "p9b_not_a_semantic_benchmark_case": True,
        "production_cache_4b22": "NOT ACCEPTED",
        "book_json": "NOT PUBLISHED",
    }


__all__ = ["architecture_payload"]
