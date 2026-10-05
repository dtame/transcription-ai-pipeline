"""Atomic 4B.2.11 audit writes. Never production book.json. Never historical mutation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b211.constants import (
    AUDIT_CONTRACT,
    AUDIT_COST,
    AUDIT_COVERAGE,
    AUDIT_EVIDENCE,
    AUDIT_HASHES_AFTER,
    AUDIT_HASHES_BEFORE,
    AUDIT_INDEX,
    AUDIT_INVOCATION,
    AUDIT_LEAK,
    AUDIT_POLICY,
    AUDIT_PREFLIGHT,
    AUDIT_RAW_RESPONSE,
    AUDIT_READINESS,
    AUDIT_REPLAY,
    AUDIT_REQUEST,
    AUDIT_REQUEST_SHA,
    AUDIT_SEMANTIC,
    AUDIT_SERIALIZATION,
    AUDIT_TESTS,
    AUDIT_USAGE,
    PHASE,
)
from app.book_semantic_gate_4b211.paths import (
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
                f"4B.2.11 must not write into historical {name} audit directory."
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
    provider = bundle.get("provider_invocation") or bundle.get("provider_evidence")
    if provider is not None:
        target = directory / AUDIT_INVOCATION
        _assert_isolated(target, historical)
        written["invocation"] = _write(target, provider)
    usage = bundle.get("provider_usage") or bundle.get("token_usage")
    if usage is not None:
        target = directory / AUDIT_USAGE
        _assert_isolated(target, historical)
        written["usage"] = _write(target, usage)
    return written


def write_canary_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Path]:
    directory = canary_audit_dir(root=root)
    historical = historical_audit_dirs(root=root)
    if directory.resolve() in {path.resolve() for path in historical.values()}:
        raise RuntimeError("4B.2.11 must not write into a historical audit directory.")
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    mapping = {
        "preflight": (AUDIT_PREFLIGHT, bundle.get("preflight") or bundle.get("precall")),
        "hashes_before": (
            AUDIT_HASHES_BEFORE,
            bundle.get("canonical_hashes_before") or (bundle.get("precall") or {}).get("canonical_hashes"),
        ),
        "request": (AUDIT_REQUEST, bundle.get("request_integrity") or bundle.get("request_identity")),
        "leak": (AUDIT_LEAK, bundle.get("label_leakage_check") or bundle.get("label_leakage_verification")),
        "serialization": (AUDIT_SERIALIZATION, bundle.get("sdk_serialization")),
        "invocation": (AUDIT_INVOCATION, bundle.get("provider_invocation")),
        "usage": (AUDIT_USAGE, bundle.get("provider_usage")),
        "cost": (AUDIT_COST, bundle.get("provider_cost") or bundle.get("cost")),
        "contract": (AUDIT_CONTRACT, bundle.get("contract_validation")),
        "coverage": (AUDIT_COVERAGE, bundle.get("unit_coverage_validation")),
        "evidence": (AUDIT_EVIDENCE, bundle.get("evidence_validation")),
        "semantic": (AUDIT_SEMANTIC, bundle.get("semantic_human_review") or bundle.get("semantic_review")),
        "policy": (AUDIT_POLICY, bundle.get("acceptance_policy")),
        "replay": (AUDIT_REPLAY, bundle.get("deterministic_replay") or bundle.get("replay")),
        "tests": (AUDIT_TESTS, bundle.get("offline_regression_tests") or bundle.get("tests")),
        "hashes_after": (AUDIT_HASHES_AFTER, bundle.get("canonical_hashes_after")),
        "readiness": (AUDIT_READINESS, bundle.get("readiness")),
    }
    for key, (name, payload) in mapping.items():
        if payload is None:
            continue
        target = directory / name
        _assert_isolated(target, historical)
        written[key] = _write(target, payload)
    sha = bundle.get("request_sha256_text")
    if isinstance(sha, str) and sha.strip():
        written["request_sha"] = _write(directory / AUDIT_REQUEST_SHA, sha.strip())
    raw = bundle.get("provider_response_raw") or bundle.get("raw_response")
    if raw is not None and "raw_response" not in written:
        written["raw_response"] = _write(directory / AUDIT_RAW_RESPONSE, raw)
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
        "semantic_gate_20_activated": False,
    }
    written["index"] = _write(directory / AUDIT_INDEX, header)
    return written


__all__ = ["persist_raw_evidence", "write_canary_artifacts"]
