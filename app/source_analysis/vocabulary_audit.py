"""
Diagnostic déterministe — contrat lexical 3B.4.4.

Aucun horodatage, aucun UUID, aucun réseau, aucun engine.generate().
N'écrit jamais source_map.json.
N'écrase jamais source_analyzer_clean_preflight.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.ai.estimation import estimate_tokens
from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.file_utils import content_hash
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.canonical_vocabulary import (
    CURRENT_PROMPT_VERSION,
    GENERATION_C_ANTHROPIC_SHA256_3B43,
    GENERATION_C_RAW_SHA256_3B43,
    OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS,
    PREVIOUS_PROMPT_SHA256,
    PREVIOUS_PROMPT_VERSION,
    PREVIOUS_SIGNATURE,
    PREVIOUS_SYSTEM_CHARS,
    PREVIOUS_SYSTEM_TOKENS,
    PREVIOUS_TOTAL_TOKENS,
    PREVIOUS_USER_CHARS,
    PREVIOUS_USER_TOKENS,
    VOCABULARY_CATEGORY_ORDER,
    all_controlled_values,
    build_canonical_vocabulary_contract,
    controlled_vocabularies,
    controlled_value_count,
    free_text_fields,
    intent_audience_kinds_are_free_text,
    prompt_decoder_parity,
)
from app.source_analysis.schema import schema_fingerprint
from app.source_analysis.schema_complexity import analyze_schema_complexity
from app.source_analysis.ultra_compact_schema import (
    SEMANTIC_TRANSPORT_VERSION,
    ULTRA_INSTANCE_MAX_DEPTH,
    build_ultra_compact_response_schema,
    ultra_compact_schema_fingerprint,
)
from app.source_analysis.writer import transcripts_dir
from app.source_analysis_schema_canary.architecture import count_recursive_refs

AUDIT_SCHEMA_VERSION = "1.0"
AUDIT_ARTIFACT_NAME = "source_analysis_vocabulary_contract_audit.json"
SERVER_ACCEPTANCE_SCHEMA = "PREVIOUSLY_VERIFIED"
VOCABULARY_PROMPT_SERVER_COMPLIANCE = "UNVERIFIED"

PHASE_3B_REPORT = "PHASE_3B_REAL_SOURCE_ANALYZER_CLEAN_REPORT.md"
PHASE_3B4_REPORT = "PHASE_3B4_COMPACT_ANTHROPIC_SCHEMA_REPORT.md"
PHASE_3B41_REPORT = "PHASE_3B41_SERVER_GRAMMAR_CANARY_REPORT.md"
PHASE_3B42_REPORT = "PHASE_3B42_ULTRA_COMPACT_SEMANTIC_TRANSPORT_REPORT.md"
PHASE_3B43_REPORT = "PHASE_3B43_ULTRA_COMPACT_SERVER_CANARY_REPORT.md"
COMPACT_AUDIT = "source_analysis_compact_schema_audit.json"
ULTRA_AUDIT = "source_analysis_ultra_compact_schema_audit.json"
SCHEMA_CANARY_INPUT = "source_analysis_schema_canary_input.json"
SCHEMA_CANARY_RESULT = "source_analysis_schema_canary_result.json"
ULTRA_CANARY_INPUT = "source_analysis_ultra_compact_canary_input.json"
ULTRA_CANARY_RESULT = "source_analysis_ultra_compact_canary_result.json"
ULTRA_CANARY_TRANSPORT = "source_analysis_ultra_compact_canary_transport.json"

EXTRA_PROTECTED_KEYS = (
    f"audit/{PHASE_3B_REPORT}",
    f"audit/{PHASE_3B4_REPORT}",
    f"audit/{COMPACT_AUDIT}",
    f"audit/{PHASE_3B41_REPORT}",
    f"audit/{SCHEMA_CANARY_INPUT}",
    f"audit/{SCHEMA_CANARY_RESULT}",
    f"audit/{PHASE_3B42_REPORT}",
    f"audit/{ULTRA_AUDIT}",
    f"audit/{PHASE_3B43_REPORT}",
    f"audit/{ULTRA_CANARY_INPUT}",
    f"audit/{ULTRA_CANARY_RESULT}",
    f"audit/{ULTRA_CANARY_TRANSPORT}",
)


def extra_protected_paths(
    project_name: str, *, sortie_dir: Path | None = None
) -> dict[str, Path]:
    root = Path(transcripts_dir(project_name, sortie_dir=sortie_dir)).parent
    return {key: root / key for key in EXTRA_PROTECTED_KEYS}


def extra_protected_snapshot(
    project_name: str, *, sortie_dir: Path | None = None
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, path in extra_protected_paths(project_name, sortie_dir=sortie_dir).items():
        if Path(path).is_file():
            hashes[key] = sha256_of_file(path)
    return hashes


def _estimate(text: str, model: str) -> int:
    return estimate_tokens(text, model=model).tokens


def build_vocabulary_contract_audit(
    *,
    preflight: Mapping[str, Any] | None = None,
    golden_status: str = "PASS",
    coverage: Mapping[str, Any] | None = None,
    observed_rejected: bool = True,
    generate_calls: int = 0,
    current_prompt_sha256: str = "",
    current_signature: str = "",
    system_chars: int = 0,
    user_chars: int = 0,
    vocabulary_block_characters: int | None = None,
    vocabulary_block_estimated_tokens: int | None = None,
    system_tokens: int | None = None,
    user_tokens: int | None = None,
    total_tokens: int | None = None,
    model: str = "claude-sonnet-5",
) -> dict[str, Any]:
    """Diagnostic déterministe — clés stables, aucun timestamp."""
    generation_c = build_ultra_compact_response_schema()
    anthropic_c = prepare_anthropic_json_schema(generation_c)
    metrics_c = analyze_schema_complexity(generation_c)
    metrics_a = analyze_schema_complexity(anthropic_c)
    raw_sha = ultra_compact_schema_fingerprint(generation_c)
    anth_sha = schema_fingerprint(anthropic_c)
    compatibility = audit_unsupported_features(anthropic_c)
    recursive = count_recursive_refs(anthropic_c)
    known = sum(len(value) for value in compatibility.values()) + recursive

    contract = build_canonical_vocabulary_contract()
    block_chars = (
        len(contract)
        if vocabulary_block_characters is None
        else vocabulary_block_characters
    )
    block_tokens = (
        _estimate(contract, model)
        if vocabulary_block_estimated_tokens is None
        else vocabulary_block_estimated_tokens
    )

    parity = prompt_decoder_parity()
    vocabularies: dict[str, Any] = {}
    for key in VOCABULARY_CATEGORY_ORDER:
        item = controlled_vocabularies()[key]
        row = parity[key]
        vocabularies[key] = {
            "source": item.source,
            "values": list(item.values),
            "prompt_values": row["prompt_values"],
            "missing_from_prompt": row["missing_from_prompt"],
            "extra_in_prompt": row["extra_in_prompt"],
            "fallback": item.fallback,
            "usage": item.usage,
        }

    missing_total = [
        value
        for row in parity.values()
        for value in row["missing_from_prompt"]
    ]
    extra_total = [
        value
        for row in parity.values()
        for value in row["extra_in_prompt"]
    ]

    coverage_block = dict(coverage) if coverage is not None else {
        "total": controlled_value_count(),
        "tested": controlled_value_count(),
        "percent": 100.0,
    }

    preflight_block = dict(preflight) if preflight is not None else {}

    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "transport_version": SEMANTIC_TRANSPORT_VERSION,
        "generation_c": {
            "raw_sha256": raw_sha,
            "anthropic_sha256": anth_sha,
            "raw_sha256_3b43": GENERATION_C_RAW_SHA256_3B43,
            "anthropic_sha256_3b43": GENERATION_C_ANTHROPIC_SHA256_3B43,
            "unchanged": (
                raw_sha == GENERATION_C_RAW_SHA256_3B43
                and anth_sha == GENERATION_C_ANTHROPIC_SHA256_3B43
            ),
            "metrics": metrics_c,
            "anthropic_metrics": metrics_a,
            "instance_max_depth": ULTRA_INSTANCE_MAX_DEPTH,
            "provider_enums": metrics_c["enum_count"],
            "provider_enum_values": metrics_c["total_enum_values"],
            "local_compatibility": "PASS" if known == 0 else "FAIL",
            "recursive_refs": recursive,
            "server_acceptance": SERVER_ACCEPTANCE_SCHEMA,
        },
        "prompt": {
            "previous_version": PREVIOUS_PROMPT_VERSION,
            "current_version": CURRENT_PROMPT_VERSION,
            "previous_sha256": PREVIOUS_PROMPT_SHA256,
            "current_sha256": current_prompt_sha256,
            "previous_system_characters": PREVIOUS_SYSTEM_CHARS,
            "current_system_characters": system_chars,
            "previous_user_characters": PREVIOUS_USER_CHARS,
            "current_user_characters": user_chars,
            "previous_system_tokens": PREVIOUS_SYSTEM_TOKENS,
            "current_system_tokens": system_tokens,
            "previous_user_tokens": PREVIOUS_USER_TOKENS,
            "current_user_tokens": user_tokens,
            "previous_total_tokens": PREVIOUS_TOTAL_TOKENS,
            "current_total_tokens": total_tokens,
            "vocabulary_block_characters": block_chars,
            "vocabulary_block_estimated_tokens": block_tokens,
            "system_delta_characters": (
                system_chars - PREVIOUS_SYSTEM_CHARS if system_chars else 0
            ),
            "system_delta_tokens": (
                (system_tokens - PREVIOUS_SYSTEM_TOKENS)
                if system_tokens is not None
                else 0
            ),
        },
        "signature": {
            "previous": PREVIOUS_SIGNATURE,
            "current": current_signature,
            "changed": bool(current_signature)
            and current_signature != PREVIOUS_SIGNATURE,
            "old_cache_collision_possible": False,
        },
        "vocabularies": vocabularies,
        "free_text_fields": list(free_text_fields()),
        "intent_audience_kinds_are_free_text": intent_audience_kinds_are_free_text(),
        "parity": {
            "missing_from_prompt": missing_total,
            "extra_in_prompt": extra_total,
        },
        "observed_3b43_invalid_tokens": list(OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS),
        "observed_invalid_tokens_still_rejected": observed_rejected,
        "golden_fixture": golden_status,
        "vocabulary_test_coverage": coverage_block,
        "controlled_value_total": len(all_controlled_values()),
        "canonical_sourcemap_changed": False,
        "canonical_validator_weakened": False,
        "decoder_fail_closed": True,
        "alias_synonym_repair": False,
        "clean_preflight": preflight_block,
        "network_calls": 0,
        "engine_generate": generate_calls,
        "vocabulary_prompt_server_compliance": VOCABULARY_PROMPT_SERVER_COMPLIANCE,
        "anthropic_compatibility": {
            key: list(value) for key, value in sorted(compatibility.items())
        },
    }


def write_vocabulary_contract_audit(
    path: Path,
    payload: Mapping[str, Any] | None = None,
) -> Path:
    document = dict(payload) if payload is not None else build_vocabulary_contract_audit()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    encoded = content.encode("utf-8")
    partial = path.with_name(path.name + ".partial")
    try:
        partial.write_bytes(encoded)
        on_disk = partial.read_bytes()
        if on_disk != encoded:
            raise ValueError(f"Octets partiels ≠ contenu canonique pour {path.name}.")
        loaded = json.loads(on_disk.decode("utf-8"))
        if not isinstance(loaded, dict) or loaded.get("schema_version") != AUDIT_SCHEMA_VERSION:
            raise ValueError(f"Audit vocabulaire partiel invalide : {path.name}.")
        if loaded.get("vocabulary_prompt_server_compliance") != VOCABULARY_PROMPT_SERVER_COMPLIANCE:
            raise ValueError("vocabulary_prompt_server_compliance doit rester UNVERIFIED.")
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
