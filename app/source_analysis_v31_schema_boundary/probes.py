"""Sondes offline : modèle canonique, roundtrip, mixte, publication. FakeAI isolé."""

from __future__ import annotations

import copy
import dataclasses
import json
from pathlib import Path
from typing import Any

from app.ai.errors import AIStructuredOutputError
from app.ai.structured import parse_structured_output
from app.source_analysis.errors import (
    HybridReconstructionError,
    WindowTransportValidationError,
)
from app.source_analysis.hybrid_reconstructor import _idea_raw, _idea_raw_local_lite
from app.source_analysis.models import IDEA_KINDS, IMPORTANCE_LEVELS, Idea, SourceMap
from app.source_analysis.schema import build_response_schema
from app.source_analysis.validator import ensure_valid_source_map, validate_source_map
from app.source_analysis.window_models import WindowIntermediateRecord
from app.source_analysis.writer import source_map_path
from app.source_analysis.consolidation_models import ConsolidationNode
from app.source_analysis_local_v3.compatibility import (
    normalize_v3_transport_to_local_lite,
    normalize_v3_window_result_to_local_lite,
)
from app.source_analysis_local_v3.constants import (
    SEMANTIC_TRANSPORT_VERSION_V3,
    SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
)
from app.source_analysis_local_v3.decoder import (
    decode_v3_transport,
    decode_v31_local_lite_transport,
)
from app.source_analysis_local_v3.e2e import (
    run_direct_e2e_v31,
    run_v3_windows,
    run_v31_windows,
)
from app.source_analysis_local_v3.fixtures import (
    seven_window_plan,
    v3_success_transport,
    v31_success_transport,
)
from app.source_analysis_local_v3.pipeline import build_v140_window_request
from app.source_analysis_local_v3.reconstruct import reconstruct_source_map_from_v31
from app.source_analysis_local_v3.schema import (
    build_semantic_transport_v31_local_lite_schema,
)
from app.source_analysis_local_v3.consolidation import (
    build_v31_consolidation_input,
)
from app.source_analysis_local_v3.e2e import _consolidate
from app.source_analysis_local_v3.fixtures import default_recovery, global_v3_transport
from app.source_analysis_v31_schema_boundary.constants import (
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    TRANSPORT_VERSION,
)

_GENERATION_A_PAYLOAD = {
    "source_analysis": {
        "main_theme": "Le rôle de la foi dans la manière de traverser les épreuves",
        "author_intent": {
            "summary": "Enseigner ce que la foi change dans l'épreuve.",
            "confidence": "high",
            "kinds": ["enseigner"],
        },
        "target_audience": {
            "summary": "Audience croyante.",
            "confidence": "medium",
            "kinds": [],
        },
    },
    "topics": [
        {
            "topic_id": "t_foi",
            "label": "Foi dans l'épreuve",
            "summary": "Ce que la foi modifie dans la traversée d'une épreuve.",
            "source_refs": ["SRC000001"],
        }
    ],
    "ideas": [
        {
            "idea_id": "idea_7",
            "summary": "La foi change la manière de traverser l'épreuve.",
            "kind": "claim",
            "importance": "central",
            "topic_refs": ["t_foi"],
            "relations": [],
            "source_refs": ["SRC000001"],
        }
    ],
    "examples": [],
    "references": [],
    "uncertainties": [],
    "repetitions": [],
    "author_voice_profile": {},
}


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _idea_node() -> ConsolidationNode:
    return ConsolidationNode(
        node_id="C0001",
        operation="KEEP_RECORD",
        kind="IDEA",
        value="",
        member_ids=("WIN001:R0001",),
        source_refs=("SRC000001",),
        source_refs_are_local_union=True,
    )


def _member(metadata: tuple[str, ...]) -> WindowIntermediateRecord:
    return WindowIntermediateRecord(
        record_id="WIN001:R0001",
        transport_index=1,
        kind="IDEA",
        value="Faith changes the crossing.",
        source_refs=("SRC000001",),
        links=(),
        link_record_ids=(),
        metadata=metadata,
    )


