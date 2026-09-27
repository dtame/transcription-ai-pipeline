"""
CLI offline de la configuration timeout 3B.5.1.

Usage :
    python -m app.source_analysis_timeout_config.cli <projet>

Aucun --real-call. Aucun engine.generate(). Aucun réseau.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.source_analysis_timeout_config.audit import (
    assert_offline_package,
    assert_source_map_absent,
    build_deterministic_audit,
    inspect_project_state,
)
from app.source_analysis_timeout_config.constants import (
    DIAGNOSTIC_ARTIFACT_NAME,
    MODE,
    NEW_ANTHROPIC_CALL_AUTHORIZED,
    PHASE,
    REPORT_NAME,
)
from app.source_analysis_timeout_config.integrity import (
    assert_protected_unchanged,
    snapshot_timeout_config_protected,
)
from app.source_analysis_timeout_config.report import render_report
from app.source_analysis_timeout_config.writer import (
    assert_no_production_source_map,
    diagnostic_path,
    report_path,
    write_bytes_atomic,
)


@dataclass
class TimeoutConfigResult:
    project_name: str
    outcome: str = "PASS"
    diagnostic_sha256: str = ""
    diagnostic_deterministic: bool = False
    protected_unchanged: bool = False
    source_map_present: bool = False
    project_state_status: str = ""
    project_state_error: str | None = None
    files_created: list[str] = field(default_factory=list)
    diagnostic: dict[str, Any] = field(default_factory=dict)


def run_timeout_config_audit(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    write_artifacts: bool = True,
) -> TimeoutConfigResult:
    assert_offline_package()
    assert_source_map_absent(project_name, sortie_dir=sortie_dir)
    before = snapshot_timeout_config_protected(
        project_name, sortie_dir=sortie_dir, require_all=False
    )
    state = inspect_project_state(project_name)
    payload, sha1, sha2 = build_deterministic_audit()
    result = TimeoutConfigResult(
        project_name=project_name,
        diagnostic=payload,
        diagnostic_sha256=sha1,
        diagnostic_deterministic=sha1 == sha2,
        project_state_status=str(state.get("status") or ""),
        project_state_error=state.get("error"),
        source_map_present=False,
    )
    if write_artifacts:
        write_bytes_atomic(
            diagnostic_path(project_name, sortie_dir=sortie_dir),
            payload,
        )
        result.files_created.append(DIAGNOSTIC_ARTIFACT_NAME)
        write_bytes_atomic(
            report_path(project_name, sortie_dir=sortie_dir),
            render_report(payload, sha256=sha1),
        )
        result.files_created.append(REPORT_NAME)
    after = snapshot_timeout_config_protected(
        project_name, sortie_dir=sortie_dir, require_all=False
    )
    assert_protected_unchanged(before, after)
    assert_no_production_source_map(project_name, sortie_dir=sortie_dir)
    result.protected_unchanged = True
    if not result.diagnostic_deterministic:
        result.outcome = "FAIL"
    if result.diagnostic.get("architecture", {}).get("legacy_constant_controls_runner"):
        result.outcome = "FAIL"
    if result.diagnostic.get("production_decision", {}).get(
        "exact_next_read_timeout_authorized"
    ):
        result.outcome = "FAIL"
    return result


def _usage() -> None:
    print("Usage  : python -m app.source_analysis_timeout_config.cli <projet>")
    print("Mode   : OFFLINE. Aucun --real-call. 0 appel réseau.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0
    if "--real-call" in argv:
        print("[ERREUR] --real-call est interdit. Cet audit est OFFLINE.")
        return 2
    project_name = argv[0]
    flags = set(argv[1:])
    if flags:
        print(f"[ERREUR] option(s) inconnue(s) : {sorted(flags)}")
        _usage()
        return 2

    print(f"[timeout_config] projet={project_name}")
    print(f"[timeout_config] phase={PHASE} mode={MODE}")
    print("[timeout_config] aucun engine.generate(), aucun réseau")
    print(f"[timeout_config] new_anthropic_call_authorized={NEW_ANTHROPIC_CALL_AUTHORIZED}")

    result = run_timeout_config_audit(project_name)
    print(f"[timeout_config] outcome={result.outcome}")
    print(f"[timeout_config] diagnostic_sha={result.diagnostic_sha256}")
    print(f"[timeout_config] deterministic={result.diagnostic_deterministic}")
    print(
        f"[timeout_config] state={result.project_state_status} "
        f"error={result.project_state_error}"
    )
    print(f"[timeout_config] protected_unchanged={result.protected_unchanged}")
    print("[timeout_config] STOP — aucun nouvel appel Anthropic. Revue humaine.")
    return 0 if result.outcome == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
