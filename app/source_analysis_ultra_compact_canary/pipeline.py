"""
Pipeline local post-appel : semantic-transport-v1 → decoder → normalizer → validator.

Aucune réparation JSON / regex / LLM. Le validateur de production n'est pas
affaibli : on lui passe une vue TranscriptInput limitée à l'extrait canary.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from app.source_analysis.errors import (
    SourceMapEditorialLeakError,
    SourceMapValidationError,
)
from app.source_analysis.models import (
    AnalysisProvenance,
    SourceMap,
    forbidden_editorial_fields,
)
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.semantic_transport_decoder import decode_to_canonical_raw
from app.source_analysis.transcript_input import SourceSegment, TranscriptInput
from app.source_analysis.ultra_compact_schema import (
    ULTRA_RECORD_FIELDS,
    ULTRA_ROOT_FIELDS,
    looks_like_ultra_transport,
)
from app.source_analysis.validator import (
    ensure_valid_source_map,
    validate_source_map,
)

_SRC_RE = __import__("re").compile(r"^SRC[0-9]{6}$")


@dataclass
class PipelineOutcome:
    transport_parse: str = "N/A"
    local_semantic: str = "N/A"
    source_refs_in_canary: str = "N/A"
    link_validation: str = "N/A"
    decoder: str = "N/A"
    reconstruction: str = "N/A"
    normalization: str = "N/A"
    canonical_validation: str = "N/A"
    editorial_leakage: str = "N/A"
    raw_canonical: dict | None = None
    source_map: SourceMap | None = None
    errors: list[str] | None = None
    record_kinds: list[str] | None = None
    topic_ids: list[str] | None = None
    idea_ids: list[str] | None = None
    example_ids: list[str] | None = None
    reference_ids: list[str] | None = None
    uncertainty_ids: list[str] | None = None
    repetition_ids: list[str] | None = None
    all_source_refs: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "transport_parse": self.transport_parse,
            "local_semantic": self.local_semantic,
            "source_refs_in_canary": self.source_refs_in_canary,
            "link_validation": self.link_validation,
            "decoder": self.decoder,
            "reconstruction": self.reconstruction,
            "normalization": self.normalization,
            "canonical_validation": self.canonical_validation,
            "editorial_leakage": self.editorial_leakage,
            "errors": list(self.errors or []),
            "record_kinds": list(self.record_kinds or []),
            "canonical_ids": {
                "topics": list(self.topic_ids or []),
                "ideas": list(self.idea_ids or []),
                "examples": list(self.example_ids or []),
                "references": list(self.reference_ids or []),
                "uncertainties": list(self.uncertainty_ids or []),
                "repetitions": list(self.repetition_ids or []),
            },
        }


def slice_transcript(
    transcript: TranscriptInput,
    segments: tuple[SourceSegment, ...] | list[SourceSegment],
) -> TranscriptInput:
    """Vue lecture seule limitée à l'extrait — le validateur global reste intact."""
    return replace(transcript, segments=tuple(segments))


