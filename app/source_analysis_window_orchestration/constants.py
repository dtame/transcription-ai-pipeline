"""Constantes 3B.7.3 — orchestration cache / resume, offline FakeAI."""

from __future__ import annotations

from app.source_analysis.orchestration_models import (
    EXECUTION_ORDER_SEQUENTIAL,
    FAILURE_POLICY_STOP_ON_FIRST,
    MAX_ATTEMPTS_PER_WINDOW,
)

SCHEMA_VERSION = "1.0"
PHASE = "3B.7.3"
MODE = "OFFLINE_FAKE_AI"

IMPLEMENTATION_ARTIFACT_NAME = (
    "source_analysis_window_cache_resume_implementation.json"
)
SYNTHETIC_ARTIFACT_NAME = "source_analysis_window_cache_resume_fake_ai.json"
PREFLIGHT_ARTIFACT_NAME = "source_analysis_window_orchestration_real_preflight.json"
REPORT_NAME = (
    "PHASE_3B73_WINDOW_CACHE_RESUME_VALIDATION_ORCHESTRATION_REPORT.md"
)

PHASE_3B_STATUS = "INCOMPLETE"
NEXT_PHASE = "3B.7.4_CONSOLIDATION_TRANSPORT_DECODER_VALIDATOR"
NEXT_PHASE_LABEL = (
    "3B.7.4 — CONSOLIDATION TRANSPORT + DECODER + VALIDATOR"
)

PHASE_3B72_NOW_HISTORICAL = (
    "audit/PHASE_3B72_WINDOW_ANALYSIS_PIPELINE_WITH_FAKE_AI_REPORT.md",
    "audit/source_analysis_window_pipeline_fake_ai.json",
    "audit/source_analysis_window_pipeline_real_preflight.json",
)

ORCHESTRATION_POLICY = {
    "execution_order": EXECUTION_ORDER_SEQUENTIAL,
    "failure_policy": FAILURE_POLICY_STOP_ON_FIRST,
    "max_attempts_per_window": MAX_ATTEMPTS_PER_WINDOW,
    "cache_revalidation": True,
    "transport_recovery": True,
}

CACHE_POLICY = {
    "identity": "window_analysis_signature",
    "transport_required": True,
    "result_revalidated": True,
    "mtime_identity": False,
    "file_size_identity": False,
    "age_invalidation": False,
}

__all__ = [
    "CACHE_POLICY",
    "IMPLEMENTATION_ARTIFACT_NAME",
    "MODE",
    "NEXT_PHASE",
    "ORCHESTRATION_POLICY",
    "PHASE",
    "PHASE_3B72_NOW_HISTORICAL",
    "PHASE_3B_STATUS",
    "PREFLIGHT_ARTIFACT_NAME",
    "REPORT_NAME",
    "SCHEMA_VERSION",
    "SYNTHETIC_ARTIFACT_NAME",
]
