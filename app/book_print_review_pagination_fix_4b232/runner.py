"""
Runner Phase 4B.2.32.

Regenerate the print-review interior with next-page chapter starts.
Preserve print-review-v1. Publish print-review-v1.1 only.
Zero provider calls. Zero book.json mutation.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.ai.provider_preflight import redact_secrets
from app.book_print_review_pagination_fix_4b232.constants import (
    AUTHORIZATION_SCOPE,
    BOOK_TITLE,
    CANONICAL_PYTHON,
    CHAPTER_BREAK_POLICY,
    EXPECTED_BOOK_SHA256,
    EXPECTED_CHAPTER_COUNT,
    EXPECTED_PARAGRAPH_COUNT,
    EXPECTED_SECTION_COUNT,
    EXPECTED_TRANSITION_COUNT,
    NEXT_ACTION_FAIL,
    NEXT_ACTION_PARTIAL,
    NEXT_ACTION_PASS,
    ORIGINAL_INTERCHAPTER_BLANK_PAGES,
    ORIGINAL_PDF_PAGE_COUNT,
    OUTPUT_VERSION,
    PHASE,
    PRINT_FORMAT,
    SOURCE_VERSION,
)
from app.book_print_review_pagination_fix_4b232.generation import (
    build_docx_bytes,
    generation_manifest,
    write_docx_bytes,
)
from app.book_print_review_pagination_fix_4b232.guard import (
    BookPrintReviewPaginationFix4232Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_print_review_pagination_fix_4b232.hashes import (
    assert_book_hash,
    assert_originals_preserved,
    assert_sources_unchanged,
    file_sha256,
    hashes_match,
    originals_match,
    snapshot,
    snapshot_original_publication,
)
from app.book_print_review_pagination_fix_4b232.integrity import validate_docx_integrity
from app.book_print_review_pagination_fix_4b232.paths import (
    official_docx_path,
    official_pdf_path,
    official_v1_docx_path,
    repo_root,
    unfinalized_docx_path,
    venv_python_path,
    working_docx_path,
)
from app.book_print_review_pagination_fix_4b232.pdf_integrity import (
    validate_pdf_integrity,
    validate_toc,
)
from app.book_print_review_pagination_fix_4b232.preflight import build_preflight
from app.book_print_review_pagination_fix_4b232.publication import publish_print_review
from app.book_print_review_pagination_fix_4b232.report import render_report
from app.book_print_review_pagination_fix_4b232.scenarios import evaluate_offline_scenarios
from app.book_print_review_pagination_fix_4b232.transitions import (
    compare_front_matter,
    policy_before_after,
    validate_transitions,
)
from app.book_print_review_pagination_fix_4b232.word_inspect import inspect_word_document
from app.book_print_review_pagination_fix_4b232.writer import write_phase_artifacts
from app.word_renderer.finalizer import detect_word_environment, finalize_word_document


@dataclass
class PhaseResult:
    accepted: bool
    mode: str
    bundle: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _first_chapter_page(inspection: dict[str, Any], finalization: dict[str, Any]) -> int | None:
    chapters = list(inspection.get("chapters") or [])
    if chapters and chapters[0].get("first_page"):
        return int(chapters[0]["first_page"])
    starts = list(finalization.get("chapter_starts") or [])
    if starts and starts[0].get("page"):
        return int(starts[0]["page"])
    return None


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = ["app/tests/test_book_print_review_pagination_fix_4b232.py"]
    python = str(venv_python_path(root=root))
    completed = subprocess.run(
        [python, "-m", "pytest", "-q", "--tb=line", *tests],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = completed.stdout or ""
    summary = next(
        (
            line.strip()
            for line in reversed((stdout + "\n" + (completed.stderr or "")).splitlines())
            if "passed" in line or "failed" in line or "skipped" in line
        ),
        "",
    )
    passed_match = re.search(r"(\d+) passed", summary)
    failed_match = re.search(r"(\d+) failed", summary)
    return {
        "returncode": completed.returncode,
        "summary": summary,
        "passed": int(passed_match.group(1)) if passed_match else 0,
        "failed": int(failed_match.group(1))
        if failed_match
        else (0 if completed.returncode == 0 else 1),
        "stderr_tail": "\n".join((completed.stderr or "").strip().splitlines()[-12:]),
        "suites": tests,
        "real_provider_calls": 0,
        "phase": PHASE,
        "canonical_python": python,
    }


def run_phase(
    *,
    authorization_scope: str | None,
    write_artifacts: bool = True,
    run_tests: bool = True,
    finalize: bool = True,
    probe_word: bool = True,
    allow_official: bool | None = None,
    root: Path | None = None,
    word_backend=None,
) -> PhaseResult:
    result = PhaseResult(accepted=False, mode="OFFLINE")
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
    except BookPrintReviewPaginationFix4232Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    official = allow_official
    if official is None:
        official = write_artifacts and base.resolve() == repo_root().resolve()
    before = snapshot(root=base)
    original_before = snapshot_original_publication()
    try:
        assert_book_hash(before)
        preflight = build_preflight(root=base)
    except Exception as exc:
        after = snapshot(root=base)
        original_after = snapshot_original_publication()
        bundle = _blocked_bundle(before, after, original_before, original_after, str(exc))
        if write_artifacts:
            bundle["written"] = write_phase_artifacts(bundle, root=base)
            bundle["report_text"] = render_report(bundle)
            bundle["written"] = write_phase_artifacts(bundle, root=base)
        result.bundle = redact_secrets(bundle)
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    book = preflight["book"]
    profile = preflight["profile"]
    blob = build_docx_bytes(book, profile)
    integrity = validate_docx_integrity(blob, book, profile)
    unfinalized_info = {"path": "", "sha256": "", "bytes": 0, "exists": False}
    if write_artifacts or finalize:
        unfinalized_info = write_docx_bytes(unfinalized_docx_path(root=base), blob)

    environment = detect_word_environment(
        probe=bool(finalize and probe_word and word_backend is None),
        backend=word_backend,
    )
    pdf_working = working_docx_path(root=base).with_suffix(".pdf")
    if finalize and environment.get("word_available"):
        finalization = finalize_word_document(
            source_docx=unfinalized_docx_path(root=base),
            working_docx=working_docx_path(root=base),
            pdf_path=pdf_working,
            backend=word_backend,
        )
    elif finalize:
        finalization = finalize_word_document(
            source_docx=unfinalized_docx_path(root=base),
            working_docx=working_docx_path(root=base),
            pdf_path=None,
            backend=word_backend,
        )
    else:
        finalization = {
            "status": "NOT_STARTED",
            "executed": False,
            "fields_updated": False,
            "toc_updated": False,
            "pagination_stable": False,
            "pdf_exported": False,
            "environment": environment,
        }

    pdf_source = None
    if finalization.get("pdf_exported") and finalization.get("pdf_path"):
        candidate = Path(str(finalization["pdf_path"]))
        if candidate.is_file() and candidate.stat().st_size > 0:
            pdf_source = candidate
    publish_source = working_docx_path(root=base)
    if not publish_source.is_file():
        publish_source = unfinalized_docx_path(root=base)
    publication: dict[str, Any] = {"action": "not_published", "atomic": False}
    if write_artifacts and integrity["status"] == "PASS" and publish_source.is_file():
        publication = publish_print_review(
            finalized_docx=publish_source,
            pdf_path=pdf_source,
            destination_docx=official_docx_path(root=base),
            destination_pdf=official_pdf_path(root=base),
            allow_official=bool(official),
        )

    inspect_new = {"status": "NOT_STARTED", "pages": [], "chapters": []}
    inspect_old = {"status": "NOT_STARTED", "pages": [], "chapters": []}
    inspect_target = Path(publication.get("destination_docx") or "")
    if not inspect_target.is_file():
        inspect_target = publish_source
    if finalize and environment.get("word_available") and inspect_target.is_file():
        inspect_new = inspect_word_document(inspect_target)
        if official_v1_docx_path().is_file():
            inspect_old = inspect_word_document(official_v1_docx_path())

    tests = _tests_or_skip(run_tests, base)
    after = snapshot(root=base)
    original_after = snapshot_original_publication()
    hashes_ok = _hashes_ok(before, after, result)
    originals_ok = originals_match(original_before, original_after)
    try:
        assert_originals_preserved(original_before, original_after)
    except BookPrintReviewPaginationFix4232Error as exc:
        originals_ok = False
        result.error = str(exc)

    result_label, ready = _classify(
        integrity=integrity,
        finalization=finalization,
        hashes_ok=hashes_ok,
        originals_ok=originals_ok,
        tests=tests,
        transitions=validate_transitions(
            inspection=inspect_new,
            book=book,
            finalization=finalization,
        ),
        front=compare_front_matter(
            original=inspect_old,
            updated=inspect_new,
            original_chapter1_page=5,
            updated_chapter1_page=_first_chapter_page(inspect_new, finalization),
        ),
        toc=validate_toc(finalization, book),
        pdf=validate_pdf_integrity(
            Path(str((publication.get("pdf") or {}).get("path") or finalization.get("pdf_path") or ""))
            if ((publication.get("pdf") or {}).get("path") or finalization.get("pdf_path"))
            else None,
            book,
            finalization=finalization,
        ),
    )
    bundle = _assemble(
        preflight=preflight,
        unfinalized=unfinalized_info,
        integrity=integrity,
        environment=environment,
        finalization=finalization,
        publication=publication,
        tests=tests,
        hashes_ok=hashes_ok,
        originals_ok=originals_ok,
        original_before=original_before,
        original_after=original_after,
        before=before,
        after=after,
        inspect_new=inspect_new,
        inspect_old=inspect_old,
        result_label=result_label,
        ready=ready,
        official_docx=publication.get("destination_docx") or "",
        official_pdf=(publication.get("pdf") or {}).get("path") or "",
    )
    if write_artifacts:
        bundle["written"] = write_phase_artifacts(bundle, root=base)
        bundle["report_text"] = render_report(bundle)
        bundle["written"] = write_phase_artifacts(bundle, root=base)
    result.bundle = redact_secrets(bundle)
    result.accepted = result_label == "PASS"
    result.mode = result_label
    result.error = "" if result_label == "PASS" else (result.error or result_label)
    return result


def _tests_or_skip(run_tests: bool, base: Path) -> dict[str, Any]:
    if run_tests:
        return _run_focused_tests(root=base)
    return {
        "returncode": 0,
        "summary": "skipped",
        "passed": 0,
        "failed": 0,
        "suites": [],
        "real_provider_calls": 0,
    }


def _hashes_ok(before: dict[str, Any], after: dict[str, Any], result: PhaseResult) -> bool:
    ok = hashes_match(before, after)
    try:
        assert_sources_unchanged(before, after)
    except BookPrintReviewPaginationFix4232Error as exc:
        ok = False
        result.error = str(exc)
    return ok


def _classify(
    *,
    integrity: dict[str, Any],
    finalization: dict[str, Any],
    hashes_ok: bool,
    originals_ok: bool,
    tests: dict[str, Any],
    transitions: dict[str, Any],
    front: dict[str, Any],
    toc: dict[str, Any],
    pdf: dict[str, Any],
) -> tuple[str, bool]:
    if integrity["status"] != "PASS" or not hashes_ok or not originals_ok:
        return "FAIL", False
    if int(tests.get("failed") or 0) > 0:
        return "FAIL", False
    word_pass = finalization.get("status") == "PASS" and finalization.get("toc_updated")
    if (
        word_pass
        and pdf.get("status") == "PASS"
        and finalization.get("pagination_stable")
        and toc.get("status") == "PASS"
        and transitions.get("status") == "PASS"
        and front.get("front_matter_unchanged") == "YES"
    ):
        return "PASS", True
    return "PARTIAL", False


def _blocked_bundle(
    before: dict[str, Any],
    after: dict[str, Any],
    original_before: dict[str, Any],
    original_after: dict[str, Any],
    error: str,
) -> dict[str, Any]:
    header = {
        "result": "BLOCKED",
        "book_title": BOOK_TITLE,
        "book_canonical_sha256": EXPECTED_BOOK_SHA256,
        "source_version": SOURCE_VERSION,
        "output_version": OUTPUT_VERSION,
        "page_format": PRINT_FORMAT,
        "chapter_break_policy": CHAPTER_BREAK_POLICY,
        "front_matter_unchanged": "NO",
        "chapters": f"0 / {EXPECTED_CHAPTER_COUNT}",
        "sections": f"0 / {EXPECTED_SECTION_COUNT}",
        "paragraphs": f"0 / {EXPECTED_PARAGRAPH_COUNT}",
        "chapter_transitions_checked": f"0 / {EXPECTED_TRANSITION_COUNT}",
        "unnecessary_interchapter_blank_pages": f"0 / {ORIGINAL_INTERCHAPTER_BLANK_PAGES}",
        "toc_updated": "NO",
        "pagination_stable": "NO",
        "original_pdf_page_count": ORIGINAL_PDF_PAGE_COUNT,
        "new_pdf_page_count": "",
        "docx_integrity": "FAIL",
        "pdf_integrity": "FAIL",
        "canonical_hashes_pre_post": "MATCH" if hashes_match(before, after) else "MISMATCH",
        "original_files_preserved": _yn(originals_match(original_before, original_after)),
        "ready_for_print_review": "NO",
        "issues": f"- {error}",
        "pytest_summary": "not run",
        "scenario_summary": "not run",
        "next_action": NEXT_ACTION_FAIL,
        "authorization_scope": AUTHORIZATION_SCOPE,
    }
    bundle = {
        "header": header,
        "canonical_hashes_pre_post": {
            "phase": PHASE,
            "pre": before,
            "post": after,
            "match": hashes_match(before, after),
            "status": "MATCH" if hashes_match(before, after) else "MISMATCH",
            "original_publication_pre": original_before,
            "original_publication_post": original_after,
            "originals_preserved": originals_match(original_before, original_after),
        },
    }
    bundle["report_text"] = render_report(bundle)
    return bundle


def _assemble(
    *,
    preflight: dict[str, Any],
    unfinalized: dict[str, Any],
    integrity: dict[str, Any],
    environment: dict[str, Any],
    finalization: dict[str, Any],
    publication: dict[str, Any],
    tests: dict[str, Any],
    hashes_ok: bool,
    originals_ok: bool,
    original_before: dict[str, Any],
    original_after: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    inspect_new: dict[str, Any],
    inspect_old: dict[str, Any],
    result_label: str,
    ready: bool,
    official_docx: str,
    official_pdf: str,
) -> dict[str, Any]:
    book = preflight["book"]
    profile = preflight["profile"]
    toc = validate_toc(finalization, book)
    transitions = validate_transitions(
        inspection=inspect_new,
        book=book,
        finalization=finalization,
    )
    front = compare_front_matter(
        original=inspect_old,
        updated=inspect_new,
        original_chapter1_page=5,
        updated_chapter1_page=_first_chapter_page(inspect_new, finalization),
    )
    pdf_path = official_pdf or finalization.get("pdf_path") or ""
    pdf_file = Path(pdf_path) if pdf_path else None
    pdf = validate_pdf_integrity(pdf_file, book, finalization=finalization)
    policy = policy_before_after(profile)
    scenarios = evaluate_offline_scenarios(
        bundle={
            "docx_integrity_validation": integrity,
            "chapter_transition_validation": transitions,
            "front_matter_comparison": front,
            "toc_pagination_validation": toc,
            "pdf_integrity_validation": pdf,
            "publication_manifest": publication,
            "canonical_hashes_pre_post": {"status": "MATCH" if hashes_ok else "MISMATCH"},
        },
        hashes_ok=hashes_ok,
        originals_ok=originals_ok,
        tests=tests,
    )
    next_action = {
        "PASS": NEXT_ACTION_PASS,
        "PARTIAL": NEXT_ACTION_PARTIAL,
        "FAIL": NEXT_ACTION_FAIL,
        "BLOCKED": NEXT_ACTION_FAIL,
    }[result_label]
    issues = []
    if integrity["status"] != "PASS":
        failed = [name for name, ok in (integrity.get("checks") or {}).items() if not ok]
        issues.append("DOCX integrity failed: " + ", ".join(failed))
    if finalization.get("error"):
        issues.append(str(finalization["error"]))
    if transitions.get("status") == "FAIL" and int(transitions.get("unnecessary_blank_count") or 0):
        issues.append("One or more interchapter transitions still insert a blank page.")
    elif transitions.get("status") == "FAIL":
        issues.append("Interchapter transition validation failed.")
    if front.get("front_matter_unchanged") == "NO":
        issues.append("Front-matter presentation drifted from print-review-v1.")
    if not hashes_ok:
        issues.append("Canonical hashes changed.")
    if not originals_ok:
        issues.append("print-review-v1 files were modified.")
    if int(tests.get("failed") or 0):
        issues.append(f"pytest failures: {tests.get('summary')}")
    blank_count = int(transitions.get("unnecessary_blank_count") or 0)
    header = {
        "result": result_label,
        "provider_calls": 0,
        "book_title": BOOK_TITLE,
        "book_canonical_sha256": EXPECTED_BOOK_SHA256,
        "source_version": SOURCE_VERSION,
        "output_version": OUTPUT_VERSION,
        "page_format": PRINT_FORMAT,
        "chapter_break_policy": CHAPTER_BREAK_POLICY,
        "front_matter_unchanged": front.get("front_matter_unchanged") or "NO",
        "chapters": f"{integrity.get('chapter_count')} / {EXPECTED_CHAPTER_COUNT}",
        "sections": f"{integrity.get('section_count')} / {EXPECTED_SECTION_COUNT}",
        "paragraphs": f"{integrity.get('paragraph_count')} / {EXPECTED_PARAGRAPH_COUNT}",
        "chapter_transitions_checked": transitions.get("transitions_checked"),
        "unnecessary_interchapter_blank_pages": (
            f"{blank_count} / {ORIGINAL_INTERCHAPTER_BLANK_PAGES}"
        ),
        "toc_updated": _yn(bool(finalization.get("toc_updated"))),
        "pagination_stable": (
            "YES"
            if finalization.get("pagination_stable")
            else ("NOT_VERIFIED" if not finalization.get("executed") else "NO")
        ),
        "original_pdf_page_count": ORIGINAL_PDF_PAGE_COUNT,
        "new_pdf_page_count": pdf.get("page_count") if pdf.get("status") != "NOT_VERIFIED" else "",
        "docx_integrity": integrity.get("status"),
        "pdf_integrity": pdf.get("status"),
        "canonical_hashes_pre_post": "MATCH" if hashes_ok else "MISMATCH",
        "original_files_preserved": _yn(originals_ok),
        "ready_for_print_review": _yn(ready),
        "docx_path": official_docx or unfinalized.get("path") or "",
        "pdf_path": pdf_path,
        "docx_sha256": (file_sha256(Path(official_docx)) if official_docx else unfinalized).get(
            "sha256"
        )
        if official_docx or unfinalized
        else "",
        "authorization_scope": AUTHORIZATION_SCOPE,
        "pytest_summary": tests.get("summary") or "skipped",
        "scenario_summary": f"{scenarios.get('passed')} passed / {scenarios.get('failed')} failed",
        "issues": "- None." if not issues else "\n".join(f"- {item}" for item in issues),
        "next_action": next_action,
        "generation_manifest": generation_manifest(
            book=book,
            profile=profile,
            unfinalized=unfinalized,
            book_sha256=EXPECTED_BOOK_SHA256,
        ),
    }
    bundle = {
        "header": header,
        "chapter_break_policy_before_after": policy,
        "chapter_transition_validation": transitions,
        "front_matter_comparison": front,
        "docx_integrity_validation": integrity,
        "pdf_integrity_validation": pdf,
        "toc_pagination_validation": toc,
        "canonical_hashes_pre_post": {
            "phase": PHASE,
            "pre": before,
            "post": after,
            "match": hashes_ok,
            "status": "MATCH" if hashes_ok else "MISMATCH",
            "book_json_pre": before.get("book_json"),
            "book_json_post": after.get("book_json"),
            "expected_book_sha256": EXPECTED_BOOK_SHA256,
            "original_publication_pre": original_before,
            "original_publication_post": original_after,
            "originals_preserved": originals_ok,
            "secrets_included": False,
        },
        "publication_manifest": publication,
        "offline_tests": {"pytest": tests, "scenarios": scenarios},
        "word_environment_detection": environment,
        "word_finalization_report": finalization,
        "word_page_inspection": {
            "updated": {
                key: inspect_new.get(key)
                for key in ("status", "page_count", "path", "error")
            },
            "original": {
                key: inspect_old.get(key)
                for key in ("status", "page_count", "path", "error")
            },
        },
    }
    bundle["report_text"] = render_report(bundle)
    return bundle


__all__ = ["PhaseResult", "run_phase"]
