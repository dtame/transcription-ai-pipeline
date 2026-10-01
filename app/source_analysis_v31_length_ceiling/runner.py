"""Assemble le dossier A.29. 0 provider. 0 mutation de politique."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_length_ceiling.boundary import build_boundary_map
from app.source_analysis_v31_length_ceiling.classify import classify_offenders
from app.source_analysis_v31_length_ceiling.constants import (
    A18_PROOF_STILL_APPLIES,
    A27_STATUS_UNCHANGED,
    A28_STATUS_UNCHANGED,
    FAILURE_CLASS,
    MODE,
    PHASE,
    PHASE_3B_STATUS,
    PROJECT_NAME,
    READY_WINDOWS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SCHEMA_VERSION,
    SELECTED_POLICY,
    SOURCE_MAP_STATUS,
    WIN003_RETRY_AUTHORIZED,
)
from app.source_analysis_v31_length_ceiling.counterfactual import (
    assert_production_limits_untouched,
    build_counterfactual,
)
from app.source_analysis_v31_length_ceiling.decision import build_decision
from app.source_analysis_v31_length_ceiling.distribution import build_distribution
from app.source_analysis_v31_length_ceiling.evidence import evidence_inventory
from app.source_analysis_v31_length_ceiling.options import build_options
from app.source_analysis_v31_length_ceiling.replay import replay_win003_offline
from app.source_analysis_v31_local_lite.downstream import build_downstream_impact


def build_bundle(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.29",
) -> dict[str, Any]:
    assert_production_limits_untouched()
    evidence = evidence_inventory(project_name, sortie_dir=sortie_dir)
    replay = replay_win003_offline(project_name, sortie_dir=sortie_dir)
    boundary = build_boundary_map()
    distribution = build_distribution(
        project_name,
        sortie_dir=sortie_dir,
        win003_transport=replay["transport"],
    )
    classification = classify_offenders(
        replay["offenders"],
        window=replay["window"],
        transcript=replay["transcript"],
        transport=replay["transport"],
    )
    counterfactual = build_counterfactual(replay)
    options = build_options(
        offenders=replay["offenders"],
        classification=classification,
        counterfactual=counterfactual,
        boundary=boundary,
    )
    decision = build_decision(
        options=options,
        counterfactual=counterfactual,
        classification=classification,
        semantic=counterfactual.get("semantic_review"),
        distribution=distribution,
    )
    downstream = build_downstream_impact(
        project_name,
        source_map_exists=source_map_path(
            project_name, sortie_dir=sortie_dir
        ).exists(),
    )
    result = "PASS" if replay["reproduced"] and decision["selected_policy"] == SELECTED_POLICY else "FAIL"
    header = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "a27_status": A27_STATUS_UNCHANGED,
        "a28_status": A28_STATUS_UNCHANGED,
        "ready_windows": READY_WINDOWS,
        "win003_retry_authorized": WIN003_RETRY_AUTHORIZED,
        "source_map": SOURCE_MAP_STATUS,
        "phase_3b": PHASE_3B_STATUS,
        "failure_class": FAILURE_CLASS,
        "a18_proof_still_applies": A18_PROOF_STILL_APPLIES,
        "tests": tests,
        "next_action": "HUMAN REVIEW",
    }
    assert_production_limits_untouched()
    return {
        "header": header,
        "evidence": evidence,
        "replay": replay,
        "boundary": boundary,
        "distribution": distribution,
        "classification": classification,
        "counterfactual": counterfactual,
        "options": options,
        "decision": decision,
        "downstream": downstream,
    }


__all__ = ["build_bundle"]
