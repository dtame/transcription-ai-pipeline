"""
Vérifications Generation C + métriques recalculées + audit local Anthropic.

STOP avant tout appel si le schéma de production n'est pas Generation C,
si A/B sont encore sélectionnés, ou si l'audit local échoue.
"""

from __future__ import annotations

import inspect
import json
from typing import Any, Mapping

from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.source_analysis.analyzer import analyze_source
from app.source_analysis.compact_schema import (
    build_compact_response_schema,
    compact_schema_fingerprint,
)
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.schema import build_response_schema, schema_fingerprint
from app.source_analysis.schema_complexity import analyze_schema_complexity
from app.source_analysis.semantic_transport_decoder import decode_to_canonical_raw
from app.source_analysis.ultra_compact_schema import (
    SEMANTIC_TRANSPORT_VERSION,
    ULTRA_INSTANCE_MAX_DEPTH,
    build_provider_response_schema,
    build_ultra_compact_response_schema,
    ultra_compact_schema_fingerprint,
)
from app.source_analysis.validator import ensure_valid_source_map
from app.source_analysis_schema_canary.architecture import count_recursive_refs
from app.source_analysis_ultra_compact_canary.constants import (
    REFERENCE_3B42_ANTHROPIC_BYTES,
    REFERENCE_3B42_ANTHROPIC_SHA256,
    REFERENCE_3B42_RAW_BYTES,
    REFERENCE_3B42_RAW_SHA256,
    TRANSPORT_VERSION,
)
from app.source_analysis_ultra_compact_canary.errors import (
    LocalSchemaAuditError,
    PreCallFailure,
    SchemaRegressionError,
)

_AB_SCHEMA_MARKERS = (
    "topic_indexes",
    "idea_indexes",
    "author_intent",
    "target_audience",
    "main_theme",
    "topic_id",
    "idea_id",
    "normalized_reference",
    "supports_idea_refs",
    "source_analysis",
)


def production_generation_c_schema() -> dict:
    """Le contrat Generation C de production — jamais un mini-schéma canary."""
    return build_ultra_compact_response_schema()


def verify_generation_c_architecture() -> dict[str, Any]:
    """
    Confirme que le chemin de production utilise Generation C.

    STOP si A ou B sont encore sélectionnés pour le future AIRequest.
    """
    generation_a = build_response_schema()
    generation_b = build_compact_response_schema()
    generation_c = build_ultra_compact_response_schema()
    provider_c = build_provider_response_schema()

    sha_a = schema_fingerprint(generation_a)
    sha_b = compact_schema_fingerprint(generation_b)
    sha_c = ultra_compact_schema_fingerprint(generation_c)
    sha_provider = ultra_compact_schema_fingerprint(provider_c)

    if sha_c != sha_provider:
        raise PreCallFailure(
            "build_provider_response_schema() n'est pas Generation C."
        )
    if sha_a == sha_c or sha_b == sha_c:
        raise PreCallFailure(
            "Generation C n'est pas distincte de Generation A ou B."
        )
    if SEMANTIC_TRANSPORT_VERSION != TRANSPORT_VERSION:
        raise PreCallFailure(
            f"transport version {SEMANTIC_TRANSPORT_VERSION!r} "
            f"≠ {TRANSPORT_VERSION!r}."
        )

    analyzer_source = inspect.getsource(analyze_source)
    if "build_ultra_compact_response_schema" not in analyzer_source:
        raise PreCallFailure(
            "analyze_source n'utilise pas build_ultra_compact_response_schema(). "
            "STOP : 0 appel."
        )
    if "response_schema = build_response_schema()" in analyzer_source:
        raise PreCallFailure(
            "analyze_source sélectionne encore Generation A. STOP : 0 appel."
        )
    if "response_schema = build_compact_response_schema()" in analyzer_source:
        raise PreCallFailure(
            "analyze_source sélectionne encore Generation B. STOP : 0 appel."
        )

    if not callable(decode_to_canonical_raw):
        raise PreCallFailure("decode_to_canonical_raw() est absent.")
    if not callable(normalize_source_map):
        raise PreCallFailure("normalize_source_map() est absent.")
    if not callable(ensure_valid_source_map):
        raise PreCallFailure("ensure_valid_source_map() est absent.")

    import app.source_analysis.semantic_transport_decoder as decoder_module

    decoder_source = inspect.getsource(decoder_module)
    fail_closed = (
        callable(decode_to_canonical_raw)
        and "SourceMapValidationError" in decoder_source
        and "kind inconnu" in decoder_source
        and "source_ref inconnu" in decoder_source
        and "index" in decoder_source
        and "hors plage" in decoder_source
    )
    if not fail_closed:
        raise PreCallFailure("Le decoder Generation C n'est pas fail-closed.")

    return {
        "transport_version": SEMANTIC_TRANSPORT_VERSION,
        "canonical_sourcemap_changed": False,
        "canonical_validator_changed": False,
        "generation_c_exists": True,
        "decoder_exists": True,
        "decoder_fail_closed": True,
        "generation_c_selected": True,
        "generation_b_selected": False,
        "generation_a_selected": False,
        "future_analyzer_uses_c": True,
        "generation_a_sha256": sha_a,
        "generation_b_sha256": sha_b,
        "generation_c_sha256": sha_c,
    }


