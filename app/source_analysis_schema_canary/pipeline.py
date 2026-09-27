"""
Pipeline local post-appel : parse compact → reconstruction → normalizer → validator.

Aucune réparation JSON / regex / LLM. Le validateur de production n'est pas
affaibli : on lui passe une vue TranscriptInput limitée à l'extrait canary.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from app.source_analysis.compact_reconstructor import reconstruct_to_canonical_raw
from app.source_analysis.compact_schema import COMPACT_REQUIRED_FIELDS
from app.source_analysis.errors import (
    SourceMapEditorialLeakError,
    SourceMapValidationError,
)
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
    UNCERTAINTY_KINDS,
    AnalysisProvenance,
    SourceMap,
)
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.transcript_input import SourceSegment, TranscriptInput
from app.source_analysis.validator import (
    ensure_valid_source_map,
    validate_source_map,
)

_SRC_RE = __import__("re").compile(r"^SRC[0-9]{6}$")
_COLLECTIONS = (
    "topics",
    "ideas",
    "examples",
    "references",
    "uncertainties",
    "repetitions",
)


@dataclass
class PipelineOutcome:
    compact_parse: str = "N/A"
    compact_semantic: str = "N/A"
    source_refs_in_canary: str = "N/A"
    index_validation: str = "N/A"
    reconstruction: str = "N/A"
    normalization: str = "N/A"
    canonical_validation: str = "N/A"
    raw_canonical: dict | None = None
    source_map: SourceMap | None = None
    errors: list[str] | None = None
    topic_ids: list[str] | None = None
    idea_ids: list[str] | None = None
    example_ids: list[str] | None = None
    reference_ids: list[str] | None = None
    uncertainty_ids: list[str] | None = None
    repetition_ids: list[str] | None = None
    all_source_refs: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "compact_parse": self.compact_parse,
            "compact_semantic": self.compact_semantic,
            "source_refs_in_canary": self.source_refs_in_canary,
            "index_validation": self.index_validation,
            "reconstruction": self.reconstruction,
            "normalization": self.normalization,
            "canonical_validation": self.canonical_validation,
            "errors": list(self.errors or []),
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


def collect_source_refs(payload: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for name in _COLLECTIONS:
        for item in payload.get(name) or []:
            if isinstance(item, Mapping):
                refs.extend(str(ref) for ref in (item.get("source_refs") or []))
    return refs


def validate_compact_payload(payload: Mapping[str, Any]) -> list[str]:
    """Champs requis, enums, intervalles de confiance — sans reconstruction."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return [f"réponse compacte inattendue : {type(payload).__name__}"]

    for name in COMPACT_REQUIRED_FIELDS:
        if name not in payload:
            errors.append(f"champ compact requis absent : {name}")

    header = payload.get("source_analysis")
    if not isinstance(header, Mapping):
        errors.append("source_analysis : un objet est attendu")
        return errors

    if not str(header.get("main_theme") or "").strip():
        errors.append("source_analysis.main_theme vide")

    for field in ("author_intent", "target_audience"):
        intent = header.get(field)
        if not isinstance(intent, Mapping):
            errors.append(f"{field} : un objet est attendu")
            continue
        confidence = intent.get("confidence")
        if confidence not in CONFIDENCE_LEVELS:
            errors.append(f"{field}.confidence invalide : {confidence!r}")

    for position, item in enumerate(payload.get("ideas") or []):
        if not isinstance(item, Mapping):
            continue
        if item.get("kind") not in IDEA_KINDS:
            errors.append(f"ideas[{position}].kind invalide")
        if item.get("importance") not in IMPORTANCE_LEVELS:
            errors.append(f"ideas[{position}].importance invalide")

    for position, item in enumerate(payload.get("examples") or []):
        if isinstance(item, Mapping) and item.get("kind") not in EXAMPLE_KINDS:
            errors.append(f"examples[{position}].kind invalide")

    for position, item in enumerate(payload.get("references") or []):
        if not isinstance(item, Mapping):
            continue
        if item.get("kind") not in REFERENCE_KINDS:
            errors.append(f"references[{position}].kind invalide")
        if item.get("completeness") not in REFERENCE_COMPLETENESS:
            errors.append(f"references[{position}].completeness invalide")

    for position, item in enumerate(payload.get("uncertainties") or []):
        if not isinstance(item, Mapping):
            continue
        if item.get("kind") not in UNCERTAINTY_KINDS:
            errors.append(f"uncertainties[{position}].kind invalide")
        if item.get("severity") not in SEVERITY_LEVELS:
            errors.append(f"uncertainties[{position}].severity invalide")

    for position, item in enumerate(payload.get("repetitions") or []):
        if isinstance(item, Mapping) and item.get("character") not in REPETITION_CHARACTERS:
            errors.append(f"repetitions[{position}].character invalide")

    for position, item in enumerate(payload.get("relations") or []):
        if isinstance(item, Mapping) and item.get("relation") not in RELATION_KINDS:
            errors.append(f"relations[{position}].relation invalide")

    return errors


