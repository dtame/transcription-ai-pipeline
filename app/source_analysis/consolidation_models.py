"""
Contrats déterministes de consolidation — 3B.7.4.

ConsolidationInput n'est PAS le transcript.
ConsolidationSemanticResult n'est PAS le SourceMap canonique.
Les IDs C0001 sont locaux, assignés après decode, jamais par le provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from app.source_analysis_hybrid.constants import (
    CONSOLIDATION_OPERATIONS,
    CONSOLIDATION_PROMPT_VERSION,
    CONSOLIDATION_TRANSPORT_VERSION,
    FORBIDDEN_CONSOLIDATION_OPERATIONS,
    PLAN_STRATEGY,
)

CONSOLIDATION_RESULT_SCHEMA_VERSION = "1.0"
CONSOLIDATION_INPUT_SCHEMA_VERSION = "1.0"
STAGE_CONSOLIDATION = "source_analysis_consolidation"
CONSOLIDATION_MAX_OUTPUT_TOKENS = 16000
CONSOLIDATION_CONNECT_TIMEOUT_SECONDS = 30.0
CONSOLIDATION_READ_TIMEOUT_SECONDS = 1800.0
CONSOLIDATION_MAX_ATTEMPTS = 1
CONSOLIDATION_RETRY = False
CONSOLIDATION_FALLBACK = None
CONSOLIDATION_TARGET_PROVIDER = "anthropic"
CONSOLIDATION_TARGET_MODEL = "claude-sonnet-5"
CONSOLIDATION_OUTPUT_LANGUAGE = "en"
CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS = 80000
CONSOLIDATION_NODE_ID_WIDTH = 4
RECORD_ORDER_RULE = "TRANSPORT_ORDER"
NODE_ID_PREFIX = "C"

# A — candidats substantifs canoniques : KEEP ou MERGE exclusif obligatoire.
CATEGORY_A_SUBSTANTIVE = frozenset(
    {
        "TOPIC",
        "IDEA",
        "EXAMPLE",
        "REFERENCE",
        "UNCERTAINTY",
        "REPETITION",
    }
)

# B — relations / évidence relationnelle : KEEP par défaut, MERGE same-kind.
CATEGORY_B_RELATION = frozenset({"RELATION"})

# C — évidence de métadonnées globales : comptabilisées via GLOBAL_METADATA
#     ou KEEP. Pas des éléments SourceMap autonomes en v1.
CATEGORY_C_METADATA_EVIDENCE = frozenset(
    {
        "VOICE",
        "INTENT_KIND",
        "AUDIENCE_KIND",
    }
)

RECORD_CATEGORIES = {
    "A": CATEGORY_A_SUBSTANTIVE,
    "B": CATEGORY_B_RELATION,
    "C": CATEGORY_C_METADATA_EVIDENCE,
}

MERGE_COMPATIBLE_KINDS = frozenset(
    CATEGORY_A_SUBSTANTIVE | CATEGORY_B_RELATION | CATEGORY_C_METADATA_EVIDENCE
)

TRANSPORT_OP_KEEP = "KEEP"
TRANSPORT_OP_MERGE = "MERGE"
TRANSPORT_OP_REL = "REL"
TRANSPORT_OP_REP = "REP"

TRANSPORT_OP_TO_CANONICAL = {
    TRANSPORT_OP_KEEP: "KEEP_RECORD",
    TRANSPORT_OP_MERGE: "MERGE_RECORDS",
    TRANSPORT_OP_REL: "RELATION",
    TRANSPORT_OP_REP: "REPETITION",
}

CANONICAL_OPS = frozenset(CONSOLIDATION_OPERATIONS)
FORBIDDEN_OPS = frozenset(FORBIDDEN_CONSOLIDATION_OPERATIONS)

GLOBAL_METADATA_FIELDS = (
    "main_theme",
    "author_intent",
    "target_audience",
    "author_voice_profile",
)


def record_category(kind: str) -> str | None:
    if kind in CATEGORY_A_SUBSTANTIVE:
        return "A"
    if kind in CATEGORY_B_RELATION:
        return "B"
    if kind in CATEGORY_C_METADATA_EVIDENCE:
        return "C"
    return None


def requires_exclusive_disposition(kind: str) -> bool:
    """TOPIC/IDEA/EXAMPLE/REFERENCE/UNCERTAINTY/REPETITION/RELATION."""
    return kind in CATEGORY_A_SUBSTANTIVE or kind in CATEGORY_B_RELATION


def format_consolidation_node_id(index: int) -> str:
    if int(index) < 1:
        raise ValueError(f"index de nœud de consolidation invalide : {index}.")
    return f"{NODE_ID_PREFIX}{int(index):0{CONSOLIDATION_NODE_ID_WIDTH}d}"


@dataclass(frozen=True)
class ConsolidationInputRecord:
    """Record intermédiaire compact — IDs WIN:R, vrais SRC, pas de texte SRC."""

    record_id: str
    window_id: str
    kind: str
    category: str
    value: str
    source_refs: tuple[str, ...]
    link_record_ids: tuple[str, ...]
    metadata: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "window_id": self.window_id,
            "kind": self.kind,
            "category": self.category,
            "value": self.value,
            "source_refs": list(self.source_refs),
            "link_record_ids": list(self.link_record_ids),
            "metadata": list(self.metadata),
        }


@dataclass(frozen=True)
class ConsolidationInputWindow:
    """Identité + records d'une fenêtre, ordre WindowPlan."""

    window_id: str
    window_input_hash: str
    window_analysis_signature: str
    window_result_sha256: str
    candidates: Mapping[str, Any]
    voice_evidence: Mapping[str, Any]
    records: tuple[ConsolidationInputRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "window_input_hash": self.window_input_hash,
            "window_analysis_signature": self.window_analysis_signature,
            "window_result_sha256": self.window_result_sha256,
            "candidates": dict(self.candidates),
            "voice_evidence": dict(self.voice_evidence),
            "records": [record.to_dict() for record in self.records],
        }


