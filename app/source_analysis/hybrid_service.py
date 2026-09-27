"""
Orchestration offline hybride — 3B.7.5.

    TranscriptInput
        → WindowPlannerV2 (déjà fourni)
        → WindowAnalysisOrchestrator / FakeAI
        → ConsolidationInput
        → Fake consolidation
        → HybridCanonicalReconstructor
        → normalize_source_map()
        → validateur canonique

NON branché dans analyzer.py. Engine FakeAI obligatoire.
Aucun writer de production contre un projet réel.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.ai.providers.fake import FakeAIEngine
from app.source_analysis.consolidation_analyzer import consolidate
from app.source_analysis.consolidation_input import build_consolidation_input
from app.source_analysis.consolidation_models import ConsolidationSemanticResult
from app.source_analysis.errors import HybridPreconditionError, HybridReconstructionError
from app.source_analysis.hybrid_e2e_fixtures import HybridMappedFakeAI
from app.source_analysis.hybrid_reconstructor import (
    reconstruct_source_map,
    reconstruction_allowed,
)
from app.source_analysis.models import SourceMap
from app.source_analysis.orchestration_models import WindowOrchestrationResult
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_orchestrator import orchestrate_windows
from app.source_analysis_hybrid.contracts import WindowPlan


@dataclass(frozen=True)
class HybridRunResult:
    source_map: SourceMap | None
    orchestration: WindowOrchestrationResult
    consolidation_result: ConsolidationSemanticResult | None
    all_windows_ready: bool
    consolidation_available: bool
    canonical_reconstruction_allowed: bool
    window_fake_calls: int
    consolidation_fake_calls: int
    real_provider_calls: int = 0


def assert_fake_engine(engine) -> None:
    if engine is None:
        raise HybridReconstructionError(
            "run_hybrid_source_analysis exige un FakeAI injecté. "
            "Aucun get_engine_for_stage."
        )
    if not isinstance(engine, FakeAIEngine):
        raise HybridReconstructionError(
            f"engine {type(engine).__name__} interdit — FakeAI only."
        )


def run_hybrid_source_analysis(
    transcript: TranscriptInput,
    plan: WindowPlan,
    engine,
    *,
    windows_root: Path,
    consolidation_root: Path,
    project_name: str = "hybrid-e2e",
    max_new_calls: int | None = None,
    prompt_version: str | None = None,
) -> HybridRunResult:
    """
    Pipeline hybride offline. N'écrit jamais le source_map de production.
    """
    assert_fake_engine(engine)
    window_before = (
        engine.window_calls if isinstance(engine, HybridMappedFakeAI) else engine.call_count
    )
    orchestration = orchestrate_windows(
        plan,
        transcript,
        engine=engine,
        windows_root=windows_root,
        project_name=project_name,
        max_new_calls=max_new_calls,
        prompt_version=prompt_version,
    )
    if isinstance(engine, HybridMappedFakeAI):
        window_fake_calls = engine.window_calls - window_before
    else:
        window_fake_calls = engine.call_count - window_before

    if not orchestration.all_windows_ready:
        return HybridRunResult(
            source_map=None,
            orchestration=orchestration,
            consolidation_result=None,
            all_windows_ready=False,
            consolidation_available=False,
            canonical_reconstruction_allowed=False,
            window_fake_calls=window_fake_calls,
            consolidation_fake_calls=0,
        )

    built = build_consolidation_input(orchestration, plan=plan)
    cons_before = (
        engine.consolidation_calls
        if isinstance(engine, HybridMappedFakeAI)
        else engine.call_count
    )
    consolidation_result = consolidate(
        built,
        engine,
        consolidation_root=consolidation_root,
        project_name=project_name,
    )
    if isinstance(engine, HybridMappedFakeAI):
        consolidation_fake_calls = engine.consolidation_calls - cons_before
    else:
        consolidation_fake_calls = engine.call_count - cons_before

    source_map = reconstruct_source_map(
        transcript,
        plan,
        orchestration.get_ready_results_in_plan_order(),
        consolidation_result,
        consolidation_input=built,
        orchestration=orchestration,
    )
    allowed = reconstruction_allowed(
        all_windows_ready=True,
        consolidation_available=True,
    )
    return HybridRunResult(
        source_map=source_map,
        orchestration=orchestration,
        consolidation_result=consolidation_result,
        all_windows_ready=True,
        consolidation_available=True,
        canonical_reconstruction_allowed=allowed,
        window_fake_calls=window_fake_calls,
        consolidation_fake_calls=max(consolidation_fake_calls, 0),
    )


def preflight_hybrid_reconstruction(
    transcript: TranscriptInput,
    plan: WindowPlan,
    engine,
    *,
    windows_root: Path,
) -> HybridRunResult:
    """Préflight : max_new_calls=0. Aucune exécution sémantique FakeAI."""
    assert_fake_engine(engine)
    orchestration = orchestrate_windows(
        plan,
        transcript,
        engine=engine,
        windows_root=windows_root,
        max_new_calls=0,
    )
    allowed = reconstruction_allowed(
        all_windows_ready=orchestration.all_windows_ready,
        consolidation_available=False,
    )
    if allowed:
        raise HybridPreconditionError(
            "préflight réel ne doit pas autoriser la reconstruction."
        )
    return HybridRunResult(
        source_map=None,
        orchestration=orchestration,
        consolidation_result=None,
        all_windows_ready=orchestration.all_windows_ready,
        consolidation_available=False,
        canonical_reconstruction_allowed=False,
        window_fake_calls=getattr(engine, "window_calls", engine.call_count),
        consolidation_fake_calls=getattr(engine, "consolidation_calls", 0),
    )


__all__ = [
    "HybridRunResult",
    "assert_fake_engine",
    "preflight_hybrid_reconstruction",
    "run_hybrid_source_analysis",
]
