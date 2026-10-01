"""Deterministic Book serialization. Publication blocked in 4B.1."""

from __future__ import annotations

import json
from pathlib import Path

from app.book_generation.constants import BOOK_FILENAME, PUBLICATION_AUTHORIZED
from app.book_generation.errors import BookPublicationBlocked
from app.book_generation.models import Book
from app.book_generation.paths import book_path
from app.file_utils import content_hash, write_text_atomic

_JSON_INDENT = 2


def render_book(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=_JSON_INDENT) + "\n"


def book_sha256(book: Book) -> str:
    return content_hash(render_book(book.to_dict()))


def candidate_sha256(payload: dict) -> str:
    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def write_book(path: Path, payload: dict) -> Path:
    if not PUBLICATION_AUTHORIZED:
        raise BookPublicationBlocked(
            f"Refus d'écrire {path} : PUBLICATION_AUTHORIZED=False (Phase 4B.1)."
        )
    return write_text_atomic(Path(path), render_book(payload))


def production_book_absent(project_name: str, *, sortie_dir: Path | None = None) -> bool:
    return not book_path(project_name, sortie_dir=sortie_dir).is_file()
