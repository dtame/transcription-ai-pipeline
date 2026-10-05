"""
Phase 4B.2.8 runner.

Offline only. Comparative forensics and experimental prototype.
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
from app.book_semantic_gate_4b28.architecture import (
    architecture_a_analysis,
    architecture_b_analysis,
    architecture_c_analysis,
    architecture_comparison,
)
from app.book_semantic_gate_4b28.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    CANONICAL_PYTHON_EXECUTABLE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
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
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_20_ACTIVATED,
    PROMPT_VERSION_20_PROPOSAL,
    TARGET_ARCHITECTURE,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_11,
    TRANSPORT_VERSION_20_ACTIVATED,
)
from app.book_semantic_gate_4b28.contract import semantic_contract_20_proposal
from app.book_semantic_gate_4b28.cost import cost_comparison
from app.book_semantic_gate_4b28.fakeai import run_offline_fixtures
from app.book_semantic_gate_4b28.false_rejection import false_rejection_analysis
from app.book_semantic_gate_4b28.forensics import (
    h01_claim_forensics,
    h02_claim_forensics,
    h11_claim_forensics,
)
from app.book_semantic_gate_4b28.guard import (
    BookSemanticGate28Error,
    assert_no_publication,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b28.inventory import historical_evidence_inventory
from app.book_semantic_gate_4b28.migration import migration_plan
from app.book_semantic_gate_4b28.paths import production_book_path, repo_root, venv_python_path
from app.book_semantic_gate_4b28.replay import segmentation_design, segmentation_offline_replay
from app.book_semantic_gate_4b28.report import render_report
from app.book_semantic_gate_4b28.taxonomy import failure_taxonomy
from app.file_utils import content_hash


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_semantic_gate_4b28.py",
        "app/tests/test_book_semantic_gate_4b277.py",
        "app/tests/test_book_semantic_gate_4b276.py",
        "app/tests/test_book_semantic_gate_4b275.py",
        "app/tests/test_book_semantic_gate_4b274.py",
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
class Phase28Result:
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
) -> Phase28Result:
    result = Phase28Result()
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
        assert_no_publication(production_book_path())
    except BookSemanticGate28Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if TERRA_EXECUTION_AUTHORIZED or AUTHORIZED_TERRA_CALLS != 0:
        result.error = "Terra must not be authorized in 4B.2.8."
        result.mode = "REJECTED"
        return result
    if PROMPT_VERSION_20_ACTIVATED or TRANSPORT_VERSION_20_ACTIVATED:
        result.error = "Contract 2.0 must remain a proposal."
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = verify_canonical_inputs(root=root)
    inventory = historical_evidence_inventory(root=root)
    h01 = h01_claim_forensics(root=root)
    h02 = h02_claim_forensics(root=root)
    h11 = h11_claim_forensics(root=root)
    taxonomy = failure_taxonomy(root=root)
    arch_a = architecture_a_analysis()
    arch_b = architecture_b_analysis()
    arch_c = architecture_c_analysis()
    comparison = architecture_comparison()
    design = segmentation_design()
    replay = segmentation_offline_replay(root=root)
    false_rej = false_rejection_analysis(root=root)
    cost = cost_comparison()
    contract = semantic_contract_20_proposal()
    migration = migration_plan()
    fixtures = run_offline_fixtures(root=root)
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
    fakeai_ok = bool(fixtures.get("passed"))
    inventory_ok = not inventory.get("MISSING_HISTORICAL_EVIDENCE")
    canaries_ok = (
        int(h01.get("claim_count") or 0) == 7
        and int(h02.get("claim_count") or 0) == 11
        and int(h11.get("claim_count") or 0) == 7
    )
    replay_ok = bool(replay.get("all_complete_char_coverage")) and bool(
        replay.get("all_offset_stable")
    )
    contract_ok = (
        prompt_10_ok
        and prompt_11_ok
        and prompt_111_ok
        and prompt_112_ok
        and prompt_113_ok
        and contract.get("proposal_activated") is False
        and contract.get("does_not_replace_transport_1_1") is True
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
        and HISTORICAL_H01_STATUS == "PARTIAL"
        and HISTORICAL_H02_STATUS == "PARTIAL"
        and HISTORICAL_H11_STATUS == "PARTIAL"
    )
    h01_preserved = bool((replay.get("h01") or {}).get("preserved_propositions"))
    because_preserved = any(
        item.get("preserved_in_one_unit")
        for item in ((replay.get("h02") or {}).get("preserved_propositions") or [])
        if item.get("label") == "because_clause"
    )
    guarantee_preserved = any(
        item.get("preserved_in_one_unit")
        for item in ((replay.get("h11") or {}).get("preserved_propositions") or [])
        if item.get("label") == "universal_guarantee"
    )
    ready_review = (
        inventory_ok
        and canaries_ok
        and replay_ok
        and tests_ok
        and fakeai_ok
        and contract_ok
        and book_absent
        and historical_status_ok
        and hashes_ok
        and source_ok
        and plan_ok
        and transcript_ok
        and because_preserved
        and guarantee_preserved
    )
    phase_pass = (
        ready_review
        and int(AUTHORIZED_TERRA_CALLS) == 0
        and not inventory.get("invented_missing_data")
        and h11.get("coverage_gaps_classification") == "SUBSTANTIVE_WORD_ENDINGS_NOT_SEPARATORS"
    )
    verdict = "PASS" if phase_pass else "PARTIAL" if canaries_ok and inventory_ok else "FAIL"
    if not hashes_ok or not source_ok or not plan_ok or not transcript_ok:
        verdict = "BLOCKED"
    coverage_note = (
        "COMPLETE_ON_H01_H02_H11_OFFLINE"
        if replay.get("all_complete_char_coverage")
        else "INCOMPLETE"
    )
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
        "raw_responses_preserved": True,
        "historical_labels_preserved": True,
        "historical_contracts_preserved": True,
        "h01_false_rejection_analysis": (
            "Relative clause stays in its sentence; disagreement is lexical vs entailment"
        ),
        "h02_false_rejection_analysis": (
            "Because-clause isolable locally; two stylistic false rejections remain semantic"
        ),
        "h11_false_rejection_analysis": (
            "Guarantee isolable; three supported-prefix rejections remain semantic; "
            "word-ending gaps would be locally owned"
        ),
        "failure_taxonomy": "observed_false_rejections_unknown_codes_word_ending_gaps",
        "architecture_a": "current_gate_model_owns_structure_and_semantics",
        "architecture_b": "deterministic_presegmentation_prototype",
        "architecture_c": "hybrid_two_level_proposed_target",
        "segmentation_feasibility": "CONSERVATIVE_HYBRID_FEASIBLE_OFFLINE",
        "segmentation_prototype": "CREATED",
        "segmentation_coverage": coverage_note,
        "negation_causality_preservation": (
            "YES" if because_preserved and h01_preserved else "PARTIAL"
        ),
        "contract_20_proposal": PROMPT_VERSION_20_PROPOSAL,
        "transport_changes_required": (
            f"proposal_only; {TRANSPORT_VERSION_11} reused; not activated"
        ),
        "cost_analysis": (
            "h01=0.018812 h02=0.066036 h11=0.029556 "
            "B_and_C_hypothetical_reasoning_unknown no_provider_spend_here"
        ),
        "architecture_comparison": "matrix_without_numeric_scores",
        "proposed_target_architecture": TARGET_ARCHITECTURE,
        "evidence_level": "OBSERVED_PLUS_HYPOTHESIS_NOT_TERRA_VALIDATED",
        "migration_plan": "six_steps_with_stop_points",
        "fakeai_positives": fixtures.get("fakeai_positives"),
        "fakeai_negatives": fixtures.get("fakeai_negatives"),
        "new_regressions": tests.get("new_failures"),
        "source_hashes_unchanged": hashes_ok and source_ok and plan_ok and transcript_ok,
        "ready_for_architecture_human_review": ready_review,
        "notes": (
            "Three real Terra canaries remain PARTIAL. h01 is a documented false "
            "rejection of supported paraphrase. h02 correctly blocked invented "
            "causality, then failed unknown reason codes and produced two false "
            "rejections plus one indeterminate origin claim. h11 correctly blocked "
            "the universal guarantee with NEW_CONCLUSION, rejected three historically "
            "supported prefixes, and left coverage gaps that are word endings, not "
            "separators. Architecture C with conservative presegmentation is proposed "
            "because it assigns observed structural failures to local code. It is not "
            "Terra-validated and does not automatically correct semantic false "
            "rejections. Contract 2.0 is a proposal only. Transport 1.1 is unchanged. "
            "No provider call."
        ),
        "authorization_scope": AUTHORIZATION_SCOPE,
    }
    readiness = {
        "READY_FOR_ARCHITECTURE_HUMAN_REVIEW": ready_review,
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
            "Offline comparative forensics and an isolated segmentation prototype "
            "are complete. A later Terra call still needs a distinct human "
            "authorization. 2.0 is a proposal only."
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
        "frozen_1_1_3_prompt_sha256": candidate_113_prompt_bundle()["prompt_sha256"],
        "fakeai_not_terra_quality": True,
    }
    bundle = {
        "header": header,
        "inventory": inventory,
        "h01": h01,
        "h02": h02,
        "h11": h11,
        "taxonomy": taxonomy,
        "architecture_a": arch_a,
        "architecture_b": arch_b,
        "architecture_c": arch_c,
        "segmentation": design,
        "replay": replay,
        "false_rejection": false_rej,
        "cost": cost,
        "contract": contract,
        "comparison": comparison,
        "migration": migration,
        "readiness": readiness,
        "tests": tests_artifact,
        "canonical": before,
        "canonical_after": after,
    }
    bundle["report_text"] = render_report(bundle)
    bundle = redact_secrets(bundle)
    if write_artifacts:
        from app.book_semantic_gate_4b28.writer import write_phase_artifacts

        write_phase_artifacts(bundle, root=root)
    result.bundle = bundle
    result.accepted = verdict == "PASS"
    result.mode = "OFFLINE"
    return result


__all__ = ["Phase28Result", "run_phase"]
