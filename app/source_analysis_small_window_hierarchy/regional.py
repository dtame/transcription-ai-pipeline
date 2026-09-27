"""
Regional consolidation contract — separately versioned.

Reuses consolidation-transport-v1 KEEP/MERGE/REL/REP encoding.
Does NOT reuse consolidation-1.0 GLOBAL_METADATA semantics.
Regional output is intermediate, never canonical SourceMap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from app.file_utils import content_hash
from app.source_analysis.consolidation_decoder import decode_consolidation_transport
from app.source_analysis.consolidation_input import (
    _assert_no_editorial,
    _payload_for_hash,
    build_consolidation_input_from_plan,
)
from app.source_analysis.consolidation_models import (
    CATEGORY_A_SUBSTANTIVE,
    CATEGORY_B_RELATION,
    CATEGORY_C_METADATA_EVIDENCE,
    CONSOLIDATION_INPUT_SCHEMA_VERSION,
    CONSOLIDATION_PROMPT_VERSION,
    CONSOLIDATION_RESULT_SCHEMA_VERSION,
    CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
    CONSOLIDATION_TRANSPORT_VERSION,
    ConsolidationInput,
    ConsolidationInputRecord,
    ConsolidationInputWindow,
    ConsolidationNode,
    ConsolidationProviderMetadata,
    ConsolidationSemanticResult,
    FORBIDDEN_OPS,
    record_category,
    requires_exclusive_disposition,
    union_source_refs,
)
from app.source_analysis.errors import (
    HierarchyCapacityExceeded,
    RegionalConsolidationValidationError,
    SourceMapEditorialLeakError,
)
from app.source_analysis.models import forbidden_editorial_fields
from app.source_analysis.window_models import WindowSemanticResult
from app.source_analysis_hybrid.contracts import (
    WINDOW_RECORD_ID_PATTERN,
    WindowPlan,
    canonical_dumps,
    canonical_hash,
)
from app.source_analysis_hybrid.constants import ESTIMATION_MODEL, PLAN_STRATEGY
from app.ai.estimation import estimate_tokens
from app.source_analysis_small_window_hierarchy.constants import (
    REGIONAL_ALLOWS_GLOBAL_METADATA,
    REGIONAL_CONTRACT_VERSION,
    REGIONAL_ID_WIDTH,
    REGIONAL_RECORD_INDEX_WIDTH,
    REGIONAL_REUSES_CONSOLIDATION_10_TRANSPORT,
)
from app.source_analysis_small_window_hierarchy.grouping import (
    RegionalGroup,
    _subset_plan,
)

REGIONAL_RECORD_ID_PATTERN = re.compile(
    rf"^REG\d{{{REGIONAL_ID_WIDTH},}}:R\d{{{REGIONAL_RECORD_INDEX_WIDTH}}}$"
)


def format_regional_record_id(group_id: str, record_index: int) -> str:
    if int(record_index) < 1:
        raise RegionalConsolidationValidationError(
            f"index de record régional invalide : {record_index}."
        )
    return f"{group_id}:R{int(record_index):0{REGIONAL_RECORD_INDEX_WIDTH}d}"


@dataclass(frozen=True)
class RegionalNode:
    record_id: str
    operation: str
    kind: str
    value: str
    member_ids: tuple[str, ...]
    origin_record_ids: tuple[str, ...]
    source_refs: tuple[str, ...]
    window_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "operation": self.operation,
            "kind": self.kind,
            "value": self.value,
            "member_ids": list(self.member_ids),
            "origin_record_ids": list(self.origin_record_ids),
            "source_refs": list(self.source_refs),
            "window_ids": list(self.window_ids),
            "canonical_id": None,
        }


@dataclass(frozen=True)
class RegionalSemanticResult:
    """Intermediate regional output. Not canonical SourceMap. No global metadata."""

    schema_version: str
    group_id: str
    contract_version: str
    input_hash: str
    regional_signature: str
    transport_version: str
    window_ids: tuple[str, ...]
    nodes: tuple[RegionalNode, ...]
    accounted_record_ids: tuple[str, ...]
    global_metadata: None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "group_id": self.group_id,
            "contract_version": self.contract_version,
            "input_hash": self.input_hash,
            "regional_signature": self.regional_signature,
            "transport_version": self.transport_version,
            "window_ids": list(self.window_ids),
            "nodes": [node.to_dict() for node in self.nodes],
            "accounted_record_ids": list(self.accounted_record_ids),
            "global_metadata": self.global_metadata,
            "canonical_sourcemap": False,
            "drop_supported": False,
            "allows_global_metadata": REGIONAL_ALLOWS_GLOBAL_METADATA,
            "reuses_consolidation_1_0_transport": (
                REGIONAL_REUSES_CONSOLIDATION_10_TRANSPORT
            ),
        }

    def result_sha256(self) -> str:
        return canonical_hash(self.to_dict())


def regional_contract_facts() -> dict[str, Any]:
    return {
        "version": REGIONAL_CONTRACT_VERSION,
        "reuses_consolidation_1_0_safely": False,
        "reason": (
            "consolidation-1.0 requires GLOBAL_METADATA. Regional stage "
            "must not assert final theme/intent/audience. Separate version "
            "reuses KEEP/MERGE/REL/REP transport encoding only."
        ),
        "reuses_transport_encoding": REGIONAL_REUSES_CONSOLIDATION_10_TRANSPORT,
        "allows_global_metadata": REGIONAL_ALLOWS_GLOBAL_METADATA,
        "historical_consolidation_1_0_unchanged": True,
        "output_is_canonical_sourcemap": False,
    }


def build_regional_input(
    plan: WindowPlan,
    results: Sequence[WindowSemanticResult],
    group: RegionalGroup,
    *,
    guard: int = CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
) -> ConsolidationInput:
    wanted = set(group.window_ids)
    windows = tuple(window for window in plan.windows if window.window_id in wanted)
    subset_results = tuple(
        result for result in results if result.window_id in wanted
    )
    subset = _subset_plan(plan, windows)
    built = build_consolidation_input_from_plan(
        subset, subset_results, safe_budget=guard, enforce_budget=True
    )
    return built


def _origin_window_ids(member_ids: Sequence[str]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for member in member_ids:
        window_id = member.split(":", 1)[0]
        seen.setdefault(window_id, None)
    return tuple(seen)


def validate_regional_decoded(
    decoded: ConsolidationSemanticResult,
    consolidation_input: ConsolidationInput,
    *,
    group: RegionalGroup,
    signature: str,
) -> RegionalSemanticResult:
    errors: list[str] = []
    records = consolidation_input.record_by_id()
    allowed_src = consolidation_input.allowed_source_refs()
    member_seen: dict[str, str] = {}
    regional_nodes: list[RegionalNode] = []

    leaked = forbidden_editorial_fields(decoded.to_dict())
    if leaked:
        raise SourceMapEditorialLeakError(leaked, location="regional result")

    for index, node in enumerate(decoded.nodes, start=1):
        if node.operation not in {"KEEP_RECORD", "MERGE_RECORDS"}:
            errors.append(f"{node.node_id} : opération {node.operation!r}")
        if node.operation in FORBIDDEN_OPS or "DROP" in node.operation:
            errors.append(f"{node.node_id} : DROP interdit")
        kinds: list[str] = []
        for member in node.member_ids:
            if member not in records:
                errors.append(f"{node.node_id} : membre inconnu {member}")
                continue
            if not WINDOW_RECORD_ID_PATTERN.fullmatch(member):
                errors.append(f"{node.node_id} : ID membre invalide {member}")
            if member in member_seen:
                errors.append(
                    f"disposition multiple pour {member} : "
                    f"{member_seen[member]} et {node.node_id}"
                )
            member_seen[member] = node.node_id
            kinds.append(records[member].kind)
        if kinds and len(set(kinds)) != 1:
            errors.append(f"{node.node_id} : kinds incompatibles {kinds}")
        unknown_src = [ref for ref in node.source_refs if ref not in allowed_src]
        if unknown_src:
            errors.append(f"{node.node_id} : SRC inventés {unknown_src}")
        origin_refs = []
        for member in node.member_ids:
            record = records.get(member)
            if record is not None:
                origin_refs.append(record.source_refs)
        expected_union = union_source_refs(origin_refs)
        if tuple(node.source_refs) != expected_union and origin_refs:
            # decoder already unions; tolerate order if same set
            if set(node.source_refs) != set(expected_union):
                errors.append(
                    f"{node.node_id} : SRC ≠ union déterministe des membres"
                )
        regional_nodes.append(
            RegionalNode(
                record_id=format_regional_record_id(group.group_id, index),
                operation=node.operation,
                kind=node.kind,
                value=node.value,
                member_ids=node.member_ids,
                origin_record_ids=node.member_ids,
                source_refs=tuple(node.source_refs) or expected_union,
                window_ids=_origin_window_ids(node.member_ids),
            )
        )

    for record in consolidation_input.all_records():
        if requires_exclusive_disposition(record.kind):
            if record.record_id not in member_seen:
                errors.append(f"record non comptabilisé : {record.record_id}")
        elif record.kind in CATEGORY_C_METADATA_EVIDENCE:
            if record.record_id not in member_seen:
                errors.append(
                    f"évidence métadonnée non comptabilisée : {record.record_id}"
                )

    if errors:
        raise RegionalConsolidationValidationError(" | ".join(errors))

    return RegionalSemanticResult(
        schema_version=CONSOLIDATION_RESULT_SCHEMA_VERSION,
        group_id=group.group_id,
        contract_version=REGIONAL_CONTRACT_VERSION,
        input_hash=consolidation_input.input_hash,
        regional_signature=signature,
        transport_version=CONSOLIDATION_TRANSPORT_VERSION,
        window_ids=group.window_ids,
        nodes=tuple(regional_nodes),
        accounted_record_ids=tuple(member_seen),
    )


def regional_nodes_to_input_records(
    result: RegionalSemanticResult,
) -> tuple[ConsolidationInputRecord, ...]:
    records: list[ConsolidationInputRecord] = []
    for node in result.nodes:
        category = record_category(node.kind)
        if category is None:
            raise RegionalConsolidationValidationError(
                f"{node.record_id} : kind inconnu {node.kind!r}."
            )
        records.append(
            ConsolidationInputRecord(
                record_id=node.record_id,
                window_id=result.group_id,
                kind=node.kind,
                category=category,
                value=node.value,
                source_refs=node.source_refs,
                link_record_ids=(),
                metadata=(),
            )
        )
    return tuple(records)


def build_global_input_from_regional(
    plan: WindowPlan,
    regional_results: Sequence[RegionalSemanticResult],
    *,
    guard: int = CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
    enforce_budget: bool = True,
) -> ConsolidationInput:
    """Final global input from regional semantic outputs. No full transcript."""
    windows: list[ConsolidationInputWindow] = []
    seen: set[str] = set()
    for result in regional_results:
        if result.group_id in seen:
            raise RegionalConsolidationValidationError(
                f"group_id dupliqué : {result.group_id}."
            )
        seen.add(result.group_id)
        records = regional_nodes_to_input_records(result)
        windows.append(
            ConsolidationInputWindow(
                window_id=result.group_id,
                window_input_hash=result.input_hash,
                window_analysis_signature=result.regional_signature,
                window_result_sha256=result.result_sha256(),
                candidates={},
                voice_evidence={},
                records=records,
            )
        )
    hash_payload = _payload_for_hash(windows)
    _assert_no_editorial(hash_payload, location="ConsolidationInput")
    input_hash = canonical_hash(hash_payload)
    serialized = canonical_dumps(hash_payload)
    estimate = estimate_tokens(serialized, model=ESTIMATION_MODEL)
    tokens = int(estimate.tokens)
    if enforce_budget and tokens > int(guard):
        raise HierarchyCapacityExceeded(
            "ConsolidationInput global après régional dépasse la garde "
            f"({tokens} > {guard}). Profondeur max atteinte. STOP.",
            estimated_tokens=tokens,
            safe_input_budget=int(guard),
        )
    built = ConsolidationInput(
        schema_version=CONSOLIDATION_INPUT_SCHEMA_VERSION,
        contract="ConsolidationInput",
        transcript_id=plan.transcript_id,
        planner_version=plan.planner_version,
        strategy=PLAN_STRATEGY,
        prompt_version=CONSOLIDATION_PROMPT_VERSION,
        transport_version=CONSOLIDATION_TRANSPORT_VERSION,
        windows=tuple(windows),
        input_hash=input_hash,
        estimated_tokens=tokens,
        token_estimate_method=estimate.method,
    )
    _assert_no_editorial(built.to_dict(), location="ConsolidationInput")
    return built


def flatten_global_result_to_window_members(
    global_result: ConsolidationSemanticResult,
    regional_results: Sequence[RegionalSemanticResult],
    direct_input: ConsolidationInput,
) -> ConsolidationSemanticResult:
    """
    Structural expansion REG:R → WIN:R for HybridCanonicalReconstructor.

    No semantic equivalence decision. Membership only.
    """
    origin: dict[str, tuple[str, ...]] = {}
    src_by_origin: dict[str, tuple[str, ...]] = {}
    for regional in regional_results:
        for node in regional.nodes:
            origin[node.record_id] = node.origin_record_ids
            src_by_origin[node.record_id] = node.source_refs

    def expand(ids: Sequence[str]) -> tuple[str, ...]:
        out: list[str] = []
        seen: set[str] = set()
        for item in ids:
            members = origin.get(item, (item,))
            for member in members:
                if member not in seen:
                    seen.add(member)
                    out.append(member)
        return tuple(out)

    new_nodes: list[ConsolidationNode] = []
    for node in global_result.nodes:
        members = expand(node.member_ids)
        operation = node.operation
        if operation == "KEEP_RECORD" and len(members) > 1:
            operation = "MERGE_RECORDS"
        new_nodes.append(
            replace(
                node,
                operation=operation,
                member_ids=members,
                source_refs=union_source_refs(
                    [src_by_origin.get(item, node.source_refs) for item in node.member_ids]
                    or [node.source_refs]
                ),
            )
        )
    metadata = global_result.global_metadata
    flattened_meta = replace(
        metadata,
        theme_evidence=expand(metadata.theme_evidence),
        intent_evidence=expand(metadata.intent_evidence),
        audience_evidence=expand(metadata.audience_evidence),
        voice_evidence=expand(metadata.voice_evidence),
    )
    return replace(
        global_result,
        nodes=tuple(new_nodes),
        global_metadata=flattened_meta,
        input_hash=direct_input.input_hash,
        accounted_record_ids=tuple(
            member for node in new_nodes for member in node.member_ids
        ),
    )


__all__ = [
    "REGIONAL_RECORD_ID_PATTERN",
    "RegionalNode",
    "RegionalSemanticResult",
    "build_global_input_from_regional",
    "build_regional_input",
    "flatten_global_result_to_window_members",
    "format_regional_record_id",
    "regional_contract_facts",
    "validate_regional_decoded",
]
