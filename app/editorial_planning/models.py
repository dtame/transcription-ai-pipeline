"""
Contrat interne de editorial_plan.json — Phase 4.

Ce module définit CE QUE LE PLAN ÉDITORIAL EST. Pas d'appel IA, pas de
fichier, pas de prompt.

    Source Analyzer     = ce que la source contient
    Editorial Planner   = comment organiser ce contenu en livre
    Book Generator      = comment l'exprimer en manuscrit

Hiérarchie figée : BOOK -> CHAPTER -> SECTION.
Aucun paragraphe de manuscrit. Les fenêtres techniques ne sont pas des
unités éditoriales.

Les identifiants CH/SEC sont assignés localement, jamais repris du provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from app.editorial_planning.constants import (
    EDITORIAL_PLAN_SCHEMA_VERSION,
    IDEA_DISPOSITIONS,
)

_EMPTY = ""


def format_chapter_id(index: int) -> str:
    """Identifiant de chapitre : CH001, CH002, …"""
    return f"CH{index:03d}"


def format_section_id(index: int) -> str:
    """Identifiant de section, global dans l'ordre éditorial : SEC001, …"""
    return f"SEC{index:03d}"


def _read_text(data: Mapping, key: str) -> str:
    if not isinstance(data, Mapping):
        return _EMPTY
    value = data.get(key)
    if value is None:
        return _EMPTY
    return value.strip() if isinstance(value, str) else str(value).strip()


def _read_text_tuple(data: Mapping, key: str) -> tuple[str, ...]:
    if not isinstance(data, Mapping):
        return ()
    value = data.get(key)
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(
        item.strip() if isinstance(item, str) else str(item)
        for item in value
        if item is not None
    )


def _read_mapping(data: Mapping, key: str) -> Mapping:
    if not isinstance(data, Mapping):
        return {}
    value = data.get(key)
    return value if isinstance(value, Mapping) else {}


