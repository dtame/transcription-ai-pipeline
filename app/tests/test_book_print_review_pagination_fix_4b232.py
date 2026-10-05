"""Phase 4B.2.32 — offline interchapter blank-page removal."""

from __future__ import annotations

import hashlib
from io import BytesIO

import pytest
from docx import Document
from docx.enum.section import WD_SECTION
from docx.shared import Inches

from app.book_print_review_canonical_4b229.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B229_SCOPE,
)
from app.book_print_review_pagination_fix_4b232.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BOOK_JSON_MUTATION_AUTHORIZED,
    BOOK_STATUS,
    BOOK_TITLE,
    BOOK_VERSION,
    CHAPTER_BREAK_POLICY,
    COVER_GENERATION_AUTHORIZED,
    EXPECTED_BOOK_SHA256,
    EXPECTED_CHAPTER_COUNT,
    EXPECTED_FRONT_MATTER_PAGE_BREAKS,
    EXPECTED_PARAGRAPH_COUNT,
    EXPECTED_SECTION_COUNT,
    EXPECTED_TRANSITION_COUNT,
    OUTPUT_VERSION,
    SOURCE_VERSION,
)
from app.book_print_review_pagination_fix_4b232.generation import build_docx_bytes
from app.book_print_review_pagination_fix_4b232.guard import (
    BookPrintReviewPaginationFix4232Error,
    assert_not_v1_target,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_print_review_pagination_fix_4b232.hashes import (
    snapshot,
    snapshot_original_publication,
)
from app.book_print_review_pagination_fix_4b232.integrity import validate_docx_integrity
from app.book_print_review_pagination_fix_4b232.paths import (
    official_v1_docx_path,
    official_v1_pdf_path,
    official_v1_publication_root,
    production_book_path,
)
from app.book_print_review_pagination_fix_4b232.preflight import build_preflight
from app.book_print_review_pagination_fix_4b232.runner import run_phase
from app.book_print_review_pagination_fix_4b232.transitions import (
    compare_front_matter,
    validate_transitions,
)
from app.book_print_review_render_4b231.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B231_SCOPE,
)
from app.word_print_profile_4b230.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B230_SCOPE,
)
from app.word_print_profile_4b230.validation import synthetic_book_payload
from app.word_renderer.constants import (
    GUTTER_INCHES,
    INSIDE_MARGIN_INCHES,
    PAGE_HEIGHT_INCHES,
    PAGE_WIDTH_INCHES,
    STYLE_BODY,
    STYLE_BODY_FIRST,
    STYLE_CHAPTER_TITLE,
)
from app.word_renderer.document import build_print_document, inspect_document
from app.word_renderer.finalizer import UnavailableWordBackend
from app.word_renderer.mapping import map_book
from app.word_renderer.oxml import count_explicit_page_breaks, gutter_emu, page_number_start
from app.word_renderer.profile import (
    chapter_start_type_name,
    front_matter_section_start_name,
    load_profile,
)
from app.word_renderer.styles import inspect_style


@pytest.fixture(scope="module")
def preflight_data():
    return build_preflight()


@pytest.fixture(scope="module")
def real_docx_bytes(preflight_data):
    return build_docx_bytes(preflight_data["book"], preflight_data["profile"])


@pytest.fixture(scope="module")
def real_integrity(real_docx_bytes, preflight_data):
    return validate_docx_integrity(
        real_docx_bytes,
        preflight_data["book"],
        preflight_data["profile"],
    )


def test_offline_authorizations_and_no_provider_calls():
    assert AUTHORIZED_ANTHROPIC_CALLS == 0
    assert AUTHORIZED_OPENAI_CALLS == 0
    assert AUTHORIZED_SONNET_CALLS == 0
    assert AUTHORIZED_TERRA_CALLS == 0
    assert COVER_GENERATION_AUTHORIZED is False
    assert BOOK_JSON_MUTATION_AUTHORIZED is False
    assert_offline_only()
    validate_authorization_scope(AUTHORIZATION_SCOPE)
    with pytest.raises(BookPrintReviewPaginationFix4232Error):
        validate_authorization_scope(CONSUMED_4B229_SCOPE)
    with pytest.raises(BookPrintReviewPaginationFix4232Error):
        validate_authorization_scope(CONSUMED_4B230_SCOPE)
    with pytest.raises(BookPrintReviewPaginationFix4232Error):
        validate_authorization_scope(CONSUMED_4B231_SCOPE)


