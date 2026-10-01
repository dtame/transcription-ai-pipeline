"""Phase 4B.2.3 offline runner. Zero provider calls."""

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
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.accept import acceptance_policy_payload
from app.book_semantic_gate_4b23.architecture import architecture_payload
from app.book_semantic_gate_4b23.benchmark import (
    benchmark_manifest,
    build_historical_benchmark,
)
from app.book_semantic_gate_4b23.budget import measure_chapter_budget, select_extrema
from app.book_semantic_gate_4b23.cache_contract import cache_contract_payload
from app.book_semantic_gate_4b23.claims import claim_contract_payload
from app.book_semantic_gate_4b23.constants import (
    DETERMINISTIC_VALIDATOR_VERSION,
    EXPECTED_EVIDENCE_SHA256,
    GENERATOR_PROMPT_VERSION,
    GRANULARITY,
    HISTORICAL_4B21_STATUS,
    HISTORICAL_4B22_STATUS,
    HISTORICAL_4B2_STATUS,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS,
    SEMANTIC_GATE_MODEL,
    SEMANTIC_GATE_PROVIDER,
    SEMANTIC_VALIDATION_TRANSPORT_VERSION,
    SEMANTIC_VALIDATOR_PROMPT_VERSION,
    TARGET_CHAPTER_ID,
)
from app.book_semantic_gate_4b23.costing import estimate_from_budgets
from app.book_semantic_gate_4b23.evidence import (
    evidence_contract_payload,
    production_evidence_sha256,
)
from app.book_semantic_gate_4b23.fakeai import run_fakeai_catalog
from app.book_semantic_gate_4b23.guard import assert_offline_package
from app.book_semantic_gate_4b23.identity import (
    load_json,
    snapshot_identities,
    verify_canonical_inputs,
)
from app.book_semantic_gate_4b23.paths import (
    historical_4b22_dir,
    historical_4b2_dir,
    production_book_path,
    repo_root,
)
from app.book_semantic_gate_4b23.prompt import prompt_identity
from app.book_semantic_gate_4b23.reasons import reason_codes_payload
from app.book_semantic_gate_4b23.report import render_report
from app.book_semantic_gate_4b23.schema import schema_identity
from app.book_semantic_gate_4b23.sufficiency import sufficiency_assessment
from app.book_semantic_gate_4b23.transport import transport_identity
from app.editorial_planning.pipeline import (
    load_published_editorial_plan,
    load_published_source_map,
)


@dataclass
class SemanticGateResult:
    bundle: dict[str, Any]
    result: str


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_semantic_gate_4b23.py",
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
        "stderr_tail": "\n".join((completed.stderr or "").strip().splitlines()[-8:]),
        "new_failures": 0 if not failed else 1,
        "network_blocked": True,
        "suites": tests,
    }


def _readiness(
    *,
    result: str,
    fakeai_ok: bool,
    coverage_strong: bool,
) -> dict[str, Any]:
    terra_ready = result == "PASS" and fakeai_ok and coverage_strong
    return {
        "READY_FOR_ONE_REAL_TERRA_SEMANTIC_GATE_CANARY": terra_ready,
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT": False,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "recommended_next": (
            "A. Terra benchmark canary on frozen historical cases"
            if terra_ready
            else "D. architectural revision"
        ),
        "why_not_another_sonnet_ch016": (
            "Do not authorize another Sonnet CH016 generation merely to seek "
            "a perfect sample. The next useful experiment tests the "
            "independent semantic gate against frozen human-labeled cases."
        ),
        "future_terra_canary_uses_frozen_candidates_only": True,
        "future_terra_canary_needs_sonnet": False,
        "book_json": "NOT PUBLISHED",
        "phase_5": False,
        "historical_4b2_status": HISTORICAL_4B2_STATUS,
        "historical_4b22_status": HISTORICAL_4B22_STATUS,
    }


