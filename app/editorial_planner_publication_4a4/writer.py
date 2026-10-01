"""Atomic audit writes for Phase 4A.4. Does not rewrite A.3 / A.3.3 / A.3.5."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.editorial_planner_publication_4a4.constants import (
    AUDIT_ACCOUNTABILITY,
    AUDIT_BYTE_IDENTITY,
    AUDIT_FREEZE,
    AUDIT_LANGUAGE,
    AUDIT_PREPUBLICATION,
    AUDIT_PUBLICATION,
    AUDIT_RELOAD,
    PHASE,
)
from app.editorial_planner_publication_4a4.paths import (
    phase_audit_dir,
    readiness_path,
    report_path,
)
from app.editorial_planner_publication_4a4.report import render_report
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def _strip_identity(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    nested = dict(value)
    nested.pop("payload", None)
    nested.pop("canonical_json", None)
    nested.pop("plan", None)
    return nested


def _sanitize(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(payload or {})
    data.pop("payload", None)
    data.pop("canonical_json", None)
    data.pop("plan", None)
    for key in (
        "identity",
        "candidate",
        "existing",
        "published_identity",
        "candidate_identity",
        "language",
        "accountability",
    ):
        if key in data and isinstance(data[key], dict):
            nested = dict(data[key])
            nested.pop("payload", None)
            nested.pop("assigned_ids", None)
            nested.pop("deferred_ids", None)
            nested.pop("excluded_ids", None)
            nested.pop("reused_ids", None)
            nested.pop("measurement", None)
            nested.pop("policy", None)
            data[key] = nested
    validation = data.get("validation")
    if isinstance(validation, dict):
        nested = dict(validation)
        nested.pop("plan", None)
        if isinstance(nested.get("accountability"), dict):
            acc = dict(nested["accountability"])
            acc.pop("assigned_ids", None)
            acc.pop("deferred_ids", None)
            acc.pop("excluded_ids", None)
            acc.pop("reused_ids", None)
            nested["accountability"] = acc
        if isinstance(nested.get("language"), dict):
            lang = dict(nested["language"])
            lang.pop("measurement", None)
            lang.pop("policy", None)
            nested["language"] = lang
        data["validation"] = nested
    evidence = data.get("evidence")
    if isinstance(evidence, dict):
        data["evidence"] = _strip_identity(evidence)
    return data


def write_audit_bundle(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
    tests: str = "offline 4A.4",
) -> dict[str, Path]:
    directory = phase_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    gate = _sanitize(bundle.get("gate"))
    publication = _sanitize(bundle.get("publication"))
    reload = _sanitize(bundle.get("reload"))
    header = dict(bundle.get("header") or {})
    written = {
        "prepublication": write_bytes_atomic(
            directory / AUDIT_PREPUBLICATION,
            {"phase": PHASE, **gate, "candidate_identity": _strip_identity(
                bundle.get("candidate_identity")
            )},
        ),
        "publication": write_bytes_atomic(
            directory / AUDIT_PUBLICATION,
            {"phase": PHASE, **publication, "header": header},
        ),
        "byte_identity": write_bytes_atomic(
            directory / AUDIT_BYTE_IDENTITY,
            {
                "phase": PHASE,
                "byte_identity": header.get("byte_identity"),
                "published_sha256": header.get("published_sha256"),
                "actual_candidate_sha256": header.get("actual_candidate_sha256"),
                "expected_candidate_sha256": header.get("expected_candidate_sha256"),
                "published_bytes": reload.get("published_bytes"),
                "published_chars": reload.get("published_chars"),
            },
        ),
        "reload": write_bytes_atomic(
            directory / AUDIT_RELOAD,
            {"phase": PHASE, **reload},
        ),
        "accountability": write_bytes_atomic(
            directory / AUDIT_ACCOUNTABILITY,
            {
                "phase": PHASE,
                **dict(reload.get("accountability") or {}),
                "coverage_display": header.get("idea_coverage"),
                "assigned": header.get("assigned"),
                "deferred": header.get("deferred"),
                "excluded": header.get("excluded"),
                "silent_omissions": header.get("silent_omissions"),
                "duplicate_primary_dispositions": header.get(
                    "duplicate_primary_dispositions"
                ),
            },
        ),
        "language": write_bytes_atomic(
            directory / AUDIT_LANGUAGE,
            {
                "phase": PHASE,
                "canonical_language": header.get("canonical_language"),
                "language_policy": header.get("language_policy"),
                "editorial_language": header.get("editorial_language"),
                **_sanitize(reload.get("language") if isinstance(reload.get("language"), dict) else {}),
            },
        ),
        "freeze": write_bytes_atomic(
            directory / AUDIT_FREEZE,
            {"phase": PHASE, **dict(bundle.get("freeze") or {})},
        ),
        "readiness": write_bytes_atomic(
            readiness_path(root=root),
            dict(bundle.get("readiness") or {}),
        ),
        "report": write_bytes_atomic(
            report_path(root=root),
            render_report(bundle, tests=tests),
        ),
    }
    return written


__all__ = ["write_audit_bundle"]
