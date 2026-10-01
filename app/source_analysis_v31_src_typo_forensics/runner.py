"""Assemble le dossier A.32. 0 provider. 0 mutation de politique. 0 promotion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_src_typo_forensics.classify import srec_transformation
from app.source_analysis_v31_src_typo_forensics.constants import (
    A31_STATUS_UNCHANGED,
    MODE,
    PHASE,
    PHASE_3B_STATUS,
    PROJECT_NAME,
    READY_AFTER,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SCHEMA_VERSION,
    SOURCE_MAP_STATUS,
    WIN007_PROMOTION_AUTHORIZED,
    WIN007_REQUEST_ID,
    WINDOW_ID,
)
from app.source_analysis_v31_src_typo_forensics.content import intended_source_analysis
from app.source_analysis_v31_src_typo_forensics.counterfactual import (
    replay_derived_correction,
)
from app.source_analysis_v31_src_typo_forensics.decision import build_decision
from app.source_analysis_v31_src_typo_forensics.evidence import evidence_inventory
from app.source_analysis_v31_src_typo_forensics.history import build_src_history
from app.source_analysis_v31_src_typo_forensics.policy import build_options
from app.source_analysis_v31_src_typo_forensics.replay import replay_win007_offline


def _root_cascade(replay: dict[str, Any]) -> dict[str, Any]:
    inventory = replay.get("src_inventory") or {}
    malformed = list(inventory.get("malformed_rows") or [])
    pipeline = []
    for gate, key in (
        ("v31_decoder", "v31_decoder"),
        ("handle_registry", "handle_registry"),
        ("handle_resolution", "handle_resolution"),
        ("v31_validator", "v31_validator"),
    ):
        if replay.get(key) == "FAIL":
            pipeline.append(gate)
    return {
        "root_src_violations": len(malformed),
        "cascade_src_violations": 0,
        "other_src_root_violations": max(0, len(malformed) - 1),
        "cascade_pipeline_gates": pipeline,
        "cascade_pipeline_count": len(pipeline),
        "note": (
            "Decoder fail-closed on the first malformed SRC. Handle registry / "
            "resolution / validator did not independently discover additional "
            "SRC defects. Exhaustive raw inventory found no second root SRC."
        ),
    }


def build_bundle(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.32",
) -> dict[str, Any]:
    evidence = evidence_inventory(project_name, sortie_dir=sortie_dir)
    replay = replay_win007_offline(project_name, sortie_dir=sortie_dir)
    transformation = srec_transformation()
    record = {
        "k": replay.get("record_kind"),
        "h": replay.get("record_handle"),
        "v": replay.get("record_value"),
        "s": replay.get("record_refs"),
    }
    intended = intended_source_analysis(
        window=replay["window"],
        transcript=replay["transcript"],
        record=record,
    )
    history = build_src_history(project_name, sortie_dir=sortie_dir)
    counterfactual = replay_derived_correction(
        replay, project_name=project_name, sortie_dir=sortie_dir
    )
    options = build_options(
        replay=replay,
        intended=intended,
        history=history,
        transformation=transformation,
        counterfactual=counterfactual,
    )
    decision = build_decision(
        options=options,
        intended=intended,
        counterfactual=counterfactual,
        history=history,
        transformation=transformation,
    )
    root = _root_cascade(replay)
    semantic = counterfactual.get("semantic_review")
    quality = None
    if isinstance(semantic, dict):
        quality = semantic.get("semantic_quality")
    result = "PASS" if (
        replay["reproduced"]
        and replay["request_id_match"]
        and REAL_PROVIDER_CALLS_THIS_PHASE == 0
        and not WIN007_PROMOTION_AUTHORIZED
        and not source_map_path(project_name, sortie_dir=sortie_dir).exists()
        and decision["selected_policy"]
    ) else "FAIL"
    header = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "a31_status": A31_STATUS_UNCHANGED,
        "ready": READY_AFTER,
        "win007": "NOT READY",
        "original_request_id": WIN007_REQUEST_ID,
        "window_id": WINDOW_ID,
        "source_map": SOURCE_MAP_STATUS,
        "phase_3b": PHASE_3B_STATUS,
        "promoted": False,
        "tests": tests,
        "next_action": "HUMAN REVIEW",
        "counterfactual_semantic_quality": quality,
    }
    return {
        "header": header,
        "evidence": evidence,
        "replay": replay,
        "root_cascade": root,
        "transformation": transformation,
        "intended": intended,
        "history": history,
        "options": options,
        "counterfactual": counterfactual,
        "decision": decision,
    }


__all__ = ["build_bundle"]