def test_canonical_unchanged(preflight_data):
    path = production_book_path()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == EXPECTED_BOOK_SHA256
    assert preflight_data["book_sha256"] == EXPECTED_BOOK_SHA256
    assert preflight_data["version"] == BOOK_VERSION == SOURCE_VERSION
    assert preflight_data["editorial_status"] == BOOK_STATUS
    assert OUTPUT_VERSION != SOURCE_VERSION


def test_profile_loaded_with_next_page_policy():
    profile = load_profile()
    assert profile["profile_id"] == "print_review_6x9_v1"
    assert chapter_start_type_name(profile) == "next_page"
    assert front_matter_section_start_name(profile) == "keep_existing"
    assert CHAPTER_BREAK_POLICY == "NEXT_PAGE"
    assert profile["chapter"]["start"] == "next_page"
    assert profile["pagination"]["body"]["chapter_start"] == "next_page"


def test_next_page_applied_and_no_interchapter_odd_page(real_docx_bytes, preflight_data):
    doc = Document(BytesIO(real_docx_bytes))
    inspection = inspect_document(doc, preflight_data["profile"])
    assert doc.sections[0].start_type != WD_SECTION.ODD_PAGE
    assert all(section.start_type == WD_SECTION.NEW_PAGE for section in doc.sections[1:])
    assert inspection["interchapter_odd_page"] is False
    assert inspection["interchapter_next_page"] is True
    assert inspection["explicit_page_breaks"] == EXPECTED_FRONT_MATTER_PAGE_BREAKS


def test_no_double_page_break_insertion(real_docx_bytes):
    doc = Document(BytesIO(real_docx_bytes))
    assert count_explicit_page_breaks(doc.element) == EXPECTED_FRONT_MATTER_PAGE_BREAKS


def test_chapter_section_paragraph_identity(real_integrity, preflight_data):
    assert real_integrity["chapter_count"] == EXPECTED_CHAPTER_COUNT
    assert real_integrity["section_count"] == EXPECTED_SECTION_COUNT
    assert real_integrity["paragraph_count"] == EXPECTED_PARAGRAPH_COUNT
    assert real_integrity["mapping_all_match"] is True
    assert real_integrity["status"] == "PASS"
    assert preflight_data["book"].title == BOOK_TITLE


def test_styles_margins_headers_footers_and_pagination(real_docx_bytes, real_integrity):
    doc = Document(BytesIO(real_docx_bytes))
    section = doc.sections[1]
    assert abs(section.page_width.inches - PAGE_WIDTH_INCHES) < 0.0001
    assert abs(section.page_height.inches - PAGE_HEIGHT_INCHES) < 0.0001
    assert abs(section.left_margin.inches - INSIDE_MARGIN_INCHES) < 0.0001
    assert gutter_emu(section) == int(Inches(GUTTER_INCHES))
    body = inspect_style(doc, STYLE_BODY)
    first = inspect_style(doc, STYLE_BODY_FIRST)
    assert body["font_name"] == "Georgia"
    assert first["first_line_indent_inches"] == 0
    assert inspect_style(doc, STYLE_CHAPTER_TITLE)["keep_with_next"] is True
    assert real_integrity["checks"]["headers_present"] is True
    assert real_integrity["checks"]["footers_present"] is True
    assert page_number_start(doc.sections[1]) == 1
    assert all(page_number_start(item) is None for item in doc.sections[2:])
    assert real_integrity["checks"]["pagination_continuous"] is True


def test_front_matter_structure_unchanged(real_docx_bytes, preflight_data):
    doc = Document(BytesIO(real_docx_bytes))
    texts = [paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()]
    assert texts[0] == BOOK_TITLE
    assert "Contents" in texts
    assert doc.sections[0].start_type != WD_SECTION.ODD_PAGE
    assert front_matter_section_start_name(preflight_data["profile"]) == "keep_existing"