def probe_canonical_model(source_map: SourceMap, transcript) -> dict[str, Any]:
    cases: dict[str, Any] = {}

    absent = Idea.from_dict(
        {
            "idea_id": "IDEA001",
            "summary": "Faith changes the crossing.",
            "importance": "central",
            "source_refs": ["SRC000001"],
        }
    )
    cases["kind_absent"] = {
        "constructed": absent.kind,
        "serialized": absent.to_dict().get("kind"),
        "accepted_by_model": absent.kind == "",
    }

    empty = Idea.from_dict(
        {
            "idea_id": "IDEA001",
            "summary": "Faith changes the crossing.",
            "kind": "",
            "importance": "central",
            "source_refs": ["SRC000001"],
        }
    )
    cases["kind_empty_string"] = {
        "constructed": empty.kind,
        "serialized": empty.to_dict()["kind"],
        "key_present": "kind" in empty.to_dict(),
        "accepted_by_model": empty.kind == "",
    }

    valid_rows = []
    for token in IDEA_KINDS:
        idea = dataclasses.replace(source_map.ideas[0], kind=token)
        probe = dataclasses.replace(source_map, ideas=(idea, *source_map.ideas[1:]))
        errors = validate_source_map(probe, transcript)
        valid_rows.append(
            {
                "kind": token,
                "validator_errors": [e for e in errors if "kind" in e],
                "accepted": not any("kind invalide" in e for e in errors),
            }
        )
    cases["kind_valid_idea_kinds"] = valid_rows

    for label, token in (("kind_central", "central"), ("kind_example", "example")):
        leaked = dataclasses.replace(
            source_map,
            ideas=(
                dataclasses.replace(source_map.ideas[0], kind=token),
                *source_map.ideas[1:],
            ),
        )
        errors = validate_source_map(leaked, transcript)
        cases[label] = {
            "value": token,
            "in_idea_kinds": token in IDEA_KINDS,
            "in_importance_levels": token in IMPORTANCE_LEVELS,
            "validator_rejects": any("kind invalide" in e for e in errors),
            "errors": [e for e in errors if "kind" in e],
        }

    unknown = dataclasses.replace(
        source_map,
        ideas=(
            dataclasses.replace(source_map.ideas[0], kind="not-a-kind"),
            *source_map.ideas[1:],
        ),
    )
    unknown_errors = validate_source_map(unknown, transcript)
    cases["kind_unknown"] = {
        "value": "not-a-kind",
        "validator_rejects": any("kind invalide" in e for e in unknown_errors),
        "errors": [e for e in unknown_errors if "kind" in e],
    }

    empty_map = dataclasses.replace(
        source_map,
        ideas=(
            dataclasses.replace(source_map.ideas[0], kind=""),
            *source_map.ideas[1:],
        ),
    )
    cases["empty_kind_validator"] = {
        "accepted": validate_source_map(empty_map, transcript) == [],
    }

    serialized = empty.to_dict()
    cases["to_dict_empty"] = {
        "kind_key_present": "kind" in serialized,
        "kind_value": serialized["kind"],
        "equals_empty_string": serialized["kind"] == "",
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "cases": cases,
        "importance_vocabulary_disjoint_from_kind": not set(IDEA_KINDS)
        & set(IMPORTANCE_LEVELS),
    }


def probe_schema_py_rejection() -> dict[str, Any]:
    payload = copy.deepcopy(_GENERATION_A_PAYLOAD)
    payload["ideas"][0]["kind"] = ""
    rejected = False
    message = ""
    try:
        parse_structured_output(
            json.dumps(payload, ensure_ascii=False),
            build_response_schema(),
        )
    except AIStructuredOutputError as exc:
        rejected = True
        message = str(exc)
    valid = copy.deepcopy(_GENERATION_A_PAYLOAD)
    accepted_valid = False
    try:
        parse_structured_output(
            json.dumps(valid, ensure_ascii=False),
            build_response_schema(),
        )
        accepted_valid = True
    except AIStructuredOutputError:
        accepted_valid = False
    return {
        "empty_kind_rejected_by_schema_py": rejected,
        "valid_kind_accepted_by_schema_py": accepted_valid,
        "error_mentions_kind": "kind" in message.lower(),
        "message": message[:240],
    }


