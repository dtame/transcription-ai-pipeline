"""Faits d'implémentation déterministes 3B.7.7A.2."""

from __future__ import annotations

from typing import Any

from app.source_analysis.ultra_compact_schema import SEMANTIC_TRANSPORT_VERSION
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
)
from app.source_analysis_window_output_bounding.constants import (
    REAL_PROVIDER_CALLS_THIS_PHASE,
    WIN001_RETRIED,
)


def implementation_facts() -> dict[str, Any]:
    return {
        "modules_changed": [
            "app/source_analysis/errors.py",
            "app/source_analysis/window_prompt.py",
            "app/source_analysis/window_analyzer.py",
            "app/source_analysis/window_validator.py",
            "app/source_analysis/window_signature.py",
            "app/source_analysis/window_orchestrator.py",
            "app/source_analysis/window_cache.py",
            "app/source_analysis/hybrid_service.py",
            "app/source_analysis/hybrid_signature.py",
            "app/source_analysis/hybrid_reconstructor.py",
            "app/source_analysis_window_pipeline/constants.py",
            "app/source_analysis_window_pipeline/runner.py",
            "app/source_analysis_window_orchestration/runner.py",
            "app/source_analysis_win001_failure_diagnosis/accounting.py",
            "app/source_analysis_win001_failure_diagnosis/diagnosis.py",
            "app/source_analysis_hybrid_readiness/constants.py",
            "app/source_analysis_hybrid_readiness/facts.py",
            "app/source_analysis_hybrid_readiness/canary.py",
            "app/source_analysis_hybrid_reconstruction/runner.py",
            "app/source_analysis_consolidation/runner.py",
        ],
        "modules_added": [
            "app/source_analysis/window_granularity.py",
            "app/source_analysis/window_granularity_fixtures.py",
            "app/source_analysis_window_output_bounding/",
        ],
        "validator_additions": [
            "validate_window_transport_granularity",
            "validate_window_result_granularity",
        ],
        "error_types": [
            "WindowSemanticCapacityExceeded",
            "WindowGranularityLimitExceeded",
        ],
        "prompt_versioning": {
            "historical": WINDOW_ANALYSIS_PROMPT_VERSION_V10,
            "successor": WINDOW_ANALYSIS_PROMPT_VERSION,
            "historical_mutated": False,
        },
        "transport_version_status": {
            "version": SEMANTIC_TRANSPORT_VERSION,
            "generation_c_changed": False,
            "overflow_representation": (
                "UNCERTAINTY.v exact token analysis_capacity_exceeded; "
                "no schema field added"
            ),
        },
        "signature_behavior": (
            "window analysis signature includes prompt_version and prompt SHA; "
            "1.1 invalidates 1.0 cache without a special hack"
        ),
        "consolidation_compatibility": True,
        "reconstructor_compatibility": True,
        "canonical_schema_changed": False,
        "generation_c_changed": False,
        "local_semantic_merge": False,
        "local_string_truncation": False,
        "max_output_changed": False,
        "window_plan_changed": False,
        "network": 0,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "win001_retried": WIN001_RETRIED,
        "tests": [
            "policy config",
            "prompt versioning",
            "soft targets",
            "hard ceilings",
            "multi-SRC grouping",
            "record counts",
            "per-kind ceilings",
            "total ceiling",
            "relation ceiling",
            "text size",
            "overflow signal",
            "transport-first on over-limit",
            "no local truncation",
            "no local semantic merge",
            "signature invalidation",
            "cache compatibility",
            "consolidation compatibility",
            "reconstructor compatibility",
            "FakeAI E2E",
            "network block",
        ],
    }


__all__ = ["implementation_facts"]