def collect_transport_source_refs(payload: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for item in payload.get("records") or []:
        if isinstance(item, Mapping):
            refs.extend(str(ref) for ref in (item.get("s") or []))
    return refs


def collect_record_kinds(payload: Mapping[str, Any]) -> list[str]:
    kinds: list[str] = []
    for item in payload.get("records") or []:
        if isinstance(item, Mapping) and isinstance(item.get("k"), str):
            kinds.append(item["k"].strip())
    return kinds


def _classify_decoder_errors(errors: list[str]) -> dict[str, bool]:
    text = " | ".join(errors)
    return {
        "source_refs": "source_ref" in text or "s (source_refs)" in text,
        "links": "index " in text and "hors plage" in text
        or "ne peut lier" in text
        or "auto-lien" in text
        or "relation dupliquée" in text
        or "l doit être vide" in text,
        "semantic": any(
            marker in text
            for marker in (
                "kind inconnu",
                "invalide",
                "vide",
                "exige",
            )
        ),
    }


def run_local_pipeline(
    parsed: Any,
    transcript: TranscriptInput,
    selected: tuple[SourceSegment, ...],
    *,
    provenance: AnalysisProvenance,
) -> PipelineOutcome:
    """
    semantic-transport-v1 → decode_to_canonical_raw → normalize → validate.

    Parser et decoder de production : aucun format parallèle.
    """
    outcome = PipelineOutcome()
    allowed = {segment.src_id for segment in selected}
    sliced = slice_transcript(transcript, selected)

    if not isinstance(parsed, Mapping) or not looks_like_ultra_transport(parsed):
        outcome.transport_parse = "FAIL"
        outcome.errors = [
            f"réponse provider inattendue : {type(parsed).__name__}"
        ]
        return outcome

    missing_root = [name for name in ULTRA_ROOT_FIELDS if name not in parsed]
    records = parsed.get("records")
    record_shape_ok = isinstance(records, list) and all(
        isinstance(item, Mapping)
        and all(field in item for field in ULTRA_RECORD_FIELDS)
        for item in records
    )
    if missing_root or not record_shape_ok:
        outcome.transport_parse = "FAIL"
        outcome.errors = [
            "champs racine ou forme de record manquants : "
            + ", ".join(missing_root or ["records.k/v/s/l/m"])
        ]
        return outcome

    outcome.transport_parse = "PASS"
    outcome.record_kinds = collect_record_kinds(parsed)
    outcome.all_source_refs = collect_transport_source_refs(parsed)

    leaked = forbidden_editorial_fields(parsed)
    if leaked:
        outcome.editorial_leakage = "FAIL"
        outcome.errors = [f"fuite éditoriale : {', '.join(leaked)}"]
        return outcome

    try:
        raw = decode_to_canonical_raw(parsed, allowed_source_refs=allowed)
    except SourceMapEditorialLeakError as exc:
        outcome.editorial_leakage = "FAIL"
        outcome.decoder = "FAIL"
        outcome.errors = list(getattr(exc, "errors", [str(exc)]))
        return outcome
    except SourceMapValidationError as exc:
        errors = list(exc.errors)
        flags = _classify_decoder_errors(errors)
        outcome.decoder = "FAIL"
        outcome.local_semantic = "FAIL" if flags["semantic"] else "PASS"
        outcome.source_refs_in_canary = "FAIL" if flags["source_refs"] else "PASS"
        outcome.link_validation = "FAIL" if flags["links"] else "PASS"
        outcome.errors = errors
        return outcome

    outcome.decoder = "PASS"
    outcome.reconstruction = "PASS"
    outcome.local_semantic = "PASS"
    outcome.source_refs_in_canary = "PASS"
    outcome.link_validation = "PASS"
    outcome.editorial_leakage = "PASS"
    outcome.raw_canonical = raw

    try:
        source_map = normalize_source_map(raw, sliced, provenance=provenance)
    except Exception as exc:
        outcome.normalization = "FAIL"
        outcome.errors = [str(exc)]
        return outcome

    outcome.normalization = "PASS"
    outcome.source_map = source_map
    outcome.topic_ids = [topic.topic_id for topic in source_map.topics]
    outcome.idea_ids = [idea.idea_id for idea in source_map.ideas]
    outcome.example_ids = [item.example_id for item in source_map.examples]
    outcome.reference_ids = [item.reference_id for item in source_map.references]
    outcome.uncertainty_ids = [item.uncertainty_id for item in source_map.uncertainties]
    outcome.repetition_ids = [item.repetition_id for item in source_map.repetitions]

    leaked_map = forbidden_editorial_fields(source_map.to_dict())
    if leaked_map:
        outcome.editorial_leakage = "FAIL"
        outcome.errors = [f"fuite éditoriale SourceMap : {', '.join(leaked_map)}"]
        return outcome

    try:
        ensure_valid_source_map(source_map, sliced)
    except SourceMapValidationError as exc:
        leftover = validate_source_map(source_map, sliced)
        outcome.canonical_validation = "FAIL"
        outcome.errors = leftover or list(exc.errors)
        return outcome

    outcome.canonical_validation = "PASS"
    return outcome
