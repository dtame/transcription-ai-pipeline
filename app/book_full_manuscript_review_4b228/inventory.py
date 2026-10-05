"""Resolve and verify the 19 chapter sources. Read-only. STOP on mismatch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.book_ch002_offline_recovery_4b224.chapter_io import (
    iter_candidate_paragraphs,
    load_json,
)
from app.book_generation.coverage import assigned_idea_ids_for_chapter, chapter_by_id
from app.book_full_manuscript_review_4b228.constants import (
    ACCEPTED_CHAPTER_IDS,
    CANONICAL_CHAPTER_IDS,
    CH012_ACCEPTED_JSON_REL,
    CH012_ACCEPTED_MD_REL,
    CH012_IDEA_MAPPING_REL,
    CH012_ORIGINAL_JSON_REL,
    CH012_ORIGINAL_MD_REL,
    CH002_IDEA_REVIEW_REL,
    CH002_ORIGINAL_JSON_REL,
    CH002_ORIGINAL_MD_REL,
    EXPECTED_ACCEPTED_JSON_SHA256,
    EXPECTED_ACCEPTED_MD_SHA256,
    EXPECTED_CH001_JSON_SHA256,
    EXPECTED_CH001_MD_SHA256,
    EXPECTED_CH002_RECOVERED_JSON_SHA256,
    EXPECTED_CH002_RECOVERED_MD_SHA256,
    EXPECTED_CH003_JSON_SHA256,
    EXPECTED_CH003_MD_SHA256,
    EXPECTED_CH004_JSON_SHA256,
    EXPECTED_CH004_MD_SHA256,
    EXPECTED_CH018_JSON_SHA256,
    EXPECTED_CH018_MD_SHA256,
    EXPECTED_IDEA_COUNT,
    EXPECTED_SECTION_COUNT,
    GENERATED_STRUCTURALLY_VALID,
    HUMAN_ACCEPTANCE_STATUS,
    HUMAN_REVIEW_PENDING_STATUS,
    PENDING_CHAPTER_IDS,
    PHASE,
)
from app.book_full_manuscript_review_4b228.guard import BookFullManuscriptReview4228Error
from app.book_full_manuscript_review_4b228.hashes import file_sha256
from app.book_full_manuscript_review_4b228.paths import (
    ch001_approved_json_path,
    ch001_approved_md_path,
    ch001_existing_manifest_path,
    ch002_approved_json_path,
    ch002_approved_md_path,
    ch002_existing_manifest_path,
    ch002_original_json_path,
    ch002_original_md_path,
    ch003_accepted_manifest_path,
    ch003_approved_json_path,
    ch003_approved_md_path,
    ch004_accepted_manifest_path,
    ch004_approved_json_path,
    ch004_approved_md_path,
    ch012_accepted_manifest_path,
    ch012_original_json_path,
    ch012_original_md_path,
    ch018_accepted_manifest_path,
    ch018_json_path,
    ch018_md_path,
    historical_rel,
    remaining13_chapter_dir,
    remaining13_json_path,
    remaining13_md_path,
)
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus, load_canonical_corpus


def _rel(path: Path) -> str:
    return str(path).replace("\\", "/")


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def parse_markdown_document(text: str) -> dict[str, Any]:
    normalized = text.replace("\r\n", "\n").strip("\n")
    blocks = [block.strip("\n") for block in normalized.split("\n\n")]
    title = ""
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for block in blocks:
        stripped = block.strip()
        if not stripped:
            continue
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            continue
        if stripped.startswith("## ") and not stripped.startswith("### "):
            current = {"title": stripped[3:].strip(), "paragraphs": []}
            sections.append(current)
            continue
        if current is None:
            raise BookFullManuscriptReview4228Error(
                "Markdown prose appeared before the first section heading."
            )
        current["paragraphs"].append(stripped)
    return {"title": title, "sections": sections}


def _verify_expected(path: Path, expected: str | None, label: str) -> dict[str, Any]:
    hashed = file_sha256(path)
    if not hashed.get("exists"):
        raise BookFullManuscriptReview4228Error(f"{label} is missing: {path}. STOP.")
    if expected and hashed.get("sha256") != expected:
        raise BookFullManuscriptReview4228Error(
            f"{label} hash mismatch: {hashed.get('sha256')} ≠ {expected}. STOP."
        )
    return hashed


def _idea_ids_from_chapter(payload: dict[str, Any]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for _section_id, _index, paragraph in iter_candidate_paragraphs(payload):
        handles = list(paragraph.get("evidence_handles") or []) + list(
            paragraph.get("idea_refs") or []
        )
        for handle in handles:
            text = str(handle)
            if text.startswith("IDEA") and text not in seen:
                seen.add(text)
                found.append(text)
    return found


def _paragraphs_from_json(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section in payload.get("sections") or []:
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id") or "")
        section_title = str(section.get("title") or "")
        for paragraph in section.get("paragraphs") or []:
            if not isinstance(paragraph, dict):
                continue
            text = str(paragraph.get("text") or "")
            rows.append(
                {
                    "section_id": section_id,
                    "section_title": section_title,
                    "paragraph_id": str(paragraph.get("paragraph_id") or ""),
                    "text": text,
                    "kind": str(paragraph.get("kind") or ""),
                    "evidence_handles": [
                        str(item) for item in (paragraph.get("evidence_handles") or [])
                    ],
                    "source_refs": [str(item) for item in (paragraph.get("source_refs") or [])],
                    "idea_refs": [str(item) for item in (paragraph.get("idea_refs") or [])],
                    "example_refs": [
                        str(item) for item in (paragraph.get("example_refs") or [])
                    ],
                    "reference_refs": [
                        str(item) for item in (paragraph.get("reference_refs") or [])
                    ],
                    "uncertainty_refs": [
                        str(item) for item in (paragraph.get("uncertainty_refs") or [])
                    ],
                }
            )
    return rows


def _source_spec(chapter_id: str, *, root: Path | None = None) -> dict[str, Any]:
    accepted = {
        "CH001": {
            "json_path": ch001_approved_json_path(),
            "markdown_path": ch001_approved_md_path(),
            "manifest_path": ch001_existing_manifest_path(),
            "expected_json": EXPECTED_CH001_JSON_SHA256,
            "expected_md": EXPECTED_CH001_MD_SHA256,
            "approved_version": "4b223_generated_candidate",
            "status": HUMAN_ACCEPTANCE_STATUS,
            "human_status_exact": HUMAN_ACCEPTANCE_STATUS,
            "forbidden_json": (),
            "forbidden_md": (),
        },
        "CH002": {
            "json_path": ch002_approved_json_path(),
            "markdown_path": ch002_approved_md_path(),
            "manifest_path": ch002_existing_manifest_path(),
            "expected_json": EXPECTED_CH002_RECOVERED_JSON_SHA256,
            "expected_md": EXPECTED_CH002_RECOVERED_MD_SHA256,
            "approved_version": "offline_derived_recovered",
            "status": HUMAN_ACCEPTANCE_STATUS,
            "human_status_exact": HUMAN_ACCEPTANCE_STATUS,
            "forbidden_json": (ch002_original_json_path(),),
            "forbidden_md": (ch002_original_md_path(),),
        },
        "CH003": {
            "json_path": ch003_approved_json_path(),
            "markdown_path": ch003_approved_md_path(),
            "manifest_path": ch003_accepted_manifest_path(),
            "expected_json": EXPECTED_CH003_JSON_SHA256,
            "expected_md": EXPECTED_CH003_MD_SHA256,
            "approved_version": "4b225_generated_candidate",
            "status": HUMAN_ACCEPTANCE_STATUS,
            "human_status_exact": HUMAN_ACCEPTANCE_STATUS,
            "forbidden_json": (),
            "forbidden_md": (),
        },
        "CH004": {
            "json_path": ch004_approved_json_path(),
            "markdown_path": ch004_approved_md_path(),
            "manifest_path": ch004_accepted_manifest_path(),
            "expected_json": EXPECTED_CH004_JSON_SHA256,
            "expected_md": EXPECTED_CH004_MD_SHA256,
            "approved_version": "4b225_generated_candidate",
            "status": HUMAN_ACCEPTANCE_STATUS,
            "human_status_exact": HUMAN_ACCEPTANCE_STATUS,
            "forbidden_json": (),
            "forbidden_md": (),
        },
        "CH012": {
            "json_path": historical_rel(CH012_ACCEPTED_JSON_REL),
            "markdown_path": historical_rel(CH012_ACCEPTED_MD_REL),
            "manifest_path": ch012_accepted_manifest_path(),
            "expected_json": EXPECTED_ACCEPTED_JSON_SHA256,
            "expected_md": EXPECTED_ACCEPTED_MD_SHA256,
            "approved_version": "chapter_candidate_authorial_v2",
            "status": HUMAN_ACCEPTANCE_STATUS,
            "human_status_exact": HUMAN_ACCEPTANCE_STATUS,
            "forbidden_json": (ch012_original_json_path(),),
            "forbidden_md": (ch012_original_md_path(),),
        },
        "CH018": {
            "json_path": ch018_json_path(),
            "markdown_path": ch018_md_path(),
            "manifest_path": ch018_accepted_manifest_path(),
            "expected_json": EXPECTED_CH018_JSON_SHA256,
            "expected_md": EXPECTED_CH018_MD_SHA256,
            "approved_version": "4b221_generated_candidate",
            "status": HUMAN_ACCEPTANCE_STATUS,
            "human_status_exact": HUMAN_ACCEPTANCE_STATUS,
            "forbidden_json": (),
            "forbidden_md": (),
        },
    }
    if chapter_id in accepted:
        return accepted[chapter_id]
    return {
        "json_path": remaining13_json_path(chapter_id, root=root),
        "markdown_path": remaining13_md_path(chapter_id, root=root),
        "manifest_path": None,
        "sidecar_dir": remaining13_chapter_dir(chapter_id, root=root),
        "expected_json": None,
        "expected_md": None,
        "approved_version": "4b227_generated_candidate",
        "status": GENERATED_STRUCTURALLY_VALID,
        "human_status_exact": HUMAN_REVIEW_PENDING_STATUS,
        "forbidden_json": (),
        "forbidden_md": (),
    }


def _sidecar_dir(spec: dict[str, Any]) -> Path:
    if spec.get("sidecar_dir"):
        return Path(spec["sidecar_dir"])
    return Path(spec["json_path"]).parent


def inspect_chapter(
    chapter_id: str,
    *,
    corpus: CanonicalCorpus,
    book_order: int,
    root: Path | None = None,
) -> dict[str, Any]:
    spec = _source_spec(chapter_id, root=root)
    json_hash = _verify_expected(spec["json_path"], spec["expected_json"], f"{chapter_id} JSON")
    md_hash = _verify_expected(spec["markdown_path"], spec["expected_md"], f"{chapter_id} Markdown")
    for forbidden in spec["forbidden_json"]:
        if Path(spec["json_path"]).resolve() == Path(forbidden).resolve():
            raise BookFullManuscriptReview4228Error(
                f"{chapter_id} resolved to a forbidden historical JSON. STOP."
            )
    for forbidden in spec["forbidden_md"]:
        if Path(spec["markdown_path"]).resolve() == Path(forbidden).resolve():
            raise BookFullManuscriptReview4228Error(
                f"{chapter_id} resolved to a forbidden historical Markdown. STOP."
            )
    payload = load_json(spec["json_path"])
    if not isinstance(payload, dict):
        raise BookFullManuscriptReview4228Error(f"{chapter_id} JSON is not an object. STOP.")
    if str(payload.get("chapter_id") or "") != chapter_id:
        raise BookFullManuscriptReview4228Error(
            f"{chapter_id} JSON identifier is {payload.get('chapter_id')!r}. STOP."
        )
    planned = chapter_by_id(corpus.plan, chapter_id)
    planned_sections = [section.section_id for section in planned.sections]
    planned_ideas = list(assigned_idea_ids_for_chapter(planned))
    generated_sections = [
        str(section.get("section_id") or "")
        for section in (payload.get("sections") or [])
        if isinstance(section, dict)
    ]
    if generated_sections != planned_sections:
        raise BookFullManuscriptReview4228Error(
            f"{chapter_id} sections {generated_sections} ≠ plan {planned_sections}. STOP."
        )
    markdown = spec["markdown_path"].read_text(encoding="utf-8")
    parsed_md = parse_markdown_document(markdown)
    json_title = str(payload.get("title") or "")
    if json_title != planned.working_title:
        raise BookFullManuscriptReview4228Error(
            f"{chapter_id} JSON title {json_title!r} ≠ plan {planned.working_title!r}. STOP."
        )
    if parsed_md["title"] != json_title:
        raise BookFullManuscriptReview4228Error(
            f"{chapter_id} Markdown title drifted from JSON. STOP."
        )
    json_paragraphs = _paragraphs_from_chapter_payload(payload)
    md_paragraphs: list[str] = []
    md_section_titles: list[str] = []
    for section in parsed_md["sections"]:
        md_section_titles.append(section["title"])
        md_paragraphs.extend(section["paragraphs"])
    json_section_titles = [
        str(section.get("title") or "")
        for section in (payload.get("sections") or [])
        if isinstance(section, dict)
    ]
    if md_section_titles != json_section_titles:
        raise BookFullManuscriptReview4228Error(
            f"{chapter_id} Markdown section titles drifted from JSON. STOP."
        )
    json_texts = [row["text"] for row in json_paragraphs]
    if md_paragraphs != json_texts:
        raise BookFullManuscriptReview4228Error(
            f"{chapter_id} Markdown paragraphs drifted from JSON. STOP."
        )
    if any(not str(text).strip() for text in json_texts):
        raise BookFullManuscriptReview4228Error(
            f"{chapter_id} contains an unexpected empty paragraph. STOP."
        )
    sidecar = _sidecar_dir(spec)
    structural = _load_optional_json(sidecar / "structural_validation.json")
    idea_review = _load_optional_json(sidecar / "idea_traceability_review.json")
    if idea_review is None and chapter_id == "CH002":
        idea_review = _load_optional_json(historical_rel(CH002_IDEA_REVIEW_REL))
    ch012_mapping = (
        _load_optional_json(historical_rel(CH012_IDEA_MAPPING_REL))
        if chapter_id == "CH012"
        else None
    )
    ex_ref = _load_optional_json(sidecar / "ex_ref_traceability_review.json")
    editorial = _load_optional_json(sidecar / "editorial_readiness_review.json")
    structural_status = str((structural or {}).get("status") or "")
    if structural and structural_status != "PASS":
        raise BookFullManuscriptReview4228Error(
            f"{chapter_id} structural validation is {structural_status!r}. STOP."
        )
    found_ideas = _idea_ids_from_chapter(payload)
    if ch012_mapping:
        expected_ideas = list(ch012_mapping.get("ideas_planned") or planned_ideas)
        covered_ideas = list(ch012_mapping.get("content_supported") or expected_ideas)
        missing = list(ch012_mapping.get("not_supported") or [])
        if missing:
            raise BookFullManuscriptReview4228Error(
                f"CH012 4B.2.19 mapping lists unsupported IDEA ids: {missing}. STOP."
            )
        idea_review_path = _rel(historical_rel(CH012_IDEA_MAPPING_REL))
        idea_contract = "ch012-idea-content-mapping-4b219-1.0"
    elif idea_review:
        expected_from_review = list(idea_review.get("ideas_expected") or planned_ideas)
        found_from_review = list(idea_review.get("ideas_found_in_paras_e") or found_ideas)
        missing = list(idea_review.get("ideas_missing_from_paras_e") or [])
        if missing:
            raise BookFullManuscriptReview4228Error(
                f"{chapter_id} IDEA coverage is incomplete: {missing}. STOP."
            )
        expected_ideas = expected_from_review
        covered_ideas = found_from_review
        idea_review_path = _rel(
            sidecar / "idea_traceability_review.json"
            if (sidecar / "idea_traceability_review.json").is_file()
            else historical_rel(CH002_IDEA_REVIEW_REL)
        )
        idea_contract = "idea_traceability_review"
    else:
        missing = [idea_id for idea_id in planned_ideas if idea_id not in set(found_ideas)]
        if missing:
            raise BookFullManuscriptReview4228Error(
                f"{chapter_id} planned IDEA handles are absent: {missing}. STOP."
            )
        expected_ideas = planned_ideas
        covered_ideas = found_ideas
        idea_review_path = ""
        idea_contract = "json_handles_versus_plan"
    manifest_path = spec.get("manifest_path")
    manifest = _load_optional_json(manifest_path) if manifest_path else None
    if chapter_id in ACCEPTED_CHAPTER_IDS:
        if manifest is None:
            raise BookFullManuscriptReview4228Error(
                f"{chapter_id} acceptance manifest is missing. STOP."
            )
        status = str(
            manifest.get("status")
            or (manifest.get("human_acceptance") or {}).get("status")
            or ""
        )
        if status not in {HUMAN_ACCEPTANCE_STATUS, "accepted", "HUMAN_EDITORIALLY_ACCEPTED"}:
            raise BookFullManuscriptReview4228Error(
                f"{chapter_id} acceptance manifest status is {status!r}. STOP."
            )
    return {
        "chapter_id": chapter_id,
        "book_order": book_order,
        "title": json_title,
        "working_title": planned.working_title,
        "purpose": planned.purpose,
        "summary": planned.summary,
        "json_path": _rel(spec["json_path"]),
        "markdown_path": _rel(spec["markdown_path"]),
        "manifest_path": _rel(manifest_path) if manifest_path else "",
        "json_sha256": json_hash["sha256"],
        "markdown_sha256": md_hash["sha256"],
        "json_bytes": json_hash["bytes"],
        "markdown_bytes": md_hash["bytes"],
        "approved_version": spec["approved_version"],
        "status": spec["status"],
        "human_status_exact": spec["human_status_exact"],
        "accepted": chapter_id in ACCEPTED_CHAPTER_IDS,
        "pending_human_review": chapter_id in PENDING_CHAPTER_IDS,
        "section_ids": generated_sections,
        "section_titles": json_section_titles,
        "section_count": len(generated_sections),
        "paragraphs": json_paragraphs,
        "paragraph_count": len(json_paragraphs),
        "planned_idea_ids": planned_ideas,
        "expected_idea_ids": expected_ideas,
        "covered_idea_ids": covered_ideas,
        "idea_expected_count": len(expected_ideas),
        "idea_covered_count": len(set(covered_ideas)),
        "structural_status": structural_status or "VERIFIED_AGAINST_PLAN",
        "structural_validation_path": _rel(sidecar / "structural_validation.json")
        if structural
        else "",
        "idea_review_path": idea_review_path,
        "idea_contract": idea_contract,
        "ex_ref_review_path": _rel(sidecar / "ex_ref_traceability_review.json")
        if ex_ref
        else "",
        "editorial_review_path": _rel(sidecar / "editorial_readiness_review.json")
        if editorial
        else "",
        "json_markdown_consistent": True,
        "forbidden_historical_version_used": False,
        "modified_by_this_phase": False,
        "secrets_included": False,
    }


def _paragraphs_from_chapter_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return _paragraphs_from_json(payload)


def build_chapters_inventory(
    *,
    corpus: CanonicalCorpus | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    corpus = corpus or load_canonical_corpus()
    planned_ids = tuple(chapter.chapter_id for chapter in corpus.plan.chapters)
    if planned_ids != CANONICAL_CHAPTER_IDS:
        raise BookFullManuscriptReview4228Error(
            f"EditorialPlan order {planned_ids} ≠ {CANONICAL_CHAPTER_IDS}. STOP."
        )
    rows = [
        inspect_chapter(chapter_id, corpus=corpus, book_order=index + 1, root=root)
        for index, chapter_id in enumerate(planned_ids)
    ]
    ids = [row["chapter_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise BookFullManuscriptReview4228Error("Duplicate chapter identifiers. STOP.")
    if ids != list(CANONICAL_CHAPTER_IDS):
        raise BookFullManuscriptReview4228Error("Chapter inventory order drifted. STOP.")
    missing_accepted = [item for item in ACCEPTED_CHAPTER_IDS if item not in ids]
    if missing_accepted:
        raise BookFullManuscriptReview4228Error(
            f"Accepted chapters missing: {missing_accepted}. STOP."
        )
    section_count = sum(row["section_count"] for row in rows)
    idea_ids: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for idea_id in row["covered_idea_ids"]:
            if idea_id not in seen:
                seen.add(idea_id)
                idea_ids.append(idea_id)
    if section_count != EXPECTED_SECTION_COUNT:
        raise BookFullManuscriptReview4228Error(
            f"Section count {section_count} ≠ {EXPECTED_SECTION_COUNT}. STOP."
        )
    if len(idea_ids) != EXPECTED_IDEA_COUNT:
        raise BookFullManuscriptReview4228Error(
            f"IDEA coverage {len(idea_ids)} ≠ {EXPECTED_IDEA_COUNT}. STOP."
        )
    ch002 = next(row for row in rows if row["chapter_id"] == "CH002")
    if CH002_ORIGINAL_JSON_REL.replace("\\", "/") in ch002["json_path"].replace("\\", "/"):
        raise BookFullManuscriptReview4228Error("CH002 original failed candidate was selected. STOP.")
    ch012 = next(row for row in rows if row["chapter_id"] == "CH012")
    if CH012_ORIGINAL_JSON_REL.replace("\\", "/") in ch012["json_path"].replace("\\", "/"):
        raise BookFullManuscriptReview4228Error("CH012 pre-voice-correction candidate was selected. STOP.")
    accepted = [row for row in rows if row["accepted"]]
    pending = [row for row in rows if row["pending_human_review"]]
    return {
        "phase": PHASE,
        "project": corpus.plan.project_name,
        "selected_title": corpus.plan.selected_title,
        "subtitle": corpus.plan.subtitle,
        "title_source": "EditorialPlan.selected_title",
        "title_invented_by_this_phase": False,
        "canonical_order": list(CANONICAL_CHAPTER_IDS),
        "order_matches_editorial_plan": True,
        "duplicate_chapter_ids": [],
        "missing_chapter_ids": [],
        "chapter_count": len(rows),
        "accepted_chapter_ids": [row["chapter_id"] for row in accepted],
        "pending_chapter_ids": [row["chapter_id"] for row in pending],
        "accepted_count": len(accepted),
        "human_review_pending_count": len(pending),
        "section_count": section_count,
        "idea_coverage_count": len(idea_ids),
        "idea_ids": idea_ids,
        "ch002_recovered_used": True,
        "ch012_authorial_v2_used": True,
        "ch018_accepted_used": True,
        "thirteen_candidates_not_treated_as_approved": True,
        "chapters": rows,
        "secrets_included": False,
    }


__all__ = [
    "build_chapters_inventory",
    "inspect_chapter",
    "parse_markdown_document",
]
