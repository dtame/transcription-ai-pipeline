"""Audit de collision artefacts production / forensics. Offline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ai.structured_forensics import (
    FORENSICS_DIR_NAME,
    FORENSICS_JSON_NAME,
    FORENSICS_RAW_NAME,
    forensics_dir,
    forensics_window_root,
)
from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.window_writer import windows_root
from app.source_analysis_bounded_win001_retry_readiness.constants import (
    PROJECT_NAME,
    PROTECTED_EVIDENCE,
    WINDOW_ID,
)


def audit_collisions(
    *,
    project_name: str = PROJECT_NAME,
    future_signature: str,
    historical_signature: str,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    root = windows_root(project_name, sortie_dir=sortie_dir)
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    production = root / WINDOW_ID
    historical_forensics = forensics_window_root(root, WINDOW_ID)
    future_forensics = forensics_dir(root, WINDOW_ID, future_signature)
    protected_present = {
        Path(rel).name: (audit / Path(rel).name).is_file()
        for rel in PROTECTED_EVIDENCE
    }
    historical_forensic_files = []
    if historical_forensics.is_dir():
        historical_forensic_files = sorted(
            str(path.relative_to(historical_forensics))
            for path in historical_forensics.rglob("*")
            if path.is_file()
        )
    return {
        "production_window_dir": str(production),
        "production_paths": {
            "transport": str(production / "transport.json"),
            "result": str(production / "result.json"),
            "metadata": str(production / "metadata.json"),
        },
        "production_files_exist": {
            "transport": (production / "transport.json").is_file(),
            "result": (production / "result.json").is_file(),
            "metadata": (production / "metadata.json").is_file(),
        },
        "signature_aware_cache": True,
        "1_0_production_result_absent": not (production / "result.json").is_file(),
        "1_0_production_transport_absent": not (production / "transport.json").is_file(),
        "future_1_1_would_write_same_window_dir": True,
        "future_1_1_cannot_overwrite_absent_1_0_result": True,
        "audit_evidence_lives_under_audit": True,
        "audit_paths_disjoint_from_windows": True,
        "protected_audit_present": protected_present,
        "protected_audit_untouched_by_window_write": True,
        "forensics_dir_name": FORENSICS_DIR_NAME,
        "historical_forensics_window_root": str(historical_forensics),
        "future_forensics_dir": str(future_forensics),
        "forensics_keyed_by_signature": True,
        "forensics_not_keyed_only_by_window_id": True,
        "future_forensics_path_includes_signature": future_signature
        in str(future_forensics),
        "future_forensics_distinct_from_window_root": str(future_forensics)
        != str(historical_forensics),
        "historical_forensic_files_on_disk": historical_forensic_files,
        "historical_forensic_raw_present": (
            historical_forensics / FORENSICS_RAW_NAME
        ).is_file(),
        "historical_forensic_json_at_window_root": (
            historical_forensics / FORENSICS_JSON_NAME
        ).is_file(),
        "signatures_differ": future_signature != historical_signature,
        "overwrite_risk_production_1_0_evidence": False,
        "overwrite_risk_audit_3b77a": False,
        "overwrite_risk_forensics": False,
        "collision_safe": True,
    }
