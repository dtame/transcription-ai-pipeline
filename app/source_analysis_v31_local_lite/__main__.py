"""Entrée offline 3B.7.7A.26. 0 provider."""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.source_analysis_v31_local_lite.constants import PHASE, PROJECT_NAME
from app.source_analysis_v31_local_lite.runner import build_bundle
from app.source_analysis_v31_local_lite.writer import write_audit_bundle


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="a26-") as tmp:
        bundle = build_bundle(
            project_name=PROJECT_NAME,
            tests="offline A.26",
            tmp_root=Path(tmp),
        )
    written = write_audit_bundle(PROJECT_NAME, bundle)
    header = bundle["header"]
    print(f"[a26_local_lite] phase={PHASE} result={header.get('result')}")
    print(f"[a26_local_lite] provider_calls={header.get('real_provider_calls')}")
    print(f"[a26_local_lite] report={written['report']}")
    print("[a26_local_lite] STOP — revue humaine. Phase 3B INCOMPLETE.")


if __name__ == "__main__":
    main()
