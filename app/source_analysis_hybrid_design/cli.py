"""
CLI offline du design 3B.7.

Usage :
    python -m app.source_analysis_hybrid_design.cli <projet>

Aucun --real-call. Aucun engine.generate(). Aucun réseau.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.source_analysis_execution_strategy.review import (
    inspect_project_state,
    source_map_present,
)
from app.source_analysis_hybrid_design.architecture import assert_offline_package
from app.source_analysis_hybrid_design.constants import (
    ARCHITECTURE_DESIGN_ARTIFACT_NAME,
    CONSOLIDATION_DESIGN_ARTIFACT_NAME,
    MODE,
    PHASE,
    PLANNER_SIMULATION_ARTIFACT_NAME,
    REPORT_NAME,
    STRATEGY,
    WINDOW_DESIGN_ARTIFACT_NAME,
)
from app.source_analysis_hybrid_design.design import build_deterministic_pair
from app.source_analysis_hybrid_design.contracts import (
    architecture_design,
    consolidation_design,
    window_design,
)
from app.source_analysis_hybrid_design.integrity import (
    assert_protected_unchanged,
    snapshot_hybrid_design_protected,
)
from app.source_analysis_hybrid_design.report import render_report
from app.source_analysis_hybrid_design.simulation import (
    build_deterministic_simulation,
    load_clean_transcript,
)
from app.source_analysis_hybrid_design.writer import (
    architecture_design_path,
    assert_no_production_source_map,
    consolidation_design_path,
    planner_simulation_path,
    report_path,
    window_design_path,
    write_bytes_atomic,
)


@dataclass
class HybridDesignResult:
    project_name: str
    outcome: str = "PASS"
    simulation_sha256: str = ""
    window_sha256: str = ""
    consolidation_sha256: str = ""
    architecture_sha256: str = ""
    deterministic: bool = False
    protected_unchanged: bool = False
    source_map_present: bool = False
    project_state_status: str = ""
    project_state_error: str | None = None
    files_created: list[str] = field(default_factory=list)
    simulation: dict[str, Any] = field(default_factory=dict)
    window: dict[str, Any] = field(default_factory=dict)
    consolidation: dict[str, Any] = field(default_factory=dict)
    architecture: dict[str, Any] = field(default_factory=dict)


def run_hybrid_design(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    write_artifacts: bool = True,
) -> HybridDesignResult:
    assert_offline_package()
    assert_no_production_source_map(project_name, sortie_dir=sortie_dir)
    before = snapshot_hybrid_design_protected(
        project_name, sortie_dir=sortie_dir, require_all=False
    )
    state = inspect_project_state(project_name, sortie_dir=sortie_dir)
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    simulation, sim1, sim2 = build_deterministic_simulation(transcript)
    window, win1, win2 = build_deterministic_pair(window_design, simulation)
    consolidation, con1, con2 = build_deterministic_pair(
        consolidation_design, simulation
    )
    architecture, arc1, arc2 = build_deterministic_pair(
        architecture_design, simulation, window, consolidation
    )
    result = HybridDesignResult(
        project_name=project_name,
        simulation=simulation,
        window=window,
        consolidation=consolidation,
        architecture=architecture,
        simulation_sha256=sim1,
        window_sha256=win1,
        consolidation_sha256=con1,
        architecture_sha256=arc1,
        deterministic=sim1 == sim2 and win1 == win2 and con1 == con2 and arc1 == arc2,
        project_state_status=str(state.get("status") or ""),
        project_state_error=state.get("error"),
        source_map_present=source_map_present(project_name, sortie_dir=sortie_dir),
    )
    if write_artifacts:
        write_bytes_atomic(
            planner_simulation_path(project_name, sortie_dir=sortie_dir),
            simulation,
        )
        result.files_created.append(PLANNER_SIMULATION_ARTIFACT_NAME)
        write_bytes_atomic(
            window_design_path(project_name, sortie_dir=sortie_dir),
            window,
        )
        result.files_created.append(WINDOW_DESIGN_ARTIFACT_NAME)
        write_bytes_atomic(
            consolidation_design_path(project_name, sortie_dir=sortie_dir),
            consolidation,
        )
        result.files_created.append(CONSOLIDATION_DESIGN_ARTIFACT_NAME)
        write_bytes_atomic(
            architecture_design_path(project_name, sortie_dir=sortie_dir),
            architecture,
        )
        result.files_created.append(ARCHITECTURE_DESIGN_ARTIFACT_NAME)
        write_bytes_atomic(
            report_path(project_name, sortie_dir=sortie_dir),
            render_report(
                simulation=simulation,
                window=window,
                consolidation=consolidation,
                architecture=architecture,
            ),
        )
        result.files_created.append(REPORT_NAME)
    after = snapshot_hybrid_design_protected(
        project_name, sortie_dir=sortie_dir, require_all=False
    )
    assert_protected_unchanged(before, after)
    assert_no_production_source_map(project_name, sortie_dir=sortie_dir)
    result.protected_unchanged = True
    selected = simulation.get("selected_policy") or {}
    if not result.deterministic:
        result.outcome = "FAIL"
    if architecture.get("strategy") != STRATEGY:
        result.outcome = "FAIL"
    if not selected.get("all_present_owned_exactly_once"):
        result.outcome = "FAIL"
    if selected.get("any_hard_max_violation"):
        result.outcome = "FAIL"
    if result.source_map_present:
        result.outcome = "FAIL"
    if state.get("status") in ("SUCCESS", "completed"):
        result.outcome = "FAIL"
    return result


def _usage() -> None:
    print("Usage  : python -m app.source_analysis_hybrid_design.cli <projet>")
    print("Mode   : OFFLINE_DESIGN. Aucun --real-call. 0 appel réseau.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0
    if "--real-call" in argv:
        print("[ERREUR] --real-call est interdit. Ce design est OFFLINE.")
        return 2
    project_name = argv[0]
    flags = set(argv[1:])
    if flags:
        print(f"[ERREUR] option(s) inconnue(s) : {sorted(flags)}")
        _usage()
        return 2

    print(f"[hybrid_design] projet={project_name}")
    print(f"[hybrid_design] phase={PHASE} mode={MODE}")
    print("[hybrid_design] aucun engine.generate(), aucun réseau, aucun Attempt #3")
    print(f"[hybrid_design] strategy={STRATEGY}")

    result = run_hybrid_design(project_name)
    print(f"[hybrid_design] outcome={result.outcome}")
    print(f"[hybrid_design] simulation_sha={result.simulation_sha256}")
    print(f"[hybrid_design] window_sha={result.window_sha256}")
    print(f"[hybrid_design] consolidation_sha={result.consolidation_sha256}")
    print(f"[hybrid_design] architecture_sha={result.architecture_sha256}")
    print(f"[hybrid_design] deterministic={result.deterministic}")
    print(
        f"[hybrid_design] state={result.project_state_status} "
        f"error={result.project_state_error}"
    )
    print(f"[hybrid_design] protected_unchanged={result.protected_unchanged}")
    print("[hybrid_design] STOP — revue humaine. Phase 3B INCOMPLETE.")
    return 0 if result.outcome == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
