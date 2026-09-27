"""Écriture atomique de la politique et du rapport 3B.5.2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_long_run_policy.constants import (
    POLICY_ARTIFACT_NAME,
    REPORT_NAME,
    SCHEMA_VERSION,
)

__all__ = [
    "POLICY_ARTIFACT_NAME",
    "REPORT_NAME",
    "policy_path",
    "report_path",
    "write_bytes_atomic",
]


def policy_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / POLICY_ARTIFACT_NAME


def report_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / REPORT_NAME


def write_bytes_atomic(path: Path, payload: Mapping[str, Any] | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        content = payload if payload.endswith("\n") else payload + "\n"
    else:
        content = json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"
    encoded = content.encode("utf-8")
    partial = path.with_name(path.name + ".partial")
    try:
        partial.write_bytes(encoded)
        if partial.read_bytes() != encoded:
            raise ValueError(f"Octets partiels ≠ contenu canonique pour {path.name}.")
        if not isinstance(payload, str):
            loaded = json.loads(encoded.decode("utf-8"))
            if not isinstance(loaded, dict) or loaded.get("schema_version") != SCHEMA_VERSION:
                raise ValueError(f"Politique partielle invalide : {path.name}.")
            if loaded.get("network", {}).get("anthropic") != 0:
                raise ValueError("network.anthropic doit rester 0.")
            if loaded.get("execution", {}).get("provider_call_performed") is not False:
                raise ValueError("provider_call_performed doit rester false.")
            if loaded.get("execution", {}).get("execution_authorized") is not False:
                raise ValueError("execution_authorized doit rester false.")
            selected = loaded.get("selected_policy") or {}
            if selected.get("third_global_timeout_escalation_allowed") is not False:
                raise ValueError("third_global_timeout_escalation_allowed doit rester false.")
            if selected.get("status") == "AUTHORIZED_FOR_EXECUTION":
                raise ValueError("3B.5.2 ne peut pas autoriser l'exécution.")
        partial.replace(path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    leftover = path.with_name(path.name + ".partial")
    if leftover.exists():
        leftover.unlink()
    return path


def assert_no_production_source_map(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> None:
    path = source_map_path(project_name, sortie_dir=sortie_dir)
    if path.exists():
        raise RuntimeError(f"source_map de production présent : {path}")