def _read_int(data: Mapping, key: str) -> int:
    if not isinstance(data, Mapping):
        return 0
    try:
        return int(data.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _read_float(data: Mapping, key: str) -> float:
    if not isinstance(data, Mapping):
        return 0.0
    try:
        return float(data.get(key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _read_bool(data: Mapping, key: str, default: bool = False) -> bool:
    if not isinstance(data, Mapping):
        return default
    value = data.get(key, default)
    return bool(value)


def _read_items(data: Mapping, key: str, factory) -> tuple:
    if not isinstance(data, Mapping):
        return ()
    value = data.get(key)
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(
        factory.from_dict(item) for item in value if isinstance(item, Mapping)
    )


@dataclass(frozen=True)
class BookConcept:
    """Promesse, sujet, parcours lecteur, progression — ancrés dans le SourceMap."""

    purpose: str
    core_subject: str
    reader_journey: str
    editorial_progression: str

    def to_dict(self) -> dict:
        return {
            "purpose": self.purpose,
            "core_subject": self.core_subject,
            "reader_journey": self.reader_journey,
            "editorial_progression": self.editorial_progression,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "BookConcept":
        return cls(
            purpose=_read_text(data, "purpose"),
            core_subject=_read_text(data, "core_subject"),
            reader_journey=_read_text(data, "reader_journey"),
            editorial_progression=_read_text(data, "editorial_progression"),
        )


@dataclass(frozen=True)
class TitleCandidate:
    """Proposition éditoriale, jamais un fait de source."""

    title: str
    rationale: str
    is_editorial_construct: bool = True

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "rationale": self.rationale,
            "is_editorial_construct": True,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "TitleCandidate":
        return cls(
            title=_read_text(data, "title"),
            rationale=_read_text(data, "rationale"),
            is_editorial_construct=True,
        )


@dataclass(frozen=True)
class EditorialAction:
    """Décision d'organisation. N'autorise aucune invention sémantique."""

    kind: str
    note: str = ""
    target_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "note": self.note,
            "target_refs": list(self.target_refs),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "EditorialAction":
        return cls(
            kind=_read_text(data, "kind"),
            note=_read_text(data, "note"),
            target_refs=_read_text_tuple(data, "target_refs"),
        )


@dataclass(frozen=True)
class EditorialSection:
    """Unité éditoriale minimale. Pas de prose de manuscrit."""

    section_id: str
    working_title: str
    purpose: str
    idea_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    example_refs: tuple[str, ...] = ()
    reference_refs: tuple[str, ...] = ()
    uncertainty_refs: tuple[str, ...] = ()
    repetition_refs: tuple[str, ...] = ()
    topic_refs: tuple[str, ...] = ()
    editorial_actions: tuple[EditorialAction, ...] = ()

    def to_dict(self) -> dict:
        return {
            "section_id": self.section_id,
            "working_title": self.working_title,
            "purpose": self.purpose,
            "idea_refs": list(self.idea_refs),
            "source_refs": list(self.source_refs),
            "example_refs": list(self.example_refs),
            "reference_refs": list(self.reference_refs),
            "uncertainty_refs": list(self.uncertainty_refs),
            "repetition_refs": list(self.repetition_refs),
            "topic_refs": list(self.topic_refs),
            "editorial_actions": [item.to_dict() for item in self.editorial_actions],
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "EditorialSection":
        return cls(
            section_id=_read_text(data, "section_id"),
            working_title=_read_text(data, "working_title"),
            purpose=_read_text(data, "purpose"),
            idea_refs=_read_text_tuple(data, "idea_refs"),
            source_refs=_read_text_tuple(data, "source_refs"),
            example_refs=_read_text_tuple(data, "example_refs"),
            reference_refs=_read_text_tuple(data, "reference_refs"),
            uncertainty_refs=_read_text_tuple(data, "uncertainty_refs"),
            repetition_refs=_read_text_tuple(data, "repetition_refs"),
            topic_refs=_read_text_tuple(data, "topic_refs"),
            editorial_actions=_read_items(data, "editorial_actions", EditorialAction),
        )


@dataclass(frozen=True)
class EditorialChapter:
    """Chapitre éditorial. Contient des sections, jamais des chapitres."""

    chapter_id: str
    working_title: str
    purpose: str
    summary: str
    idea_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    topic_refs: tuple[str, ...] = ()
    uncertainty_refs: tuple[str, ...] = ()
    sections: tuple[EditorialSection, ...] = ()
    editorial_actions: tuple[EditorialAction, ...] = ()

    def to_dict(self) -> dict:
        return {
            "chapter_id": self.chapter_id,
            "working_title": self.working_title,
            "purpose": self.purpose,
            "summary": self.summary,
            "idea_refs": list(self.idea_refs),
            "source_refs": list(self.source_refs),
            "topic_refs": list(self.topic_refs),
            "uncertainty_refs": list(self.uncertainty_refs),
            "sections": [item.to_dict() for item in self.sections],
            "editorial_actions": [item.to_dict() for item in self.editorial_actions],
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "EditorialChapter":
        return cls(
            chapter_id=_read_text(data, "chapter_id"),
            working_title=_read_text(data, "working_title"),
            purpose=_read_text(data, "purpose"),
            summary=_read_text(data, "summary"),
            idea_refs=_read_text_tuple(data, "idea_refs"),
            source_refs=_read_text_tuple(data, "source_refs"),
            topic_refs=_read_text_tuple(data, "topic_refs"),
            uncertainty_refs=_read_text_tuple(data, "uncertainty_refs"),
            sections=_read_items(data, "sections", EditorialSection),
            editorial_actions=_read_items(data, "editorial_actions", EditorialAction),
        )


@dataclass(frozen=True)
class IdeaDisposition:
    """Disposition explicite d'une IDEA du SourceMap. L'omission silencieuse est interdite."""

    idea_id: str
    disposition: str
    primary_section_id: str = ""
    additional_section_ids: tuple[str, ...] = ()
    reason: str = ""
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "idea_id": self.idea_id,
            "disposition": self.disposition,
            "primary_section_id": self.primary_section_id,
            "additional_section_ids": list(self.additional_section_ids),
            "reason": self.reason,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "IdeaDisposition":
        disposition = _read_text(data, "disposition")
        if disposition not in IDEA_DISPOSITIONS:
            disposition = disposition
        return cls(
            idea_id=_read_text(data, "idea_id"),
            disposition=disposition,
            primary_section_id=_read_text(data, "primary_section_id"),
            additional_section_ids=_read_text_tuple(data, "additional_section_ids"),
            reason=_read_text(data, "reason"),
            note=_read_text(data, "note"),
        )


@dataclass(frozen=True)
class SourceMapIdentity:
    """Lien déterministe vers le SourceMap consommé en lecture seule."""

    sha256: str
    bytes: int
    schema_version: str
    project: str
    topic_count: int
    idea_count: int
    example_count: int
    reference_count: int
    uncertainty_count: int
    repetition_count: int

    def to_dict(self) -> dict:
        return {
            "sha256": self.sha256,
            "bytes": self.bytes,
            "schema_version": self.schema_version,
            "project": self.project,
            "inventory": {
                "topic_count": self.topic_count,
                "idea_count": self.idea_count,
                "example_count": self.example_count,
                "reference_count": self.reference_count,
                "uncertainty_count": self.uncertainty_count,
                "repetition_count": self.repetition_count,
            },
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "SourceMapIdentity":
        inventory = _read_mapping(data, "inventory")
        return cls(
            sha256=_read_text(data, "sha256"),
            bytes=_read_int(data, "bytes"),
            schema_version=_read_text(data, "schema_version"),
            project=_read_text(data, "project"),
            topic_count=_read_int(inventory, "topic_count"),
            idea_count=_read_int(inventory, "idea_count"),
            example_count=_read_int(inventory, "example_count"),
            reference_count=_read_int(inventory, "reference_count"),
            uncertainty_count=_read_int(inventory, "uncertainty_count"),
            repetition_count=_read_int(inventory, "repetition_count"),
        )


@dataclass(frozen=True)
class UncertaintyHandling:
    """Les UNC restent visibles. Le planner ne les convertit pas en certitude."""

    policy: str
    assigned_uncertainty_refs: tuple[str, ...] = ()
    unassigned_uncertainty_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "policy": self.policy,
            "assigned_uncertainty_refs": list(self.assigned_uncertainty_refs),
            "unassigned_uncertainty_refs": list(self.unassigned_uncertainty_refs),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "UncertaintyHandling":
        return cls(
            policy=_read_text(data, "policy"),
            assigned_uncertainty_refs=_read_text_tuple(
                data, "assigned_uncertainty_refs"
            ),
            unassigned_uncertainty_refs=_read_text_tuple(
                data, "unassigned_uncertainty_refs"
            ),
        )


@dataclass(frozen=True)
class SourceCoverage:
    """Provenance SRC dérivée des unités assignées, pas un ordre éditorial."""

    referenced_source_refs: tuple[str, ...] = ()
    referenced_source_count: int = 0

    def to_dict(self) -> dict:
        return {
            "referenced_source_count": self.referenced_source_count,
            "referenced_source_refs": list(self.referenced_source_refs),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "SourceCoverage":
        refs = _read_text_tuple(data, "referenced_source_refs")
        count = _read_int(data, "referenced_source_count") or len(refs)
        return cls(referenced_source_refs=refs, referenced_source_count=count)


@dataclass(frozen=True)
class EditorialPlanStats:
    """Compteurs dérivés. Aucun horodatage."""

    chapter_count: int
    section_count: int
    assigned_idea_count: int
    deferred_idea_count: int
    excluded_idea_count: int
    reused_idea_count: int
    example_assigned_count: int
    reference_assigned_count: int
    uncertainty_assigned_count: int
    repetition_assigned_count: int
    title_candidate_count: int

    def to_dict(self) -> dict:
        return {
            "chapter_count": self.chapter_count,
            "section_count": self.section_count,
            "assigned_idea_count": self.assigned_idea_count,
            "deferred_idea_count": self.deferred_idea_count,
            "excluded_idea_count": self.excluded_idea_count,
            "reused_idea_count": self.reused_idea_count,
            "example_assigned_count": self.example_assigned_count,
            "reference_assigned_count": self.reference_assigned_count,
            "uncertainty_assigned_count": self.uncertainty_assigned_count,
            "repetition_assigned_count": self.repetition_assigned_count,
            "title_candidate_count": self.title_candidate_count,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "EditorialPlanStats":
        return cls(
            chapter_count=_read_int(data, "chapter_count"),
            section_count=_read_int(data, "section_count"),
            assigned_idea_count=_read_int(data, "assigned_idea_count"),
            deferred_idea_count=_read_int(data, "deferred_idea_count"),
            excluded_idea_count=_read_int(data, "excluded_idea_count"),
            reused_idea_count=_read_int(data, "reused_idea_count"),
            example_assigned_count=_read_int(data, "example_assigned_count"),
            reference_assigned_count=_read_int(data, "reference_assigned_count"),
            uncertainty_assigned_count=_read_int(data, "uncertainty_assigned_count"),
            repetition_assigned_count=_read_int(data, "repetition_assigned_count"),
            title_candidate_count=_read_int(data, "title_candidate_count"),
        )


@dataclass(frozen=True)
class EditorialPlanMetadata:
    """
    Provenance du plan. Déterministe : versions, provider, modèle, thinking,
    signature. Pas de generated_at — l'identité sémantique doit être rejouable.
    """

    prompt_version: str
    transport_version: str
    schema_version: str
    coverage_policy_version: str
    validator_version: str
    provider: str
    model: str
    strategy: str
    thinking_mode: str
    effort: str
    signature: str
    source_map_path: str = ""

    def to_dict(self) -> dict:
        return {
            "prompt_version": self.prompt_version,
            "transport_version": self.transport_version,
            "schema_version": self.schema_version,
            "coverage_policy_version": self.coverage_policy_version,
            "validator_version": self.validator_version,
            "provider": self.provider,
            "model": self.model,
            "strategy": self.strategy,
            "thinking_mode": self.thinking_mode,
            "effort": self.effort,
            "signature": self.signature,
            "source_map_path": self.source_map_path,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "EditorialPlanMetadata":
        return cls(
            prompt_version=_read_text(data, "prompt_version"),
            transport_version=_read_text(data, "transport_version"),
            schema_version=_read_text(data, "schema_version"),
            coverage_policy_version=_read_text(data, "coverage_policy_version"),
            validator_version=_read_text(data, "validator_version"),
            provider=_read_text(data, "provider"),
            model=_read_text(data, "model"),
            strategy=_read_text(data, "strategy"),
            thinking_mode=_read_text(data, "thinking_mode"),
            effort=_read_text(data, "effort"),
            signature=_read_text(data, "signature"),
            source_map_path=_read_text(data, "source_map_path"),
        )


@dataclass(frozen=True)
class EditorialPlan:
    """Plan de livre publiable. to_dict() fixe l'ordre de lecture."""

    project_name: str
    source_map: SourceMapIdentity
    book_concept: BookConcept
    title_candidates: tuple[TitleCandidate, ...]
    selected_title: str
    subtitle: str
    editorial_angle: str
    target_reader: str
    editorial_strategy: str
    chapters: tuple[EditorialChapter, ...]
    idea_coverage: tuple[IdeaDisposition, ...]
    source_coverage: SourceCoverage
    uncertainty_handling: UncertaintyHandling
    editorial_actions: tuple[EditorialAction, ...]
    stats: EditorialPlanStats
    planner: EditorialPlanMetadata
    schema_version: str = EDITORIAL_PLAN_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "project": {"name": self.project_name},
            "source_map": self.source_map.to_dict(),
            "book_concept": self.book_concept.to_dict(),
            "title_candidates": [item.to_dict() for item in self.title_candidates],
            "selected_title": self.selected_title,
            "subtitle": self.subtitle,
            "editorial_angle": self.editorial_angle,
            "target_reader": self.target_reader,
            "editorial_strategy": self.editorial_strategy,
            "chapters": [item.to_dict() for item in self.chapters],
            "idea_coverage": [item.to_dict() for item in self.idea_coverage],
            "source_coverage": self.source_coverage.to_dict(),
            "uncertainty_handling": self.uncertainty_handling.to_dict(),
            "editorial_actions": [item.to_dict() for item in self.editorial_actions],
            "stats": self.stats.to_dict(),
            "planner": self.planner.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "EditorialPlan":
        return cls(
            schema_version=_read_text(data, "schema_version"),
            project_name=_read_text(_read_mapping(data, "project"), "name"),
            source_map=SourceMapIdentity.from_dict(_read_mapping(data, "source_map")),
            book_concept=BookConcept.from_dict(_read_mapping(data, "book_concept")),
            title_candidates=_read_items(data, "title_candidates", TitleCandidate),
            selected_title=_read_text(data, "selected_title"),
            subtitle=_read_text(data, "subtitle"),
            editorial_angle=_read_text(data, "editorial_angle"),
            target_reader=_read_text(data, "target_reader"),
            editorial_strategy=_read_text(data, "editorial_strategy"),
            chapters=_read_items(data, "chapters", EditorialChapter),
            idea_coverage=_read_items(data, "idea_coverage", IdeaDisposition),
            source_coverage=SourceCoverage.from_dict(
                _read_mapping(data, "source_coverage")
            ),
            uncertainty_handling=UncertaintyHandling.from_dict(
                _read_mapping(data, "uncertainty_handling")
            ),
            editorial_actions=_read_items(data, "editorial_actions", EditorialAction),
            stats=EditorialPlanStats.from_dict(_read_mapping(data, "stats")),
            planner=EditorialPlanMetadata.from_dict(_read_mapping(data, "planner")),
        )

    def all_sections(self) -> tuple[EditorialSection, ...]:
        sections: list[EditorialSection] = []
        for chapter in self.chapters:
            sections.extend(chapter.sections)
        return tuple(sections)

    def assigned_idea_ids(self) -> tuple[str, ...]:
        seen: dict[str, None] = {}
        for section in self.all_sections():
            for idea_id in section.idea_refs:
                seen.setdefault(idea_id, None)
        return tuple(seen)


FORBIDDEN_MANUSCRIPT_FIELDS = (
    "paragraphs",
    "paragraph",
    "manuscript",
    "prose",
    "body_text",
    "book_json",
    "pages",
)

FORBIDDEN_TECHNICAL_FIELDS = (
    "analysis_window",
    "chunk_id",
    "chunk_index",
    "chunks",
    "technical_window",
    "window_id",
    "windows",
    "win_id",
)

FORBIDDEN_NESTED_HIERARCHY_FIELDS = (
    "book_parts",
    "book_part",
    "subchapters",
    "subchapter",
    "subsections",
)


def forbidden_plan_structure_keys() -> frozenset[str]:
    return frozenset(
        FORBIDDEN_MANUSCRIPT_FIELDS
        + FORBIDDEN_TECHNICAL_FIELDS
        + FORBIDDEN_NESTED_HIERARCHY_FIELDS
    )


def scan_forbidden_plan_structure(payload: object) -> tuple[str, ...]:
    keys = forbidden_plan_structure_keys()
    found: set[str] = set()

    def _walk(node: object) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                name = str(key)
                if name in keys:
                    found.add(name)
                _walk(value)
        elif isinstance(node, (list, tuple)):
            for item in node:
                _walk(item)

    _walk(payload)
    return tuple(name for name in sorted(keys) if name in found)
