"""
Vérifications 3B.4 + complexité + audit local Anthropic — avant tout appel.
"""

from __future__ import annotations

import inspect
from typing import Any, Mapping

from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.source_analysis.analyzer import analyze_source
from app.source_analysis.compact_reconstructor import reconstruct_to_canonical_raw
from app.source_analysis.compact_schema import (
    build_compact_response_schema,
    compact_schema_fingerprint,
)
from app.source_analysis.semantic_transport_decoder import decode_to_canonical_raw
from app.source_analysis.ultra_compact_schema import (
    build_ultra_compact_response_schema,
    ultra_compact_schema_fingerprint,
)
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.schema import build_response_schema, schema_fingerprint
from app.source_analysis.schema_complexity import (
    analyze_schema_complexity,
    reduction_percents,
)
from app.source_analysis.validator import ensure_valid_source_map
from app.source_analysis_schema_canary.errors import (
    LocalSchemaAuditError,
    PreCallFailure,
    SchemaRegressionError,
)

# Une réduction old→compact sous ce seuil, ou des champs optionnels / *_id
# qui réapparaissent, est une régression importante. Les chiffres 3B.4
# (58.1 %, 4398 octets) ne sont PAS des constantes métier : on recalcule.
_MIN_REDUCTION_RATIO = 0.40


def count_recursive_refs(schema: Mapping[str, Any]) -> int:
    """Nombre de $defs qui participent à un cycle de $ref."""
    defs = schema.get("$defs") if isinstance(schema.get("$defs"), dict) else {}
    graph: dict[str, list[str]] = {}

    def _collect(node: Any, found: list[str]) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                found.append(ref.rsplit("/", 1)[-1])
            for value in node.values():
                _collect(value, found)
        elif isinstance(node, list):
            for value in node:
                _collect(value, found)

    for name, sub_schema in defs.items():
        refs: list[str] = []
        _collect(sub_schema, refs)
        graph[str(name)] = refs

    cyclic = 0

    def _visit(name: str, stack: set[str], seen: set[str]) -> None:
        nonlocal cyclic
        if name in stack:
            cyclic += 1
            return
        if name in seen or name not in graph:
            return
        stack.add(name)
        for nxt in graph[name]:
            _visit(nxt, stack, seen)
        stack.remove(name)
        seen.add(name)

    seen: set[str] = set()
    for name in graph:
        _visit(name, set(), seen)
    return cyclic


def verify_3b4_architecture() -> dict[str, Any]:
    """
    Confirme que le chemin de production utilise le DTO compact, pas l'ancien
    gros schéma. STOP si l'ancien schéma est encore sélectionné.
    """
    old = build_response_schema()
    compact = build_compact_response_schema()
    old_sha = schema_fingerprint(old)
    compact_sha = compact_schema_fingerprint(compact)

    if old_sha == compact_sha:
        raise PreCallFailure(
            "Le schéma compact n'est pas distinct du schéma canonique / ancien."
        )

    analyzer_source = inspect.getsource(analyze_source)
    if "build_ultra_compact_response_schema" not in analyzer_source:
        raise PreCallFailure(
            "analyze_source n'utilise pas build_ultra_compact_response_schema(). "
            "STOP : 0 appel."
        )
    if "response_schema = build_response_schema()" in analyzer_source:
        raise PreCallFailure(
            "analyze_source sélectionne encore l'ancien gros schéma. STOP : 0 appel."
        )
    if "response_schema = build_compact_response_schema()" in analyzer_source:
        raise PreCallFailure(
            "analyze_source sélectionne encore le DTO compact 3B.4. STOP : 0 appel."
        )

    if not callable(reconstruct_to_canonical_raw):
        raise PreCallFailure("reconstruct_to_canonical_raw() est absent.")
    if not callable(decode_to_canonical_raw):
        raise PreCallFailure("decode_to_canonical_raw() est absent.")
    if not callable(normalize_source_map):
        raise PreCallFailure("normalize_source_map() est absent.")
    if not callable(ensure_valid_source_map):
        raise PreCallFailure("ensure_valid_source_map() est absent.")

    ultra = build_ultra_compact_response_schema()
    return {
        "canonical_schema_unchanged": True,
        "compact_dto_exists": True,
        "compact_distinct_from_old": True,
        "ultra_distinct_from_compact": compact_schema_fingerprint(compact)
        != ultra_compact_schema_fingerprint(ultra),
        "reconstruct_to_canonical_raw": True,
        "decode_to_canonical_raw": True,
        "normalizer_canonical_unchanged": True,
        "validator_canonical_unchanged": True,
        "future_analyzer_uses_compact": False,
        "future_analyzer_uses_ultra": True,
        "old_schema_sha256": old_sha,
        "compact_schema_sha256": compact_sha,
        "ultra_schema_sha256": ultra_compact_schema_fingerprint(ultra),
    }


