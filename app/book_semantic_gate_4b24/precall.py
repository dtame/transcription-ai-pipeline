"""Pre-call gates. Provider is not contacted here."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_generation.evidence import build_chapter_evidence, evidence_identity
from app.book_generation.hydrate import load_clean_transcript_index
from app.book_generation.language import resolve_canonical_language
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.budget import measure_chapter_budget
from app.ai.provider_preflight import (
    REASON_PROVIDER_CREDENTIAL_NOT_READY,
    check_provider_runtime_readiness,
)
from app.book_semantic_gate_4b24.constants import (
    AUTHORIZATION_SCOPE,
    CONSERVATIVE_MAX_OUTPUT_TOKENS,
    EXPECTED_EVIDENCE_SHA256,
    EXPECTED_NEGATIVE_CASES,
    EXPECTED_POSITIVE_CASES,
    EXPECTED_REQUEST_SHA256,
    EXPECTED_SCORED_CASES,
    MODEL,
    OUTPUT_MODE,
    PHASE,
    PROJECT_NAME,
    PROVIDER,
    SCORED_CASE_ORDER,
    TARGET_CHAPTER_ID,
)
from app.book_semantic_gate_4b24.costing import estimate_canary_cost
from app.book_semantic_gate_4b24.engine import credential_available
from app.book_semantic_gate_4b24.identity import (
    benchmark_identity,
    contract_identities,
    load_frozen_benchmark,
    load_json,
    scored_cases,
    snapshot_identities,
    verify_canonical_inputs,
)
from app.book_semantic_gate_4b24.leak import audit_label_leak
from app.book_semantic_gate_4b24.paths import (
    historical_4b22_dir,
    historical_4b2_dir,
    production_book_path,
)
from app.book_semantic_gate_4b24.payload import (
    build_benchmark_candidate,
    build_benchmark_gate_input,
    build_request_twice,
    paragraph_texts_from_candidate,
)
from app.editorial_planning.pipeline import (
    load_published_editorial_plan,
    load_published_source_map,
)


def build_precall(*, root: Path | None = None) -> dict[str, Any]:
    before = verify_canonical_inputs(root=root)
    before_snap = snapshot_identities(before)
    benchmark_meta = benchmark_identity(root=root)
    contracts = contract_identities()
    blockers: list[str] = []

    if not before["source_map_unchanged"]:
        blockers.append("source_map")
    if not before["editorial_plan_unchanged"]:
        blockers.append("editorial_plan")
    if not before["clean_transcript_unchanged"]:
        blockers.append("clean_transcript")
    if not before["candidate_4b2_unchanged"]:
        blockers.append("historical_4b2_candidate")
    if not before["candidate_4b22_unchanged"]:
        blockers.append("historical_4b22_candidate")
    if not before["raw_4b2_unchanged"]:
        blockers.append("historical_4b2_raw")
    if not benchmark_meta["identity_match"]:
        blockers.append("benchmark_identity")
    if not contracts["contract_match"]:
        blockers.append("schema_or_prompt_or_transport")
    if not production_book_absent(PROJECT_NAME):
        blockers.append("book_json_present")

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
    historical = historical_4b2_dir(root=root)
    hardened = historical_4b22_dir(root=root)
    candidate_4b2 = load_json(historical / "chapter_CH016_candidate.json")
    candidate_4b22 = load_json(hardened / "chapter_CH016_candidate.json")
    benchmark = load_frozen_benchmark(root=root)
    scored = scored_cases(benchmark)
    if len(scored) != EXPECTED_SCORED_CASES:
        blockers.append("benchmark_count")

    chapter = next(item for item in plan.chapters if item.chapter_id == TARGET_CHAPTER_ID)
    evidence = build_chapter_evidence(
        plan,
        source_map,
        chapter,
        language=language,
        hydrate=True,
        transcript_index=index,
    )
    evidence_sha = evidence_identity(evidence)
    if evidence_sha != EXPECTED_EVIDENCE_SHA256:
        blockers.append("evidence_identity")

    candidate = build_benchmark_candidate(
        benchmark=benchmark,
        candidate_4b2=candidate_4b2,
        candidate_4b22=candidate_4b22,
    )
    gate_input = build_benchmark_gate_input(
        candidate=candidate, evidence=evidence, language=language
    )
    texts = paragraph_texts_from_candidate(candidate)
    required = [handle for handle, _case_id in SCORED_CASE_ORDER]
    if set(texts) != set(required):
        blockers.append("benchmark_coverage")

    positives = [item for item in scored if item.get("role") == "positive"]
    negatives = [item for item in scored if item.get("role") == "negative"]
    if len(positives) != EXPECTED_POSITIVE_CASES or len(negatives) != EXPECTED_NEGATIVE_CASES:
        blockers.append("benchmark_count")

    twice = build_request_twice(
        gate_input, max_output_tokens=CONSERVATIVE_MAX_OUTPUT_TOKENS
    )
    if not twice["deterministic"]:
        blockers.append("request_determinism")
    if twice["first"]["sha256"] != EXPECTED_REQUEST_SHA256:
        blockers.append("request_sha256")

    request = twice["request"]
    payload = twice["payload"]
    leak = audit_label_leak(
        payload,
        request={
            "system_prompt": request.system_prompt,
            "prompt": request.prompt,
        },
    )
    if not leak["pass"]:
        blockers.append("label_leakage")

    estimate = estimate_canary_cost(
        system_prompt=str(request.system_prompt or ""),
        user_prompt=str(request.prompt or ""),
        max_output_tokens=int(request.max_output_tokens or CONSERVATIVE_MAX_OUTPUT_TOKENS),
    )
    if not estimate["context_safe"]:
        blockers.append("context_safety")
    if not credential_available():
        blockers.append("openai_credential")
    runtime = check_provider_runtime_readiness(
        PROVIDER,
        model=MODEL,
        request=request,
        output_mode=OUTPUT_MODE,
        construct_client=True,
    )
    if not runtime.ready:
        if runtime.primary_reason == REASON_PROVIDER_CREDENTIAL_NOT_READY:
            if "openai_credential" not in blockers:
                blockers.append("openai_credential")
        else:
            blockers.append("openai_runtime")

    budget = measure_chapter_budget(
        evidence=evidence,
        candidate=candidate,
        language=language,
        chapter_id=TARGET_CHAPTER_ID,
        idea_count=len(chapter.idea_refs),
        section_count=len(chapter.sections),
    )

    after = verify_canonical_inputs(root=root)
    after_snap = snapshot_identities(after)
    inputs_unchanged = before_snap == after_snap
    if not inputs_unchanged:
        blockers.append("input_mutation")

    blocked = bool(blockers)
    return {
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "blocked_precall": blocked,
        "block_reasons": blockers,
        "block_reason": blockers[0] if blockers else None,
        "identities_before": before,
        "identities_after": after,
        "inputs_unchanged": inputs_unchanged,
        "language": language,
        "benchmark": benchmark_meta,
        "contracts": contracts,
        "evidence_sha256": evidence_sha,
        "candidate_handles": required,
        "paragraph_texts": texts,
        "gate_input": gate_input,
        "request": {
            "sha256": twice["first"]["sha256"],
            "sha256_repeat": twice["second"]["sha256"],
            "expected_sha256": EXPECTED_REQUEST_SHA256,
            "identity_match": twice["first"]["sha256"] == EXPECTED_REQUEST_SHA256,
            "chars": twice["first"]["chars"],
            "bytes": twice["first"]["bytes"],
            "deterministic": twice["deterministic"],
            "temperature_present": twice["first"]["temperature_present"],
            "thinking_present": twice["first"]["thinking_present"],
            "response_format": twice["first"]["response_format"],
            "max_tokens": twice["first"]["max_tokens"],
            "max_completion_tokens": twice["first"].get("max_completion_tokens"),
            "model": twice["first"]["model"],
            "gate_input_sha256": twice["gate_input_sha256"],
        },
        "payload": payload,
        "ai_request": request,
        "label_leak": leak,
        "cost_estimate": estimate,
        "budget": {
            "context_safe": budget.get("context_safe"),
            "request": budget.get("request"),
            "output": budget.get("output"),
            "context_utilization_pessimistic": budget.get(
                "context_utilization_pessimistic"
            ),
        },
        "credential_available": credential_available(),
        "provider_runtime": runtime.to_dict(),
        "production_book_absent": not production_book_path().is_file(),
        "allowed_handles": list(evidence.get("allowed") or []),
        "scored_cases": scored,
        "http_sent": False,
        "engine_generate_called": False,
    }


__all__ = ["build_precall"]
