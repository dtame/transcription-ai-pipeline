"""
Structural provenance inspector.

Handle presence is not semantic equivalence. Content checks on fixtures are
explicitly not a Semantic Gate certificate.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.book_generation.coverage import assigned_idea_ids_for_chapter
from app.book_generation.evidence import classify_handle
from app.book_generation.errors import BookGenerationTransportError
from app.book_generation.pipeline import materialize_chapter
from app.book_generation.transport import decode_transport
from app.book_generation.validator import validate_chapter_candidate
from app.editorial_planning.models import EditorialChapter, EditorialPlan
from app.source_analysis.models import SourceMap


def inspect_transport(
    transport: Any,
    *,
    plan: EditorialPlan,
    source_map: SourceMap,
    chapter: EditorialChapter,
    language: str,
    allowed_handles: Iterable[str] | None = None,
    content_expectations: Mapping[str, Any] | None = None,
    stop_reason: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    json_valid = isinstance(transport, Mapping)
    truncated = stop_reason in {"max_tokens", "length", "incomplete", "truncated"}
    if truncated:
        errors.append("output marked truncated")
    if not json_valid:
        errors.append("provider JSON is not a valid object")
        return _result(
            json_valid=False,
            truncated=truncated,
            errors=errors,
            warnings=warnings,
            status="FAIL",
        )
    try:
        decoded = decode_transport(transport)
    except BookGenerationTransportError as exc:
        errors.extend(list(exc.errors))
        return _result(
            json_valid=True,
            truncated=truncated or True,
            errors=errors,
            warnings=warnings,
            status="FAIL",
        )
    candidate, validation, digest = materialize_chapter(
        decoded,
        plan,
        source_map,
        chapter,
        language=language,
        allowed_handles=list(allowed_handles or []),
    )
    if validation.status == "FAIL":
        errors.extend(list(validation.errors))
    warnings.extend(list(validation.warnings))
    planned = list(assigned_idea_ids_for_chapter(chapter))
    paragraph_ideas: list[str] = []
    paragraph_src: list[str] = []
    invented: list[str] = []
    allowed = set(allowed_handles or [])
    prose_by_idea: dict[str, list[str]] = {idea_id: [] for idea_id in planned}
    for section in candidate.sections:
        for paragraph in section.paragraphs:
            handles = list(paragraph.evidence_handles) + list(paragraph.uncertainty_refs)
            for handle in handles:
                kind = classify_handle(handle)
                if kind == "IDEA":
                    paragraph_ideas.append(handle)
                    if handle in prose_by_idea:
                        prose_by_idea[handle].append(paragraph.text)
                if kind == "SRC":
                    paragraph_src.append(handle)
                if allowed and handle not in allowed:
                    invented.append(handle)
    missing_ideas = [idea_id for idea_id in planned if idea_id not in set(paragraph_ideas)]
    extra_ideas = [
        idea_id for idea_id in paragraph_ideas if idea_id not in set(planned)
    ]
    if missing_ideas:
        errors.append("IDEA handles missing from paragraph evidence: " + ",".join(missing_ideas))
    if extra_ideas:
        errors.append("invented or unassigned IDEA handles: " + ",".join(sorted(set(extra_ideas))))
    invalid_src = [
        src
        for src in paragraph_src
        if classify_handle(src) != "SRC" or (allowed and src not in allowed)
    ]
    if invalid_src:
        errors.append("invalid SRC handles: " + ",".join(sorted(set(invalid_src))))

    content_rows = []
    if content_expectations:
        for idea_id, expected in (content_expectations.get("ideas") or {}).items():
            tokens = list(expected.get("required_tokens") or [])
            texts = " ".join(prose_by_idea.get(idea_id) or []).lower()
            present = [token for token in tokens if token.lower() in texts]
            missing_tokens = [token for token in tokens if token.lower() not in texts]
            handle_present = idea_id in set(paragraph_ideas)
            if handle_present and missing_tokens:
                errors.append(
                    f"{idea_id} handle declared without corresponding required content"
                )
            if present and not handle_present and expected.get("require_handle"):
                warnings.append(
                    f"{idea_id} content tokens appear without an IDEA handle"
                )
            content_rows.append(
                {
                    "idea_id": idea_id,
                    "handle_present": handle_present,
                    "required_tokens_present": present,
                    "required_tokens_missing": missing_tokens,
                    "not_semantic_equivalence": True,
                }
            )
        for row in content_expectations.get("narrative") or []:
            text = " ".join(
                paragraph.text for section in candidate.sections for paragraph in section.paragraphs
            )
            needle = str(row.get("must_contain") or "")
            forbidden = str(row.get("must_not_contain") or "")
            ok = (not needle or needle in text) and (not forbidden or forbidden not in text)
            if not ok:
                errors.append(str(row.get("failure") or "narrative attribution check failed"))
            content_rows.append(
                {
                    "kind": row.get("kind"),
                    "ok": ok,
                    "not_semantic_equivalence": True,
                }
            )

    structural = validate_chapter_candidate(
        candidate,
        plan,
        source_map,
        chapter,
        language=language,
        allowed_handles=allowed_handles,
    )
    if structural.status == "FAIL":
        for item in structural.errors:
            if item not in errors:
                errors.append(item)
    status = "FAIL" if errors else "PASS"
    return _result(
        json_valid=True,
        truncated=truncated,
        errors=errors,
        warnings=warnings,
        status=status,
        extra={
            "candidate_sha256": digest,
            "missing_idea_handles": missing_ideas,
            "invented_idea_handles": sorted(set(extra_ideas + invented)),
            "invalid_src": sorted(set(invalid_src)),
            "content_rows": content_rows,
            "structural_validator_status": structural.status,
            "not_semantic_equivalence": True,
        },
    )


def _result(
    *,
    json_valid: bool,
    truncated: bool,
    errors: list[str],
    warnings: list[str],
    status: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "json_valid": json_valid,
        "truncated": truncated,
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "not_semantic_equivalence": True,
        "must_not_backfill_paras_e": True,
    }
    if extra:
        payload.update(extra)
    return payload


__all__ = ["inspect_transport"]
