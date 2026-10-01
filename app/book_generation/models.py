"""
Canonical Book / Chapter / Section / Paragraph models.

Semantic manuscript only. No Word/PDF/layout fields.
Canonical paragraph IDs are assigned locally during assembly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.book_generation.constants import (
    BOOK_SCHEMA_VERSION,
    PARAGRAPH_KIND_CONNECTIVE,
    PARAGRAPH_KIND_SUBSTANTIVE,
    TITLE_STATUS_WORKING,
)

_EMPTY = ""


def format_paragraph_id(index: int) -> str:
    """Canonical paragraph ID: P000001, P000002, …"""
    return f"P{index:06d}"


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
class EvidenceRef:
    """Compact provenance handle supplied to / returned by the provider."""

    handle: str
    kind: str = ""

    def to_dict(self) -> dict:
        payload = {"handle": self.handle}
        if self.kind:
            payload["kind"] = self.kind
        return payload

    @classmethod
    def from_dict(cls, data: Mapping) -> "EvidenceRef":
        handle = _read_text(data, "handle") or _read_text(data, "id")
        return cls(handle=handle, kind=_read_text(data, "kind"))


@dataclass(frozen=True)
class BookParagraph:
    """
    One manuscript paragraph.

    Substantive paragraphs must carry evidence handles that resolve to SRC.
    Connective paragraphs may omit source claims.
    Canonical paragraph_id is empty on a chapter candidate and assigned
    during deterministic book assembly.
    """

    text: str
    kind: str
    evidence_handles: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    idea_refs: tuple[str, ...] = ()
    example_refs: tuple[str, ...] = ()
    reference_refs: tuple[str, ...] = ()
    uncertainty_refs: tuple[str, ...] = ()
    paragraph_id: str = ""
    provider_handle: str = ""

    def to_dict(self) -> dict:
        payload = {
            "text": self.text,
            "kind": self.kind,
            "evidence_handles": list(self.evidence_handles),
            "source_refs": list(self.source_refs),
            "idea_refs": list(self.idea_refs),
            "example_refs": list(self.example_refs),
            "reference_refs": list(self.reference_refs),
            "uncertainty_refs": list(self.uncertainty_refs),
        }
        if self.paragraph_id:
            payload["paragraph_id"] = self.paragraph_id
        if self.provider_handle:
            payload["provider_handle"] = self.provider_handle
        return payload

    @classmethod
    def from_dict(cls, data: Mapping) -> "BookParagraph":
        kind = _read_text(data, "kind") or PARAGRAPH_KIND_SUBSTANTIVE
        return cls(
            paragraph_id=_read_text(data, "paragraph_id"),
            provider_handle=_read_text(data, "provider_handle"),
            kind=kind,
            text=_read_text(data, "text"),
            evidence_handles=_read_text_tuple(data, "evidence_handles"),
            source_refs=_read_text_tuple(data, "source_refs"),
            idea_refs=_read_text_tuple(data, "idea_refs"),
            example_refs=_read_text_tuple(data, "example_refs"),
            reference_refs=_read_text_tuple(data, "reference_refs"),
            uncertainty_refs=_read_text_tuple(data, "uncertainty_refs"),
        )

    @property
    def is_connective(self) -> bool:
        return self.kind == PARAGRAPH_KIND_CONNECTIVE

    @property
    def is_substantive(self) -> bool:
        return self.kind == PARAGRAPH_KIND_SUBSTANTIVE


@dataclass(frozen=True)
class BookSection:
    section_id: str
    title: str
    paragraphs: tuple[BookParagraph, ...] = ()
    idea_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "paragraphs": [item.to_dict() for item in self.paragraphs],
            "idea_refs": list(self.idea_refs),
            "source_refs": list(self.source_refs),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "BookSection":
        return cls(
            section_id=_read_text(data, "section_id"),
            title=_read_text(data, "title"),
            paragraphs=_read_items(data, "paragraphs", BookParagraph),
            idea_refs=_read_text_tuple(data, "idea_refs"),
            source_refs=_read_text_tuple(data, "source_refs"),
        )


@dataclass(frozen=True)
class BookChapter:
    chapter_id: str
    title: str
    sections: tuple[BookSection, ...] = ()
    idea_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "chapter_id": self.chapter_id,
            "title": self.title,
            "sections": [item.to_dict() for item in self.sections],
            "idea_refs": list(self.idea_refs),
            "source_refs": list(self.source_refs),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "BookChapter":
        return cls(
            chapter_id=_read_text(data, "chapter_id"),
            title=_read_text(data, "title"),
            sections=_read_items(data, "sections", BookSection),
            idea_refs=_read_text_tuple(data, "idea_refs"),
            source_refs=_read_text_tuple(data, "source_refs"),
        )

    def all_paragraphs(self) -> tuple[BookParagraph, ...]:
        paragraphs: list[BookParagraph] = []
        for section in self.sections:
            paragraphs.extend(section.paragraphs)
        return tuple(paragraphs)


@dataclass(frozen=True)
class BookIdentity:
    source_map_sha256: str
    editorial_plan_sha256: str
    source_map_bytes: int = 0
    editorial_plan_bytes: int = 0
    transcript_sha256: str = ""
    transcript_path: str = ""

    def to_dict(self) -> dict:
        return {
            "source_map_sha256": self.source_map_sha256,
            "editorial_plan_sha256": self.editorial_plan_sha256,
            "source_map_bytes": self.source_map_bytes,
            "editorial_plan_bytes": self.editorial_plan_bytes,
            "transcript_sha256": self.transcript_sha256,
            "transcript_path": self.transcript_path,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "BookIdentity":
        return cls(
            source_map_sha256=_read_text(data, "source_map_sha256"),
            editorial_plan_sha256=_read_text(data, "editorial_plan_sha256"),
            source_map_bytes=_read_int(data, "source_map_bytes"),
            editorial_plan_bytes=_read_int(data, "editorial_plan_bytes"),
            transcript_sha256=_read_text(data, "transcript_sha256"),
            transcript_path=_read_text(data, "transcript_path"),
        )


@dataclass(frozen=True)
class BookGenerationMetadata:
    prompt_version: str
    transport_version: str
    schema_version: str
    validator_version: str
    evidence_strategy: str
    generation_unit: str
    provider: str
    model: str
    thinking_mode: str
    effort: str
    language: str
    title_status: str = TITLE_STATUS_WORKING
    signature: str = ""

    def to_dict(self) -> dict:
        return {
            "prompt_version": self.prompt_version,
            "transport_version": self.transport_version,
            "schema_version": self.schema_version,
            "validator_version": self.validator_version,
            "evidence_strategy": self.evidence_strategy,
            "generation_unit": self.generation_unit,
            "provider": self.provider,
            "model": self.model,
            "thinking_mode": self.thinking_mode,
            "effort": self.effort,
            "language": self.language,
            "title_status": self.title_status,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "BookGenerationMetadata":
        return cls(
            prompt_version=_read_text(data, "prompt_version"),
            transport_version=_read_text(data, "transport_version"),
            schema_version=_read_text(data, "schema_version"),
            validator_version=_read_text(data, "validator_version"),
            evidence_strategy=_read_text(data, "evidence_strategy"),
            generation_unit=_read_text(data, "generation_unit"),
            provider=_read_text(data, "provider"),
            model=_read_text(data, "model"),
            thinking_mode=_read_text(data, "thinking_mode"),
            effort=_read_text(data, "effort"),
            language=_read_text(data, "language"),
            title_status=_read_text(data, "title_status") or TITLE_STATUS_WORKING,
            signature=_read_text(data, "signature"),
        )


@dataclass(frozen=True)
class Book:
    """Canonical future book.json object. Semantic manuscript, not layout."""

    project_name: str
    language: str
    title: str
    chapters: tuple[BookChapter, ...]
    identity: BookIdentity
    generation: BookGenerationMetadata
    subtitle: str = ""
    title_status: str = TITLE_STATUS_WORKING
    schema_version: str = BOOK_SCHEMA_VERSION
    front_matter: tuple = ()
    back_matter: tuple = ()

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "project": {"name": self.project_name},
            "language": self.language,
            "title": self.title,
            "subtitle": self.subtitle,
            "title_status": self.title_status,
            "front_matter": list(self.front_matter),
            "back_matter": list(self.back_matter),
            "chapters": [item.to_dict() for item in self.chapters],
            "identity": self.identity.to_dict(),
            "generation": self.generation.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "Book":
        return cls(
            schema_version=_read_text(data, "schema_version") or BOOK_SCHEMA_VERSION,
            project_name=_read_text(_read_mapping(data, "project"), "name"),
            language=_read_text(data, "language"),
            title=_read_text(data, "title"),
            subtitle=_read_text(data, "subtitle"),
            title_status=_read_text(data, "title_status") or TITLE_STATUS_WORKING,
            front_matter=tuple(_read_text_tuple(data, "front_matter")),
            back_matter=tuple(_read_text_tuple(data, "back_matter")),
            chapters=_read_items(data, "chapters", BookChapter),
            identity=BookIdentity.from_dict(_read_mapping(data, "identity")),
            generation=BookGenerationMetadata.from_dict(
                _read_mapping(data, "generation")
            ),
        )

    def all_sections(self) -> tuple[BookSection, ...]:
        sections: list[BookSection] = []
        for chapter in self.chapters:
            sections.extend(chapter.sections)
        return tuple(sections)

    def all_paragraphs(self) -> tuple[BookParagraph, ...]:
        paragraphs: list[BookParagraph] = []
        for chapter in self.chapters:
            paragraphs.extend(chapter.all_paragraphs())
        return tuple(paragraphs)


@dataclass(frozen=True)
class ChapterCandidate:
    """Validated provider output before canonical P IDs / book assembly."""

    chapter_id: str
    title: str
    sections: tuple[BookSection, ...]
    idea_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    provider_raw_sha256: str = ""
    cache_signature: str = ""

    def to_dict(self) -> dict:
        return {
            "chapter_id": self.chapter_id,
            "title": self.title,
            "sections": [item.to_dict() for item in self.sections],
            "idea_refs": list(self.idea_refs),
            "source_refs": list(self.source_refs),
            "provider_raw_sha256": self.provider_raw_sha256,
            "cache_signature": self.cache_signature,
        }

    def to_book_chapter(self) -> BookChapter:
        return BookChapter(
            chapter_id=self.chapter_id,
            title=self.title,
            sections=self.sections,
            idea_refs=self.idea_refs,
            source_refs=self.source_refs,
        )


FORBIDDEN_LAYOUT_FIELDS = (
    "fonts",
    "page_size",
    "margins",
    "headers",
    "footers",
    "pagination",
    "toc_format",
    "cover_layout",
    "word_styles",
    "docx",
    "pdf",
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


def scan_forbidden_book_structure(payload: object) -> tuple[str, ...]:
    keys = frozenset(FORBIDDEN_LAYOUT_FIELDS + FORBIDDEN_TECHNICAL_FIELDS)
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
