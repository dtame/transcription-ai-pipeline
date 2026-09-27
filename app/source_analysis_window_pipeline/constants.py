"""Constantes 3B.7.2 — pipeline fenêtre FakeAI, offline."""

from __future__ import annotations

from app.source_analysis.window_models import (
    STAGE_WINDOW,
    TARGET_MODEL,
    TARGET_PROVIDER,
    WINDOW_CONNECT_TIMEOUT_SECONDS,
    WINDOW_FALLBACK,
    WINDOW_MAX_ATTEMPTS,
    WINDOW_MAX_OUTPUT_TOKENS,
    WINDOW_READ_TIMEOUT_SECONDS,
    WINDOW_RETRY,
)
from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION_V10
from app.source_analysis_hybrid.constants import (
    HARD_MAX_INPUT_TOKENS,
    PLANNER_VERSION,
    WINDOW_TRANSPORT_VERSION,
)

SCHEMA_VERSION = "1.0"
PHASE = "3B.7.2"
MODE = "OFFLINE_FAKE_AI"

FAKE_ARTIFACT_NAME = "source_analysis_window_pipeline_fake_ai.json"
PREFLIGHT_ARTIFACT_NAME = "source_analysis_window_pipeline_real_preflight.json"
REPORT_NAME = "PHASE_3B72_WINDOW_ANALYSIS_PIPELINE_WITH_FAKE_AI_REPORT.md"

STAGE = STAGE_WINDOW
PROMPT_VERSION = WINDOW_ANALYSIS_PROMPT_VERSION_V10
TRANSPORT_VERSION = WINDOW_TRANSPORT_VERSION

MAX_OUTPUT_POLICY = {
    "value": WINDOW_MAX_OUTPUT_TOKENS,
    "source": "3B.7 design WINDOW_MAX_OUTPUT_TOKENS",
    "kind": "operational_design_bound",
    "provider_guarantee": False,
    "why": (
        "Borne le workload de réponse d'une fenêtre tout en laissant "
        "assez de place pour une extraction sémantique riche "
        "semantic-transport-v1. Ce n'est pas une prédiction exacte "
        "du volume de sortie, ni un héritage du 128000 global."
    ),
}

TIMEOUT_POLICY = {
    "connect_timeout_seconds": WINDOW_CONNECT_TIMEOUT_SECONDS,
    "read_timeout_seconds": WINDOW_READ_TIMEOUT_SECONDS,
    "reuses_7200_blindly": False,
    "why": (
        "Valeurs du design 3B.7 pour source_analysis_window. "
        "1800 s n'est pas le 7200 de l'essai global échoué. "
        "Aucun timeout provider n'est exercé en 3B.7.2."
    ),
}

PHASE_3B_STATUS = "INCOMPLETE"
NEXT_PHASE = "3B.7.3_WINDOW_CACHE_RESUME_VALIDATION_ORCHESTRATION"
NEXT_PHASE_LABEL = "3B.7.3 — WINDOW CACHE / RESUME / VALIDATION ORCHESTRATION"

PHASE_3B71_NOW_HISTORICAL = (
    "audit/source_analysis_window_planner_v2_implementation.json",
    "audit/PHASE_3B71_WINDOW_PLANNER_V2_AND_HYBRID_CONTRACTS_REPORT.md",
)

__all__ = [
    "FAKE_ARTIFACT_NAME",
    "HARD_MAX_INPUT_TOKENS",
    "MODE",
    "NEXT_PHASE",
    "PHASE",
    "PLANNER_VERSION",
    "PREFLIGHT_ARTIFACT_NAME",
    "PROMPT_VERSION",
    "REPORT_NAME",
    "SCHEMA_VERSION",
    "STAGE",
    "TARGET_MODEL",
    "TARGET_PROVIDER",
    "TRANSPORT_VERSION",
    "WINDOW_MAX_ATTEMPTS",
    "WINDOW_MAX_OUTPUT_TOKENS",
    "WINDOW_RETRY",
    "WINDOW_FALLBACK",
]
