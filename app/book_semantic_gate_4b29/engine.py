"""Offline Semantic Gate 2.0 orchestration. Transport must be injected."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b29.constants import DECISION_BLOCK, PHASE
from app.book_semantic_gate_4b29.coverage import validate_prepared_coverage
from app.book_semantic_gate_4b29.diagnostics import build_diagnostics
from app.book_semantic_gate_4b29.guard import BookSemanticGate29Error, assert_offline_only
from app.book_semantic_gate_4b29.interface import SemanticModelTransport, require_local_transport
from app.book_semantic_gate_4b29.policy import apply_acceptance_policy
from app.book_semantic_gate_4b29.preparation import prepare_paragraph_units
from app.book_semantic_gate_4b29.request import build_model_request
from app.book_semantic_gate_4b29.validator import validate_response_20


def evaluate_paragraph(
    *,
    paragraph_id: str,
    text: str,
    transport: SemanticModelTransport,
    evidence_handles: Sequence[str] | None = None,
    evidence_records: Sequence[Mapping[str, Any]] | None = None,
    context: Mapping[str, Any] | None = None,
    chapter_handle: str = "CH016",
) -> dict[str, Any]:
    """Run preparation → request → injected transport → validator → policy.

    No provider is contacted unless a transport that does so is explicitly
    injected. 4B.2.9 rejects remote transports.
    """
    assert_offline_only()
    local = require_local_transport(transport)
    prepared = prepare_paragraph_units(
        paragraph_id,
        text,
        context=context,
        evidence_handles=evidence_handles,
    )
    coverage = validate_prepared_coverage(prepared)
    request = build_model_request(
        prepared,
        chapter_handle=chapter_handle,
        evidence_records=evidence_records,
    )
    raw: Any = None
    if coverage.get("ok"):
        raw = local.evaluate(request)
        validation = validate_response_20(
            raw,
            prepared,
            allowed_evidence=list(prepared.get("evidence_handles") or []),
            expected_chapter=chapter_handle,
        )
    else:
        validation = {
            "ok": False,
            "status": DECISION_BLOCK,
            "errors": ["preparation_coverage_failed"],
            "parsed": None,
            "verdicts": [],
            "required_unit_ids": [unit["unit_id"] for unit in prepared.get("units") or []],
            "raw_preserved": True,
            "does_not_complete_missing_units": True,
            "does_not_repair_reason_codes": True,
            "does_not_rewrite_model_response": True,
        }
    policy = apply_acceptance_policy(prepared, coverage, validation)
    diagnostics = build_diagnostics(
        prepared=prepared,
        coverage=coverage,
        request=request,
        raw=raw,
        validation=validation,
        policy=policy,
        transport_source=str(getattr(local, "source", "") or ""),
    )
    return {
        "phase": PHASE,
        "decision": policy.get("decision"),
        "prepared": prepared,
        "coverage": coverage,
        "request": request,
        "raw": raw,
        "validation": validation,
        "policy": policy,
        "diagnostics": diagnostics,
        "transport_source": getattr(local, "source", ""),
        "not_terra": True,
        "production_hook_connected": False,
        "secrets_included": False,
    }


def evaluate_or_reject_remote(**kwargs: Any) -> dict[str, Any]:
    try:
        return evaluate_paragraph(**kwargs)
    except BookSemanticGate29Error as exc:
        return {
            "phase": PHASE,
            "decision": DECISION_BLOCK,
            "error": str(exc),
            "remote_blocked": True,
            "not_terra": True,
        }


__all__ = ["evaluate_or_reject_remote", "evaluate_paragraph"]
