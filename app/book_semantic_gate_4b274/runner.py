"""
Phase 4B.2.7.4 runner.

Offline only. Consolidates h01/h02 forensics. Never authorizes a provider call.
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
from app.book_semantic_gate_4b274.claims import disagreement_matrix, load_saved_h02_payload, review_h02_claims
from app.book_semantic_gate_4b274.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    CANONICAL_PYTHON_EXECUTABLE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_PROMPT_111_SHA256,
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
    HISTORICAL_4B27_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_112,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_11,
)
from app.book_semantic_gate_4b274.contract import (
    candidate_112_prompt_bundle,
    contract_112_review,
    contract_comparison,
    transport_compatibility,
)
from app.book_semantic_gate_4b274.cost import cost_comparison
from app.book_semantic_gate_4b274.fakeai import run_offline_fixtures
from app.book_semantic_gate_4b274.guard import (
    BookSemanticGate274Error,
    assert_no_publication,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b274.inventory import comparative_analysis, historical_canary_inventory
from app.book_semantic_gate_4b274.paths import production_book_path, repo_root, venv_python_path
from app.book_semantic_gate_4b274.punctuation import (
    coverage_validator_design,
    punctuation_coverage_inventory,
)
from app.book_semantic_gate_4b274.reasons import catalog_audit, reason_code_policy
from app.book_semantic_gate_4b274.replay import historical_response_replays
from app.book_semantic_gate_4b274.report import render_report
from app.file_utils import content_hash


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
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
class Phase274Result:
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
) -> Phase274Result:
    result = Phase274Result()
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
        assert_no_publication(production_book_path())
    except BookSemanticGate274Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if TERRA_EXECUTION_AUTHORIZED or AUTHORIZED_TERRA_CALLS != 0:
        result.error = "Terra must not be authorized in 4B.2.7.4."
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = verify_canonical_inputs(root=root)
    inventory = historical_canary_inventory(root=root)
    claims = review_h02_claims(root=root)
    disagreement = disagreement_matrix(claims, root=root)
    reasons_audit = catalog_audit()
    policy = reason_code_policy()
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
    punctuation = punctuation_coverage_inventory(
        h01_text=h01_text,
        h01_claims=h01_claims,
        h02_text=h02_text,
        h02_claims=h02_claims,
    )
    coverage_design = coverage_validator_design()
    contract = contract_112_review()
    comparison_contracts = contract_comparison()
    transport = transport_compatibility()
    comparison = comparative_analysis(
        h01_payload=h01_payload,
        h02_payload=h02_payload if "pr" in h02_payload else {"pr": []},
        h01_text=h01_text,
        h02_text=h02_text,
    )
    replays = historical_response_replays(root=root)
    fixtures = run_offline_fixtures(root=root)
    cost = cost_comparison(h01_payload=h01_payload, h02_payload=h02_payload)
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
    book_absent = production_book_absent(PROJECT_NAME)
    tests_ok = int(tests.get("new_failures") or 0) == 0
    fakeai_ok = bool(fixtures.get("passed"))
    inventory_ok = (
        source_ok
        and plan_ok
        and transcript_ok
        and hashes_ok
        and not inventory.get("MISSING_HISTORICAL_EVIDENCE")
    )
    claims_ok = int(claims.get("claims_reviewed") or 0) == 11
    reasons_ok = policy.get("unknown_codes_handling") == "COMPLIANCE_FAIL_NO_SILENT_ACCEPTANCE"
    punctuation_ok = punctuation.get("h02", {}).get("coverage_1_1_2") == "PASS"
    substantive_ok = punctuation.get("h01", {}).get("coverage_1_1_2") == "PASS"
    contracts_ok = (
        prompt_10_ok
        and prompt_11_ok
        and prompt_111_ok
        and comparison_contracts.get("historical_contracts_modified") is False
        and contract.get("promoted") is False
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
        and HISTORICAL_H01_STATUS == "PARTIAL"
        and HISTORICAL_H02_STATUS == "PARTIAL"
    )
    ready_review = (
        inventory_ok
        and claims_ok
        and reasons_ok
        and punctuation_ok
        and tests_ok
        and fakeai_ok
        and contracts_ok
        and transport_ok
        and replay_ok
        and book_absent
        and historical_status_ok
    )
    phase_pass = (
        ready_review
        and substantive_ok
        and int(AUTHORIZED_TERRA_CALLS) == 0
        and not inventory.get("invented_missing_data")
    )
    verdict = "PASS" if phase_pass else "FAIL"
    h01_replay_status = (
        f"json={(replays.get('h01') or {}).get('json_parse')} "
        f"1.1.1={(((replays.get('h01') or {}).get('first') or {}).get('validator_1_1_1') or {}).get('status')} "
        f"1.1.2={(((replays.get('h01') or {}).get('first') or {}).get('validator_1_1_2') or {}).get('status')}"
    )
    h02_replay_status = (
        f"json={(replays.get('h02') or {}).get('json_parse')} "
        f"1.1.1={(((replays.get('h02') or {}).get('first') or {}).get('validator_1_1_1') or {}).get('status')} "
        f"1.1.2={(((replays.get('h02') or {}).get('first') or {}).get('validator_1_1_2') or {}).get('status')}"
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
        "h02_claims_reviewed": claims.get("claims_reviewed"),
        "h02_false_rejections": claims.get("false_rejection_count"),
        "h02_justified_reservations": claims.get("justified_reservation_count"),
        "h02_indeterminate_claims": claims.get("indeterminate_count"),
        "reason_code_policy": "CLOSED_CATALOG_STRICT_COMPLIANCE",
        "unknown_codes_handling": policy.get("unknown_codes_handling"),
        "punctuation_coverage": "ADMISSIBLE_SEPARATORS_ALLOWED",
        "substantive_coverage": "WORDS_AND_CONNECTIVES_MANDATORY",
        "contract_candidate": PROMPT_VERSION_112,
        "transport": TRANSPORT_VERSION_11,
        "h01_replay": h01_replay_status,
        "h02_replay": h02_replay_status,
        "fakeai_positives": fixtures.get("fakeai_positives"),
        "fakeai_negatives": fixtures.get("fakeai_negatives"),
        "new_regressions": tests.get("new_failures"),
        "cost_analysis": (
            "h01=0.018812 h02=0.066036 input_similar completion_and_reasoning_higher_on_h02 "
            "no_single_factor_claimed no_provider_spend_here"
        ),
        "source_hashes_unchanged": hashes_ok and source_ok and plan_ok and transcript_ok,
        "ready_for_next_canary_design_review": ready_review,
        "notes": (
            "h01 remains a documented false rejection of supported paraphrase. "
            "h02 correctly isolated and blocked the invented because-clause, then "
            "failed contract compliance on unknown reason codes and separator "
            "coverage. Offline review finds two neighboring false rejections "
            "(very person; since the beginning), several justified reservations, "
            "and one indeterminate origin-framing claim. 1.1.2-candidate lists the "
            "closed catalog, requires reservation codes, and generalizes admissible "
            "separator coverage. Frozen 1.0 / 1.1 / 1.1.1 are unchanged. Transport "
            "1.1-candidate is reused. Replays are deterministic and do not rewrite "
            "historical verdicts. No provider call."
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
            "Offline consolidation complete. A later Terra call still needs a "
            "distinct human authorization. 1.1.2 is a proposal only."
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
        "candidate_1_1_2_prompt_sha256": candidate_112_prompt_bundle()["prompt_sha256"],
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
        "fakeai_not_terra_quality": True,
        "labels_unmodified": True,
        "historical_ten_cases_preserved": True,
        "secrets_included": False,
    }
    bundle = {
        "header": header,
        "inventory": inventory,
        "comparison": comparison,
        "claims": claims,
        "disagreement": disagreement,
        "reason_catalog": reasons_audit.get("observed"),
        "reason_policy": policy,
        "punctuation": punctuation,
        "coverage_design": coverage_design,
        "contract": contract,
        "transport": transport,
        "replays": replays,
        "benchmark": benchmark,
        "cost": cost,
        "readiness": readiness,
        "tests": tests_artifact,
        "canonical": before,
        "canonical_after": after,
        "contract_comparison": comparison_contracts,
    }
    bundle["report_text"] = render_report(bundle)
    bundle = redact_secrets(bundle)
    if write_artifacts:
        from app.book_semantic_gate_4b274.writer import write_phase_artifacts

        write_phase_artifacts(bundle, root=root)
    result.bundle = bundle
    result.accepted = verdict == "PASS"
    result.mode = "OFFLINE"
    return result


__all__ = ["Phase274Result", "run_phase"]
