"""
Contrats déterministes du pipeline d'analyse d'une fenêtre — 3B.7.2.

WindowSemanticResult n'est PAS un SourceMap canonique.
Les IDs WIN001:R0001 sont locaux, stables, non canoniques.
theme / intent / audience / voice sont des CANDIDATS de fenêtre.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from app.file_utils import content_hash
from app.source_analysis.errors import SourceAnalysisWindowPlanError
from app.source_analysis.transcript_input import SourceSegment, TranscriptInput
from app.source_analysis_hybrid.constants import (
    PLANNER_VERSION,
    WINDOW_PROMPT_VERSION,
    WINDOW_TRANSPORT_VERSION,
)
from app.source_analysis_hybrid.contracts import (
    WINDOW_ID_PATTERN,
    WINDOW_RECORD_ID_PATTERN,
    WindowInput,
    format_intermediate_record_id,
    src_ids_hash,
    segments_content_hash,
    window_input_hash,
)
WINDOW_RESULT_SCHEMA_VERSION = "1.0"
WINDOW_CANDIDATE_SCOPE = "WINDOW_CANDIDATE_ONLY"
OWNERSHIP_RULE = "AT_LEAST_ONE_OWNED_SRC_FOR_SUBSTANTIVE"
MIXED_OWNED_CONTEXT_ALLOWED = True
CONTEXT_ONLY_SUBSTANTIVE_FORBIDDEN = True
RECORD_ORDER_RULE = "TRANSPORT_ORDER"
STAGE_WINDOW = "source_analysis_window"
WINDOW_MAX_OUTPUT_TOKENS = 32000
WINDOW_CONNECT_TIMEOUT_SECONDS = 30.0
WINDOW_READ_TIMEOUT_SECONDS = 1800.0
WINDOW_MAX_ATTEMPTS = 1
WINDOW_RETRY = False
WINDOW_FALLBACK = None
TARGET_PROVIDER = "anthropic"
TARGET_MODEL = "claude-sonnet-5"

# Kinds qui portent une affirmation sémantique fondée sur des SRC.
SUBSTANTIVE_RECORD_KINDS = frozenset(
    {
        "TOPIC",
        "IDEA",
        "EXAMPLE",
        "REFERENCE",
        "UNCERTAINTY",
        "REPETITION",
    }
)


def assert_safe_window_id(window_id: str) -> str:
    """WIN IDs locaux uniquement — jamais un composant de chemin provider."""
    if not isinstance(window_id, str) or not WINDOW_ID_PATTERN.fullmatch(window_id):
        raise SourceAnalysisWindowPlanError(f"window_id invalide : {window_id!r}.")
    if any(part in window_id for part in ("/", "\\", "..", ":", "\x00")):
        raise SourceAnalysisWindowPlanError(
            f"window_id interdit dans un chemin : {window_id!r}."
        )
    return window_id


def assert_intermediate_record_id(record_id: str, *, window_id: str) -> str:
    if not WINDOW_RECORD_ID_PATTERN.fullmatch(record_id):
        raise SourceAnalysisWindowPlanError(
            f"identifiant intermédiaire invalide : {record_id!r}."
        )
    if not record_id.startswith(f"{window_id}:"):
        raise SourceAnalysisWindowPlanError(
            f"identifiant {record_id!r} hors fenêtre {window_id}."
        )
    return record_id


def make_window_input(
    transcript: TranscriptInput,
    *,
    owned_src_refs: Sequence[str],
    context_src_refs: Sequence[str] = (),
    window_id: str = "WIN001",
    planner_version: str = PLANNER_VERSION,
    estimated_input_tokens: int = 0,
    source_order_start: int = 0,
    source_order_stop: int | None = None,
) -> WindowInput:
    """Construit un WindowInput 3B.7.1 — aucun contrat concurrent."""
    assert_safe_window_id(window_id)
    owned = tuple(owned_src_refs)
    context = tuple(context_src_refs)
    if not owned:
        raise SourceAnalysisWindowPlanError("owned_src_refs ne peut pas être vide.")
    lookup = {segment.src_id: segment for segment in transcript.segments}
    owned_segments: list[SourceSegment] = []
    for src_id in owned:
        segment = lookup.get(src_id)
        if segment is None:
            raise SourceAnalysisWindowPlanError(
                f"SRC owned {src_id} absent du TranscriptInput."
            )
        owned_segments.append(segment)
    context_segments: list[SourceSegment] = []
    for src_id in context:
        segment = lookup.get(src_id)
        if segment is None:
            raise SourceAnalysisWindowPlanError(
                f"SRC context {src_id} absent du TranscriptInput."
            )
        if src_id in owned:
            raise SourceAnalysisWindowPlanError(
                f"SRC {src_id} à la fois owned et context."
            )
        context_segments.append(segment)
    owned_content = segments_content_hash(owned_segments)
    context_content = segments_content_hash(context_segments)
    stop = (
        source_order_stop
        if source_order_stop is not None
        else source_order_start + len(owned)
    )
    return WindowInput(
        window_id=window_id,
        transcript_id=transcript.transcript_id,
        planner_version=planner_version,
        owned_src_refs=owned,
        context_src_refs=context,
        first_owned_src_ref=owned[0],
        last_owned_src_ref=owned[-1],
        owned_src_count=len(owned),
        estimated_input_tokens=int(estimated_input_tokens),
        owned_src_ids_sha256=src_ids_hash(owned),
        owned_content_sha256=owned_content,
        context_src_ids_sha256=src_ids_hash(context),
        context_content_sha256=context_content,
        input_hash=window_input_hash(
            planner_version=planner_version,
            window_id=window_id,
            owned=owned,
            context=context,
            owned_content_sha256=owned_content,
            context_content_sha256=context_content,
        ),
        source_order_start=int(source_order_start),
        source_order_stop=int(stop),
        word_count=sum(segment.word_count for segment in owned_segments),
        content_tokens=0,
        planner_estimate_tokens=int(estimated_input_tokens),
    )


def allowed_window_source_refs(window: WindowInput) -> frozenset[str]:
    return frozenset(window.owned_src_refs) | frozenset(window.context_src_refs)


def owned_source_refs(window: WindowInput) -> frozenset[str]:
    return frozenset(window.owned_src_refs)


@dataclass(frozen=True)
class WindowCandidateMetadata:
    """theme / intent / audience — évidence locale, pas décision globale."""

    theme: str
    intent: str
    intent_confidence: str
    audience: str
    audience_confidence: str
    intent_kinds: tuple[str, ...] = ()
    audience_kinds: tuple[str, ...] = ()
    scope: str = WINDOW_CANDIDATE_SCOPE

    def to_dict(self) -> dict[str, Any]:
        return {
            "theme": self.theme,
            "intent": self.intent,
            "intent_confidence": self.intent_confidence,
            "audience": self.audience,
            "audience_confidence": self.audience_confidence,
            "intent_kinds": list(self.intent_kinds),
            "audience_kinds": list(self.audience_kinds),
            "scope": self.scope,
            "global_decision": False,
        }


@dataclass(frozen=True)
class WindowIntermediateRecord:
    """Record décodé, identité locale WINxxx:Rxxxx, ordre du transport."""

    record_id: str
    transport_index: int
    kind: str
    value: str
    source_refs: tuple[str, ...]
    links: tuple[int, ...]
    link_record_ids: tuple[str, ...]
    metadata: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "transport_index": self.transport_index,
            "kind": self.kind,
            "value": self.value,
            "source_refs": list(self.source_refs),
            "links": list(self.links),
            "link_record_ids": list(self.link_record_ids),
            "metadata": list(self.metadata),
        }


@dataclass(frozen=True)
class WindowCoverage:
    owned_src_count: int
    context_src_count: int
    cited_owned_src_count: int
    cited_context_src_count: int
    owned_src_cited: tuple[str, ...]
    owned_src_uncited: tuple[str, ...]
    context_src_cited: tuple[str, ...]
    owned_coverage_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "owned_src_count": self.owned_src_count,
            "context_src_count": self.context_src_count,
            "cited_owned_src_count": self.cited_owned_src_count,
            "cited_context_src_count": self.cited_context_src_count,
            "owned_src_cited": list(self.owned_src_cited),
            "owned_src_uncited": list(self.owned_src_uncited),
            "context_src_cited": list(self.context_src_cited),
            "owned_coverage_ratio": self.owned_coverage_ratio,
        }


@dataclass(frozen=True)
class WindowRecordStats:
    record_count: int
    topic_count: int
    idea_count: int
    relation_count: int
    example_count: int
    reference_count: int
    uncertainty_count: int
    repetition_count: int
    voice_count: int
    intent_kind_count: int
    audience_kind_count: int

    def to_dict(self) -> dict[str, int]:
        return {
            "record_count": self.record_count,
            "topic_count": self.topic_count,
            "idea_count": self.idea_count,
            "relation_count": self.relation_count,
            "example_count": self.example_count,
            "reference_count": self.reference_count,
            "uncertainty_count": self.uncertainty_count,
            "repetition_count": self.repetition_count,
            "voice_count": self.voice_count,
            "intent_kind_count": self.intent_kind_count,
            "audience_kind_count": self.audience_kind_count,
        }


@dataclass(frozen=True)
class WindowProviderMetadata:
    """
    Observabilité provider — hors identité de cache.

    latency_ms et request_id restent hors du résultat canonique : ils
    peuvent être non déterministes et ne doivent pas contaminer la
    signature ni le hash de result.json.
    """

    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    usage_source: str
    finish_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "usage_source": self.usage_source,
            "finish_reason": self.finish_reason,
        }


@dataclass(frozen=True)
class WindowSemanticResult:
    """Résultat validé d'UNE fenêtre — pas un SourceMap, pas une consolidation."""

    schema_version: str
    window_id: str
    window_input_hash: str
    window_analysis_signature: str
    transport_version: str
    prompt_version: str
    planner_version: str
    owned_src_refs: tuple[str, ...]
    context_src_refs: tuple[str, ...]
    candidates: WindowCandidateMetadata
    records: tuple[WindowIntermediateRecord, ...]
    coverage: WindowCoverage
    stats: WindowRecordStats
    provider_metadata: WindowProviderMetadata
    voice_evidence: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "window_id": self.window_id,
            "window_input_hash": self.window_input_hash,
            "window_analysis_signature": self.window_analysis_signature,
            "transport_version": self.transport_version,
            "prompt_version": self.prompt_version,
            "planner_version": self.planner_version,
            "owned_src_refs": list(self.owned_src_refs),
            "context_src_refs": list(self.context_src_refs),
            "candidates": self.candidates.to_dict(),
            "records": [record.to_dict() for record in self.records],
            "voice_evidence": dict(self.voice_evidence),
            "coverage": self.coverage.to_dict(),
            "stats": self.stats.to_dict(),
            "provider_metadata": self.provider_metadata.to_dict(),
            "canonical_sourcemap": False,
            "record_order": RECORD_ORDER_RULE,
            "ownership_rule": OWNERSHIP_RULE,
            "mixed_owned_context_allowed": MIXED_OWNED_CONTEXT_ALLOWED,
        }

    def result_sha256(self) -> str:
        from app.source_analysis_hybrid.contracts import canonical_hash

        return canonical_hash(self.to_dict())