def test_original_v1_preserved_and_not_targeted():
    originals = snapshot_original_publication()
    assert official_v1_docx_path().is_file()
    assert official_v1_pdf_path().is_file()
    assert originals["docx"]["exists"] is True
    assert originals["pdf"]["exists"] is True
    with pytest.raises(BookPrintReviewPaginationFix4232Error):
        assert_not_v1_target(official_v1_publication_root() / "probe.docx")


def test_transition_validator_rejects_parity_blank(preflight_data):
    inspection = {
        "status": "PASS",
        "chapters": [
            {"title": preflight_data["book"].chapters[0].title, "first_page": 5, "last_page": 8},
            {"title": preflight_data["book"].chapters[1].title, "first_page": 9, "last_page": 12},
        ],
        "pages": [
            {"page": 5, "blank": False, "preview": "1"},
            {"page": 6, "blank": False, "preview": "body"},
            {"page": 7, "blank": False, "preview": "body"},
            {"page": 8, "blank": True, "preview": ""},
            {"page": 9, "blank": False, "preview": preflight_data["book"].chapters[1].title},
        ],
    }
    payload = validate_transitions(inspection=inspection, book=preflight_data["book"])
    assert payload["transitions"][0]["result"] == "FAIL"
    assert payload["unnecessary_blank_count"] == 1


def test_transition_validator_accepts_next_page(preflight_data):
    chapters = []
    pages = []
    page = 5
    for chapter in preflight_data["book"].chapters:
        chapters.append({"title": chapter.title, "first_page": page, "last_page": page + 1})
        pages.append({"page": page, "blank": False, "preview": chapter.title})
        pages.append({"page": page + 1, "blank": False, "preview": "body"})
        page += 2
    payload = validate_transitions(
        inspection={"status": "PASS", "chapters": chapters, "pages": pages},
        book=preflight_data["book"],
    )
    assert payload["transitions_checked_count"] == EXPECTED_TRANSITION_COUNT
    assert payload["unnecessary_blank_count"] == 0
    assert payload["status"] == "PASS"


def test_front_matter_comparison_ignores_toc_page_numbers():
    original = {
        "status": "PASS",
        "front_matter_pages": [
            {"page": 1, "preview": "The Life You Already Inherited", "blank": False},
            {"page": 2, "preview": "The Life You Already Inherited\nDraft", "blank": False},
            {"page": 3, "preview": "Contents\nUnlearning What Was Handed Down\t1", "blank": False},
        ],
    }
    updated = {
        "status": "PASS",
        "front_matter_pages": [
            {"page": 1, "preview": "The Life You Already Inherited", "blank": False},
            {"page": 2, "preview": "The Life You Already Inherited\nDraft", "blank": False},
            {"page": 3, "preview": "Contents\nUnlearning What Was Handed Down\t1", "blank": False},
        ],
    }
    updated["front_matter_pages"][2]["preview"] = (
        "Contents\nUnlearning What Was Handed Down\t1"
    )
    compared = compare_front_matter(original=original, updated=updated)
    assert compared["front_matter_unchanged"] == "YES"


def test_sources_unchanged_and_no_v1_overwrite(tmp_path, real_integrity):
    del real_integrity
    before = snapshot()
    original_before = snapshot_original_publication()
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        write_artifacts=True,
        run_tests=False,
        finalize=True,
        probe_word=False,
        allow_official=False,
        root=tmp_path,
        word_backend=UnavailableWordBackend(),
    )
    after = snapshot()
    original_after = snapshot_original_publication()
    assert before["book_json"] == after["book_json"]
    assert original_before == original_after
    assert result.bundle["header"]["provider_calls"] == 0
    assert result.bundle["header"]["docx_integrity"] == "PASS"
    published = list((tmp_path / "sortie").rglob("*.docx"))
    assert published
    official_v1 = official_v1_publication_root().resolve()
    assert all(official_v1 not in path.resolve().parents for path in published)
    assert not any(path.suffix == ".pdf" for path in (tmp_path / "sortie").rglob("*"))


def test_reusable_on_synthetic_book():
    profile = load_profile()
    other = map_book(synthetic_book_payload())
    doc = build_print_document(other, profile)
    assert doc.core_properties.title == "A Different Synthetic Book"
    assert all(section.start_type == WD_SECTION.NEW_PAGE for section in doc.sections[1:])
