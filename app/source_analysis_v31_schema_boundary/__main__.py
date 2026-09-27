"""Entrée offline 3B.7.7A.26.1. 0 provider."""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.source_analysis_v31_schema_boundary.constants import PHASE, PROJECT_NAME
from app.source_analysis_v31_schema_boundary.runner import build_bundle
from app.source_analysis_v31_schema_boundary.writer import write_audit_bundle


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="a261-") as tmp:
        bundle = build_bundle(
            project_name=PROJECT_NAME,
            tests="offline A.26.1",
            tmp_root=Path(tmp),
        )
    written = write_audit_bundle(PROJECT_NAME, bundle)
    header = bundle["header"]
    print(f"[a261_schema_boundary] phase={PHASE} result={header.get('result')}")
    print(f"[a261_schema_boundary] provider_calls={header.get('real_provider_calls')}")
    print(f"[a261_schema_boundary] classification={header.get('mismatch_classification')}")
    print(f"[a261_schema_boundary] report={written['report']}")
    print("[a261_schema_boundary] STOP — revue humaine. Phase 3B INCOMPLETE.")


if __name__ == "__main__":
    main()
