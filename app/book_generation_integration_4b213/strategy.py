"""Controlled real-generation strategy. Documentation only. Not executed."""

from __future__ import annotations

from typing import Any

from app.book_generation_integration_4b213.constants import PHASE


def controlled_generation_strategy() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "executed": False,
        "order": [
            "1. Offline preflight (this phase).",
            "2. Human review of architecture, contract, FakeAI results, and costs.",
            "3. If later authorized: one real chapter experiment, not CH016 regeneration by default and never 19 chapters.",
            "4. Analyze structure, evidence, Semantic Gate 2.0.2, PASS/REVIEW/BLOCK, and cost.",
            "5. Human decision whether to generalize.",
            "6. Progressive chapter generation with fail-closed gate and isolated acceptance.",
            "7. Independent Book Validator (Phase 5).",
            "8. Book assembly, still unpublished until sign-off.",
        ],
        "stop_conditions": {
            "substantial_inventions": "BLOCK the chapter. Do not auto-regenerate the book.",
            "repeated_false_rejects": "Stop generalization. Diagnose contract vs generator vs model.",
            "contract_failure": "Do not treat as semantic rejection. Do not convert PARTIAL to PASS.",
            "excessive_cost": "Stop. Re-estimate before any further authorized call.",
            "traceability_loss": "BLOCK. Do not accept the chapter.",
            "resume_errors": "Stop. Preserve artifacts. Do not skip validation.",
        },
        "not_executed": True,
        "no_ch016_regeneration": True,
        "no_19_chapter_run": True,
        "no_phase_5": True,
        "no_word_pdf": True,
        "ready_for_one_real_chapter_experiment": False,
        "ready_for_full_real_book_generation": False,
        "next_action": "HUMAN REVIEW",
        "secrets_included": False,
    }


__all__ = ["controlled_generation_strategy"]
