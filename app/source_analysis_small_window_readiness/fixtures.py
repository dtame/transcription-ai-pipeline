"""FakeAI isolé — même runner canary, jamais le cache pastoral."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any

from app.ai.errors import AIResponseError, AIStructuredOutputError
from app.ai.provider_forensics import (
    CLASS_INVALID_RESPONSE_JSON,
    ENVELOPE_JSON_NAME,
    ProviderHttpEnvelope,
    RAW_BODY_NAME,
    forensics_dir as provider_forensics_dir,
)
from app.ai.providers.fake import FakeReply
from app.ai.structured_forensics import FORENSICS_JSON_NAME, FORENSICS_RAW_NAME, forensics_dir
from app.source_analysis.window_analyzer import resolve_window_execution
from app.source_analysis.window_fixtures import WindowMappedFakeAI
from app.source_analysis.window_granularity import OVERFLOW_TOKEN
from app.source_analysis.window_granularity_fixtures import (
    bounded_success_transport,
    idea_hard_limit_transport,
    overflow_signal_transport,
)
from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION
from app.source_analysis.window_writer import result_path, transport_path
from app.source_analysis.writer import source_map_path
from app.source_analysis_hybrid_readiness.canary import run_win001_canary
from app.source_analysis_hybrid_readiness.constants import (
    AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY,
)
from app.source_analysis_small_window_hierarchy.constants import CANDIDATE_PLANNER_VERSION
from app.source_analysis_small_window_hierarchy.fixtures import n_window_plan


def _engine(replies: dict[str, FakeReply | BaseException]) -> WindowMappedFakeAI:
    return WindowMappedFakeAI(replies)


def _provider_boundary_error() -> AIResponseError:
    raw = b"{this is not json"
    envelope = ProviderHttpEnvelope(
        provider="anthropic",
        model="claude-sonnet-5",
        post_attempted=True,
        response_received=True,
        http_status=200,
        headers_subset={"request-id": "req_small_invalid_json"},
        request_id="req_small_invalid_json",
        raw_body=raw,
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        raw_size=len(raw),
        json_decode_ok=False,
        classification=CLASS_INVALID_RESPONSE_JSON,
        usage={"input_tokens": 80, "output_tokens": 9},
        input_tokens=80,
        output_tokens=9,
        finish_reason="stop",
        elapsed_ms=12,
    )
    error = AIResponseError("invalid response json")
    error.classification = CLASS_INVALID_RESPONSE_JSON
    error.http_envelope = envelope
    error.post_attempted = True
    error.response_received = True
    error.http_status = 200
    error.request_id = "req_small_invalid_json"
    error.input_tokens = 80
    error.output_tokens = 9
    return error


def run_isolated_canary(
    tmp: Path,
    engine,
    transcript,
    plan,
):
    return run_win001_canary(
        "fixture",
        window_id="WIN001",
        dry_run=False,
        execute_real=True,
        authorization_scope=AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY,
        planner_version=CANDIDATE_PLANNER_VERSION,
        prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
        engine=engine,
        windows_root_override=tmp / "windows",
        sortie_dir=tmp,
        transcript=transcript,
        plan=plan,
    )


def run_fakeai_matrix() -> dict[str, Any]:
    transcript, plan = n_window_plan(2)
    assert plan.planner_version == CANDIDATE_PLANNER_VERSION
    window = plan.windows[0]
    owned = window.owned_src_refs
    root = Path()
    results: dict[str, Any] = {}

    import tempfile

    with tempfile.TemporaryDirectory(prefix="sw_ready_ok_") as tmp_name:
        tmp = Path(tmp_name)
        engine = _engine(
            {
                "WIN001": FakeReply(parsed=bounded_success_transport(owned=owned)),
                "WIN002": FakeReply(parsed={"records": []}),
            }
        )
        result = run_isolated_canary(tmp, engine, transcript, plan)
        root = tmp / "windows"
        warm_engine = _engine(
            {
                "WIN001": FakeReply(parsed=bounded_success_transport(owned=owned)),
                "WIN002": FakeReply(parsed={"records": []}),
            }
        )
        warm = run_isolated_canary(tmp, warm_engine, transcript, plan)
        results["success"] = {
            "accepted": result.accepted,
            "provider_calls": result.provider_calls,
            "engine_calls": engine.call_count,
            "ready_windows": result.execution.get("ready_windows"),
            "generated_windows": result.execution.get("generated_windows"),
            "continued": result.continued_to_next_window,
            "consolidation": result.consolidation_called,
            "source_map": result.source_map_published,
            "source_analysis_success": result.source_analysis_success,
            "transport_present": transport_path("fixture", "WIN001", root=root).is_file(),
            "result_present": result_path("fixture", "WIN001", root=root).is_file(),
            "pastoral_source_map_untouched": not source_map_path(
                "fixture", sortie_dir=tmp
            ).exists(),
            "warm_provider_calls": warm.provider_calls,
            "warm_engine_calls": warm_engine.call_count,
            "warm_used_cache": warm.execution.get("generated_windows") == 0,
            "isolated_tmp": True,
        }

    with tempfile.TemporaryDirectory(prefix="sw_ready_http_") as tmp_name:
        tmp = Path(tmp_name)
        error = _provider_boundary_error()
        engine = _engine({"WIN001": error})
        result = run_isolated_canary(tmp, engine, transcript, plan)
        bundle = resolve_window_execution(
            window,
            transcript,
            engine=engine,
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
        )
        forensic = provider_forensics_dir(tmp / "windows", "WIN001", bundle.signature)
        results["provider_boundary"] = {
            "provider_calls": result.provider_calls,
            "engine_calls": engine.call_count,
            "continued": result.continued_to_next_window,
            "forensics_json": (forensic / ENVELOPE_JSON_NAME).is_file(),
            "forensics_raw": (forensic / RAW_BODY_NAME).is_file(),
            "result_absent": not result_path(
                "fixture", "WIN001", root=tmp / "windows"
            ).exists(),
            "analysis_signature": bundle.signature,
        }

    with tempfile.TemporaryDirectory(prefix="sw_ready_struct_") as tmp_name:
        tmp = Path(tmp_name)
        engine = _engine(
            {
                "WIN001": FakeReply(
                    text='{"theme": "cut mid-stream"',
                    output_tokens=4000,
                    finish_reason="stop",
                    request_id="msg_small_parse",
                )
            }
        )
        result = run_isolated_canary(tmp, engine, transcript, plan)
        bundle = resolve_window_execution(
            window,
            transcript,
            engine=engine,
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
        )
        forensic = forensics_dir(tmp / "windows", "WIN001", bundle.signature)
        payload = {}
        if (forensic / FORENSICS_JSON_NAME).is_file():
            import json

            payload = json.loads(
                (forensic / FORENSICS_JSON_NAME).read_text(encoding="utf-8")
            )
        results["structured"] = {
            "provider_calls": result.provider_calls,
            "engine_calls": engine.call_count,
            "continued": result.continued_to_next_window,
            "forensics_present": (forensic / FORENSICS_JSON_NAME).is_file(),
            "raw_present": (forensic / FORENSICS_RAW_NAME).is_file(),
            "parse_kind": (payload.get("parse_error") or {}).get("parse_failure_kind"),
            "result_absent": not result_path(
                "fixture", "WIN001", root=tmp / "windows"
            ).exists(),
            "error_type": AIStructuredOutputError.__name__,
        }

    with tempfile.TemporaryDirectory(prefix="sw_ready_cap_") as tmp_name:
        tmp = Path(tmp_name)
        engine = _engine(
            {"WIN001": FakeReply(parsed=overflow_signal_transport(owned=owned))}
        )
        result = run_isolated_canary(tmp, engine, transcript, plan)
        raw = {}
        t_path = transport_path("fixture", "WIN001", root=tmp / "windows")
        if t_path.is_file():
            import json

            raw = json.loads(t_path.read_text(encoding="utf-8"))
        results["capacity"] = {
            "provider_calls": result.provider_calls,
            "engine_calls": engine.call_count,
            "failed_windows": result.execution.get("failed_windows"),
            "ready_windows": result.execution.get("ready_windows"),
            "transport_present": t_path.is_file(),
            "overflow_present": any(
                item.get("v") == OVERFLOW_TOKEN for item in raw.get("records", [])
            ),
            "result_absent": not result_path(
                "fixture", "WIN001", root=tmp / "windows"
            ).exists(),
            "continued": result.continued_to_next_window,
        }

    with tempfile.TemporaryDirectory(prefix="sw_ready_hard_") as tmp_name:
        tmp = Path(tmp_name)
        engine = _engine(
            {"WIN001": FakeReply(parsed=idea_hard_limit_transport(owned=owned))}
        )
        result = run_isolated_canary(tmp, engine, transcript, plan)
        results["hard_limit"] = {
            "provider_calls": result.provider_calls,
            "engine_calls": engine.call_count,
            "failed_windows": result.execution.get("failed_windows"),
            "transport_present": transport_path(
                "fixture", "WIN001", root=tmp / "windows"
            ).is_file(),
            "result_absent": not result_path(
                "fixture", "WIN001", root=tmp / "windows"
            ).exists(),
            "continued": result.continued_to_next_window,
        }

    mutated = replace(window, planner_version="window-planner-v2.0")
    sig_a = resolve_window_execution(
        window, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION
    ).signature
    sig_b = resolve_window_execution(
        mutated, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION
    ).signature
    results["signature_mutations"] = {
        "planner_change_changes_signature": sig_a != sig_b,
        "same_label": window.window_id == mutated.window_id == "WIN001",
    }
    return {
        "isolated_from_pastoral": True,
        "planner": CANDIDATE_PLANNER_VERSION,
        "window": "WIN001",
        **results,
    }


__all__ = ["run_fakeai_matrix", "run_isolated_canary"]
