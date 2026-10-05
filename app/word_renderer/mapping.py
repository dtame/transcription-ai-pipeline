"""Convert book.json into a print model. Technical IDs stay out of the body."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from app.word_renderer.constants import (
    ABSENT_EDITORIAL_FIELDS,
    TECHNICAL_ID_PATTERNS,
    TECHNICAL_STATUS_TOKENS,
)

_ID_RE = tuple(re.compile(pattern) for pattern in TECHNICAL_ID_PATTERNS)


@dataclass(frozen=True)
class PrintParagraph:
    text: str
    is_first: bool


@dataclass(frozen=True)
class PrintSection:
    title: str
    order: int
    paragraphs: tuple[PrintParagraph, ...]


@dataclass(frozen=True)
class PrintChapter:
    order: int
    title: str
    sections: tuple[PrintSection, ...]


@dataclass(frozen=True)
class PrintBook:
    title: str
    subtitle: str
    language: str
    version: str
    status: str
    chapters: tuple[PrintChapter, ...]
    absent_editorial_fields: tuple[str, ...]

    @property
    def chapter_count(self) -> int:
        return len(self.chapters)

    @property
    def section_count(self) -> int:
        return sum(len(chapter.sections) for chapter in self.chapters)

    @property
    def paragraph_texts(self) -> tuple[str, ...]:
        texts: list[str] = []
        for chapter in self.chapters:
            for section in chapter.sections:
                for paragraph in section.paragraphs:
                    texts.append(paragraph.text)
        return tuple(texts)


def map_book(payload: Mapping[str, Any]) -> PrintBook:
    subtitle = str(payload.get("subtitle") or "").strip()
    absent = tuple(
        field
        for field in ABSENT_EDITORIAL_FIELDS
        if _field_is_absent(payload, field)
    )
    chapters = tuple(
        _map_chapter(chapter)
        for chapter in payload.get("chapters") or []
        if isinstance(chapter, Mapping)
    )
    return PrintBook(
        title=str(payload.get("title") or "").strip(),
        subtitle=subtitle,
        language=str(payload.get("language") or "").strip(),
        version=str(payload.get("document_version") or "").strip(),
        status=str(payload.get("editorial_status") or "").strip(),
        chapters=chapters,
        absent_editorial_fields=absent,
    )


def source_paragraph_texts(payload: Mapping[str, Any]) -> tuple[str, ...]:
    texts: list[str] = []
    for chapter in payload.get("chapters") or []:
        if not isinstance(chapter, Mapping):
            continue
        for section in chapter.get("sections") or []:
            if not isinstance(section, Mapping):
                continue
            for paragraph in section.get("paragraphs") or []:
                if not isinstance(paragraph, Mapping):
                    continue
                texts.append(str(paragraph.get("text") or ""))
    return tuple(texts)


def visible_metadata(book: PrintBook) -> dict[str, Any]:
    return {
        "title": book.title,
        "subtitle": book.subtitle or None,
        "author": None,
        "publisher": None,
        "isbn": None,
        "copyright": None,
        "publication_date": None,
        "logo": None,
    }


def printed_strings(book: PrintBook, *, diagnostic: bool = False) -> tuple[str, ...]:
    values = [book.title]
    if book.subtitle:
        values.append(book.subtitle)
    for chapter in book.chapters:
        values.append(str(chapter.order))
        values.append(chapter.title)
        for section in chapter.sections:
            values.append(section.title)
            values.extend(paragraph.text for paragraph in section.paragraphs)
    if diagnostic:
        return tuple(values)
    return tuple(values)


def find_technical_leaks(texts: tuple[str, ...]) -> tuple[str, ...]:
    leaks: list[str] = []
    for text in texts:
        for pattern in _ID_RE:
            match = pattern.search(text)
            if match:
                leaks.append(match.group(0))
        for token in TECHNICAL_STATUS_TOKENS:
            if token in text:
                leaks.append(token)
    return tuple(sorted(set(leaks)))


def _map_chapter(payload: Mapping[str, Any]) -> PrintChapter:
    sections = tuple(
        _map_section(section)
        for section in payload.get("sections") or []
        if isinstance(section, Mapping)
    )
    return PrintChapter(
        order=int(payload.get("order") or 0),
        title=str(payload.get("title") or "").strip(),
        sections=sections,
    )


def _map_section(payload: Mapping[str, Any]) -> PrintSection:
    raw = [
        str(paragraph.get("text") or "")
        for paragraph in payload.get("paragraphs") or []
        if isinstance(paragraph, Mapping)
    ]
    paragraphs = tuple(
        PrintParagraph(text=text, is_first=index == 0)
        for index, text in enumerate(raw)
        if text
    )
    return PrintSection(
        title=str(payload.get("title") or "").strip(),
        order=int(payload.get("order") or 0),
        paragraphs=paragraphs,
    )


def _field_is_absent(payload: Mapping[str, Any], field: str) -> bool:
    declared = payload.get("absent_editorial_fields")
    if isinstance(declared, Mapping) and field in declared:
        return declared.get(field) in (None, "", [], {})
    return payload.get(field) in (None, "", [], {})


__all__ = [
    "PrintBook",
    "PrintChapter",
    "PrintParagraph",
    "PrintSection",
    "find_technical_leaks",
    "map_book",
    "printed_strings",
    "source_paragraph_texts",
    "visible_metadata",
]
