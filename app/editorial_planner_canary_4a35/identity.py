"""A.3.5 pre-call identities. Mismatch = BLOCKED_PRECALL, 0 provider calls."""

from __future__ import annotations

from typing import Any

from app.editorial_planner_canary_4a35.constants import (
    A33_CANDIDATE_SHA256,
    A33_PROMPT,
    A33_PROMPT_INSTRUCTIONS_SHA256,
    A33_PROMPT_SHA256,
    A33_PROMPT_SYSTEM_SHA256,
    A33_REQUEST_UTF8_BYTES,
    A3_CANDIDATE_SHA256,
    ADAPTED_SCHEMA_BYTES,
    ADAPTED_SCHEMA_SHA256,
    AUTHORIZATION_SCOPE,
    CANONICAL_LANGUAGE_SOURCE,
    EXPECTED_CANONICAL_DOCUMENT_LANGUAGE,
    EXPECTED_IDEA_COUNT,
    EXPECTED_REQUEST_CHARS,
    EXPECTED_REQUEST_SHA256,
    EXPECTED_REQUEST_UTF8_BYTES,
    EXPECTED_SOURCE_MAP_BYTES,
    EXPECTED_SOURCE_MAP_CHARS,
    EXPECTED_SOURCE_MAP_SHA256,
    FORBIDDEN_PROMPT_HACK_TOKENS,
    FORENSIC_FOLLOWUP_IDEAS,
    HISTORICAL_A33_REQUEST_SHA256,
    HISTORICAL_A3_REQUEST_SHA256,
    HISTORICAL_PROMPT,
    HISTORICAL_PROPOSED_MAX_OUTPUT,
    LANGUAGE_POLICY,
    MODEL,
    PHASE,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    RAW_SCHEMA_BYTES,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.editorial_planner_canary_4a35.guard import PlannerCanaryError
from app.editorial_planner_canary_4a35.paths import (
    a3_candidate_path,
    a33_candidate_path,
    production_editorial_plan_path,
    production_source_map_path,
    repo_root,
)
from app.editorial_planner_forensics_4a34.budget import measure_input_budget
from app.editorial_planner_forensics_4a34.coverage_stress import run_coverage_stress
from app.editorial_planner_forensics_4a34.identity import (
    compare_historical_prompt,
    compare_prompt_101,
    compare_schema,
    file_sha256,
    source_map_identity_audit,
)
from app.editorial_planner_forensics_4a34.payload import (
    build_production_request,
    production_settings,
    request_identity,
)
from app.editorial_planner_forensics_4a34.prompt_audit import prompt_coverage_analysis
from app.editorial_planner_language_policy_4a32.language import load_language_provenance
from app.editorial_planner_preflight_4a2.coverage import input_coverage_audit
from app.editorial_planning.errors import DocumentLanguageBlocked
from app.editorial_planning.pipeline import load_published_source_map
from app.editorial_planning.prompt import prompt_bundle as prompt_bundle_v10
from app.editorial_planning.prompt_v101 import prompt_bundle as prompt_bundle_v101
from app.editorial_planning.prompt_v102 import (
    coverage_hardening_rule,
    prompt_bundle as prompt_bundle_v102,
)
from app.editorial_planning.settings import frozen_production_settings


def _status(ok: bool) -> str:
    return "MATCH" if ok else "MISMATCH"


def _candidate_ok(path, expected: str) -> dict[str, Any]:
    if not path.is_file():
        return {"present": False, "unchanged": False, "sha256": None, "expected": expected}
    digest = file_sha256(path)
    return {
        "present": True,
        "unchanged": digest == expected,
        "sha256": digest,
        "expected": expected,
        "path": str(path).replace("\\", "/"),
    }


def precall_identity() -> dict[str, Any]:
    source_identity = source_map_identity_audit()
    schema = compare_schema()
    historical_prompt = compare_historical_prompt()
    prompt_101_live = compare_prompt_101()
    prompt_audit = prompt_coverage_analysis()
    a3_candidate = _candidate_ok(a3_candidate_path(), A3_CANDIDATE_SHA256)
    a33_candidate = _candidate_ok(a33_candidate_path(), A33_CANDIDATE_SHA256)
    frozen = frozen_production_settings()
    historical_ok = frozen.max_output_tokens == HISTORICAL_PROPOSED_MAX_OUTPUT
    publication_absent = not production_editorial_plan_path().is_file()
    source_path = production_source_map_path()
    source_path_ok = source_path.is_file()

    v10 = prompt_bundle_v10()
    v101 = prompt_bundle_v101(EXPECTED_CANONICAL_DOCUMENT_LANGUAGE)
    v102 = prompt_bundle_v102(EXPECTED_CANONICAL_DOCUMENT_LANGUAGE)
    hardening = coverage_hardening_rule()
    v101_ok = (
        v101.get("system_sha256") == A33_PROMPT_SYSTEM_SHA256
        and v101.get("instructions_sha256") == A33_PROMPT_INSTRUCTIONS_SHA256
        and v101.get("prompt_sha256") == A33_PROMPT_SHA256
        and v101.get("version") == A33_PROMPT
        and not v101.get("historical_prompt_mutated")
    )
    v102_contract_ok = (
        v102.get("version") == PROMPT_VERSION
        and hardening.strip() in v102.get("system", "")
        and hardening.strip() in v102.get("instructions", "")
        and "AUTO-VERIFICATION DE SORTIE" in v102.get("system", "")
        and "Chaque IDEA d'entrée a exactement une disposition primaire" in v102.get("system", "")
        and "N'expose pas de chaîne de pensée" in v102.get("system", "")
    )
    prompt_blob = f"{v102.get('system', '')}\n{v102.get('instructions', '')}"
    idea_specific = any(token in prompt_blob for token in FORENSIC_FOLLOWUP_IDEAS)
    content_specific = any(
        token.lower() in prompt_blob.lower() for token in FORBIDDEN_PROMPT_HACK_TOKENS
    )

    block_reasons: list[str] = []
    if source_identity.get("blocked"):
        block_reasons.append("source_map_identity")
    if source_identity.get("status") != "PASS" and not source_identity.get("blocked"):
        block_reasons.append("source_map_inventory_or_validation")
    if schema.get("identity") != "MATCH":
        block_reasons.append("schema_identity")
    if historical_prompt.get("identity") != "MATCH":
        block_reasons.append("historical_prompt_1_0_mutated")
    if not v101_ok:
        block_reasons.append("historical_prompt_1_0_1_mutated")
    if not v102_contract_ok:
        block_reasons.append("prompt_1_0_2_coverage_contract")
    if idea_specific:
        block_reasons.append("idea_specific_prompt_hack")
    if content_specific:
        block_reasons.append("content_specific_prompt_hack")
    if not a3_candidate.get("unchanged"):
        block_reasons.append("historical_a3_candidate_mutated")
    if not a33_candidate.get("unchanged"):
        block_reasons.append("historical_a33_candidate_mutated")
    if not historical_ok:
        block_reasons.append("historical_max_output_mutated")
    if not publication_absent:
        block_reasons.append("editorial_plan_json_already_present")
    if not source_path_ok:
        block_reasons.append("source_map_missing")

    source_map = None
    raw = b""
    digest = ""
    request: dict[str, Any] = {}
    coverage: dict[str, Any] = {}
    input_budget: dict[str, Any] = {}
    settings_override = None
    request_ok = False
    payload: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    language = ""
    fakeai: dict[str, Any] = {}

    if source_path_ok and not source_identity.get("blocked"):
        source_map, raw, digest, _path = load_published_source_map(PROJECT_NAME)
        try:
            provenance = load_language_provenance(
                source_map, project_name=PROJECT_NAME, root=repo_root()
            )
            language = str(provenance.get("canonical_document_language") or "")
        except DocumentLanguageBlocked as exc:
            block_reasons.append("document_language_blocked")
            provenance = {
                "blocked": True,
                "canonical_document_language": "",
                "error": str(exc),
            }
            language = ""

        if provenance.get("blocked") or not language:
            if "document_language_blocked" not in block_reasons:
                block_reasons.append("canonical_language_unresolved")
        elif language != EXPECTED_CANONICAL_DOCUMENT_LANGUAGE:
            block_reasons.append("canonical_language_not_derived_en")

        if language and "document_language_blocked" not in block_reasons:
            settings_override = production_settings(
                max_output_tokens=PRODUCTION_MAX_OUTPUT_TOKENS
            )
            request = request_identity(
                source_map,
                canonical_document_language=language,
                max_output_tokens=PRODUCTION_MAX_OUTPUT_TOKENS,
            )
            payload = dict(request.get("payload") or {})
            coverage = input_coverage_audit(source_map)
            ai_request = build_production_request(
                source_map,
                canonical_document_language=language,
                max_output_tokens=PRODUCTION_MAX_OUTPUT_TOKENS,
            )
            input_budget = measure_input_budget(
                system=ai_request.system_prompt or "",
                user=ai_request.prompt,
                payload=payload,
                a33_payload_utf8_bytes=A33_REQUEST_UTF8_BYTES,
                selected_max_output=PRODUCTION_MAX_OUTPUT_TOKENS,
            )
            fakeai = run_coverage_stress(source_map)
            v102_live = prompt_bundle_v102(language)

            sha = request.get("request_sha256")
            sha2 = request.get("request_sha256_repeat")
            if sha != EXPECTED_REQUEST_SHA256:
                block_reasons.append("request_sha256_mismatch")
            if sha == HISTORICAL_A3_REQUEST_SHA256:
                block_reasons.append("request_identical_to_historical_a3")
            if sha == HISTORICAL_A33_REQUEST_SHA256:
                block_reasons.append("request_identical_to_historical_a33")
            if sha != sha2 or not request.get("request_determinism"):
                block_reasons.append("request_not_deterministic")
            if request.get("canonical_document_language") != language:
                block_reasons.append("request_language_field_mismatch")
            if not request.get("request_explicitly_requires_language"):
                block_reasons.append("request_missing_language_instruction")
            if request.get("max_tokens") != PRODUCTION_MAX_OUTPUT_TOKENS:
                block_reasons.append("max_tokens_not_65536")
            if request.get("model") != MODEL:
                block_reasons.append("model_mismatch")
            if request.get("thinking_present"):
                block_reasons.append("thinking_injected")
            if request.get("effort_present"):
                block_reasons.append("effort_injected")
            if request.get("thinking_mode") != THINKING_MODE:
                block_reasons.append("thinking_mode_mismatch")
            if request.get("effort") is not None:
                block_reasons.append("effort_not_none")
            if not coverage.get("pass"):
                block_reasons.append("input_coverage")
            if not request.get("no_technical_chunks"):
                block_reasons.append("technical_chunks")
            idea_count = int(coverage.get("idea_count") or 0)
            if idea_count != EXPECTED_IDEA_COUNT:
                block_reasons.append("idea_count")
            if int(request.get("expected_idea_count") or 0) != idea_count:
                block_reasons.append("expected_idea_count_not_dynamic")
            if not request.get("expected_idea_count_dynamic"):
                block_reasons.append("expected_idea_count_hardcoded")
            if not request.get("expected_idea_count_in_user"):
                block_reasons.append("expected_idea_count_missing_from_user")
            if int(request.get("idea_ids_in_user") or 0) != EXPECTED_IDEA_COUNT:
                block_reasons.append("idea_manifest_incomplete")
            if int(coverage.get("unknown_input_refs") or 0) != 0:
                block_reasons.append("unknown_input_refs")
            if settings_override.max_output_tokens != PRODUCTION_MAX_OUTPUT_TOKENS:
                block_reasons.append("override_settings_max_output")
            if frozen.max_output_tokens != HISTORICAL_PROPOSED_MAX_OUTPUT:
                block_reasons.append("frozen_settings_mutated")
            if v102_live.get("version") != PROMPT_VERSION:
                block_reasons.append("prompt_version_not_102")
            if request.get("prompt_version") != PROMPT_VERSION:
                block_reasons.append("request_prompt_version")
            if not request.get("hardening_in_system"):
                block_reasons.append("hardening_missing_from_system")
            if not request.get("self_check_in_system"):
                block_reasons.append("self_check_missing_from_system")
            if request.get("idea_specific_prompting"):
                block_reasons.append("idea_specific_prompting")
            if request.get("full_id_manifest_duplicated"):
                block_reasons.append("full_id_manifest_duplicated")
            if input_budget.get("context_safety") != "PASS":
                block_reasons.append("context_safety")
            if fakeai.get("status") != "PASS":
                block_reasons.append("fakeai_coverage_stress")
            request_ok = sha == EXPECTED_REQUEST_SHA256 and sha == sha2

    blocked = bool(block_reasons)
    request_identity_status = _status(request_ok)
    if "request_sha256_mismatch" in block_reasons:
        request_identity_status = "MISMATCH"

    return {
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "blocked_precall": blocked,
        "block_reasons": block_reasons,
        "block_reason": "; ".join(block_reasons) if block_reasons else None,
        "source_identity": source_identity,
        "schema": schema,
        "historical_prompt": historical_prompt,
        "historical_prompt_1_0_1": {
            **{k: v for k, v in prompt_101_live.items() if k not in {"system", "instructions"}},
            "system_sha256_expected": A33_PROMPT_SYSTEM_SHA256,
            "instructions_sha256_expected": A33_PROMPT_INSTRUCTIONS_SHA256,
            "prompt_sha256_expected": A33_PROMPT_SHA256,
            "unchanged": v101_ok,
        },
        "prompt_coverage_audit": {
            k: v
            for k, v in prompt_audit.items()
            if k not in {"v10", "v101", "v102", "coverage_wording_1_0_system"}
        },
        "historical_a3_candidate": a3_candidate,
        "historical_a33_candidate": a33_candidate,
        "schema_identity": schema.get("identity"),
        "prompt_identity": historical_prompt.get("identity"),
        "historical_prompt_mutated": historical_prompt.get("historical_prompt_mutated"),
        "historical_prompt_1_0_1_mutated": not v101_ok,
        "source_map_sha256": digest or source_identity.get("sha256"),
        "source_map_bytes": len(raw) or source_identity.get("bytes"),
        "source_map_chars": source_identity.get("chars") or EXPECTED_SOURCE_MAP_CHARS,
        "expected_source_map_sha256": EXPECTED_SOURCE_MAP_SHA256,
        "expected_source_map_bytes": EXPECTED_SOURCE_MAP_BYTES,
        "source_map_path": str(source_path).replace("\\", "/"),
        "canonical_language_source": CANONICAL_LANGUAGE_SOURCE,
        "language_policy": LANGUAGE_POLICY,
        "language_provenance": provenance,
        "canonical_document_language": language or provenance.get(
            "canonical_document_language"
        ),
        "language_hardcoded": False,
        "historical_proposed_max_output": HISTORICAL_PROPOSED_MAX_OUTPUT,
        "historical_settings_unchanged": historical_ok,
        "frozen_settings_max_output_tokens": frozen.max_output_tokens,
        "production_max_output_override": PRODUCTION_MAX_OUTPUT_TOKENS,
        "provider": PROVIDER,
        "model": payload.get("model") or MODEL,
        "max_tokens": payload.get("max_tokens"),
        "thinking_present_in_payload": request.get("thinking_present"),
        "effort_present_in_payload": request.get("effort_present"),
        "temperature_present_in_payload": request.get("temperature_present"),
        "thinking_mode": request.get("thinking_mode") or THINKING_MODE,
        "effort": request.get("effort"),
        "thinking_budget_tokens": None,
        "payload_keys": request.get("payload_keys")
        or (sorted(payload) if payload else None),
        "expected_request_sha256": EXPECTED_REQUEST_SHA256,
        "historical_a3_request_sha256": HISTORICAL_A3_REQUEST_SHA256,
        "historical_a33_request_sha256": HISTORICAL_A33_REQUEST_SHA256,
        "actual_request_sha256": request.get("request_sha256"),
        "actual_request_sha256_repeat": request.get("request_sha256_repeat"),
        "request_identity": request_identity_status,
        "request_determinism": bool(request.get("request_determinism")),
        "request_changed_from_a3": (
            bool(request.get("request_sha256"))
            and request.get("request_sha256") != HISTORICAL_A3_REQUEST_SHA256
        ),
        "request_changed_from_a33": (
            bool(request.get("request_sha256"))
            and request.get("request_sha256") != HISTORICAL_A33_REQUEST_SHA256
        ),
        "request_chars": request.get("request_chars"),
        "request_utf8_bytes": request.get("request_utf8_bytes"),
        "expected_request_chars": EXPECTED_REQUEST_CHARS,
        "expected_request_utf8_bytes": EXPECTED_REQUEST_UTF8_BYTES,
        "prompt": PROMPT_VERSION,
        "historical_prompt_version": HISTORICAL_PROMPT,
        "a33_prompt_version": A33_PROMPT,
        "transport": TRANSPORT_VERSION,
        "schema_raw_adapted": f"{RAW_SCHEMA_BYTES} / {ADAPTED_SCHEMA_BYTES}",
        "schema_hash": ADAPTED_SCHEMA_SHA256,
        "coverage": coverage,
        "precall_idea_coverage": (
            f"{int(coverage.get('idea_count') or 0)} / {EXPECTED_IDEA_COUNT}"
            if coverage
            else None
        ),
        "expected_idea_count": request.get("expected_idea_count"),
        "input_budget": input_budget,
        "fakeai_coverage_stress": {
            k: v for k, v in fakeai.items() if k != "scenarios"
        }
        if fakeai
        else {},
        "fakeai_coverage_stress_status": fakeai.get("status"),
        "prompt_v10": {k: v for k, v in v10.items() if k not in {"system", "instructions"}},
        "prompt_v101": {k: v for k, v in v101.items() if k not in {"system", "instructions"}},
        "prompt_v102": {k: v for k, v in v102.items() if k not in {"system", "instructions"}},
        "request_audit": {k: v for k, v in request.items() if k != "payload"},
        "payload": payload,
        "publication_absent": publication_absent,
        "production_source_map_included": True,
        "secrets_included": False,
        "retries": 0,
        "connect_timeout": 30.0,
        "read_timeout": 1800.0,
        "idea_specific_prompting": idea_specific,
        "content_specific_prompting": content_specific,
        "new_grammar_canary_required": "NO",
        "new_synthetic_contract_canary_required": "NO",
    }


def require_precall_identity(identity: dict[str, Any] | None = None) -> dict[str, Any]:
    identity = identity or precall_identity()
    if identity.get("blocked_precall"):
        raise PlannerCanaryError(
            "BLOCKED_PRECALL: " + str(identity.get("block_reason"))
        )
    return identity


__all__ = ["precall_identity", "require_precall_identity"]
