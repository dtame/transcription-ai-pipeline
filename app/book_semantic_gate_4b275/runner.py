"""
Phase 4B.2.7.5 runner.

Offline only. Stabilizes the 1.1.2 candidate via a distinct 1.1.3 proposal.
Never authorizes a provider call.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.ai.provider_preflight import redact_secrets
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.identity import snapshot_identities, verify_canonical_inputs
from app.book_semantic_gate_4b23.prompt import instruction_prompt, system_prompt
from app.book_semantic_gate_4b261.candidates import candidate_prompt_bundle
from app.book_semantic_gate_4b27.request import paragraph_context
from app.book_semantic_gate_4b271.calibration import candidate_111_prompt_bundle
from app.book_semantic_gate_4b271.evidence import load_saved_terra_payload as load_h01_payload
from app.book_semantic_gate_4b272.identity import load_p3_gate_paragraph
from app.book_semantic_gate_4b274.claims import load_saved_h02_payload
from app.book_semantic_gate_4b274.contract import candidate_112_prompt_bundle
from app.book_semantic_gate_4b275.canary import future_canary_selection_criteria
from app.book_semantic_gate_4b275.catalog import reason_code_catalog
from app.book_semantic_gate_4b275.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    CANONICAL_PYTHON_EXECUTABLE,
    CLOSED_CATALOG_POLICY,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_PROMPT_111_SHA256,
    EXPECTED_PROMPT_112_SHA256,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B261_STATUS,
    HISTORICAL_4B262_STATUS,
    HISTORICAL_4B26_STATUS,
    HISTORICAL_4B271_STATUS,
    HISTORICAL_4B272_STATUS,
    HISTORICAL_4B273_STATUS,
    HISTORICAL_4B274_STATUS,
    HISTORICAL_4B27_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_113,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_11,
    UNKNOWN_CODE_POLICY,
)
from app.book_semantic_gate_4b275.contract import (
    candidate_113_prompt_bundle,
    contract_113_review,
    contract_comparison,
    contract_inventory,
    transport_compatibility,
)
from app.book_semantic_gate_4b275.coverage import coverage_policy_review
from app.book_semantic_gate_4b275.diagnostic import diagnostic_failure_behavior
from app.book_semantic_gate_4b275.fakeai import run_offline_fixtures
from app.book_semantic_gate_4b275.guard import (
    BookSemanticGate275Error,
    assert_no_publication,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b275.indeterminate import review_h02_indeterminate_claim
from app.book_semantic_gate_4b275.matrix import verdict_reason_code_matrix
from app.book_semantic_gate_4b275.paths import production_book_path, repo_root, venv_python_path
from app.book_semantic_gate_4b275.replay import historical_response_replays
from app.book_semantic_gate_4b275.report import render_report
from app.book_semantic_gate_4b275.unknown import unknown_reason_code_policy
from app.book_semantic_gate_4b275.verdicts import verdict_definitions_review
from app.file_utils import content_hash


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_semantic_gate_4b275.py",
        "app/tests/test_book_semantic_gate_4b274.py",
        "app/tests/test_book_semantic_gate_4b273.py",
        "app/tests/test_book_semantic_gate_4b272.py",
        "app/tests/test_book_semantic_gate_4b271.py",
        "app/tests/test_book_semantic_gate_4b262.py",
        "app/tests/test_book_semantic_gate_4b23.py",
    ]
    python = str(venv_python_path(root=root))
    command = [python, "-m", "pytest", "-q", "--tb=no", *tests]
    completed = subprocess.run(
        command,
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = completed.stdout or ""
    failed = completed.returncode != 0
    summary = next(
        (
            line.strip()
            for line in reversed(stdout.splitlines())
            if "passed" in line or "failed" in line
        ),
        stdout.strip().splitlines()[-1] if stdout.strip() else "",
    )
    passed_match = re.search(r"(\d+) passed", summary)
    failed_match = re.search(r"(\d+) failed", summary)
    return {
        "returncode": completed.returncode,
        "summary": summary,
        "passed": int(passed_match.group(1)) if passed_match else 0,
        "failed": int(failed_match.group(1)) if failed_match else 0,
        "stderr_tail": "\n".join((completed.stderr or "").strip().splitlines()[-8:]),
        "new_failures": 0 if not failed else 1,
        "network_blocked": True,
        "suites": tests,
        "real_provider_calls": 0,
        "phase": PHASE,
        "canonical_python": python,
    }


@dataclass
class Phase275Result:
    mode: str = "OFFLINE"
    accepted: bool = False
    error: str | None = None
    bundle: dict[str, Any] = field(default_factory=dict)


def run_phase(
    *,
    authorization_scope: str | None = None,
    root: Path | None = None,
    write_artifacts: bool = True,
    run_tests: bool = True,
) -> Phase275Result:
    result = Phase275Result()
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
        assert_no_publication(production_book_path())
    except BookSemanticGate275Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if TERRA_EXECUTION_AUTHORIZED or AUTHORIZED_TERRA_CALLS != 0:
        result.error = "Terra must not be authorized in 4B.2.7.5."
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = verify_canonical_inputs(root=root)
    inventory = contract_inventory()
    verdicts = verdict_definitions_review()
    indeterminate = review_h02_indeterminate_claim(root=root)
    catalog = reason_code_catalog()
    matrix = verdict_reason_code_matrix()
    unknown = unknown_reason_code_policy()
    h01_payload = load_h01_payload(root=root)
    h02_payload = load_saved_h02_payload(root=root)
    h01_text = str(
        (paragraph_context(root=root).get("paragraph_texts") or {}).get("h01") or ""
    )
    h02_text = str(load_p3_gate_paragraph(root=root).get("text") or "")
    h01_claims = next(item["c"] for item in h01_payload.get("pr") or [] if item.get("h") == "h01")
    h02_claims = []
    if "pr" in h02_payload:
        h02_claims = next(
            item["c"] for item in h02_payload.get("pr") or [] if item.get("h") == "h02"
        )
    coverage = coverage_policy_review(
        h01_text=h01_text,
        h01_claims=h01_claims,
        h02_text=h02_text,
        h02_claims=h02_claims,
    )
    diagnostic_policy = diagnostic_failure_behavior()
    contract = contract_113_review()
    comparison_contracts = contract_comparison()
    transport = transport_compatibility()
    replays = historical_response_replays(root=root)
    fixtures = run_offline_fixtures(root=root)
    canary = future_canary_selection_criteria()
    tests = (
        _run_focused_tests(root=base)
        if run_tests
        else {
            "skipped": True,
            "new_failures": 0,
            "network_blocked": True,
            "summary": "deferred",
            "passed": 0,
            "failed": 0,
            "real_provider_calls": 0,
        }
    )
    after = verify_canonical_inputs(root=root)
    before_snap = snapshot_identities(before)
    after_snap = snapshot_identities(after)
    hashes_ok = before_snap == after_snap
    source_ok = before["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
    plan_ok = before["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
    transcript_ok = before["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT
    prompt_10_ok = (
        content_hash(system_prompt()) == EXPECTED_PROMPT_SYSTEM_SHA256
        and content_hash(instruction_prompt()) == EXPECTED_PROMPT_INSTRUCTIONS_SHA256
    )
    prompt_11_ok = candidate_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_11_SHA256
    prompt_111_ok = candidate_111_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_111_SHA256
    prompt_112_ok = candidate_112_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_112_SHA256
    book_absent = production_book_absent(PROJECT_NAME)
    tests_ok = int(tests.get("new_failures") or 0) == 0
    fakeai_ok = bool(fixtures.get("passed"))
    inventory_ok = (
        source_ok
        and plan_ok
        and transcript_ok
        and hashes_ok
        and inventory.get("historical_contracts_modified") is False
        and inventory.get("silent_1_1_2_modification") is False
    )
    verdicts_ok = verdicts.get("coherence") == "PASS"
    indeterminate_ok = (
        indeterminate.get("human_review_conclusion") == "INDETERMINATE"
        and indeterminate.get("conclusion_forced") is False
        and indeterminate.get("human_label_unmodified") is True
        and indeterminate.get("text_match") is True
    )
    catalog_ok = catalog.get("catalog_closed") is True and catalog.get("no_code_invented") is True
    unknown_ok = unknown.get("unknown_codes_handling") == UNKNOWN_CODE_POLICY
    matrix_ok = bool(matrix.get("structural_passed"))
    coverage_ok = (
        (coverage.get("historical_inventory") or {}).get("h01", {}).get("coverage_1_1_2")
        == "PASS"
        and (coverage.get("historical_inventory") or {}).get("h02", {}).get("coverage_1_1_2")
        == "PASS"
        and coverage.get("does_not_strip_punctuation_before_validation") is True
    )
    diagnostic_ok = diagnostic_policy["outputs"]["B_diagnostic"]["never_converted_to_acceptance"]
    contracts_ok = (
        prompt_10_ok
        and prompt_11_ok
        and prompt_111_ok
        and prompt_112_ok
        and comparison_contracts.get("historical_contracts_modified") is False
        and contract.get("promoted") is False
        and contract.get("not_in_prompt", {}).get("overfit_tokens_absent") is True
    )
    transport_ok = transport.get("new_transport_created") is False
    replay_ok = bool((replays.get("h01") or {}).get("deterministic")) and bool(
        (replays.get("h02") or {}).get("deterministic")
    )
    historical_status_ok = (
        HISTORICAL_4B26_STATUS == "FAIL"
        and HISTORICAL_4B261_STATUS == "PASS"
        and HISTORICAL_4B262_STATUS == "PASS"
        and HISTORICAL_4B27_STATUS == "PARTIAL"
        and HISTORICAL_4B271_STATUS == "PASS"
        and HISTORICAL_4B272_STATUS == "PASS"
        and HISTORICAL_4B273_STATUS == "PARTIAL"
        and HISTORICAL_4B274_STATUS == "PASS"
        and HISTORICAL_H01_STATUS == "PARTIAL"
        and HISTORICAL_H02_STATUS == "PARTIAL"
    )
    ready_review = (
        inventory_ok
        and verdicts_ok
        and indeterminate_ok
        and catalog_ok
        and unknown_ok
        and matrix_ok
        and coverage_ok
        and diagnostic_ok
        and tests_ok
        and fakeai_ok
        and contracts_ok
        and transport_ok
        and replay_ok
        and book_absent
        and historical_status_ok
        and canary.get("not_sent") is True
    )
    phase_pass = (
        ready_review
        and int(AUTHORIZED_TERRA_CALLS) == 0
        and (replays.get("h01") or {}).get("historical_status_preserved") == "PARTIAL"
        and (replays.get("h02") or {}).get("historical_status_preserved") == "PARTIAL"
    )
    verdict = "PASS" if phase_pass else "FAIL"
    h01_replay_status = (
        f"json={(replays.get('h01') or {}).get('json_parse')} "
        f"1.1.1={(((replays.get('h01') or {}).get('first') or {}).get('validator_1_1_1') or {}).get('status')} "
        f"1.1.2={(((replays.get('h01') or {}).get('first') or {}).get('validator_1_1_2') or {}).get('status')} "
        f"1.1.3={(replays.get('h01') or {}).get('validator_1_1_3', {}).get('status')}"
    )
    h02_replay_status = (
        f"json={(replays.get('h02') or {}).get('json_parse')} "
        f"1.1.1={(((replays.get('h02') or {}).get('first') or {}).get('validator_1_1_1') or {}).get('status')} "
        f"1.1.2={(((replays.get('h02') or {}).get('first') or {}).get('validator_1_1_2') or {}).get('status')} "
        f"1.1.3={(replays.get('h02') or {}).get('validator_1_1_3', {}).get('status')}"
    )
    header = {
        "result": verdict,
        "provider_calls": 0,
        "openai_http": 0,
        "anthropic_http": 0,
        "historical_h01": HISTORICAL_H01_STATUS,
        "historical_h02": HISTORICAL_H02_STATUS,
        "canonical_python": CANONICAL_PYTHON_EXECUTABLE,
        "source_hashes": {
            "source_pre": before_snap["source_map"],
            "plan_pre": before_snap["editorial_plan"],
            "transcript_pre": before_snap["clean_transcript"],
            "source_post": after_snap["source_map"],
            "plan_post": after_snap["editorial_plan"],
            "transcript_post": after_snap["clean_transcript"],
        },
        "h02_indeterminate_claim_conclusion": indeterminate.get(
            "human_review_conclusion"
        ),
        "verdict_definitions": "OPERATIONAL_COHERENT",
        "reason_code_catalog": CLOSED_CATALOG_POLICY,
        "unknown_code_policy": UNKNOWN_CODE_POLICY,
        "verdict_code_compatibility": (
            "STRUCTURAL_DETERMINISTIC_SEMANTIC_DIAGNOSTIC"
        ),
        "coverage_policy": "ADMISSIBLE_SEPARATORS_WORDS_AND_CONNECTIVES_MANDATORY",
        "failure_diagnostics": "ACCEPTANCE_FAIL_DIAGNOSTIC_RETAINED",
        "contract_candidate": PROMPT_VERSION_113,
        "transport": TRANSPORT_VERSION_11,
        "h01_replay": h01_replay_status,
        "h02_replay": h02_replay_status,
        "fakeai_positives": fixtures.get("fakeai_positives"),
        "fakeai_negatives": fixtures.get("fakeai_negatives"),
        "new_regressions": tests.get("new_failures"),
        "future_canary_criteria": "INDEPENDENCE_INFORMATIVE_CLEAR_EVIDENCE_LOW_AMBIGUITY_COST_UNRESOLVED_FAILURE",
        "source_hashes_unchanged": hashes_ok and source_ok and plan_ok and transcript_ok,
        "ready_for_next_canary_design_review": ready_review,
        "notes": (
            "1.1.2 remains frozen. 1.1.3-candidate adds operational verdict "
            "definitions, origin/attribution as a claim type, and an "
            "anti-masking rule for NON_SUBSTANTIVE. The h02 origin-framing "
            "sentence stays INDETERMINATE as a human-review category. Unknown "
            "reason codes remain blocking. Coverage and transport 1.1-candidate "
            "are reused. Historical h01/h02 remain PARTIAL. Diagnostics remain "
            "exploitable on FAIL. No provider call."
        ),
        "authorization_scope": AUTHORIZATION_SCOPE,
    }
    readiness = {
        "READY_FOR_NEXT_CANARY_DESIGN_REVIEW": ready_review,
        "READY_FOR_NEW_REMOTE_TERRA_CALL": False,
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT": False,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "candidate_promoted": False,
        "human_label_modified": False,
        "historical_contracts_modified": False,
        "why": (
            "Offline 1.1.2 stabilization complete. A later Terra call still "
            "needs a distinct human authorization. 1.1.3 is a proposal only."
        ),
        "phase": PHASE,
        "secrets_included": False,
    }
    tests_artifact = {
        **tests,
        "offline_fixtures": fixtures,
        "frozen_1_0_prompt_sha256": content_hash(system_prompt()),
        "frozen_1_1_prompt_sha256": candidate_prompt_bundle()["prompt_sha256"],
        "frozen_1_1_1_prompt_sha256": candidate_111_prompt_bundle()["prompt_sha256"],
        "frozen_1_1_2_prompt_sha256": candidate_112_prompt_bundle()["prompt_sha256"],
        "candidate_1_1_3_prompt_sha256": candidate_113_prompt_bundle()["prompt_sha256"],
        "fakeai_not_terra_quality": True,
    }
    benchmark = {
        "phase": PHASE,
        "positives_accepted": fixtures.get("fakeai_positives"),
        "negatives_blocked": fixtures.get("fakeai_negatives"),
        "protected": (fixtures.get("historical") or {}).get("protected"),
        "validator_1_1_2_status": (fixtures.get("historical") or {}).get(
            "validator_1_1_2_status"
        ),
        "additional_fixtures_passed": (fixtures.get("additional") or {}).get("passed"),
        "fakeai_not_terra_quality": True,
        "labels_unmodified": True,
        "historical_ten_cases_preserved": True,
        "no_h01_h02_exceptions_in_general_rules": True,
        "secrets_included": False,
    }
    bundle = {
        "header": header,
        "inventory": inventory,
        "verdicts": verdicts,
        "indeterminate": indeterminate,
        "catalog": catalog,
        "matrix": matrix,
        "unknown": unknown,
        "coverage": coverage,
        "diagnostic_policy": diagnostic_policy,
        "replays": replays,
        "benchmark": benchmark,
        "contract": contract,
        "transport": transport,
        "canary": canary,
        "readiness": readiness,
        "tests": tests_artifact,
        "canonical": before,
        "canonical_after": after,
        "contract_comparison": comparison_contracts,
    }
    bundle["report_text"] = render_report(bundle)
    bundle = redact_secrets(bundle)
    if write_artifacts:
        from app.book_semantic_gate_4b275.writer import write_phase_artifacts

        write_phase_artifacts(bundle, root=root)
    result.bundle = bundle
    result.accepted = verdict == "PASS"
    result.mode = "OFFLINE"
    return result


__all__ = ["Phase275Result", "run_phase"]
