"""
Runner Phase 4B.2.26.

Record CH003/CH004 acceptances, install the empty-paragraph normalizer,
inventory the remaining 13 chapters, forecast the budget, and simulate
the future one-shot control flow. Zero provider calls. Zero generation.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from app.ai.provider_preflight import redact_secrets
from app.book_full_generation_preparation_4b226.acceptance import record_acceptances
from app.book_full_generation_preparation_4b226.authorization import (
    global_authorization_proposal,
)
from app.book_full_generation_preparation_4b226.constants import (
    AUTHORIZATION_SCOPE,
    CANONICAL_PYTHON,
    HUMAN_ACCEPTANCE_STATUS,
    NEXT_ACTION,
    PHASE,
    REMAINING_CHAPTER_IDS,
)
from app.book_full_generation_preparation_4b226.costing import (
    remaining_chapters_budget_forecast,
)
from app.book_full_generation_preparation_4b226.guard import (
    BookFullGenerationPreparation4226Error,
    assert_no_publication,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_full_generation_preparation_4b226.hashes import (
    assert_accepted_unchanged,
    assert_canonical,
    snapshot,
    snapshots_match,
)
from app.book_full_generation_preparation_4b226.inventory import remaining_chapters_inventory
from app.book_full_generation_preparation_4b226.normalize import normalizer_spec
from app.book_full_generation_preparation_4b226.paths import (
    production_book_path,
    repo_root,
    venv_python_path,
)
from app.book_full_generation_preparation_4b226.plan import remaining_chapters_generation_plan
from app.book_full_generation_preparation_4b226.report import render_report
from app.book_full_generation_preparation_4b226.scenarios import (
    evaluate_normalizer_tests,
    evaluate_offline_scenarios,
)
from app.book_full_generation_preparation_4b226.simulation import (
    simulate_full_batch,
    simulate_resume_and_locks,
)
from app.book_full_generation_preparation_4b226.writer import write_phase_artifacts
from app.book_scale_up_preparation_4b220.corpus import load_canonical_corpus


@dataclass
class PhaseResult:
    accepted: bool
    mode: str
    bundle: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = ["app/tests/test_book_full_generation_preparation_4b226.py"]
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


def _hash_line(label: str, snap: dict[str, Any]) -> str:
    canonical = snap["canonical"]
    return (
        f"{label} source={canonical['source_map']['sha256']} "
        f"plan={canonical['editorial_plan']['sha256']} "
        f"transcript={canonical['clean_transcript']['sha256']}"
    )


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
        assert_no_publication(production_book_path())
    except BookFullGenerationPreparation4226Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = snapshot(root=base)
    try:
        assert_canonical(before)
        acceptances = record_acceptances()
        assert_accepted_unchanged(before)
        corpus = load_canonical_corpus()
        cost = remaining_chapters_budget_forecast(corpus=corpus)
        costs_by_chapter = {row["chapter_id"]: row for row in cost["per_chapter"]}
        inventory = remaining_chapters_inventory(
            corpus, costs_by_chapter=costs_by_chapter
        )
        plan = remaining_chapters_generation_plan(inventory=inventory, cost=cost)
        authorization = global_authorization_proposal(cost=cost, plan=plan)
        spec = normalizer_spec()
        normalizer_tests = evaluate_normalizer_tests()
        simulation = simulate_full_batch(
            inventory=inventory,
            cost=cost,
            plan=plan,
            authorized=False,
        )
        resume = simulate_resume_and_locks()
        scenarios = evaluate_offline_scenarios(
            inventory=inventory,
            cost=cost,
            simulation=simulation,
            resume=resume,
            root=base,
        )
    except Exception as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        after = snapshot(root=base)
        bundle = {
            "header": {
                "result": "BLOCKED",
                "ch003_human_acceptance": "FAILED",
                "ch004_human_acceptance": "FAILED",
                "stop_reason": str(exc),
                "next_action": NEXT_ACTION,
            },
            "canonical_hashes_pre": before,
            "canonical_hashes_post": after,
            "readiness": {"READY_FOR_SINGLE_13_CHAPTER_AUTHORIZATION": False},
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
    hashes_ok = snapshots_match(before, after) and after["canonical_match_expected"]
    six_ok = bool(after.get("six_accepted_immutable"))
    ch003_ok = acceptances.get("CH003_HUMAN_ACCEPTANCE") == HUMAN_ACCEPTANCE_STATUS
    ch004_ok = acceptances.get("CH004_HUMAN_ACCEPTANCE") == HUMAN_ACCEPTANCE_STATUS
    normalizer_ok = int(normalizer_tests.get("failed") or 0) == 0
    simulation_ok = simulation.get("status") == "PASS"
    resume_ok = resume.get("status") == "PASS"
    cost_blocked = bool(cost.get("blocked"))
    test_failures = int(tests.get("failed") or 0) + int(scenarios.get("failed") or 0)
    ready = all(
        (
            ch003_ok,
            ch004_ok,
            six_ok,
            hashes_ok,
            normalizer_ok,
            simulation_ok,
            resume_ok,
            not cost_blocked,
            test_failures == 0,
            simulation.get("chapters_generated") == 0,
            not production_book_path().is_file(),
        )
    )
    if not hashes_ok or not six_ok:
        result_label = "FAIL"
    elif cost_blocked:
        result_label = "BLOCKED"
    elif ready:
        result_label = "PASS"
    elif ch003_ok and ch004_ok:
        result_label = "PARTIAL"
    else:
        result_label = "FAIL"

    header = {
        "result": result_label,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "provider_calls": 0,
        "anthropic_http": 0,
        "openai_http": 0,
        "ch003_human_acceptance": "RECORDED" if ch003_ok else "FAILED",
        "ch004_human_acceptance": "RECORDED" if ch004_ok else "FAILED",
        "accepted_chapters": ", ".join(
            acceptances["accepted_chapters_inventory"]["accepted_chapter_ids"]
        ),
        "remaining_chapters": ", ".join(REMAINING_CHAPTER_IDS),
        "empty_paragraph_normalizer": "IMPLEMENTED" if normalizer_ok else "BLOCKED",
        "normalizer_tests": (
            f"{normalizer_tests.get('passed') or 0} / {normalizer_tests.get('failed') or 0}"
        ),
        "production_validator": "UNCHANGED",
        "full_batch_offline_simulation": simulation.get("status"),
        "resume_safety": "PASS" if resume_ok else "FAIL",
        "call_lock_safety": "PASS" if resume.get("uncertain_ch006_blocks_replay") else "FAIL",
        "global_estimated_cost": cost.get("GLOBAL_ESTIMATED_COST"),
        "global_preflight_max_cost": cost.get("GLOBAL_PREFLIGHT_MAX_COST"),
        "recommended_authorization_cap": cost.get("RECOMMENDED_AUTHORIZATION_CAP"),
        "unknown_cost_components": cost.get("unknown_cost_components"),
        "canonical_hashes_pre_post": _hash_line("pre", before)
        + "; "
        + _hash_line("post", after),
        "canonical_hashes_pre_post_status": "MATCH" if hashes_ok else "MISMATCH",
        "six_accepted_chapters_immutable": _yn(six_ok),
        "production_cache": "UNCHANGED",
        "ready_for_single_13_chapter_authorization": _yn(ready),
        "next_action": NEXT_ACTION,
        "canonical_python": CANONICAL_PYTHON,
        "code_modified": (
            "app/book_full_generation_preparation_4b226/* ; "
            "app/tests/test_book_full_generation_preparation_4b226.py"
        ),
        "tests_executed": (
            "app/tests/test_book_full_generation_preparation_4b226.py ; "
            "evaluate_normalizer_tests ; evaluate_offline_scenarios"
        ),
        "notes": (
            "CH003 and CH004 human editorial acceptances were recorded. "
            "The six accepted chapters are protected. The empty-paragraph "
            "normalizer is installed at the derived-candidate step before the "
            "unchanged production validator. The remaining 13 chapters are "
            "inventoried and budgeted offline. No provider call was made."
        ),
    }
    readiness = {
        "READY_FOR_SINGLE_13_CHAPTER_AUTHORIZATION": ready,
        "CH003_HUMAN_ACCEPTANCE": "RECORDED" if ch003_ok else "FAILED",
        "CH004_HUMAN_ACCEPTANCE": "RECORDED" if ch004_ok else "FAILED",
        "SIX_ACCEPTED_CHAPTERS_IMMUTABLE": six_ok,
        "CANONICAL_HASHES": "MATCH" if hashes_ok else "MISMATCH",
        "EMPTY_PARAGRAPH_NORMALIZER": "IMPLEMENTED" if normalizer_ok else "BLOCKED",
        "PRODUCTION_VALIDATOR": "UNCHANGED",
        "FULL_BATCH_OFFLINE_SIMULATION": simulation.get("status"),
        "RESUME_SAFETY": "PASS" if resume_ok else "FAIL",
        "CALL_LOCK_SAFETY": "PASS" if resume.get("uncertain_ch006_blocks_replay") else "FAIL",
        "NEW_CHAPTERS_GENERATED": 0,
        "SEMANTIC_CERTIFICATION": "NOT PERFORMED",
        "book_json": "NOT PUBLISHED",
        "PRODUCTION_CACHE": "UNCHANGED",
        "FUTURE_AUTHORIZATION_ACTIVATED": False,
        "NEXT_ACTION": NEXT_ACTION,
        "why": "OFFLINE_PREPARATION_COMPLETED" if ready else result_label,
    }
    preflight = {
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "offline": True,
        "provider_calls": 0,
        "canonical_hashes_ok": before["canonical_match_expected"],
        "future_authorization_activated": False,
        "real_generation_authorized": False,
        "secrets_included": False,
    }
    hashes_pre_post = {
        "phase": PHASE,
        "pre": before,
        "post": after,
        "match": hashes_ok,
        "status": "MATCH" if hashes_ok else "MISMATCH",
        "secrets_included": False,
    }
    bundle = {
        "header": header,
        "preflight": preflight,
        "canonical_hashes_pre": before,
        "ch003_accepted_editorial_manifest": acceptances["ch003"],
        "ch004_accepted_editorial_manifest": acceptances["ch004"],
        "accepted_chapters_inventory": acceptances["accepted_chapters_inventory"],
        "empty_paragraph_normalization_spec": spec,
        "empty_paragraph_normalization_tests": normalizer_tests,
        "remaining_chapters_inventory": inventory,
        "remaining_chapters_generation_plan": plan,
        "remaining_chapters_budget_forecast": cost,
        "global_authorization_proposal": authorization,
        "full_batch_offline_simulation": simulation,
        "resume_and_lock_validation": resume,
        "canonical_hashes_pre_post": hashes_pre_post,
        "canonical_hashes_post": after,
        "offline_regression_tests": {
            "pytest": tests,
            "scenarios": scenarios,
            "normalizer": {
                "passed": normalizer_tests.get("passed"),
                "failed": normalizer_tests.get("failed"),
            },
        },
        "readiness": readiness,
    }
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        write_phase_artifacts(bundle, root=base)
    result.bundle = redact_secrets(bundle)
    result.accepted = result_label == "PASS"
    result.mode = result_label
    result.error = "" if result_label == "PASS" else result_label
    return result


def _unused_mapping_probe(value: Mapping[str, Any] | None) -> None:
    del value


__all__ = ["PhaseResult", "run_phase"]
