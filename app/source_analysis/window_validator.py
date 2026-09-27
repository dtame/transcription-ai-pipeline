"""
Validation fail-closed d'une fenêtre.

Réutilise le decoder existant (vocabulaire, liens, kinds, fuite éditoriale).
Ajoute : domaine SRC de la fenêtre, membership réelle, ownership owned/context.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.errors import (
    SourceMapEditorialLeakError,
    SourceMapValidationError,
    WindowResultValidationError,
    WindowSourceRefError,
    WindowTransportValidationError,
)
from app.source_analysis.models import forbidden_editorial_fields
from app.source_analysis.semantic_transport_decoder import decode_to_canonical_raw
from app.source_analysis.ultra_compact_schema import SEMANTIC_TRANSPORT_VERSION
from app.source_analysis.window_models import (
    CONTEXT_ONLY_SUBSTANTIVE_FORBIDDEN,
    MIXED_OWNED_CONTEXT_ALLOWED,
    OWNERSHIP_RULE,
    SUBSTANTIVE_RECORD_KINDS,
    WINDOW_CANDIDATE_SCOPE,
    WINDOW_RESULT_SCHEMA_VERSION,
    WindowSemanticResult,
    allowed_window_source_refs,
    assert_intermediate_record_id,
    assert_safe_window_id,
    owned_source_refs,
)
from app.source_analysis.window_granularity import (
    validate_window_result_granularity,
)
from app.source_analysis.window_prompt import KNOWN_WINDOW_PROMPT_VERSIONS
from app.source_analysis_hybrid.contracts import WindowInput


def validate_window_source_refs(
    transport: Mapping[str, Any],
    window: WindowInput,
) -> None:
    """
    Membership réelle uniquement.

    Un SRC numériquement entre first/last mais absent de owned∪context
    (supprimé, gap) est rejeté. first/last ne sont jamais expansés.
    """
    allowed = allowed_window_source_refs(window)
    owned = owned_source_refs(window)
    records = transport.get("records")
    if not isinstance(records, list):
        return
    errors: list[str] = []
    for index, item in enumerate(records):
        if not isinstance(item, Mapping):
            continue
        refs = item.get("s") or []
        if not isinstance(refs, list):
            continue
        kind = str(item.get("k") or "")
        present = [str(ref).strip() for ref in refs if isinstance(ref, str)]
        unknown = [ref for ref in present if ref not in allowed]
        if unknown:
            errors.append(
                f"records[{index}] : source_ref hors fenêtre {unknown}"
            )
            continue
        if kind in SUBSTANTIVE_RECORD_KINDS:
            if not present:
                errors.append(
                    f"records[{index}] : record substantif {kind} sans source_ref"
                )
                continue
            if not any(ref in owned for ref in present):
                errors.append(
                    f"records[{index}] : {kind} fondé uniquement sur CONTEXT-ONLY "
                    f"{present} — interdit ({OWNERSHIP_RULE})"
                )
    if errors:
        raise WindowSourceRefError(" | ".join(errors))


def decode_window_transport(
    transport: Mapping[str, Any],
    window: WindowInput,
) -> dict:
    """Decoder fail-closed existant, domaine SRC = owned ∪ context."""
    try:
        leaked = forbidden_editorial_fields(transport)
        if leaked:
            raise SourceMapEditorialLeakError(leaked, location="window transport")
        raw = decode_to_canonical_raw(
            transport,
            allowed_source_refs=set(allowed_window_source_refs(window)),
        )
    except SourceMapEditorialLeakError:
        raise
    except SourceMapValidationError as exc:
        raise WindowTransportValidationError(str(exc)) from exc
    except WindowTransportValidationError:
        raise
    validate_window_source_refs(transport, window)
    return raw


def validate_window_result(
    result: WindowSemanticResult,
    window: WindowInput,
) -> None:
    errors: list[str] = []
    try:
        assert_safe_window_id(result.window_id)
    except Exception as exc:
        errors.append(str(exc))
    if result.window_id != window.window_id:
        errors.append(
            f"window_id résultat {result.window_id!r} ≠ entrée {window.window_id!r}"
        )
    if result.window_input_hash != window.input_hash:
        errors.append("window_input_hash ≠ WindowInput.input_hash")
    if result.prompt_version not in KNOWN_WINDOW_PROMPT_VERSIONS:
        errors.append(
            f"prompt_version {result.prompt_version!r} hors "
            f"{sorted(KNOWN_WINDOW_PROMPT_VERSIONS)}"
        )
    if result.transport_version != SEMANTIC_TRANSPORT_VERSION:
        errors.append(
            f"transport_version {result.transport_version!r} ≠ {SEMANTIC_TRANSPORT_VERSION}"
        )
    if result.schema_version != WINDOW_RESULT_SCHEMA_VERSION:
        errors.append(f"schema_version inattendue : {result.schema_version!r}")
    if result.planner_version != window.planner_version:
        errors.append("planner_version ≠ WindowInput")
    if tuple(result.owned_src_refs) != tuple(window.owned_src_refs):
        errors.append("owned_src_refs ≠ WindowInput")
    if tuple(result.context_src_refs) != tuple(window.context_src_refs):
        errors.append("context_src_refs ≠ WindowInput")
    if result.candidates.scope != WINDOW_CANDIDATE_SCOPE:
        errors.append("candidates.scope doit être WINDOW_CANDIDATE_ONLY")
    if result.candidates.to_dict().get("global_decision") is not False:
        errors.append("candidates ne doivent pas être une décision globale")

    leaked = forbidden_editorial_fields(result.to_dict())
    if leaked:
        errors.append(f"fuite éditoriale dans le résultat : {leaked}")

    seen: set[str] = set()
    allowed = allowed_window_source_refs(window)
    owned = owned_source_refs(window)
    for record in result.records:
        try:
            assert_intermediate_record_id(record.record_id, window_id=result.window_id)
        except Exception as exc:
            errors.append(str(exc))
        if record.record_id in seen:
            errors.append(f"identifiant intermédiaire dupliqué : {record.record_id}")
        seen.add(record.record_id)
        unknown = [ref for ref in record.source_refs if ref not in allowed]
        if unknown:
            errors.append(f"{record.record_id} : SRC hors fenêtre {unknown}")
        if record.kind in SUBSTANTIVE_RECORD_KINDS:
            if not any(ref in owned for ref in record.source_refs):
                errors.append(
                    f"{record.record_id} : {record.kind} sans SRC owned "
                    f"(context-only interdit)"
                )
        for link in record.links:
            if link < 0 or link >= len(result.records):
                errors.append(f"{record.record_id} : lien {link} hors plage")

    if result.stats.record_count != len(result.records):
        errors.append("stats.record_count incohérent")
    if result.coverage.owned_src_count != len(window.owned_src_refs):
        errors.append("coverage.owned_src_count incohérent")
    if result.coverage.context_src_count != len(window.context_src_refs):
        errors.append("coverage.context_src_count incohérent")
    cited_owned = set(result.coverage.owned_src_cited)
    expected_cited = {
        ref
        for record in result.records
        for ref in record.source_refs
        if ref in owned
    }
    if cited_owned != expected_cited:
        errors.append("coverage owned cités incohérents avec les records")

    payload = result.to_dict()
    for forbidden in (
        "chapters",
        "sections",
        "book_title",
        "book_subtitle",
        "editorial_plan",
        "source_map",
    ):
        if forbidden in payload:
            errors.append(f"fuite éditoriale : champ {forbidden}")

    if errors:
        raise WindowResultValidationError(" | ".join(errors))
    validate_window_result_granularity(result)


def ownership_policy() -> dict[str, Any]:
    return {
        "rule": OWNERSHIP_RULE,
        "mixed_owned_context_allowed": MIXED_OWNED_CONTEXT_ALLOWED,
        "context_only_substantive_forbidden": CONTEXT_ONLY_SUBSTANTIVE_FORBIDDEN,
        "substantive_kinds": sorted(SUBSTANTIVE_RECORD_KINDS),
        "deleted_src_membership_only": True,
        "numeric_range_insufficient": True,
    }


__all__ = [
    "decode_window_transport",
    "ownership_policy",
    "validate_window_result",
    "validate_window_source_refs",
]
