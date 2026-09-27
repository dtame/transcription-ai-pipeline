"""
Validateur fail-closed du ConsolidationSemanticResult.

Le decoder a déjà rejeté le transport invalide. Ce module vérifie
l'identité, le grounding, la comptabilité et l'absence de SourceMap.
"""

from __future__ import annotations

from app.source_analysis.consolidation_models import (
    CATEGORY_C_METADATA_EVIDENCE,
    CONSOLIDATION_PROMPT_VERSION,
    CONSOLIDATION_RESULT_SCHEMA_VERSION,
    CONSOLIDATION_TRANSPORT_VERSION,
    ConsolidationInput,
    ConsolidationSemanticResult,
    requires_exclusive_disposition,
)
from app.source_analysis.errors import (
    ConsolidationResultValidationError,
    SourceMapEditorialLeakError,
)
from app.source_analysis.models import (
    RELATION_KINDS,
    REPETITION_CHARACTERS,
    forbidden_editorial_fields,
)
from app.source_analysis_hybrid.contracts import WINDOW_RECORD_ID_PATTERN


def validate_consolidation_result(
    result: ConsolidationSemanticResult,
    consolidation_input: ConsolidationInput,
    *,
    allowed_record_id_pattern=WINDOW_RECORD_ID_PATTERN,
) -> None:
    errors: list[str] = []
    if result.schema_version != CONSOLIDATION_RESULT_SCHEMA_VERSION:
        errors.append(f"schema_version inattendue : {result.schema_version!r}")
    if result.input_hash != consolidation_input.input_hash:
        errors.append("input_hash ≠ ConsolidationInput")
    if result.prompt_version != CONSOLIDATION_PROMPT_VERSION:
        errors.append(
            f"prompt_version {result.prompt_version!r} ≠ {CONSOLIDATION_PROMPT_VERSION}"
        )
    if result.transport_version != CONSOLIDATION_TRANSPORT_VERSION:
        errors.append(
            f"transport_version {result.transport_version!r} ≠ "
            f"{CONSOLIDATION_TRANSPORT_VERSION}"
        )
    if result.to_dict().get("canonical_sourcemap") is not False:
        errors.append("ConsolidationSemanticResult ne doit pas être un SourceMap")

    leaked = forbidden_editorial_fields(result.to_dict())
    if leaked:
        raise SourceMapEditorialLeakError(leaked, location="consolidation result")

    records = consolidation_input.record_by_id()
    allowed_src = consolidation_input.allowed_source_refs()
    node_ids = {node.node_id for node in result.nodes}
    member_seen: dict[str, str] = {}

    for node in result.nodes:
        if node.operation not in {"KEEP_RECORD", "MERGE_RECORDS"}:
            errors.append(f"{node.node_id} : opération {node.operation!r}")
        if node.operation == "KEEP_RECORD" and len(node.member_ids) != 1:
            errors.append(f"{node.node_id} : KEEP doit citer exactement 1 record")
        if node.operation == "MERGE_RECORDS" and len(node.member_ids) < 2:
            errors.append(f"{node.node_id} : MERGE singleton")
        if len(node.member_ids) != len(set(node.member_ids)):
            errors.append(f"{node.node_id} : membre dupliqué")
        kinds: list[str] = []
        for member in node.member_ids:
            if member not in records:
                errors.append(f"{node.node_id} : membre inconnu {member}")
                continue
            if not allowed_record_id_pattern.fullmatch(member):
                errors.append(f"{node.node_id} : ID intermédiaire invalide {member}")
            if member in member_seen:
                errors.append(
                    f"disposition multiple pour {member} : "
                    f"{member_seen[member]} et {node.node_id}"
                )
            member_seen[member] = node.node_id
            kinds.append(records[member].kind)
        if kinds and len(set(kinds)) != 1:
            errors.append(f"{node.node_id} : kinds incompatibles {kinds}")
        if node.operation == "MERGE_RECORDS" and not node.value.strip():
            errors.append(f"{node.node_id} : texte fusionné vide")
        unknown_src = [ref for ref in node.source_refs if ref not in allowed_src]
        if unknown_src:
            errors.append(f"{node.node_id} : SRC non fournis par l'input {unknown_src}")
        if node.canonical_id if hasattr(node, "canonical_id") else None:
            errors.append(f"{node.node_id} : ID canonique interdit")

    metadata = result.global_metadata
    for field in (
        "main_theme",
        "author_intent",
        "target_audience",
        "author_voice_profile",
    ):
        if not str(getattr(metadata, field) or "").strip():
            errors.append(f"GLOBAL_METADATA.{field} vide")
    for label, refs in (
        ("theme_evidence", metadata.theme_evidence),
        ("intent_evidence", metadata.intent_evidence),
        ("audience_evidence", metadata.audience_evidence),
        ("voice_evidence", metadata.voice_evidence),
    ):
        if not refs:
            errors.append(f"GLOBAL_METADATA.{label} vide")
        for ref in refs:
            if ref not in records:
                errors.append(f"GLOBAL_METADATA.{label} : {ref} inconnu")

    metadata_evidence = set(
        metadata.theme_evidence
        + metadata.intent_evidence
        + metadata.audience_evidence
        + metadata.voice_evidence
    )

    for record in consolidation_input.all_records():
        if requires_exclusive_disposition(record.kind):
            if record.record_id not in member_seen:
                errors.append(f"record non comptabilisé : {record.record_id}")
        elif record.kind in CATEGORY_C_METADATA_EVIDENCE:
            if (
                record.record_id not in member_seen
                and record.record_id not in metadata_evidence
            ):
                errors.append(
                    f"évidence métadonnée non comptabilisée : {record.record_id}"
                )

    for relation in result.relations:
        if relation.relation_type not in RELATION_KINDS:
            errors.append(f"relation inconnue : {relation.relation_type!r}")
        if relation.left_node_id not in node_ids:
            errors.append(f"relation left {relation.left_node_id} inconnu")
        if relation.right_node_id not in node_ids:
            errors.append(f"relation right {relation.right_node_id} inconnu")
        for ref in (relation.left_ref, relation.right_ref):
            if ref not in records and ref not in node_ids:
                errors.append(f"relation ref inconnue : {ref}")

    for repetition in result.repetitions:
        if repetition.character not in REPETITION_CHARACTERS:
            errors.append(f"répétition inconnue : {repetition.character!r}")
        if len(repetition.member_ids) < 2:
            errors.append("REPETITION sans 2 membres")
        for ref in repetition.member_ids:
            if ref not in records:
                errors.append(f"REPETITION membre inconnu : {ref}")
        for node_id in repetition.node_ids:
            if node_id not in node_ids:
                errors.append(f"REPETITION nœud inconnu : {node_id}")

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
        raise ConsolidationResultValidationError(" | ".join(errors))


__all__ = ["validate_consolidation_result"]