def window_semantic_result_from_dict(payload: Mapping[str, Any]) -> WindowSemanticResult:
    """Reconstruit un WindowSemanticResult. Fail-closed si le contrat manque."""
    from app.source_analysis.errors import WindowResultValidationError

    if not isinstance(payload, Mapping):
        raise WindowResultValidationError("result.json n'est pas un objet.")
    required = (
        "schema_version",
        "window_id",
        "window_input_hash",
        "window_analysis_signature",
        "transport_version",
        "prompt_version",
        "planner_version",
        "owned_src_refs",
        "context_src_refs",
        "candidates",
        "records",
        "coverage",
        "stats",
        "provider_metadata",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        raise WindowResultValidationError(
            "result.json incomplet : " + ", ".join(missing)
        )
    candidates_raw = payload.get("candidates")
    if not isinstance(candidates_raw, Mapping):
        raise WindowResultValidationError("candidates n'est pas un objet.")
    records_raw = payload.get("records")
    if not isinstance(records_raw, list):
        raise WindowResultValidationError("records n'est pas une liste.")
    coverage_raw = payload.get("coverage")
    if not isinstance(coverage_raw, Mapping):
        raise WindowResultValidationError("coverage n'est pas un objet.")
    stats_raw = payload.get("stats")
    if not isinstance(stats_raw, Mapping):
        raise WindowResultValidationError("stats n'est pas un objet.")
    provider_raw = payload.get("provider_metadata")
    if not isinstance(provider_raw, Mapping):
        raise WindowResultValidationError("provider_metadata n'est pas un objet.")
    records: list[WindowIntermediateRecord] = []
    for item in records_raw:
        if not isinstance(item, Mapping):
            raise WindowResultValidationError("record fenêtre non objet.")
        records.append(
            WindowIntermediateRecord(
                record_id=str(item.get("record_id") or ""),
                transport_index=int(item.get("transport_index") or 0),
                kind=str(item.get("kind") or ""),
                value=str(item.get("value") or ""),
                source_refs=tuple(item.get("source_refs") or ()),
                links=tuple(int(value) for value in (item.get("links") or ())),
                link_record_ids=tuple(item.get("link_record_ids") or ()),
                metadata=tuple(item.get("metadata") or ()),
            )
        )
    return WindowSemanticResult(
        schema_version=str(payload["schema_version"]),
        window_id=str(payload["window_id"]),
        window_input_hash=str(payload["window_input_hash"]),
        window_analysis_signature=str(payload["window_analysis_signature"]),
        transport_version=str(payload["transport_version"]),
        prompt_version=str(payload["prompt_version"]),
        planner_version=str(payload["planner_version"]),
        owned_src_refs=tuple(payload["owned_src_refs"] or ()),
        context_src_refs=tuple(payload["context_src_refs"] or ()),
        candidates=WindowCandidateMetadata(
            theme=str(candidates_raw.get("theme") or ""),
            intent=str(candidates_raw.get("intent") or ""),
            intent_confidence=str(candidates_raw.get("intent_confidence") or ""),
            audience=str(candidates_raw.get("audience") or ""),
            audience_confidence=str(candidates_raw.get("audience_confidence") or ""),
            intent_kinds=tuple(candidates_raw.get("intent_kinds") or ()),
            audience_kinds=tuple(candidates_raw.get("audience_kinds") or ()),
            scope=str(candidates_raw.get("scope") or WINDOW_CANDIDATE_SCOPE),
        ),
        records=tuple(records),
        coverage=WindowCoverage(
            owned_src_count=int(coverage_raw.get("owned_src_count") or 0),
            context_src_count=int(coverage_raw.get("context_src_count") or 0),
            cited_owned_src_count=int(coverage_raw.get("cited_owned_src_count") or 0),
            cited_context_src_count=int(
                coverage_raw.get("cited_context_src_count") or 0
            ),
            owned_src_cited=tuple(coverage_raw.get("owned_src_cited") or ()),
            owned_src_uncited=tuple(coverage_raw.get("owned_src_uncited") or ()),
            context_src_cited=tuple(coverage_raw.get("context_src_cited") or ()),
            owned_coverage_ratio=float(coverage_raw.get("owned_coverage_ratio") or 0.0),
        ),
        stats=WindowRecordStats(
            record_count=int(stats_raw.get("record_count") or 0),
            topic_count=int(stats_raw.get("topic_count") or 0),
            idea_count=int(stats_raw.get("idea_count") or 0),
            relation_count=int(stats_raw.get("relation_count") or 0),
            example_count=int(stats_raw.get("example_count") or 0),
            reference_count=int(stats_raw.get("reference_count") or 0),
            uncertainty_count=int(stats_raw.get("uncertainty_count") or 0),
            repetition_count=int(stats_raw.get("repetition_count") or 0),
            voice_count=int(stats_raw.get("voice_count") or 0),
            intent_kind_count=int(stats_raw.get("intent_kind_count") or 0),
            audience_kind_count=int(stats_raw.get("audience_kind_count") or 0),
        ),
        provider_metadata=WindowProviderMetadata(
            provider=str(provider_raw.get("provider") or ""),
            model=str(provider_raw.get("model") or ""),
            input_tokens=provider_raw.get("input_tokens"),
            output_tokens=provider_raw.get("output_tokens"),
            total_tokens=provider_raw.get("total_tokens"),
            usage_source=str(provider_raw.get("usage_source") or ""),
            finish_reason=provider_raw.get("finish_reason"),
        ),
        voice_evidence=dict(payload.get("voice_evidence") or {}),
    )


def assign_intermediate_records(
    transport_records: Sequence[Mapping[str, Any]],
    *,
    window_id: str,
) -> tuple[WindowIntermediateRecord, ...]:
    """
    Identités locales dans l'ordre du transport.

    Pas de jugement sémantique : R0001 est le premier record reçu.
    """
    assert_safe_window_id(window_id)
    assigned: list[WindowIntermediateRecord] = []
    for index, item in enumerate(transport_records, start=1):
        record_id = format_intermediate_record_id(window_id, index)
        links = tuple(int(value) for value in (item.get("l") or ()))
        assigned.append(
            WindowIntermediateRecord(
                record_id=record_id,
                transport_index=index - 1,
                kind=str(item.get("k") or ""),
                value=str(item.get("v") or ""),
                source_refs=tuple(item.get("s") or ()),
                links=links,
                link_record_ids=(),
                metadata=tuple(item.get("m") or ()),
            )
        )
    remapped: list[WindowIntermediateRecord] = []
    for record in assigned:
        link_ids: list[str] = []
        for link in record.links:
            if 0 <= link < len(assigned):
                link_ids.append(assigned[link].record_id)
        remapped.append(
            WindowIntermediateRecord(
                record_id=record.record_id,
                transport_index=record.transport_index,
                kind=record.kind,
                value=record.value,
                source_refs=record.source_refs,
                links=record.links,
                link_record_ids=tuple(link_ids),
                metadata=record.metadata,
            )
        )
    return tuple(remapped)


def compute_record_stats(
    records: Sequence[WindowIntermediateRecord],
) -> WindowRecordStats:
    counts = {kind: 0 for kind in (
        "TOPIC",
        "IDEA",
        "RELATION",
        "EXAMPLE",
        "REFERENCE",
        "UNCERTAINTY",
        "REPETITION",
        "VOICE",
        "INTENT_KIND",
        "AUDIENCE_KIND",
    )}
    for record in records:
        if record.kind in counts:
            counts[record.kind] += 1
    return WindowRecordStats(
        record_count=len(records),
        topic_count=counts["TOPIC"],
        idea_count=counts["IDEA"],
        relation_count=counts["RELATION"],
        example_count=counts["EXAMPLE"],
        reference_count=counts["REFERENCE"],
        uncertainty_count=counts["UNCERTAINTY"],
        repetition_count=counts["REPETITION"],
        voice_count=counts["VOICE"],
        intent_kind_count=counts["INTENT_KIND"],
        audience_kind_count=counts["AUDIENCE_KIND"],
    )


def compute_coverage(
    window: WindowInput,
    records: Sequence[WindowIntermediateRecord],
) -> WindowCoverage:
    owned = list(window.owned_src_refs)
    context = list(window.context_src_refs)
    cited: set[str] = set()
    for record in records:
        cited.update(record.source_refs)
    owned_cited = tuple(src for src in owned if src in cited)
    owned_uncited = tuple(src for src in owned if src not in cited)
    context_cited = tuple(src for src in context if src in cited)
    ratio = (len(owned_cited) / len(owned)) if owned else 0.0
    return WindowCoverage(
        owned_src_count=len(owned),
        context_src_count=len(context),
        cited_owned_src_count=len(owned_cited),
        cited_context_src_count=len(context_cited),
        owned_src_cited=owned_cited,
        owned_src_uncited=owned_uncited,
        context_src_cited=context_cited,
        owned_coverage_ratio=ratio,
    )


__all__ = [
    "CONTEXT_ONLY_SUBSTANTIVE_FORBIDDEN",
    "MIXED_OWNED_CONTEXT_ALLOWED",
    "OWNERSHIP_RULE",
    "RECORD_ORDER_RULE",
    "STAGE_WINDOW",
    "SUBSTANTIVE_RECORD_KINDS",
    "TARGET_MODEL",
    "TARGET_PROVIDER",
    "WINDOW_CANDIDATE_SCOPE",
    "WINDOW_CONNECT_TIMEOUT_SECONDS",
    "WINDOW_FALLBACK",
    "WINDOW_MAX_ATTEMPTS",
    "WINDOW_MAX_OUTPUT_TOKENS",
    "WINDOW_PROMPT_VERSION",
    "WINDOW_READ_TIMEOUT_SECONDS",
    "WINDOW_RESULT_SCHEMA_VERSION",
    "WINDOW_RETRY",
    "WINDOW_TRANSPORT_VERSION",
    "WindowCandidateMetadata",
    "WindowCoverage",
    "WindowIntermediateRecord",
    "WindowProviderMetadata",
    "WindowRecordStats",
    "WindowSemanticResult",
    "allowed_window_source_refs",
    "assert_intermediate_record_id",
    "assert_safe_window_id",
    "assign_intermediate_records",
    "compute_coverage",
    "compute_record_stats",
    "make_window_input",
    "owned_source_refs",
    "window_semantic_result_from_dict",
]
