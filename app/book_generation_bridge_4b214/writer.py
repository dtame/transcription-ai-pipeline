"""Atomic 4B.2.14 audit writes. Never production book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_generation_bridge_4b214.constants import (
    AUDIT_ADAPTER,
    AUDIT_ARCHITECTURE,
    AUDIT_AUTHORIZATION,
    AUDIT_BUDGET_POLICY,
    AUDIT_BUDGET_RECONCILIATION,
    AUDIT_BUDGET_RESERVATION,
    AUDIT_COST_ASSUMPTIONS,
    AUDIT_COST_ESTIMATES,
    AUDIT_GRANULARITY,
    AUDIT_HASHES,
    AUDIT_IDEMPOTENCE,
    AUDIT_INDEX,
    AUDIT_INTERFACES,
    AUDIT_INVENTORY,
    AUDIT_PHASE5,
    AUDIT_READINESS,
    AUDIT_RECOVERY,
    AUDIT_REVIEW,
    AUDIT_SAFETY,
    AUDIT_SCENARIOS,
    AUDIT_SINGLE_CHAPTER,
    AUDIT_TESTS,
    AUDIT_TRACEABILITY,
    AUDIT_VOLUMES,
    PHASE,
)
from app.book_generation_bridge_4b214.paths import (
    phase_audit_dir,
    production_book_path,
    report_path,
)
from decimal import Decimal

from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def write_phase_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Path]:
    directory = phase_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    mapping = {
        "inventory": (AUDIT_INVENTORY, bundle.get("inventory")),
        "interfaces": (AUDIT_INTERFACES, bundle.get("interfaces")),
        "architecture": (AUDIT_ARCHITECTURE, bundle.get("architecture")),
        "adapter": (AUDIT_ADAPTER, bundle.get("adapter")),
        "granularity": (AUDIT_GRANULARITY, bundle.get("granularity")),
        "volumes": (AUDIT_VOLUMES, bundle.get("volumes")),
        "scenarios": (AUDIT_SCENARIOS, bundle.get("scenarios")),
        "cost_assumptions": (AUDIT_COST_ASSUMPTIONS, bundle.get("cost_assumptions")),
        "cost": (AUDIT_COST_ESTIMATES, bundle.get("cost")),
        "budget_policy": (AUDIT_BUDGET_POLICY, bundle.get("budget_policy")),
        "budget_reservation": (AUDIT_BUDGET_RESERVATION, bundle.get("budget_reservation")),
        "budget_reconciliation": (
            AUDIT_BUDGET_RECONCILIATION,
            bundle.get("budget_reconciliation"),
        ),
        "single_chapter": (AUDIT_SINGLE_CHAPTER, bundle.get("single_chapter")),
        "authorization": (AUDIT_AUTHORIZATION, bundle.get("authorization")),
        "review": (AUDIT_REVIEW, bundle.get("review")),
        "recovery": (AUDIT_RECOVERY, bundle.get("recovery")),
        "idempotence": (AUDIT_IDEMPOTENCE, bundle.get("idempotence")),
        "traceability": (AUDIT_TRACEABILITY, bundle.get("traceability")),
        "phase5": (AUDIT_PHASE5, bundle.get("phase5")),
        "safety": (AUDIT_SAFETY, bundle.get("safety")),
        "hashes": (AUDIT_HASHES, bundle.get("hashes")),
        "tests": (AUDIT_TESTS, bundle.get("tests")),
        "readiness": (AUDIT_READINESS, bundle.get("readiness")),
    }
    for key, (name, payload) in mapping.items():
        if payload is None:
            continue
        written[key] = write_bytes_atomic(directory / name, _jsonable(payload))
    report_text = bundle.get("report_text")
    if isinstance(report_text, str) and report_text.strip():
        written["report"] = write_bytes_atomic(report_path(root=root), report_text)
    header = {
        "phase": PHASE,
        "book_json": "NOT PUBLISHED",
        "production_book_absent": not production_book_path().is_file(),
        "written": sorted(written),
        "result": (bundle.get("header") or {}).get("result"),
        "real_provider_calls": 0,
        "openai_http_requests": 0,
        "anthropic_http_requests": 0,
        "historical_contracts_modified": False,
        "historical_labels_modified": False,
        "production_pipeline_modified": False,
        "bridge_enabled_by_default": False,
        "real_providers_enabled": False,
        "real_chapter_generation_authorized": False,
    }
    written["index"] = write_bytes_atomic(directory / AUDIT_INDEX, header)
    return written


__all__ = ["write_phase_artifacts"]
