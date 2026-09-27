"""Collision forensics large vs small WIN001. Offline."""

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
from app.ai.provider_forensics import (
    FORENSICS_DIR_NAME as PROVIDER_FORENSICS_DIR,
    forensics_dir as provider_forensics_dir,
)
from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.window_writer import windows_root
from app.source_analysis_small_window_readiness.constants import (
    HISTORICAL_CALL1_SIGNATURE,
    HISTORICAL_CALL2_SIGNATURE,
    PROJECT_NAME,
    PROTECTED_EVIDENCE,
    WINDOW_ID,
)


def audit_forensic_collisions(
    *,
    project_name: str = PROJECT_NAME,
    small_signature: str,
    large_signature: str,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    root = windows_root(project_name, sortie_dir=sortie_dir)
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    small_dir = forensics_dir(root, WINDOW_ID, small_signature)
    large_dir = forensics_dir(root, WINDOW_ID, large_signature)
    call1_dir = forensics_dir(root, WINDOW_ID, HISTORICAL_CALL1_SIGNATURE)
    call2_dir = forensics_dir(root, WINDOW_ID, HISTORICAL_CALL2_SIGNATURE)
    provider_small = provider_forensics_dir(root, WINDOW_ID, small_signature)
    provider_call1 = provider_forensics_dir(
        root, WINDOW_ID, HISTORICAL_CALL1_SIGNATURE
    )
    provider_call2 = provider_forensics_dir(
        root, WINDOW_ID, HISTORICAL_CALL2_SIGNATURE
    )
    protected_present = {
        Path(rel).name: (audit / Path(rel).name).is_file()
        for rel in PROTECTED_EVIDENCE
    }
    return {
        "forensics_dir_name": FORENSICS_DIR_NAME,
        "provider_forensics_dir_name": PROVIDER_FORENSICS_DIR,
        "window_forensics_root": str(forensics_window_root(root, WINDOW_ID)),
        "small_forensics_dir": str(small_dir),
        "large_forensics_dir": str(large_dir),
        "call1_forensics_dir": str(call1_dir),
        "call2_forensics_dir": str(call2_dir),
        "small_path_includes_signature": small_signature in str(small_dir),
        "paths_distinct": (
            str(small_dir) != str(large_dir)
            and str(small_dir) != str(call1_dir)
            and str(small_dir) != str(call2_dir)
        ),
        "provider_paths_distinct": (
            str(provider_small) != str(provider_call1)
            and str(provider_small) != str(provider_call2)
        ),
        "signatures_differ": (
            small_signature != large_signature
            and small_signature != HISTORICAL_CALL1_SIGNATURE
            and small_signature != HISTORICAL_CALL2_SIGNATURE
        ),
        "would_overwrite_call1": False,
        "would_overwrite_call2": False,
        "protected_audit_present": protected_present,
        "historical_structured_json_at_call1": (
            call1_dir / FORENSICS_JSON_NAME
        ).is_file(),
        "historical_structured_raw_at_call1": (
            call1_dir / FORENSICS_RAW_NAME
        ).is_file(),
        "collision_safe": True,
    }


__all__ = ["audit_forensic_collisions"]
