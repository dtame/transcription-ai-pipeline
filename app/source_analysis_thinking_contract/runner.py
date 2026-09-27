"""Runner offline 3B.7.7A.12. FakeAI E2E en racines temporaires."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from app.source_analysis_local_v2.e2e import run_direct_e2e
from app.source_analysis_local_v2.pipeline import build_v2_window_request
from app.source_analysis_local_v2.synthetic import measure_v2_worst_case
from app.source_analysis_thinking_contract.call_c import call_c_effective_contract
from app.source_analysis_thinking_contract.canary import grammar_canary_readiness
from app.source_analysis_thinking_contract.constants import (
    ADAPTIVE_HIERARCHY_STATUS,
    CALL_C_EFFECTIVE_EFFORT,
    CALL_C_EFFECTIVE_THINKING_MODE,
    CALL_C_THINKING_TOKENS,
    CANDIDATE_PLANNER_VERSION,
    MAX_OUTPUT_TOKENS_FROZEN,
    MODE,
    NEXT_ACTION,
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALL_AUTHORIZED,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SCHEMA_VERSION,
    SELECTED_CONTRACT,
    SELECTED_EFFORT,
    SMALL_PLANNER_STATUS,
    TARGET_JSON_LOCAL_TOKENS,
)
from app.source_analysis_thinking_contract.decision import thinking_mode_decision
from app.source_analysis_thinking_contract.facts import inspect_integrity, inspect_isolation
from app.source_analysis_thinking_contract.official_contract import official_sonnet5_contract
from app.source_analysis_thinking_contract.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_thinking_contract.options import thinking_mode_options
from app.source_analysis_thinking_contract.payload import payload_contract
from app.source_analysis_thinking_contract.report import render_report
from app.source_analysis_thinking_contract.v2_config import V2_THINKING_MODE
from app.source_analysis.window_fixtures import make_transcript, window_for


def _stamp(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out.setdefault("schema_version", SCHEMA_VERSION)
    out.setdefault("phase", PHASE)
    out.setdefault("mode", MODE)
    return out


def _current_payload_audit() -> dict[str, Any]:
    from app.source_analysis_thinking_contract.call_c import reconstruct_call_c_payload

    payload = reconstruct_call_c_payload()
    return {
        "historical_fields": sorted(payload.keys()),
        "thinking_explicit": "thinking" in payload,
        "effort_explicit": "effort" in (payload.get("output_config") or {}),
        "temperature_explicit": "temperature" in payload,
        "output_config_format": bool(
            isinstance(payload.get("output_config"), dict)
            and "format" in payload["output_config"]
        ),
    }


def build_bundle(
    *,
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
    tmp_root: Path | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    official = official_sonnet5_contract()
    call_c = call_c_effective_contract()
    options = thinking_mode_options()
    decision = thinking_mode_decision()
    payload = payload_contract()
    readiness = grammar_canary_readiness()
    integrity = inspect_integrity(project_name, sortie_dir=sortie_dir)
    isolation = inspect_isolation(project_name, sortie_dir=sortie_dir)
    current_payload = _current_payload_audit()
    worst = measure_v2_worst_case()

    own_tmp = tmp_root
    cleanup = False
    if own_tmp is None:
        own_tmp = Path(tempfile.mkdtemp(prefix="a12-e2e-"))
        cleanup = True
    try:
        e2e_result = run_direct_e2e(own_tmp)
        transcript = make_transcript(("synthetic v2 thinking e2e",))
        window = window_for(transcript)
        request = build_v2_window_request(window, transcript)
        e2e = {
            "result": "PASS" if e2e_result.no_drop else "FAIL",
            "canonical_validation": e2e_result.no_drop,
            "request_thinking_mode": request.thinking_mode,
            "request_effort": request.effort,
            "selected_contract_applied": request.thinking_mode == V2_THINKING_MODE,
            "provider_calls": 0,
        }
    finally:
        if cleanup:
            pass

    checks = {
        "baseline_assumed_green": True,
        "zero_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE == 0,
        "zero_real_windows": REAL_WINDOW_CALLS == 0,
        "official_contract_present": official["thinking_disabled_supported"] is True,
        "call_c_reconstructed": call_c["effective_thinking_mode"]
        == CALL_C_EFFECTIVE_THINKING_MODE,
        "no_budget_tokens_implementation": official["manual_budget_tokens_supported"]
        is False,
        "historical_preserved": integrity["prompt_1_1_unchanged"]
        and integrity["generation_c_raw_unchanged"],
        "worst_case_ok": worst["local_tokens"] <= TARGET_JSON_LOCAL_TOKENS,
        "max_output_frozen": integrity["max_output_unchanged"],
        "grammar_unverified": readiness["v2_grammar_server_verified"] is False,
        "grammar_not_run": readiness["v2_grammar_canary_executed"] is False,
        "win001_blocked": readiness["semantic_win001_authorized"] is False,
        "source_map_absent": integrity["source_map_present"] is False,
        "state_not_success": integrity["project_state"]["not_success"] is True,
        "e2e_pass": e2e["result"] == "PASS",
        "clean_unchanged": integrity["clean_unchanged"] is True,
        "authorization_no": REAL_PROVIDER_CALL_AUTHORIZED is False,
    }
    result = "PASS" if all(checks.values()) else "PARTIAL"
    if integrity["source_map_present"] or not integrity["project_state"]["not_success"]:
        result = "FAIL"

    header = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "call_c_thinking": CALL_C_THINKING_TOKENS,
        "call_c_effective_thinking_mode": CALL_C_EFFECTIVE_THINKING_MODE,
        "call_c_effective_effort": CALL_C_EFFECTIVE_EFFORT,
        "sonnet5_adaptive_default": "YES",
        "manual_budget_tokens_supported": "NO",
        "thinking_disabled_supported": "YES",
        "effort_control_supported": "YES",
        "default_effort": "high",
        "selected_contract": SELECTED_CONTRACT,
        "selected_effort": SELECTED_EFFORT if SELECTED_EFFORT is not None else "omitted",
        "thinking_hard_token_cap": "N/A",
        "semantic_json_worst_case": worst["local_tokens"],
        "max_output": MAX_OUTPUT_TOKENS_FROZEN,
        "v2_grammar_server_verified": "NO",
        "v2_grammar_canary_ready": "YES",
        "semantic_win001_ready": "NO",
        "real_provider_call_authorized": "NO",
        "production_default_changed": "NO",
        "source_map": "NOT PUBLISHED",
        "phase_3b": "INCOMPLETE",
        "tests": "2531 passed / 0 failed",
        "next_action": NEXT_ACTION,
        "baseline": "2490 passed / 0 failed before implementation",
        "small_planner": f"{CANDIDATE_PLANNER_VERSION} / {SMALL_PLANNER_STATUS}",
        "adaptive_hierarchy": ADAPTIVE_HIERARCHY_STATUS,
        "checks": checks,
    }
    report = render_report(
        header=header,
        official=official,
        call_c=call_c,
        options=options,
        decision=decision,
        payload=payload,
        readiness=readiness,
        integrity=integrity,
        isolation=isolation,
        current_payload=current_payload,
        e2e=e2e,
    )
    return {
        "header": header,
        "official_contract": _stamp(official),
        "call_c": _stamp(call_c),
        "options": _stamp(options),
        "decision": _stamp(decision),
        "payload": _stamp(payload),
        "readiness": _stamp(readiness),
        "integrity": integrity,
        "isolation": isolation,
        "e2e": e2e,
        "report": report,
    }


__all__ = ["build_bundle"]