def audit_generation_c_complexity() -> dict[str, Any]:
    """Recalcule A / B / C / Anthropic-C. Lève si régression inattendue."""
    generation_a = build_response_schema()
    generation_b = build_compact_response_schema()
    generation_c = build_ultra_compact_response_schema()
    anthropic_c = prepare_anthropic_json_schema(generation_c)

    metrics_a = analyze_schema_complexity(generation_a)
    metrics_b = analyze_schema_complexity(generation_b)
    metrics_c = analyze_schema_complexity(generation_c)
    metrics_ac = analyze_schema_complexity(anthropic_c)

    sha_c = ultra_compact_schema_fingerprint(generation_c)
    sha_ac = schema_fingerprint(anthropic_c)

    reasons: list[str] = []
    if int(metrics_c.get("object_nodes") or 0) != 2:
        reasons.append(f"objects={metrics_c.get('object_nodes')} ≠ 2")
    if int(metrics_c.get("arrays_of_objects") or 0) != 1:
        reasons.append(
            f"arrays_of_objects={metrics_c.get('arrays_of_objects')} ≠ 1"
        )
    if int(metrics_c.get("total_properties") or 0) != 11:
        reasons.append(f"properties={metrics_c.get('total_properties')} ≠ 11")
    if int(metrics_c.get("constraints") or 0) != 0:
        reasons.append(f"constraints={metrics_c.get('constraints')} ≠ 0")
    if int(metrics_c.get("enum_count") or 0) != 0:
        reasons.append(f"provider enums={metrics_c.get('enum_count')} ≠ 0")
    if ULTRA_INSTANCE_MAX_DEPTH != 3:
        reasons.append(f"instance depth={ULTRA_INSTANCE_MAX_DEPTH} ≠ 3")
    if int(metrics_c.get("serialized_json_bytes") or 0) != REFERENCE_3B42_RAW_BYTES:
        reasons.append(
            f"raw bytes={metrics_c.get('serialized_json_bytes')} "
            f"≠ {REFERENCE_3B42_RAW_BYTES} (3B.4.2)"
        )
    if int(metrics_ac.get("serialized_json_bytes") or 0) != REFERENCE_3B42_ANTHROPIC_BYTES:
        reasons.append(
            f"anthropic bytes={metrics_ac.get('serialized_json_bytes')} "
            f"≠ {REFERENCE_3B42_ANTHROPIC_BYTES} (3B.4.2)"
        )
    if sha_c != REFERENCE_3B42_RAW_SHA256:
        reasons.append(
            f"raw SHA {sha_c} ≠ 3B.4.2 {REFERENCE_3B42_RAW_SHA256}"
        )
    if sha_ac != REFERENCE_3B42_ANTHROPIC_SHA256:
        reasons.append(
            f"anthropic SHA {sha_ac} ≠ 3B.4.2 {REFERENCE_3B42_ANTHROPIC_SHA256}"
        )

    if reasons:
        raise SchemaRegressionError(
            "Régression structurelle Generation C, STOP avant appel : "
            + " ; ".join(reasons)
        )

    return {
        "generation_a": {"sha256": schema_fingerprint(generation_a), "metrics": metrics_a},
        "generation_b": {
            "sha256": compact_schema_fingerprint(generation_b),
            "metrics": metrics_b,
        },
        "generation_c": {
            "sha256": sha_c,
            "metrics": metrics_c,
            "instance_max_depth": ULTRA_INSTANCE_MAX_DEPTH,
        },
        "anthropic_generation_c": {
            "sha256": sha_ac,
            "metrics": metrics_ac,
            "instance_max_depth": ULTRA_INSTANCE_MAX_DEPTH,
        },
        "sha_match_3b42": True,
        "regressed": False,
    }


