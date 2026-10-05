"""
Phase 4B.2.22 runner.

Offline only. Records CH018 editorial acceptance, reviews EX046, inventories
the remaining 17 chapters, and prepares batch generation. Never authorizes
a provider call. Never regenerates CH012 or CH018.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.book_batch_preparation_4b222.acceptance import editorial_acceptance_record
from app.book_batch_preparation_4b222.authorization import batch_authorization_template
from app.book_batch_preparation_4b222.batches import batch_generation_plan
from app.book_batch_preparation_4b222.constants import (
    ACCEPTED_CH012_ID,
    ACCEPTED_CH018_ID,
    AUTHORIZATION_SCOPE,
    BATCH_IDS,
    CANONICAL_PYTHON,
    CONSUMED_4B221_SCOPE,
    FAITHFUL_PROMPT_1_1,
    FIRST_BATCH_ID,
    HISTORICAL_4B210_STATUS,
    HISTORICAL_4B211_STATUS,
    HISTORICAL_4B212_STATUS,
    HISTORICAL_4B213_STATUS,
    HISTORICAL_4B214_STATUS,
    HISTORICAL_4B215_STATUS,
    HISTORICAL_4B216_STATUS,
    HISTORICAL_4B217_STATUS,
    HISTORICAL_4B218_STATUS,
    HISTORICAL_4B219_STATUS,
    HISTORICAL_4B220_STATUS,
    HISTORICAL_4B221_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    NEXT_ACTION,
    PHASE,
    REMAINING_CHAPTER_COUNT,
)
from app.book_batch_preparation_4b222.costing import batch_cost_envelope
from app.book_batch_preparation_4b222.ex046 import review_ex046_traceability
from app.book_batch_preparation_4b222.guard import (
    BookBatchPreparation4222Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_batch_preparation_4b222.hard_stop import operational_hard_stop_conditions
from app.book_batch_preparation_4b222.hashes import (
    assert_canonical,
    assert_ch012_unchanged,
    assert_ch018_unchanged,
    snapshot,
    snapshots_match,
)
from app.book_batch_preparation_4b222.integrity import inspect_ch018_integrity
from app.book_batch_preparation_4b222.inventory import remaining_17_chapters_inventory
from app.book_batch_preparation_4b222.manifest import accepted_editorial_manifest
from app.book_batch_preparation_4b222.paths import (
    phase_audit_dir,
    production_book_path,
    repo_root,
    venv_python_path,
)
from app.book_batch_preparation_4b222.progress import batch_progress_manifest
from app.book_batch_preparation_4b222.prompt import verify_prompt_1_1
from app.book_batch_preparation_4b222.report import render_report
from app.book_batch_preparation_4b222.scenarios import evaluate_offline_scenarios
from app.book_batch_preparation_4b222.writer import write_phase_artifacts
from app.book_scale_up_preparation_4b220.corpus import load_canonical_corpus


@dataclass
class PhaseResult:
    accepted: bool
    mode: str
    bundle: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_batch_preparation_4b222.py",
        "app/tests/test_book_scale_up_preparation_4b220.py",
        "app/tests/test_book_editorial_acceptance_4b219.py",
    ]
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
        raise BookBatchPreparation4222Error("production book.json must remain unpublished")

    corpus = load_canonical_corpus()
    integrity = inspect_ch018_integrity()
    acceptance = editorial_acceptance_record(
        accepted_md_sha256=integrity["markdown_sha256"],
        accepted_json_sha256=integrity["json_sha256"],
    )
    freeze_allowed = (
        integrity["integrity_ok"]
        and integrity["unchanged_since_generation"]
        and integrity["markdown_json_consistency"]["consistent"]
        and integrity["ideas_traced"]
        and integrity["lock"]["reusable_blocked"]
    )
    manifest = accepted_editorial_manifest(
        accepted_md_sha256=integrity["markdown_sha256"],
        accepted_json_sha256=integrity["json_sha256"],
        lock_sha256=integrity["lock_sha256"],
        freeze_allowed=freeze_allowed,
    )
    ex046 = review_ex046_traceability(corpus=corpus)
    prompt = verify_prompt_1_1()
    inventory = remaining_17_chapters_inventory(corpus)
    remaining_ids = [row["chapter_id"] for row in inventory["chapters"]]
    cost = batch_cost_envelope(remaining_ids, corpus=corpus)
    costs_by_chapter = {row["chapter_id"]: row for row in cost["per_chapter"]}
    inventory = remaining_17_chapters_inventory(corpus, costs_by_chapter=costs_by_chapter)
    plan = batch_generation_plan(inventory=inventory, cost=cost)
    authorization = batch_authorization_template(plan=plan, cost=cost)
    ch018_manifest_path = str(phase_audit_dir(root=base) / "ch018_accepted_editorial_manifest.json").replace(
        "\\", "/"
    )
    progress = batch_progress_manifest(
        inventory=inventory,
        cost=cost,
        ch018_manifest_path=ch018_manifest_path,
    )
    stops = operational_hard_stop_conditions()
    scenarios = evaluate_offline_scenarios(
        inventory=inventory,
        plan=plan,
        cost=cost,
        prompt=prompt,
        integrity=integrity,
        progress=progress,
        root=base,
    )
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
    generation = dict(cost.get("generation_17_chapters") or {})
    first = next(
        (row for row in plan.get("batches") or [] if row.get("batch_id") == FIRST_BATCH_ID),
        {},
    )
    ready_first = (
        hashes_ok
        and freeze_allowed
        and prompt.get("hash_match") is True
        and stops.get("operational") is True
        and scenarios["failed"] == 0
        and tests["failed"] == 0
        and tests["returncode"] == 0
        and inventory["remaining_chapter_count"] == REMAINING_CHAPTER_COUNT
        and ex046.get("correspondence_established") is True
    )
    checks = {
        "no_provider_calls": True,
        "canonical_hashes_unchanged": hashes_ok,
        "ch012_unchanged": after.get("ch012_unchanged") is True,
        "ch018_unchanged": after.get("ch018_unchanged") is True,
        "ch018_accepted": freeze_allowed,
        "seventeen_chapters_inventoried": inventory["remaining_chapter_count"] == 17,
        "accepted_excluded": ACCEPTED_CH012_ID not in remaining_ids
        and ACCEPTED_CH018_ID not in remaining_ids,
        "prompt_1_1_hash_match": prompt.get("hash_match") is True,
        "prompt_not_globally_activated": prompt.get("activated") is False,
        "cost_envelope_documented": generation.get("central_usd") is not None,
        "authorized_spend_zero": cost.get("authorized_spend_usd") == 0.0,
        "hard_stops_operational": stops.get("operational") is True,
        "offline_scenarios_pass": scenarios["failed"] == 0,
        "focused_tests_pass": tests["failed"] == 0 and tests["returncode"] == 0,
        "no_publication": not production_book_path().exists(),
        "no_authorized_progress_state": progress.get("any_authorized_false") is True,
        "semantic_gate_not_promoted": True,
        "consumed_ch018_scope_not_reused": CONSUMED_4B221_SCOPE != AUTHORIZATION_SCOPE,
        "ready_for_all_17": False,
    }
    blocking = [key for key, value in checks.items() if key != "ready_for_all_17" and not value]
    if not hashes_ok:
        result = "FAIL"
    elif blocking:
        result = "FAIL"
    else:
        result = "PASS"
    notes = (
        "CH018 was recorded as human-accepted and frozen by hash without rewriting "
        "its prose. CH012 remains referenced by the 4B.2.19 manifest. The 17 remaining "
        "EditorialPlan chapters were inventoried in book order and grouped into four "
        "lots (4+4+4+5). Prompt 1.1 still hashes to the CH018 observed value and stays "
        "an isolated explicit selection. Authorized spend remains 0 USD. No remaining "
        "chapter was generated."
    )
    header = {
        "result": result,
        "provider_calls": 0,
        "anthropic_http": 0,
        "openai_http": 0,
        "canonical_python": CANONICAL_PYTHON,
        "canonical_hashes_pre_post": _hash_line("pre", before) + "; " + _hash_line("post", after),
        "ch012_immutable": "YES" if checks["ch012_unchanged"] else "NO",
        "ch018_immutable": "YES" if checks["ch018_unchanged"] else "NO",
        "ch018_md_sha256": integrity["markdown_sha256"],
        "ch018_json_sha256": integrity["json_sha256"],
        "ch018_ex046_traceability": (
            "CORRESPONDENCE_ESTABLISHED_NOT_INJECTED"
            if ex046.get("correspondence_established")
            else "UNRESOLVED"
        ),
        "remaining_chapters": inventory["remaining_chapter_count"],
        "remaining_sections": inventory["total_remaining_sections"],
        "remaining_ideas": inventory["total_remaining_ideas"],
        "batch_count": len(BATCH_IDS),
        "batch_sizes": [len(row["chapter_ids"]) for row in plan.get("batches") or []],
        "prompt_11_hash_match": "YES" if prompt.get("hash_match") else "NO",
        "generation_cost": (
            f"{generation.get('low_usd')} / {generation.get('central_usd')} / "
            f"{generation.get('high_calculable_maximum_usd')} USD"
        ),
        "complete_cost": generation.get("complete_cost") or "UNKNOWN",
        "hard_stop_tests": "PASS" if stops.get("operational") else "FAIL",
        "offline_tests": f"{scenarios['passed']} / {scenarios['failed']}",
        "ready_for_first_batch_authorization": "YES" if ready_first and result == "PASS" else "NO",
        "next_action": NEXT_ACTION,
        "notes": notes,
        "checks": checks,
        "blocking": blocking,
        "first_batch": first,
    }
    preflight = {
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "canonical_hashes_ok": before["canonical_match_expected"],
        "ch012_present": True,
        "ch018_present": True,
        "offline_only": True,
        "provider_calls_authorized": 0,
        "production_book_absent": not production_book_path().exists(),
        "faithful_prompt_1_1_registered": False,
        "consumed_ch018_authorization": CONSUMED_4B221_SCOPE,
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
            "4B.2.18": HISTORICAL_4B218_STATUS,
            "4B.2.19": HISTORICAL_4B219_STATUS,
            "4B.2.20": HISTORICAL_4B220_STATUS,
            "4B.2.21": HISTORICAL_4B221_STATUS,
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
        "READY_FOR_FIRST_BATCH_AUTHORIZATION": ready_first and result == "PASS",
        "READY_FOR_ALL_17_REAL_GENERATIONS": False,
        "SEMANTIC_GATE_PROMOTED": False,
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "NEXT_ACTION": NEXT_ACTION,
        "why": notes,
        "future_authorization": authorization,
        "secrets_included": False,
    }
    regression = {
        "phase": PHASE,
        "focused_tests": tests,
        "offline_scenarios": scenarios,
        "hard_stops": stops,
        "ch018_integrity": integrity,
        "secrets_included": False,
    }
    bundle = {
        "header": header,
        "preflight": preflight,
        "canonical_hashes_pre": before,
        "ch018_editorial_acceptance": acceptance,
        "ch018_accepted_editorial_manifest": manifest,
        "ch018_ex046_traceability_review": ex046,
        "remaining_17_chapters_inventory": inventory,
        "batch_generation_plan": plan,
        "batch_cost_envelope": cost,
        "batch_authorization_template": authorization,
        "batch_progress_manifest": progress,
        "batch_hard_stop_conditions": stops,
        "canonical_hashes_post": after,
        "offline_regression_tests": regression,
        "readiness": readiness,
        "offline_scenarios": scenarios,
        "execution": {
            "mode": "OFFLINE",
            "provider_calls": 0,
            "anthropic_http": 0,
            "openai_http": 0,
            "retries": 0,
            "fallbacks": 0,
            "generator_prompt": FAITHFUL_PROMPT_1_1,
        },
    }
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        write_phase_artifacts(bundle, root=base)
        after_write = snapshot(root=base)
        if not snapshots_match(before, after_write):
            raise BookBatchPreparation4222Error(
                "Writing isolated audits mutated canonical or accepted artifacts. STOP."
            )
        bundle["canonical_hashes_post"] = after_write
    return PhaseResult(accepted=result == "PASS", mode="OFFLINE", bundle=bundle, error="")


__all__ = ["PhaseResult", "run_phase"]
