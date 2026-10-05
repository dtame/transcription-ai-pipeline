"""Book Generator resumption plan. Documentation only. Nothing is executed."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b212.constants import PHASE


def book_generator_resumption_plan() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "executed": False,
        "questions": {
            "1_minimum_conditions_to_resume_book_generator": [
                "Canonical SourceMap, EditorialPlan, and cleaned transcript hashes unchanged.",
                "Book Generator prompt/transport/validator versions remain the frozen production pair.",
                "Semantic Gate 2.0.2 remains a candidate, not a production hook.",
                "A later human authorization is required before any real chapter generation.",
                "No automatic 19-chapter run.",
            ],
            "2_mandatory_controls_before_book_json_publication": [
                "Independent Book Validator (Phase 5) PASS on the assembled book.",
                "Semantic decisions fail-closed: any BLOCK chapter excluded.",
                "REVIEW chapters not accepted into the production cache.",
                "Source-to-chapter evidence map complete.",
                "Human sign-off on residual ambiguities.",
                "book.json remains unpublished until that sign-off.",
            ],
            "3_blocked_chapter": [
                "Keep the raw generator output and the gate artifacts.",
                "Do not silently regenerate the whole book.",
                "Diagnose: generator invention vs gate contract vs coverage.",
                "If the generator invented content, repair that chapter only after authorization.",
                "If the gate contract failed, do not treat the chapter as semantically rejected.",
            ],
            "4_review_verdict": [
                "REVIEW is not PASS.",
                "REVIEW does not write the production cache.",
                "A human inspects QUESTIONABLE units and evidence handles.",
                "Possible exits: accept with recorded waiver, request a bounded rewrite, or BLOCK.",
            ],
            "5_source_to_chapter_traceability": [
                "Retain SourceMap handles on each generated paragraph.",
                "Keep Semantic Gate unit ids stable (u00, u01, ...).",
                "Store raw model text, parsed JSON, validator errors, and policy decision beside the chapter.",
                "Do not drop IDEA/SRC identifiers during editorial smoothing.",
            ],
            "6_avoid_useless_full_regeneration": [
                "Regenerate only the blocked chapter after a bounded diagnosis.",
                "Do not invalidate chapters that already have a recorded PASS-quality semantic result.",
                "Do not rerun Terra because a contract key was uppercase.",
                "Keep frozen requests; change contract version explicitly.",
            ],
            "7_limit_paid_calls": [
                "No retry. No fallback. No second model.",
                "Do not propose a Terra canary from this phase.",
                "If a later canary is authorized, freeze one request and consume one slot.",
                "Prefer local FakeAI and historical replay for contract work.",
            ],
            "8_integrate_independent_book_validator": [
                "Phase 5 remains a separate validator of the assembled book.",
                "Semantic Gate 2.0.2 does not replace it.",
                "A chapter-level PASS does not skip book-level validation.",
                "Phase 5 is not started from this phase.",
            ],
            "9_remain_under_human_review": [
                "REVIEW and BLOCK outcomes.",
                "Any residual high-risk claim (causality, guarantee, example, reference).",
                "Any contract mismatch even when unit k values look right.",
                "The decision to resume real generation.",
                "Publication of book.json.",
            ],
            "10_shortest_reasonable_path_to_19_chapters": [
                "Human review of this 2.0.2 consolidation.",
                "Controlled integration preflight only (no Terra, no CH016 rewrite).",
                "If authorized later: one contract-proving remote check is a separate phase, not this one.",
                "Then one real chapter (not 19) with fail-closed gate and human review.",
                "Only after that chapter is understood, a bounded remainder — never an unattended 19-chapter run.",
            ],
        },
        "readiness_states": {
            "READY_FOR_CONTROLLED_INTEGRATION_PREFLIGHT": {
                "meaning": "Offline contract, validator, policy, and plan are coherent enough for humans to inspect an integration design. No provider. No chapter generation.",
                "not_equivalent_to_real_generation": True,
            },
            "READY_FOR_REAL_CHAPTER_GENERATION": {
                "meaning": "A later authorization may generate one real chapter under fail-closed controls.",
                "this_phase": False,
            },
            "READY_FOR_FULL_BOOK_GENERATION": {
                "meaning": "All 19 chapters may be generated.",
                "this_phase": False,
            },
        },
        "states_are_not_equivalent": True,
        "READY_FOR_NEW_REMOTE_TERRA_CALL": False,
        "no_ch016_regeneration": True,
        "no_19_chapter_run": True,
        "no_phase_5": True,
        "no_word_pdf": True,
        "secrets_included": False,
    }


__all__ = ["book_generator_resumption_plan"]
