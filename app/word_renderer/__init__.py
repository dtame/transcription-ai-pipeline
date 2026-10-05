"""Reusable Word print renderer. Layout only. Content comes from book.json."""

from app.word_renderer.constants import DRAFT_NOTICE, PROFILE_NAME
from app.word_renderer.document import build_print_document, configure_document
from app.word_renderer.mapping import map_book
from app.word_renderer.profile import load_profile

__all__ = [
    "DRAFT_NOTICE",
    "PROFILE_NAME",
    "build_print_document",
    "configure_document",
    "load_profile",
    "map_book",
]
