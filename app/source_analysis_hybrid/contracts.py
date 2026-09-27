"""
Contrats déterministes d'entrée hybride — 3B.7.1.

WindowInput / WindowPlan / WindowInputSignature.
Squelettes structurels pour le futur WindowAnalyzer et le consolidateur.

Aucun résultat sémantique faux. Aucun appel provider.
WIN001 est une identité de plan, pas une signature de cache complète.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.file_utils import content_hash
from app.source_analysis.errors import SourceAnalysisWindowPlanError
from app.source_analysis.transcript_input import SourceSegment
from app.source_analysis_hybrid.constants import (
    CONSOLIDATION_OPERATIONS,
    CONSOLIDATION_TRANSPORT_VERSION,
    FORBIDDEN_CONSOLIDATION_OPERATIONS,
    OWNERSHIP_CONTEXT_ONLY,
    OWNERSHIP_OWNED,
    PLAN_STRATEGY,
    PLANNER_VERSION,
    WINDOW_ID_WIDTH,
    WINDOW_PROMPT_VERSION,
    WINDOW_RECORD_INDEX_WIDTH,
    WINDOW_TRANSPORT_VERSION,
)

WINDOW_ID_PATTERN = re.compile(rf"^WIN\d{{{WINDOW_ID_WIDTH},}}$")
WINDOW_RECORD_ID_PATTERN = re.compile(
    rf"^WIN\d{{{WINDOW_ID_WIDTH},}}:R\d{{{WINDOW_RECORD_INDEX_WIDTH}}}$"
)


def format_window_id(index: int) -> str:
    if int(index) < 1:
        raise SourceAnalysisWindowPlanError(f"index de fenêtre invalide : {index}.")
    return f"WIN{int(index):0{WINDOW_ID_WIDTH}d}"


def format_intermediate_record_id(window_id: str, record_index: int) -> str:
    """Identité intermédiaire WINxxx:Rxxxx — pas un id canonique final."""
    if not WINDOW_ID_PATTERN.fullmatch(window_id):
        raise SourceAnalysisWindowPlanError(f"window_id invalide : {window_id!r}.")
    if int(record_index) < 1:
        raise SourceAnalysisWindowPlanError(
            f"index de record intermédiaire invalide : {record_index}."
        )
    return f"{window_id}:R{int(record_index):0{WINDOW_RECORD_INDEX_WIDTH}d}"


def src_ids_hash(src_ids: Sequence[str]) -> str:
    return content_hash("\n".join(src_ids))


def segments_content_hash(segments: Sequence[SourceSegment]) -> str:
    return content_hash(
        "\n".join(f"{segment.src_id}\t{segment.text}" for segment in segments)
    )


def window_input_hash(
    *,
    planner_version: str,
    window_id: str,
    owned: Sequence[str],
    context: Sequence[str],
    owned_content_sha256: str,
    context_content_sha256: str,
) -> str:
    return content_hash(
        "\n".join(
            [
                planner_version,
                window_id,
                "owned:" + ",".join(owned),
                "context:" + ",".join(context),
                "owned_content:" + owned_content_sha256,
                "context_content:" + context_content_sha256,
            ]
        )
    )


def canonical_dumps(payload: Mapping[str, Any]) -> str:
    """Sérialisation canonique : UTF-8, ordre d'insertion, pas de timestamp."""
    return json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"


def canonical_hash(payload: Mapping[str, Any]) -> str:
    return content_hash(canonical_dumps(payload))


@dataclass(frozen=True)
class WindowInputSignature:
    """
    Identité déterministe d'une entrée de fenêtre.

    Ce n'est PAS la future WindowAnalysisSignature (prompt SHA, provider,
    modèle, température, schéma de transport). WIN001 seul n'est pas une
    signature de cache.
    """

    clean_transcript_sha256: str
    planner_version: str
    window_id: str
    window_input_hash: str
    owned_src_ids_sha256: str
    owned_content_sha256: str
    context_src_ids_sha256: str
    context_content_sha256: str

    def to_dict(self) -> dict[str, str]:
        return {
            "clean_transcript_sha256": self.clean_transcript_sha256,
            "planner_version": self.planner_version,
            "window_id": self.window_id,
            "window_input_hash": self.window_input_hash,
            "owned_src_ids_sha256": self.owned_src_ids_sha256,
            "owned_content_sha256": self.owned_content_sha256,
            "context_src_ids_sha256": self.context_src_ids_sha256,
            "context_content_sha256": self.context_content_sha256,
        }

    def digest(self) -> str:
        return canonical_hash(self.to_dict())


