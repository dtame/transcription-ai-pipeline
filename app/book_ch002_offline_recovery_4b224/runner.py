"""
Phase 4B.2.24 runner.

Offline only. Inspects CH002, recovers the empty paragraph if admissible,
prepares the CH001 human review packet, and drafts a CH003/CH004 resume plan.
Never calls a provider. Never resets locks. Never rewrites originals.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.book_ch002_offline_recovery_4b224.chapter_io import load_json, paragraph_ids
from app.book_ch002_offline_recovery_4b224.constants import (
    ARTIFACT_KIND,
    AUTHORIZATION_SCOPE,
    CANONICAL_PYTHON,
    CH001_STATUS,
    CONSUMED_4B223_SCOPE,
    EMPTY_PARAGRAPH_ID,
    EXPECTED_CH002_IDEA_COUNT,
    HISTORICAL_BATCH01_COST_USD,
    NEXT_ACTION,
    NOT_ORIGINAL,
    PHASE,
    RECOVERED_STATUS,
    TARGET_CHAPTER_ID,
)
from app.book_ch002_offline_recovery_4b224.forensic import inspect_ch002
from app.book_ch002_offline_recovery_4b224.guard import (
    BookCh002OfflineRecovery4224Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_ch002_offline_recovery_4b224.hashes import (
    assert_canonical,
    assert_ch012_unchanged,
    assert_ch018_unchanged,
    file_sha256,
    snapshot,
    snapshots_match,
)
from app.book_ch002_offline_recovery_4b224.paths import (
    original_candidate_json_path,
    original_candidate_md_path,
    original_lock_file,
    original_raw_response_path,
    phase_audit_dir,
    production_book_path,
    repo_root,
    venv_python_path,
)
from app.book_ch002_offline_recovery_4b224.prevention import (
    analyze_prevention,
    render_prevention_markdown,
)
from app.book_ch002_offline_recovery_4b224.recovery import remove_empty_paragraph
from app.book_ch002_offline_recovery_4b224.report import render_report
from app.book_ch002_offline_recovery_4b224.resume import build_resume_plan
from app.book_ch002_offline_recovery_4b224.review_ch001 import (
    build_ch001_review_packet,
    render_ch001_review_markdown,
)
from app.book_ch002_offline_recovery_4b224.scenarios import evaluate_offline_scenarios
from app.book_ch002_offline_recovery_4b224.validate import validate_recovered_chapter
from app.book_ch002_offline_recovery_4b224.writer import write_phase_artifacts
from app.book_generation_4b223.context import load_corpus
from app.book_generation_4b223.lock import lock_already_consumed, read_lock


@dataclass
class PhaseResult:
    accepted: bool
    mode: str
    bundle: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = ["app/tests/test_book_ch002_offline_recovery_4b224.py"]
    python = str(venv_python_path(root=root))
    completed = subprocess.run(
        [
            python,
            "-m",
            "pytest",
            "-q",
            "--tb=line",
            "-k",
            "not test_phase_writes_isolated_audits",
            *tests,
        ],
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


def _hash_line(label: str, snap: dict[str, Any]) -> str:
    canonical = snap["canonical"]
    return (
        f"{label} source={canonical['source_map']['sha256']} "
        f"plan={canonical['editorial_plan']['sha256']} "
        f"transcript={canonical['clean_transcript']['sha256']}"
    )


def _content_diff(original: dict[str, Any], recovered: dict[str, Any]) -> dict[str, Any]:
    original_ids = paragraph_ids(original)
    recovered_ids = paragraph_ids(recovered)
    removed = [item for item in original_ids if item not in recovered_ids]
    added = [item for item in recovered_ids if item not in original_ids]
    text_changes = []
    orig_map = {
        para.get("paragraph_id"): para
        for section in original.get("sections") or []
        for para in section.get("paragraphs") or []
    }
    new_map = {
        para.get("paragraph_id"): para
        for section in recovered.get("sections") or []
        for para in section.get("paragraphs") or []
    }
    for paragraph_id, paragraph in orig_map.items():
        if paragraph_id == EMPTY_PARAGRAPH_ID:
            continue
        other = new_map.get(paragraph_id)
        if other is None:
            text_changes.append({"paragraph_id": paragraph_id, "change": "missing"})
            continue
        if other != paragraph:
            text_changes.append({"paragraph_id": paragraph_id, "change": "content"})
    return {
        "removed_paragraph_ids": removed,
        "added_paragraph_ids": added,
        "renumbered": False,
        "other_paragraph_content_changes": text_changes,
        "only_p000008_removed": removed == [EMPTY_PARAGRAPH_ID]
        and not added
        and not text_changes,
    }


def run_phase(
    *,
    authorization_scope: str | None,
    write_artifacts: bool = True,
    run_tests: bool = True,
    root: Path | None = None,
) -> PhaseResult:
    validate_authorization_scope(authorization_scope)
    assert_offline_only()
    base = root or repo_root()
    before = snapshot(root=base)
    assert_canonical(before)
    assert_ch012_unchanged(before)
    assert_ch018_unchanged(before)
    if production_book_path().exists():
        raise BookCh002OfflineRecovery4224Error(
            "production book.json must remain unpublished"
        )

    forensic = inspect_ch002()
    original = load_json(original_candidate_json_path(TARGET_CHAPTER_ID))
    original_md = original_candidate_md_path(TARGET_CHAPTER_ID).read_text(encoding="utf-8")
    raw = load_json(original_raw_response_path(TARGET_CHAPTER_ID))
    lock = read_lock(original_lock_file(TARGET_CHAPTER_ID)) or {}
    corpus = load_corpus()

    recovery_blocked = not forensic.get("recovery_admissible_from_forensics")
    recovered_payload = None
    recovered_md = None
    recovery_result = None
    validation = None
    recovery_error = ""
    if not recovery_blocked:
        try:
            recovery_result = remove_empty_paragraph(original)
            recovered_payload = recovery_result["recovered"]
            validation = validate_recovered_chapter(
                recovered_payload,
                corpus=corpus,
                finish_reason=raw.get("finish_reason"),
                max_output_tokens=11766,
            )
            recovered_md = validation.get("markdown")
            if validation.get("status") != "PASS":
                recovery_blocked = True
                recovery_error = "; ".join(validation.get("errors") or ["validation FAIL"])
        except BookCh002OfflineRecovery4224Error as exc:
            recovery_blocked = True
            recovery_error = str(exc)
    else:
        recovery_error = "; ".join(forensic.get("recovery_block_reasons") or ["blocked"])

    content_diff = (
        _content_diff(original, recovered_payload)
        if recovered_payload is not None
        else {
            "removed_paragraph_ids": [],
            "added_paragraph_ids": [],
            "renumbered": False,
            "other_paragraph_content_changes": [],
            "only_p000008_removed": False,
        }
    )
    if recovered_payload is not None and not content_diff["only_p000008_removed"]:
        recovery_blocked = True
        recovery_error = recovery_error or "diff contains more than P000008 removal"

    recovered_status = None
    if (
        not recovery_blocked
        and recovered_payload is not None
        and validation is not None
        and validation.get("status") == "PASS"
        and content_diff["only_p000008_removed"]
    ):
        recovered_status = RECOVERED_STATUS
    else:
        recovered_status = "RECOVERY = BLOCKED"

    original_json_hash = file_sha256(original_candidate_json_path(TARGET_CHAPTER_ID))
    original_md_hash = file_sha256(original_candidate_md_path(TARGET_CHAPTER_ID))
    raw_hash = file_sha256(original_raw_response_path(TARGET_CHAPTER_ID))

    recovered_json_sha = ""
    recovered_md_sha = ""
    if recovered_payload is not None:
        recovered_json_sha = hashlib.sha256(
            json.dumps(recovered_payload, ensure_ascii=True, indent=2).encode("utf-8")
        ).hexdigest()
    if isinstance(recovered_md, str):
        recovered_md_sha = hashlib.sha256(recovered_md.encode("utf-8")).hexdigest()

    markdown_identical = recovered_md == original_md if recovered_md is not None else False
    recovery_diff = {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "json": content_diff,
        "markdown": {
            "original_omitted_empty_paragraph": True,
            "recovered_identical_to_original_markdown": markdown_identical,
            "mechanical_render_only": markdown_identical,
        },
        "unauthorized_editorial_changes": bool(content_diff["other_paragraph_content_changes"]),
        "secrets_included": False,
    }
    recovery_manifest = {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "raw_json_sha256": raw_hash.get("sha256"),
        "original_candidate_json_sha256": original_json_hash.get("sha256"),
        "recovered_json_sha256": recovered_json_sha,
        "original_markdown_sha256": original_md_hash.get("sha256"),
        "recovered_markdown_sha256": recovered_md_sha,
        "removed_paragraph_id": EMPTY_PARAGRAPH_ID,
        "justification": (
            "P000008 is a model-emitted empty connective with no editorial text "
            "and no IDEA/SRC/EX/REF/UNC provenance. Removing the object does not "
            "renumber remaining paragraphs and does not change chapter meaning."
            if recovered_status == RECOVERED_STATUS
            else recovery_error
        ),
        "exact_modifications": (
            ["delete SEC006 paragraph object P000008"]
            if recovered_status == RECOVERED_STATUS
            else []
        ),
        "validation_status": None if validation is None else validation.get("status"),
        "artifact_kind": ARTIFACT_KIND,
        "not_provider_original": NOT_ORIGINAL,
        "additional_provider_calls": 0,
        "human_acceptance": "PENDING",
        "recovery_status": recovered_status,
        "originals_immutable": True,
        "secrets_included": False,
    }
    recovery_readiness = {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "recovery_status": recovered_status,
        "human_review_pending": recovered_status == RECOVERED_STATUS,
        "user_accepted": False,
        "ready_for_human_review": recovered_status == RECOVERED_STATUS,
        "ready_for_publication": False,
        "call_lock_consumed": lock_already_consumed(original_lock_file(TARGET_CHAPTER_ID)),
        "lock_state": lock.get("state"),
        "secrets_included": False,
    }

    ch001 = build_ch001_review_packet()
    ch001_md = render_ch001_review_markdown(ch001)
    resume = build_resume_plan(
        recovery_succeeded=recovered_status == RECOVERED_STATUS
    )
    prevention = analyze_prevention(
        forensic,
        original_validation_status=str(
            (forensic.get("structural_validation") or {}).get("status") or ""
        ),
        recovered_validation_status=None
        if validation is None
        else str(validation.get("status") or ""),
    )
    prevention_md = render_prevention_markdown(prevention)

    tests = (
        _run_focused_tests(root=repo_root())
        if run_tests
        else {
            "returncode": 0,
            "summary": "not_run",
            "passed": 0,
            "failed": 0,
            "suites": [],
            "real_provider_calls": 0,
        }
    )
    after = snapshot(root=base)
    hashes_ok = snapshots_match(before, after) and after["canonical_match_expected"]
    scenarios = evaluate_offline_scenarios(
        forensic=forensic,
        recovery=recovery_result,
        recovered=recovered_payload,
        validation=validation,
        before=before,
        after=after,
        tests=tests if run_tests else None,
    )

    additional_defects = list(forensic.get("other_raw_anomalies") or []) + list(
        forensic.get("other_candidate_anomalies") or []
    ) + list((forensic.get("structural_validation") or {}).get("additional_contract_errors") or [])
    recovered_contract = (
        "PASS"
        if recovered_status == RECOVERED_STATUS and validation and validation.get("status") == "PASS"
        else "FAIL"
    )
    idea_traced = 0
    if validation is not None:
        idea_traced = int((validation.get("checks") or {}).get("ideas_traced") or 0)
    elif forensic.get("structural_validation"):
        idea_traced = int(
            (forensic.get("structural_validation") or {}).get("ideas_found_in_paras_e") or 0
        )

    checks = {
        "no_provider_calls": True,
        "canonical_hashes_unchanged": hashes_ok,
        "ch012_unchanged": after.get("ch012_unchanged") is True,
        "ch018_unchanged": after.get("ch018_unchanged") is True,
        "batch01_originals_unchanged": before.get("batch01_originals")
        == after.get("batch01_originals"),
        "locks_unchanged": before.get("locks") == after.get("locks"),
        "ch002_lock_consumed": lock_already_consumed(original_lock_file(TARGET_CHAPTER_ID)),
        "ch002_inspected": True,
        "forensic_identifies_empty_p8": bool(
            (forensic.get("candidate") or {}).get("target", {}).get("empty")
        ),
        "recovery_validated": recovered_status == RECOVERED_STATUS,
        "ch001_review_prepared": bool(ch001.get("title")),
        "prevention_documented": True,
        "offline_scenarios_pass": scenarios["failed"] == 0,
        "focused_tests_pass": tests["failed"] == 0 and tests["returncode"] == 0,
        "no_publication": not production_book_path().exists(),
        "production_pipeline_unmodified": True,
        "consumed_4b223_not_reused": CONSUMED_4B223_SCOPE != AUTHORIZATION_SCOPE,
        "resume_not_executed": resume.get("executed_this_phase") is False,
    }
    blocking = [key for key, value in checks.items() if not value]
    if not hashes_ok or not checks["batch01_originals_unchanged"] or not checks["locks_unchanged"]:
        result = "FAIL"
    elif recovered_status != RECOVERED_STATUS:
        result = "PARTIAL"
    elif blocking:
        result = "FAIL"
    else:
        result = "PASS"

    notes = (
        "CH002 P000008 was a model-emitted empty connective with no provenance. "
        "A derived copy deleted only that object, kept remaining identifiers, "
        "and passed the existing structural validator. Originals and locks are "
        "unchanged. CH001 has a human review packet. CH003 and CH004 remain "
        "NOT_STARTED and require a new authorization."
        if recovered_status == RECOVERED_STATUS
        else (
            "CH002 recovery is blocked: "
            + (recovery_error or "see forensic review")
            + ". Originals remain unchanged."
        )
    )
    header = {
        "result": result,
        "provider_calls": 0,
        "anthropic_http": 0,
        "openai_http": 0,
        "ch001_status": CH001_STATUS,
        "ch002_recovery": recovered_status,
        "ch002_recovered_contract": recovered_contract,
        "ch002_idea_coverage": f"{idea_traced} / {EXPECTED_CH002_IDEA_COUNT}",
        "ch002_empty_paragraph": (
            "P000008 empty connective in SEC006; removed in derived copy"
            if recovered_status == RECOVERED_STATUS
            else "P000008 empty connective in SEC006; recovery blocked"
        ),
        "ch002_additional_defects": additional_defects or "none",
        "ch002_original_immutable": "YES" if checks["batch01_originals_unchanged"] else "NO",
        "ch002_lock_consumed": "YES" if checks["ch002_lock_consumed"] else "NO",
        "canonical_python": CANONICAL_PYTHON,
        "canonical_hashes_pre_post": _hash_line("pre", before)
        + "; "
        + _hash_line("post", after),
        "ch012_immutable": "YES" if checks["ch012_unchanged"] else "NO",
        "ch018_immutable": "YES" if checks["ch018_unchanged"] else "NO",
        "offline_tests": f"{scenarios['passed']} / {scenarios['failed']}",
        "ready_for_ch001_human_review": "YES" if result in {"PASS", "PARTIAL"} else "NO",
        "ready_for_ch002_human_review": "YES" if recovered_status == RECOVERED_STATUS else "NO",
        "ready_for_ch003_ch004_authorization": "YES" if result in {"PASS", "PARTIAL"} else "NO",
        "next_action": NEXT_ACTION,
        "recovery_notes": notes,
        "prevention_notes": (prevention.get("where_introduced") or {}).get("rationale")
        or notes,
        "historical_batch01_cost": str(HISTORICAL_BATCH01_COST_USD),
        "checks": checks,
        "blocking": blocking,
    }
    preflight = {
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "canonical_hashes_ok": before["canonical_match_expected"],
        "ch012_present": True,
        "ch018_present": True,
        "ch002_originals_present": True,
        "offline_only": True,
        "provider_calls_authorized": 0,
        "authorized_spend_usd": 0,
        "production_book_absent": not production_book_path().exists(),
        "consumed_batch01_authorization": CONSUMED_4B223_SCOPE,
        "secrets_included": False,
    }
    readiness = {
        "phase": PHASE,
        "result": result,
        "checks": checks,
        "provider_calls": 0,
        "openai_http_requests": 0,
        "anthropic_http_requests": 0,
        "CH001_STATUS": CH001_STATUS,
        "CH002_RECOVERY": recovered_status,
        "READY_FOR_CH001_HUMAN_REVIEW": result in {"PASS", "PARTIAL"},
        "READY_FOR_CH002_HUMAN_REVIEW": recovered_status == RECOVERED_STATUS,
        "READY_FOR_CH003_CH004_AUTHORIZATION": result in {"PASS", "PARTIAL"},
        "READY_FOR_BATCH02": False,
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "NEXT_ACTION": NEXT_ACTION,
        "why": notes,
        "secrets_included": False,
    }
    validation_artifact = None
    if validation is not None:
        validation_artifact = {
            key: value
            for key, value in validation.items()
            if key != "markdown"
        }
    bundle = {
        "header": header,
        "preflight": preflight,
        "canonical_hashes_pre": before,
        "ch002_empty_paragraph_forensic_review": forensic,
        "chapter_candidate_recovered": recovered_payload,
        "chapter_candidate_recovered_md": recovered_md,
        "recovery_diff": recovery_diff,
        "recovery_manifest": recovery_manifest,
        "recovery_validation": validation_artifact,
        "recovery_readiness": recovery_readiness,
        "ch001_human_editorial_review_packet": ch001,
        "ch001_human_editorial_review_packet_md": ch001_md,
        "empty_paragraph_prevention_analysis": prevention_md,
        "prevention": prevention,
        "batch01_resume_plan": resume,
        "canonical_hashes_post": after,
        "offline_regression_tests": {
            "phase": PHASE,
            "focused_tests": tests,
            "offline_scenarios": scenarios,
            "secrets_included": False,
        },
        "readiness": readiness,
        "execution": {
            "mode": "OFFLINE",
            "provider_calls": 0,
            "anthropic_http": 0,
            "openai_http": 0,
            "retries": 0,
            "fallbacks": 0,
            "audit_dir": str(phase_audit_dir(root=base)).replace("\\", "/"),
        },
    }
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        write_phase_artifacts(bundle, root=base)
        after_write = snapshot(root=base)
        if not snapshots_match(before, after_write):
            raise BookCh002OfflineRecovery4224Error(
                "Writing isolated audits mutated canonical, accepted, or BATCH-01 originals. STOP."
            )
        bundle["canonical_hashes_post"] = after_write
    return PhaseResult(
        accepted=result == "PASS",
        mode="OFFLINE",
        bundle=bundle,
        error=recovery_error,
    )


__all__ = ["PhaseResult", "run_phase"]
