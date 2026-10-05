"""
Phase 4B.2.16 runner.

Offline only. Builds the candidate policy, risk map, prompt, coverage
control, and pilot package. Never authorizes a provider call.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.book_editorial_alignment_4b216.constants import (
    AUTHORIZATION_SCOPE,
    CANONICAL_PYTHON,
    COVERAGE_CONTRACT_VERSION,
    EDITORIAL_POLICY_VERSION,
    FAITHFUL_PROMPT_VERSION,
    HISTORICAL_4B210_STATUS,
    HISTORICAL_4B211_STATUS,
    HISTORICAL_4B212_STATUS,
    HISTORICAL_4B213_STATUS,
    HISTORICAL_4B214_STATUS,
    HISTORICAL_4B215_STATUS,
    HISTORICAL_GENERATOR_PROMPT,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    HISTORICAL_SEMANTIC_CONTRACT,
    HUMAN_RESOLUTION_VERSION,
    PHASE,
    THEMATIC_RULES_VERSION,
)
from app.book_editorial_alignment_4b216.coverage import source_coverage_contract
from app.book_editorial_alignment_4b216.guard import (
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_editorial_alignment_4b216.hashes import snapshot, snapshots_match
from app.book_editorial_alignment_4b216.human_resolution import protocol_document
from app.book_editorial_alignment_4b216.paths import repo_root, venv_python_path
from app.book_editorial_alignment_4b216.pilot import pilot_budget_estimate, select_pilot
from app.book_editorial_alignment_4b216.policy import editorial_policy
from app.book_editorial_alignment_4b216.prompt_candidate import prompt_bundle
from app.book_editorial_alignment_4b216.prompt_review import current_prompt_review
from app.book_editorial_alignment_4b216.report import render_report
from app.book_editorial_alignment_4b216.risk_map import analyze_editorial_plan
from app.book_editorial_alignment_4b216.scenarios import evaluate_offline_scenarios
from app.book_editorial_alignment_4b216.semantic_alignment import semantic_gate_alignment
from app.book_editorial_alignment_4b216.writer import write_phase_artifacts
from app.book_generation.prompt_select import resolve_prompt_module
from app.book_generation.writer import production_book_absent


@dataclass
class PhaseResult:
    accepted: bool
    mode: str
    bundle: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_editorial_alignment_4b216.py",
        "app/tests/test_book_generation_4b1.py",
        "app/tests/test_book_semantic_gate_4b212.py",
        "app/tests/test_book_semantic_gate_4b215.py",
    ]
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
        "failed": int(failed_match.group(1)) if failed_match else (0 if completed.returncode == 0 else 1),
        "stderr_tail": "\n".join((completed.stderr or "").strip().splitlines()[-12:]),
        "suites": tests,
        "real_provider_calls": 0,
        "openai_http_requests": 0,
        "anthropic_http_requests": 0,
        "phase": PHASE,
        "canonical_python": python,
    }


def _candidate_is_unregistered() -> bool:
    try:
        resolve_prompt_module(FAITHFUL_PROMPT_VERSION)
    except ValueError:
        return True
    return False


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
    policy = editorial_policy()
    review = current_prompt_review()
    risk_map = analyze_editorial_plan()
    faithful = prompt_bundle()
    coverage = source_coverage_contract()
    semantic = semantic_gate_alignment()
    human = protocol_document()
    selection = select_pilot(risk_map)
    selected = selection["selected"]
    budget = pilot_budget_estimate(selected, root=base)
    scenarios = evaluate_offline_scenarios()
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
    hashes_ok = snapshots_match(before, after) and before["canonical_match_expected"]
    book_absent = production_book_absent("pastoral_retreat_v2_validation")
    structural = risk_map["structural_assignment"]["structurally_complete"]
    checks = {
        "no_provider_calls": True,
        "canonical_hashes_unchanged": hashes_ok,
        "historical_results_preserved": (
            HISTORICAL_H01_STATUS == "PARTIAL"
            and HISTORICAL_H02_STATUS == "PARTIAL"
            and HISTORICAL_H11_STATUS == "PARTIAL"
            and HISTORICAL_4B211_STATUS == "PARTIAL"
            and HISTORICAL_4B212_STATUS == "PASS"
            and HISTORICAL_4B213_STATUS == "PASS"
            and HISTORICAL_4B214_STATUS == "PASS"
            and HISTORICAL_4B215_STATUS == "PARTIAL"
            and HISTORICAL_4B210_STATUS == "PASS"
        ),
        "editorial_policy_explicit": policy["version"] == EDITORIAL_POLICY_VERSION,
        "transformations_defined": (
            len(policy["allowed_transformations"]) == 12
            and len(policy["forbidden_transformations"]) == 14
        ),
        "thematic_rules_defined": len(policy["thematic_rules"]) == 6,
        "historical_prompts_not_overwritten": (
            review["book_generator_1_0"]["matches_frozen_prompt"]
            and review["historical_prompts_modified"] is False
            and review["review_complete"] is True
        ),
        "faithful_prompt_available_and_inactive": (
            faithful["version"] == FAITHFUL_PROMPT_VERSION
            and faithful["activated"] is False
            and faithful["fundamental_rule_present"] is True
            and _candidate_is_unregistered()
        ),
        "coverage_specified_and_inactive": (
            coverage["version"] == COVERAGE_CONTRACT_VERSION
            and coverage["activated_in_production"] is False
        ),
        "semantic_gate_protections_retained": (
            semantic["contract"] == HISTORICAL_SEMANTIC_CONTRACT
            and semantic["contract_modified"] is False
            and semantic["contract_activated"] is False
            and semantic["automatic_block_to_pass"] is False
            and semantic["historical_h11_human_label"] == "UNSUPPORTED"
        ),
        "human_resolution_traceable": human["version"] == HUMAN_RESOLUTION_VERSION,
        "pilot_identified": (
            selected.get("chapter_id") not in {"", "CH001", "CH016"}
            and selected.get("generation_executed") is False
            and structural
        ),
        "budget_keeps_unknown": (
            budget["phase5"]["status"] == "UNKNOWN"
            and budget["phase5"]["counted_as_zero"] is False
            and budget["pilot_semantic_gate"]["actual_paragraph_count"] == "UNKNOWN"
        ),
        "offline_scenarios_pass": scenarios["failed"] == 0 and scenarios["scenario_count"] == 20,
        "production_pipeline_not_activated": hashes_ok,
        "no_chapter_generated": book_absent and selected.get("generation_executed") is False,
        "focused_tests_pass": tests["failed"] == 0 and tests["returncode"] == 0,
    }
    result = "PASS" if all(checks.values()) else "FAIL"
    partial_cost = budget["pilot_partial_generator_plus_gate_hypothesis"]["central_usd"]
    obstacles = [
        "Human review of this phase has not been recorded, so no real chapter is authorized.",
        "The faithful prompt is a candidate and is not the production prompt.",
        "Contract 2.0.2-candidate is not promoted.",
        "Generated paragraph count is UNKNOWN, so the Semantic Gate cost is a hypothesis.",
        "Phase 5 cost is UNKNOWN and is not treated as zero.",
        "The coverage control is specified and inactive.",
        "Historical h01, h02, h11, 4B.2.11, and 4B.2.15 remain PARTIAL.",
    ]
    header = {
        "result": result,
        "canonical_python": CANONICAL_PYTHON,
        "canonical_hashes": _hash_line("pre", before) + "; " + _hash_line("post", after),
        "editorial_policy": EDITORIAL_POLICY_VERSION,
        "faithful_prompt": FAITHFUL_PROMPT_VERSION,
        "thematic_rules": THEMATIC_RULES_VERSION,
        "source_coverage": COVERAGE_CONTRACT_VERSION + " INACTIVE",
        "semantic_alignment": HISTORICAL_SEMANTIC_CONTRACT + " UNMODIFIED",
        "human_resolution": HUMAN_RESOLUTION_VERSION,
        "pilot_chapter": selected.get("chapter_id"),
        "pilot_sections": selected.get("section_count"),
        "pilot_ideas": selected.get("idea_count"),
        "pilot_cost": (
            f"partial_generator_plus_gate_hypothesis central={partial_cost}; "
            "complete_total_including_phase5=UNKNOWN"
        ),
        "phase5_cost": "UNKNOWN",
        "tests_passed": tests["passed"],
        "tests_failed": tests["failed"],
        "new_regressions": tests["failed"],
        "ready_for_one_real_pilot_chapter": "NO",
        "obstacles": obstacles,
        "notes": (
            f"Structural assignment of {risk_map['structural_assignment']['assigned_idea_count']} "
            "ideas is complete. Semantic fitness of each grouping is not claimed. "
            f"Eligible ranking: {', '.join(selection['eligible_ranking'][:8])}. "
            "Offline scenarios are synthetic and are not Terra or Sonnet quality."
        ),
    }
    readiness = {
        "phase": PHASE,
        "result": result,
        "checks": checks,
        "provider_calls": 0,
        "openai_http_requests": 0,
        "anthropic_http_requests": 0,
        "historical_generator_prompt_modified": False,
        "historical_semantic_contract_modified": False,
        "production_pipeline_modified": False,
        "production_cache": "UNCHANGED",
        "book_json": "NOT PUBLISHED",
        "ready_for_one_real_pilot_chapter": "NO",
        "ready_for_full_real_book_generation": "NO",
        "next_action": "HUMAN REVIEW",
        "obstacles": obstacles,
        "secrets_included": False,
    }
    hash_document = {
        "phase": PHASE,
        "before": before,
        "after": after,
        "unchanged": hashes_ok,
        "expected_matched": before["canonical_match_expected"],
        "secrets_included": False,
    }
    bundle = {
        "header": header,
        "policy": policy,
        "prompt_review": review,
        "risk_map": risk_map,
        "faithful_prompt": faithful,
        "coverage": coverage,
        "semantic": semantic,
        "human": human,
        "candidates": {
            "phase": PHASE,
            "excluded_without_scoring": selection["excluded_without_scoring"],
            "eligible_ranking": selection["eligible_ranking"],
            "candidates": selection["candidates"],
            "secrets_included": False,
        },
        "selected": selected,
        "budget": budget,
        "scenarios": scenarios,
        "hashes": hash_document,
        "tests": tests,
        "readiness": readiness,
        "report": render_report(header),
    }
    if write_artifacts:
        write_phase_artifacts(bundle, root=base)
    return PhaseResult(accepted=result == "PASS", mode="OFFLINE", bundle=bundle)


__all__ = ["PhaseResult", "run_phase"]


# Imported for the authorization constant used by the CLI.
_ = AUTHORIZATION_SCOPE
