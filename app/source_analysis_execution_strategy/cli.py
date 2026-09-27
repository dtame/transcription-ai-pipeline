"""
CLI offline de la revue 3B.6.

Usage :
    python -m app.source_analysis_execution_strategy.cli <projet>

Aucun --real-call. Aucun engine.generate(). Aucun réseau.
Aucun Attempt #3.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.source_analysis_execution_strategy.architecture import (
    assert_offline_package,
)
from app.source_analysis_execution_strategy.constants import (
    MODE,
    PHASE,
    RECOMMENDED_STRATEGY,
    REPORT_NAME,
    REVIEW_ARTIFACT_NAME,
    SIMULATION_ARTIFACT_NAME,
)
from app.source_analysis_execution_strategy.integrity import (
    assert_protected_unchanged,
    snapshot_strategy_review_protected,
)
from app.source_analysis_execution_strategy.report import render_report
from app.source_analysis_execution_strategy.review import (
    build_deterministic_review,
    inspect_project_state,
    source_map_present,
)
from app.source_analysis_execution_strategy.windows import (
    build_deterministic_simulation,
    load_clean_transcript,
)
from app.source_analysis_execution_strategy.writer import (
    assert_no_production_source_map,
    report_path,
    review_path,
    simulation_path,
    write_bytes_atomic,
)


@dataclass
class StrategyReviewResult:
    project_name: str
    outcome: str = "PASS"
    simulation_sha256: str = ""
    review_sha256: str = ""
    deterministic: bool = False
    protected_unchanged: bool = False
    source_map_present: bool = False
    project_state_status: str = ""
    project_state_error: str | None = None
    files_created: list[str] = field(default_factory=list)
    simulation: dict[str, Any] = field(default_factory=dict)
    review: dict[str, Any] = field(default_factory=dict)


def run_strategy_review(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    write_artifacts: bool = True,
) -> StrategyReviewResult:
    assert_offline_package()
    assert_no_production_source_map(project_name, sortie_dir=sortie_dir)
    before = snapshot_strategy_review_protected(
        project_name, sortie_dir=sortie_dir, require_all=False
    )
    state = inspect_project_state(project_name, sortie_dir=sortie_dir)
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    simulation, sim_sha1, sim_sha2 = build_deterministic_simulation(transcript)
    review, rev_sha1, rev_sha2 = build_deterministic_review(
        simulation, project_name=project_name, sortie_dir=sortie_dir
    )
    result = StrategyReviewResult(
        project_name=project_name,
        simulation=simulation,
        review=review,
        simulation_sha256=sim_sha1,
        review_sha256=rev_sha1,
        deterministic=sim_sha1 == sim_sha2 and rev_sha1 == rev_sha2,
        project_state_status=str(state.get("status") or ""),
        project_state_error=state.get("error"),
        source_map_present=source_map_present(
            project_name, sortie_dir=sortie_dir
        ),
    )
    if write_artifacts:
        write_bytes_atomic(
            simulation_path(project_name, sortie_dir=sortie_dir),
            simulation,
        )
        result.files_created.append(SIMULATION_ARTIFACT_NAME)
        write_bytes_atomic(
            review_path(project_name, sortie_dir=sortie_dir),
            review,
        )
        result.files_created.append(REVIEW_ARTIFACT_NAME)
        write_bytes_atomic(
            report_path(project_name, sortie_dir=sortie_dir),
            render_report(
                review,
                simulation=simulation,
                sha256=rev_sha1,
                simulation_sha256=sim_sha1,
            ),
        )
        result.files_created.append(REPORT_NAME)
    after = snapshot_strategy_review_protected(
        project_name, sortie_dir=sortie_dir, require_all=False
    )
    assert_protected_unchanged(before, after)
    assert_no_production_source_map(project_name, sortie_dir=sortie_dir)
    result.protected_unchanged = True
    if not result.deterministic:
        result.outcome = "FAIL"
    if review.get("recommended_strategy") != RECOMMENDED_STRATEGY:
        result.outcome = "FAIL"
    if review.get("execution", {}).get("provider_calls") != 0:
        result.outcome = "FAIL"
    if review.get("execution", {}).get("source_map_published"):
        result.outcome = "FAIL"
    if review.get("execution", {}).get("attempt_3_executed"):
        result.outcome = "FAIL"
    if state.get("status") in ("SUCCESS", "completed"):
        result.outcome = "FAIL"
    if result.source_map_present:
        result.outcome = "FAIL"
    return result


def _usage() -> None:
    print("Usage  : python -m app.source_analysis_execution_strategy.cli <projet>")
    print("Mode   : OFFLINE_ARCHITECTURE_REVIEW. Aucun --real-call. 0 appel réseau.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0
    if "--real-call" in argv:
        print("[ERREUR] --real-call est interdit. Cette revue est OFFLINE.")
        return 2
    project_name = argv[0]
    flags = set(argv[1:])
    if flags:
        print(f"[ERREUR] option(s) inconnue(s) : {sorted(flags)}")
        _usage()
        return 2

    print(f"[strategy_review] projet={project_name}")
    print(f"[strategy_review] phase={PHASE} mode={MODE}")
    print("[strategy_review] aucun engine.generate(), aucun réseau, aucun Attempt #3")
    print(f"[strategy_review] recommended={RECOMMENDED_STRATEGY}")

    result = run_strategy_review(project_name)
    print(f"[strategy_review] outcome={result.outcome}")
    print(f"[strategy_review] simulation_sha={result.simulation_sha256}")
    print(f"[strategy_review] review_sha={result.review_sha256}")
    print(f"[strategy_review] deterministic={result.deterministic}")
    print(
        f"[strategy_review] state={result.project_state_status} "
        f"error={result.project_state_error}"
    )
    print(f"[strategy_review] protected_unchanged={result.protected_unchanged}")
    print("[strategy_review] STOP — revue humaine. Phase 3B INCOMPLETE.")
    return 0 if result.outcome == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
