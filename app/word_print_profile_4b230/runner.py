"""
Runner Phase 4B.2.30.

Prepare and validate the 6x9 Word print profile. Zero provider calls.
Zero book.json mutation. Zero published DOCX/PDF.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.ai.provider_preflight import redact_secrets
from app.word_print_profile_4b230.constants import (
    AUTHORIZATION_SCOPE,
    BOOK_STATUS,
    BOOK_TITLE,
    BOOK_VERSION,
    CANONICAL_PYTHON,
    EXPECTED_BOOK_SHA256,
    NEXT_ACTION,
    PHASE,
    PRINT_FORMAT,
    PRINT_PROFILE,
)
from app.word_print_profile_4b230.guard import (
    WordPrintProfile4230Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.word_print_profile_4b230.hashes import (
    assert_book_hash,
    assert_sources_unchanged,
    hashes_match,
    snapshot,
)
from app.word_print_profile_4b230.paths import production_book_path, repo_root, venv_python_path
from app.word_print_profile_4b230.report import render_report
from app.word_print_profile_4b230.scenarios import evaluate_offline_scenarios
from app.word_print_profile_4b230.validation import build_validations
from app.word_print_profile_4b230.writer import write_phase_artifacts


@dataclass
class PhaseResult:
    accepted: bool
    mode: str
    bundle: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = ["app/tests/test_word_print_profile_4b230.py"]
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
            if "passed" in line or "failed" in line
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
    root: Path | None = None,
) -> PhaseResult:
    result = PhaseResult(accepted=False, mode="OFFLINE")
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
    except WordPrintProfile4230Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = snapshot(root=base)
    try:
        assert_book_hash(before)
        validations = build_validations(root=base)
    except Exception as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        after = snapshot(root=base)
        bundle = {
            "header": {
                "result": "BLOCKED",
                "stop_reason": str(exc),
                "next_action": NEXT_ACTION,
                "book_title": BOOK_TITLE,
                "book_status": BOOK_STATUS,
                "book_version": BOOK_VERSION,
            },
            "canonical_hashes_pre_post": {
                "phase": PHASE,
                "pre": before,
                "post": after,
                "match": hashes_match(before, after),
            },
            "readiness": {"READY_FOR_DOCX_PDF_GENERATION": False},
        }
        bundle["report_text"] = render_report(bundle)
        if write_artifacts:
            write_phase_artifacts(bundle, root=base)
        result.bundle = redact_secrets(bundle)
        return result

    tests = (
        _run_focused_tests(root=base)
        if run_tests
        else {
            "returncode": 0,
            "summary": "skipped",
            "passed": 0,
            "failed": 0,
            "suites": [],
            "real_provider_calls": 0,
        }
    )
    after = snapshot(root=base)
    hashes_ok = hashes_match(before, after)
    try:
        assert_sources_unchanged(before, after)
    except WordPrintProfile4230Error as exc:
        hashes_ok = False
        result.error = str(exc)
    scenarios = evaluate_offline_scenarios(
        validations=validations,
        hashes_ok=hashes_ok,
        tests=tests,
        root=base,
    )
    styles_ok = validations["styles"]["status"] == "PASS"
    geometry_ok = validations["geometry"]["status"] == "PASS"
    toc_ok = validations["toc"]["status"] == "PASS"
    headers_ok = validations["headers"]["status"] == "PASS"
    mapping_ok = validations["mapping"]["status"] == "PASS"
    breaks_ok = validations["page_breaks"]["status"] == "PASS"
    test_failures = int(tests.get("failed") or 0) + int(scenarios.get("failed") or 0)
    ready = all(
        (
            validations["ready"],
            hashes_ok,
            test_failures == 0,
            styles_ok,
            geometry_ok,
            toc_ok,
            headers_ok,
            mapping_ok,
            breaks_ok,
        )
    )
    if not hashes_ok:
        result_label = "FAIL"
    elif ready:
        result_label = "PASS"
    else:
        result_label = "PARTIAL"

    header = {
        "result": result_label,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "provider_calls": 0,
        "book_title": BOOK_TITLE,
        "book_version": BOOK_VERSION,
        "book_status": BOOK_STATUS,
        "book_sha256": EXPECTED_BOOK_SHA256,
        "book_canonical_path": str(production_book_path(root=base)).replace("\\", "/"),
        "print_format": PRINT_FORMAT,
        "profile": PRINT_PROFILE,
        "word_renderer": "READY" if ready else "PARTIAL",
        "word_finalizer": "PARTIAL",
        "page_geometry": validations["geometry"]["status"],
        "mirror_margins": "PASS" if validations["geometry"]["checks"]["mirror_margins"] else "FAIL",
        "typography_styles": validations["styles"]["status"],
        "chapter_styles": "PASS" if validations["styles"]["checks"]["chapter_keep_with_next"] else "FAIL",
        "section_styles": "PASS" if validations["styles"]["checks"]["section_keep_with_next"] else "FAIL",
        "toc_preparation": validations["toc"]["status"],
        "headers_footers": validations["headers"]["status"],
        "chapter_page_breaks": validations["page_breaks"]["status"],
        "cover_integration": "OPTIONAL",
        "book_content_mapping": validations["mapping"]["status"],
        "offline_tests": f"{int(tests.get('passed') or 0) + int(scenarios.get('passed') or 0)} / {int(tests.get('failed') or 0) + int(scenarios.get('failed') or 0)}",
        "canonical_hashes_pre_post": "MATCH" if hashes_ok else "MISMATCH",
        "ready_for_docx_pdf_generation": _yn(ready),
        "next_action": NEXT_ACTION,
        "pytest_summary": tests.get("summary") or "skipped",
        "scenario_summary": f"{scenarios.get('passed')} passed / {scenarios.get('failed')} failed",
        "issues": "- None." if result_label == "PASS" else f"- {result.error or result_label}",
        "canonical_python": CANONICAL_PYTHON,
    }
    readiness = {
        "READY_FOR_DOCX_PDF_GENERATION": ready,
        "WORD_RENDERER": header["word_renderer"],
        "WORD_FINALIZER": "PARTIAL",
        "PROFILE": PRINT_PROFILE,
        "PRINT_FORMAT": PRINT_FORMAT,
        "DOCX": "NOT GENERATED",
        "PDF": "NOT GENERATED",
        "COVER": "OPTIONAL",
        "BOOK_JSON_UNCHANGED": hashes_ok,
        "NEXT_ACTION": NEXT_ACTION,
        "why": "PRINT_PROFILE_PREPARED" if ready else result_label,
    }
    hashes_pre_post = {
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
    }
    bundle = {
        "header": header,
        "word_renderer_inventory": validations["inventory"],
        "print_profile_6x9": validations["profile"],
        "styles_validation": validations["styles"],
        "page_geometry_validation": validations["geometry"],
        "toc_validation": validations["toc"],
        "headers_footers_validation": validations["headers"],
        "book_mapping_validation": validations["mapping"],
        "word_finalizer_readiness": validations["finalizer"],
        "cover_integration_contract": validations["cover"],
        "offline_tests": {
            "pytest": tests,
            "scenarios": scenarios,
        },
        "canonical_hashes_pre_post": hashes_pre_post,
        "readiness": readiness,
    }
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        written = write_phase_artifacts(bundle, root=base)
        bundle["written"] = written
        bundle["report_text"] = render_report(bundle)
        written = write_phase_artifacts(bundle, root=base)
        bundle["written"] = written
    result.bundle = redact_secrets(bundle)
    result.accepted = result_label == "PASS"
    result.mode = result_label
    result.error = "" if result_label == "PASS" else result_label
    return result


__all__ = ["PhaseResult", "run_phase"]
