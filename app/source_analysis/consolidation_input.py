"""
ConsolidationInputBuilder — 3B.7.4.

ALL_WINDOWS_READY obligatoire. Ordre WindowPlan, jamais filesystem/mtime.
Pas de transcript complet. Pas de texte SRC original.
"""

from __future__ import annotations

from typing import Sequence

from app.ai.estimation import estimate_tokens
from app.source_analysis.errors import (
    ConsolidationContextExceeded,
    ConsolidationInputError,
    WindowsIncompleteError,
)
from app.source_analysis.models import forbidden_editorial_fields
from app.source_analysis.orchestration_models import WindowOrchestrationResult
from app.source_analysis.window_models import WindowSemanticResult
from app.source_analysis.window_validator import validate_window_result
from app.source_analysis.consolidation_models import (
    CONSOLIDATION_INPUT_SCHEMA_VERSION,
    CONSOLIDATION_OUTPUT_LANGUAGE,
    CONSOLIDATION_PROMPT_VERSION,
    CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
    CONSOLIDATION_TARGET_MODEL,
    CONSOLIDATION_TRANSPORT_VERSION,
    ConsolidationInput,
    ConsolidationInputRecord,
    ConsolidationInputWindow,
    record_category,
)
from app.source_analysis_hybrid.constants import ESTIMATION_MODEL, PLAN_STRATEGY
from app.source_analysis_hybrid.contracts import (
    WindowPlan,
    canonical_dumps,
    canonical_hash,
)


def _assert_no_editorial(payload: dict, *, location: str) -> None:
    leaked = forbidden_editorial_fields(payload)
    if leaked:
        raise ConsolidationInputError(
            f"fuite éditoriale dans {location} : {leaked}"
        )


def _ordered_results_from_plan(
    plan: WindowPlan,
    results: Sequence[WindowSemanticResult],
) -> tuple[WindowSemanticResult, ...]:
    by_id: dict[str, list[WindowSemanticResult]] = {}
    for result in results:
        by_id.setdefault(result.window_id, []).append(result)
    ordered: list[WindowSemanticResult] = []
    for window in plan.windows:
        matches = by_id.get(window.window_id) or []
        if len(matches) != 1:
            raise ConsolidationInputError(
                f"ordre/identité ambiguë pour {window.window_id} : "
                f"{len(matches)} résultat(s). "
                "Le builder exige un résultat unique par WindowPlan, "
                "jamais un listing filesystem."
            )
        ordered.append(matches[0])
    extra = set(by_id) - {window.window_id for window in plan.windows}
    if extra:
        raise ConsolidationInputError(
            f"résultats hors plan : {sorted(extra)}"
        )
    return tuple(ordered)


def _validate_result_against_plan(
    result: WindowSemanticResult,
    plan: WindowPlan,
) -> None:
    window = next(
        (item for item in plan.windows if item.window_id == result.window_id),
        None,
    )
    if window is None:
        raise ConsolidationInputError(
            f"fenêtre {result.window_id} absente du WindowPlan."
        )
    if result.window_input_hash != window.input_hash:
        raise ConsolidationInputError(
            f"{result.window_id} : window_input_hash ≠ plan courant."
        )
    validate_window_result(result, window)


def _compact_record(result: WindowSemanticResult) -> tuple[ConsolidationInputRecord, ...]:
    compacted: list[ConsolidationInputRecord] = []
    for record in result.records:
        category = record_category(record.kind)
        if category is None:
            raise ConsolidationInputError(
                f"{record.record_id} : kind inconnu {record.kind!r}."
            )
        compacted.append(
            ConsolidationInputRecord(
                record_id=record.record_id,
                window_id=result.window_id,
                kind=record.kind,
                category=category,
                value=record.value,
                source_refs=tuple(record.source_refs),
                link_record_ids=tuple(record.link_record_ids),
                metadata=tuple(record.metadata),
            )
        )
    return tuple(compacted)


def _payload_for_hash(windows: Sequence[ConsolidationInputWindow]) -> dict:
    return {
        "schema_version": CONSOLIDATION_INPUT_SCHEMA_VERSION,
        "contract": "ConsolidationInput",
        "prompt_version": CONSOLIDATION_PROMPT_VERSION,
        "transport_version": CONSOLIDATION_TRANSPORT_VERSION,
        "windows": [window.to_dict() for window in windows],
    }


