"""4B.2.3 human-readable report."""

from __future__ import annotations

from typing import Any, Mapping


def _dash(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value)


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    architecture = dict(bundle.get("architecture") or {})
    fakeai = dict(bundle.get("fakeai") or {})
    cost = dict(bundle.get("cost_estimate") or {})
    sufficiency = dict(bundle.get("sufficiency") or {})
    readiness = dict(bundle.get("readiness") or {})
    tests = dict(bundle.get("tests") or {})
    identities = dict(bundle.get("identities_before") or {})
    lines = [
        "# PHASE 4B.2.3 — INDEPENDENT SEMANTIC GATE ARCHITECTURE + OFFLINE BENCHMARK",
        "",
        "## Result",
        "",
        _dash(header.get("result")),
        "",
        "REAL PROVIDER CALLS =",
        str(header.get("real_provider_calls", 0)),
        "",
        "4B.2 STATUS =",
        _dash(header.get("historical_4b2_status")),
        "",
        "4B.2.2 STATUS =",
        _dash(header.get("historical_4b22_status")),
        "",
        "SOURCE MAP UNCHANGED =",
        _dash(header.get("source_map_unchanged")),
        "",
        "EDITORIAL PLAN UNCHANGED =",
        _dash(header.get("editorial_plan_unchanged")),
        "",
        "CLEAN TRANSCRIPT UNCHANGED =",
        _dash(header.get("clean_transcript_unchanged")),
        "",
        "GENERATOR MODEL =",
        _dash(header.get("generator_model")),
        "",
        "GENERATOR PROMPT =",
        _dash(header.get("generator_prompt")),
        "",
        "DETERMINISTIC VALIDATOR =",
        _dash(header.get("deterministic_validator")),
        "",
        "SEMANTIC GATE MODEL =",
        _dash(header.get("semantic_gate_model")),
        "",
        "SEMANTIC GATE PROMPT =",
        _dash(header.get("semantic_gate_prompt")),
        "",
        "SEMANTIC GATE TRANSPORT =",
        _dash(header.get("semantic_gate_transport")),
        "",
        "SEMANTIC GATE SCHEMA =",
        _dash(header.get("semantic_gate_schema")),
        "",
        "SEMANTIC VALIDATION GRANULARITY =",
        _dash(header.get("semantic_validation_granularity")),
        "",
        "EVIDENCE SCOPE =",
        _dash(header.get("evidence_scope")),
        "",
        "SUPPORTED CLASS =",
        _dash(header.get("supported_class")),
        "",
        "QUESTIONABLE CLASS =",
        _dash(header.get("questionable_class")),
        "",
        "UNSUPPORTED CLASS =",
        _dash(header.get("unsupported_class")),
        "",
        "NON_SUBSTANTIVE CLASS =",
        _dash(header.get("non_substantive_class")),
        "",
        "QUESTIONABLE ACCEPTED =",
        _dash(header.get("questionable_accepted")),
        "",
        "UNSUPPORTED ACCEPTED =",
        _dash(header.get("unsupported_accepted")),
        "",
        "CACHE ACCEPTANCE REQUIRES SEMANTIC PASS =",
        _dash(header.get("cache_acceptance_requires_semantic_pass")),
        "",
        "HISTORICAL BENCHMARK CASES =",
        _dash(header.get("historical_benchmark_cases")),
        "",
        "POSITIVE CASES =",
        _dash(header.get("positive_cases")),
        "",
        "NEGATIVE CASES =",
        _dash(header.get("negative_cases")),
        "",
        "P3 EXPECTED CLASS =",
        _dash(header.get("p3_expected_class")),
        "",
        "P3 EXPECTED REASON =",
        _dash(header.get("p3_expected_reason")),
        "",
        "P8 EXPECTED CLASS =",
        _dash(header.get("p8_expected_class")),
        "",
        "P8 EXPECTED REASON =",
        _dash(header.get("p8_expected_reason")),
        "",
        "FUNERAL CASE EXPECTED =",
        _dash(header.get("funeral_case_expected")),
        "",
        "CONNECTIVE CASE EXPECTED =",
        _dash(header.get("connective_case_expected")),
        "",
        "FAKEAI TESTS =",
        _dash(header.get("fakeai_tests")),
        "",
        "CH016 SEMANTIC REQUEST ESTIMATE =",
        _dash(header.get("ch016_semantic_request_estimate")),
        "",
        "LARGEST CHAPTER SEMANTIC REQUEST ESTIMATE =",
        _dash(header.get("largest_chapter_semantic_request_estimate")),
        "",
        "19-CHAPTER SEMANTIC GATE ESTIMATED COST =",
        _dash(header.get("nineteen_chapter_semantic_gate_estimated_cost")),
        "",
        "BOOK-GENERATOR-1.0.1 SUFFICIENCY =",
        _dash(header.get("book_generator_101_sufficiency")),
        "",
        "4B.2.2 CANDIDATE PRODUCTION CACHE =",
        "NOT ACCEPTED",
        "",
        "book.json =",
        "NOT PUBLISHED",
        "",
        "READY_FOR_ONE_REAL_TERRA_SEMANTIC_GATE_CANARY =",
        _dash(header.get("ready_for_one_real_terra_semantic_gate_canary")),
        "",
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT =",
        "NO",
        "",
        "READY_FOR_FULL_REAL_BOOK_GENERATION =",
        "NO",
        "",
        "NEXT ACTION =",
        "HUMAN REVIEW",
        "",
        "## Notes",
        "",
        "Zero provider calls. Historical 4B.2 remains FAIL. 4B.2.1 remains PASS. "
        "4B.2.2 remains PARTIAL. No CH016 regeneration. No book-generator-1.0.2. "
        "No production cache acceptance. No book.json.",
        "",
        f"Clean transcript SHA-256={_dash((identities.get('clean_transcript') or {}).get('sha256'))}.",
        "",
        architecture.get("central_finding_text") or "",
        "",
        architecture.get("second_finding_text") or "",
        "",
        architecture.get("third_finding_text") or "",
        "",
        "Gate placement: Sonnet chapter candidate → deterministic "
        "BookGenerationValidator → independent semantic gate → production "
        "chapter cache acceptance. Deterministic PASS is required before a "
        "semantic provider call. Empty paragraph remains validator territory.",
        "",
        f"Granularity={architecture.get('granularity')}. Evidence scope="
        f"{architecture.get('evidence_scope')}. Declared handles are hints, "
        "never proof. Section-bounded evidence is the verification scope. "
        "Other chapters cannot rescue a claim unless EditorialPlan authorized reuse.",
        "",
        "Terra thinking is unverified; proposed configuration is "
        "provider_default with temperature omitted. OpenAIEngine structured "
        "output remains json_object. The schema is the local contract.",
        "",
        f"FakeAI catalog: {fakeai.get('count')} cases, "
        f"determinism={fakeai.get('determinism')}, "
        f"passed={fakeai.get('passed')}.",
        "",
        f"19-chapter cost status={cost.get('status')}. "
        f"Long-context threshold modeled=NO. Assumed applied=NO. "
        f"Previous rough estimate {cost.get('previous_rough_estimate_usd')} "
        "is not frozen. Unknown != zero. Not spent.",
        "",
        f"book-generator-1.0.1 sufficiency={sufficiency.get('classification')}. "
        "Two residual 4B.2.2 QUESTIONABLE paragraphs block cache acceptance. "
        "Do not infer a 19-chapter rejection rate from two CH016 samples.",
        "",
        f"Recommended next: {readiness.get('recommended_next')}. "
        "Future Terra canary uses frozen historical candidates only. "
        "No Sonnet call. Phase 5 is not started.",
        "",
        f"Focused tests: {_dash(tests.get('summary'))}. "
        f"New failures={tests.get('new_failures')}. Network blocked.",
        "",
        "Wait for human review.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