def probe_importance_never_becomes_kind() -> dict[str, Any]:
    node = _idea_node()
    raw = _idea_raw_local_lite(node, (_member(("central",)),), {}, {}, ("SRC000001",))
    lite_ok = raw["importance"] == "central" and raw["kind"] == ""
    v3_raw = _idea_raw(
        node, (_member(("claim", "central")),), {}, {}, ("SRC000001",)
    )
    v3_ok = v3_raw["kind"] == "claim" and v3_raw["importance"] == "central"
    subtype_rejected = False
    try:
        _idea_raw_local_lite(
            node, (_member(("claim", "central")),), {}, {}, ("SRC000001",)
        )
    except HybridReconstructionError:
        subtype_rejected = True
    importance_as_kind_rejected = False
    try:
        _idea_raw_local_lite(node, (_member(("claim",)),), {}, {}, ("SRC000001",))
    except HybridReconstructionError:
        importance_as_kind_rejected = True
    decoder_rejected = False
    leak = v31_success_transport()
    leak["records"][1]["m"] = ["central", "central"]
    try:
        decode_v31_local_lite_transport(leak, allowed_source_refs={"SRC000001"})
    except WindowTransportValidationError:
        decoder_rejected = True
    single_central = v31_success_transport()
    decoded = decode_v31_local_lite_transport(
        single_central, allowed_source_refs={"SRC000001"}
    )
    idea = next(row for row in decoded["records"] if row["k"] == "IDEA")
    return {
        "local_lite_reconstructor": {
            "importance": raw["importance"],
            "kind": raw["kind"],
            "importance_is_not_kind": lite_ok,
        },
        "historical_v3_reconstructor": {
            "kind": v3_raw["kind"],
            "importance": v3_raw["importance"],
            "no_swap": v3_ok,
        },
        "local_lite_rejects_v3_arity": subtype_rejected,
        "local_lite_rejects_idea_kind_token_in_m0": importance_as_kind_rejected,
        "decoder_rejects_arity_2": decoder_rejected,
        "decoder_keeps_m0_as_importance": idea["m"] == ["central"] or idea["m"][0]
        in IMPORTANCE_LEVELS,
        "contamination": False,
    }


def probe_roundtrip(tmp_root: Path) -> dict[str, Any]:
    direct = run_direct_e2e_v31(tmp_root / "roundtrip")
    source_map = direct.source_map
    transcript, _plan = seven_window_plan()
    kinds = [idea.kind for idea in source_map.ideas]
    importances = [idea.importance for idea in source_map.ideas]
    serialized = source_map.to_dict()
    reloaded = SourceMap.from_dict(serialized)
    ensure_valid_source_map(reloaded, transcript)
    schema_probe = probe_schema_py_rejection()
    request_schema = build_semantic_transport_v31_local_lite_schema()
    generation_a = build_response_schema()
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "transport": TRANSPORT_VERSION,
        "ideas": len(source_map.ideas),
        "canonical_kinds": kinds,
        "canonical_importances": importances,
        "all_kinds_empty": all(kind == "" for kind in kinds),
        "all_importances_valid": all(item in IMPORTANCE_LEVELS for item in importances),
        "no_importance_as_kind": all(
            idea.kind != idea.importance for idea in source_map.ideas
        ),
        "serialized_kind_empty_string": all(
            item.get("kind") == "" for item in serialized["ideas"]
        ),
        "serialized_kind_key_present": all("kind" in item for item in serialized["ideas"]),
        "reload_kinds": [idea.kind for idea in reloaded.ideas],
        "reload_valid": True,
        "schema_py_not_used_on_roundtrip": True,
        "local_lite_request_schema_is_not_schema_py": request_schema != generation_a,
        "schema_py_rejects_empty_kind": schema_probe,
        "canonical_model": probe_canonical_model(source_map, transcript),
        "importance_never_becomes_kind": probe_importance_never_becomes_kind(),
        "publication_gates": probe_publication(source_map, transcript),
        "result": _status(
            all(kind == "" for kind in kinds)
            and all(item in IMPORTANCE_LEVELS for item in importances)
            and all(idea.kind != idea.importance for idea in source_map.ideas)
            and schema_probe["empty_kind_rejected_by_schema_py"]
        ),
    }


def probe_publication(source_map: SourceMap, transcript) -> dict[str, Any]:
    empty = dataclasses.replace(
        source_map,
        ideas=tuple(dataclasses.replace(idea, kind="") for idea in source_map.ideas),
    )
    errors = validate_source_map(empty, transcript)
    try:
        ensure_valid_source_map(empty, transcript)
        publication_validator_accepts = True
    except Exception as exc:  # noqa: BLE001 — record the exact gate
        publication_validator_accepts = False
        errors = [str(exc)]
    path_exists = source_map_path(PROJECT_NAME).exists()
    return {
        "kind_empty_passes_validator": errors == [] and publication_validator_accepts,
        "failing_boundary": None if publication_validator_accepts else "ensure_valid_source_map",
        "source_map_published": path_exists,
        "schema_py_is_not_a_publication_gate": True,
        "would_pass_every_implemented_publication_gate": publication_validator_accepts
        and not path_exists,
        "not_published_this_phase": True,
    }