@dataclass(frozen=True)
class ConsolidationInput:
    """
    Contrat compact des analyses fenêtre validées.

    Pas de transcript. Pas de timestamps. Pas d'UUID.
    """

    schema_version: str
    contract: str
    transcript_id: str
    planner_version: str
    strategy: str
    prompt_version: str
    transport_version: str
    windows: tuple[ConsolidationInputWindow, ...]
    input_hash: str
    estimated_tokens: int
    token_estimate_method: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "contract": self.contract,
            "transcript_id": self.transcript_id,
            "planner_version": self.planner_version,
            "strategy": self.strategy,
            "prompt_version": self.prompt_version,
            "transport_version": self.transport_version,
            "window_count": len(self.windows),
            "windows": [window.to_dict() for window in self.windows],
            "input_hash": self.input_hash,
            "estimated_tokens": self.estimated_tokens,
            "token_estimate_method": self.token_estimate_method,
            "contains_full_transcript": False,
            "contains_original_src_text": False,
        }

    def all_records(self) -> tuple[ConsolidationInputRecord, ...]:
        return tuple(
            record for window in self.windows for record in window.records
        )

    def record_by_id(self) -> dict[str, ConsolidationInputRecord]:
        return {record.record_id: record for record in self.all_records()}

    def allowed_source_refs(self) -> frozenset[str]:
        refs: set[str] = set()
        for record in self.all_records():
            refs.update(record.source_refs)
        return frozenset(refs)

    def window_result_hashes_in_order(self) -> tuple[str, ...]:
        return tuple(window.window_result_sha256 for window in self.windows)

    def window_signatures_in_order(self) -> tuple[str, ...]:
        return tuple(window.window_analysis_signature for window in self.windows)


@dataclass(frozen=True)
class ConsolidationNode:
    """Nœud local Cxxxx — KEEP ou MERGE. Pas un ID canonique TOP/IDEA."""

    node_id: str
    operation: str
    kind: str
    value: str
    member_ids: tuple[str, ...]
    source_refs: tuple[str, ...]
    source_refs_are_local_union: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "operation": self.operation,
            "kind": self.kind,
            "value": self.value,
            "member_ids": list(self.member_ids),
            "source_refs": list(self.source_refs),
            "source_refs_are_local_union": self.source_refs_are_local_union,
            "canonical_id": None,
        }


@dataclass(frozen=True)
class ConsolidationRelation:
    relation_type: str
    left_ref: str
    right_ref: str
    left_node_id: str
    right_node_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_type": self.relation_type,
            "left_ref": self.left_ref,
            "right_ref": self.right_ref,
            "left_node_id": self.left_node_id,
            "right_node_id": self.right_node_id,
        }


@dataclass(frozen=True)
class ConsolidationRepetition:
    character: str
    member_ids: tuple[str, ...]
    node_ids: tuple[str, ...]
    value: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "character": self.character,
            "member_ids": list(self.member_ids),
            "node_ids": list(self.node_ids),
            "value": self.value,
        }


