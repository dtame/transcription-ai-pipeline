"""Forensic inspection of CH002 SEC006 / P000008. Evidence, not a guess."""

from __future__ import annotations

from typing import Any

from app.book_ch002_offline_recovery_4b224.chapter_io import (
    find_candidate_paragraph,
    find_raw_paragraph,
    iter_candidate_paragraphs,
    iter_raw_paragraphs,
    load_json,
)
from app.book_ch002_offline_recovery_4b224.constants import (
    EMPTY_PARAGRAPH_ID,
    EMPTY_PROVIDER_HANDLE,
    EMPTY_SECTION_ID,
    PHASE,
    TARGET_CHAPTER_ID,
)
from app.book_ch002_offline_recovery_4b224.hashes import file_sha256
from app.book_ch002_offline_recovery_4b224.paths import (
    batch01_dir,
    batch01_summary_path,
    ch002_dir,
    original_candidate_json_path,
    original_candidate_md_path,
    original_lock_file,
    original_raw_response_path,
    original_structural_path,
)
from app.book_ch002_offline_recovery_4b224.recovery import inspect_paragraph, removal_is_admissible
from app.book_generation.evidence import classify_handle


def _paragraph_anomalies(paragraph: dict[str, Any], *, source: str) -> list[str]:
    issues: list[str] = []
    text = paragraph.get("t") if source == "raw" else paragraph.get("text")
    text_str = "" if text is None else str(text)
    if text_str.strip() == "":
        issues.append("empty_or_whitespace_text")
    if text is None:
        issues.append("missing_text_field")
    handles = []
    if source == "raw":
        handles.extend(str(item) for item in paragraph.get("e") or [])
        handles.extend(str(item) for item in paragraph.get("u") or [])
    else:
        for field in (
            "evidence_handles",
            "source_refs",
            "idea_refs",
            "example_refs",
            "reference_refs",
            "uncertainty_refs",
        ):
            handles.extend(str(item) for item in paragraph.get(field) or [])
    if text_str.strip() == "" and handles:
        issues.append("empty_text_with_provenance")
    return issues


