"""
Artefact diagnostique déterministe — complexité old vs compact.

Aucun horodatage, aucun UUID. Deux exécutions : byte-identiques.
N'écrit jamais source_map.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.source_analysis.compact_schema import (
    SEMANTIC_DIMENSIONS_PRESERVED,
    build_compact_response_schema,
    compact_schema_fingerprint,
)
from app.source_analysis.schema import build_response_schema, schema_fingerprint
from app.source_analysis.schema_complexity import (
    analyze_schema_complexity,
    reduction_percents,
)

AUDIT_SCHEMA_VERSION = "1.0"
AUDIT_ARTIFACT_NAME = "source_analysis_compact_schema_audit.json"
SERVER_ACCEPTANCE = "UNVERIFIED"


def build_compact_schema_audit() -> dict[str, Any]:
    """Diagnostic déterministe old / compact / anthropic-adapted."""
    old = build_response_schema()
    compact = build_compact_response_schema()
    anthropic = prepare_anthropic_json_schema(compact)
    old_metrics = analyze_schema_complexity(old)
    compact_metrics = analyze_schema_complexity(compact)
    anthropic_metrics = analyze_schema_complexity(anthropic)
    audit = audit_unsupported_features(anthropic)

    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "old_schema": {
            "sha256": schema_fingerprint(old),
            "metrics": old_metrics,
        },
        "compact_schema": {
            "sha256": compact_schema_fingerprint(compact),
            "metrics": compact_metrics,
        },
        "anthropic_compact_schema": {
            "sha256": schema_fingerprint(anthropic),
            "metrics": anthropic_metrics,
            "compatibility_audit": {
                key: list(value) for key, value in sorted(audit.items())
            },
        },
        "reduction": {
            "old_to_compact": reduction_percents(old_metrics, compact_metrics),
            "old_to_anthropic_compact": reduction_percents(
                old_metrics, anthropic_metrics
            ),
        },
        "semantic_contract": {
            "dimensions_preserved": list(SEMANTIC_DIMENSIONS_PRESERVED),
        },
        "server_acceptance": SERVER_ACCEPTANCE,
    }


def write_compact_schema_audit(
    path: Path,
    payload: Mapping[str, Any] | None = None,
) -> Path:
    """
    Écriture atomique déterministe :

        .partial  →  valider  →  replace

    write_bytes pour éviter la traduction Windows \\n → \\r\\n.
    """
    document = dict(payload) if payload is not None else build_compact_schema_audit()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    encoded = content.encode("utf-8")
    partial = path.with_name(path.name + ".partial")

    try:
        partial.write_bytes(encoded)
        on_disk = partial.read_bytes()
        if on_disk != encoded:
            raise ValueError(
                f"Octets partiels ≠ contenu canonique pour {path.name}."
            )
        loaded = json.loads(on_disk.decode("utf-8"))
        if not isinstance(loaded, dict) or loaded.get("schema_version") != AUDIT_SCHEMA_VERSION:
            raise ValueError(f"Audit compact partiel invalide : {path.name}.")
        if loaded.get("server_acceptance") != SERVER_ACCEPTANCE:
            raise ValueError("server_acceptance doit rester UNVERIFIED.")
        partial.replace(path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise

    leftover = path.with_name(path.name + ".partial")
    if leftover.exists():
        leftover.unlink()

    return path