def _build_from_ordered(
    *,
    transcript_id: str,
    planner_version: str,
    results: Sequence[WindowSemanticResult],
    plan: WindowPlan | None,
    safe_budget: int,
    enforce_budget: bool = True,
) -> ConsolidationInput:
    if plan is not None and len(results) != plan.window_count:
        raise WindowsIncompleteError(
            "ALL_WINDOWS_READY refusé : "
            f"{len(results)}/{plan.window_count} fenêtres prêtes."
        )
    if not results:
        raise WindowsIncompleteError(
            "ALL_WINDOWS_READY refusé : aucune fenêtre prête."
        )

    windows: list[ConsolidationInputWindow] = []
    seen_ids: set[str] = set()
    all_record_ids: set[str] = set()

    for result in results:
        if result.window_id in seen_ids:
            raise ConsolidationInputError(
                f"window_id dupliqué : {result.window_id}."
            )
        seen_ids.add(result.window_id)
        if plan is not None:
            _validate_result_against_plan(result, plan)

        leaked = forbidden_editorial_fields(result.to_dict())
        if leaked:
            raise ConsolidationInputError(
                f"fuite éditoriale dans {result.window_id} : {leaked}"
            )

        records = _compact_record(result)
        for record in records:
            if record.record_id in all_record_ids:
                raise ConsolidationInputError(
                    f"identifiant intermédiaire dupliqué : {record.record_id}."
                )
            all_record_ids.add(record.record_id)
            if not record.record_id.startswith(f"{result.window_id}:"):
                raise ConsolidationInputError(
                    f"{record.record_id} n'appartient pas à {result.window_id}."
                )

        windows.append(
            ConsolidationInputWindow(
                window_id=result.window_id,
                window_input_hash=result.window_input_hash,
                window_analysis_signature=result.window_analysis_signature,
                window_result_sha256=result.result_sha256(),
                candidates=result.candidates.to_dict(),
                voice_evidence=dict(result.voice_evidence),
                records=records,
            )
        )

    record_lookup = {
        record.record_id: record
        for window in windows
        for record in window.records
    }
    for window in windows:
        for record in window.records:
            for link in record.link_record_ids:
                if link and link not in record_lookup:
                    raise ConsolidationInputError(
                        f"{record.record_id} : lien {link} introuvable."
                    )

    hash_payload = _payload_for_hash(windows)
    _assert_no_editorial(hash_payload, location="ConsolidationInput")
    input_hash = canonical_hash(hash_payload)
    serialized = canonical_dumps(hash_payload)
    estimate = estimate_tokens(serialized, model=ESTIMATION_MODEL)
    if enforce_budget and int(estimate.tokens) > int(safe_budget):
        raise ConsolidationContextExceeded(
            "ConsolidationInput dépasse le budget sûr "
            f"({estimate.tokens} > {safe_budget}). "
            "Aucune troncature. STOP.",
            estimated_tokens=int(estimate.tokens),
            safe_input_budget=int(safe_budget),
        )

    built = ConsolidationInput(
        schema_version=CONSOLIDATION_INPUT_SCHEMA_VERSION,
        contract="ConsolidationInput",
        transcript_id=transcript_id,
        planner_version=planner_version,
        strategy=PLAN_STRATEGY,
        prompt_version=CONSOLIDATION_PROMPT_VERSION,
        transport_version=CONSOLIDATION_TRANSPORT_VERSION,
        windows=tuple(windows),
        input_hash=input_hash,
        estimated_tokens=int(estimate.tokens),
        token_estimate_method=estimate.method,
    )
    _assert_no_editorial(built.to_dict(), location="ConsolidationInput")
    return built


def build_consolidation_input(
    orchestration: WindowOrchestrationResult,
    *,
    plan: WindowPlan | None = None,
    safe_budget: int = CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
    enforce_budget: bool = True,
) -> ConsolidationInput:
    """
    Handoff 3B.7.3 : get_ready_results_in_plan_order().

    2/3 fenêtres → WindowsIncompleteError. Pas de consolidation partielle.
    """
    results = orchestration.get_ready_results_in_plan_order()
    if plan is not None:
        results = _ordered_results_from_plan(plan, results)
        if list(window.window_id for window in plan.windows) != [
            result.window_id for result in results
        ]:
            raise ConsolidationInputError(
                "l'ordre des résultats ≠ ordre WindowPlan."
            )
    planner_version = (
        plan.planner_version if plan is not None else orchestration.planner_version
    )
    return _build_from_ordered(
        transcript_id=orchestration.transcript_id,
        planner_version=planner_version,
        results=results,
        plan=plan,
        safe_budget=safe_budget,
        enforce_budget=enforce_budget,
    )


def build_consolidation_input_from_plan(
    plan: WindowPlan,
    results: Sequence[WindowSemanticResult],
    *,
    safe_budget: int = CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
    enforce_budget: bool = True,
) -> ConsolidationInput:
    """
    Restaure l'ordre WindowPlan même si `results` est mélangé.

    N'accepte pas un ordre ambigu : un résultat par window_id du plan.
    """
    if len(results) != plan.window_count:
        raise WindowsIncompleteError(
            "ALL_WINDOWS_READY refusé : "
            f"{len(results)}/{plan.window_count} fenêtres prêtes."
        )
    ordered = _ordered_results_from_plan(plan, results)
    return _build_from_ordered(
        transcript_id=plan.transcript_id,
        planner_version=plan.planner_version,
        results=ordered,
        plan=plan,
        safe_budget=safe_budget,
        enforce_budget=enforce_budget,
    )


def consolidation_input_fingerprint(payload: ConsolidationInput) -> str:
    return payload.input_hash


def estimate_consolidation_input_tokens(
    payload: ConsolidationInput,
    *,
    model: str = CONSOLIDATION_TARGET_MODEL,
) -> dict:
    text = canonical_dumps(payload.to_dict())
    estimate = estimate_tokens(text, model=model)
    return {
        "tokens": estimate.tokens,
        "method": estimate.method,
        "model": model,
        "estimated": True,
        "output_language": CONSOLIDATION_OUTPUT_LANGUAGE,
        "mark": "FIXTURE" if payload.transcript_id != "TR001-REAL" else "SCENARIO",
    }


__all__ = [
    "build_consolidation_input",
    "build_consolidation_input_from_plan",
    "consolidation_input_fingerprint",
    "estimate_consolidation_input_tokens",
]
