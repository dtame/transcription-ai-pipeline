"""Runner offline 3B.7.7A.26.1. 0 provider. 0 fenêtre réelle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_v3_a25_forensics.evidence import (
    assert_a24_evidence_intact,
    evidence_inventory,
    protected_a24_phase_hashes,
)
from app.source_analysis_v31_schema_boundary.analysis import build_boundary_analysis
from app.source_analysis_v31_schema_boundary.constants import (
    A19_STATUS,
    A21_STATUS_UNCHANGED,
    A22_STATUS,
    A23_STATUS_UNCHANGED,
    A24_STATUS,
    A25_STATUS,
    A26_STATUS,
    A27_AUTHORIZATION,
    BLOCKS_A27,
    MISMATCH_CLASSIFICATION,
    MODE,
    NEXT_ACTION,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_CHANGED,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    READY_WINDOWS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SCHEMA_VERSION,
    SOURCE_MAP_STATUS,
)
from app.source_analysis_v31_schema_boundary.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
    assert_schema_py_untouched,
)
from app.source_analysis_v31_schema_boundary.probes import (
    probe_a27_cannot_hit_schema_py,
    probe_mixed,
    probe_roundtrip,
)
from app.source_analysis_v31_schema_boundary.report import render_report


def _pass(value: Any) -> bool:
    return value == "PASS" or value is True


def build_bundle(
    project_name: str = PROJECT_NAME,
    *,
    tests: str,
    tmp_root: Path,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    assert_schema_py_untouched()
    before = protected_a24_phase_hashes(project_name, sortie_dir=sortie_dir)
    evidence = evidence_inventory(project_name, sortie_dir=sortie_dir)
    boundary = build_boundary_analysis()
    roundtrip = probe_roundtrip(tmp_root / "roundtrip")
    mixed = probe_mixed(tmp_root / "mixed")
    a27 = probe_a27_cannot_hit_schema_py()
    after = protected_a24_phase_hashes(project_name, sortie_dir=sortie_dir)
    assert_a24_evidence_intact(before, after)
    source_map_absent = not source_map_path(project_name, sortie_dir=sortie_dir).exists()
    classification = boundary["classification"]
    consumers = boundary["consumers"]
    role = boundary["schema_py_role"]
    publication = roundtrip["publication_gates"]
    contamination = roundtrip["importance_never_becomes_kind"]
    result = "PASS"
    required = [
        roundtrip.get("result"),
        mixed.get("result"),
        roundtrip.get("all_kinds_empty"),
        not contamination.get("contamination", True),
        consumers["used_for_local_window_extraction"] is False,
        consumers["reconstructed_local_lite_passes_through_it"] is False,
        classification["mismatch_classification"] == MISMATCH_CLASSIFICATION,
        a27["a27_hits_schema_py"] is False,
        source_map_absent,
        PLANNER_VERSION == "window-planner-v2.0",
        REAL_PROVIDER_CALLS_THIS_PHASE == 0,
        REAL_WINDOW_CALLS == 0,
        PRODUCTION_CHANGED is False,
        role["ideas_kind_required"] is True,
        role["empty_string_in_enum"] is False,
    ]
    if not all(_pass(item) if isinstance(item, str) else bool(item) for item in required):
        result = "PARTIAL"
    if REAL_PROVIDER_CALLS_THIS_PHASE or REAL_WINDOW_CALLS:
        result = "FAIL"
    header = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "a26_status": f"{A26_STATUS} unchanged",
        "schema_py_role": role["boundary"],
        "schema_py_used_by_local_lite": "NO",
        "schema_py_used_by_global_consolidation": "NO",
        "schema_py_used_by_publication": "NO",
        "canonical_kind_optional": "YES — empty string",
        "empty_kind_valid": "YES at model/validator/serialization; NO at schema.py",
        "empty_kind_serialization": '"kind": ""',
        "importance_to_kind_contamination": "NO",
        "local_lite_roundtrip": roundtrip.get("result"),
        "mixed_v3_v31": mixed.get("result"),
        "mismatch_classification": MISMATCH_CLASSIFICATION,
        "blocks_a27": "YES" if BLOCKS_A27 else "NO",
        "a27_authorization": A27_AUTHORIZATION,
        "production_changed": "NO",
        "source_map": SOURCE_MAP_STATUS if source_map_absent else "PRESENT",
        "real_windows_ready": READY_WINDOWS,
        "phase_3b": PHASE_3B_STATUS,
        "tests": tests,
        "next_action": NEXT_ACTION,
        "a19": A19_STATUS,
        "a21": A21_STATUS_UNCHANGED,
        "a22": A22_STATUS,
        "a23": A23_STATUS_UNCHANGED,
        "a24": A24_STATUS,
        "a25": A25_STATUS,
        "a26": A26_STATUS,
        "production_default": PRODUCTION_PLANNER_VERSION,
        "publication_empty_kind_passes": publication.get(
            "would_pass_every_implemented_publication_gate"
        ),
    }
    isolation = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "source_map_absent": source_map_absent,
        "historical_hashes_intact": before == after,
        "evidence": evidence,
        "schema_py_untouched": True,
        "production_changed": False,
    }
    report = render_report(
        header=header,
        boundary=boundary,
        roundtrip=roundtrip,
        mixed=mixed,
        a27=a27,
        isolation=isolation,
        tests=tests,
    )
    return {
        "header": header,
        "boundary": boundary,
        "roundtrip": roundtrip,
        "mixed": mixed,
        "a27": a27,
        "isolation": isolation,
        "report": report,
    }


__all__ = ["build_bundle"]