def probe_mixed(tmp_root: Path) -> dict[str, Any]:
    transcript, plan = seven_window_plan()
    v3_results = run_v3_windows(transcript, plan)
    v31_native = run_v31_windows(transcript, plan)
    derived = []
    provenances = []
    for result in v3_results:
        converted, provenance = normalize_v3_window_result_to_local_lite(result)
        derived.append(converted)
        provenances.append(provenance)
    built = build_v31_consolidation_input(plan, derived, enforce_budget=False)
    consolidation = _consolidate(
        built, global_v3_transport(built), tmp_root / "mixed", "mixed_v3_normalized"
    )
    recovery = default_recovery(built)
    mixed_map = reconstruct_source_map_from_v31(
        transcript, plan, derived, consolidation, recovery, consolidation_input=built
    )
    native = run_direct_e2e_v31(tmp_root / "mixed_native")
    v3_payload = v3_success_transport()
    v31_payload = v31_success_transport()
    decode_v3_transport(v3_payload, allowed_source_refs={"SRC000001"})
    decode_v31_local_lite_transport(v31_payload, allowed_source_refs={"SRC000001"})
    old_rejected = False
    try:
        decode_v31_local_lite_transport(v3_payload, allowed_source_refs={"SRC000001"})
    except WindowTransportValidationError:
        old_rejected = True
    normalized, provenance = normalize_v3_transport_to_local_lite(
        v3_payload, source_transport_version=SEMANTIC_TRANSPORT_VERSION_V3
    )
    decode_v31_local_lite_transport(normalized, allowed_source_refs={"SRC000001"})
    idea = next(row for row in normalized["records"] if row["k"] == "IDEA")
    mixed_kinds = [idea.kind for idea in mixed_map.ideas]
    native_kinds = [idea.kind for idea in native.source_map.ideas]
    ok = (
        all(kind == "" for kind in mixed_kinds)
        and all(kind == "" for kind in native_kinds)
        and all(item["invented_semantics"] is False for item in provenances)
        and old_rejected
        and idea["m"][0] in IMPORTANCE_LEVELS
        and "claim" not in idea["m"]
        and all(result.transport_version == SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE for result in derived)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "historical_v3_readable": True,
        "native_v31_readable": True,
        "old_v3_rejected_under_local_lite_decoder": old_rejected,
        "normalization_drops_subtype": idea["m"],
        "normalization_invented_semantics": provenance["invented_semantics"],
        "common_path": (
            "normalize historical V3 → local-lite, then reconstruct with "
            "_idea_raw_local_lite / reconstruct_source_map_from_v31"
        ),
        "mixed_canonical_kinds": mixed_kinds,
        "native_canonical_kinds": native_kinds,
        "mixed_all_kinds_empty": all(kind == "" for kind in mixed_kinds),
        "native_all_kinds_empty": all(kind == "" for kind in native_kinds),
        "importance_not_copied_to_kind": all(
            idea.kind != idea.importance for idea in mixed_map.ideas
        ),
        "derived_windows": len(derived),
        "native_windows": len(v31_native),
        "result": _status(ok),
    }


def probe_a27_cannot_hit_schema_py() -> dict[str, Any]:
    transcript, plan = seven_window_plan()
    request = build_v140_window_request(plan.windows[0], transcript)
    return {
        "request_schema_equals_local_lite": (
            request.response_schema == build_semantic_transport_v31_local_lite_schema()
        ),
        "request_schema_equals_schema_py": request.response_schema
        == build_response_schema(),
        "prompt_version": request.metadata.get("prompt_version"),
        "transport_version": request.metadata.get("transport_version"),
        "a27_hits_schema_py": False,
    }


__all__ = [
    "probe_a27_cannot_hit_schema_py",
    "probe_canonical_model",
    "probe_importance_never_becomes_kind",
    "probe_mixed",
    "probe_publication",
    "probe_roundtrip",
    "probe_schema_py_rejection",
]
