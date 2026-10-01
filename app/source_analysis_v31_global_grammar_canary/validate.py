"""Interprétation canary : decoder + validator A.34 + handles + dispositions."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.models import RELATION_KINDS
from app.source_analysis_v31_global_grammar_canary.decoder import decode_global_transport
from app.source_analysis_v31_global_grammar_canary.dispositions import audit_dispositions
from app.source_analysis_v31_global_grammar_canary.fixture import (
    SyntheticConsolidationFixture,
    all_records,
)
from app.source_analysis_v31_global_grammar_canary.handles import inspect_global_handles
from app.source_analysis_v31_global_grammar_canary.reconstruct import (
    reconstruct_source_map,
    replay_reconstruction,
    source_map_public_view,
)
from app.source_analysis_v31_global_grammar_canary.semantic import review_semantic_fixture
from app.source_analysis_v31_global_preflight.validator import validate_global_transport


def audit_traceability(
    transport: Mapping[str, Any] | None,
    fixture: SyntheticConsolidationFixture,
) -> dict[str, Any]:
    errors: list[str] = []
    unknown_src: list[str] = []
    missing: list[str] = []
    if not isinstance(transport, Mapping):
        return {"ok": False, "status": "FAIL", "errors": ["transport missing"]}
    allowed = set(fixture.allowed_source_refs)
    for index, node in enumerate(transport.get("n") or []):
        if not isinstance(node, dict):
            continue
        kind = str(node.get("k") or "")
        refs = [str(item) for item in (node.get("s") or [])]
        if kind in {"TOPIC", "IDEA", "EXAMPLE", "REFERENCE", "UNCERTAINTY", "REPETITION"}:
            if not refs:
                missing.append(f"n[{index}] {kind}")
            for ref in refs:
                if ref not in allowed:
                    unknown_src.append(ref)
    ok = not errors and not unknown_src and not missing
    return {
        "ok": ok,
        "status": "PASS" if ok else "FAIL",
        "unknown_synthetic_source_refs": unknown_src,
        "missing_source_evidence": missing,
        "errors": errors,
    }


def audit_relations_policy_c(
    transport: Mapping[str, Any] | None,
    fixture: SyntheticConsolidationFixture,
) -> dict[str, Any]:
    """Local relations are hints. Global relations must be source-grounded."""
    if not isinstance(transport, Mapping):
        return {"ok": False, "status": "FAIL", "errors": ["transport missing"]}
    global_rels = [item for item in (transport.get("r") or []) if isinstance(item, dict)]
    local_hints = [
        item for item in all_records() if item.get("k") == "RELATION"
    ]
    local_pairs = {
        (str(item.get("v") or ""), tuple(item.get("l") or []))
        for item in local_hints
    }
    mechanical_copies = 0
    ungrounded = []
    invalid_type = []
    for rel in global_rels:
        rel_type = str(rel.get("t") or "")
        if rel_type not in RELATION_KINDS:
            invalid_type.append(rel_type)
        refs = [str(item) for item in (rel.get("s") or [])]
        if not refs:
            ungrounded.append(rel)
        pair = (rel_type, (str(rel.get("a") or ""), str(rel.get("b") or "")))
        # Local hints use input ids, not global handles — cannot be a 1:1 copy.
        if pair in local_pairs:
            mechanical_copies += 1
    ok = (
        bool(global_rels)
        and not ungrounded
        and not invalid_type
        and mechanical_copies == 0
    )
    return {
        "ok": ok,
        "status": "PASS" if ok else "FAIL",
        "global_relation_count": len(global_rels),
        "local_hint_count": len(local_hints),
        "mechanical_copies": mechanical_copies,
        "ungrounded": len(ungrounded),
        "invalid_type": invalid_type,
        "policy": "C",
        "local_relations_authoritative": False,
    }


def interpret_canary_response(
    parsed: dict[str, Any] | None,
    *,
    fixture: SyntheticConsolidationFixture,
    raw_text: str | None = None,
    signature: str = "",
) -> dict[str, Any]:
    decoded = decode_global_transport(parsed, raw_text=raw_text)
    transport = decoded.get("transport")
    structured = decoded.get("structured_parse") or "FAIL"
    decoder_status = decoded.get("decoder") or "FAIL"
    handles = inspect_global_handles(transport)
    validator = (
        validate_global_transport(
            transport,
            idea_input_ids=list(fixture.idea_input_ids),
            allowed_input_ids=set(fixture.allowed_input_ids),
            allowed_source_refs=set(fixture.allowed_source_refs),
        )
        if isinstance(transport, dict)
        else {"ok": False, "errors": ["transport missing"], "idea_disposition_coverage": 0.0}
    )
    dispositions = audit_dispositions(transport, fixture)
    traceability = audit_traceability(transport, fixture)
    relations = audit_relations_policy_c(transport, fixture)
    no_drop = {
        "ok": int(dispositions.get("silent_drop_count") or 0) == 0,
        "status": (
            "PASS" if int(dispositions.get("silent_drop_count") or 0) == 0 else "FAIL"
        ),
        "silent_drops": dispositions.get("silent_drops") or [],
    }
    reconstruction = None
    replay = None
    semantic = review_semantic_fixture(transport, fixture)
    if isinstance(transport, dict):
        reconstruction = reconstruct_source_map(
            transport, fixture.transcript, signature=signature
        )
        replay = replay_reconstruction(
            transport, fixture.transcript, signature=signature
        )
    gm = (transport or {}).get("gm") if isinstance(transport, dict) else {}
    return {
        "structured_parse": structured,
        "decoder": decoder_status,
        "inventory": decoded.get("inventory"),
        "handles": handles,
        "handle_validation": handles.get("handle_validation"),
        "global_validator": "PASS" if validator.get("ok") else "FAIL",
        "validator": validator,
        "dispositions": dispositions,
        "idea_disposition_coverage": dispositions.get("idea_disposition_coverage"),
        "silent_drops": dispositions.get("silent_drop_count"),
        "no_drop_validator": no_drop.get("status"),
        "traceability": traceability.get("status"),
        "traceability_audit": traceability,
        "relation_validator": relations.get("status"),
        "relation_audit": relations,
        "canonical_reconstruction": (
            "PASS" if reconstruction and reconstruction.get("ok") else "FAIL"
        ),
        "canonical_validation": (
            reconstruction.get("validate_source_map") if reconstruction else "FAIL"
        ),
        "deterministic_replay": replay.get("status") if replay else "FAIL",
        "reconstruction": (
            source_map_public_view(reconstruction) if reconstruction else None
        ),
        "replay": replay,
        "semantic_review": semantic,
        "theme_present": bool((gm or {}).get("th")),
        "intent_present": bool((gm or {}).get("in")) and bool((gm or {}).get("ic")),
        "audience_present": bool((gm or {}).get("au")) and bool((gm or {}).get("ac")),
        "voice_present": bool((gm or {}).get("vo")),
        "errors": list(decoded.get("errors") or [])
        + list(validator.get("errors") or []),
        "transport": transport,
        "repaired": False,
    }


__all__ = [
    "audit_relations_policy_c",
    "audit_traceability",
    "interpret_canary_response",
]
