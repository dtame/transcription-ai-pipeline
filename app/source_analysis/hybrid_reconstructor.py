"""
HybridCanonicalReconstructor — 3B.7.5.

Transformation STRUCTURELLE et DÉTERMINISTE :

    ConsolidationSemanticResult
    + WindowSemanticResult[] validés
    + TranscriptInput / WindowPlan
        → raw canonical candidate
        → normalize_source_map() existant
        → validateur canonique existant
        → SourceMap

Aucun engine. Aucune décision d'équivalence sémantique.
KEEP / MERGE / REL / REP / GLOBAL_METADATA sont déjà tranchés
par le consolidateur validé. Ici : résolution d'identités, union
SRC, IDs locaux, réécriture, normalisation.

Règle des relations (3B.7.4) :

    1. Disposition finale des RELATION fenêtre = KEEP ou MERGE
       exclusif déjà validé. On ne jette pas les relations locales.
    2. Les REL de consolidation ajoutent des relations inter-fenêtres
       dont les extrémités sont déjà KEEP/MERGE.
    3. Déduplication STRUCTURELLE uniquement :
       (from_node, type, to_node). Pas de fusion sémantique.
    4. IDEA→IDEA devient IdeaRelation. EXAMPLE→IDEA
       (supports/illustrates) devient supports_idea_refs.
    5. Tout autre couple d'extrémités : FAIL CLOSED.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from app.source_analysis.consolidation_input import build_consolidation_input_from_plan
from app.source_analysis.consolidation_models import (
    ConsolidationInput,
    ConsolidationNode,
    ConsolidationSemanticResult,
)
from app.source_analysis.consolidation_prompt import (
    build_consolidation_system_prompt,
    build_consolidation_user_prompt,
    consolidation_prompt_fingerprint,
)
from app.source_analysis.consolidation_schema import consolidation_schema_fingerprint
from app.source_analysis.consolidation_validator import validate_consolidation_result
from app.source_analysis.errors import (
    HybridPreconditionError,
    HybridReconstructionError,
    SourceMapEditorialLeakError,
)
from app.source_analysis.hybrid_signature import (
    HYBRID_STRATEGY,
    RECONSTRUCTOR_VERSION,
    build_hybrid_signature,
    hybrid_signature_inputs_for,
)
from app.source_analysis_hybrid.constants import CONSOLIDATION_PROMPT_VERSION
from app.source_analysis.models import (
    CONFIDENCE_LEVELS,
    EXAMPLE_KINDS,
    IDEA_KINDS,
    IMPORTANCE_LEVELS,
    REFERENCE_COMPLETENESS,
    REFERENCE_KINDS,
    RELATION_KINDS,
    REPETITION_CHARACTERS,
    SEVERITY_LEVELS,
    SOURCE_MAP_SCHEMA_VERSION,
    UNCERTAINTY_KINDS,
    AnalysisProvenance,
    SourceMap,
    forbidden_editorial_fields,
)
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.orchestration_models import WindowOrchestrationResult
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.ultra_compact_schema import (
    VOICE_FIELDS,
    VOICE_LIST_FIELDS,
    VOICE_SCALAR_FIELDS,
)
from app.source_analysis.ultra_compact_schema import ultra_compact_schema_fingerprint
from app.source_analysis.validator import ensure_valid_source_map
from app.source_analysis.window_models import (
    WindowIntermediateRecord,
    WindowSemanticResult,
)
from app.source_analysis.window_prompt import (
    build_window_system_prompt,
    build_window_user_prompt,
    window_prompt_fingerprint,
)
from app.source_analysis.window_validator import validate_window_result
from app.source_analysis_hybrid.contracts import WindowPlan

IDEA_METADATA_LAYOUT_V3 = "v3"
IDEA_METADATA_LAYOUT_LOCAL_LITE = "v3.1-local-lite"

_EXAMPLE_SUPPORT_RELATIONS = frozenset({"supports", "illustrates"})


def union_source_refs_in_source_order(
    groups: Sequence[Sequence[str]],
    src_index: Mapping[str, int],
) -> tuple[str, ...]:
    """
    Union déterministe : membership réelle uniquement, ordre source.

    Pas de plage numérique. Pas de SRC intermédiaire inventé.
    """
    seen: dict[str, None] = {}
    for group in groups:
        for ref in group:
            if ref not in src_index:
                raise HybridReconstructionError(
                    f"source_ref « {ref} » absent du transcript — "
                    "pas d'expansion de plage, pas d'invention."
                )
            seen.setdefault(ref, None)
    return tuple(sorted(seen, key=lambda ref: src_index[ref]))


def _fail(message: str) -> None:
    raise HybridReconstructionError(message)


def _precondition(message: str) -> None:
    raise HybridPreconditionError(message)


def _ordered_results(
    plan: WindowPlan,
    results: Sequence[WindowSemanticResult],
) -> tuple[WindowSemanticResult, ...]:
    by_id: dict[str, list[WindowSemanticResult]] = {}
    for result in results:
        by_id.setdefault(result.window_id, []).append(result)
    ordered: list[WindowSemanticResult] = []
    for window in plan.windows:
        matches = by_id.get(window.window_id) or []
        if len(matches) != 1:
            _precondition(
                f"ALL_WINDOWS_READY refusé : {window.window_id} a "
                f"{len(matches)} résultat(s)."
            )
        ordered.append(matches[0])
    extra = set(by_id) - {window.window_id for window in plan.windows}
    if extra:
        _precondition(f"résultats hors plan : {sorted(extra)}")
    return tuple(ordered)


def assert_hybrid_preconditions(
    transcript: TranscriptInput,
    plan: WindowPlan,
    window_results: Sequence[WindowSemanticResult],
    consolidation_result: ConsolidationSemanticResult,
    *,
    consolidation_input: ConsolidationInput | None = None,
    orchestration: WindowOrchestrationResult | None = None,
    enforce_budget: bool = True,
) -> tuple[tuple[WindowSemanticResult, ...], ConsolidationInput]:
    """
    Identités et hashes. Fail-closed. Aucune reconstruction partielle.
    """
    if orchestration is not None and not orchestration.all_windows_ready:
        _precondition(
            "ALL_WINDOWS_READY refusé — reconstruction canonique interdite."
        )
    if transcript.transcript_id != plan.transcript_id:
        _precondition(
            f"transcript {transcript.transcript_id!r} ≠ plan {plan.transcript_id!r}."
        )
    if transcript.content_sha256 != plan.transcript_sha256:
        _precondition("transcript_sha256 ≠ WindowPlan.")
    if len(window_results) != plan.window_count:
        _precondition(
            "ALL_WINDOWS_READY refusé : "
            f"{len(window_results)}/{plan.window_count} fenêtres."
        )
    ordered = _ordered_results(plan, window_results)
    for window, result in zip(plan.windows, ordered):
        if result.window_input_hash != window.input_hash:
            _precondition(
                f"{result.window_id} : window_input_hash ≠ plan courant."
            )
        if result.planner_version != plan.planner_version:
            _precondition(
                f"{result.window_id} : planner_version ≠ WindowPlan."
            )
        validate_window_result(result, window)
        leaked = forbidden_editorial_fields(result.to_dict())
        if leaked:
            raise SourceMapEditorialLeakError(
                leaked, location=f"window result {result.window_id}"
            )

    rebuilt = build_consolidation_input_from_plan(
        plan, ordered, enforce_budget=enforce_budget
    )
    if rebuilt.transcript_id != transcript.transcript_id:
        _precondition("ConsolidationInput.transcript_id ≠ transcript.")
    if consolidation_input is not None:
        if consolidation_input.input_hash != rebuilt.input_hash:
            _precondition(
                "ConsolidationInput fourni ≠ jeu de fenêtres courant "
                "(consolidation périmée ou mauvais plan)."
            )
        if consolidation_input.transcript_id != transcript.transcript_id:
            _precondition("ConsolidationInput.transcript_id ≠ transcript.")
        if consolidation_input.planner_version != plan.planner_version:
            _precondition("ConsolidationInput.planner_version ≠ WindowPlan.")
    if consolidation_result.input_hash != rebuilt.input_hash:
        _precondition(
            "ConsolidationSemanticResult.input_hash ≠ ConsolidationInput "
            "courant — consolidation périmée ou jeu de fenêtres changé."
        )
    leaked_cons = forbidden_editorial_fields(consolidation_result.to_dict())
    if leaked_cons:
        raise SourceMapEditorialLeakError(
            leaked_cons, location="consolidation result"
        )
    validate_consolidation_result(consolidation_result, rebuilt)
    return ordered, rebuilt


def _record_table(
    results: Sequence[WindowSemanticResult],
) -> dict[str, WindowIntermediateRecord]:
    table: dict[str, WindowIntermediateRecord] = {}
    for result in results:
        for record in result.records:
            if record.record_id in table:
                _fail(f"identifiant intermédiaire dupliqué : {record.record_id}")
            table[record.record_id] = record
    return table


def _require_same(values: Sequence[str], label: str) -> str:
    unique = {value for value in values}
    if len(unique) != 1:
        _fail(
            f"{label} divergent parmi les membres MERGE {sorted(unique)} — "
            "aucune décision sémantique locale."
        )
    return next(iter(unique))


def _meta(record: WindowIntermediateRecord, index: int, label: str) -> str:
    if index >= len(record.metadata) or not record.metadata[index]:
        _fail(f"{record.record_id} : {label} absent (fail-closed).")
    return record.metadata[index]


def _members(
    node: ConsolidationNode,
    table: Mapping[str, WindowIntermediateRecord],
) -> tuple[WindowIntermediateRecord, ...]:
    members: list[WindowIntermediateRecord] = []
    for member_id in node.member_ids:
        record = table.get(member_id)
        if record is None:
            _fail(f"{node.node_id} : membre {member_id} absent de la table.")
        members.append(record)
    return tuple(members)


def _remap_links(
    link_ids: Sequence[str],
    record_to_node: Mapping[str, str],
    nodes_by_id: Mapping[str, ConsolidationNode],
    *,
    expected_kind: str,
    context: str,
) -> tuple[str, ...]:
    resolved: dict[str, None] = {}
    for link in link_ids:
        node_id = record_to_node.get(link)
        if node_id is None:
            _fail(f"{context} : lien {link} sans disposition KEEP/MERGE.")
        node = nodes_by_id[node_id]
        if node.kind != expected_kind:
            _fail(
                f"{context} : lien {link} résout vers {node.node_id} "
                f"kind={node.kind} (attendu {expected_kind})."
            )
        resolved.setdefault(node_id, None)
    return tuple(resolved)


class HybridCanonicalReconstructor:
    """
    Reconstructeur local. Ne reçoit aucun engine. Ne peut pas appeler l'IA.
    """

    version = RECONSTRUCTOR_VERSION

    def reconstruct(
        self,
        transcript: TranscriptInput,
        window_plan: WindowPlan,
        window_results: Sequence[WindowSemanticResult],
        consolidation_result: ConsolidationSemanticResult,
        *,
        consolidation_input: ConsolidationInput | None = None,
        orchestration: WindowOrchestrationResult | None = None,
        enforce_budget: bool = True,
    ) -> SourceMap:
        return reconstruct_source_map(
            transcript,
            window_plan,
            window_results,
            consolidation_result,
            consolidation_input=consolidation_input,
            orchestration=orchestration,
            enforce_budget=enforce_budget,
        )


def reconstruct_source_map(
    transcript: TranscriptInput,
    window_plan: WindowPlan,
    window_results: Sequence[WindowSemanticResult],
    consolidation_result: ConsolidationSemanticResult,
    *,
    consolidation_input: ConsolidationInput | None = None,
    orchestration: WindowOrchestrationResult | None = None,
    enforce_budget: bool = True,
) -> SourceMap:
    """
    Reconstruction canonique. Fail-closed. Passe par normalize_source_map().
    """
    ordered, rebuilt = assert_hybrid_preconditions(
        transcript,
        window_plan,
        window_results,
        consolidation_result,
        consolidation_input=consolidation_input,
        orchestration=orchestration,
        enforce_budget=enforce_budget,
    )
    raw = build_raw_canonical_candidate(
        transcript,
        ordered,
        consolidation_result,
    )
    leaked = forbidden_editorial_fields(raw)
    if leaked:
        raise SourceMapEditorialLeakError(
            leaked, location="hybrid raw canonical candidate"
        )
    provenance = _build_provenance(
        transcript,
        window_plan,
        rebuilt,
        consolidation_result,
        ordered,
    )
    source_map = normalize_source_map(raw, transcript, provenance=provenance)
    ensure_valid_source_map(source_map, transcript)
    _assert_canonical_ids(source_map)
    return source_map


def build_raw_canonical_candidate(
    transcript: TranscriptInput,
    window_results: Sequence[WindowSemanticResult],
    consolidation_result: ConsolidationSemanticResult,
    *,
    idea_metadata_layout: str = IDEA_METADATA_LAYOUT_V3,
) -> dict:
    """Raw candidate compatible avec normalize_source_map(). Sans IDs canoniques."""
    table = _record_table(window_results)
    src_index = transcript.src_index()
    nodes_by_id = {node.node_id: node for node in consolidation_result.nodes}
    record_to_node = {
        member: node.node_id
        for node in consolidation_result.nodes
        for member in node.member_ids
    }
    results_by_id = {result.window_id: result for result in window_results}

    topics: list[dict] = []
    ideas: list[dict] = []
    examples: list[dict] = []
    references: list[dict] = []
    uncertainties: list[dict] = []
    repetitions: list[dict] = []
    idea_relations: dict[str, list[dict]] = {}
    example_supports: dict[str, list[str]] = {}

    for node in consolidation_result.nodes:
        members = _members(node, table)
        source_refs = union_source_refs_in_source_order(
            [member.source_refs for member in members],
            src_index,
        )
        if node.kind == "TOPIC":
            label, summary = _topic_text(node, members)
            topics.append(
                {
                    "topic_id": node.node_id,
                    "label": label,
                    "summary": summary,
                    "source_refs": list(source_refs),
                }
            )
        elif node.kind == "IDEA":
            if idea_metadata_layout == IDEA_METADATA_LAYOUT_LOCAL_LITE:
                ideas.append(
                    _idea_raw_local_lite(
                        node, members, record_to_node, nodes_by_id, source_refs
                    )
                )
            elif idea_metadata_layout == IDEA_METADATA_LAYOUT_V3:
                ideas.append(
                    _idea_raw(node, members, record_to_node, nodes_by_id, source_refs)
                )
            else:
                _fail(
                    f"{node.node_id} : idea_metadata_layout inconnu "
                    f"{idea_metadata_layout!r}."
                )
            idea_relations.setdefault(node.node_id, [])
        elif node.kind == "EXAMPLE":
            supports = _remap_links(
                [link for member in members for link in member.link_record_ids],
                record_to_node,
                nodes_by_id,
                expected_kind="IDEA",
                context=f"{node.node_id} EXAMPLE",
            )
            example_supports[node.node_id] = list(supports)
            examples.append(
                {
                    "example_id": node.node_id,
                    "kind": _example_kind(node, members),
                    "summary": (
                        node.value
                        if node.operation == "MERGE_RECORDS"
                        else members[0].value
                    ),
                    "supports_idea_refs": list(supports),
                    "source_refs": list(source_refs),
                }
            )
        elif node.kind == "REFERENCE":
            references.append(_reference_raw(node, members, source_refs))
        elif node.kind == "UNCERTAINTY":
            uncertainties.append(_uncertainty_raw(node, members, source_refs))
        elif node.kind == "REPETITION":
            repetitions.append(
                _repetition_from_node(
                    node, members, record_to_node, nodes_by_id, source_refs
                )
            )
        elif node.kind == "RELATION":
            _apply_relation_node(
                node,
                members,
                record_to_node,
                nodes_by_id,
                idea_relations,
            )
        elif node.kind in {"VOICE", "INTENT_KIND", "AUDIENCE_KIND"}:
            continue
        else:
            _fail(f"{node.node_id} : kind non reconstructible {node.kind!r}.")

    _apply_consolidation_relations(
        consolidation_result,
        nodes_by_id,
        idea_relations,
        example_supports,
        examples,
    )
    for idea in ideas:
        idea["relations"] = _dedupe_relations(idea_relations.get(idea["idea_id"], ()))
    for example in examples:
        example["supports_idea_refs"] = _unique(
            example_supports.get(example["example_id"], example["supports_idea_refs"])
        )

    for item in consolidation_result.repetitions:
        repetitions.append(
            _repetition_from_op(
                item,
                table,
                record_to_node,
                nodes_by_id,
                src_index,
            )
        )

    metadata = _canonical_global_metadata(
        consolidation_result,
        table,
        results_by_id,
    )
    return {
        "source_analysis": metadata["source_analysis"],
        "topics": topics,
        "ideas": ideas,
        "examples": examples,
        "references": references,
        "uncertainties": uncertainties,
        "repetitions": repetitions,
        "author_voice_profile": metadata["author_voice_profile"],
    }


def _topic_text(
    node: ConsolidationNode,
    members: Sequence[WindowIntermediateRecord],
) -> tuple[str, str]:
    if node.operation == "KEEP_RECORD":
        label = members[0].value
        summary = members[0].metadata[0] if members[0].metadata else members[0].value
        if not label or not summary:
            _fail(f"{node.node_id} : TOPIC KEEP sans label/summary.")
        return label, summary
    if not node.value.strip():
        _fail(f"{node.node_id} : MERGE TOPIC sans texte consolidé.")
    return node.value, node.value


def _idea_raw(
    node: ConsolidationNode,
    members: Sequence[WindowIntermediateRecord],
    record_to_node: Mapping[str, str],
    nodes_by_id: Mapping[str, ConsolidationNode],
    source_refs: Sequence[str],
) -> dict:
    kinds = [_meta(member, 0, "idea kind") for member in members]
    importances = [_meta(member, 1, "importance") for member in members]
    kind = kinds[0] if node.operation == "KEEP_RECORD" else _require_same(kinds, "idea kind")
    importance = (
        importances[0]
        if node.operation == "KEEP_RECORD"
        else _require_same(importances, "importance")
    )
    if kind not in IDEA_KINDS:
        _fail(f"{node.node_id} : idea kind invalide {kind!r}.")
    if importance not in IMPORTANCE_LEVELS:
        _fail(f"{node.node_id} : importance invalide {importance!r}.")
    summary = members[0].value if node.operation == "KEEP_RECORD" else node.value
    if not summary.strip():
        _fail(f"{node.node_id} : IDEA sans texte.")
    topic_refs = _remap_links(
        [link for member in members for link in member.link_record_ids],
        record_to_node,
        nodes_by_id,
        expected_kind="TOPIC",
        context=f"{node.node_id} IDEA",
    )
    return {
        "idea_id": node.node_id,
        "summary": summary,
        "kind": kind,
        "importance": importance,
        "topic_refs": list(topic_refs),
        "relations": [],
        "source_refs": list(source_refs),
    }


def _idea_raw_local_lite(
    node: ConsolidationNode,
    members: Sequence[WindowIntermediateRecord],
    record_to_node: Mapping[str, str],
    nodes_by_id: Mapping[str, ConsolidationNode],
    source_refs: Sequence[str],
) -> dict:
    """
    Local-lite : m=[importance] seulement.

    Ne copie jamais m[0] vers Idea.kind. Absence de sous-type = kind vide.
    """
    for member in members:
        if len(member.metadata) != 1:
            _fail(
                f"{member.record_id} : IDEA local-lite exige m=[importance] "
                f"(reçu {list(member.metadata)!r})."
            )
        token = member.metadata[0]
        if token in IDEA_KINDS:
            _fail(
                f"{member.record_id} : IDEA local-lite refuse un sous-type "
                f"{token!r} dans m[0]."
            )
    importances = [_meta(member, 0, "importance") for member in members]
    importance = (
        importances[0]
        if node.operation == "KEEP_RECORD"
        else _require_same(importances, "importance")
    )
    if importance not in IMPORTANCE_LEVELS:
        _fail(f"{node.node_id} : importance invalide {importance!r}.")
    if importance in IDEA_KINDS:
        _fail(
            f"{node.node_id} : importance {importance!r} ne peut pas devenir "
            "Idea.kind."
        )
    summary = members[0].value if node.operation == "KEEP_RECORD" else node.value
    if not summary.strip():
        _fail(f"{node.node_id} : IDEA sans texte.")
    topic_refs = _remap_links(
        [link for member in members for link in member.link_record_ids],
        record_to_node,
        nodes_by_id,
        expected_kind="TOPIC",
        context=f"{node.node_id} IDEA",
    )
    return {
        "idea_id": node.node_id,
        "summary": summary,
        "kind": "",
        "importance": importance,
        "topic_refs": list(topic_refs),
        "relations": [],
        "source_refs": list(source_refs),
    }


def _example_kind(
    node: ConsolidationNode,
    members: Sequence[WindowIntermediateRecord],
) -> str:
    kinds = [_meta(member, 0, "example kind") for member in members]
    kind = kinds[0] if node.operation == "KEEP_RECORD" else _require_same(kinds, "example kind")
    if kind not in EXAMPLE_KINDS:
        _fail(f"{node.node_id} : example kind invalide {kind!r}.")
    return kind


def _reference_raw(
    node: ConsolidationNode,
    members: Sequence[WindowIntermediateRecord],
    source_refs: Sequence[str],
) -> dict:
    kinds = [_meta(member, 0, "reference kind") for member in members]
    completions = [_meta(member, 1, "completeness") for member in members]
    normalized_values = [
        member.metadata[2] if len(member.metadata) > 2 else "" for member in members
    ]
    kind = kinds[0] if node.operation == "KEEP_RECORD" else _require_same(kinds, "reference kind")
    completeness = (
        completions[0]
        if node.operation == "KEEP_RECORD"
        else _require_same(completions, "completeness")
    )
    normalized = (
        normalized_values[0]
        if node.operation == "KEEP_RECORD"
        else _require_same(normalized_values, "normalized_reference")
    )
    if kind not in REFERENCE_KINDS:
        _fail(f"{node.node_id} : reference kind invalide {kind!r}.")
    if completeness not in REFERENCE_COMPLETENESS:
        _fail(f"{node.node_id} : completeness invalide {completeness!r}.")
    raw = members[0].value if node.operation == "KEEP_RECORD" else node.value
    if not raw.strip():
        _fail(f"{node.node_id} : raw_reference vide.")
    return {
        "reference_id": node.node_id,
        "kind": kind,
        "raw_reference": raw,
        "normalized_reference": normalized,
        "completeness": completeness,
        "source_refs": list(source_refs),
    }


def _uncertainty_raw(
    node: ConsolidationNode,
    members: Sequence[WindowIntermediateRecord],
    source_refs: Sequence[str],
) -> dict:
    kinds = [_meta(member, 0, "uncertainty kind") for member in members]
    severities = [_meta(member, 1, "severity") for member in members]
    kind = kinds[0] if node.operation == "KEEP_RECORD" else _require_same(kinds, "uncertainty kind")
    severity = (
        severities[0]
        if node.operation == "KEEP_RECORD"
        else _require_same(severities, "severity")
    )
    if kind not in UNCERTAINTY_KINDS:
        _fail(f"{node.node_id} : uncertainty kind invalide {kind!r}.")
    if severity not in SEVERITY_LEVELS:
        _fail(f"{node.node_id} : severity invalide {severity!r}.")
    description = members[0].value if node.operation == "KEEP_RECORD" else node.value
    if not description.strip():
        _fail(f"{node.node_id} : uncertainty description vide.")
    return {
        "uncertainty_id": node.node_id,
        "kind": kind,
        "description": description,
        "severity": severity,
        "source_refs": list(source_refs),
    }


def _repetition_from_node(
    node: ConsolidationNode,
    members: Sequence[WindowIntermediateRecord],
    record_to_node: Mapping[str, str],
    nodes_by_id: Mapping[str, ConsolidationNode],
    source_refs: Sequence[str],
) -> dict:
    characters = [_meta(member, 0, "repetition character") for member in members]
    character = (
        characters[0]
        if node.operation == "KEEP_RECORD"
        else _require_same(characters, "repetition character")
    )
    if character not in REPETITION_CHARACTERS:
        _fail(f"{node.node_id} : character invalide {character!r}.")
    description = members[0].value if node.operation == "KEEP_RECORD" else node.value
    if not description.strip():
        _fail(f"{node.node_id} : repetition description vide.")
    idea_refs = _remap_links(
        [link for member in members for link in member.link_record_ids],
        record_to_node,
        nodes_by_id,
        expected_kind="IDEA",
        context=f"{node.node_id} REPETITION",
    )
    if len(idea_refs) < 2:
        _fail(f"{node.node_id} : REPETITION sans 2 idea_refs canoniques.")
    return {
        "character": character,
        "description": description,
        "idea_refs": list(idea_refs),
        "source_refs": list(source_refs),
    }


def _repetition_from_op(
    item,
    table: Mapping[str, WindowIntermediateRecord],
    record_to_node: Mapping[str, str],
    nodes_by_id: Mapping[str, ConsolidationNode],
    src_index: Mapping[str, int],
) -> dict:
    if item.character not in REPETITION_CHARACTERS:
        _fail(f"REP character invalide {item.character!r}.")
    if not item.value.strip():
        _fail("REP consolidation sans description.")
    idea_refs = _remap_links(
        item.member_ids,
        record_to_node,
        nodes_by_id,
        expected_kind="IDEA",
        context="consolidation REP",
    )
    if len(idea_refs) < 2:
        _fail("REP consolidation : moins de 2 ideas après remap.")
    groups = []
    for member_id in item.member_ids:
        record = table.get(member_id)
        if record is None:
            _fail(f"REP membre {member_id} absent.")
        groups.append(record.source_refs)
    return {
        "character": item.character,
        "description": item.value,
        "idea_refs": list(idea_refs),
        "source_refs": list(union_source_refs_in_source_order(groups, src_index)),
    }


def _apply_relation_node(
    node: ConsolidationNode,
    members: Sequence[WindowIntermediateRecord],
    record_to_node: Mapping[str, str],
    nodes_by_id: Mapping[str, ConsolidationNode],
    idea_relations: dict[str, list[dict]],
) -> None:
    endpoints: list[tuple[str, str]] = []
    types: list[str] = []
    for member in members:
        if len(member.link_record_ids) != 2:
            _fail(f"{member.record_id} : RELATION exige 2 extrémités.")
        left, right = member.link_record_ids
        left_node = _remap_links(
            [left], record_to_node, nodes_by_id, expected_kind="IDEA", context=node.node_id
        )
        right_node = _remap_links(
            [right], record_to_node, nodes_by_id, expected_kind="IDEA", context=node.node_id
        )
        if not left_node or not right_node:
            _fail(f"{node.node_id} : extrémité RELATION non résolue.")
        endpoints.append((left_node[0], right_node[0]))
        types.append(member.value)
    if node.operation == "MERGE_RECORDS":
        relation_type = node.value.strip() or _require_same(types, "relation type")
        endpoint = _require_same(
            [f"{left}->{right}" for left, right in endpoints],
            "relation endpoints",
        )
        left, right = endpoint.split("->", 1)
    else:
        relation_type = types[0]
        left, right = endpoints[0]
    if relation_type not in RELATION_KINDS:
        _fail(f"{node.node_id} : relation type invalide {relation_type!r}.")
    if left == right:
        _fail(f"{node.node_id} : relation sur elle-même.")
    idea_relations.setdefault(left, []).append(
        {"relation": relation_type, "to_idea": right}
    )


def _apply_consolidation_relations(
    consolidation_result: ConsolidationSemanticResult,
    nodes_by_id: Mapping[str, ConsolidationNode],
    idea_relations: dict[str, list[dict]],
    example_supports: dict[str, list[str]],
    examples: list[dict],
) -> None:
    example_ids = {item["example_id"] for item in examples}
    for relation in consolidation_result.relations:
        if relation.relation_type not in RELATION_KINDS:
            _fail(f"REL type invalide {relation.relation_type!r}.")
        left = nodes_by_id.get(relation.left_node_id)
        right = nodes_by_id.get(relation.right_node_id)
        if left is None or right is None:
            _fail(
                f"REL extrémité inconnue {relation.left_node_id}/"
                f"{relation.right_node_id}."
            )
        if left.kind == "IDEA" and right.kind == "IDEA":
            if left.node_id == right.node_id:
                _fail("REL IDEA sur elle-même.")
            idea_relations.setdefault(left.node_id, []).append(
                {"relation": relation.relation_type, "to_idea": right.node_id}
            )
            continue
        if (
            left.kind == "EXAMPLE"
            and right.kind == "IDEA"
            and relation.relation_type in _EXAMPLE_SUPPORT_RELATIONS
        ):
            if left.node_id not in example_ids:
                _fail(f"REL EXAMPLE {left.node_id} absent des examples reconstruits.")
            example_supports.setdefault(left.node_id, []).append(right.node_id)
            continue
        _fail(
            f"REL {left.kind}->{right.kind} type={relation.relation_type} "
            "non représentable dans le SourceMap canonique."
        )


def _dedupe_relations(items: Sequence[Mapping[str, str]]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for item in items:
        key = (item["relation"], item["to_idea"])
        if key in seen:
            continue
        seen.add(key)
        out.append({"relation": item["relation"], "to_idea": item["to_idea"]})
    return out


def _unique(values: Sequence[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        seen.setdefault(value, None)
    return list(seen)


def _canonical_global_metadata(
    consolidation_result: ConsolidationSemanticResult,
    table: Mapping[str, WindowIntermediateRecord],
    results_by_id: Mapping[str, WindowSemanticResult],
) -> dict:
    gm = consolidation_result.global_metadata
    intent_confidence = _unanimous_confidence(
        gm.intent_evidence, table, results_by_id, field="intent"
    )
    audience_confidence = _unanimous_confidence(
        gm.audience_evidence, table, results_by_id, field="audience"
    )
    return {
        "source_analysis": {
            "main_theme": gm.main_theme,
            "author_intent": {
                "summary": gm.author_intent,
                "confidence": intent_confidence,
                "kinds": _evidence_kind_values(gm.intent_evidence, table, "INTENT_KIND"),
            },
            "target_audience": {
                "summary": gm.target_audience,
                "confidence": audience_confidence,
                "kinds": _evidence_kind_values(
                    gm.audience_evidence, table, "AUDIENCE_KIND"
                ),
            },
        },
        "author_voice_profile": _voice_from_evidence(
            gm.voice_evidence, table, gm.author_voice_profile
        ),
    }


def _unanimous_confidence(
    evidence_ids: Sequence[str],
    table: Mapping[str, WindowIntermediateRecord],
    results_by_id: Mapping[str, WindowSemanticResult],
    *,
    field: str,
) -> str:
    values: list[str] = []
    for record_id in evidence_ids:
        record = table.get(record_id)
        if record is None:
            _fail(f"GLOBAL_METADATA évidence {record_id} absente.")
        result = results_by_id.get(record.record_id.split(":", 1)[0])
        if result is None:
            _fail(f"fenêtre de {record_id} absente.")
        if field == "intent":
            values.append(result.candidates.intent_confidence)
        else:
            values.append(result.candidates.audience_confidence)
    unique = set(values)
    if len(unique) != 1:
        _fail(
            f"confidence {field} divergente {sorted(unique)} — "
            "aucun vote local, aucun choix majoritaire."
        )
    confidence = next(iter(unique))
    if confidence not in CONFIDENCE_LEVELS:
        _fail(f"confidence {field} invalide {confidence!r}.")
    return confidence


def _evidence_kind_values(
    evidence_ids: Sequence[str],
    table: Mapping[str, WindowIntermediateRecord],
    kind: str,
) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for record_id in evidence_ids:
        record = table.get(record_id)
        if record is None:
            _fail(f"évidence {record_id} absente.")
        if record.kind != kind:
            continue
        if record.value and record.value not in seen:
            seen.add(record.value)
            values.append(record.value)
    return values


def _voice_from_evidence(
    evidence_ids: Sequence[str],
    table: Mapping[str, WindowIntermediateRecord],
    synthesis: str,
) -> dict:
    voice: dict = {
        field: [] if field in VOICE_LIST_FIELDS else "" for field in VOICE_FIELDS
    }
    scalar_seen: dict[str, str] = {}
    for record_id in evidence_ids:
        record = table.get(record_id)
        if record is None:
            _fail(f"VOICE évidence {record_id} absente.")
        if record.kind != "VOICE":
            continue
        if not record.metadata:
            _fail(f"{record_id} : VOICE sans champ.")
        field = record.metadata[0]
        if field not in VOICE_FIELDS:
            _fail(f"{record_id} : champ VOICE inconnu {field!r}.")
        if field in VOICE_LIST_FIELDS:
            if record.value:
                voice[field].append(record.value)
        elif field in VOICE_SCALAR_FIELDS:
            previous = scalar_seen.get(field)
            if previous is not None and previous != record.value:
                _fail(
                    f"VOICE {field} conflictuel ({previous!r} vs {record.value!r}) "
                    "— aucun vote local."
                )
            scalar_seen[field] = record.value
            voice[field] = record.value
    if synthesis and synthesis not in voice["distinctive_traits"]:
        voice["distinctive_traits"].append(synthesis)
    return voice


def _build_provenance(
    transcript: TranscriptInput,
    plan: WindowPlan,
    consolidation_input: ConsolidationInput,
    consolidation_result: ConsolidationSemanticResult,
    window_results: Sequence[WindowSemanticResult],
) -> AnalysisProvenance:
    first_owned = plan.windows[0]
    window_prompt_version = window_results[0].prompt_version
    window_system = build_window_system_prompt(
        transcript.primary_language, version=window_prompt_version
    )
    window_user = build_window_user_prompt(
        transcript, first_owned, version=window_prompt_version
    )
    cons_system = build_consolidation_system_prompt("en")
    cons_user = build_consolidation_user_prompt(consolidation_input)
    window_provider = window_results[0].provider_metadata.provider
    window_model = window_results[0].provider_metadata.model
    inputs = hybrid_signature_inputs_for(
        transcript,
        plan,
        consolidation_input,
        consolidation_result,
        window_prompt_sha256=window_prompt_fingerprint(window_system, window_user),
        window_schema_sha256=ultra_compact_schema_fingerprint(),
        consolidation_prompt_sha256=consolidation_prompt_fingerprint(
            cons_system, cons_user
        ),
        consolidation_schema_sha256=consolidation_schema_fingerprint(),
        window_provider=window_provider,
        window_model=window_model,
        window_max_output_tokens=None,
        consolidation_provider=consolidation_result.provider_metadata.provider,
        consolidation_model=consolidation_result.provider_metadata.model,
        consolidation_max_output_tokens=None,
        window_prompt_version=window_prompt_version,
    )
    return AnalysisProvenance(
        prompt_version=f"{window_prompt_version}+{CONSOLIDATION_PROMPT_VERSION}",
        schema_version=SOURCE_MAP_SCHEMA_VERSION,
        provider=consolidation_result.provider_metadata.provider,
        model=consolidation_result.provider_metadata.model,
        strategy=HYBRID_STRATEGY,
        signature=build_hybrid_signature(inputs),
    )


def _assert_canonical_ids(source_map: SourceMap) -> None:
    declared = source_map.declared_ids()
    for collection, ids in declared.items():
        for identifier in ids:
            if ":" in identifier or identifier.startswith("C") and identifier[1:].isdigit():
                _fail(
                    f"{collection} : identité intermédiaire fuitée {identifier!r}."
                )
            if identifier.startswith("WIN"):
                _fail(f"{collection} : WIN id canonique interdit {identifier!r}.")


def reconstruction_allowed(
    *,
    all_windows_ready: bool,
    consolidation_available: bool,
) -> bool:
    return bool(all_windows_ready and consolidation_available)


__all__ = [
    "HybridCanonicalReconstructor",
    "assert_hybrid_preconditions",
    "build_raw_canonical_candidate",
    "reconstruct_source_map",
    "reconstruction_allowed",
    "union_source_refs_in_source_order",
]
