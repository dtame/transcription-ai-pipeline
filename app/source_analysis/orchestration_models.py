"""
Contrats déterministes d'orchestration multi-fenêtres — 3B.7.3.

Aucun timestamp. Aucune consolidation. Ce n'est PAS un SourceMap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.source_analysis.errors import WindowsIncompleteError
from app.source_analysis.window_models import WindowSemanticResult

CACHE_HIT = "HIT"
CACHE_MISS = "MISS"
CACHE_STALE = "STALE"
CACHE_INVALID = "INVALID"
CACHE_CORRUPT = "CORRUPT"

READINESS_READY = "READY"
READINESS_PENDING = "PENDING"
READINESS_FAILED = "FAILED"

EXECUTION_NONE = "NONE"
EXECUTION_GENERATED = "GENERATED"
EXECUTION_TRANSPORT_RECOVERED = "TRANSPORT_RECOVERED"

FAILURE_POLICY_STOP_ON_FIRST = "STOP_ON_FIRST_EXECUTION_FAILURE"
EXECUTION_ORDER_SEQUENTIAL = "SEQUENTIAL"
MAX_ATTEMPTS_PER_WINDOW = 1

CACHE_STATES = frozenset(
    {CACHE_HIT, CACHE_MISS, CACHE_STALE, CACHE_INVALID, CACHE_CORRUPT}
)
READINESS_STATES = frozenset(
    {READINESS_READY, READINESS_PENDING, READINESS_FAILED}
)


@dataclass(frozen=True)
class WindowCacheInspection:
    """Classification déterministe d'une entrée de cache. Pas un booléen."""

    window_id: str
    expected_signature: str
    cache_state: str
    transport_present: bool
    metadata_present: bool
    result_present: bool
    transport_hash_matches: bool
    signature_matches: bool
    recoverable: bool
    result: WindowSemanticResult | None = None
    error_classification: str | None = None
    transport_path: str = ""
    result_path: str = ""
    metadata_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "expected_signature": self.expected_signature,
            "cache_state": self.cache_state,
            "transport_present": self.transport_present,
            "metadata_present": self.metadata_present,
            "result_present": self.result_present,
            "transport_hash_matches": self.transport_hash_matches,
            "signature_matches": self.signature_matches,
            "recoverable": self.recoverable,
            "error_classification": self.error_classification,
            "transport_path": self.transport_path,
            "result_path": self.result_path,
            "metadata_path": self.metadata_path,
        }


@dataclass(frozen=True)
class WindowOrchestrationStatus:
    """Observabilité d'une fenêtre — ordre WindowPlan. Pas de secrets."""

    window_id: str
    expected_signature: str
    cache_state: str
    execution_kind: str
    execution_attempted: bool
    call_consumed: bool
    transport_present: bool
    transport_recovered: bool
    result_valid: bool
    readiness: str
    error_classification: str | None = None
    transport_path: str = ""
    result_path: str = ""
    metadata_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "expected_signature": self.expected_signature,
            "cache_state": self.cache_state,
            "execution_kind": self.execution_kind,
            "execution_attempted": self.execution_attempted,
            "call_consumed": self.call_consumed,
            "transport_present": self.transport_present,
            "transport_recovered": self.transport_recovered,
            "result_valid": self.result_valid,
            "readiness": self.readiness,
            "error_classification": self.error_classification,
            "transport_path": self.transport_path,
            "result_path": self.result_path,
            "metadata_path": self.metadata_path,
        }


@dataclass(frozen=True)
class WindowOrchestrationResult:
    """
    Résumé déterministe d'une passe d'orchestration.

    all_windows_ready seulement si chaque WindowInput du plan a
    exactement un WindowSemanticResult courant valide.
    """

    plan_sha256: str
    planner_version: str
    transcript_id: str
    total_windows: int
    ready_windows: int
    generated_windows: int
    cache_hit_windows: int
    transport_recovered_windows: int
    failed_windows: int
    pending_windows: int
    all_windows_ready: bool
    new_calls_consumed: int
    max_new_calls: int | None
    execution_order: str
    failure_policy: str
    statuses: tuple[WindowOrchestrationStatus, ...]
    ready_results: tuple[WindowSemanticResult, ...] = ()
    real_anthropic_cost: int = 0
    real_provider_calls: int = 0
    fake_ai_calls: int = 0
    reporting: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_sha256": self.plan_sha256,
            "planner_version": self.planner_version,
            "transcript_id": self.transcript_id,
            "total_windows": self.total_windows,
            "ready_windows": self.ready_windows,
            "generated_windows": self.generated_windows,
            "cache_hit_windows": self.cache_hit_windows,
            "transport_recovered_windows": self.transport_recovered_windows,
            "failed_windows": self.failed_windows,
            "pending_windows": self.pending_windows,
            "all_windows_ready": self.all_windows_ready,
            "new_calls_consumed": self.new_calls_consumed,
            "max_new_calls": self.max_new_calls,
            "execution_order": self.execution_order,
            "failure_policy": self.failure_policy,
            "statuses": [status.to_dict() for status in self.statuses],
            "real_anthropic_cost": self.real_anthropic_cost,
            "real_provider_calls": self.real_provider_calls,
            "fake_ai_calls": self.fake_ai_calls,
            "reporting": dict(self.reporting),
        }

    def get_ready_results_in_plan_order(self) -> tuple[WindowSemanticResult, ...]:
        """
        Handoff futur ConsolidationInputBuilder.

        Zéro transformation sémantique. Échoue si le jeu n'est pas complet.
        """
        if not self.all_windows_ready:
            raise WindowsIncompleteError(
                "ALL_WINDOWS_READY refusé : "
                f"{self.ready_windows}/{self.total_windows} fenêtres prêtes."
            )
        return self.ready_results


def assert_all_windows_ready(result: WindowOrchestrationResult) -> None:
    """Porte de consolidation future — jeu partiel interdit."""
    result.get_ready_results_in_plan_order()


def reporting_counters(result: WindowOrchestrationResult) -> dict[str, Any]:
    return {
        "strategy": "hybrid",
        "windows": {
            "total": result.total_windows,
            "ready": result.ready_windows,
            "cached": result.cache_hit_windows,
            "generated": result.generated_windows,
            "failed": result.failed_windows,
            "pending": result.pending_windows,
            "transport_recovered": result.transport_recovered_windows,
        },
        "all_windows_ready": result.all_windows_ready,
    }


__all__ = [
    "CACHE_CORRUPT",
    "CACHE_HIT",
    "CACHE_INVALID",
    "CACHE_MISS",
    "CACHE_STALE",
    "CACHE_STATES",
    "EXECUTION_GENERATED",
    "EXECUTION_NONE",
    "EXECUTION_ORDER_SEQUENTIAL",
    "EXECUTION_TRANSPORT_RECOVERED",
    "FAILURE_POLICY_STOP_ON_FIRST",
    "MAX_ATTEMPTS_PER_WINDOW",
    "READINESS_FAILED",
    "READINESS_PENDING",
    "READINESS_READY",
    "READINESS_STATES",
    "WindowCacheInspection",
    "WindowOrchestrationResult",
    "WindowOrchestrationStatus",
    "assert_all_windows_ready",
    "reporting_counters",
]
