"""Politique EXAMPLE.l[] vs SourceMap canonique. Ne répare pas A.19."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v3.handles import handle_kind
from app.source_analysis_v3_a19_forensics.constants import (
    EXAMPLE_POLICY,
    EXAMPLE_POLICY_LABEL,
    MODE,
    PHASE,
    SCHEMA_VERSION,
)


def _idea_handles(records: list[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for item in records:
        if str(item.get("k") or "") != "IDEA":
            continue
        handle = item.get("h")
        if isinstance(handle, str) and handle:
            out[handle] = item
    return out


def audit_examples(
    payload: Mapping[str, Any] | None,
    *,
    window: WindowInput,
    transcript: TranscriptInput,
) -> dict[str, Any]:
    records: list[Mapping[str, Any]] = []
    if isinstance(payload, Mapping) and isinstance(payload.get("records"), list):
        records = [item for item in payload["records"] if isinstance(item, Mapping)]
    ideas = _idea_handles(records)
    src_index = {
        segment.src_id: segment.text
        for segment in transcript.segments
        if segment.src_id in set(window.owned_src_refs)
    }
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(records):
        if str(item.get("k") or "") != "EXAMPLE":
            continue
        refs = [str(ref) for ref in (item.get("s") or []) if isinstance(ref, str)]
        links = [raw for raw in (item.get("l") or []) if isinstance(raw, str)]
        cited = " ".join(src_index.get(ref, "") for ref in refs if ref in src_index)
        plausible = []
        value = str(item.get("v") or "")
        low = value.lower()
        for handle, idea in ideas.items():
            idea_v = str(idea.get("v") or "").lower()
            tokens = [tok for tok in idea_v.split() if len(tok) >= 5]
            if tokens and sum(1 for tok in tokens if tok in low) >= 2:
                plausible.append({"handle": handle, "idea": idea_v[:160]})
        empty_valid_canonical = True
        empty_valid_a19_era = not ideas
        rows.append(
            {
                "record_index": index,
                "value": value,
                "source_refs": refs,
                "l": links,
                "local_ideas_exist": bool(ideas),
                "empty_is_a19_era_contract_valid": (not links and empty_valid_a19_era)
                or bool(links),
                "empty_is_settled_canonical_valid": True if not links else True,
                "target_kinds": [handle_kind(raw) for raw in links],
                "semantically_plausible_idea_targets": plausible,
                "cited_excerpt": cited[:240],
            }
        )
    record_87 = next((row for row in rows if row["record_index"] == 87), None)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "canonical_supports_idea_refs": {
            "required": False,
            "optional": True,
            "allowed_empty": True,
            "source_refs_required": True,
            "source": "app.source_analysis.models.Example + validator._validate_examples",
        },
        "traceability_vs_association": (
            "An EXAMPLE remains source-grounded through s[] even with empty "
            "supports_idea_refs. Canonical design permits that."
        ),
        "policies_compared": {
            "A": "EXAMPLE must link >=1 IDEA whenever window has any IDEA — TOO BROAD vs canonical.",
            "B": EXAMPLE_POLICY_LABEL,
            "C": (
                "Every valid EXAMPLE must correspond to an extracted IDEA — "
                "completeness aspiration, not a fail-fast transport rule."
            ),
            "D": None,
        },
        "settled_policy": EXAMPLE_POLICY,
        "settled_policy_label": EXAMPLE_POLICY_LABEL,
        "a19_era_v3_rule": "allowed_only_if_no_local_idea",
        "a19_era_rule_correct": False,
        "reason": (
            "Canonical SourceMap allows empty supports_idea_refs. "
            "V3 must not invent a stronger validity rule than canonical semantics."
        ),
        "examples": rows,
        "record_87": record_87,
        "record_87_violates_settled_contract": False,
        "record_87_would_fail_a19_era_resolver": bool(
            record_87 and not record_87.get("l") and ideas
        ),
        "do_not_repair": True,
    }


__all__ = ["audit_examples"]
