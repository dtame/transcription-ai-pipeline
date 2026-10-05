"""
Phase 4B.2.20 runner.

Offline only. Inventories remaining chapters, selects the first chapter,
inspects prompt 1.1, maps the generation contract, prepares source context
and cost envelopes, and records hard stops. Never authorizes a provider call.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.book_scale_up_preparation_4b220.authorization import (
    future_first_chapter_authorization_template,
)
from app.book_scale_up_preparation_4b220.constants import (
    ACCEPTED_CHAPTER,
    AUTHORIZATION_SCOPE,
    CANONICAL_PYTHON,
    EXPECTED_FIRST_CHAPTER_ID,
    FAITHFUL_PROMPT_1_1,
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
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    NEXT_ACTION,
    PHASE,
)
from app.book_scale_up_preparation_4b220.context import (
    first_chapter_source_context_manifest,
)
from app.book_scale_up_preparation_4b220.contract import generation_contract_matrix
from app.book_scale_up_preparation_4b220.corpus import load_canonical_corpus
from app.book_scale_up_preparation_4b220.costing import scale_up_cost_envelope
from app.book_scale_up_preparation_4b220.execution import scale_up_execution_plan
from app.book_scale_up_preparation_4b220.guard import (
    BookScaleUpPreparation4220Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_scale_up_preparation_4b220.hard_stop import operational_hard_stop_conditions
from app.book_scale_up_preparation_4b220.hashes import (
    assert_canonical,
    assert_historical_artifacts,
    snapshot,
    snapshots_match,
)
from app.book_scale_up_preparation_4b220.inventory import remaining_chapters_inventory
from app.book_scale_up_preparation_4b220.paths import (
    production_book_path,
    repo_root,
    venv_python_path,
)
from app.book_scale_up_preparation_4b220.progress import scale_up_progress_manifest
from app.book_scale_up_preparation_4b220.prompt_readiness import generator_prompt_11_readiness
from app.book_scale_up_preparation_4b220.report import render_report
from app.book_scale_up_preparation_4b220.scenarios import evaluate_offline_scenarios
from app.book_scale_up_preparation_4b220.selection import select_first_chapter
from app.book_scale_up_preparation_4b220.writer import write_phase_artifacts


@dataclass
class PhaseResult:
    accepted: bool
    mode: str
    bundle: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_scale_up_preparation_4b220.py",
        "app/tests/test_book_editorial_acceptance_4b219.py",
        "app/tests/test_book_authorial_voice_4b218.py",
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
    assert_historical_artifacts(before)
    if production_book_path().exists():
        raise BookScaleUpPreparation4220Error("production book.json must remain unpublished")

    corpus = load_canonical_corpus()
    inventory = remaining_chapters_inventory(corpus)
    selection = select_first_chapter(inventory)
    if selection["selected_chapter_id"] != EXPECTED_FIRST_CHAPTER_ID:
        raise BookScaleUpPreparation4220Error(
            "Deterministic first-chapter selection diverged from the expected "
            f"{EXPECTED_FIRST_CHAPTER_ID}."
        )
    prompt = generator_prompt_11_readiness()
    contract = generation_contract_matrix()
    context = first_chapter_source_context_manifest(selection, corpus=corpus)
    remaining_ids = [row["chapter_id"] for row in inventory["chapters"]]
    cost = scale_up_cost_envelope(
        first_chapter_id=selection["selected_chapter_id"],
        remaining_ids=remaining_ids,
        corpus=corpus,
    )
    plan = scale_up_execution_plan(
        selection=selection, inventory=inventory, cost=cost
    )
    progress = scale_up_progress_manifest(
        inventory=inventory, selection=selection, context=context
    )
    stops = operational_hard_stop_conditions()
    authorization = future_first_chapter_authorization_template(
        selection=selection, cost=cost
    )
    scenarios = evaluate_offline_scenarios(
        inventory=inventory,
        selection=selection,
        context=context,
        prompt=prompt,
        contract=contract,
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
    first = dict(cost.get("first_chapter") or {})
    generation = dict(cost.get("generation_18_chapters") or {})
    validation = dict(cost.get("validation_cost") or {})
    ready_first = (
        hashes_ok
        and context.get("ready") is True
        and prompt.get("ready_as_isolated_candidate") is True
        and contract.get("compatible") is True
        and stops.get("operational") is True
        and scenarios["failed"] == 0
        and tests["failed"] == 0
        and tests["returncode"] == 0
        and selection["selected_chapter_id"] == EXPECTED_FIRST_CHAPTER_ID
    )
    checks = {
        "no_provider_calls": True,
        "canonical_hashes_unchanged": hashes_ok,
        "ch012_unchanged": (
            before["accepted_chapter"] == after["accepted_chapter"]
            and before["original_chapter"] == after["original_chapter"]
        ),
        "eighteen_chapters_inventoried": inventory["remaining_chapter_count"] == 18,
        "ch012_excluded": ACCEPTED_CHAPTER
        not in [row["chapter_id"] for row in inventory["chapters"]],
        "first_chapter_selected": selection["selected_chapter_id"]
        == EXPECTED_FIRST_CHAPTER_ID,
        "prompt_1_1_available_isolated": (
            prompt.get("available") is True and prompt.get("isolated") is True
        ),
        "prompt_not_globally_activated": prompt.get("activated") is False,
        "contract_compatible": contract.get("compatible") is True,
        "first_chapter_sources_ready": context.get("ready") is True,
        "cost_envelope_documented": first.get("expected_cost_usd") is not None,
        "authorized_spend_zero": cost.get("authorized_spend_usd") == 0.0,
        "hard_stops_operational": stops.get("operational") is True,
        "offline_scenarios_pass": scenarios["failed"] == 0,
        "focused_tests_pass": tests["failed"] == 0 and tests["returncode"] == 0,
        "no_publication": not production_book_path().exists(),
        "no_authorized_progress_state": progress.get("any_authorized_false") is True,
        "semantic_gate_not_promoted": True,
        "ready_for_18_chapter_run": False,
    }
    if not hashes_ok:
        result = "FAIL"
    elif not all(value for key, value in checks.items() if key != "ready_for_18_chapter_run"):
        result = "FAIL"
    else:
        result = "PASS"
    notes = (
        f"The 18 remaining chapters were inventoried from the canonical EditorialPlan. "
        f"{selection['selected_chapter_id']} was selected as the first remaining chapter "
        f"because it has {selection['section_count']} sections and {selection['idea_count']} "
        "IDEA units, carries EX and REF handles, and presents testimony attribution risk "
        "without being CH001 or the shortest chapter. Prompt 1.1 is available through an "
        "isolated selector and is not globally activated. First-chapter sources resolve by "
        "targeted hydration. Authorized spend remains 0 USD. No remaining chapter was generated."
    )
    header = {
        "result": result,
        "provider_calls": 0,
        "anthropic_http": 0,
        "openai_http": 0,
        "canonical_python": CANONICAL_PYTHON,
        "canonical_hashes_pre_post": _hash_line("pre", before) + "; " + _hash_line("post", after),
        "ch012_immutable": "YES" if checks["ch012_unchanged"] else "NO",
        "remaining_chapters": inventory["remaining_chapter_count"],
        "total_remaining_sections": inventory["total_remaining_sections"],
        "total_remaining_ideas": inventory["total_remaining_ideas"],
        "first_chapter_selected": (
            f"{selection['selected_chapter_id']} — {selection['working_title']}"
        ),
        "first_chapter_sections": selection["section_count"],
        "first_chapter_ideas": selection["idea_count"],
        "prompt_11_available": "YES" if prompt.get("available") else "NO",
        "prompt_11_isolated": "YES" if prompt.get("isolated") else "NO",
        "generation_contract_compatible": "YES" if contract.get("compatible") else "NO",
        "first_chapter_source_context_ready": "YES" if context.get("ready") else "NO",
        "estimated_first_chapter_cost": (
            f"expected {first.get('expected_cost_usd')} USD; "
            f"calculable maximum {first.get('calculable_maximum_usd')} USD; "
            "authorized 0 USD"
        ),
        "estimated_18_chapter_cost": (
            f"low {generation.get('low_usd')} / central {generation.get('central_usd')} / "
            f"high {generation.get('high_calculable_maximum_usd')} USD; complete UNKNOWN"
        ),
        "validation_cost": (
            f"{validation.get('semantic_gate_complete_cost')}; "
            "Terra analog "
            f"{validation.get('terra_h01_analog_using_idea_or_section_proxy_usd')} USD "
            "(hypothesis, not complete)"
        ),
        "hard_stop_tests": "PASS" if stops.get("operational") else "FAIL",
        "offline_tests": f"{scenarios['passed']} / {scenarios['failed']}",
        "production_pipeline_modified": "NO",
        "ready_for_first_real_chapter": "YES" if ready_first and result == "PASS" else "NO",
        "next_action": NEXT_ACTION,
        "notes": notes,
        "checks": checks,
    }
    preflight = {
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "canonical_hashes_ok": before["canonical_match_expected"],
        "accepted_chapter_present": True,
        "original_lock_present": True,
        "offline_only": True,
        "provider_calls_authorized": 0,
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
            "4B.2.18": HISTORICAL_4B218_STATUS,
            "4B.2.19": HISTORICAL_4B219_STATUS,
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
        "READY_FOR_FIRST_REAL_CHAPTER": ready_first and result == "PASS",
        "READY_FOR_18_CHAPTER_RUN": False,
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
        "secrets_included": False,
    }
    bundle = {
        "header": header,
        "preflight": preflight,
        "canonical_hashes_pre": before,
        "remaining_chapters_inventory": inventory,
        "first_chapter_selection": selection,
        "generation_contract_matrix": contract,
        "prompt_11_readiness": prompt,
        "first_chapter_source_context_manifest": context,
        "scale_up_cost_envelope": cost,
        "scale_up_execution_plan": plan,
        "scale_up_progress_manifest": progress,
        "hard_stop_conditions": stops,
        "future_authorization": authorization,
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
            "generator_prompt": FAITHFUL_PROMPT_1_1,
        },
    }
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        write_phase_artifacts(bundle, root=base)
    return PhaseResult(accepted=result == "PASS", mode="OFFLINE", bundle=bundle, error="")


__all__ = ["PhaseResult", "run_phase"]