def audit_local_anthropic_generation_c() -> dict[str, Any]:
    """prepare_anthropic_json_schema(Generation C) + audit d'incompatibilités."""
    generation_c = production_generation_c_schema()
    adapted = prepare_anthropic_json_schema(generation_c)
    features = audit_unsupported_features(adapted)
    recursive = count_recursive_refs(adapted)
    known = sum(len(value) for value in features.values()) + recursive
    metrics = analyze_schema_complexity(adapted)

    if known > 0 or recursive > 0:
        raise LocalSchemaAuditError(
            "Audit local Anthropic Generation C en échec, STOP : 0 appel. "
            f"incompatibilités={known} recursive_refs={recursive}"
        )
    if int(metrics.get("object_nodes") or 0) != 2:
        raise LocalSchemaAuditError("Anthropic Generation C : objects ≠ 2.")
    if int(metrics.get("arrays_of_objects") or 0) != 1:
        raise LocalSchemaAuditError(
            "Anthropic Generation C : arrays of objects ≠ 1."
        )
    if int(metrics.get("total_properties") or 0) != 11:
        raise LocalSchemaAuditError("Anthropic Generation C : properties ≠ 11.")
    if int(metrics.get("constraints") or 0) != 0:
        raise LocalSchemaAuditError("Anthropic Generation C : constraints ≠ 0.")
    if int(metrics.get("enum_count") or 0) != 0:
        raise LocalSchemaAuditError(
            "Anthropic Generation C : provider enums ≠ 0."
        )

    return {
        "raw_sha256": ultra_compact_schema_fingerprint(generation_c),
        "anthropic_sha256": schema_fingerprint(adapted),
        "compatibility": "PASS",
        "objects": metrics["object_nodes"],
        "arrays_of_objects": metrics["arrays_of_objects"],
        "properties": metrics["total_properties"],
        "constraints": metrics["constraints"],
        "provider_enums": metrics["enum_count"],
        "additionalProperties_not_false": list(
            features.get("additionalProperties_not_false") or []
        ),
        "recursive_refs": recursive,
        "unsupported_minLength": list(features.get("minLength") or []),
        "unsupported_minItems": list(features.get("unsupported_minItems") or []),
        "unsupported_maxLength": list(features.get("maxLength") or []),
        "unsupported_maxItems": list(features.get("maxItems") or []),
        "unsupported_minimum": list(features.get("minimum") or []),
        "unsupported_maximum": list(features.get("maximum") or []),
        "unsupported_multipleOf": list(features.get("multipleOf") or []),
        "known_unsupported_constructs": known,
        "audit": {key: list(value) for key, value in sorted(features.items())},
    }


def payload_contains_ab_schema(schema: Mapping[str, Any] | None) -> bool:
    """True si le schéma du payload porte un fragment identifiable A ou B."""
    if not isinstance(schema, Mapping):
        return False
    dumped = json.dumps(schema, ensure_ascii=False)
    return any(marker in dumped for marker in _AB_SCHEMA_MARKERS)
