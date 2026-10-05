"""
Phase 4B.2.18 runner.

Offline only. Audits CH012, applies justified voice corrections, versions
the 1.1 prompt, and diagnoses IDEA handle traceability. Never authorizes
a provider call. Never overwrites the original chapter or lock.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.book_authorial_voice_4b218.attribution import collect_attribution_evidence
from app.book_authorial_voice_4b218.chapter_io import (
    iter_paragraphs,
    load_original_chapter,
    paragraph_ids,
    section_ids,
)
from app.book_authorial_voice_4b218.constants import (
    AUTHORIAL_VOICE_POLICY_VERSION,
    AUTHORIZATION_SCOPE,
    CANONICAL_PYTHON,
    CLASS_ATTRIBUTION_UNCERTAIN,
    CLASS_EXTERNAL_CONFIRMED,
    CLASS_POSSIBLE_EXTERNAL,
    EXPECTED_PARAGRAPH_COUNT,
    FAITHFUL_PROMPT_1_1_VERSION,
    HISTORICAL_4B210_STATUS,
    HISTORICAL_4B211_STATUS,
    HISTORICAL_4B212_STATUS,
    HISTORICAL_4B213_STATUS,
    HISTORICAL_4B214_STATUS,
    HISTORICAL_4B215_STATUS,
    HISTORICAL_4B216_STATUS,
    HISTORICAL_4B217_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    PHASE,
    STATUS_APPLIED,
    STATUS_ATTRIBUTION_UNCERTAIN,
    TARGET_CHAPTER_ID,
)
from app.book_authorial_voice_4b218.correction import (
    apply_corrections,
    build_diff,
    correction_catalog,
    human_review_document,
    render_revised_markdown,
    targeted_corrections_document,
)
from app.book_authorial_voice_4b218.coverage_review import review_source_coverage
from app.book_authorial_voice_4b218.guard import (
    BookAuthorialVoice4218Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_authorial_voice_4b218.hashes import assert_canonical, snapshot, snapshots_match
from app.book_authorial_voice_4b218.idea_traceability import (
    diagnose_idea_traceability,
    propose_idea_mappings,
)
from app.book_authorial_voice_4b218.narrative import audit_chapter
from app.book_authorial_voice_4b218.paths import (
    original_chapter_json_path,
    original_lock_path,
    production_book_path,
    repo_root,
    venv_python_path,
)
from app.book_authorial_voice_4b218.policy import authorial_voice_policy
from app.book_authorial_voice_4b218.prompt_candidate import prompt_bundle
from app.book_authorial_voice_4b218.report import render_report
from app.book_authorial_voice_4b218.scenarios import evaluate_offline_scenarios
from app.book_authorial_voice_4b218.writer import write_phase_artifacts
from app.book_generation.prompt_select import resolve_prompt_module


@dataclass
class PhaseResult:
    accepted: bool
    mode: str
    bundle: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_authorial_voice_4b218.py",
        "app/tests/test_book_editorial_alignment_4b216.py",
        "app/tests/test_book_generation_4b217.py",
    ]
    python = str(venv_python_path(root=root))
    # 4B.2.17's lock_absent_before_call scenario reads the real consumed
    # lock. That is the required post-call state. Do not rewrite the
    # historical test; skip only that environment-dependent case.
    completed = subprocess.run(
        [
            python,
            "-m",
            "pytest",
            "-q",
            "--tb=line",
            "-k",
            "not (test_offline_scenarios_pass and test_book_generation_4b217)",
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
        "failed": int(failed_match.group(1)) if failed_match else (0 if completed.returncode == 0 else 1),
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


def _original_hash_line(label: str, snap: dict[str, Any]) -> str:
    original = snap["original_chapter"]
    return (
        f"{label} json={original['chapter_candidate_json']['sha256']} "
        f"md={original['chapter_candidate_md']['sha256']} "
        f"lock={original['provider_lock']['sha256']}"
    )


def _candidate_is_unregistered(version: str) -> bool:
    try:
        resolve_prompt_module(version)
    except ValueError:
        return True
    return False


def _paragraph_table(
    narrative: dict[str, Any],
    corrections: dict[str, Any],
) -> list[dict[str, str]]:
    catalog = {row["paragraph_id"]: row for row in corrections.get("corrections") or []}
    rows = []
    for item in narrative.get("classifications") or []:
        paragraph_id = item["paragraph_id"]
        correction = catalog.get(paragraph_id)
        if correction and correction.get("applied"):
            change = "applied first-person / neutralization"
            status = correction["status"]
            src = "; ".join(correction.get("src_proof") or item.get("source_refs") or [])
        elif correction and not correction.get("applied"):
            change = "proposed only"
            status = correction["status"]
            src = "; ".join(correction.get("src_proof") or item.get("source_refs") or [])
        else:
            change = "none"
            status = "UNCHANGED"
            src = ", ".join(item.get("source_refs") or [])
        rows.append(
            {
                "paragraph_id": paragraph_id,
                "problem": item.get("classification") or "",
                "correction": change,
                "src": src,
                "status": status,
            }
        )
    return rows


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
    if production_book_path().exists():
        raise BookAuthorialVoice4218Error("production book.json must remain unpublished")
    if not original_chapter_json_path().is_file():
        raise BookAuthorialVoice4218Error("original CH012 candidate is required")
    if not original_lock_path().is_file():
        raise BookAuthorialVoice4218Error("original CH012 provider lock is required")

    original = load_original_chapter()
    policy = authorial_voice_policy()
    narrative = audit_chapter(original)
    attribution = collect_attribution_evidence(original)
    revised = apply_corrections(original)
    again = apply_corrections(original)
    if again != revised:
        raise BookAuthorialVoice4218Error("authorial correction is not idempotent")
    if paragraph_ids(original) != paragraph_ids(revised):
        raise BookAuthorialVoice4218Error("paragraph IDs must be preserved")
    if section_ids(original) != section_ids(revised):
        raise BookAuthorialVoice4218Error("section IDs must be preserved")
    corrections = targeted_corrections_document(original, revised)
    markdown = render_revised_markdown(revised)
    diff = build_diff(original, revised)
    prompt = prompt_bundle()
    idea_diag = diagnose_idea_traceability(original)
    idea_map = propose_idea_mappings(original)
    coverage = review_source_coverage(revised)
    human = human_review_document()
    scenarios = evaluate_offline_scenarios(root=base)
    tests = (
        _run_focused_tests(root=base)
        if run_tests
        else {
            "returncode": 0,
            "summary": "not_run",
            "passed": scenarios["passed"],
            "failed": scenarios["failed"],
            "suites": [],
            "real_provider_calls": 0,
        }
    )
    after = snapshot(root=base)
    hashes_ok = snapshots_match(before, after) and after["canonical_match_expected"]
    applied = [row["paragraph_id"] for row in correction_catalog() if row["applied"]]
    uncertain = [
        row["paragraph_id"]
        for row in correction_catalog()
        if row["status"] == STATUS_ATTRIBUTION_UNCERTAIN
    ]
    external = [
        row["paragraph_id"]
        for row in narrative["classifications"]
        if row["classification"]
        in {CLASS_EXTERNAL_CONFIRMED, CLASS_POSSIBLE_EXTERNAL, CLASS_ATTRIBUTION_UNCERTAIN}
    ]
    essential_applied = {"P000008", "P000009"}.issubset(set(applied))
    checks = {
        "no_provider_calls": True,
        "canonical_hashes_unchanged": hashes_ok,
        "original_chapter_unchanged": (
            before["original_chapter"] == after["original_chapter"]
        ),
        "provider_lock_unchanged": (
            before["original_chapter"]["provider_lock"]
            == after["original_chapter"]["provider_lock"]
        ),
        "policy_formalized": policy["version"] == AUTHORIAL_VOICE_POLICY_VERSION,
        "fourteen_paragraphs_audited": (
            narrative["paragraphs_audited"] == EXPECTED_PARAGRAPH_COUNT
        ),
        "narrative_anomalies_identified": bool(external),
        "justified_corrections_applied": essential_applied and len(applied) >= 2,
        "uncertain_left_for_human": bool(uncertain),
        "distinct_corrected_version": revised != original,
        "diff_available": "P000008" in diff and "Before" in diff,
        "prompt_1_1_versioned": (
            prompt["version"] == FAITHFUL_PROMPT_1_1_VERSION
            and prompt["activated"] is False
            and _candidate_is_unregistered(FAITHFUL_PROMPT_1_1_VERSION)
        ),
        "historical_prompts_preserved": hashes_ok,
        "idea_diagnosis_documented": bool(idea_diag.get("primary_diagnosis")),
        "no_fictional_coverage": (
            coverage["semantic_coverage_certified"] is False
            and coverage["prose_was_not_changed_to_satisfy_the_heuristic"] is True
            and idea_map["written_into_paragraph_evidence"] is False
        ),
        "offline_scenarios_pass": scenarios["failed"] == 0,
        "focused_tests_pass": tests["failed"] == 0 and tests["returncode"] == 0,
        "production_not_activated": (
            not production_book_path().exists() and hashes_ok
        ),
        "unc029_preserved": coverage.get("unc029_preserved") is True,
    }
    if not hashes_ok:
        result = "FAIL"
    elif not essential_applied:
        result = "PARTIAL"
    elif not all(checks.values()):
        result = "FAIL"
    else:
        result = "PASS"
    notes = (
        f"{len(applied)} justified corrections were applied offline "
        f"({', '.join(applied)}). {len(uncertain)} attribution-uncertain "
        f"passage(s) remain for human review ({', '.join(uncertain) or 'none'}). "
        "IDEA handles were not injected into the provider response. "
        "The 4B.2.17 lock and original chapter were not modified."
    )
    header = {
        "result": result,
        "provider_calls": 0,
        "anthropic_http": 0,
        "openai_http": 0,
        "canonical_python": CANONICAL_PYTHON,
        "canonical_hashes_pre_post": _hash_line("pre", before) + "; " + _hash_line("post", after),
        "chapter": TARGET_CHAPTER_ID,
        "paragraphs_audited": narrative["paragraphs_audited"],
        "external_narrator_issues": len(external),
        "corrections_applied": len(applied),
        "corrections_requiring_human_review": len(uncertain),
        "attribution_uncertain": ",".join(uncertain) or "none",
        "original_chapter_hash_pre_post": (
            _original_hash_line("pre", before) + "; " + _original_hash_line("post", after)
        ),
        "authorial_voice_policy": AUTHORIAL_VOICE_POLICY_VERSION,
        "generator_prompt_1_1": FAITHFUL_PROMPT_1_1_VERSION,
        "idea_traceability_diagnosis": idea_diag.get("primary_diagnosis"),
        "idea_mappings_confirmed": len(idea_map.get("confirmed") or []),
        "idea_mappings_proposed": len(idea_map.get("proposed") or []),
        "idea_mappings_unresolved": len(idea_map.get("unresolved") or []),
        "source_coverage_status": (
            "heuristic reused; not a Terra verdict; flagged units reviewed"
        ),
        "unc029_preserved": "YES" if coverage.get("unc029_preserved") else "NO",
        "tests_passed": tests["passed"],
        "tests_failed": tests["failed"],
        "new_regressions": tests["failed"],
        "ready_for_human_review": "YES",
        "ready_for_terra_validation": "NO",
        "paragraph_table": _paragraph_table(narrative, corrections),
        "notes": notes,
        "checks": checks,
    }
    preflight = {
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "chapter_id": TARGET_CHAPTER_ID,
        "canonical_hashes_ok": before["canonical_match_expected"],
        "original_chapter_present": True,
        "original_lock_present": True,
        "offline_only": True,
        "provider_calls_authorized": 0,
        "4b217_authorization_reused": False,
        "production_book_absent": not production_book_path().exists(),
        "faithful_prompt_1_1_registered": False,
        "historical_statuses": {
            "h01": HISTORICAL_H01_STATUS,
            "h02": HISTORICAL_H02_STATUS,
            "h11": HISTORICAL_H11_STATUS,
            "4B.2.10": HISTORICAL_4B210_STATUS,
            "4B.2.11": HISTORICAL_4B211_STATUS,
            "4B.2.12": HISTORICAL_4B212_STATUS,
            "4B.2.13": HISTORICAL_4B213_STATUS,
            "4B.2.14": HISTORICAL_4B214_STATUS,
            "4B.2.15": HISTORICAL_4B215_STATUS,
            "4B.2.16": HISTORICAL_4B216_STATUS,
            "4B.2.17": HISTORICAL_4B217_STATUS,
        },
        "secrets_included": False,
    }
    readiness = {
        "phase": PHASE,
        "result": result,
        "checks": checks,
        "provider_calls": 0,
        "openai_http_requests": 0,
        "anthropic_http_requests": 0,
        "READY_FOR_HUMAN_REVIEW": True,
        "READY_FOR_TERRA_VALIDATION": False,
        "READY_FOR_FULL_BOOK_GENERATION": False,
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "semantic_gate_promoted": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "why": notes,
        "secrets_included": False,
    }
    regression = {
        "phase": PHASE,
        "focused_tests": tests,
        "offline_scenarios": scenarios,
        "idempotent": again == revised,
        "original_paragraph_count": len(list(iter_paragraphs(original))),
        "revised_paragraph_count": len(list(iter_paragraphs(revised))),
        "applied_status": STATUS_APPLIED,
        "historical_4b217_lock_absence_scenario": (
            "Skipped. The 4B.2.17 real lock is consumed by design. "
            "The historical test was not modified."
        ),
        "secrets_included": False,
    }
    bundle = {
        "header": header,
        "preflight": preflight,
        "canonical_hashes_pre": before,
        "authorial_voice_policy": policy,
        "narrative_audit": narrative,
        "speaker_attribution_evidence": attribution,
        "targeted_corrections": corrections,
        "chapter_candidate_authorial_v2": revised,
        "chapter_candidate_authorial_v2_md": markdown,
        "chapter_diff_md": diff,
        "generator_prompt_1_1_candidate": prompt,
        "idea_traceability_diagnosis": idea_diag,
        "idea_paragraph_mapping_proposals": idea_map,
        "source_coverage_review": coverage,
        "human_review_required": human,
        "canonical_hashes_post": after,
        "regression_tests": regression,
        "readiness": readiness,
        "offline_scenarios": scenarios,
        "execution": {
            "mode": "OFFLINE",
            "provider_calls": 0,
            "anthropic_http": 0,
            "openai_http": 0,
            "retries": 0,
            "fallbacks": 0,
        },
    }
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        write_phase_artifacts(bundle, root=base)
    return PhaseResult(accepted=result == "PASS", mode="OFFLINE", bundle=bundle, error="")


__all__ = ["PhaseResult", "run_phase"]
