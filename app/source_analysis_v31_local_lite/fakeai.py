"""FakeAI local-lite : WIN001, WIN004, 7 fenêtres, consolidation, reconstruction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.errors import WindowTransportValidationError
from app.source_analysis.window_fixtures import make_transcript, window_for
from app.source_analysis_local_v3.decoder import (
    decode_transport,
    decode_v3_transport,
    decode_v31_local_lite_transport,
)
from app.source_analysis_local_v3.e2e import run_direct_e2e_v31, run_hierarchical_e2e_v31
from app.source_analysis_local_v3.fixtures import (
    seven_window_plan,
    v3_success_transport,
    v31_a22_pattern_transports,
    v31_example_empty_link_transport,
    v31_i44_proposition_illustration,
    v31_success_transport,
    v31_two_distinct_ideas_same_importance,
)
from app.source_analysis_local_v3.pipeline import analyze_window_v31
from app.source_analysis_v31_local_lite.constants import (
    MODE,
    PHASE,
    SCHEMA_VERSION,
    SEMANTIC_TRANSPORT_VERSION_V3,
    TRANSPORT_VERSION,
)


def _engine(payload: dict) -> FakeAIEngine:
    return FakeAIEngine(
        script=[FakeReply(text="{}", parsed=payload, finish_reason="stop")],
        retry_policy=no_delay_policy(),
    )


def _window(owned: str = "SRC000001", window_id: str = "WIN001"):
    transcript = make_transcript(
        ["Faith window teaches how a trial is crossed."],
        src_ids=(owned,),
        transcript_id="TR-V31",
        content_sha256="d" * 64,
    )
    return transcript, window_for(transcript, owned=(owned,), window_id=window_id)


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def run_fakeai_validation(tmp_root: Path) -> dict[str, Any]:
    transcript, win001 = _window("SRC000001", "WIN001")
    _, win004 = _window("SRC000001", "WIN004")
    out001 = analyze_window_v31(win001, transcript, _engine(v31_success_transport()))
    out004 = analyze_window_v31(win004, transcript, _engine(v31_success_transport()))
    plan_transcript, plan = seven_window_plan()
    seven_ok = True
    seven_errors: list[str] = []
    for window in plan.windows:
        outcome = analyze_window_v31(
            window,
            plan_transcript,
            _engine(v31_success_transport(owned_src=window.owned_src_refs[0])),
        )
        if not outcome.ready:
            seven_ok = False
            seven_errors.append(f"{window.window_id}:{outcome.errors}")

    i44 = v31_i44_proposition_illustration()
    i44_decoded = decode_v31_local_lite_transport(
        i44, allowed_source_refs={"SRC000001"}
    )
    i44_ideas = [row for row in i44_decoded["records"] if row["k"] == "IDEA"]
    i44_examples = [row for row in i44_decoded["records"] if row["k"] == "EXAMPLE"]
    i44_ok = (
        len(i44_ideas) == 1
        and i44_ideas[0]["m"] == ["central"]
        and "claim" not in i44_ideas[0]["m"]
        and len(i44_examples) == 1
        and (
            "illustrat" in i44_examples[0]["v"].lower()
            or "leader" in i44_examples[0]["v"].lower()
        )
    )
    patterns_ok = True
    for payload in v31_a22_pattern_transports():
        decoded = decode_v31_local_lite_transport(
            payload, allowed_source_refs={"SRC000001"}
        )
        ideas = [row for row in decoded["records"] if row["k"] == "IDEA"]
        examples = [row for row in decoded["records"] if row["k"] == "EXAMPLE"]
        if not ideas or ideas[0]["m"] != ["central"] or not examples:
            patterns_ok = False

    old_v3_rejected = False
    try:
        decode_v31_local_lite_transport(
            v3_success_transport(), allowed_source_refs={"SRC000001"}
        )
    except WindowTransportValidationError:
        old_v3_rejected = True

    example_leak_rejected = False
    leak = v31_success_transport()
    leak["records"][1]["m"] = ["example", "supporting"]
    try:
        decode_v31_local_lite_transport(leak, allowed_source_refs={"SRC000001"})
    except WindowTransportValidationError:
        example_leak_rejected = True

    claim_primary_rejected = False
    claim = v31_success_transport()
    claim["records"][1]["m"] = ["claim", "primary"]
    try:
        decode_v31_local_lite_transport(claim, allowed_source_refs={"SRC000001"})
    except WindowTransportValidationError:
        claim_primary_rejected = True

    valid_ok = True
    decode_v31_local_lite_transport(
        v31_success_transport(), allowed_source_refs={"SRC000001"}
    )
    empty_rejected = False
    empty = v31_success_transport()
    empty["records"][1]["m"] = []
    try:
        decode_v31_local_lite_transport(empty, allowed_source_refs={"SRC000001"})
    except WindowTransportValidationError:
        empty_rejected = True
    unknown_rejected = False
    unknown = v31_success_transport()
    unknown["records"][1]["m"] = ["primary"]
    try:
        decode_v31_local_lite_transport(unknown, allowed_source_refs={"SRC000001"})
    except WindowTransportValidationError:
        unknown_rejected = True

    src_typo_rejected = False
    typo = v31_success_transport()
    typo["records"][0]["s"] = ["SRc000609"]
    try:
        decode_v31_local_lite_transport(typo, allowed_source_refs={"SRC000001"})
    except WindowTransportValidationError:
        src_typo_rejected = True

    historical_v3 = True
    decode_v3_transport(v3_success_transport(), allowed_source_refs={"SRC000001"})
    decode_transport(
        v3_success_transport(),
        transport_version=SEMANTIC_TRANSPORT_VERSION_V3,
        allowed_source_refs={"SRC000001"},
    )
    version_aware = False
    try:
        decode_transport(
            v31_success_transport(),
            transport_version="semantic-transport-heuristic",
            allowed_source_refs={"SRC000001"},
        )
    except WindowTransportValidationError:
        version_aware = True

    empty_link = decode_v31_local_lite_transport(
        v31_example_empty_link_transport(), allowed_source_refs={"SRC000001"}
    )
    empty_link_ok = any(
        row["k"] == "EXAMPLE" and row["l"] == [] for row in empty_link["records"]
    )

    distinct = v31_two_distinct_ideas_same_importance()
    distinct_decoded = decode_v31_local_lite_transport(
        distinct, allowed_source_refs={"SRC000001"}
    )
    distinct_ok = (
        sum(1 for row in distinct_decoded["records"] if row["k"] == "IDEA") == 2
    )

    direct = run_direct_e2e_v31(tmp_root / "direct")
    hierarchical = run_hierarchical_e2e_v31(tmp_root / "hierarchical")
    source_map = direct.source_map
    no_kind_leak = all(not idea.kind for idea in source_map.ideas)
    no_importance_as_kind = all(
        idea.kind != idea.importance for idea in source_map.ideas
    )
    src_ok = all(idea.source_refs for idea in source_map.ideas)
    topic_ok = all(idea.topic_refs for idea in source_map.ideas)
    relation_ok = any(idea.relations for idea in source_map.ideas)
    example_ok = bool(source_map.examples) and all(
        example.source_refs for example in source_map.examples
    )
    no_drop = direct.no_drop and hierarchical.no_drop

    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "fakeai_win001": _status(out001.ready),
        "fakeai_win004": _status(out004.ready),
        "fakeai_all_7": _status(seven_ok),
        "seven_errors": seven_errors,
        "direct_consolidation": _status(direct.source_map is not None),
        "hierarchical_consolidation": _status(hierarchical.source_map is not None),
        "canonical_reconstruction": _status(bool(source_map.ideas)),
        "no_drop": _status(no_drop),
        "src_traceability": _status(src_ok),
        "topic_association": _status(topic_ok),
        "relation_preservation": _status(relation_ok),
        "example_preservation": _status(example_ok),
        "i44_separation": _status(bool(i44_ok)),
        "a22_patterns": _status(patterns_ok),
        "old_v3_rejected_under_local_lite": _status(old_v3_rejected),
        "example_leakage_rejected": _status(example_leak_rejected),
        "claim_primary_rejected": _status(claim_primary_rejected),
        "valid_local_lite_idea": _status(valid_ok),
        "empty_metadata_rejected": _status(empty_rejected),
        "unknown_importance_rejected": _status(unknown_rejected),
        "src_typo_rejected": _status(src_typo_rejected),
        "example_empty_link_valid": _status(empty_link_ok),
        "historical_v3": _status(historical_v3),
        "version_aware_decoder": _status(version_aware),
        "no_silent_merge": _status(distinct_ok),
        "importance_not_kind": _status(no_kind_leak and no_importance_as_kind),
        "canonical_idea_kinds": [idea.kind for idea in source_map.ideas],
        "canonical_idea_importances": [idea.importance for idea in source_map.ideas],
        "transport": TRANSPORT_VERSION,
    }


__all__ = ["run_fakeai_validation"]