@dataclass(frozen=True)
class WindowInput:
    """
    Contrat immuable d'une fenêtre planifiée.

    first/last_owned_src_ref sont descriptifs. Le contenu réel est
    owned_src_refs — jamais range(first, last).
    """

    window_id: str
    transcript_id: str
    planner_version: str
    owned_src_refs: tuple[str, ...]
    context_src_refs: tuple[str, ...]
    first_owned_src_ref: str
    last_owned_src_ref: str
    owned_src_count: int
    estimated_input_tokens: int
    owned_src_ids_sha256: str
    owned_content_sha256: str
    context_src_ids_sha256: str
    context_content_sha256: str
    input_hash: str
    source_order_start: int
    source_order_stop: int
    word_count: int
    content_tokens: int
    planner_estimate_tokens: int

    @property
    def context_src_count(self) -> int:
        return len(self.context_src_refs)

    def input_signature(self, *, clean_transcript_sha256: str) -> WindowInputSignature:
        return WindowInputSignature(
            clean_transcript_sha256=clean_transcript_sha256,
            planner_version=self.planner_version,
            window_id=self.window_id,
            window_input_hash=self.input_hash,
            owned_src_ids_sha256=self.owned_src_ids_sha256,
            owned_content_sha256=self.owned_content_sha256,
            context_src_ids_sha256=self.context_src_ids_sha256,
            context_content_sha256=self.context_content_sha256,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "transcript_id": self.transcript_id,
            "planner_version": self.planner_version,
            "owned_src_refs": list(self.owned_src_refs),
            "context_src_refs": list(self.context_src_refs),
            "first_owned_src_ref": self.first_owned_src_ref,
            "last_owned_src_ref": self.last_owned_src_ref,
            "owned_src_count": self.owned_src_count,
            "context_src_count": self.context_src_count,
            "estimated_input_tokens": self.estimated_input_tokens,
            "owned_src_ids_sha256": self.owned_src_ids_sha256,
            "owned_content_sha256": self.owned_content_sha256,
            "context_src_ids_sha256": self.context_src_ids_sha256,
            "context_content_sha256": self.context_content_sha256,
            "input_hash": self.input_hash,
            "source_order_start": self.source_order_start,
            "source_order_stop": self.source_order_stop,
            "word_count": self.word_count,
            "content_tokens": self.content_tokens,
            "planner_estimate_tokens": self.planner_estimate_tokens,
        }


@dataclass(frozen=True)
class WindowPlan:
    strategy: str
    planner_version: str
    transcript_id: str
    transcript_sha256: str
    target_input_tokens: int
    hard_max_input_tokens: int
    overlap_policy: str
    prompt_overhead_tokens: int
    windows: tuple[WindowInput, ...]
    owned_src_count: int
    context_src_count: int
    window_count: int
    estimated_input_tokens_min: int
    estimated_input_tokens_max: int
    estimated_input_tokens_mean: float
    estimated_input_tokens_median: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "planner_version": self.planner_version,
            "transcript_id": self.transcript_id,
            "transcript_sha256": self.transcript_sha256,
            "target_input_tokens": self.target_input_tokens,
            "hard_max_input_tokens": self.hard_max_input_tokens,
            "overlap_policy": self.overlap_policy,
            "prompt_overhead_tokens": self.prompt_overhead_tokens,
            "window_count": self.window_count,
            "owned_src_count": self.owned_src_count,
            "context_src_count": self.context_src_count,
            "estimated_input_tokens_min": self.estimated_input_tokens_min,
            "estimated_input_tokens_max": self.estimated_input_tokens_max,
            "estimated_input_tokens_mean": self.estimated_input_tokens_mean,
            "estimated_input_tokens_median": self.estimated_input_tokens_median,
            "windows": [window.to_dict() for window in self.windows],
        }

    def canonical_text(self) -> str:
        return canonical_dumps(self.to_dict())

    def plan_sha256(self) -> str:
        return content_hash(self.canonical_text())


@dataclass(frozen=True)
class WindowAnalysisPromptContract:
    """Contrat/version du futur prompt fenêtre — pas d'appel, pas de texte envoyé."""

    version: str = WINDOW_PROMPT_VERSION
    transport_version: str = WINDOW_TRANSPORT_VERSION
    distinct_from_prompt_1_3: bool = True
    implemented: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "transport_version": self.transport_version,
            "distinct_from_prompt_1_3": self.distinct_from_prompt_1_3,
            "implemented": self.implemented,
        }


@dataclass(frozen=True)
class WindowResultSkeleton:
    """Squelette structurel — aucun parsing provider, aucun résultat sémantique."""

    window_id: str
    record_id_form: str = "WIN001:R0001"
    transport_version: str = WINDOW_TRANSPORT_VERSION
    implemented: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "record_id_form": self.record_id_form,
            "transport_version": self.transport_version,
            "implemented": self.implemented,
        }


@dataclass(frozen=True)
class ConsolidationContractSkeleton:
    """Constantes du transport de consolidation — pas de consolidateur."""

    version: str = CONSOLIDATION_TRANSPORT_VERSION
    operations: tuple[str, ...] = CONSOLIDATION_OPERATIONS
    drop_records_v1: bool = False
    implemented: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "operations": list(self.operations),
            "forbidden_operations": list(FORBIDDEN_CONSOLIDATION_OPERATIONS),
            "drop_records_v1": self.drop_records_v1,
            "implemented": self.implemented,
        }


def assert_allowed_consolidation_operation(operation: str) -> str:
    if operation in FORBIDDEN_CONSOLIDATION_OPERATIONS:
        raise SourceAnalysisWindowPlanError(
            f"opération de consolidation interdite en v1 : {operation}."
        )
    if operation not in CONSOLIDATION_OPERATIONS:
        raise SourceAnalysisWindowPlanError(
            f"opération de consolidation inconnue : {operation}."
        )
    return operation


def empty_context_refs() -> tuple[str, ...]:
    return ()


def default_plan_strategy() -> str:
    return PLAN_STRATEGY


def default_planner_version() -> str:
    return PLANNER_VERSION


def ownership_labels() -> tuple[str, str]:
    return (OWNERSHIP_OWNED, OWNERSHIP_CONTEXT_ONLY)
