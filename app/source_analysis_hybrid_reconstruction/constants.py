"""Constantes 3B.7.5 — reconstruction canonique hybride + E2E FakeAI."""

from __future__ import annotations

from app.source_analysis.hybrid_signature import (
    HYBRID_STRATEGY,
    RECONSTRUCTOR_VERSION,
)
from app.source_analysis.models import SOURCE_MAP_SCHEMA_VERSION

SCHEMA_VERSION = "1.0"
PHASE = "3B.7.5"
MODE = "OFFLINE_HYBRID_END_TO_END_FAKE_AI"

IMPLEMENTATION_ARTIFACT_NAME = (
    "source_analysis_hybrid_canonical_reconstruction.json"
)
SYNTHETIC_ARTIFACT_NAME = "source_analysis_hybrid_end_to_end_fake_ai.json"
PREFLIGHT_ARTIFACT_NAME = (
    "source_analysis_hybrid_reconstruction_real_preflight.json"
)
REPORT_NAME = (
    "PHASE_3B75_HYBRID_CANONICAL_RECONSTRUCTION_END_TO_END_FAKE_AI_REPORT.md"
)

PHASE_3B_STATUS = "INCOMPLETE"
NEXT_PHASE = "3B.7.6_HYBRID_PRODUCTION_EXECUTION_READINESS_AND_REAL_CALL_PLAN"
NEXT_PHASE_LABEL = (
    "3B.7.6 — HYBRID PRODUCTION EXECUTION READINESS & REAL-CALL PLAN"
)

CANONICAL_SCHEMA_VERSION = SOURCE_MAP_SCHEMA_VERSION
RECONSTRUCTOR = RECONSTRUCTOR_VERSION
STRATEGY = HYBRID_STRATEGY

PHASE_3B74_NOW_HISTORICAL = (
    "audit/PHASE_3B74_CONSOLIDATION_TRANSPORT_DECODER_VALIDATOR_REPORT.md",
    "audit/source_analysis_consolidation_implementation.json",
    "audit/source_analysis_consolidation_fake_ai.json",
    "audit/source_analysis_consolidation_real_preflight.json",
    "audit/source_analysis_consolidation_transport_schema_metrics.json",
)

__all__ = [
    "CANONICAL_SCHEMA_VERSION",
    "IMPLEMENTATION_ARTIFACT_NAME",
    "MODE",
    "NEXT_PHASE",
    "NEXT_PHASE_LABEL",
    "PHASE",
    "PHASE_3B74_NOW_HISTORICAL",
    "PHASE_3B_STATUS",
    "PREFLIGHT_ARTIFACT_NAME",
    "RECONSTRUCTOR",
    "REPORT_NAME",
    "SCHEMA_VERSION",
    "STRATEGY",
    "SYNTHETIC_ARTIFACT_NAME",
]
