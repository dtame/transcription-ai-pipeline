"""Comparaison des options de transport de liens. Pas d'implémentation ici."""

from __future__ import annotations

from typing import Any

from app.source_analysis_v2_a15_forensics.constants import (
    MODE,
    PHASE,
    SCHEMA_VERSION,
    SELECTED_LINK_ARCHITECTURE,
)

_CRITERIA = (
    "semantic_clarity",
    "llm_cognitive_burden",
    "deterministic_decoding",
    "grammar_size",
    "anthropic_grammar_compatibility_risk",
    "token_overhead",
    "traceability",
    "canonical_mapping",
    "fakeai_complexity",
    "cost",
    "provider_calls",
)


def build_transport_options() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "principle": (
            "The LLM should make semantic decisions. Python should make "
            "deterministic structural transformations. Prefer removing "
            "arithmetic/index bookkeeping from the LLM if possible without "
            "increasing grammar complexity materially."
        ),
        "should_llm_calculate_global_numeric_indexes": {
            "question": "Should an LLM be required to calculate fragile numeric cross-record indexes at all?",
            "evidence": (
                "IDEA→TOPIC worked 100% with global indexes. 16/18 RELATION "
                "records also used global IDEA indexes correctly. The 7 "
                "invalid links are correct global numbers pointing at TOPIC "
                "records. Arithmetic works when the intended kind is IDEA; "
                "it fails when the model conceptually targets TOPIC."
            ),
            "answer": (
                "Global numeric indexes are usable but fragile for late kinds. "
                "They force bookkeeping the LLM should not own. A kind-bearing "
                "handle removes the arithmetic without letting TOPIC-intended "
                "numbers silently become the wrong IDEA."
            ),
        },
        "criteria": list(_CRITERIA),
        "options": {
            "A_prompt_clarification": {
                "id": "E",
                "name": "PROMPT_ONLY_HARDENING",
                "summary": (
                    "New prompt 1.2.2: RELATION JSON example after several "
                    "TOPIC rows; explicit never-TOPIC-for-RELATION/EXAMPLE."
                ),
                "semantic_clarity": "medium",
                "llm_cognitive_burden": "unchanged-high (still global indexes)",
                "deterministic_decoding": "unchanged",
                "grammar_size": "unchanged",
                "anthropic_grammar_compatibility_risk": "none",
                "token_overhead": "small prompt delta",
                "traceability": "same",
                "canonical_mapping": "same",
                "fakeai_complexity": "none",
                "cost": "same per call",
                "provider_calls": 0,
                "schema_change": False,
                "a13_grammar_reusable": True,
                "verdict": (
                    "NOT SUFFICIENT ALONE. A.14 already made 0-based TARGET "
                    "rules explicit. Kind violations remained. Do not assume "
                    "one more example will hold on WIN001."
                ),
            },
            "B_fixed_local_ordinals_by_kind": {
                "id": "B",
                "name": "FIXED_LOCAL_ORDINALS_BY_KIND",
                "summary": "RELATION/EXAMPLE l references IDEA ordinals, not global indexes.",
                "semantic_clarity": "medium",
                "llm_cognitive_burden": "lower arithmetic, same kind-choice problem",
                "deterministic_decoding": "Python maps ordinal → global",
                "grammar_size": "unchanged integers",
                "anthropic_grammar_compatibility_risk": "none if schema identical",
                "token_overhead": "none",
                "traceability": "needs new transport version",
                "canonical_mapping": "extra Python step",
                "fakeai_complexity": "decoder/validator/fixtures",
                "cost": "same",
                "provider_calls": 0,
                "schema_change": False,
                "a13_grammar_reusable": True,
                "verdict": (
                    "CONTRAINDICATED by A.15. Invalid l=1,2,3,4,5,10,11 are "
                    "TOPIC globals. Under ordinals those numbers would become "
                    "IDEA[1], IDEA[2]… — structurally valid, semantically wrong. "
                    "Silent corruption."
                ),
            },
            "C_inline_relation_targets": {
                "id": "C",
                "name": "INLINE_RELATION_TARGETS",
                "summary": "Nest example/relation associations inside parent objects.",
                "semantic_clarity": "high",
                "llm_cognitive_burden": "low",
                "deterministic_decoding": "harder nested decode",
                "grammar_size": "materially larger",
                "anthropic_grammar_compatibility_risk": "high — new canary required",
                "token_overhead": "higher JSON nesting",
                "traceability": "local",
                "canonical_mapping": "rewrite",
                "fakeai_complexity": "high",
                "cost": "unknown grammar risk",
                "provider_calls": 0,
                "schema_change": True,
                "a13_grammar_reusable": False,
                "verdict": "Reject for now — grammar cost exceeds evidence need.",
            },
            "D_two_pass": {
                "id": "D",
                "name": "TWO_PASS_LOCAL_EXTRACTION",
                "summary": "First concepts, then relationships.",
                "semantic_clarity": "high",
                "llm_cognitive_burden": "split",
                "deterministic_decoding": "two transports",
                "grammar_size": "same or two schemas",
                "anthropic_grammar_compatibility_risk": "medium",
                "token_overhead": "second call input",
                "traceability": "two signatures",
                "canonical_mapping": "join step",
                "fakeai_complexity": "high",
                "cost": "approximately 2× WIN001",
                "provider_calls": 1,
                "schema_change": "maybe",
                "a13_grammar_reusable": "if schema unchanged",
                "verdict": "Not justified. Content quality is already acceptable.",
            },
            "E_local_symbolic_handles": {
                "id": "A",
                "name": "LOCAL_SYMBOLIC_HANDLES",
                "summary": (
                    "Model assigns T1… / I1… handles. RELATION links I3,I7. "
                    "Python maps handles to record indexes / canonical IDs."
                ),
                "semantic_clarity": "high — kind is in the token",
                "llm_cognitive_burden": "low — no global arithmetic",
                "deterministic_decoding": "Python handle map",
                "grammar_size": (
                    "small if l stays integer and handles live in v/m, "
                    "or string l[] which is a schema change"
                ),
                "anthropic_grammar_compatibility_risk": (
                    "UNVERIFIED if l becomes string; none if handles are in m/v "
                    "and schema shape is unchanged"
                ),
                "token_overhead": "a few handle tokens per record",
                "traceability": "excellent",
                "canonical_mapping": "deterministic Python",
                "fakeai_complexity": "moderate new decoder",
                "cost": "same call count",
                "provider_calls": 0,
                "schema_change": "depends on encoding",
                "a13_grammar_reusable": (
                    "YES if schema structure identical; UNVERIFIED if l type changes"
                ),
                "verdict": "PREFERRED. Removes bookkeeping; keeps kind visible so TOPIC-intended links still fail closed.",
            },
        },
        "rejected": ["B_fixed_local_ordinals_by_kind", "C_inline_relation_targets", "D_two_pass"],
        "insufficient_alone": ["A_prompt_clarification"],
        "selected": SELECTED_LINK_ARCHITECTURE,
        "implementation_this_phase": False,
        "reason_not_implemented": (
            "Encoding of handles (string l vs handle-in-m with integer l) is "
            "not uniquely determined. Implementing the wrong encoding would "
            "force a grammar canary or a silent-corruption ordinal scheme. "
            "A.16 selects the architecture; A.17 implements it offline."
        ),
    }


__all__ = ["build_transport_options"]
