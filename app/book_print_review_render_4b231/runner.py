"""
Runner Phase 4B.2.31.

Generate the print-review DOCX from book.json. Finalize with Microsoft Word
when available. Export PDF only after a real Word pass. Zero provider calls.
Zero book.json mutation.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.ai.provider_preflight import redact_secrets
from app.book_print_review_render_4b231.constants import (
    AUTHORIZATION_SCOPE,
    BOOK_STATUS,
    BOOK_TITLE,
    BOOK_VERSION,
    CANONICAL_PYTHON,
    EXPECTED_BOOK_SHA256,
    EXPECTED_CHAPTER_COUNT,
    EXPECTED_PARAGRAPH_COUNT,
    EXPECTED_SECTION_COUNT,
    NEXT_ACTION_FAIL,
    NEXT_ACTION_PARTIAL,
    NEXT_ACTION_PASS,
    PHASE,
    PRINT_FORMAT,
    PRINT_PROFILE,
    PUBLICATION_STATUS,
)
from app.book_print_review_render_4b231.generation import (
    build_docx_bytes,
    generation_manifest,
    write_docx_bytes,
)
from app.book_print_review_render_4b231.guard import (
    BookPrintReviewRender4231Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_print_review_render_4b231.hashes import (
    assert_book_hash,
    assert_sources_unchanged,
    file_sha256,
    hashes_match,
    snapshot,
)
from app.book_print_review_render_4b231.integrity import validate_docx_integrity
from app.book_print_review_render_4b231.paths import (
    official_docx_path,
    official_pdf_path,
    repo_root,
    unfinalized_docx_path,
    venv_python_path,
    working_docx_path,
)
from app.book_print_review_render_4b231.pdf_validation import (
    validate_pagination,
    validate_pdf_content,
    validate_pdf_export,
    validate_pdf_geometry,
    validate_toc,
    visual_inspection_report,
)
from app.book_print_review_render_4b231.preflight import build_preflight
from app.book_print_review_render_4b231.publication import publish_print_review
from app.book_print_review_render_4b231.report import render_report
from app.book_print_review_render_4b231.scenarios import evaluate_offline_scenarios
from app.book_print_review_render_4b231.writer import write_phase_artifacts
from app.word_renderer.finalizer import detect_word_environment, finalize_word_document


@dataclass
class PhaseResult:
    accepted: bool
    mode: str
    bundle: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = ["app/tests/test_book_print_review_render_4b231.py"]
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
        "openai_http_requests": 0,
        "anthropic_http_requests": 0,
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
    except BookPrintReviewRender4231Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    official = allow_official
    if official is None:
        official = write_artifacts and base.resolve() == repo_root().resolve()
    before = snapshot(root=base)
    try:
        assert_book_hash(before)
        preflight = build_preflight(root=base)
    except Exception as exc:
        after = snapshot(root=base)
        bundle = _blocked_bundle(before, after, str(exc))
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
    mapping = integrity.pop("mapping")
    unfinalized_info = {"path": "", "sha256": "", "bytes": 0, "exists": False}
    if write_artifacts or finalize:
        unfinalized_info = write_docx_bytes(unfinalized_docx_path(root=base), blob)

    if integrity["status"] != "PASS":
        environment = detect_word_environment(probe=False, backend=word_backend)
        finalization = {
            "status": "NOT_STARTED",
            "executed": False,
            "error": "DOCX integrity failed. Finalization refused.",
            "required_human_action": NEXT_ACTION_FAIL,
        }
        tests = _tests_or_skip(run_tests, base)
        after = snapshot(root=base)
        hashes_ok = _hashes_ok(before, after, result)
        bundle = _assemble(
            preflight=preflight,
            unfinalized=unfinalized_info,
            integrity=integrity,
            mapping=mapping,
            environment=environment,
            finalization=finalization,
            publication={"action": "not_published", "atomic": False},
            tests=tests,
            hashes_ok=hashes_ok,
            before=before,
            after=after,
            result_label="FAIL",
            ready=False,
            official_docx="",
            official_pdf="",
        )
        if write_artifacts:
            bundle["written"] = write_phase_artifacts(bundle, root=base)
            bundle["report_text"] = render_report(bundle)
            bundle["written"] = write_phase_artifacts(bundle, root=base)
        result.bundle = redact_secrets(bundle)
        result.mode = "FAIL"
        result.error = "DOCX content integrity failed"
        return result

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

    tests = _tests_or_skip(run_tests, base)
    after = snapshot(root=base)
    hashes_ok = _hashes_ok(before, after, result)
    pdf_preview = None
    if (publication.get("pdf") or {}).get("path"):
        pdf_preview = Path(str(publication["pdf"]["path"]))
    elif finalization.get("pdf_path"):
        pdf_preview = Path(str(finalization["pdf_path"]))
    pdf_content_preview = validate_pdf_content(pdf_preview, book)
    result_label, ready = _classify(
        integrity=integrity,
        finalization=finalization,
        publication=publication,
        hashes_ok=hashes_ok,
        tests=tests,
        pdf_content=pdf_content_preview,
    )
    bundle = _assemble(
        preflight=preflight,
        unfinalized=unfinalized_info,
        integrity=integrity,
        mapping=mapping,
        environment=environment,
        finalization=finalization,
        publication=publication,
        tests=tests,
        hashes_ok=hashes_ok,
        before=before,
        after=after,
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
    result.error = "" if result_label == "PASS" else result_label
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
    except BookPrintReviewRender4231Error as exc:
        ok = False
        result.error = str(exc)
    return ok


def _classify(
    *,
    integrity: dict[str, Any],
    finalization: dict[str, Any],
    publication: dict[str, Any],
    hashes_ok: bool,
    tests: dict[str, Any],
    pdf_content: dict[str, Any] | None = None,
) -> tuple[str, bool]:
    if integrity["status"] != "PASS" or not hashes_ok:
        return "FAIL", False
    if int(tests.get("failed") or 0) > 0:
        return "FAIL", False
    word_pass = finalization.get("status") == "PASS" and finalization.get("toc_updated")
    pdf_ok = bool((publication.get("pdf") or {}).get("generated")) or bool(
        finalization.get("pdf_exported")
    )
    toc_aligned = _toc_entries_align(finalization)
    pdf_text_ok = (pdf_content or {}).get("status") == "PASS"
    if (
        word_pass
        and pdf_ok
        and finalization.get("pagination_stable")
        and toc_aligned
        and pdf_text_ok
    ):
        return "PASS", True
    return "PARTIAL", False


def _toc_entries_align(finalization: dict[str, Any]) -> bool:
    starts = list(finalization.get("chapter_starts") or [])
    toc = list(finalization.get("toc_entries") or [])
    by_title = {
        str(item.get("title") or "").strip(): item.get("page")
        for item in toc
        if item.get("page") is not None
    }
    if not starts or not by_title:
        return False
    printed = all(
        by_title.get(str(item.get("title") or "").strip()) == item.get("page")
        for item in starts
    )
    adjusted = all(
        by_title.get(str(item.get("title") or "").strip()) == item.get("page_adjusted")
        for item in starts
    )
    return printed or adjusted


def _blocked_bundle(before: dict[str, Any], after: dict[str, Any], error: str) -> dict[str, Any]:
    header = {
        "result": "BLOCKED",
        "provider_calls": 0,
        "book_title": BOOK_TITLE,
        "book_version": BOOK_VERSION,
        "book_status": BOOK_STATUS,
        "book_sha256": EXPECTED_BOOK_SHA256,
        "print_format": PRINT_FORMAT,
        "print_profile": PRINT_PROFILE,
        "word_available": "NO",
        "word_finalization": "NOT_AVAILABLE",
        "docx_generated": "NO",
        "docx_path": "",
        "docx_sha256": "",
        "docx_content_integrity": "FAIL",
        "chapters": f"0 / {EXPECTED_CHAPTER_COUNT}",
        "sections": f"0 / {EXPECTED_SECTION_COUNT}",
        "paragraphs": f"0 / {EXPECTED_PARAGRAPH_COUNT}",
        "toc_updated": "NO",
        "pagination_stable": "NOT_VERIFIED",
        "pdf_generated": "NO",
        "pdf_path": "",
        "pdf_sha256": "",
        "pdf_page_count": "",
        "pdf_page_size": "",
        "pdf_content_integrity": "NOT_VERIFIED",
        "odd_page_chapter_starts": "NOT_VERIFIED",
        "visual_inspection": "NOT_PERFORMED",
        "canonical_hashes_pre_post": "MATCH" if hashes_match(before, after) else "MISMATCH",
        "source_chapters_immutable": _yn(hashes_match(before, after)),
        "publication_status": PUBLICATION_STATUS,
        "ready_for_physical_print_review": "NO",
        "next_action": NEXT_ACTION_FAIL,
        "issues": f"- {error}",
        "pytest_summary": "not run",
        "scenario_summary": "not run",
        "word_limits": "- Preflight stopped before Word detection.",
        "human_checks": "- Resolve the blocking preflight error.",
        "technical_corrections": "- None.",
        "canonical_python": CANONICAL_PYTHON,
    }
    bundle = {
        "header": header,
        "canonical_hashes_pre_post": {
            "phase": PHASE,
            "pre": before,
            "post": after,
            "match": hashes_match(before, after),
            "status": "MATCH" if hashes_match(before, after) else "MISMATCH",
        },
        "readiness": {
            "READY_FOR_PHYSICAL_PRINT_REVIEW": False,
            "why": error,
            "NEXT_ACTION": NEXT_ACTION_FAIL,
        },
    }
    bundle["report_text"] = render_report(bundle)
    return bundle


def _assemble(
    *,
    preflight: dict[str, Any],
    unfinalized: dict[str, Any],
    integrity: dict[str, Any],
    mapping: dict[str, Any],
    environment: dict[str, Any],
    finalization: dict[str, Any],
    publication: dict[str, Any],
    tests: dict[str, Any],
    hashes_ok: bool,
    before: dict[str, Any],
    after: dict[str, Any],
    result_label: str,
    ready: bool,
    official_docx: str,
    official_pdf: str,
) -> dict[str, Any]:
    book = preflight["book"]
    toc = validate_toc(finalization, book)
    pagination = validate_pagination(finalization=finalization, book=book)
    pdf_path = official_pdf or finalization.get("pdf_path") or ""
    pdf_file = Path(pdf_path) if pdf_path else None
    pdf_export = validate_pdf_export(pdf_file)
    pdf_content = validate_pdf_content(pdf_file, book)
    pdf_geometry = validate_pdf_geometry(pdf_file)
    visual = visual_inspection_report(
        pdf_path=pdf_file,
        pagination=pagination,
        pdf_content=pdf_content,
    )
    scenarios = evaluate_offline_scenarios(
        bundle={
            "render_preflight": preflight,
            "docx_integrity_validation": integrity,
            "docx_content_mapping": mapping,
            "word_environment_detection": environment,
            "word_finalization_report": finalization,
            "publication_manifest": publication,
        },
        hashes_ok=hashes_ok,
        tests=tests,
    )
    pdf_hash = file_sha256(Path(pdf_path)) if pdf_path else {"sha256": "", "bytes": 0}
    docx_path = official_docx or unfinalized.get("path") or ""
    docx_hash = file_sha256(Path(docx_path)) if docx_path else unfinalized
    word_available = _yn(bool(environment.get("word_available")))
    if finalization.get("status") == "NOT_AVAILABLE":
        word_finalization = "NOT_AVAILABLE"
    else:
        word_finalization = str(finalization.get("status") or "NOT_AVAILABLE")
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
    if finalization.get("status") == "NOT_AVAILABLE":
        issues.append(str(finalization.get("required_human_action") or "Word is unavailable."))
    if not hashes_ok:
        issues.append("Canonical hashes changed.")
    if int(tests.get("failed") or 0):
        issues.append(f"pytest failures: {tests.get('summary')}")
    word_limits = [
        "- python-docx cannot compute final page numbers; Microsoft Word is required.",
        "- win32com is not installed; Word automation uses PowerShell COM and does not add a package.",
        "- Existing user Word sessions are not quit; only a process-created instance is closed.",
        "- Soft visual inspection of printed pages was not performed.",
    ]
    human_checks = [
        "- Inspect the half-title, title page, contents, first chapter, a middle chapter, and the last chapter on paper or in Word/PDF preview.",
        "- Confirm headers, footers, and any verso blanks created by odd-page chapter starts.",
        "- The six human-accepted chapters keep their status; the thirteen others remain pending.",
    ]
    header = {
        "result": result_label,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "provider_calls": 0,
        "book_title": BOOK_TITLE,
        "book_version": BOOK_VERSION,
        "book_status": BOOK_STATUS,
        "book_sha256": EXPECTED_BOOK_SHA256,
        "print_format": PRINT_FORMAT,
        "print_profile": PRINT_PROFILE,
        "word_available": word_available,
        "word_finalization": word_finalization,
        "docx_generated": _yn(bool(unfinalized.get("exists") or official_docx)),
        "docx_path": docx_path,
        "docx_sha256": docx_hash.get("sha256") or "",
        "docx_content_integrity": integrity.get("status"),
        "chapters": f"{integrity.get('chapter_count')} / {EXPECTED_CHAPTER_COUNT}",
        "sections": f"{integrity.get('section_count')} / {EXPECTED_SECTION_COUNT}",
        "paragraphs": f"{integrity.get('paragraph_count')} / {EXPECTED_PARAGRAPH_COUNT}",
        "toc_updated": _yn(bool(finalization.get("toc_updated"))),
        "pagination_stable": (
            "YES"
            if finalization.get("pagination_stable")
            else ("NOT_VERIFIED" if not finalization.get("executed") else "NO")
        ),
        "pdf_generated": _yn(bool(pdf_export.get("exists"))),
        "pdf_path": pdf_export.get("path") or "",
        "pdf_sha256": pdf_hash.get("sha256") or "",
        "pdf_page_count": pdf_geometry.get("page_count") if pdf_export.get("exists") else "",
        "pdf_page_size": pdf_geometry.get("page_size") if pdf_export.get("exists") else "",
        "pdf_content_integrity": pdf_content.get("status"),
        "odd_page_chapter_starts": pagination.get("odd_page_chapter_starts"),
        "visual_inspection": visual.get("status"),
        "canonical_hashes_pre_post": "MATCH" if hashes_ok else "MISMATCH",
        "source_chapters_immutable": _yn(hashes_ok),
        "publication_status": PUBLICATION_STATUS,
        "ready_for_physical_print_review": _yn(ready),
        "next_action": next_action,
        "pytest_summary": tests.get("summary") or "skipped",
        "scenario_summary": f"{scenarios.get('passed')} passed / {scenarios.get('failed')} failed",
        "issues": "- None." if not issues else "\n".join(f"- {item}" for item in issues),
        "word_limits": "\n".join(word_limits),
        "human_checks": "\n".join(human_checks),
        "technical_corrections": (
            "- Added a canonical version line on the title page and w:updateFields "
            "as a convenience for unfinalized drafts. Neither replaces a real Word pass.\n"
            "- Cleared inherited w:start page restarts on later chapter sections so "
            "body pagination continues instead of restarting at 1 in every chapter.\n"
            "- PDF text comparison folds glyph-spaced Word output and allows head/tail "
            "matches when a few encoded characters are dropped by the stdlib extractor."
        ),
        "canonical_python": CANONICAL_PYTHON,
    }
    readiness = {
        "READY_FOR_PHYSICAL_PRINT_REVIEW": ready,
        "DOCX": header["docx_generated"],
        "PDF": header["pdf_generated"],
        "WORD_FINALIZATION": word_finalization,
        "DOCX_CONTENT_INTEGRITY": integrity.get("status"),
        "PUBLICATION_STATUS": PUBLICATION_STATUS,
        "BOOK_JSON_UNCHANGED": hashes_ok,
        "NEXT_ACTION": next_action,
        "why": result_label,
    }
    preflight_public = {
        key: value
        for key, value in preflight.items()
        if key not in {"payload", "profile", "book"}
    }
    bundle = {
        "header": header,
        "render_preflight": preflight_public,
        "word_environment_detection": environment,
        "docx_generation_manifest": generation_manifest(
            book=book,
            profile=preflight["profile"],
            unfinalized=unfinalized,
            book_sha256=EXPECTED_BOOK_SHA256,
        ),
        "docx_integrity_validation": integrity,
        "docx_content_mapping": mapping,
        "word_finalization_report": finalization,
        "toc_validation": toc,
        "pagination_validation": pagination,
        "pdf_export_report": pdf_export,
        "pdf_content_validation": pdf_content,
        "pdf_page_geometry_validation": pdf_geometry,
        "visual_inspection_report": visual,
        "canonical_hashes_pre_post": {
            "phase": PHASE,
            "pre": before,
            "post": after,
            "match": hashes_ok,
            "status": "MATCH" if hashes_ok else "MISMATCH",
            "book_json_pre": before.get("book_json"),
            "book_json_post": after.get("book_json"),
            "expected_book_sha256": EXPECTED_BOOK_SHA256,
            "source_chapters_immutable": hashes_ok,
            "secrets_included": False,
        },
        "publication_manifest": publication,
        "offline_tests": {"pytest": tests, "scenarios": scenarios},
        "readiness": readiness,
    }
    bundle["report_text"] = render_report(bundle)
    return bundle


__all__ = ["PhaseResult", "run_phase"]
