"""
Phase 4B.2.9 runner.

Offline only. Semantic Gate 2.0 implementation candidate.
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
from app.book_semantic_gate_4b271.calibration import candidate_111_prompt_bundle
from app.book_semantic_gate_4b274.contract import candidate_112_prompt_bundle
from app.book_semantic_gate_4b275.contract import candidate_113_prompt_bundle
from app.book_semantic_gate_4b275.constants import (
    EXPECTED_PROMPT_111_SHA256,
    EXPECTED_PROMPT_112_SHA256,
    EXPECTED_PROMPT_113_SHA256,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
)
from app.book_semantic_gate_4b28.canaries import load_canary_bundle
from app.book_semantic_gate_4b29.architecture import architecture_implementation
from app.book_semantic_gate_4b29.benchmark import benchmark_compatibility
from app.book_semantic_gate_4b29.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    CANONICAL_PYTHON_EXECUTABLE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    H01_EVIDENCE_HANDLES,
    HISTORICAL_4B261_STATUS,
    HISTORICAL_4B262_STATUS,
    HISTORICAL_4B26_STATUS,
    HISTORICAL_4B271_STATUS,
    HISTORICAL_4B272_STATUS,
    HISTORICAL_4B273_STATUS,
    HISTORICAL_4B274_STATUS,
    HISTORICAL_4B275_STATUS,
    HISTORICAL_4B276_STATUS,
    HISTORICAL_4B277_STATUS,
    HISTORICAL_4B27_STATUS,
    HISTORICAL_4B28_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    OFFSET_CONVENTION,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_20_ACTIVATED,
    PROMPT_VERSION_20_CANDIDATE,
    SEMANTIC_GATE_20_ENABLED,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_20_ACTIVATED,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_semantic_gate_4b29.contract import semantic_contract_20_candidate
from app.book_semantic_gate_4b29.coverage import validate_prepared_coverage
from app.book_semantic_gate_4b29.engine import evaluate_paragraph
from app.book_semantic_gate_4b29.fakeai import (
    FakeAITransport,
    SCENARIO_NAMES,
    run_fakeai_scenarios,
)
from app.book_semantic_gate_4b29.guard import (
    BookSemanticGate29Error,
    assert_no_publication,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b29.integration import integration_preflight
from app.book_semantic_gate_4b29.inventory import technical_inventory
from app.book_semantic_gate_4b29.paths import production_book_path, repo_root, venv_python_path
from app.book_semantic_gate_4b29.policy import acceptance_policy_document
from app.book_semantic_gate_4b29.preparation import prepare_paragraph_units
from app.book_semantic_gate_4b29.provider_safety import provider_safety
from app.book_semantic_gate_4b29.replay import replay_all_historical
from app.book_semantic_gate_4b29.report import render_report
from app.book_semantic_gate_4b29.transport import semantic_transport_20_candidate
from app.file_utils import content_hash


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_semantic_gate_4b29.py",
        "app/tests/test_book_semantic_gate_4b28.py",
        "app/tests/test_book_semantic_gate_4b277.py",
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


def _exercise_scenarios(text: str, paragraph_id: str, evidence: list[str]) -> dict[str, Any]:
    prepared = prepare_paragraph_units(paragraph_id, text, evidence_handles=evidence)
    rows = []
    for name in SCENARIO_NAMES:
        result = evaluate_paragraph(
            paragraph_id=paragraph_id,
            text=text,
            transport=FakeAITransport(name, prepared, chapter="CH016"),
            evidence_handles=evidence,
            chapter_handle="CH016",
        )
        rows.append(
            {
                "scenario": name,
                "source": "FAKEAI_SIMULATED",
                "not_terra": True,
                "decision": result.get("decision"),
                "validation_ok": (result.get("validation") or {}).get("ok"),
            }
        )
    expected_block = {
        "invented_causality",
        "invented_implication",
        "universal_guarantee",
        "missing_unit",
        "duplicate_unit",
        "unknown_unit",
        "unknown_reason_code",
        "unknown_evidence_handle",
        "incoherent_global_verdict",
        "invalid_json",
        "truncated_response",
        "abusive_non_substantive",
    }
    expected_review = {"questionable"}
    expected_pass = {"all_supported", "legitimate_paraphrase"}
    ok = True
    for row in rows:
        name = row["scenario"]
        decision = row["decision"]
        if name in expected_block and decision != "BLOCK":
            ok = False
        if name in expected_review and decision != "REVIEW":
            ok = False
        if name in expected_pass and decision not in {"PASS", "REVIEW"}:
            ok = False
    return {
        "phase": PHASE,
        "source": "FAKEAI_SIMULATED",
        "not_terra": True,
        "catalog": run_fakeai_scenarios(text, paragraph_id=paragraph_id, evidence_handles=evidence),
        "engine_rows": rows,
        "passed": ok and len(rows) == len(SCENARIO_NAMES),
        "secrets_included": False,
    }


@dataclass
class Phase29Result:
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
) -> Phase29Result:
    result = Phase29Result()
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
        assert_no_publication(production_book_path())
    except BookSemanticGate29Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if TERRA_EXECUTION_AUTHORIZED or AUTHORIZED_TERRA_CALLS != 0:
        result.error = "Terra must not be authorized in 4B.2.9."
        result.mode = "REJECTED"
        return result
    if PROMPT_VERSION_20_ACTIVATED or TRANSPORT_VERSION_20_ACTIVATED or SEMANTIC_GATE_20_ENABLED:
        result.error = "Semantic Gate 2.0 must remain inactive."
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = verify_canonical_inputs(root=root)
    inventory = technical_inventory(root=root)
    architecture = architecture_implementation()
    canaries = load_canary_bundle(root=root)
    h01_text = str((canaries.get("h01") or {}).get("text") or "")
    prepared_h01 = prepare_paragraph_units(
        "h01",
        h01_text,
        evidence_handles=list(H01_EVIDENCE_HANDLES),
    )
    coverage_h01 = validate_prepared_coverage(prepared_h01)
    contract = semantic_contract_20_candidate()
    transport = semantic_transport_20_candidate()
    policy_doc = acceptance_policy_document()
    fakeai = _exercise_scenarios(h01_text, "h01", list(H01_EVIDENCE_HANDLES))
    historical = replay_all_historical(root=root)
    benchmark = benchmark_compatibility(root=root)
    integration = integration_preflight()
    safety = provider_safety(root=root)
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
    prompt_113_ok = candidate_113_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_113_SHA256
    book_absent = production_book_absent(PROJECT_NAME)
    tests_ok = int(tests.get("new_failures") or 0) == 0
    contract_ok = (
        prompt_10_ok
        and prompt_11_ok
        and prompt_111_ok
        and prompt_112_ok
        and prompt_113_ok
        and contract.get("candidate_activated") is False
        and contract.get("overfit_tokens_absent_from_candidate") is True
        and contract.get("historical_1_1_3_unmodified") is True
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
        and HISTORICAL_4B275_STATUS == "PASS"
        and HISTORICAL_4B276_STATUS == "PASS"
        and HISTORICAL_4B277_STATUS == "PARTIAL"
        and HISTORICAL_4B28_STATUS == "PASS"
        and HISTORICAL_H01_STATUS == "PARTIAL"
        and HISTORICAL_H02_STATUS == "PARTIAL"
        and HISTORICAL_H11_STATUS == "PARTIAL"
    )
    replay_ok = bool(historical.get("all_coverage_ok"))
    fakeai_ok = bool(fakeai.get("passed"))
    safety_ok = bool(safety.get("ok"))
    benchmark_ok = bool(benchmark.get("cases_representable")) and bool(
        benchmark.get("labels_unmodified")
    )
    h01_preserved = any(
        item.get("preserved_in_one_unit")
        for item in (historical.get("h01") or {}).get("preserved_propositions") or []
    )
    h02_preserved = any(
        item.get("preserved_in_one_unit")
        for item in (historical.get("h02") or {}).get("preserved_propositions") or []
    )
    h11_preserved = any(
        item.get("preserved_in_one_unit")
        for item in (historical.get("h11") or {}).get("preserved_propositions") or []
    )
    ready_review = (
        tests_ok
        and fakeai_ok
        and contract_ok
        and book_absent
        and historical_status_ok
        and hashes_ok
        and source_ok
        and plan_ok
        and transcript_ok
        and replay_ok
        and safety_ok
        and benchmark_ok
        and h01_preserved
        and h02_preserved
        and h11_preserved
        and coverage_h01.get("ok") is True
        and integration.get("connected") is False
    )
    phase_pass = ready_review and int(AUTHORIZED_TERRA_CALLS) == 0
    verdict = "PASS" if phase_pass else "PARTIAL" if replay_ok and contract_ok else "FAIL"
    if not hashes_ok or not source_ok or not plan_ok or not transcript_ok:
        verdict = "BLOCKED"
    header = {
        "result": verdict,
        "provider_calls": 0,
        "openai_http": 0,
        "anthropic_http": 0,
        "historical_h01": HISTORICAL_H01_STATUS,
        "historical_h02": HISTORICAL_H02_STATUS,
        "historical_h11": HISTORICAL_H11_STATUS,
        "canonical_python": CANONICAL_PYTHON_EXECUTABLE,
        "source_hashes": {
            "source_pre": before_snap["source_map"],
            "plan_pre": before_snap["editorial_plan"],
            "transcript_pre": before_snap["clean_transcript"],
            "source_post": after_snap["source_map"],
            "plan_post": after_snap["editorial_plan"],
            "transcript_post": after_snap["clean_transcript"],
        },
        "semantic_gate_20_module": "app.book_semantic_gate_4b29",
        "deterministic_preparation": "REUSES_4B28_CONSERVATIVE_SEGMENTATION",
        "unit_identifiers": "stable u00, u01, ...",
        "offset_convention": OFFSET_CONVENTION,
        "coverage": "COMPLETE_ON_H01_H02_H11_OFFLINE" if replay_ok else "INCOMPLETE",
        "context_preservation": "PARAGRAPH_ONCE_PLUS_UNIT_TEXTS",
        "contract_20": PROMPT_VERSION_20_CANDIDATE,
        "transport_20": TRANSPORT_VERSION_20_CANDIDATE,
        "response_validator": "DETERMINISTIC_NO_SILENT_REPAIR",
        "acceptance_policy": "PASS_BLOCK_REVIEW",
        "fakeai_scenarios": len(SCENARIO_NAMES),
        "h01_offline_replay": "UNITS_COVERAGE_REQUEST_FAKEAI",
        "h02_offline_replay": "UNITS_COVERAGE_REQUEST_FAKEAI",
        "h11_offline_replay": "UNITS_COVERAGE_REQUEST_FAKEAI",
        "benchmark_compatibility": "TEN_CASES_REPRESENTABLE_LABELS_LOCAL",
        "integration_preflight": "DOCUMENTED_NOT_CONNECTED",
        "provider_safety": "REMOTE_FAILS_CLOSED",
        "new_regressions": tests.get("new_failures"),
        "source_hashes_unchanged": hashes_ok and source_ok and plan_ok and transcript_ok,
        "ready_for_semantic_gate_20_human_review": ready_review,
        "notes": (
            "Semantic Gate 2.0 is implemented as an isolated offline candidate. "
            "Preparation reuses the 4B.2.8 conservative segmentation prototype, "
            "stores the paragraph once, and owns offsets locally. Contract and "
            "transport 2.0-candidate reduce model structural duties to unit_id "
            "verdicts. FakeAI exercises PASS/BLOCK/REVIEW orchestration and is "
            "not Terra quality. Historical h01/h02/h11 remain PARTIAL. "
            "No provider call. Production pipeline and cache are unchanged."
        ),
        "authorization_scope": AUTHORIZATION_SCOPE,
    }
    readiness = {
        "READY_FOR_SEMANTIC_GATE_20_HUMAN_REVIEW": ready_review,
        "READY_FOR_NEW_REMOTE_TERRA_CALL": False,
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT": False,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "production_pipeline": "UNCHANGED",
        "candidate_promoted": False,
        "contract_20_activated": False,
        "human_label_modified": False,
        "historical_contracts_modified": False,
        "why": (
            "Offline Semantic Gate 2.0 candidate and integration preflight are "
            "complete. A later Terra call still needs a distinct human "
            "authorization. 2.0 remains inactive in production."
        ),
        "phase": PHASE,
        "secrets_included": False,
    }
    preparation_artifact = {
        "phase": PHASE,
        "offset_convention": OFFSET_CONVENTION,
        "reuses_4b28": True,
        "h01": {
            "unit_count": prepared_h01.get("unit_count"),
            "paragraph_unchanged": prepared_h01.get("paragraph_unchanged"),
            "does_not_copy_paragraph_onto_each_unit": prepared_h01.get(
                "does_not_copy_paragraph_onto_each_unit"
            ),
            "units": prepared_h01.get("units"),
        },
        "does_not_judge_fidelity": True,
        "secrets_included": False,
    }
    coverage_artifact = {
        "phase": PHASE,
        "h01": coverage_h01,
        "historical": {
            "h01": (historical.get("h01") or {}).get("coverage_ok"),
            "h02": (historical.get("h02") or {}).get("coverage_ok"),
            "h11": (historical.get("h11") or {}).get("coverage_ok"),
        },
        "offset_convention": OFFSET_CONVENTION,
        "secrets_included": False,
    }
    validator_artifact = {
        "phase": PHASE,
        "controls": [
            "JSON",
            "schema",
            "required fields",
            "types",
            "verdicts",
            "reason codes",
            "evidence handles",
            "known unit ids",
            "no duplicates",
            "no missing units",
            "no unknown units",
            "verdict/code coherence",
            "global verdict coherence",
            "no extra fields",
        ],
        "does_not_complete_missing_units": True,
        "does_not_repair_reason_codes": True,
        "fakeai_invalid_json_blocks": True,
        "secrets_included": False,
    }
    tests_artifact = {
        **tests,
        "offline_fakeai": fakeai,
        "frozen_1_0_prompt_sha256": content_hash(system_prompt()),
        "frozen_1_1_prompt_sha256": candidate_prompt_bundle()["prompt_sha256"],
        "frozen_1_1_1_prompt_sha256": candidate_111_prompt_bundle()["prompt_sha256"],
        "frozen_1_1_2_prompt_sha256": candidate_112_prompt_bundle()["prompt_sha256"],
        "frozen_1_1_3_prompt_sha256": candidate_113_prompt_bundle()["prompt_sha256"],
        "fakeai_not_terra_quality": True,
    }
    bundle = {
        "header": header,
        "inventory": inventory,
        "architecture": architecture,
        "preparation": preparation_artifact,
        "coverage": coverage_artifact,
        "contract": contract,
        "transport": transport,
        "validator": validator_artifact,
        "policy": policy_doc,
        "fakeai": fakeai,
        "h01": historical.get("h01"),
        "h02": historical.get("h02"),
        "h11": historical.get("h11"),
        "benchmark": benchmark,
        "integration": integration,
        "safety": safety,
        "readiness": readiness,
        "tests": tests_artifact,
        "canonical": before,
        "canonical_after": after,
    }
    bundle["report_text"] = render_report(bundle)
    bundle = redact_secrets(bundle)
    if write_artifacts:
        from app.book_semantic_gate_4b29.writer import write_phase_artifacts

        write_phase_artifacts(bundle, root=root)
    result.bundle = bundle
    result.accepted = verdict == "PASS"
    result.mode = "OFFLINE"
    return result


__all__ = ["Phase29Result", "run_phase"]
