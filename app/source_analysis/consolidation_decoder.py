"""
Decoder fail-closed de consolidation-transport-v1.

Aucune réparation d'ID, aucune synonymie, aucun salvage JSON,
aucun merge automatique. Le provider ne fournit pas les IDs Cxxxx.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.consolidation_models import (
    CATEGORY_C_METADATA_EVIDENCE,
    CONSOLIDATION_RESULT_SCHEMA_VERSION,
    ConsolidationGlobalMetadata,
    ConsolidationInput,
    ConsolidationNode,
    ConsolidationProviderMetadata,
    ConsolidationRelation,
    ConsolidationRepetition,
    ConsolidationSemanticResult,
    FORBIDDEN_OPS,
    TRANSPORT_OP_KEEP,
    TRANSPORT_OP_MERGE,
    TRANSPORT_OP_REL,
    TRANSPORT_OP_REP,
    TRANSPORT_OP_TO_CANONICAL,
    format_consolidation_node_id,
    record_category,
    requires_exclusive_disposition,
    union_source_refs,
)
from app.source_analysis.errors import (
    ConsolidationTransportValidationError,
    SourceMapEditorialLeakError,
)
from app.source_analysis.models import (
    RELATION_KINDS,
    REPETITION_CHARACTERS,
    forbidden_editorial_fields,
)
from app.source_analysis.window_writer import render_exact_json

ALLOWED_OP_KEYS = frozenset({"o", "r", "m", "v", "t", "a", "b", "c"})
ALLOWED_GM_KEYS = frozenset({"th", "in", "au", "vo", "te", "ie", "ae", "ve"})
ALLOWED_ROOT_KEYS = frozenset({"gm", "ops"})


def _fail(message: str) -> None:
    raise ConsolidationTransportValidationError(message)


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{name} n'est pas un objet.")
    return value


def _require_list(value: Any, name: str) -> list:
    if not isinstance(value, list):
        _fail(f"{name} n'est pas une liste.")
    return value


def _require_str(value: Any, name: str) -> str:
    if not isinstance(value, str):
        _fail(f"{name} n'est pas une chaîne.")
    return value


def _require_str_list(value: Any, name: str) -> tuple[str, ...]:
    items = _require_list(value, name)
    out: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, str):
            _fail(f"{name}[{index}] n'est pas une chaîne.")
        out.append(item)
    return tuple(out)


def _assert_known_keys(payload: Mapping[str, Any], allowed: frozenset[str], name: str) -> None:
    unknown = [key for key in payload if key not in allowed]
    if unknown:
        _fail(f"{name} : clés inconnues {unknown}.")


def decode_consolidation_transport(
    transport: Mapping[str, Any],
    consolidation_input: ConsolidationInput,
    *,
    signature: str,
    provider_metadata: ConsolidationProviderMetadata,
) -> ConsolidationSemanticResult:
    leaked = forbidden_editorial_fields(transport)
    if leaked:
        raise SourceMapEditorialLeakError(leaked, location="consolidation transport")
    if not isinstance(transport, Mapping):
        _fail("transport n'est pas un objet.")
    extra_root = [key for key in transport if key not in ALLOWED_ROOT_KEYS]
    editorial_extra = forbidden_editorial_fields({key: True for key in extra_root})
    if editorial_extra:
        raise SourceMapEditorialLeakError(
            editorial_extra, location="consolidation transport"
        )
    if extra_root:
        _fail(f"clés racine inconnues : {extra_root}.")

    gm = _require_mapping(transport.get("gm"), "gm")
    _assert_known_keys(gm, ALLOWED_GM_KEYS, "gm")
    for field in ("th", "in", "au", "vo"):
        text = _require_str(gm.get(field), f"gm.{field}").strip()
        if not text:
            _fail(f"gm.{field} vide.")
    theme_ev = _require_str_list(gm.get("te"), "gm.te")
    intent_ev = _require_str_list(gm.get("ie"), "gm.ie")
    audience_ev = _require_str_list(gm.get("ae"), "gm.ae")
    voice_ev = _require_str_list(gm.get("ve"), "gm.ve")
    if not theme_ev:
        _fail("GLOBAL_METADATA.theme_evidence vide.")
    if not intent_ev:
        _fail("GLOBAL_METADATA.intent_evidence vide.")
    if not audience_ev:
        _fail("GLOBAL_METADATA.audience_evidence vide.")
    if not voice_ev:
        _fail("GLOBAL_METADATA.voice_evidence vide.")

    records = consolidation_input.record_by_id()
    for label, refs in (
        ("theme_evidence", theme_ev),
        ("intent_evidence", intent_ev),
        ("audience_evidence", audience_ev),
        ("voice_evidence", voice_ev),
    ):
        for ref in refs:
            if ref not in records:
                _fail(f"GLOBAL_METADATA.{label} référence inconnue : {ref}.")

    ops = _require_list(transport.get("ops"), "ops")
    keep_merge: list[tuple[str, Mapping[str, Any]]] = []
    relations_raw: list[Mapping[str, Any]] = []
    repetitions_raw: list[Mapping[str, Any]] = []

    for index, item in enumerate(ops):
        op_map = _require_mapping(item, f"ops[{index}]")
        leaked_op = forbidden_editorial_fields(op_map)
        if leaked_op:
            raise SourceMapEditorialLeakError(
                leaked_op, location=f"consolidation ops[{index}]"
            )
        _assert_known_keys(op_map, ALLOWED_OP_KEYS, f"ops[{index}]")
        code = _require_str(op_map.get("o"), f"ops[{index}].o")
        if code in FORBIDDEN_OPS or code in {"DROP", "DROP_RECORD"}:
            _fail(f"opération interdite : {code}.")
        if code not in TRANSPORT_OP_TO_CANONICAL:
            _fail(f"opération inconnue : {code}.")
        if code in {TRANSPORT_OP_KEEP, TRANSPORT_OP_MERGE}:
            keep_merge.append((code, op_map))
        elif code == TRANSPORT_OP_REL:
            relations_raw.append(op_map)
        else:
            repetitions_raw.append(op_map)

    dispositions: dict[str, str] = {}
    member_to_node: dict[str, str] = {}
    nodes: list[ConsolidationNode] = []

    def _account(record_id: str, op_name: str) -> None:
        if record_id not in records:
            _fail(f"référence inconnue : {record_id}.")
        previous = dispositions.get(record_id)
        if previous is not None:
            _fail(
                f"disposition dupliquée pour {record_id} : {previous} et {op_name}."
            )
        dispositions[record_id] = op_name

    for index, (code, item) in enumerate(keep_merge, start=1):
        node_id = format_consolidation_node_id(index)
        if code == TRANSPORT_OP_KEEP:
            record_id = _require_str(item.get("r"), "KEEP.r").strip()
            if not record_id:
                _fail("KEEP sans identifiant.")
            _account(record_id, "KEEP_RECORD")
            record = records[record_id]
            nodes.append(
                ConsolidationNode(
                    node_id=node_id,
                    operation="KEEP_RECORD",
                    kind=record.kind,
                    value=record.value,
                    member_ids=(record_id,),
                    source_refs=record.source_refs,
                    source_refs_are_local_union=False,
                )
            )
            member_to_node[record_id] = node_id
            continue

        members = _require_str_list(item.get("m"), "MERGE.m")
        if len(members) < 2:
            _fail("MERGE_RECORDS exige au moins 2 membres.")
        if len(members) != len(set(members)):
            _fail("MERGE_RECORDS : membre dupliqué.")
        merged_text = _require_str(item.get("v"), "MERGE.v").strip()
        if not merged_text:
            _fail("MERGE_RECORDS : texte fusionné vide.")
        kinds: list[str] = []
        src_groups: list[tuple[str, ...]] = []
        for member in members:
            _account(member, "MERGE_RECORDS")
            record = records[member]
            kinds.append(record.kind)
            src_groups.append(record.source_refs)
            member_to_node[member] = node_id
        if len(set(kinds)) != 1:
            _fail(
                f"MERGE de kinds incompatibles : {kinds}."
            )
        nodes.append(
            ConsolidationNode(
                node_id=node_id,
                operation="MERGE_RECORDS",
                kind=kinds[0],
                value=merged_text,
                member_ids=members,
                source_refs=union_source_refs(src_groups),
                source_refs_are_local_union=True,
            )
        )

    def _resolve_endpoint(ref: str, *, allow_unaccounted: bool = False) -> str:
        if ref in member_to_node:
            return member_to_node[ref]
        if ref.startswith("C") and any(node.node_id == ref for node in nodes):
            _fail(
                f"référence provider vers nœud local {ref} interdite "
                "(pas de Cxxxx provider ; pas de forward-ref)."
            )
        if ref not in records:
            _fail(f"référence inconnue : {ref}.")
        if not allow_unaccounted and ref not in dispositions:
            _fail(f"référence {ref} sans disposition KEEP/MERGE.")
        if ref in dispositions:
            return member_to_node[ref]
        _fail(f"référence {ref} non résolue.")
        return ref

    relations: list[ConsolidationRelation] = []
    for item in relations_raw:
        rel_type = _require_str(item.get("t"), "REL.t")
        if rel_type not in RELATION_KINDS:
            _fail(f"type de relation inconnu : {rel_type!r}.")
        left = _require_str(item.get("a"), "REL.a")
        right = _require_str(item.get("b"), "REL.b")
        left_node = _resolve_endpoint(left)
        right_node = _resolve_endpoint(right)
        relations.append(
            ConsolidationRelation(
                relation_type=rel_type,
                left_ref=left,
                right_ref=right,
                left_node_id=left_node,
                right_node_id=right_node,
            )
        )

    repetitions: list[ConsolidationRepetition] = []
    for item in repetitions_raw:
        character = _require_str(item.get("c"), "REP.c")
        if character not in REPETITION_CHARACTERS:
            _fail(f"caractère de répétition inconnu : {character!r}.")
        members = _require_str_list(item.get("m"), "REP.m")
        if len(members) < 2:
            _fail("REPETITION exige au moins 2 membres.")
        if len(members) != len(set(members)):
            _fail("REPETITION : membre dupliqué.")
        node_ids = tuple(_resolve_endpoint(member) for member in members)
        value = item.get("v")
        if value is None:
            value = ""
        else:
            value = _require_str(value, "REP.v")
        repetitions.append(
            ConsolidationRepetition(
                character=character,
                member_ids=members,
                node_ids=node_ids,
                value=value,
            )
        )

    metadata_evidence = set(theme_ev) | set(intent_ev) | set(audience_ev) | set(voice_ev)
    unaccounted: list[str] = []
    for record in consolidation_input.all_records():
        if requires_exclusive_disposition(record.kind):
            if record.record_id not in dispositions:
                unaccounted.append(record.record_id)
        elif record.kind in CATEGORY_C_METADATA_EVIDENCE:
            if (
                record.record_id not in dispositions
                and record.record_id not in metadata_evidence
            ):
                unaccounted.append(record.record_id)
        else:
            _fail(f"kind hors contrat : {record.kind}.")
    if unaccounted:
        _fail("records non comptabilisés : " + ", ".join(unaccounted))

    return ConsolidationSemanticResult(
        schema_version=CONSOLIDATION_RESULT_SCHEMA_VERSION,
        input_hash=consolidation_input.input_hash,
        consolidation_signature=signature,
        transport_version=consolidation_input.transport_version,
        prompt_version=consolidation_input.prompt_version,
        global_metadata=ConsolidationGlobalMetadata(
            main_theme=_require_str(gm.get("th"), "gm.th").strip(),
            author_intent=_require_str(gm.get("in"), "gm.in").strip(),
            target_audience=_require_str(gm.get("au"), "gm.au").strip(),
            author_voice_profile=_require_str(gm.get("vo"), "gm.vo").strip(),
            theme_evidence=theme_ev,
            intent_evidence=intent_ev,
            audience_evidence=audience_ev,
            voice_evidence=voice_ev,
        ),
        nodes=tuple(nodes),
        relations=tuple(relations),
        repetitions=tuple(repetitions),
        provider_metadata=provider_metadata,
        accounted_record_ids=tuple(dispositions),
    )


def transport_canonical_text(transport: Mapping[str, Any]) -> str:
    return render_exact_json(transport)


def record_category_or_fail(kind: str) -> str:
    category = record_category(kind)
    if category is None:
        _fail(f"kind inconnu : {kind}.")
    return category


__all__ = [
    "decode_consolidation_transport",
    "transport_canonical_text",
]