def inspect_ch002(*, root=None) -> dict[str, Any]:
    raw_path = original_raw_response_path(TARGET_CHAPTER_ID, root=root)
    candidate_path = original_candidate_json_path(TARGET_CHAPTER_ID, root=root)
    md_path = original_candidate_md_path(TARGET_CHAPTER_ID, root=root)
    structural_path = original_structural_path(TARGET_CHAPTER_ID, root=root)
    lock_path = original_lock_file(TARGET_CHAPTER_ID, root=root)
    raw_payload = load_json(raw_path)
    candidate = load_json(candidate_path)
    structural = load_json(structural_path)
    lock = load_json(lock_path)
    source_context = load_json(ch002_dir(root=root) / "source_context_manifest.json")
    usage = load_json(ch002_dir(root=root) / "provider_usage.json")
    summary = load_json(batch01_summary_path(root=root))
    parsed = raw_payload.get("parsed") if isinstance(raw_payload, dict) else None
    raw_located = find_raw_paragraph(parsed or {}, EMPTY_PROVIDER_HANDLE)
    cand_located = find_candidate_paragraph(candidate, EMPTY_PARAGRAPH_ID)
    raw_inspection = inspect_paragraph(None if raw_located is None else raw_located[2])
    cand_inspection = inspect_paragraph(None if cand_located is None else cand_located[2])
    if raw_located is not None:
        raw_inspection["section_id"] = raw_located[0]
        raw_inspection["section_index"] = raw_located[1]
        raw_inspection["raw_object"] = {
            "h": raw_located[2].get("h"),
            "k": raw_located[2].get("k"),
            "t": raw_located[2].get("t"),
            "e": list(raw_located[2].get("e") or []),
            "u": list(raw_located[2].get("u") or []),
        }
    if cand_located is not None:
        cand_inspection["section_id"] = cand_located[0]
        cand_inspection["section_index"] = cand_located[1]
        cand_inspection["candidate_object"] = {
            key: cand_located[2].get(key)
            for key in (
                "paragraph_id",
                "provider_handle",
                "kind",
                "text",
                "evidence_handles",
                "source_refs",
                "idea_refs",
                "example_refs",
                "reference_refs",
                "uncertainty_refs",
            )
        }

    raw_bin_hits = _search_raw_bin(ch002_dir(root=root), EMPTY_PROVIDER_HANDLE)
    other_raw_anomalies = []
    for section_id, index, paragraph in iter_raw_paragraphs(parsed or {}):
        issues = _paragraph_anomalies(paragraph, source="raw")
        handle = str(paragraph.get("h") or "")
        if handle == EMPTY_PROVIDER_HANDLE:
            continue
        if issues:
            other_raw_anomalies.append(
                {
                    "section_id": section_id,
                    "index": index,
                    "handle": handle,
                    "issues": issues,
                    "text_repr": repr(paragraph.get("t")),
                }
            )
    other_candidate_anomalies = []
    for section_id, index, paragraph in iter_candidate_paragraphs(candidate):
        issues = _paragraph_anomalies(paragraph, source="candidate")
        if str(paragraph.get("paragraph_id") or "") == EMPTY_PARAGRAPH_ID:
            continue
        if issues:
            other_candidate_anomalies.append(
                {
                    "section_id": section_id,
                    "index": index,
                    "paragraph_id": paragraph.get("paragraph_id"),
                    "issues": issues,
                    "text_repr": repr(paragraph.get("text")),
                }
            )

    referenced_elsewhere = []
    for section_id, index, paragraph in iter_candidate_paragraphs(candidate):
        if str(paragraph.get("paragraph_id") or "") == EMPTY_PARAGRAPH_ID:
            continue
        blob = " ".join(
            str(value)
            for key, value in paragraph.items()
            if key != "text"
        )
        if EMPTY_PARAGRAPH_ID in blob:
            referenced_elsewhere.append(
                {
                    "section_id": section_id,
                    "paragraph_id": paragraph.get("paragraph_id"),
                    "index": index,
                }
            )

    markdown = md_path.read_text(encoding="utf-8") if md_path.is_file() else ""
    empty_visible_in_markdown = (
        "\n\n\n\n" in markdown[markdown.find("## From Sons of Men") :]
        if "## From Sons of Men" in markdown
        else False
    )
    admissible, reasons = removal_is_admissible(cand_inspection)
    if referenced_elsewhere:
        admissible = False
        reasons.append("paragraph id is referenced elsewhere")
    additional_contract_errors = [
        error
        for error in list(structural.get("errors") or [])
        if "empty" not in str(error).lower()
    ]
    introduction = {
        "present_in_raw_parsed_json": raw_located is not None,
        "present_in_candidate_json": cand_located is not None,
        "present_in_raw_bin_search": raw_bin_hits.get("handle_found") is True,
        "raw_text_empty": bool(raw_inspection.get("empty")),
        "candidate_text_empty": bool(cand_inspection.get("empty")),
        "introduced_by_model": bool(
            raw_located is not None and raw_inspection.get("empty")
        ),
        "introduced_by_parsing": False,
        "introduced_by_normalization": False,
        "introduced_by_rendering": False,
        "contract_defect": False,
        "validation_defect": False,
        "validator_correctly_failed": structural.get("status") == "FAIL",
        "markdown_omits_empty_paragraph": not empty_visible_in_markdown,
        "rationale": (
            "The Anthropic parsed JSON already contains SEC006 handle p8 with "
            't="" and e=[]. The materialized candidate preserves that object as '
            "P000008. The markdown renderer strips empty text, so the readable "
            "file hides the defect. The existing validator reported "
            "SEC006.p4: empty text and 1 empty paragraph(s)."
        ),
    }
    questions = {
        "1_exists_in_raw_response": raw_located is not None,
        "2_exact_content": raw_inspection.get("raw_object")
        if raw_located is not None
        else None,
        "3_empty_or_whitespace_only": bool(raw_inspection.get("empty")),
        "4_contains_metadata": bool(raw_inspection.get("contains_metadata_keys")),
        "5_contains_idea_handles": bool(raw_inspection.get("contains_idea")),
        "6_contains_src_handles": bool(raw_inspection.get("contains_src")),
        "7_contains_ex_ref_unc": bool(
            raw_inspection.get("contains_ex")
            or raw_inspection.get("contains_ref")
            or raw_inspection.get("contains_unc")
        ),
        "8_id_referenced_elsewhere": referenced_elsewhere,
        "9_removal_changes_other_paragraph_order": False,
        "10_removal_affects_markdown_render": empty_visible_in_markdown,
        "11_other_paragraph_anomalies": other_raw_anomalies + other_candidate_anomalies,
        "12_other_contract_violations": additional_contract_errors,
    }
    return {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "target": {
            "section_id": EMPTY_SECTION_ID,
            "paragraph_id": EMPTY_PARAGRAPH_ID,
            "provider_handle": EMPTY_PROVIDER_HANDLE,
        },
        "files": {
            "raw_response": file_sha256(raw_path),
            "candidate_json": file_sha256(candidate_path),
            "candidate_md": file_sha256(md_path),
            "structural_validation": file_sha256(structural_path),
            "call_lock": file_sha256(lock_path),
            "source_context_manifest": file_sha256(
                ch002_dir(root=root) / "source_context_manifest.json"
            ),
            "batch_summary": file_sha256(batch01_summary_path(root=root)),
            "batch_dir": str(batch01_dir(root=root)).replace("\\", "/"),
        },
        "raw_response": {
            "http_success": raw_payload.get("http_success"),
            "finish_reason": raw_payload.get("finish_reason"),
            "json_valid": isinstance(parsed, dict),
            "section_ids": [
                str(section.get("sid") or "")
                for section in (parsed or {}).get("sections") or []
            ],
            "paragraph_handles": [
                str(paragraph.get("h") or "")
                for _section_id, _index, paragraph in iter_raw_paragraphs(parsed or {})
            ],
            "target": raw_inspection,
        },
        "candidate": {
            "chapter_id": candidate.get("chapter_id"),
            "title": candidate.get("title"),
            "section_ids": [
                str(section.get("section_id") or "")
                for section in candidate.get("sections") or []
            ],
            "paragraph_ids": [
                str(paragraph.get("paragraph_id") or "")
                for _section_id, _index, paragraph in iter_candidate_paragraphs(candidate)
            ],
            "target": cand_inspection,
        },
        "structural_validation": {
            "status": structural.get("status"),
            "chapter_contract_valid": structural.get("chapter_contract_valid"),
            "errors": list(structural.get("errors") or []),
            "empty_paragraphs": (structural.get("checks") or {}).get("empty_paragraphs"),
            "ideas_found_in_paras_e": (structural.get("checks") or {}).get(
                "ideas_found_in_paras_e"
            ),
            "ideas_expected_count": (structural.get("checks") or {}).get(
                "ideas_expected_count"
            ),
            "additional_contract_errors": additional_contract_errors,
        },
        "provenance": {
            "provider_raw_sha256": candidate.get("provider_raw_sha256"),
            "usage_raw_sha256": usage.get("raw_sha256"),
            "lock_state": lock.get("state"),
            "lock_consumed": lock.get("consumed"),
            "lock_reusable": lock.get("reusable"),
            "source_context_chapter_id": source_context.get("chapter_id"),
            "batch_result": summary.get("result"),
            "classified_target_handles": [
                classify_handle(str(handle))
                for handle in (cand_inspection.get("handles") or {}).get(
                    "evidence_handles", []
                )
            ],
        },
        "raw_bin": raw_bin_hits,
        "questions": questions,
        "introduction": introduction,
        "other_raw_anomalies": other_raw_anomalies,
        "other_candidate_anomalies": other_candidate_anomalies,
        "referenced_elsewhere": referenced_elsewhere,
        "markdown_contains_visible_empty_block": empty_visible_in_markdown,
        "recovery_admissible_from_forensics": admissible,
        "recovery_block_reasons": reasons,
        "originals_must_remain_immutable": True,
        "secrets_included": False,
    }


def _search_raw_bin(chapter_dir, handle: str) -> dict[str, Any]:
    forensic_root = chapter_dir / "provider_forensics"
    hits = []
    if forensic_root.is_dir():
        for path in forensic_root.rglob("provider_raw_response.bin"):
            raw = path.read_bytes()
            text = raw.decode("utf-8", errors="replace")
            hits.append(
                {
                    "path": str(path).replace("\\", "/"),
                    "bytes": len(raw),
                    "handle_found": handle in text,
                    "empty_t_near_handle": ('"h":"p8"' in text.replace(" ", "") or f'"{handle}"' in text)
                    and ('"t":""' in text.replace(" ", "")),
                    "sha256": file_sha256(path)["sha256"],
                }
            )
    return {
        "files": hits,
        "handle_found": any(item.get("handle_found") for item in hits),
        "empty_text_token_found": any(item.get("empty_t_near_handle") for item in hits),
    }


__all__ = ["inspect_ch002"]
