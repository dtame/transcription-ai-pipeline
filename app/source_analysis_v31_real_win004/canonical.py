"""Reconstruction canonique offline d'un candidat WIN004 local-lite. 0 provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.source_analysis.consolidation_models import ConsolidationNode
from app.source_analysis.errors import HybridReconstructionError
from app.source_analysis.hybrid_reconstructor import _idea_raw_local_lite
from app.source_analysis.models import IDEA_KINDS, IMPORTANCE_LEVELS, Idea
from app.source_analysis.schema import build_response_schema
from app.source_analysis.validator import ensure_valid_source_map, validate_source_map
from app.source_analysis.window_models import (
    WindowIntermediateRecord,
    WindowProviderMetadata,
)
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_local_v3.compatibility import (
    normalize_v3_transport_to_local_lite,
)
from app.source_analysis_local_v3.constants import SEMANTIC_TRANSPORT_VERSION_V3
from app.source_analysis_local_v3.decoder import decode_v31_local_lite_transport
from app.source_analysis_local_v3.resolver import resolve_v3_handles
from app.source_analysis_local_v3.result import v31_transport_to_window_result
from app.source_analysis_local_v3.schema import build_semantic_transport_v31_local_lite_schema
from app.source_analysis_v31_local_lite.compatibility import load_a21_historical_transport
from app.source_analysis_v31_real_win004.constants import (
    EXPECTED_ANALYSIS_SIGNATURE,
    MODE,
    MODEL,
    PHASE,
    PROJECT_NAME,
    PROVIDER,
    SCHEMA_VERSION,
    TRANSPORT_VERSION,
    WINDOW_ID,
)


def _member_from_record(record: WindowIntermediateRecord) -> WindowIntermediateRecord:
    return record


def _keep_node(record: WindowIntermediateRecord, index: int) -> ConsolidationNode:
    return ConsolidationNode(
        node_id=f"C{index:04d}",
        operation="KEEP_RECORD",
        kind=record.kind,
        value=record.value,
        member_ids=(record.record_id,),
        source_refs=tuple(record.source_refs),
        source_refs_are_local_union=True,
    )


def reconstruct_ideas(
    transport: Mapping[str, Any],
    window: WindowInput,
    *,
    signature: str,
) -> dict[str, Any]:
    allowed = set(window.owned_src_refs) | set(window.context_src_refs)
    decoded = decode_v31_local_lite_transport(transport, allowed_source_refs=allowed)
    resolved = resolve_v3_handles(decoded)
    result = v31_transport_to_window_result(
        resolved,
        window,
        signature=signature,
        provider_metadata=WindowProviderMetadata(
            provider=PROVIDER,
            model=MODEL,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            usage_source="canonical_offline",
            finish_reason=None,
        ),
    )
    nodes_by_id: dict[str, ConsolidationNode] = {}
    record_to_node: dict[str, str] = {}
    keep_nodes: list[tuple[ConsolidationNode, WindowIntermediateRecord]] = []
    for index, record in enumerate(result.records, start=1):
        node = _keep_node(record, index)
        nodes_by_id[node.node_id] = node
        record_to_node[record.record_id] = node.node_id
        keep_nodes.append((node, record))

    ideas: list[dict[str, Any]] = []
    errors: list[str] = []
    contamination = 0
    for node, record in keep_nodes:
        if record.kind != "IDEA":
            continue
        try:
            raw = _idea_raw_local_lite(
                node,
                (_member_from_record(record),),
                record_to_node,
                nodes_by_id,
                tuple(record.source_refs),
            )
            idea = Idea.from_dict(raw) if hasattr(Idea, "from_dict") else Idea(**raw)
            serialized = idea.to_dict()
            if idea.kind != "":
                errors.append(f"{record.record_id}: kind={idea.kind!r}")
            if idea.importance not in IMPORTANCE_LEVELS:
                errors.append(f"{record.record_id}: importance={idea.importance!r}")
            if idea.kind == idea.importance and idea.kind != "":
                contamination += 1
            if idea.kind in IDEA_KINDS and idea.kind == idea.importance:
                contamination += 1
            if serialized.get("kind") != "":
                errors.append(f"{record.record_id}: serialized kind={serialized.get('kind')!r}")
            if idea.importance in IDEA_KINDS:
                contamination += 1
                errors.append(f"{record.record_id}: importance leaked into kind vocabulary")
            ideas.append(
                {
                    "record_id": record.record_id,
                    "handle": record.handle if hasattr(record, "handle") else None,
                    "kind": idea.kind,
                    "importance": idea.importance,
                    "serialized_kind": serialized.get("kind"),
                    "kind_key_present": "kind" in serialized,
                }
            )
        except (HybridReconstructionError, TypeError, ValueError) as exc:
            errors.append(f"{record.record_id}: {exc}")
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "transport": TRANSPORT_VERSION,
        "idea_count": len(ideas),
        "ideas": ideas,
        "all_kinds_empty": bool(ideas) and all(item["kind"] == "" for item in ideas),
        "all_importances_valid": bool(ideas)
        and all(item["importance"] in IMPORTANCE_LEVELS for item in ideas),
        "serialized_kind_empty": bool(ideas)
        and all(item["serialized_kind"] == "" for item in ideas),
        "importance_to_kind_contamination": contamination,
        "errors": errors,
        "idea_validation": "PASS" if ideas and not errors else "FAIL",
        "schema_py_used": False,
        "request_schema_is_local_lite": (
            build_semantic_transport_v31_local_lite_schema() != build_response_schema()
        ),
    }


def reconstruct_mixed_with_a21(
    win004_transport: Mapping[str, Any],
    window: WindowInput,
    *,
    signature: str,
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    local = reconstruct_ideas(win004_transport, window, signature=signature)
    historical = load_a21_historical_transport(project_name, sortie_dir=sortie_dir)
    a21_ok = False
    a21_path = None
    normalized_ok = False
    invented = None
    old_rejected = False
    if historical is not None:
        a21_path = historical["path"]
        payload = historical["payload"]
        try:
            normalize_v3_transport_to_local_lite(
                payload, source_transport_version=SEMANTIC_TRANSPORT_VERSION_V3
            )
            a21_ok = True
        except Exception as exc:  # noqa: BLE001 — forensic
            a21_ok = False
            invented = str(exc)
        try:
            normalized, provenance = normalize_v3_transport_to_local_lite(
                payload, source_transport_version=SEMANTIC_TRANSPORT_VERSION_V3
            )
            decode_v31_local_lite_transport(
                normalized,
                allowed_source_refs=set(normalized_src_refs(normalized)),
            )
            normalized_ok = True
            invented = provenance.get("invented_semantics")
        except Exception as exc:  # noqa: BLE001
            normalized_ok = False
            invented = str(exc)
        try:
            decode_v31_local_lite_transport(
                payload, allowed_source_refs=set(normalized_src_refs(payload))
            )
        except Exception:
            old_rejected = True
    compatible = (
        local["idea_validation"] == "PASS"
        and local["all_kinds_empty"]
        and local["importance_to_kind_contamination"] == 0
        and (historical is None or (a21_ok and normalized_ok and old_rejected))
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "win004": local,
        "a21_historical_present": historical is not None,
        "a21_path": a21_path,
        "a21_readable": a21_ok,
        "a21_normalized_to_local_lite": normalized_ok,
        "a21_old_v3_rejected_under_local_lite": old_rejected,
        "normalization_invented_semantics": invented,
        "common_strategy": (
            "historical WIN001 V3 remains readable; normalize drops IDEA "
            "subtype; WIN004 native local-lite reconstructs kind=''. "
            "No real consolidation."
        ),
        "schema_py_used": False,
        "mixed_compatibility": "PASS" if compatible else "FAIL",
        "expected_a21_signature_untouched": EXPECTED_ANALYSIS_SIGNATURE,
    }


def normalized_src_refs(payload: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for item in payload.get("records") or []:
        if not isinstance(item, dict):
            continue
        for ref in item.get("s") or []:
            if isinstance(ref, str) and ref.strip():
                refs.append(ref.strip())
    return refs


def attempt_source_map_validation(
    source_map,
    transcript: TranscriptInput,
) -> dict[str, Any]:
    errors = []
    ensure_ok = False
    try:
        errors = list(validate_source_map(source_map, transcript))
    except Exception as exc:  # noqa: BLE001
        errors = [str(exc)]
    try:
        ensure_valid_source_map(source_map, transcript)
        ensure_ok = True
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))
    return {
        "validate_source_map": "PASS" if errors == [] else "FAIL",
        "ensure_valid_source_map": "PASS" if ensure_ok else "FAIL",
        "errors": errors,
        "schema_py_used": False,
    }


def refresh_canonical_from_forensics(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    """Rejoue la reconstruction sur la réponse déjà persistée. 0 réseau."""
    import json

    from app.ai.structured import parse_structured_output
    from app.source_analysis_local_v3.schema import (
        build_semantic_transport_v31_local_lite_schema,
    )
    from app.source_analysis_v31_real_win004.paths import canary_root
    from app.source_analysis_v31_real_win004.window import load_candidate_win004

    bundle = load_candidate_win004(project_name, sortie_dir=sortie_dir)
    window = bundle["window"]
    signature = EXPECTED_ANALYSIS_SIGNATURE
    raw_path = (
        canary_root(project_name, sortie_dir=sortie_dir)
        / "provider_forensics"
        / WINDOW_ID
        / signature
        / "provider_raw_response.bin"
    )
    raw = json.loads(raw_path.read_bytes().decode("utf-8"))
    text = ""
    for block in raw.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            text += str(block.get("text") or "")
    transport = parse_structured_output(
        text, build_semantic_transport_v31_local_lite_schema()
    )
    return reconstruct_mixed_with_a21(
        transport,
        window,
        signature=signature,
        project_name=project_name,
        sortie_dir=sortie_dir,
    )


__all__ = [
    "attempt_source_map_validation",
    "reconstruct_ideas",
    "reconstruct_mixed_with_a21",
    "refresh_canonical_from_forensics",
]