def validate_indexes(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    topic_count = len(payload.get("topics") or [])
    idea_count = len(payload.get("ideas") or [])

    def _check(raw: Any, bound: int, context: str) -> None:
        if raw is None:
            return
        if not isinstance(raw, list):
            errors.append(f"{context} : une liste d'entiers est attendue")
            return
        for value in raw:
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"{context} : un entier est attendu")
            elif bound <= 0 or value < 0 or value >= bound:
                errors.append(f"{context} : index {value} hors plage")

    for position, item in enumerate(payload.get("ideas") or []):
        if isinstance(item, Mapping):
            _check(item.get("topic_indexes"), topic_count, f"ideas[{position}].topic_indexes")

    for position, item in enumerate(payload.get("relations") or []):
        if not isinstance(item, Mapping):
            continue
        _check([item.get("from")], idea_count, f"relations[{position}].from")
        _check([item.get("to")], idea_count, f"relations[{position}].to")

    for position, item in enumerate(payload.get("examples") or []):
        if isinstance(item, Mapping):
            _check(item.get("idea_indexes"), idea_count, f"examples[{position}].idea_indexes")

    for position, item in enumerate(payload.get("repetitions") or []):
        if isinstance(item, Mapping):
            _check(item.get("idea_indexes"), idea_count, f"repetitions[{position}].idea_indexes")

    return errors


def validate_source_refs_in_canary(
    payload: Mapping[str, Any],
    allowed: set[str],
) -> list[str]:
    errors: list[str] = []
    for ref in collect_source_refs(payload):
        if not _SRC_RE.match(ref):
            errors.append(f"source_ref mal formé : {ref}")
        elif ref not in allowed:
            errors.append(f"source_ref hors extrait canary : {ref}")
    return errors


def run_local_pipeline(
    parsed: Any,
    transcript: TranscriptInput,
    selected: tuple[SourceSegment, ...],
    *,
    provenance: AnalysisProvenance,
) -> PipelineOutcome:
    """Parse compact → reconstruct → normalize → validate (vue extraite)."""
    outcome = PipelineOutcome()
    allowed = {segment.src_id for segment in selected}
    sliced = slice_transcript(transcript, selected)

    if not isinstance(parsed, Mapping):
        outcome.compact_parse = "FAIL"
        outcome.errors = [
            f"réponse provider inattendue : {type(parsed).__name__}"
        ]
        return outcome

    outcome.compact_parse = "PASS"
    semantic = validate_compact_payload(parsed)
    outcome.compact_semantic = "FAIL" if semantic else "PASS"

    ref_errors = validate_source_refs_in_canary(parsed, allowed)
    outcome.source_refs_in_canary = "FAIL" if ref_errors else "PASS"
    outcome.all_source_refs = collect_source_refs(parsed)

    index_errors = validate_indexes(parsed)
    outcome.index_validation = "FAIL" if index_errors else "PASS"

    pre_errors = semantic + ref_errors + index_errors
    if pre_errors:
        outcome.errors = pre_errors
        return outcome

    try:
        raw = reconstruct_to_canonical_raw(parsed)
    except (SourceMapValidationError, SourceMapEditorialLeakError) as exc:
        outcome.reconstruction = "FAIL"
        outcome.errors = list(getattr(exc, "errors", [str(exc)]))
        return outcome

    outcome.reconstruction = "PASS"
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

    try:
        ensure_valid_source_map(source_map, sliced)
    except SourceMapValidationError as exc:
        leftover = validate_source_map(source_map, sliced)
        outcome.canonical_validation = "FAIL"
        outcome.errors = leftover or list(exc.errors)
        return outcome

    outcome.canonical_validation = "PASS"
    return outcome
