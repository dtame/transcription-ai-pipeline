"""Options d'architecture output-bounded. Évaluation offline seulement."""

from __future__ import annotations

from typing import Any

from app.source_analysis_output_ceiling_review.constants import SELECTED_ARCHITECTURE


def build_architecture_options() -> dict[str, Any]:
    candidates = [
        {
            "id": "A",
            "name": "SINGLE_PASS_BOUNDED_WINDOW",
            "summary": (
                "Current: one window produces all topics/ideas/examples/"
                "references/uncertainties/relations/voice/intent/audience."
            ),
            "prevents_thinking_fill": False,
            "prevents_kind_order_tail_loss": False,
            "provider_enforced": False,
            "call_count": "1 per window",
            "traceability": True,
            "python_semantic_merge": False,
            "no_drop": "overflow token only, after generation",
            "status": "INSUFFICIENT_AS_SOLE_MECHANISM",
            "why": (
                "CALL C already used this shape. 21911 thinking tokens "
                "consumed the shared max_tokens before trailing kinds finished."
            ),
        },
        {
            "id": "B",
            "name": "MULTI_PASS_SEMANTIC_EXTRACTION",
            "summary": (
                "Pass 1 topics+ideas; pass 2 examples/refs/uncertainties; "
                "pass 3 relations/repetitions; pass 4 voice/intent/audience."
            ),
            "prevents_thinking_fill": False,
            "prevents_kind_order_tail_loss": True,
            "provider_enforced": False,
            "call_count": "3–4 per window",
            "traceability": True,
            "python_semantic_merge": False,
            "no_drop": "per-pass capacity signal",
            "status": "DEFERRED",
            "why": (
                "Reliability-friendly for kind coverage, but each pass can "
                "re-spend ~20k thinking tokens. Input is repeated. Cost "
                "risk dominates unless thinking is first capped."
            ),
        },
        {
            "id": "C",
            "name": "TWO_STAGE_INVENTORY_PLUS_DETAIL",
            "summary": (
                "Stage 1 compact inventory ids + source refs; stage 2 "
                "expands selected items."
            ),
            "prevents_thinking_fill": False,
            "prevents_kind_order_tail_loss": True,
            "provider_enforced": False,
            "call_count": "2+ per window",
            "traceability": True,
            "python_semantic_merge": False,
            "no_drop": "inventory must list overflow",
            "status": "DEFERRED",
            "why": (
                "Useful later. Still multiplies thinking unless budget is split. "
                "Stage-1 schema must stay ultra-compact."
            ),
        },
        {
            "id": "D",
            "name": "SRC_BATCH_EXTRACTION_PLUS_LOCAL_ACCOUNTING_PLUS_AI_CONSOLIDATION",
            "summary": (
                "Much smaller SRC batches emit bounded records; hierarchy consolidates."
            ),
            "prevents_thinking_fill": False,
            "prevents_kind_order_tail_loss": True,
            "provider_enforced": False,
            "call_count": "HIGH — call explosion risk",
            "traceability": True,
            "python_semantic_merge": False,
            "no_drop": "batch accounting",
            "status": "DEFERRED",
            "why": (
                "CALL C already showed grouping works. Further SRC slicing "
                "multiplies thinking cost. Adaptive hierarchy remains useful "
                "downstream, not as the first output fix."
            ),
        },
        {
            "id": "E",
            "name": "PAGINATED_SEMANTIC_EXTRACTION",
            "summary": (
                "Provider returns a bounded page plus a continuation cursor."
            ),
            "prevents_thinking_fill": False,
            "prevents_kind_order_tail_loss": True,
            "provider_enforced": False,
            "call_count": "variable",
            "traceability": True,
            "python_semantic_merge": False,
            "no_drop": "depends on cursor honesty",
            "status": "REJECTED",
            "why": (
                "A model-invented cursor is not deterministic. Continuation "
                "must be a Python-assigned SRC/range, which is candidate F."
            ),
        },
        {
            "id": "F",
            "name": "HYBRID_DETERMINISTIC_SOURCE_PARTITION_PLUS_BOUNDED_QUOTA",
            "summary": (
                "Python assigns deterministic SRC subranges. Each request "
                "has a fixed source subrange and bounded semantic output."
            ),
            "prevents_thinking_fill": False,
            "prevents_kind_order_tail_loss": True,
            "provider_enforced": False,
            "call_count": "1+ per overflow split",
            "traceability": True,
            "python_semantic_merge": False,
            "no_drop": "deterministic subdivision + capacity signal",
            "status": "SECONDARY_MECHANISM",
            "why": (
                "Keep as overflow path. Do not assume another input halving "
                "fixes output: CALL C already halved input and still hit 32000."
            ),
        },
        {
            "id": "G",
            "name": SELECTED_ARCHITECTURE,
            "summary": (
                "Single local pass of a smaller kind set; defer global "
                "metadata; cap/reserve thinking vs JSON tokens; overflow "
                "uses deterministic subdivision (F)."
            ),
            "prevents_thinking_fill": "IF_THINKING_BUDGET_IS_SET",
            "prevents_kind_order_tail_loss": True,
            "provider_enforced": False,
            "call_count": "1 per window unless overflow",
            "traceability": True,
            "python_semantic_merge": False,
            "no_drop": "capacity signal + deterministic split",
            "status": "SELECTED",
            "why": (
                "CALL C prefix already completed TOPIC/IDEA/RELATION/"
                "EXAMPLE/REFERENCE/UNCERTAINTY. Truncation hit REPETITION "
                "after 21911 thinking tokens. Shrink the tail, reserve JSON "
                "budget, keep small planner and hierarchy."
            ),
        },
    ]
    return {
        "mechanisms": {
            "A_prompt_only": {
                "can_prevent": "nothing technical",
                "cannot_prevent": "overgeneration, thinking fill, token spend",
            },
            "B_provider_schema_cardinality": {
                "can_prevent": "nothing currently — maxItems unsupported locally",
                "cannot_prevent": "thinking tokens; unverified grammar risk",
            },
            "C_architectural_decomposition": {
                "can_prevent": "kind-order starvation; oversized local scope",
                "cannot_prevent": "thinking fill unless budget is reserved",
            },
            "D_post_generation_validation": {
                "can_prevent": "accepting excessive parsed output",
                "cannot_prevent": "spending 32000 tokens first",
            },
        },
        "candidates": candidates,
        "output_quota_axes": [
            "record count",
            "per-kind record count",
            "per-record text length",
            "source-ref count",
            "thinking token budget",
        ],
        "range_compression": "FORBIDDEN if it hides sparse IDs",
        "python_semantic_merge": False,
        "ai_semantic_merge": True,
    }