@dataclass(frozen=True)
class ConsolidationGlobalMetadata:
    main_theme: str
    author_intent: str
    target_audience: str
    author_voice_profile: str
    theme_evidence: tuple[str, ...]
    intent_evidence: tuple[str, ...]
    audience_evidence: tuple[str, ...]
    voice_evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "main_theme": self.main_theme,
            "author_intent": self.author_intent,
            "target_audience": self.target_audience,
            "author_voice_profile": self.author_voice_profile,
            "theme_evidence": list(self.theme_evidence),
            "intent_evidence": list(self.intent_evidence),
            "audience_evidence": list(self.audience_evidence),
            "voice_evidence": list(self.voice_evidence),
        }


@dataclass(frozen=True)
class ConsolidationProviderMetadata:
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    usage_source: str
    finish_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "usage_source": self.usage_source,
            "finish_reason": self.finish_reason,
        }


@dataclass(frozen=True)
class ConsolidationSemanticResult:
    """Décisions sémantiques validées — PAS un SourceMap."""

    schema_version: str
    input_hash: str
    consolidation_signature: str
    transport_version: str
    prompt_version: str
    global_metadata: ConsolidationGlobalMetadata
    nodes: tuple[ConsolidationNode, ...]
    relations: tuple[ConsolidationRelation, ...]
    repetitions: tuple[ConsolidationRepetition, ...]
    provider_metadata: ConsolidationProviderMetadata
    accounted_record_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "input_hash": self.input_hash,
            "consolidation_signature": self.consolidation_signature,
            "transport_version": self.transport_version,
            "prompt_version": self.prompt_version,
            "global_metadata": self.global_metadata.to_dict(),
            "nodes": [node.to_dict() for node in self.nodes],
            "relations": [item.to_dict() for item in self.relations],
            "repetitions": [item.to_dict() for item in self.repetitions],
            "accounted_record_ids": list(self.accounted_record_ids),
            "provider_metadata": self.provider_metadata.to_dict(),
            "canonical_sourcemap": False,
            "record_order": RECORD_ORDER_RULE,
            "drop_supported": False,
        }

    def result_sha256(self) -> str:
        from app.source_analysis_hybrid.contracts import canonical_hash

        return canonical_hash(self.to_dict())


def union_source_refs(groups: Sequence[Sequence[str]]) -> tuple[str, ...]:
    """Union déterministe : ordre de première apparition, sans range numérique."""
    seen: set[str] = set()
    ordered: list[str] = []
    for group in groups:
        for ref in group:
            if ref not in seen:
                seen.add(ref)
                ordered.append(ref)
    return tuple(ordered)


__all__ = [
    "CANONICAL_OPS",
    "CATEGORY_A_SUBSTANTIVE",
    "CATEGORY_B_RELATION",
    "CATEGORY_C_METADATA_EVIDENCE",
    "CONSOLIDATION_CONNECT_TIMEOUT_SECONDS",
    "CONSOLIDATION_FALLBACK",
    "CONSOLIDATION_INPUT_SCHEMA_VERSION",
    "CONSOLIDATION_MAX_ATTEMPTS",
    "CONSOLIDATION_MAX_OUTPUT_TOKENS",
    "CONSOLIDATION_OPERATIONS",
    "CONSOLIDATION_OUTPUT_LANGUAGE",
    "CONSOLIDATION_PROMPT_VERSION",
    "CONSOLIDATION_READ_TIMEOUT_SECONDS",
    "CONSOLIDATION_RESULT_SCHEMA_VERSION",
    "CONSOLIDATION_RETRY",
    "CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS",
    "CONSOLIDATION_TARGET_MODEL",
    "CONSOLIDATION_TARGET_PROVIDER",
    "CONSOLIDATION_TRANSPORT_VERSION",
    "ConsolidationGlobalMetadata",
    "ConsolidationInput",
    "ConsolidationInputRecord",
    "ConsolidationInputWindow",
    "ConsolidationNode",
    "ConsolidationProviderMetadata",
    "ConsolidationRelation",
    "ConsolidationRepetition",
    "ConsolidationSemanticResult",
    "FORBIDDEN_OPS",
    "GLOBAL_METADATA_FIELDS",
    "MERGE_COMPATIBLE_KINDS",
    "PLAN_STRATEGY",
    "RECORD_CATEGORIES",
    "STAGE_CONSOLIDATION",
    "TRANSPORT_OP_KEEP",
    "TRANSPORT_OP_MERGE",
    "TRANSPORT_OP_REL",
    "TRANSPORT_OP_REP",
    "TRANSPORT_OP_TO_CANONICAL",
    "format_consolidation_node_id",
    "record_category",
    "requires_exclusive_disposition",
    "union_source_refs",
]
