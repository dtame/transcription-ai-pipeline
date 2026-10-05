"""Phase 4B.2.30 — offline Word 6x9 print-profile preparation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.shared import Inches

from app.book_print_review_canonical_4b229.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B229_SCOPE,
)
from app.word_print_profile_4b230.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BOOK_JSON_MUTATION_AUTHORIZED,
    BOOK_STATUS,
    BOOK_TITLE,
    BOOK_VERSION,
    COVER_GENERATION_AUTHORIZED,
    DOCX_GENERATION_AUTHORIZED,
    EXPECTED_BOOK_SHA256,
    EXPECTED_CHAPTER_COUNT,
    EXPECTED_SECTION_COUNT,
    PDF_GENERATION_AUTHORIZED,
    PRINT_PROFILE,
)
from app.word_print_profile_4b230.guard import (
    WordPrintProfile4230Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.word_print_profile_4b230.hashes import snapshot
from app.word_print_profile_4b230.paths import phase_audit_dir, production_book_path
from app.word_print_profile_4b230.runner import run_phase
from app.word_print_profile_4b230.validation import (
    load_canonical_book,
    synthetic_book_payload,
)
from app.word_renderer.constants import (
    DRAFT_NOTICE,
    GUTTER_INCHES,
    INSIDE_MARGIN_INCHES,
    PAGE_HEIGHT_INCHES,
    PAGE_WIDTH_INCHES,
    STYLE_BODY,
    STYLE_BODY_FIRST,
    STYLE_CHAPTER_TITLE,
    STYLE_SECTION_TITLE,
)
from app.word_renderer.document import (
    WordPublishForbidden,
    assert_not_published,
    build_print_document,
    configure_document,
    serialize_in_memory,
)
from app.word_renderer.geometry import inspect_geometry
from app.word_renderer.headers import inspect_headers
from app.word_renderer.mapping import map_book, source_paragraph_texts
from app.word_renderer.oxml import field_instructions, gutter_emu
from app.word_renderer.profile import load_profile
from app.word_renderer.styles import inspect_style


@pytest.fixture(scope="module")
def payload():
    return load_canonical_book()


@pytest.fixture(scope="module")
def profile():
    return load_profile()


@pytest.fixture(scope="module")
def book(payload):
    return map_book(payload)


@pytest.fixture(scope="module")
def configured(profile):
    return configure_document(profile)


@pytest.fixture(scope="module")
def synthetic_doc(profile):
    return build_print_document(map_book(synthetic_book_payload()), profile)


def test_offline_authorizations():
    assert AUTHORIZED_ANTHROPIC_CALLS == 0
    assert AUTHORIZED_OPENAI_CALLS == 0
    assert AUTHORIZED_SONNET_CALLS == 0
    assert AUTHORIZED_TERRA_CALLS == 0
    assert DOCX_GENERATION_AUTHORIZED is False
    assert PDF_GENERATION_AUTHORIZED is False
    assert COVER_GENERATION_AUTHORIZED is False
    assert BOOK_JSON_MUTATION_AUTHORIZED is False
    assert_offline_only()
    validate_authorization_scope(AUTHORIZATION_SCOPE)
    with pytest.raises(WordPrintProfile4230Error):
        validate_authorization_scope(CONSUMED_4B229_SCOPE)
    with pytest.raises(WordPrintProfile4230Error):
        validate_authorization_scope("WRONG")


def test_load_book_json_and_sha256(payload):
    path = production_book_path()
    assert path.is_file()
    raw = path.read_bytes()
    import hashlib

    assert hashlib.sha256(raw).hexdigest() == EXPECTED_BOOK_SHA256
    assert payload["title"] == BOOK_TITLE
    assert payload["document_version"] == BOOK_VERSION
    assert payload["editorial_status"] == BOOK_STATUS


def test_load_print_profile(profile):
    assert profile["profile_id"] == PRINT_PROFILE
    assert profile["book_agnostic"] is True
    dumped = json.dumps(profile)
    assert BOOK_TITLE not in dumped


def test_page_geometry_and_portrait(configured, profile):
    geometry = inspect_geometry(configured.sections[0], profile)
    section = configured.sections[0]
    assert abs(section.page_width.inches - PAGE_WIDTH_INCHES) < 0.0001
    assert abs(section.page_height.inches - PAGE_HEIGHT_INCHES) < 0.0001
    assert section.page_width < section.page_height
    assert section.orientation == WD_ORIENT.PORTRAIT
    assert geometry["portrait"] is True


def test_mirror_margins_and_gutter_not_duplicated(configured, profile):
    section = configured.sections[0]
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    assert configured.settings.element.find(f"{ns}mirrorMargins") is not None
    assert abs(section.left_margin.inches - INSIDE_MARGIN_INCHES) < 0.0001
    assert gutter_emu(section) == int(Inches(GUTTER_INCHES))
    assert abs(section.left_margin.inches - (INSIDE_MARGIN_INCHES + GUTTER_INCHES)) > 0.05
    convention = profile["gutter_convention"]
    assert convention["gutter_included_in_inside_margin_value"] is False
    assert convention["double_compensation_risk"] is False


def test_typography_styles(configured):
    body = inspect_style(configured, STYLE_BODY)
    first = inspect_style(configured, STYLE_BODY_FIRST)
    chapter = inspect_style(configured, STYLE_CHAPTER_TITLE)
    section = inspect_style(configured, STYLE_SECTION_TITLE)
    assert body["font_name"] == "Georgia"
    assert body["font_size_pt"] == 11
    assert body["first_line_indent_inches"] == pytest.approx(0.18, abs=0.002)
    assert first["first_line_indent_inches"] == 0
    assert first["font_size_pt"] == body["font_size_pt"]
    assert first["line_spacing"] == body["line_spacing"]
    assert chapter["keep_with_next"] is True
    assert section["keep_with_next"] is True
    assert chapter["outline_level"] == 0
    assert section["outline_level"] == 1
    assert body["widow_control"] is True
    assert first["widow_control"] is True
    assert body["keep_with_next"] is False


def test_chapter_page_breaks_and_front_matter(synthetic_doc):
    assert len(synthetic_doc.sections) >= 2
    assert synthetic_doc.sections[0].start_type != WD_SECTION.ODD_PAGE
    assert all(
        section.start_type == WD_SECTION.NEW_PAGE
        for section in synthetic_doc.sections[1:]
    )
    texts = [paragraph.text for paragraph in synthetic_doc.paragraphs]
    assert texts[0] == "A Different Synthetic Book"
    assert DRAFT_NOTICE in texts
    assert "Contents" in texts
    assert synthetic_doc.core_properties.author in ("", None)
    joined = "\n".join(texts)
    assert "ISBN" not in joined
    assert "TranscriptionAI" not in joined


def test_toc_field_and_header_footer_fields(synthetic_doc):
    fields = field_instructions(synthetic_doc.element)
    assert any(item.startswith("TOC") and "1-1" in item for item in fields)
    headers = inspect_headers(synthetic_doc.sections[1])
    assert headers["first_page_header_empty"] is True
    assert any("STYLEREF" in item for item in headers["odd_header_fields"])
    assert "A Different Synthetic Book" in headers["even_header_texts"]
    assert any("PAGE" in item for item in headers["footer_fields"])


def test_mapping_nineteen_chapters_and_unmodified_paragraphs(payload, book):
    assert book.chapter_count == EXPECTED_CHAPTER_COUNT
    assert book.section_count == EXPECTED_SECTION_COUNT
    assert book.paragraph_texts == source_paragraph_texts(payload)
    assert [chapter.order for chapter in book.chapters] == list(range(1, 20))
    assert all(not chapter.title.startswith("CH") for chapter in book.chapters)
    leaked = "\n".join(book.paragraph_texts)
    assert "CH001" not in book.title
    assert "HUMAN_EDITORIALLY_ACCEPTED" not in leaked


def test_profile_reuse_and_optional_cover(profile):
    other = map_book(synthetic_book_payload())
    doc = build_print_document(other, profile)
    assert doc.core_properties.title == "A Different Synthetic Book"
    assert profile["cover"]["required"] is False
    assert profile["cover"]["spine_width_computed"] is False


def test_no_published_docx_pdf_and_no_book_mutation():
    before = snapshot()
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        write_artifacts=False,
        run_tests=False,
    )
    after = snapshot()
    assert before["book_json"] == after["book_json"]
    assert after["book_json"]["sha256"] == EXPECTED_BOOK_SHA256
    assert result.bundle["header"]["result"] in {"PASS", "PARTIAL"}
    assert "DOCX = NOT GENERATED" in result.bundle["report_text"]
    assert "PDF = NOT GENERATED" in result.bundle["report_text"]
    assert not any(phase_audit_dir().glob("*.docx"))
    assert not any(phase_audit_dir().glob("*.pdf"))
    with pytest.raises(WordPublishForbidden):
        assert_not_published(Path("audit/word_print_profile_4b230/book.docx"))
    blob = serialize_in_memory(configure_document())
    assert blob.startswith(b"PK")


def test_header_ready_for_next_phase():
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        write_artifacts=False,
        run_tests=False,
    )
    header = result.bundle["header"]
    assert header["provider_calls"] == 0
    assert header["book_title"] == BOOK_TITLE
    assert header["book_version"] == BOOK_VERSION
    assert header["book_status"] == BOOK_STATUS
    assert header["book_sha256"] == EXPECTED_BOOK_SHA256
    assert header["profile"] == PRINT_PROFILE
    assert header["cover_integration"] == "OPTIONAL"
    assert header["word_finalizer"] == "PARTIAL"
