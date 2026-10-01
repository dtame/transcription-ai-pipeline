"""Rapport markdown 3B.7.7A.36. Offline."""

from __future__ import annotations

from typing import Any, Mapping


def _dash(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, list):
        if not value:
            return "(none)"
        return "; ".join(str(item) for item in value)
    return str(value)


def _violation_ids(rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return "(none)"
    ids = []
    for row in rows:
        if isinstance(row, dict):
            ids.append(str(row.get("id") or row.get("error") or row))
        else:
            ids.append(str(row))
    return "; ".join(ids)


def render_report(bundle: Mapping[str, Any], *, tests: str) -> str:
    header = bundle.get("header") or {}
    schema = bundle.get("schema") or {}
    delta = schema.get("delta_vs_1_0") or {}
    fakeai = bundle.get("fakeai") or {}
    lines = [
        "# PHASE 3B.7.7A.36 — GLOBAL CONSOLIDATION CANARY FORENSICS",
        "",
        "## Result",
        "",
        str(header.get("result")),
        "",
        "REAL PROVIDER CALLS =",
        "0",
        "",
        "REAL CONSOLIDATION CALLS =",
        "0",
        "",
        "A.35 STATUS =",
        "FAIL unchanged",
        "",
        "A.35 REQUEST =",
        str(header.get("a35_request")),
        "",
        "A.35 GRAMMAR ACCEPTED =",
        str(header.get("a35_grammar_accepted")),
        "",
        "A.35 TRANSPORT PARSE =",
        str(header.get("a35_transport_parse")),
        "",
        "A.35 ROOT VALIDATOR VIOLATIONS =",
        _violation_ids(header.get("a35_root_validator_violations")),
        "",
        "A.35 CASCADE VIOLATIONS =",
        _violation_ids(header.get("a35_cascade_violations")),
        "",
        "DROP ROOT CAUSE =",
        str(header.get("drop_root_cause")),
        "",
        "DROP FIELD CLASS =",
        str(header.get("drop_field_class")),
        "",
        "A.35 DROP PROSE =",
        str(header.get("a35_drop_prose")),
        "",
        "CANONICAL DROP TOKEN =",
        "non_substantive_fragment",
        "",
        "DROP-ONLY COUNTERFACTUAL =",
        str(header.get("drop_only_counterfactual")),
        "",
        "KEEP VS LINK_RELATED FINDING =",
        str(header.get("keep_vs_link_related")),
        "",
        "LINK_RELATED CONTRACT =",
        str(header.get("link_related_contract")),
        "",
        "REPETITION FINDING =",
        str(header.get("repetition_finding")),
        "",
        "FIXTURE OVERCONSTRAINED =",
        str(header.get("fixture_overconstrained")),
        "",
        "SELECTED DISPOSITION MODEL =",
        str(header.get("selected_disposition_model")),
        "",
        "OLD TRANSPORT =",
        "global-consolidation-transport-1.0",
        "",
        "NEXT TRANSPORT =",
        str(header.get("next_transport")),
        "",
        "OLD SCHEMA RAW / ADAPTED =",
        "1040 / 1195",
        "",
        "NEXT SCHEMA RAW / ADAPTED =",
        str(header.get("next_schema_raw_adapted")),
        "",
        "NEXT SCHEMA HASH =",
        str(header.get("next_schema_hash")),
        "",
        "SCHEMA CHANGED =",
        str(header.get("schema_changed")),
        "",
        "NEW GRAMMAR CANARY REQUIRED =",
        str(header.get("new_grammar_canary_required")),
        "",
        "OLD PROMPT =",
        "global-consolidation-1.0",
        "",
        "NEXT PROMPT =",
        str(header.get("next_prompt")),
        "",
        "MODEL =",
        "claude-sonnet-5",
        "",
        "THINKING =",
        "disabled",
        "",
        "PRODUCTION MAX OUTPUT =",
        "32000",
        "",
        "ONE GLOBAL CALL ARCHITECTURE =",
        "PRESERVED",
        "",
        "IDEA DISPOSITION COVERAGE REQUIRED =",
        "100%",
        "",
        "SILENT DROPS ALLOWED =",
        "0",
        "",
        "RELATION POLICY =",
        "C — NON-AUTHORITATIVE HINTS",
        "",
        "RELATION_QUALITY_TECHNICAL_DEBT =",
        "YES",
        "",
        "LOCAL EXTRACTION FUNCTIONALLY FROZEN =",
        "YES",
        "",
        "TESTS =",
        tests,
        "",
        "NEW FAILURES =",
        _dash(header.get("new_failures")),
        "",
        "SOURCE MAP =",
        "NOT PUBLISHED",
        "",
        "PHASE 3B =",
        "INCOMPLETE",
        "",
        "READINESS =",
        str(header.get("readiness")),
        "",
        "NEXT ACTION =",
        "HUMAN REVIEW",
        "",
        "## A.35 identity",
        "",
        f"request_id = {header.get('a35_request')}",
        f"identity_ok = {header.get('identity_ok')}",
        f"authorized/actual/successful/retries = "
        f"{(header.get('a35_facts') or {}).get('authorized_calls')}/"
        f"{(header.get('a35_facts') or {}).get('actual_calls')}/"
        f"{(header.get('a35_facts') or {}).get('successful_calls')}/"
        f"{(header.get('a35_facts') or {}).get('retries')}",
        f"HTTP = {(header.get('a35_facts') or {}).get('http')}",
        f"finish = {(header.get('a35_facts') or {}).get('finish')}",
        f"thinking tokens = {(header.get('a35_facts') or {}).get('thinking_tokens')}",
        f"cost = {(header.get('a35_facts') or {}).get('cost_usd')} USD",
        f"elapsed = {(header.get('a35_facts') or {}).get('elapsed_seconds')} s",
        "A.35 remains FAIL. Offline changes do not reinterpret it as PASS.",
        "",
        "## Schema delta vs 1.0",
        "",
        f"raw delta = {delta.get('raw_bytes')} bytes ({delta.get('raw_percent')}%)",
        f"adapted delta = {delta.get('adapted_bytes')} bytes ({delta.get('adapted_percent')}%)",
        "v1.0 schema and prompt were not mutated.",
        "New grammar canary is required before the next provider call.",
        "",
        "## FakeAI",
        "",
        f"catalog_ok = {fakeai.get('ok')}",
        "",
        "WAIT FOR HUMAN REVIEW. Do not call Anthropic. Do not call OpenAI.",
        "Do not rerun A.35. Do not run another grammar canary.",
        "Do not execute real consolidation. Do not publish source_map.",
        "Do not reopen local extraction. Do not change model or thinking policy.",
        "Do not start Phase 4. Phase 3B remains INCOMPLETE.",
        "",
    ]
    return "\n".join(lines) + "\n"


__all__ = ["render_report"]
