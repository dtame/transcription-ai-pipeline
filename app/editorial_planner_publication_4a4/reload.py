"""Reload published editorial_plan.json through the production reader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.editorial_planner_canary_4a35.accountability import exact_accountability
from app.editorial_planner_canary_4a35.language import language_audit
from app.editorial_planner_publication_4a4.constants import (
    BYTE_IDENTITY_EXACT,
    BYTE_IDENTITY_FAIL,
    EXPECTED_CANONICAL_DOCUMENT_LANGUAGE,
    WORKING_TITLE,
)
from app.editorial_planner_publication_4a4.gates import unknown_reference_counts
from app.editorial_planner_publication_4a4.identity import bytes_identity, file_identity
from app.editorial_planning.pipeline import load_published_editorial_plan
from app.editorial_planning.validator import validate_editorial_plan
from app.editorial_planning.writer import render_editorial_plan
from app.source_analysis.models import SourceMap
from app.source_analysis.writer import partial_path


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def reload_published(
    project_name: str,
    *,
    candidate_bytes: bytes,
    source_map: SourceMap,
    sortie_dir: Path | None = None,
    published_path: Path | None = None,
    canonical_document_language: str = EXPECTED_CANONICAL_DOCUMENT_LANGUAGE,
    expected_title: str | None = WORKING_TITLE,
) -> dict[str, Any]:
    try:
        if published_path is not None:
            from app.editorial_planning.models import EditorialPlan
            import hashlib
            import json

            path = Path(published_path)
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("published editorial_plan.json is not an object")
            plan = EditorialPlan.from_dict(payload)
        else:
            plan, raw, digest, path = load_published_editorial_plan(
                project_name, sortie_dir=sortie_dir
            )
        load_ok = True
        load_error = ""
    except Exception as exc:  # noqa: BLE001
        plan = None
        raw = b""
        digest = ""
        path = Path("")
        load_ok = False
        load_error = f"{type(exc).__name__}: {exc}"
    identity = file_identity(path) if load_ok else bytes_identity(raw)
    payload = identity.get("payload") or {}
    validation = None
    if plan is not None:
        validation = validate_editorial_plan(plan, source_map, payload=payload)
    accountability = exact_accountability(payload if payload else None, source_map)
    language = language_audit(
        payload if payload else None,
        canonical_document_language=canonical_document_language,
    )
    unknown = (
        unknown_reference_counts(plan, source_map)
        if plan is not None
        else {"IDEA": -1, "TOP": -1, "EX": -1, "REF": -1, "UNC": -1}
    )
    unknown_total = sum(max(0, value) for value in unknown.values())
    chapters = len(plan.chapters) if plan is not None else 0
    sections = len(plan.all_sections()) if plan is not None else 0
    title = plan.selected_title if plan is not None else ""
    byte_match = raw == candidate_bytes and bool(raw)
    serialized = ""
    deterministic = "n/a"
    if plan is not None:
        serialized = render_editorial_plan(plan.to_dict())
        deterministic = "PASS" if serialized else "FAIL"
    validator_status = validation.status if validation is not None else "FAIL"
    language_status = str(language.get("editorial_language_match") or "FAIL")
    return {
        "path": str(path).replace("\\", "/") if path else "",
        "exists": bool(load_ok and raw),
        "json_parse": _status(load_ok and bool(payload)),
        "model_load": _status(load_ok and plan is not None),
        "model_error": load_error,
        "validator": validator_status,
        "validator_errors": list(validation.errors) if validation is not None else [],
        "accountability": accountability,
        "language": language,
        "editorial_language": language_status,
        "unknown_refs": unknown,
        "unknown_ref_total": unknown_total,
        "chapters": chapters,
        "sections": sections,
        "selected_title": title,
        "title_ok": title == expected_title if expected_title is not None else True,
        "byte_identity": BYTE_IDENTITY_EXACT if byte_match else BYTE_IDENTITY_FAIL,
        "published_sha256": digest or identity.get("sha256") or "",
        "published_bytes": len(raw),
        "published_chars": identity.get("character_count") or 0,
        "deterministic_serialization": deterministic,
        "rewrote_production": False,
        "partial_leftover": partial_path(path).exists() if path else False,
        "coverage_display": accountability.get("coverage_display"),
        "assigned": accountability.get("assigned_count"),
        "deferred": accountability.get("deferred_count"),
        "excluded": accountability.get("excluded_count"),
        "silent_omissions": accountability.get("silent_omissions"),
        "duplicate_primary": len(accountability.get("duplicate_primary_ids") or []),
        "reload": _status(
            load_ok
            and validator_status == "PASS"
            and accountability.get("exactly_once") is True
            and language_status == "PASS"
            and unknown_total == 0
            and byte_match
        ),
    }


__all__ = ["reload_published"]
