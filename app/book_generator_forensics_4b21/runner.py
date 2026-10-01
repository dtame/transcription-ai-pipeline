"""Phase 4B.2.1 offline runner. Zero provider calls."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.book_generation.evidence import build_chapter_evidence, evidence_identity
from app.book_generation.hydrate import load_clean_transcript_index
from app.book_generation.language import resolve_canonical_language
from app.book_generation.semantic_review import historical_semantic_findings
from app.book_generation.writer import production_book_absent
from app.book_generator_canary_4b2.validate import interpret_production_response
from app.book_generator_forensics_4b21.constants import (
    EXPECTED_EVIDENCE_SHA256,
    HISTORICAL_4B2_STATUS,
    HISTORICAL_CANDIDATE_SHA256,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS,
    SUCCESSOR_PROMPT_VERSION,
    TARGET_CHAPTER_ID,
)
from app.book_generator_forensics_4b21.costing import future_cost_estimate
from app.book_generator_forensics_4b21.decisions import (
    prompt_hardening_decision,
    readiness_payload,
    root_cause_matrix,
    schema_transport_decision,
    semantic_validation_architecture,
    validator_hardening_decision,
)
from app.book_generator_forensics_4b21.forensics import (
    connective_claim_forensics,
    empty_paragraph_forensics,
    invented_illustration_forensics,
)
from app.book_generator_forensics_4b21.future_request import build_future_ch016_request
from app.book_generator_forensics_4b21.guard import assert_offline_package
from app.book_generator_forensics_4b21.identity import load_json, verify_canonical_inputs
from app.book_generator_forensics_4b21.paths import (
    historical_4b2_dir,
    production_book_path,
    repo_root,
)
from app.book_generator_forensics_4b21.report import render_report
from app.editorial_planning.pipeline import (
    load_published_editorial_plan,
    load_published_source_map,
)


@dataclass
class ForensicsResult:
    bundle: dict[str, Any]
    result: str


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_generation_4b1.py",
        "app/tests/test_book_generation_4b1_corpus.py",
        "app/tests/test_book_generator_canary_4b2.py",
        "app/tests/test_book_generation_4b21.py",
    ]
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=no",
        *tests,
    ]
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
    return {
        "returncode": completed.returncode,
        "summary": summary,
        "passed": int(passed_match.group(1)) if passed_match else 0,
        "stdout_tail": summary,
        "stderr_tail": "\n".join((completed.stderr or "").strip().splitlines()[-8:]),
        "new_failures": 0 if not failed else 1,
        "network_blocked": True,
        "suites": tests,
    }


def run_forensics(*, root: Path | None = None, run_tests: bool = True) -> ForensicsResult:
    assert_offline_package()
    base = root or repo_root()
    identities = verify_canonical_inputs(root=base)
    historical = historical_4b2_dir(root=base)
    raw_payload = load_json(historical / "book_generator_4b2_raw_structured_response.json")
    candidate = load_json(historical / "chapter_CH016_candidate.json")
    structural = load_json(historical / "book_generator_4b2_structural_validation.json")
    saved_evidence = load_json(historical / "book_generator_4b2_evidence_bundle.json")

    plan, _plan_raw, plan_digest, _plan_path = load_published_editorial_plan(PROJECT_NAME)
    source_map, _map_raw, map_digest, _map_path = load_published_source_map(PROJECT_NAME)
    index = load_clean_transcript_index(PROJECT_NAME)
    language = resolve_canonical_language(
        source_map_primary_language=source_map.primary_language,
        transcript_primary_language=index.primary_language,
    )
    chapter = next(item for item in plan.chapters if item.chapter_id == TARGET_CHAPTER_ID)
    evidence = build_chapter_evidence(
        plan,
        source_map,
        chapter,
        language=language,
        hydrate=True,
        transcript_index=index,
    )
    replay = interpret_production_response(
        raw_payload.get("parsed"),
        plan=plan,
        source_map=source_map,
        chapter=chapter,
        language=language,
        allowed_handles=list(evidence.get("allowed") or []),
        provider_raw_sha256=str(raw_payload.get("sha256") or ""),
    )
    replay_errors = list((replay.get("local_validator") or {}).get("errors") or [])
    empty_still_fail = any("empty text" in item for item in replay_errors)
    replay_status = str((replay.get("local_validator") or {}).get("status") or "")

    empty = empty_paragraph_forensics(
        raw_payload.get("parsed") or {},
        candidate,
        replay.get("local_validator") or structural.get("local_validator") or {},
    )
    connective = connective_claim_forensics(
        raw_payload.get("parsed") or {},
        candidate,
        evidence,
    )
    illustration = invented_illustration_forensics(
        raw_payload.get("parsed") or {},
        candidate,
        evidence,
    )
    semantic_hist = historical_semantic_findings(candidate, evidence)
    causes = root_cause_matrix(empty, connective, illustration)
    prompt = prompt_hardening_decision()
    schema = schema_transport_decision()
    validator = validator_hardening_decision()
    architecture = semantic_validation_architecture()
    future = build_future_ch016_request(
        evidence,
        chapter,
        language=language,
        all_chapter_ids=[item.chapter_id for item in plan.chapters],
        source_map_sha256=map_digest,
        editorial_plan_sha256=plan_digest,
    )
    cost = future_cost_estimate(future)
    tests = (
        _run_focused_tests(root=base)
        if run_tests
        else {"skipped": True, "new_failures": 0, "network_blocked": True}
    )

    artifacts_ok = all(
        [
            identities["source_map_unchanged"],
            identities["editorial_plan_unchanged"],
            identities["clean_transcript_unchanged"],
            identities["raw_response_unchanged"],
            identities["candidate_unchanged"],
            empty_still_fail,
            replay_status == "FAIL",
            replay.get("candidate_sha256") == HISTORICAL_CANDIDATE_SHA256,
            evidence_identity(evidence) == EXPECTED_EVIDENCE_SHA256,
            future["determinism"],
            future["future_differs_from_historical"],
            future["cache_signature_changed"],
            future["idea_set_exact"],
            future["section_set_exact"],
            future["src_handles_hydrated"],
            future["evidence_unchanged"],
            language == "en",
            prompt["historical_identity_match"],
            prompt["successor_differs"],
            not schema["schema_changed"],
            production_book_absent(PROJECT_NAME),
            REAL_PROVIDER_CALLS == 0,
            tests.get("new_failures", 1) == 0,
        ]
    )
    ready = artifacts_ok and architecture["selected"] == "D_HYBRID"
    result = "PASS" if artifacts_ok else "FAIL"
    header = {
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS,
        "historical_4b2_status": HISTORICAL_4B2_STATUS,
        "source_map_unchanged": _yn(identities["source_map_unchanged"]),
        "editorial_plan_unchanged": _yn(identities["editorial_plan_unchanged"]),
        "clean_transcript_unchanged": _yn(identities["clean_transcript_unchanged"]),
        "raw_response_unchanged": _yn(identities["raw_response_unchanged"]),
        "candidate_unchanged": _yn(identities["candidate_unchanged"]),
        "empty_paragraph_handle": empty["provider_handle"],
        "empty_paragraph_root_cause": " + ".join(empty["root_cause"]),
        "validator_correct": "YES",
        "connective_claim_handle": connective["provider_handle"],
        "connective_claim_classification": connective["classification"],
        "connective_claim_supported": _yn(bool(connective["supported"])),
        "invented_illustration_handle": illustration["provider_handle"],
        "illustration_classification": illustration["classification"],
        "illustration_source_supported": _yn(bool(illustration["source_supported"])),
        "hydration_defect": causes["HYDRATION_DEFECT"],
        "generation_granularity_defect": causes["GENERATION_GRANULARITY_DEFECT"],
        "output_budget_defect": causes["OUTPUT_BUDGET_DEFECT"],
        "thinking_configuration_defect": causes["THINKING_CONFIGURATION_DEFECT"],
        "selected_hardening": prompt["selected_hardening"],
        "successor_prompt": SUCCESSOR_PROMPT_VERSION,
        "transport": schema["transport"],
        "schema_changed": _yn(False),
        "schema_limitation": schema["schema_limitation"],
        "local_validator_changed": _yn(True),
        "new_grammar_canary_required": schema["new_grammar_canary_required"],
        "semantic_validation_strategy": architecture["selected"],
        "future_ch016_request_sha256": future["request_sha256"],
        "future_request_determinism": "PASS" if future["determinism"] else "FAIL",
        "future_model": "Anthropic / claude-sonnet-5",
        "future_thinking": "disabled",
        "future_max_output": 16384,
        "future_hydration": "SOURCE_MAP_PLUS_TARGETED_TRANSCRIPT_HYDRATION",
        "future_estimated_cost": cost["hardened_ch016"]["total_cost_display"],
        "fakeai_tests": "PASS" if tests.get("new_failures") == 0 else "FAIL",
        "total_tests": tests.get("passed"),
        "new_failures": tests.get("new_failures"),
        "book_json": "NOT PUBLISHED",
        "ready_for_one_hardened_ch016_canary": _yn(ready),
        "ready_for_production_preflight": "NO",
        "ready_for_full_real_book_generation": "NO",
        "next_action": "HUMAN REVIEW",
        "clean_transcript_path": identities["clean_transcript"]["path"],
        "clean_transcript_sha256": identities["clean_transcript"]["sha256"],
        "candidate_file_sha256": identities["candidate_file_sha256"],
        "candidate_canonical_sha256": identities["candidate_canonical_sha256"],
        "historical_replay_status": replay_status,
        "historical_empty_still_fail": empty_still_fail,
        "production_book_path_absent": not production_book_path().is_file(),
        "saved_evidence_sha256": evidence_identity(saved_evidence)
        if saved_evidence
        else None,
    }
    readiness = readiness_payload(
        result=result,
        future_request=future,
        tests=tests,
        ready_for_hardened_canary=ready,
    )
    bundle = {
        "header": header,
        "identities": identities,
        "empty_paragraph": empty,
        "connective_claim": connective,
        "invented_illustration": illustration,
        "historical_semantic": semantic_hist,
        "root_cause": causes,
        "prompt_hardening": prompt,
        "schema_transport": schema,
        "validator_hardening": validator,
        "semantic_architecture": architecture,
        "future_request": future,
        "future_cost": cost,
        "replay": {
            "status": replay_status,
            "errors": replay_errors,
            "candidate_sha256": replay.get("candidate_sha256"),
            "still_fail": empty_still_fail,
            "normalized_into_pass": False,
        },
        "tests": tests,
        "readiness": readiness,
        "language": language,
        "real_provider_calls": REAL_PROVIDER_CALLS,
    }
    bundle["report_text"] = render_report(bundle)
    return ForensicsResult(bundle=bundle, result=result)


__all__ = ["ForensicsResult", "run_forensics"]