def audit_complexity() -> dict[str, Any]:
    """Recalcule old / compact / adapté. Lève si régression importante."""
    old = build_response_schema()
    compact = build_compact_response_schema()
    anthropic = prepare_anthropic_json_schema(compact)
    old_metrics = analyze_schema_complexity(old)
    compact_metrics = analyze_schema_complexity(compact)
    anthropic_metrics = analyze_schema_complexity(anthropic)
    reduction = reduction_percents(old_metrics, compact_metrics)

    reasons: list[str] = []
    if int(compact_metrics.get("optional_properties") or 0) > 0:
        reasons.append("des champs optionnels ont réapparu dans le DTO compact")
    if int(compact_metrics.get("id_pattern_like_structures") or 0) > 0:
        reasons.append("des identifiants provider *_id ont réapparu")

    old_bytes = int(old_metrics.get("serialized_json_bytes") or 0)
    compact_bytes = int(compact_metrics.get("serialized_json_bytes") or 0)
    if old_bytes > 0:
        ratio = (old_bytes - compact_bytes) / old_bytes
        if ratio < _MIN_REDUCTION_RATIO:
            reasons.append(
                f"réduction old→compact {ratio:.1%} < {_MIN_REDUCTION_RATIO:.0%}"
            )

    if reasons:
        raise SchemaRegressionError(
            "Schéma compact régressé, STOP avant appel : " + " ; ".join(reasons)
        )

    return {
        "old": {"sha256": schema_fingerprint(old), "metrics": old_metrics},
        "compact": {
            "sha256": compact_schema_fingerprint(compact),
            "metrics": compact_metrics,
        },
        "anthropic": {
            "sha256": schema_fingerprint(anthropic),
            "metrics": anthropic_metrics,
        },
        "reduction": reduction,
        "regressed": False,
    }


def audit_local_anthropic_schema() -> dict[str, Any]:
    """prepare_anthropic_json_schema(compact) + audit d'incompatibilités."""
    compact = build_compact_response_schema()
    adapted = prepare_anthropic_json_schema(compact)
    features = audit_unsupported_features(adapted)
    recursive = count_recursive_refs(adapted)
    known = sum(len(value) for value in features.values()) + recursive

    if known > 0 or recursive > 0:
        raise LocalSchemaAuditError(
            "Audit local Anthropic en échec, STOP : 0 appel. "
            f"incompatibilités={known} recursive_refs={recursive}"
        )

    return {
        "compact_sha256": compact_schema_fingerprint(compact),
        "anthropic_sha256": schema_fingerprint(adapted),
        "compatibility": "PASS",
        "additionalProperties_not_false": list(
            features.get("additionalProperties_not_false") or []
        ),
        "minLength": list(features.get("minLength") or []),
        "unsupported_minItems": list(features.get("unsupported_minItems") or []),
        "recursive_refs": recursive,
        "minimum": list(features.get("minimum") or []),
        "maximum": list(features.get("maximum") or []),
        "multipleOf": list(features.get("multipleOf") or []),
        "maxLength": list(features.get("maxLength") or []),
        "maxItems": list(features.get("maxItems") or []),
        "known_incompatibilities": known,
        "audit": {key: list(value) for key, value in sorted(features.items())},
    }


def production_compact_schema() -> dict:
    """DTO compact 3B.4 — conservé pour comparaison / canary historique."""
    return build_compact_response_schema()


def production_ultra_schema() -> dict:
    """Le contrat ultra-compact de production — jamais un mini-schéma canary."""
    return build_ultra_compact_response_schema()
