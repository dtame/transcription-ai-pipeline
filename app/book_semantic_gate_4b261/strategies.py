"""Strategy A/B/C analysis and comparison. Recommendation follows evidence."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.ai.estimation import estimate_tokens
from app.ai.openai_compat import capture_openai_sdk_chat_request
from app.ai.providers.openai_engine import OpenAIEngine
from app.book_semantic_gate_4b23.prompt import render_user_prompt, system_prompt
from app.book_semantic_gate_4b24.constants import SCORED_CASE_ORDER
from app.book_semantic_gate_4b24.leak import audit_label_leak
from app.book_semantic_gate_4b261.candidates import (
    candidate_system_prompt,
    render_candidate_user_prompt,
)
from app.book_semantic_gate_4b261.complexity import extract_gate_input, extract_gate_paragraphs
from app.book_semantic_gate_4b261.constants import (
    CANDIDATE_PROMPT_VERSION,
    CANDIDATE_TRANSPORT_VERSION,
    EXPECTED_REQUEST_SHA256_4B26,
    HARD_MAX_OUTPUT_TOKENS,
    MODEL,
    PHASE,
    SEMANTIC_TOKEN_BUDGET,
    STRATEGY_A_BUDGETS,
    STRATEGY_C_BATCH_SIZES,
)
from app.book_semantic_gate_4b261.costing import estimate_cost, pricing_context
from app.file_utils import content_hash


def _slice_gate_input(gate: Mapping[str, Any], handles: list[str]) -> dict[str, Any]:
    wanted = set(handles)
    candidate = dict(gate.get("candidate") or {})
    sections = []
    kept_src: set[str] = set()
    kept_idea: set[str] = set()
    kept_ref: set[str] = set()
    for section in candidate.get("sections") or []:
        paras = [
            dict(para)
            for para in section.get("paras") or []
            if str(para.get("h") or "") in wanted
        ]
        if not paras:
            continue
        for para in paras:
            kept_src.update(str(item) for item in para.get("src") or [])
            kept_idea.update(str(item) for item in para.get("idea") or [])
            kept_ref.update(str(item) for item in para.get("ref") or [])
            kept_src.update(str(item) for item in para.get("e") or [])
        row = dict(section)
        row["paras"] = paras
        sections.append(row)
    sliced = dict(gate)
    sliced_candidate = dict(candidate)
    sliced_candidate["sections"] = sections
    sliced["candidate"] = sliced_candidate
    sliced["ideas"] = [
        item for item in gate.get("ideas") or [] if str(item.get("id") or "") in kept_idea
    ]
    sliced["references"] = [
        item for item in gate.get("references") or [] if str(item.get("id") or "") in kept_ref
    ]
    sliced["src_text"] = [
        item for item in gate.get("src_text") or [] if str(item.get("id") or "") in kept_src
    ]
    allowed = sorted(kept_src | kept_idea | kept_ref)
    sliced["allowed_handles"] = allowed
    return sliced


def build_candidate_payload(
    gate: Mapping[str, Any],
    *,
    max_completion_tokens: int = SEMANTIC_TOKEN_BUDGET,
) -> dict[str, Any]:
    user = render_candidate_user_prompt(
        json.dumps(gate, ensure_ascii=False, separators=(",", ":"))
    )
    engine = OpenAIEngine(api_key="offline-4b261-unused", client=object())
    from app.ai.contracts import AIRequest

    request = AIRequest(
        prompt=user,
        system_prompt=candidate_system_prompt(),
        model=MODEL,
        temperature=None,
        max_output_tokens=max_completion_tokens,
        response_schema={"type": "object"},
    )
    payload = engine.build_payload(request, MODEL)
    payload.pop("timeout", None)
    return payload


def analyze_strategy_a() -> dict[str, Any]:
    rows = []
    for budget in STRATEGY_A_BUDGETS:
        rows.append(
            {
                "candidate_budget": budget,
                "authorized": False,
                "analysis_only": True,
                "known_local_model_max_output": 128000,
                "project_hard_max_historical": HARD_MAX_OUTPUT_TOKENS,
                "if_fully_consumed": estimate_cost(4076, budget),
                "truncation_risk": (
                    "HIGH if hidden tokens again consume the entire budget "
                    "before JSON emission"
                ),
                "does_not_change_output_contract": True,
                "does_not_prove_json_emission": True,
            }
        )
    return {
        "phase": PHASE,
        "name": "A",
        "title": "Keep historical contract; raise completion budget",
        "compatibility_with_4b26_evidence": (
            "Compatible as a follow-up experiment, but 4B.2.6 already exhausted "
            "8192 tokens with zero visible JSON. A larger budget may repeat the "
            "same failure at higher cost."
        ),
        "technical_complexity": "LOW",
        "truncation_risk": "HIGH_IF_REASONING_DOMINATES",
        "resume_capability": "NONE — still one 10-case shot",
        "proposition_level_control": "UNCHANGED",
        "nineteen_chapter_fit": "POOR if every chapter repeats budget exhaustion",
        "version_changes": "none",
        "remaining_uncertainties": [
            "reasoning_tokens UNKNOWN",
            "whether extra budget becomes visible JSON",
        ],
        "budgets": rows,
        "recommendation_alone": False,
        "secrets_included": False,
    }


def analyze_strategy_b(complexity: Mapping[str, Any]) -> dict[str, Any]:
    hist = (complexity.get("output_size_estimates") or {}).get(
        "minimal_valid_historical_json"
    ) or {}
    detailed = (complexity.get("output_size_estimates") or {}).get(
        "detailed_valid_historical_json"
    ) or {}
    compact = (complexity.get("output_size_estimates") or {}).get(
        "minimal_valid_candidate_json"
    ) or {}
    return {
        "phase": PHASE,
        "name": "B",
        "title": "Compact output contract; keep 10-case request",
        "candidate_prompt_version": CANDIDATE_PROMPT_VERSION,
        "candidate_transport_version": CANDIDATE_TRANSPORT_VERSION,
        "promoted": False,
        "keeps": [
            "case/paragraph identifiers",
            "decision",
            "substantive claims via spans",
            "exact offsets",
            "evidence references",
            "reason codes",
            "short reservations when needed",
        ],
        "limits": [
            "copied claim text t",
            "free-form explanation x",
            "confidence essays",
        ],
        "does_not_remove_fidelity_requirements": True,
        "estimated_min_json_tokens_historical": hist.get("estimated_tokens"),
        "estimated_detailed_json_tokens_historical": detailed.get("estimated_tokens"),
        "estimated_min_json_tokens_candidate": compact.get("estimated_tokens"),
        "estimated": True,
        "compatibility_with_4b26_evidence": (
            "Addresses confirmed output verbosity. Does not by itself prove "
            "that hidden reasoning will stop consuming the budget."
        ),
        "technical_complexity": "MEDIUM — new candidate versions, local decoder",
        "truncation_risk": "MEDIUM — smaller visible JSON, unknown reasoning",
        "resume_capability": "NONE if still one 10-case call",
        "proposition_level_control": "PRESERVED",
        "nineteen_chapter_fit": "BETTER visible-output density; reasoning still unknown",
        "version_changes": "candidate 1.1 only; 1.0 frozen",
        "remaining_uncertainties": [
            "Terra may still reason silently before emitting compact JSON",
            "json_object semantic production still unproven",
        ],
        "secrets_included": False,
    }


def analyze_strategy_c(
    payload: Mapping[str, Any],
    *,
    complexity: Mapping[str, Any],
) -> dict[str, Any]:
    gate = extract_gate_input(payload)
    paragraphs = extract_gate_paragraphs(payload)
    handles = [str(item.get("handle") or "") for item in paragraphs]
    batches: list[dict[str, Any]] = []
    historical_sha = EXPECTED_REQUEST_SHA256_4B26
    for size in STRATEGY_C_BATCH_SIZES:
        groups = [handles[index : index + size] for index in range(0, len(handles), size)]
        call_rows = []
        for group in groups:
            sliced = _slice_gate_input(gate, group)
            candidate_payload = build_candidate_payload(sliced)
            hist_user = render_user_prompt(
                json.dumps(sliced, ensure_ascii=False, separators=(",", ":"))
            )
            hist_chars = len(system_prompt()) + len(hist_user)
            cand_chars = len(candidate_system_prompt()) + len(
                render_candidate_user_prompt(
                    json.dumps(sliced, ensure_ascii=False, separators=(",", ":"))
                )
            )
            sha = content_hash(
                json.dumps(candidate_payload, ensure_ascii=False, sort_keys=True)
            )
            leak = audit_label_leak(candidate_payload)
            call_rows.append(
                {
                    "handles": group,
                    "candidate_payload_sha256": sha,
                    "differs_from_4b26": sha != historical_sha,
                    "estimated_input_tokens_candidate": estimate_tokens(
                        candidate_system_prompt()
                        + "\n"
                        + render_candidate_user_prompt(
                            json.dumps(sliced, ensure_ascii=False, separators=(",", ":"))
                        )
                    ).tokens,
                    "estimated_input_chars_historical_slice": hist_chars,
                    "estimated_input_chars_candidate_slice": cand_chars,
                    "label_leakage": leak.get("label_leakage"),
                    "estimated": True,
                }
            )
        batches.append(
            {
                "batch_size": size,
                "calls": len(groups),
                "repeated_full_evidence": False,
                "evidence_trimmed_to_batch": True,
                "orchestration_complexity": (
                    "LOW" if size == 10 else "MEDIUM" if size in {2, 5} else "MEDIUM"
                ),
                "truncation_risk": "LOWER_PER_CALL" if size < 10 else "SAME_AS_4B26_SHAPE",
                "resume_capability": "YES" if size < 10 else "NONE",
                "traceability": "YES — one result object per call",
                "quality_not_automatically_better": True,
                "calls_detail": call_rows,
            }
        )
    return {
        "phase": PHASE,
        "name": "C",
        "title": "Split the ten-case benchmark into smaller batches",
        "batches": batches,
        "compatibility_with_4b26_evidence": (
            "If hidden reasoning scales with prompt/output complexity, smaller "
            "batches are the only locally justified way to isolate whether "
            "Terra can emit JSON at all. Smaller batches do not automatically "
            "improve semantic quality."
        ),
        "technical_complexity": "MEDIUM — orchestration, accounting, resume",
        "truncation_risk": "LOWER per call; more calls if each exhausts budget",
        "resume_capability": "HIGH for 1-2 case batches",
        "proposition_level_control": "PRESERVED if each batch still claim-covers its paragraphs",
        "nineteen_chapter_fit": "NATURAL — production already wants per-chapter calls",
        "version_changes": "orchestration only if historical 1.0 is kept; 1.1 if combined with B",
        "remaining_uncertainties": [
            "One small batch may still exhaust 8192 with empty content",
            "More calls increase accounting and lock complexity",
        ],
        "secrets_included": False,
    }


def compare_strategies(
    *,
    strategy_a: Mapping[str, Any],
    strategy_b: Mapping[str, Any],
    strategy_c: Mapping[str, Any],
    costs: Mapping[str, Any],
) -> dict[str, Any]:
    recommendation = "B+C"
    rationale = (
        "4B.2.6 confirmed budget exhaustion and zero visible JSON. "
        "Reasoning tokens are UNKNOWN, so A alone may buy more hidden tokens. "
        "The historical contract confirmedly duplicates claim text and requires "
        "free-form explanations across ten paragraphs. Compact 1.1-candidate "
        "reduces expected visible JSON without dropping fidelity fields. "
        "A one-case or two-case batch is the cheapest way to test whether "
        "Terra can emit JSON at all. Combined B+C changes two variables, but "
        "the first authorized canary should still be a single compact case so "
        "a repeat empty+length failure isolates json_object/reasoning rather "
        "than 10-case volume."
    )
    return {
        "phase": PHASE,
        "matrix": [
            {
                "strategy": "A",
                "compatibility_with_existing_evidence": strategy_a.get(
                    "compatibility_with_4b26_evidence"
                ),
                "technical_complexity": strategy_a.get("technical_complexity"),
                "truncation_risk": strategy_a.get("truncation_risk"),
                "resume_capability": strategy_a.get("resume_capability"),
                "estimated_cost": "If 12288-24576 tokens are fully used: see terra_cost_scenarios.json",
                "proposition_level_control": strategy_a.get("proposition_level_control"),
                "nineteen_chapter_fit": strategy_a.get("nineteen_chapter_fit"),
                "version_changes": strategy_a.get("version_changes"),
                "remaining_uncertainties": strategy_a.get("remaining_uncertainties"),
            },
            {
                "strategy": "B",
                "compatibility_with_existing_evidence": strategy_b.get(
                    "compatibility_with_4b26_evidence"
                ),
                "technical_complexity": strategy_b.get("technical_complexity"),
                "truncation_risk": strategy_b.get("truncation_risk"),
                "resume_capability": strategy_b.get("resume_capability"),
                "estimated_cost": strategy_b.get("estimated_min_json_tokens_candidate"),
                "proposition_level_control": strategy_b.get("proposition_level_control"),
                "nineteen_chapter_fit": strategy_b.get("nineteen_chapter_fit"),
                "version_changes": strategy_b.get("version_changes"),
                "remaining_uncertainties": strategy_b.get("remaining_uncertainties"),
            },
            {
                "strategy": "C",
                "compatibility_with_existing_evidence": strategy_c.get(
                    "compatibility_with_4b26_evidence"
                ),
                "technical_complexity": strategy_c.get("technical_complexity"),
                "truncation_risk": strategy_c.get("truncation_risk"),
                "resume_capability": strategy_c.get("resume_capability"),
                "estimated_cost": "See strategy_c rows in terra_cost_scenarios.json",
                "proposition_level_control": strategy_c.get("proposition_level_control"),
                "nineteen_chapter_fit": strategy_c.get("nineteen_chapter_fit"),
                "version_changes": strategy_c.get("version_changes"),
                "remaining_uncertainties": strategy_c.get("remaining_uncertainties"),
            },
            {
                "strategy": "B+C",
                "compatibility_with_existing_evidence": (
                    "Best match: reduce confirmed verbosity and isolate JSON emission."
                ),
                "technical_complexity": "MEDIUM",
                "truncation_risk": "LOWEST among analyzed options",
                "resume_capability": "HIGH",
                "estimated_cost": costs.get("strategy_c"),
                "proposition_level_control": "PRESERVED",
                "nineteen_chapter_fit": "ALIGNED",
                "version_changes": "1.1-candidate only; 1.0 frozen",
                "remaining_uncertainties": [
                    "json_object semantic production",
                    "reasoning_tokens",
                    "Terra semantic quality still untested",
                ],
            },
        ],
        "recommendation": recommendation,
        "rationale": rationale,
        "not_a_preference": True,
        "derived_from_investigation": True,
        "pricing": pricing_context(),
        "secrets_included": False,
    }


def proposed_next_canary(costs: Mapping[str, Any]) -> dict[str, Any]:
    one = None
    for row in costs.get("strategy_c") or []:
        if row.get("batch_size") == 1:
            one = row
            break
    return {
        "authorization": "PROPOSAL_ONLY_NOT_AN_AUTHORIZATION",
        "model": MODEL,
        "endpoint": "chat.completions",
        "prompt_version": CANDIDATE_PROMPT_VERSION,
        "transport_version": CANDIDATE_TRANSPORT_VERSION,
        "historical_1_0_unchanged": True,
        "cases": 1,
        "first_case_handle": "h01",
        "first_case_id": SCORED_CASE_ORDER[0][1],
        "why_one_positive_first": (
            "4B.2.6 produced no decisions. The first question is whether Terra "
            "can emit usable JSON. h01 is the smallest isolation of that "
            "question. Negative-case power is out of scope until JSON exists."
        ),
        "budget": {
            "field": "max_completion_tokens",
            "value": SEMANTIC_TOKEN_BUDGET,
            "strategy_a_increase_deferred": True,
            "why": (
                "If a compact 1-case request still finishes with length and "
                "empty content, the problem is not the 10-case output volume. "
                "Only then is a budget increase diagnostic."
            ),
        },
        "estimated_cost": (one or {}).get("if_one_call_returns_min_json"),
        "worst_case_if_budget_exhausted": (one or {}).get("if_one_call_exhausts_8192"),
        "success_criteria": [
            "Exactly one authorized Terra call",
            "Usable JSON object parsed without repair",
            "finish_reason != length with empty content",
            "h01 present with claim spans covering the paragraph",
            "No human-label leakage",
            "No cache acceptance even if SUPPORTED",
            "Missing cases remain unevaluated, not accepted",
        ],
        "stop_conditions": [
            "HTTP 400 or any request error",
            "finish_reason=length and empty or non-JSON content",
            "Any retry, fallback, or Sonnet call",
            "Any second Terra call",
            "Any production cache write",
        ],
        "not_success": [
            "HTTP 200 without JSON",
            "A FakeAI pass",
            "Local serialization of json_object",
        ],
    }


def candidate_request_identities(payload: Mapping[str, Any]) -> dict[str, Any]:
    gate = extract_gate_input(payload)
    full = build_candidate_payload(gate)
    one = build_candidate_payload(_slice_gate_input(gate, ["h01"]))
    captured_full = capture_openai_sdk_chat_request(full)
    captured_one = capture_openai_sdk_chat_request(one)
    full_sha = content_hash(json.dumps(full, ensure_ascii=False, sort_keys=True))
    one_sha = content_hash(json.dumps(one, ensure_ascii=False, sort_keys=True))
    return {
        "historical_4b26_sha256": EXPECTED_REQUEST_SHA256_4B26,
        "candidate_10_case_sha256": full_sha,
        "candidate_1_case_sha256": one_sha,
        "candidate_10_differs_from_historical": full_sha != EXPECTED_REQUEST_SHA256_4B26,
        "candidate_1_differs_from_historical": one_sha != EXPECTED_REQUEST_SHA256_4B26,
        "candidate_10_network_calls": captured_full.get("network_calls"),
        "candidate_1_network_calls": captured_one.get("network_calls"),
        "label_leak_10": audit_label_leak(full).get("label_leakage"),
        "label_leak_1": audit_label_leak(one).get("label_leakage"),
        "never_present_as_identical_to_4b26": True,
    }


__all__ = [
    "analyze_strategy_a",
    "analyze_strategy_b",
    "analyze_strategy_c",
    "build_candidate_payload",
    "candidate_request_identities",
    "compare_strategies",
    "proposed_next_canary",
]
