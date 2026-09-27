"""Constantes 3B.7.4 — consolidation transport / decoder / validator."""

from __future__ import annotations

from app.source_analysis.consolidation_models import (
    CONSOLIDATION_CONNECT_TIMEOUT_SECONDS,
    CONSOLIDATION_FALLBACK,
    CONSOLIDATION_MAX_ATTEMPTS,
    CONSOLIDATION_MAX_OUTPUT_TOKENS,
    CONSOLIDATION_OUTPUT_LANGUAGE,
    CONSOLIDATION_PROMPT_VERSION,
    CONSOLIDATION_READ_TIMEOUT_SECONDS,
    CONSOLIDATION_RETRY,
    CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
    CONSOLIDATION_TARGET_MODEL,
    CONSOLIDATION_TARGET_PROVIDER,
    CONSOLIDATION_TRANSPORT_VERSION,
    STAGE_CONSOLIDATION,
)

SCHEMA_VERSION = "1.0"
PHASE = "3B.7.4"
MODE = "OFFLINE_CONSOLIDATION_FAKE_AI"

IMPLEMENTATION_ARTIFACT_NAME = "source_analysis_consolidation_implementation.json"
SYNTHETIC_ARTIFACT_NAME = "source_analysis_consolidation_fake_ai.json"
PREFLIGHT_ARTIFACT_NAME = "source_analysis_consolidation_real_preflight.json"
SCHEMA_METRICS_ARTIFACT_NAME = (
    "source_analysis_consolidation_transport_schema_metrics.json"
)
REPORT_NAME = "PHASE_3B74_CONSOLIDATION_TRANSPORT_DECODER_VALIDATOR_REPORT.md"

STAGE = STAGE_CONSOLIDATION
PROMPT_VERSION = CONSOLIDATION_PROMPT_VERSION
TRANSPORT_VERSION = CONSOLIDATION_TRANSPORT_VERSION

MAX_OUTPUT_POLICY = {
    "value": CONSOLIDATION_MAX_OUTPUT_TOKENS,
    "source": "3B.7 design consolidation max_output_tokens",
    "kind": "operational_design_bound",
    "provider_guarantee": False,
    "why": (
        "Borne le transport compact d'opérations KEEP/MERGE/REL/REP "
        "et GLOBAL_METADATA. Ce n'est ni 128000 ni le 32000 fenêtre."
    ),
}

TIMEOUT_POLICY = {
    "connect_timeout_seconds": CONSOLIDATION_CONNECT_TIMEOUT_SECONDS,
    "read_timeout_seconds": CONSOLIDATION_READ_TIMEOUT_SECONDS,
    "reuses_7200_blindly": False,
    "why": (
        "Valeurs du design 3B.7 pour source_analysis_consolidation. "
        "1800 s n'est pas le 7200 de l'essai global échoué."
    ),
}

PHASE_3B_STATUS = "INCOMPLETE"
NEXT_PHASE = "3B.7.5_HYBRID_CANONICAL_RECONSTRUCTION_PLUS_END_TO_END_FAKE_AI"
NEXT_PHASE_LABEL = (
    "3B.7.5 — HYBRID CANONICAL RECONSTRUCTION + END-TO-END FAKE AI"
)

PHASE_3B73_NOW_HISTORICAL = (
    "audit/PHASE_3B73_WINDOW_CACHE_RESUME_VALIDATION_ORCHESTRATION_REPORT.md",
    "audit/source_analysis_window_cache_resume_implementation.json",
    "audit/source_analysis_window_cache_resume_fake_ai.json",
    "audit/source_analysis_window_orchestration_real_preflight.json",
)

__all__ = [
    "IMPLEMENTATION_ARTIFACT_NAME",
    "MAX_OUTPUT_POLICY",
    "MODE",
    "NEXT_PHASE",
    "NEXT_PHASE_LABEL",
    "PHASE",
    "PHASE_3B73_NOW_HISTORICAL",
    "PHASE_3B_STATUS",
    "PREFLIGHT_ARTIFACT_NAME",
    "PROMPT_VERSION",
    "REPORT_NAME",
    "SCHEMA_METRICS_ARTIFACT_NAME",
    "SCHEMA_VERSION",
    "STAGE",
    "SYNTHETIC_ARTIFACT_NAME",
    "TIMEOUT_POLICY",
    "TRANSPORT_VERSION",
]
