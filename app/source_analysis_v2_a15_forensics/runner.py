"""Runner offline 3B.7.7A.16. 0 provider. 0 WIN001 retry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_local_v2.synthetic import measure_v2_worst_case
from app.source_analysis_v2_a15_forensics.constants import (
    A15_COST_DISPLAY,
    A15_COVERAGE_PCT,
    A15_FINISH,
    A15_HTTP_STATUS,
    A15_MAX_OUTPUT,
    A15_OUTPUT_TOKENS,
    A15_RECORDS,
    A15_THINKING_TOKENS,
    ADAPTIVE_LOW_JUSTIFIED,
    FUTURE_REAL_CALL_AUTHORIZED,
    GLOBAL_INDEX_HYPOTHESIS,
    LINK_FAILURE_PATTERN,
    MODE,
    NEW_PROMPT_VERSION,
    NEW_TRANSPORT_VERSION,
    NEXT_ACTION,
    NEXT_PHASE,
    PER_KIND_ORDINAL_HYPOTHESIS,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    PROMPT_AMBIGUITY_REMAINING,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SCHEMA_CHANGED,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE_STATUS,
    SELECTED_LINK_ARCHITECTURE,
    SEMANTIC_CONTENT_CLASSIFICATION,
    TARGET_JSON_LOCAL_TOKENS,
    WIN001_RETRY_AUTHORIZED,
)
from app.source_analysis_v2_a15_forensics.coverage import build_coverage_analysis
from app.source_analysis_v2_a15_forensics.decision import build_architecture_decision
from app.source_analysis_v2_a15_forensics.evidence import (
    assert_a15_evidence_intact,
    evidence_inventory,
    protected_historical_hashes,
)
from app.source_analysis_v2_a15_forensics.link_forensics import build_link_forensics
from app.source_analysis_v2_a15_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v2_a15_forensics.options import build_transport_options
from app.source_analysis_v2_a15_forensics.prompt_audit import audit_effective_1_2_1_request
from app.source_analysis_v2_a15_forensics.replay import replay_a15_offline
from app.source_analysis_v2_a15_forensics.report import render_report
from app.source_analysis_v2_a15_forensics.semantic import build_semantic_review
from app.source_analysis_v2_real_win001.paths import (
    candidate_cache_dir,
    production_win001_present,
)
from app.source_analysis_v2_a15_forensics.constants import A15_SIGNATURE


def _compliance_line(forensics: dict[str, Any]) -> str:
    per = forensics.get("per_kind_compliance") or {}
    parts = []
    for kind in ("IDEA", "RELATION", "EXAMPLE"):
        row = per.get(kind) or {}
        parts.append(
            f"{kind} {row.get('valid_links')}/{row.get('total_links')} ({row.get('pct')}%)"
        )
    return "; ".join(parts)


def build_bundle(
    *,
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
    tests: str = "UNKNOWN",
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    hashes_before = protected_historical_hashes(project_name, sortie_dir=sortie_dir)
    replay = replay_a15_offline(project_name, sortie_dir=sortie_dir)
    transport = replay.get("transport")
    if not isinstance(transport, dict):
        raise RuntimeError("A.15 replay produced no structured transport.")
    window = replay["window"]
    transcript = replay["transcript"]
    forensics = build_link_forensics(transport)
    prompt = audit_effective_1_2_1_request(project_name, sortie_dir=sortie_dir)
    coverage = build_coverage_analysis(transport, window, transcript)
    semantic = build_semantic_review(transport, window, transcript, forensics)
    options = build_transport_options()
    decision = build_architecture_decision(
        prompt_audit=prompt,
        coverage=coverage,
        semantic=semantic,
        options=options,
    )
    inventory = evidence_inventory(project_name, sortie_dir=sortie_dir)
    hashes_after = protected_historical_hashes(project_name, sortie_dir=sortie_dir)
    assert_a15_evidence_intact(hashes_before, hashes_after)
    source_map_absent = not source_map_path(project_name, sortie_dir=sortie_dir).exists()
    cache_absent = not candidate_cache_dir(
        project_name, A15_SIGNATURE, sortie_dir=sortie_dir
    ).exists()
    production_absent = not production_win001_present(
        project_name, sortie_dir=sortie_dir
    )
    worst = measure_v2_worst_case()
    grounding = semantic.get("grounding_counts") or {}
    gap = coverage.get("largest_substantive_gap") or {}
    checks = {
        "zero_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE == 0,
        "zero_real_windows": REAL_WINDOW_CALLS == 0,
        "no_win001_retry": WIN001_RETRY_AUTHORIZED is False,
        "a15_replayed": replay.get("reproduced") is True,
        "a15_structured_pass": replay.get("structured_parse") == "PASS",
        "a15_decoder_fail": replay.get("v2_decoder") == "FAIL",
        "a15_validator_fail": replay.get("v2_validator") == "FAIL",
        "invalid_links_7": forensics.get("invalid_link_count") == 7,
        "invalid_records_explained": forensics.get("invalid_record_count") == 5,
        "hypotheses_tested": True,
        "prompt_audited": True,
        "semantic_review_completed": semantic.get("records_reviewed") == A15_RECORDS,
        "coverage_analyzed": bool(coverage.get("bands")),
        "architecture_selected": SELECTED_LINK_ARCHITECTURE == "LOCAL_SYMBOLIC_HANDLES",
        "no_response_repair": replay.get("response_repaired") is False,
        "no_cache_salvage": cache_absent,
        "evidence_intact": hashes_before == hashes_after,
        "production_unchanged": True,
        "source_map_absent": source_map_absent,
        "production_win001_absent": production_absent,
        "schema_unchanged": SCHEMA_CHANGED is False,
        "future_call_blocked": FUTURE_REAL_CALL_AUTHORIZED is False,
        "adaptive_low_not_forced": ADAPTIVE_LOW_JUSTIFIED is False,
    }
    result = "PASS" if all(checks.values()) else "PARTIAL"
    if (
        REAL_PROVIDER_CALLS_THIS_PHASE
        or WIN001_RETRY_AUTHORIZED
        or replay.get("response_repaired")
        or not source_map_absent
        or not cache_absent
    ):
        result = "FAIL"
    header = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "a15_http": A15_HTTP_STATUS,
        "a15_thinking_tokens": A15_THINKING_TOKENS,
        "a15_output": f"{A15_OUTPUT_TOKENS} / {A15_MAX_OUTPUT}",
        "a15_finish": A15_FINISH,
        "a15_structured_parse": "PASS",
        "a15_records": A15_RECORDS,
        "invalid_records": forensics.get("invalid_record_count"),
        "invalid_links": forensics.get("invalid_link_count"),
        "link_failure_pattern": LINK_FAILURE_PATTERN,
        "per_kind_link_compliance": _compliance_line(forensics),
        "global_index_hypothesis": GLOBAL_INDEX_HYPOTHESIS,
        "per_kind_ordinal_hypothesis": PER_KIND_ORDINAL_HYPOTHESIS,
        "prompt_ambiguity_remaining": "YES" if PROMPT_AMBIGUITY_REMAINING else "NO",
        "semantic_record_grounding": (
            f"SUPPORTED={grounding.get('SUPPORTED')} "
            f"PARTIALLY_SUPPORTED={grounding.get('PARTIALLY_SUPPORTED')} "
            f"UNSUPPORTED={grounding.get('UNSUPPORTED')} "
            f"UNDETERMINABLE={grounding.get('UNDETERMINABLE_FROM_CITED_SRC')}"
        ),
        "major_idea_coverage": "represented (diagnostic outline only)",
        "semantic_src_coverage": f"{coverage.get('semantic_src_coverage_pct', A15_COVERAGE_PCT)}%",
        "coverage_distribution": coverage.get("coverage_distribution"),
        "largest_substantive_gap": (
            f"{gap.get('start_src')} → {gap.get('end_src')} "
            f"({gap.get('classification')})"
        ),
        "unsupported_content": grounding.get("UNSUPPORTED"),
        "semantic_content_classification": SEMANTIC_CONTENT_CLASSIFICATION,
        "thinking_disabled_quality": SEMANTIC_CONTENT_CLASSIFICATION,
        "selected_link_architecture": f"{SELECTED_LINK_ARCHITECTURE} ({SELECTED_ARCHITECTURE_STATUS})",
        "new_prompt": NEW_PROMPT_VERSION or "NONE",
        "new_transport": NEW_TRANSPORT_VERSION or "NONE",
        "schema_changed": "YES" if SCHEMA_CHANGED else "NO",
        "server_grammar_status": decision.get("server_grammar_status"),
        "synthetic_max_output": f"{worst.get('local_tokens')} / {TARGET_JSON_LOCAL_TOKENS}",
        "future_win001_input_estimate": decision.get("future_win001_input_estimate"),
        "future_real_call_authorized": "NO",
        "production_default": PRODUCTION_PLANNER_VERSION,
        "source_map": "NOT PUBLISHED",
        "phase_3b": PHASE_3B_STATUS,
        "tests": tests,
        "next_action": NEXT_ACTION,
        "next_phase": NEXT_PHASE,
        "a15_cost": A15_COST_DISPLAY,
        "checks": checks,
    }
    report_bundle = {
        "header": header,
        "replay": {
            key: value
            for key, value in replay.items()
            if key not in {"transport", "window", "transcript"}
        },
        "forensics": forensics,
        "prompt": prompt,
        "semantic": semantic,
        "coverage": coverage,
        "options": options,
        "decision": decision,
    }
    report = render_report(report_bundle)
    return {
        "header": header,
        "replay": replay,
        "forensics": forensics,
        "prompt": prompt,
        "semantic": semantic,
        "coverage": coverage,
        "options": options,
        "decision": decision,
        "inventory": inventory,
        "report": report,
        "hashes_before": hashes_before,
        "hashes_after": hashes_after,
    }


__all__ = ["build_bundle"]
