"""Atomic 4B.2.15 audit writes. Never production book.json. Never historical mutation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b215.constants import (
    AUDIT_AUTHORIZATION,
    AUDIT_BUDGET,
    AUDIT_CONTRACT,
    AUDIT_COST,
    AUDIT_COVERAGE,
    AUDIT_EVIDENCE,
    AUDIT_HASHES_POST,
    AUDIT_HASHES_PRE,
    AUDIT_HISTORICAL,
    AUDIT_INDEX,
    AUDIT_POLICY,
    AUDIT_PREFLIGHT,
    AUDIT_RAW_RESPONSE,
    AUDIT_READINESS,
    AUDIT_REPLAY,
    AUDIT_REQUEST,
    AUDIT_REQUEST_SHA,
    AUDIT_SAFETY,
    AUDIT_SEMANTIC,
    AUDIT_TESTS,
    AUDIT_USAGE,
    PHASE,
)
from app.book_semantic_gate_4b215.paths import (
    canary_audit_dir,
    historical_audit_dirs,
    production_book_path,
    report_path,
)
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def _write(path: Path, payload: Mapping[str, Any] | str) -> Path:
    return write_bytes_atomic(path, payload)


def _assert_isolated(target: Path, historical: Mapping[str, Path]) -> None:
    resolved = target.resolve()
    for name, directory in historical.items():
        hist = directory.resolve()
        if resolved == hist or hist in resolved.parents or resolved.parent == hist:
            raise RuntimeError(
                f"4B.2.15 must not write into historical {name} audit directory."
            )


def persist_raw_evidence(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Path]:
    directory = canary_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    historical = historical_audit_dirs(root=root)
    written: dict[str, Path] = {}
    raw = bundle.get("provider_response_raw") or bundle.get("raw_response")
    if raw is not None:
        target = directory / AUDIT_RAW_RESPONSE
        _assert_isolated(target, historical)
        written["raw_response"] = _write(target, raw)
    usage = bundle.get("provider_usage") or bundle.get("token_usage")
    if usage is not None:
        target = directory / AUDIT_USAGE
        _assert_isolated(target, historical)
        written["usage"] = _write(target, usage)
    cost = bundle.get("provider_cost")
    if cost is not None:
        target = directory / AUDIT_COST
        _assert_isolated(target, historical)
        written["cost"] = _write(target, cost)
    return written


def freeze_provider_request(
    payload: Mapping[str, Any],
    sha256: str,
    *,
    root: Path | None = None,
) -> dict[str, Path]:
    directory = canary_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    historical = historical_audit_dirs(root=root)
    target = directory / AUDIT_REQUEST
    _assert_isolated(target, historical)
    if target.is_file():
        existing = json.loads(target.read_text(encoding="utf-8"))
        if existing != dict(payload):
            raise RuntimeError(
                "Frozen provider_request.json already exists and differs. "
                "4B.2.15 must not mutate a frozen request."
            )
        return {"request": target}
    written = {"request": _write(target, payload)}
    sha_target = directory / AUDIT_REQUEST_SHA
    _assert_isolated(sha_target, historical)
    written["request_sha"] = _write(
        sha_target,
        {
            "phase": PHASE,
            "algorithm": "sha256",
            "request_sha256": sha256,
            "serialization": "json.dumps(payload, ensure_ascii=False, sort_keys=True)",
            "secrets_included": False,
        },
    )
    return written


def write_canary_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Path]:
    directory = canary_audit_dir(root=root)
    historical = historical_audit_dirs(root=root)
    if directory.resolve() in {path.resolve() for path in historical.values()}:
        raise RuntimeError("4B.2.15 must not write into a historical audit directory.")
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    mapping = {
        "preflight": (AUDIT_PREFLIGHT, bundle.get("preflight") or bundle.get("precall")),
        "hashes_pre": (
            AUDIT_HASHES_PRE,
            bundle.get("canonical_hashes_pre") or bundle.get("canonical_hashes_before"),
        ),
        "authorization": (AUDIT_AUTHORIZATION, bundle.get("authorization_manifest")),
        "budget": (AUDIT_BUDGET, bundle.get("budget_reservation") or bundle.get("provider_cost")),
        "request": (AUDIT_REQUEST, bundle.get("provider_request") or (bundle.get("request_identity") or {}).get("payload")),
        "request_sha": (AUDIT_REQUEST_SHA, bundle.get("request_sha256_payload")),
        "usage": (AUDIT_USAGE, bundle.get("provider_usage")),
        "cost": (AUDIT_COST, bundle.get("provider_cost")),
        "contract": (AUDIT_CONTRACT, bundle.get("contract_validation")),
        "coverage": (AUDIT_COVERAGE, bundle.get("unit_coverage") or bundle.get("unit_coverage_validation")),
        "evidence": (AUDIT_EVIDENCE, bundle.get("evidence_validation")),
        "semantic": (AUDIT_SEMANTIC, bundle.get("semantic_review") or bundle.get("semantic_human_review")),
        "historical": (AUDIT_HISTORICAL, bundle.get("historical_comparison")),
        "policy": (AUDIT_POLICY, bundle.get("acceptance_policy")),
        "replay": (AUDIT_REPLAY, bundle.get("deterministic_replay") or bundle.get("replay")),
        "safety": (AUDIT_SAFETY, bundle.get("provider_safety")),
        "tests": (AUDIT_TESTS, bundle.get("offline_tests") or bundle.get("tests")),
        "hashes_post": (
            AUDIT_HASHES_POST,
            bundle.get("canonical_hashes_post") or bundle.get("canonical_hashes_after"),
        ),
        "readiness": (AUDIT_READINESS, bundle.get("readiness")),
    }
    for key, (name, payload) in mapping.items():
        if payload is None:
            continue
        target = directory / name
        _assert_isolated(target, historical)
        written[key] = _write(target, payload)
    raw = bundle.get("provider_response_raw") or bundle.get("raw_response")
    if raw is not None:
        target = directory / AUDIT_RAW_RESPONSE
        _assert_isolated(target, historical)
        written["raw_response"] = _write(target, raw)
    report_text = bundle.get("report_text")
    if isinstance(report_text, str) and report_text.strip():
        written["report"] = _write(report_path(root=root), report_text)
    header = {
        "phase": PHASE,
        "book_json": "NOT PUBLISHED",
        "production_book_absent": not production_book_path().is_file(),
        "written": sorted(written),
        "result": (bundle.get("header") or {}).get("result"),
        "remote_invocations": (bundle.get("header") or {}).get("remote_invocations"),
        "historical_dirs_untouched": True,
        "historical_dirs": {name: str(path) for name, path in historical.items()},
        "candidate_promoted": False,
        "human_label_modified": False,
        "production_pipeline_modified": False,
        "semantic_gate_202_activated": False,
        "bridge_4b214_enabled": False,
    }
    written["index"] = _write(directory / AUDIT_INDEX, header)
    return written


__all__ = ["freeze_provider_request", "persist_raw_evidence", "write_canary_artifacts"]
