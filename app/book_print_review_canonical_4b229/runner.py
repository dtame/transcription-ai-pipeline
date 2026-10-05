"""
Runner Phase 4B.2.29.

Constitute the provisional print-review book.json from the 19 existing
chapters. Zero provider calls. Zero rewrite. Zero DOCX/PDF.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.ai.provider_preflight import redact_secrets
from app.book_full_manuscript_review_4b228.inventory import build_chapters_inventory
from app.book_print_review_canonical_4b229.builder import (
    build_book_payload,
    render_book,
)
from app.book_print_review_canonical_4b229.constants import (
    ACCEPTED_CHAPTER_COUNT,
    AUTHORIZATION_SCOPE,
    BOOK_STATUS,
    BOOK_TITLE,
    BOOK_VERSION,
    CANONICAL_PYTHON,
    EXPECTED_IDEA_COUNT,
    EXPECTED_SECTION_COUNT,
    HUMAN_ACCEPTED_STATUS,
    NEXT_ACTION,
    PENDING_CHAPTER_IDS,
    PHASE,
    REMAINING_CHAPTER_COUNT,
    STRUCTURAL_STATUS,
)
from app.book_print_review_canonical_4b229.guard import (
    BookPrintReviewCanonical4229Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_print_review_canonical_4b229.hashes import (
    assert_accepted_unchanged,
    assert_candidates_present,
    assert_canonical,
    file_sha256,
    snapshot,
    source_snapshots_match,
)
from app.book_print_review_canonical_4b229.integrity import (
    chapter_source_rows,
    validate_book_integrity,
)
from app.book_print_review_canonical_4b229.observations import load_editorial_observations
from app.book_print_review_canonical_4b229.paths import (
    audit_book_copy_path,
    production_book_path,
    repo_root,
    venv_python_path,
)
from app.book_print_review_canonical_4b229.publisher import publish_atomic
from app.book_print_review_canonical_4b229.report import render_report
from app.book_print_review_canonical_4b229.scenarios import evaluate_offline_scenarios
from app.book_print_review_canonical_4b229.schema import validate_book_schema
from app.book_print_review_canonical_4b229.word import assess_word_readiness
from app.book_print_review_canonical_4b229.writer import write_phase_artifacts
from app.book_scale_up_preparation_4b220.corpus import load_canonical_corpus
from app.file_utils import content_hash


@dataclass
class PhaseResult:
    accepted: bool
    mode: str
    bundle: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = ["app/tests/test_book_print_review_canonical_4b229.py"]
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
    publish: bool | None = None,
    generated_at: str | None = None,
    root: Path | None = None,
) -> PhaseResult:
    result = PhaseResult(accepted=False, mode="OFFLINE")
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
    except BookPrintReviewCanonical4229Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    should_publish = write_artifacts if publish is None else publish
    before = snapshot(root=base)
    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try:
        assert_canonical(before)
        assert_accepted_unchanged(before)
        assert_candidates_present(before)
        corpus = load_canonical_corpus()
        inventory = build_chapters_inventory(corpus=corpus, root=base)
        observations = load_editorial_observations(root=base)
        payload = build_book_payload(
            inventory=inventory,
            corpus=corpus,
            generated_at=generated_at,
            root=base,
        )
        schema = validate_book_schema(payload, corpus=corpus)
        integrity = validate_book_integrity(
            inventory=inventory, payload=payload, root=base
        )
        word = assess_word_readiness(payload)
        publication: dict[str, Any] = {
            "atomic": False,
            "action": "not_requested",
            "destination": str(production_book_path(root=base)).replace("\\", "/"),
        }
        if should_publish:
            publication = publish_atomic(
                payload,
                destination=production_book_path(root=base),
                audit_copy=audit_book_copy_path(root=base),
            )
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
                "match": source_snapshots_match(before, after),
            },
            "readiness": {"READY_FOR_PRINT_REVIEW_PRODUCTION": False},
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
    hashes_ok = source_snapshots_match(before, after) and after["canonical_match_expected"]
    scenarios = evaluate_offline_scenarios(
        inventory=inventory,
        payload=payload,
        integrity=integrity,
        schema=schema,
        observations=observations,
        word=word,
        publication=publication,
        hashes_ok=hashes_ok,
        generated_at=generated_at,
        root=base,
    )
    book_digest = content_hash(render_book(payload))
    published_hash = file_sha256(production_book_path(root=base))
    paragraph_ok = integrity.get("paragraph_integrity") == "PASS"
    provenance_ok = integrity.get("provenance_integrity") == "PASS"
    markdown_ok = integrity.get("markdown_comparison") == "PASS"
    schema_ok = schema.get("status") in {"PASS", "REVIEW"}
    word_ok = word.get("status") in {"PASS", "PARTIAL"}
    observations_ok = observations.get("preserved") is True
    publication_ok = (not should_publish) or publication.get("atomic") is True
    test_failures = int(tests.get("failed") or 0) + int(scenarios.get("failed") or 0)
    ready = all(
        (
            paragraph_ok,
            provenance_ok,
            markdown_ok,
            schema_ok,
            word_ok,
            observations_ok,
            hashes_ok,
            publication_ok,
            test_failures == 0,
            integrity.get("chapter_count") == 19,
            integrity.get("section_count") == EXPECTED_SECTION_COUNT,
            integrity.get("idea_coverage_count") == EXPECTED_IDEA_COUNT,
            payload.get("editorial_status") == BOOK_STATUS,
        )
    )
    if not hashes_ok or not paragraph_ok or not provenance_ok or not schema_ok:
        result_label = "FAIL"
    elif ready:
        result_label = "PASS"
    else:
        result_label = "PARTIAL"

    canonical_path = str(production_book_path(root=base)).replace("\\", "/")
    header = {
        "result": result_label,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "provider_calls": 0,
        "anthropic_http": 0,
        "openai_http": 0,
        "book_title": BOOK_TITLE,
        "book_status": BOOK_STATUS,
        "book_version": BOOK_VERSION,
        "book_canonical_path": canonical_path,
        "book_sha256": published_hash.get("sha256") or book_digest,
        "chapters": f"{integrity.get('chapter_count')} / 19",
        "sections": f"{integrity.get('section_count')} / {EXPECTED_SECTION_COUNT}",
        "idea_coverage": f"{integrity.get('idea_coverage_count')} / {EXPECTED_IDEA_COUNT}",
        "human_accepted_chapters": ACCEPTED_CHAPTER_COUNT,
        "human_review_pending_chapters": REMAINING_CHAPTER_COUNT,
        "paragraph_integrity": integrity.get("paragraph_integrity"),
        "provenance_integrity": integrity.get("provenance_integrity"),
        "markdown_comparison": integrity.get("markdown_comparison"),
        "schema_validation": schema.get("status"),
        "word_renderer_readiness": word.get("status"),
        "editorial_observations_preserved": _yn(observations_ok),
        "canonical_hashes_pre_post": "MATCH" if hashes_ok else "MISMATCH",
        "source_chapters_immutable": _yn(hashes_ok),
        "publication_atomic": _yn(publication.get("atomic") is True) if should_publish else "NOT REQUESTED",
        "ready_for_print_review_production": _yn(ready),
        "next_action": NEXT_ACTION,
        "pytest_summary": tests.get("summary") or "skipped",
        "scenario_summary": f"{scenarios.get('passed')} passed / {scenarios.get('failed')} failed",
        "issues": "- None." if result_label == "PASS" else f"- {result.error or result_label}",
        "canonical_python": CANONICAL_PYTHON,
    }
    readiness = {
        "READY_FOR_PRINT_REVIEW_PRODUCTION": ready,
        "BOOK_STATUS": BOOK_STATUS,
        "BOOK_VERSION": BOOK_VERSION,
        "CHAPTERS": integrity.get("chapter_count"),
        "SECTIONS": integrity.get("section_count"),
        "IDEA_COVERAGE": integrity.get("idea_coverage_count"),
        "PARAGRAPH_INTEGRITY": integrity.get("paragraph_integrity"),
        "SCHEMA_VALIDATION": schema.get("status"),
        "WORD_RENDERER_READINESS": word.get("status"),
        "DOCX": "NOT GENERATED",
        "PDF": "NOT GENERATED",
        "VISUAL_DIRECTION": "NOT STARTED",
        "SEMANTIC_CERTIFICATION": "NOT PERFORMED",
        "NEXT_ACTION": NEXT_ACTION,
        "why": "PROVISIONAL_PRINT_REVIEW_BOOK_CONSTITUTED" if ready else result_label,
    }
    chapter_rows = chapter_source_rows(inventory)
    status_rows = [
        {
            "chapter_id": chapter["chapter_id"],
            "order": chapter["order"],
            "title": chapter["title"],
            "editorial_status": chapter["editorial_status"],
            "human_acceptance_status": chapter["human_acceptance_status"],
            "structural_status": chapter["structural_status"],
            "book_status_does_not_override": chapter["editorial_status"] != BOOK_STATUS
            or chapter["chapter_id"] not in PENDING_CHAPTER_IDS,
        }
        for chapter in payload.get("chapters") or []
    ]
    manifest = {
        "phase": PHASE,
        "project": inventory.get("project"),
        "title": BOOK_TITLE,
        "language": payload.get("language"),
        "document_version": BOOK_VERSION,
        "editorial_status": BOOK_STATUS,
        "generated_at": generated_at,
        "canonical_runtime_path": canonical_path,
        "audit_copy_path": str(audit_book_copy_path(root=base)).replace("\\", "/"),
        "canonical_used_by_next_steps": canonical_path,
        "sha256": header["book_sha256"],
        "chapter_count": 19,
        "section_count": EXPECTED_SECTION_COUNT,
        "idea_coverage_count": EXPECTED_IDEA_COUNT,
        "human_accepted": list(integrity.get("accepted_chapter_ids") or []),
        "human_review_pending": list(integrity.get("pending_chapter_ids") or []),
        "human_accepted_status": HUMAN_ACCEPTED_STATUS,
        "pending_status": STRUCTURAL_STATUS,
        "book_status_is_not_human_acceptance": True,
        "manuscript_sha256": (before.get("manuscript") or {}).get("sha256"),
        "editorial_plan_sha256": corpus.inputs.plan_sha256,
        "source_map_sha256": corpus.inputs.source_map_sha256,
        "transcript_sha256": corpus.transcript.content_sha256,
        "secrets_included": False,
    }
    hashes_pre_post = {
        "phase": PHASE,
        "pre": before,
        "post": after,
        "match": hashes_ok,
        "status": "MATCH" if hashes_ok else "MISMATCH",
        "book_json_pre": (before.get("canonical") or {}).get("book_json"),
        "book_json_post": (after.get("canonical") or {}).get("book_json"),
        "book_json_publication_authorized": should_publish,
        "source_chapters_immutable": hashes_ok,
        "secrets_included": False,
    }
    bundle = {
        "header": header,
        "preflight": {
            "phase": PHASE,
            "authorization_scope": AUTHORIZATION_SCOPE,
            "offline": True,
            "provider_calls": 0,
            "canonical_hashes_ok": before["canonical_match_expected"],
            "real_generation_authorized": False,
            "secrets_included": False,
        },
        "book_payload": payload,
        "book_canonical_manifest": manifest,
        "chapter_sources_manifest": {
            "phase": PHASE,
            "chapters": chapter_rows,
            "count": len(chapter_rows),
            "secrets_included": False,
        },
        "editorial_status_manifest": {
            "phase": PHASE,
            "book_status": BOOK_STATUS,
            "book_status_is_not_human_acceptance": True,
            "chapters": status_rows,
            "secrets_included": False,
        },
        "book_integrity_validation": integrity,
        "book_schema_validation": schema,
        "book_markdown_comparison": integrity.get("comparison"),
        "word_renderer_readiness": word,
        "editorial_observations_manifest": observations,
        "canonical_hashes_pre_post": hashes_pre_post,
        "publication_audit": publication,
        "offline_regression_tests": {
            "pytest": tests,
            "scenarios": scenarios,
        },
        "readiness": readiness,
    }
    if write_artifacts:
        written = write_phase_artifacts(bundle, root=base)
        bundle["written"] = written
        header["issues"] = header["issues"]
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        written = write_phase_artifacts(bundle, root=base)
        bundle["written"] = written
    result.bundle = redact_secrets(bundle)
    result.accepted = result_label == "PASS"
    result.mode = result_label
    result.error = "" if result_label == "PASS" else result_label
    return result


def _unused_mapping_probe(value: Mapping[str, Any] | None) -> None:
    del value


__all__ = ["PhaseResult", "run_phase"]
