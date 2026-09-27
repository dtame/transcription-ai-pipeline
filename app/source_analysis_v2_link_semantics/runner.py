"""Runner offline 3B.7.7A.14. FakeAI en racines temporaires. 0 provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_local_v2.decoder import decode_v2_transport
from app.source_analysis_local_v2.links import INDEX_BASE, SELF_LINKS, link_contract
from app.source_analysis_local_v2.schema import build_semantic_transport_v2_schema
from app.source_analysis_local_v2.validator import validate_v2_links
from app.source_analysis_v2_grammar_canary.fixture import build_synthetic_fixture
from app.source_analysis_v2_link_semantics.constants import (
    A13_THINKING_TOKENS,
    CANDIDATE_WINDOW_ANALYSIS_PROMPT_VERSION,
    MODE,
    NEXT_ACTION,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    ROOT_CAUSE,
    SCHEMA_VERSION,
    SEMANTIC_TRANSPORT_VERSION_V2,
    SEMANTIC_WIN001_AUTHORIZED,
    TARGET_JSON_LOCAL_TOKENS,
    THINKING_CONTRACT,
)
from app.source_analysis_v2_link_semantics.evidence import (
    assert_a13_evidence_intact,
    protected_a13_hashes,
)
from app.source_analysis_v2_link_semantics.facts import (
    inspect_a14_integrity,
    inspect_isolation,
)
from app.source_analysis_v2_link_semantics.fixtures import (
    corrected_a13_transport,
    self_link_transport,
)
from app.source_analysis_v2_link_semantics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v2_link_semantics.preflight import (
    output_budget,
    prompt_overhead,
    real_seven_window_preflight,
    run_fakeai_matrix,
    schema_regression,
)
from app.source_analysis_v2_link_semantics.prompt_audit import prompt_hardening_facts
from app.source_analysis_v2_link_semantics.replay import replay_a13_offline
from app.source_analysis_v2_link_semantics.report import render_report


def _stamp(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out.setdefault("schema_version", SCHEMA_VERSION)
    out.setdefault("phase", PHASE)
    out.setdefault("mode", MODE)
    return out


def _fixture_matrix() -> dict[str, Any]:
    fixture = build_synthetic_fixture()
    allowed = set(fixture.window.owned_src_refs)
    corrected = corrected_a13_transport()
    self_link = self_link_transport()
    corrected_ok = False
    self_fail = False
    try:
        decoded = decode_v2_transport(corrected, allowed_source_refs=allowed)
        validate_v2_links(decoded)
        corrected_ok = True
    except Exception:
        corrected_ok = False
    try:
        decode_v2_transport(self_link, allowed_source_refs=allowed)
    except Exception:
        self_fail = True
    return {
        "corrected_pass": corrected_ok,
        "self_link_fail": self_fail,
    }


def build_bundle(
    *,
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
    tmp_root: Path | None = None,
    tests: str = "UNKNOWN",
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    hashes_before = protected_a13_hashes(project_name, sortie_dir=sortie_dir)
    replay = replay_a13_offline(project_name, sortie_dir=sortie_dir)
    contract = _stamp(link_contract())
    prompt = prompt_hardening_facts()
    schema = schema_regression()
    overhead = prompt_overhead()
    worst = output_budget()
    integrity = inspect_a14_integrity(project_name, sortie_dir=sortie_dir)
    isolation = inspect_isolation(project_name, sortie_dir=sortie_dir)
    fixtures = _fixture_matrix()
    e2e = run_fakeai_matrix(tmp_root)
    preflight = real_seven_window_preflight(project_name, sortie_dir=sortie_dir)
    identity = preflight["future_win001"]
    hashes_after = protected_a13_hashes(project_name, sortie_dir=sortie_dir)
    assert_a13_evidence_intact(hashes_before, hashes_after)

    source_map_absent = not source_map_path(project_name, sortie_dir=sortie_dir).exists()
    state = (integrity.get("project_state") or {})
    not_success = state.get("not_success", True)

    checks = {
        "zero_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE == 0,
        "zero_real_windows": REAL_WINDOW_CALLS == 0,
        "a13_replayed": replay.get("reproduced") is True,
        "a13_structured_pass": replay.get("structured_parse") == "PASS",
        "a13_decoder_fail": replay.get("v2_decoder") == "FAIL",
        "a13_evidence_intact": hashes_before == hashes_after,
        "corrected_fixture": fixtures["corrected_pass"],
        "self_link_rejected": fixtures["self_link_fail"],
        "schema_unchanged": schema["matches_expected"] and schema["schema_changed"] is False,
        "worst_case_ok": bool(worst.get("within_12000")),
        "fakeai_local": e2e.get("local_v2_ready") is True,
        "direct_e2e": (e2e.get("direct") or {}).get("pass") is True,
        "hierarchical_e2e": (e2e.get("hierarchical") or {}).get("pass") is True,
        "preflight_under_max": preflight.get("all_under_35000") is True,
        "cache_miss": identity.get("cache") == "MISS",
        "forensic_isolated": identity.get("forensic_collides") is False,
        "source_map_absent": source_map_absent,
        "state_not_success": bool(not_success),
        "win001_not_authorized": SEMANTIC_WIN001_AUTHORIZED is False,
        "link_contract_unambiguous": bool(contract.get("l_meaning")),
    }
    ready = all(checks.values())
    readiness_label = (
        "READY_FOR_HUMAN_AUTHORIZATION" if ready else "BLOCKED"
    )
    result = "PASS" if ready else "PARTIAL"
    if (
        REAL_PROVIDER_CALLS_THIS_PHASE
        or not source_map_absent
        or not not_success
        or SEMANTIC_WIN001_AUTHORIZED
    ):
        result = "FAIL"
        readiness_label = "BLOCKED"

    readiness = _stamp(
        {
            "readiness": readiness_label,
            "authorized": False,
            "checks": checks,
            "semantic_quality_thinking_disabled": "UNVERIFIED_REAL",
            "future_canary_purpose": [
                "technical completion without thinking/output truncation",
                "semantic extraction quality",
            ],
            "not_editorial_quality": True,
            "grammar_canary_needed": False,
            "thinking_contract": THINKING_CONTRACT,
            "prompt": CANDIDATE_WINDOW_ANALYSIS_PROMPT_VERSION,
            "transport": SEMANTIC_TRANSPORT_VERSION_V2,
            "planner_candidate": "window-planner-v2.1-small",
            "production_default": PRODUCTION_PLANNER_VERSION,
        }
    )

    header = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "a13_grammar": "VERIFIED ACCEPTED",
        "a13_thinking_disabled": "VERIFIED ACCEPTED",
        "a13_thinking_tokens": A13_THINKING_TOKENS,
        "a13_structured_parse": "PASS",
        "a13_link_validation": "FAIL",
        "root_cause": " + ".join(ROOT_CAUSE),
        "index_base": INDEX_BASE,
        "self_links": SELF_LINKS,
        "prompt_version": CANDIDATE_WINDOW_ANALYSIS_PROMPT_VERSION,
        "transport": SEMANTIC_TRANSPORT_VERSION_V2,
        "schema_changed": "NO",
        "raw_adapted_schema": (
            f"{schema.get('raw_bytes')} / {schema.get('adapted_bytes')}"
        ),
        "synthetic_worst_case": worst.get("local_tokens"),
        "thinking_contract": "disabled",
        "real_clean_windows": preflight.get("window_count"),
        "max_future_window_input": preflight.get("max_future_window_input"),
        "future_win001_signature": identity.get("analysis_signature"),
        "future_win001_cache": identity.get("cache"),
        "fakeai_local_v2": "PASS" if e2e.get("local_v2_ready") else "FAIL",
        "direct_e2e": "PASS" if (e2e.get("direct") or {}).get("pass") else "FAIL",
        "hierarchical_e2e": (
            "PASS" if (e2e.get("hierarchical") or {}).get("pass") else "FAIL"
        ),
        "canonical_validation": (
            "PASS" if (e2e.get("direct") or {}).get("canonical") else "FAIL"
        ),
        "semantic_quality": "UNVERIFIED_REAL",
        "readiness": readiness_label,
        "authorized": "NO",
        "production_default": PRODUCTION_PLANNER_VERSION,
        "source_map": "NOT PUBLISHED",
        "phase_3b": PHASE_3B_STATUS,
        "tests": tests,
        "next_action": NEXT_ACTION,
        "result_notes": (
            "Offline link-contract hardening. A.13 grammar/thinking facts kept. "
            "Semantic quality remains UNVERIFIED_REAL."
        ),
        "checks": checks,
        "worst_target": TARGET_JSON_LOCAL_TOKENS,
        "prompt_overhead": overhead,
        "schema": build_semantic_transport_v2_schema() and True,
    }

    report_bundle = {
        "header": header,
        "replay": replay,
        "contract": contract,
        "prompt": prompt,
        "readiness": readiness,
        "identity": identity,
        "e2e": e2e,
        "preflight": preflight,
        "schema": schema,
        "worst": worst,
    }
    report = render_report(report_bundle)
    return {
        "header": header,
        "replay": replay,
        "contract": contract,
        "prompt": prompt,
        "readiness": readiness,
        "identity": identity,
        "e2e": e2e,
        "preflight": preflight,
        "schema": schema,
        "worst": worst,
        "integrity": integrity,
        "isolation": isolation,
        "report": report,
    }


__all__ = ["build_bundle"]