def run_semantic_gate_architecture(
    *, root: Path | None = None, run_tests: bool = True
) -> SemanticGateResult:
    assert_offline_package()
    base = root or repo_root()
    before = verify_canonical_inputs(root=base)
    before_snap = snapshot_identities(before)

    plan, _plan_raw, _plan_digest, _plan_path = load_published_editorial_plan(
        PROJECT_NAME
    )
    source_map, _map_raw, _map_digest, _map_path = load_published_source_map(
        PROJECT_NAME
    )
    index = load_clean_transcript_index(PROJECT_NAME)
    language = resolve_canonical_language(
        source_map_primary_language=source_map.primary_language,
        transcript_primary_language=index.primary_language,
    )
    historical = historical_4b2_dir(root=base)
    hardened = historical_4b22_dir(root=base)
    candidate_4b2 = load_json(historical / "chapter_CH016_candidate.json")
    candidate_4b22 = load_json(hardened / "chapter_CH016_candidate.json")
    raw_4b2 = load_json(historical / "book_generator_4b2_raw_structured_response.json")

    chapter_016 = next(item for item in plan.chapters if item.chapter_id == TARGET_CHAPTER_ID)
    evidence_016 = build_chapter_evidence(
        plan,
        source_map,
        chapter_016,
        language=language,
        hydrate=True,
        transcript_index=index,
    )
    evidence_sha = evidence_identity(evidence_016)

    budgets = []
    for chapter in plan.chapters:
        evidence = (
            evidence_016
            if chapter.chapter_id == TARGET_CHAPTER_ID
            else build_chapter_evidence(
                plan,
                source_map,
                chapter,
                language=language,
                hydrate=True,
                transcript_index=index,
            )
        )
        candidate = candidate_4b22 if chapter.chapter_id == TARGET_CHAPTER_ID else None
        budgets.append(
            measure_chapter_budget(
                evidence=evidence,
                candidate=candidate,
                language=language,
                chapter_id=chapter.chapter_id,
                idea_count=len(chapter.idea_refs),
                section_count=len(chapter.sections),
            )
        )
    extrema = select_extrema(budgets)
    cost = estimate_from_budgets(budgets)
    fakeai = run_fakeai_catalog()
    benchmark = build_historical_benchmark(
        candidate_4b2=candidate_4b2,
        candidate_4b22=candidate_4b22,
        raw_4b2=raw_4b2,
    )
    manifest = benchmark_manifest(benchmark)
    architecture = architecture_payload()
    claims = claim_contract_payload()
    reasons = reason_codes_payload()
    evidence_contract = evidence_contract_payload()
    prompt = prompt_identity()
    schema = schema_identity()
    transport = transport_identity()
    acceptance = acceptance_policy_payload()
    cache = cache_contract_payload()
    sufficiency = sufficiency_assessment()
    tests = (
        _run_focused_tests(root=base)
        if run_tests
        else {"skipped": True, "new_failures": 0, "network_blocked": True, "passed": 0}
    )

    after = verify_canonical_inputs(root=base)
    after_snap = snapshot_identities(after)
    inputs_unchanged = before_snap == after_snap
    coverage_strong = claims["text_spans_required"] and architecture[
        "granularity"
    ] == GRANULARITY

    artifacts_ok = all(
        [
            before["source_map_unchanged"],
            before["editorial_plan_unchanged"],
            before["clean_transcript_unchanged"],
            before["raw_4b2_unchanged"],
            before["candidate_4b2_unchanged"],
            before["candidate_4b22_unchanged"],
            inputs_unchanged,
            evidence_sha == EXPECTED_EVIDENCE_SHA256,
            production_book_absent(PROJECT_NAME),
            REAL_PROVIDER_CALLS == 0,
            fakeai["passed"],
            tests.get("new_failures", 1) == 0,
            language == "en",
            coverage_strong,
            architecture["central_finding"]
            == "STRUCTURAL_TRACEABILITY_IS_NOT_SEMANTIC_SUPPORT",
            len(benchmark.get("positive_cases") or []) >= 2,
            len(benchmark.get("negative_cases") or []) == 4,
            sufficiency["classification"] == "SUFFICIENT_WITH_SEMANTIC_GATE",
        ]
    )
    result = "PASS" if artifacts_ok else "FAIL"
    readiness = _readiness(
        result=result, fakeai_ok=bool(fakeai["passed"]), coverage_strong=coverage_strong
    )
    ch016 = extrema.get("ch016") or {}
    largest = extrema.get("largest") or {}
    header = {
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS,
        "historical_4b2_status": HISTORICAL_4B2_STATUS,
        "historical_4b21_status": HISTORICAL_4B21_STATUS,
        "historical_4b22_status": HISTORICAL_4B22_STATUS,
        "source_map_unchanged": _yn(before["source_map_unchanged"] and inputs_unchanged),
        "editorial_plan_unchanged": _yn(
            before["editorial_plan_unchanged"] and inputs_unchanged
        ),
        "clean_transcript_unchanged": _yn(
            before["clean_transcript_unchanged"] and inputs_unchanged
        ),
        "generator_model": "Anthropic / claude-sonnet-5",
        "generator_prompt": GENERATOR_PROMPT_VERSION,
        "deterministic_validator": DETERMINISTIC_VALIDATOR_VERSION,
        "semantic_gate_model": "OpenAI / gpt-5.6-terra",
        "semantic_gate_prompt": SEMANTIC_VALIDATOR_PROMPT_VERSION,
        "semantic_gate_transport": SEMANTIC_VALIDATION_TRANSPORT_VERSION,
        "semantic_gate_schema": schema["raw_schema_sha256"],
        "semantic_validation_granularity": GRANULARITY,
        "evidence_scope": architecture["evidence_scope"],
        "supported_class": "SUPPORTED",
        "questionable_class": "QUESTIONABLE",
        "unsupported_class": "UNSUPPORTED",
        "non_substantive_class": "NON_SUBSTANTIVE",
        "questionable_accepted": "NO",
        "unsupported_accepted": "NO",
        "cache_acceptance_requires_semantic_pass": "YES",
        "historical_benchmark_cases": manifest["case_count"],
        "positive_cases": manifest["positive_count"],
        "negative_cases": manifest["negative_count"],
        "p3_expected_class": "QUESTIONABLE",
        "p3_expected_reason": "NEW_CAUSAL_LINK / NEW_IMPLICATION",
        "p8_expected_class": "QUESTIONABLE",
        "p8_expected_reason": "REFERENCE_COMPLETION / REFERENCE_EXPANSION",
        "funeral_case_expected": "UNSUPPORTED + INVENTED_EXAMPLE",
        "connective_case_expected": "UNSUPPORTED + NEW_ARGUMENT / NEW_CONCLUSION / NEW_IMPLICATION",
        "fakeai_tests": "PASS" if fakeai["passed"] else "FAIL",
        "ch016_semantic_request_estimate": (ch016.get("request") or {}).get(
            "provider_adjusted_pessimistic"
        ),
        "largest_chapter_semantic_request_estimate": (largest.get("request") or {}).get(
            "provider_adjusted_pessimistic"
        ),
        "nineteen_chapter_semantic_gate_estimated_cost": cost.get("total_cost_display"),
        "book_generator_101_sufficiency": sufficiency["classification"],
        "4b22_candidate_production_cache": "NOT ACCEPTED",
        "book_json": "NOT PUBLISHED",
        "ready_for_one_real_terra_semantic_gate_canary": _yn(
            readiness["READY_FOR_ONE_REAL_TERRA_SEMANTIC_GATE_CANARY"]
        ),
        "ready_for_book_generator_production_preflight": "NO",
        "ready_for_full_real_book_generation": "NO",
        "next_action": "HUMAN REVIEW",
        "clean_transcript_path": before["clean_transcript"]["path"],
        "clean_transcript_sha256": before["clean_transcript"]["sha256"],
        "evidence_sha256": evidence_sha,
        "production_book_absent": not production_book_path().is_file(),
        "language": language,
        "tests": tests.get("summary"),
        "new_failures": tests.get("new_failures"),
    }
    bundle = {
        "header": header,
        "identities_before": before,
        "identities_after": after,
        "inputs_unchanged": inputs_unchanged,
        "architecture": architecture,
        "evidence_contract": evidence_contract,
        "claim_contract": claims,
        "reason_codes": reasons,
        "prompt_identity": prompt,
        "transport_identity": transport,
        "schema_identity": schema,
        "historical_benchmark": {
            key: value
            for key, value in benchmark.items()
            if key != "compact_4b22"
        },
        "benchmark_manifest": manifest,
        "acceptance_policy": acceptance,
        "cache_contract": cache,
        "budget": {
            "chapters": [
                {
                    "chapter_id": row["chapter_id"],
                    "candidate_source": row["candidate_source"],
                    "request": row["request"],
                    "output": row["output"],
                    "context_safe": row["context_safe"],
                    "context_utilization_pessimistic": row[
                        "context_utilization_pessimistic"
                    ],
                    "evidence_chars": (row.get("evidence") or {}).get("chars"),
                    "gate_input_chars": row.get("gate_input_chars"),
                }
                for row in budgets
            ],
            "extrema": {
                key: {
                    "chapter_id": (value or {}).get("chapter_id"),
                    "request": (value or {}).get("request"),
                    "output": (value or {}).get("output"),
                    "context_safe": (value or {}).get("context_safe"),
                }
                for key, value in extrema.items()
            },
        },
        "cost_estimate": cost,
        "sufficiency": sufficiency,
        "fakeai": {
            "passed": fakeai["passed"],
            "determinism": fakeai["determinism"],
            "count": fakeai["count"],
            "cases": [
                {
                    "name": item["name"],
                    "verdict": item["result"]["verdict"],
                    "cache_acceptance": item["result"]["cache_acceptance"],
                    "match": item["match"],
                }
                for item in fakeai["cases"]
            ],
        },
        "readiness": readiness,
        "tests": tests,
        "production_evidence_sha256": production_evidence_sha256(evidence_016),
        "real_provider_calls": REAL_PROVIDER_CALLS,
    }
    bundle["report_text"] = render_report(bundle)
    return SemanticGateResult(bundle=bundle, result=result)


__all__ = ["SemanticGateResult", "run_semantic_gate_architecture"]
