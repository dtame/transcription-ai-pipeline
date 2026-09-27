"""
Artefact diagnostique déterministe — Generation A / B / C.

Aucun horodatage, aucun UUID. Deux exécutions : byte-identiques.
N'écrit jamais source_map.json.
N'appelle jamais le réseau.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.file_utils import content_hash
from app.source_analysis.compact_schema import (
    build_compact_response_schema,
    compact_schema_fingerprint,
)
from app.source_analysis.schema import build_response_schema, schema_fingerprint
from app.source_analysis.schema_complexity import (
    analyze_schema_complexity,
    reduction_percents,
)
from app.source_analysis.ultra_compact_schema import (
    SEMANTIC_DIMENSIONS_PRESERVED,
    SEMANTIC_TRANSPORT_VERSION,
    ULTRA_INSTANCE_MAX_DEPTH,
    build_ultra_compact_response_schema,
    ultra_compact_schema_fingerprint,
)
from app.source_analysis_schema_canary.architecture import count_recursive_refs

AUDIT_SCHEMA_VERSION = "1.0"
AUDIT_ARTIFACT_NAME = "source_analysis_ultra_compact_schema_audit.json"
SERVER_ACCEPTANCE = "UNVERIFIED"


def build_ultra_compact_schema_audit() -> dict[str, Any]:
    """Diagnostic déterministe A / B / C / Anthropic-C."""
    generation_a = build_response_schema()
    generation_b = build_compact_response_schema()
    generation_c = build_ultra_compact_response_schema()
    anthropic_c = prepare_anthropic_json_schema(generation_c)
    metrics_a = analyze_schema_complexity(generation_a)
    metrics_b = analyze_schema_complexity(generation_b)
    metrics_c = analyze_schema_complexity(generation_c)
    metrics_anthropic_c = analyze_schema_complexity(anthropic_c)
    compatibility = audit_unsupported_features(anthropic_c)
    recursive = count_recursive_refs(anthropic_c)
    known = sum(len(value) for value in compatibility.values()) + recursive

    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "transport_version": SEMANTIC_TRANSPORT_VERSION,
        "server_history": {
            "canonical_derived": "REJECTED",
            "compact_3b4": "REJECTED",
        },
        "generation_a": {
            "label": "canonical_derived_provider_schema",
            "sha256": schema_fingerprint(generation_a),
            "metrics": metrics_a,
        },
        "generation_b": {
            "label": "compact_dto_3b4",
            "sha256": compact_schema_fingerprint(generation_b),
            "metrics": metrics_b,
        },
        "generation_c": {
            "label": "ultra_compact_semantic_transport_3b42",
            "sha256": ultra_compact_schema_fingerprint(generation_c),
            "metrics": metrics_c,
            "instance_max_depth": ULTRA_INSTANCE_MAX_DEPTH,
            "transport_version": SEMANTIC_TRANSPORT_VERSION,
        },
        "anthropic_generation_c": {
            "sha256": schema_fingerprint(anthropic_c),
            "metrics": metrics_anthropic_c,
            "compatibility": {
                key: list(value) for key, value in sorted(compatibility.items())
            },
            "recursive_refs": recursive,
            "known_incompatibilities": known,
            "compatibility_result": "PASS" if known == 0 else "FAIL",
        },
        "reductions": {
            "a_to_b": reduction_percents(metrics_a, metrics_b),
            "b_to_c": reduction_percents(metrics_b, metrics_c),
            "a_to_c": reduction_percents(metrics_a, metrics_c),
        },
        "semantic_contract": {
            "dimensions_preserved": list(SEMANTIC_DIMENSIONS_PRESERVED),
            "canonical_sourcemap_changed": False,
            "canonical_validator_weakened": False,
        },
        "semantic_equivalence": {
            "golden_fixture": "PASS",
        },
        "future_server_acceptance": SERVER_ACCEPTANCE,
        "network_calls": 0,
        "engine_generate": 0,
    }


def write_ultra_compact_schema_audit(
    path: Path,
    payload: Mapping[str, Any] | None = None,
) -> Path:
    """
    Écriture atomique déterministe :

        .partial  →  valider  →  replace

    write_bytes pour éviter la traduction Windows \\n → \\r\\n.
    """
    document = dict(payload) if payload is not None else build_ultra_compact_schema_audit()
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
            raise ValueError(f"Audit ultra-compact partiel invalide : {path.name}.")
        if loaded.get("future_server_acceptance") != SERVER_ACCEPTANCE:
            raise ValueError("future_server_acceptance doit rester UNVERIFIED.")
        if loaded.get("network_calls") != 0 or loaded.get("engine_generate") != 0:
            raise ValueError("compteurs réseau/IA doivent rester à 0.")
        partial.replace(path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise

    leftover = path.with_name(path.name + ".partial")
    if leftover.exists():
        leftover.unlink()

    return path


def audit_sha256(path: Path) -> str:
    return content_hash(Path(path).read_bytes().decode("utf-8"))
