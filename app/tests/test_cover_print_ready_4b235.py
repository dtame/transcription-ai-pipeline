"""Phase 4B.2.35 — print-ready front and back cover renderer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from app.cover.renderer.geometry import cover_geometry
from app.cover_generator_foundation_4b233.constants import (
    EXPECTED_INTERIOR_DOCX_SHA256,
    EXPECTED_INTERIOR_PDF_SHA256,
)
from app.cover_print_ready_4b235.constants import (
    AUTHORIZATION_SCOPE,
    BOOK_TITLE,
    EXPECTED_BOOK_SHA256,
    EXPECTED_IMAGE_SHA256,
    PROJECT_NAME,
)
from app.cover_print_ready_4b235.content import (
    PROPOSED_DESCRIPTION,
    resolve_author,
    resolve_biography,
    resolve_description,
    resolve_subtitle,
)
from app.cover_print_ready_4b235.fonts import fit_display_title
from app.cover_print_ready_4b235.guard import (
    ApprovedImageHashError,
    CoverPrintReady4235Error,
    forbidden_imports,
    validate_authorization_scope,
)
from app.cover_print_ready_4b235.image_prep import prepare_cover_image, sha256_file
from app.cover_print_ready_4b235.layout import layout_back, layout_front
from app.cover_print_ready_4b235.package import CoverJob, assemble
from app.cover_print_ready_4b235.palette import contrast_ratio, select_back_color
from app.cover_print_ready_4b235.paths import (
    generated_image_path,
    interior_docx_path,
    interior_pdf_path,
    production_book_path,
    repo_root,
)
from app.cover_print_ready_4b235.validation import (
    docx_document_xml,
    pdf_media_box,
    pdf_page_count,
    validate_package,
)
from app.cover_print_ready_4b235.constants import OFF_WHITE


def _png(path: Path, width: int = 24, height: int = 36, color=(12, 18, 32)) -> Path:
    image = Image.new("RGB", (width, height), color)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    return path


def _job(source: Path, **overrides) -> CoverJob:
    payload = dict(
        title=BOOK_TITLE,
        subtitle=None,
        subtitle_status="ABSENT",
        author_name=None,
        author_status="MISSING_OPTIONAL",
        description=None,
        description_status="MISSING",
        description_canonical=False,
        biography=None,
        biography_status="MISSING_OPTIONAL",
        source_image=source,
        expected_sha256=sha256_file(source),
        book_sha256=EXPECTED_BOOK_SHA256,
    )
    payload.update(overrides)
    return CoverJob(**payload)


def test_trim_bleed_and_safe_area():
    geometry = cover_geometry()
    assert geometry.width_in == 6
    assert geometry.height_in == 9
    assert geometry.bleed_mm == 3
    assert geometry.safety_in >= 0.25
    assert geometry.dpi == 300
    assert (geometry.trim_width_px, geometry.trim_height_px) == (1800, 2700)
    assert (geometry.full_width_px, geometry.full_height_px) == (1871, 2771)
    assert geometry.full_width_px > geometry.trim_width_px
    assert geometry.full_height_px > geometry.trim_height_px


def test_approved_image_hash_matches():
    path = generated_image_path()
    assert path.is_file()
    assert sha256_file(path) == EXPECTED_IMAGE_SHA256
    with Image.open(path) as image:
        assert image.size == (1024, 1536)


def test_wrong_hash_stops_without_replacing_the_image(tmp_path):
    source = _png(tmp_path / "approved.png")
    before = source.read_bytes()
    destination = tmp_path / "prepared.png"
    with pytest.raises(ApprovedImageHashError):
        prepare_cover_image(
            source,
            destination,
            cover_geometry(),
            expected_sha256="0" * 64,
        )
    assert not destination.exists()
    assert source.read_bytes() == before


def test_upscale_uses_cover_fit_without_stretch(tmp_path):
    source = _png(tmp_path / "small.png")
    destination = tmp_path / "prepared.png"
    info = prepare_cover_image(
        source,
        destination,
        cover_geometry(),
        expected_sha256=sha256_file(source),
    )
    with Image.open(destination) as image:
        assert image.size == (1871, 2771)
    assert info["fit"] == "cover"
    assert info["stretch"] is False
    assert info["resample"] == "LANCZOS"
    assert info["sharpened"] is False
    assert source.resolve() != destination.resolve()


def test_back_color_is_a_dark_slate(tmp_path):
    path = _png(tmp_path / "sky.png", 30, 45, (18, 26, 40))
    color = select_back_color(path)
    red, green, blue = color["rgb"]
    assert blue >= red
    assert color["luminance"] < 50
    assert contrast_ratio(OFF_WHITE, tuple(color["rgb"])) >= 7
    assert color["second_generated_image"] is False


def test_missing_author_biography_and_subtitle(tmp_path):
    source = _png(tmp_path / "art.png")
    result = assemble(_job(source), tmp_path / "out")
    record = result["record"]
    assert record["author_status"] == "MISSING_OPTIONAL"
    assert record["author"] is None
    assert record["author_biography_status"] == "MISSING_OPTIONAL"
    assert record["author_biography"] is None
    assert record["subtitle_status"] == "ABSENT"
    assert record["subtitle"] is None
    front = docx_document_xml(tmp_path / "out" / "The_Life_You_Already_Inherited_front_cover_print_review_v1.docx")
    assert "MISSING_OPTIONAL" not in front
    assert "Subtitle" not in front
    assert BOOK_TITLE.split()[-1].upper() in front


def test_missing_description_is_not_invented_as_canonical_copy(tmp_path):
    source = _png(tmp_path / "art.png")
    result = assemble(_job(source), tmp_path / "out")
    record = result["record"]
    assert record["book_description_status"] == "MISSING"
    assert record["book_description"] is None
    assert record["book_description_canonical"] is False
    back = docx_document_xml(tmp_path / "out" / "The_Life_You_Already_Inherited_back_cover_print_review_v1.docx")
    assert "PRINT REVIEW DRAFT" in back
    assert "resurrection life is an inheritance" not in back


def test_proposed_description_is_not_canonical(tmp_path):
    source = _png(tmp_path / "art.png")
    job = _job(
        source,
        description=PROPOSED_DESCRIPTION,
        description_status="PROPOSED_NOT_EDITORIALLY_APPROVED",
        description_canonical=False,
    )
    result = assemble(job, tmp_path / "out")
    record = result["record"]
    assert record["book_description_status"] == "PROPOSED_NOT_EDITORIALLY_APPROVED"
    assert record["book_description_canonical"] is False
    assert record["print_status"] == "PRINT_REVIEW_DRAFT"
    back = docx_document_xml(tmp_path / "out" / "The_Life_You_Already_Inherited_back_cover_print_review_v1.docx")
    assert "PRINT REVIEW DRAFT" in back
    assert "not editorially approved" in back
    assert "resurrection life is an inheritance" in back


def test_explicit_author_and_biography_are_drawn(tmp_path):
    source = _png(tmp_path / "art.png")
    job = _job(
        source,
        author_name="N. Writer",
        author_status="APPROVED",
        biography="A short approved biography.",
        biography_status="APPROVED",
        description="A received life, told without a borrowed voice.",
        description_status="APPROVED",
        description_canonical=True,
    )
    result = assemble(job, tmp_path / "out")
    back = docx_document_xml(tmp_path / "out" / "The_Life_You_Already_Inherited_back_cover_print_review_v1.docx")
    front = docx_document_xml(tmp_path / "out" / "The_Life_You_Already_Inherited_front_cover_print_review_v1.docx")
    assert "N. Writer" in front
    assert "N. Writer" in back
    assert "A short approved biography." in back
    assert "PRINT REVIEW DRAFT" not in back
    assert result["record"]["book_description_canonical"] is True


def test_depositor_is_not_used_as_author():
    book = {
        "title": BOOK_TITLE,
        "subtitle": "",
        "author": None,
        "absent_editorial_fields": {"author": None},
        "project_id": PROJECT_NAME,
    }
    library = {
        "authors": {
            "a1": {
                "author_id": "a1",
                "display_name": "Pat Depositor",
                "name_publication_authorized": True,
            }
        },
        "attributions": [
            {"project_id": PROJECT_NAME, "author_id": "a1", "role": "DEPOSITOR"}
        ],
    }
    resolved = resolve_author(book, library)
    assert resolved["status"] == "MISSING_OPTIONAL"
    assert resolved["name"] is None
    assert resolve_subtitle(book)["status"] == "ABSENT"


def test_book_author_requires_publication_consent_and_approved_biography():
    book = {
        "title": BOOK_TITLE,
        "subtitle": "A real subtitle",
        "author": None,
        "absent_editorial_fields": {"author": None},
        "project_id": PROJECT_NAME,
    }
    library = {
        "authors": {
            "a1": {
                "author_id": "a1",
                "display_name": "N. Writer",
                "name_publication_authorized": True,
                "professional_background": [
                    {
                        "fact_id": "b1",
                        "kind": "biography",
                        "text": "A short approved biography.",
                        "verification_status": "VERIFIED",
                        "publication_status": "APPROVED_FOR_PUBLICATION",
                    }
                ],
            }
        },
        "attributions": [
            {"project_id": PROJECT_NAME, "author_id": "a1", "role": "BOOK_AUTHOR"}
        ],
    }
    author = resolve_author(book, library)
    biography = resolve_biography(library, author["author_id"])
    assert author["name"] == "N. Writer"
    assert biography["status"] == "APPROVED"
    assert biography["text"] == "A short approved biography."
    assert resolve_subtitle(book)["text"] == "A real subtitle"


def test_conflicting_approved_descriptions_stop():
    with pytest.raises(CoverPrintReady4235Error):
        resolve_description(["One approved text.", "Another approved text."], allow_proposal=True)


def test_proposal_is_used_only_when_nothing_is_approved():
    missing = resolve_description([], allow_proposal=False)
    proposed = resolve_description([], allow_proposal=True)
    approved = resolve_description(["Already approved copy."], allow_proposal=True)
    assert missing["status"] == "MISSING"
    assert missing["text"] is None
    assert proposed["status"] == "PROPOSED_NOT_EDITORIALLY_APPROVED"
    assert proposed["canonical"] is False
    assert approved["status"] == "APPROVED"
    assert approved["canonical"] is True


def test_front_and_back_files_are_single_bleed_pages_without_spine(tmp_path):
    source = _png(tmp_path / "art.png")
    result = assemble(_job(source, subtitle="A quiet subtitle", subtitle_status="PRESENT"), tmp_path / "out")
    directory = tmp_path / "out"
    width, height = pdf_media_box(directory / "The_Life_You_Already_Inherited_front_cover_print_review_v1.pdf")
    back_box = pdf_media_box(directory / "The_Life_You_Already_Inherited_back_cover_print_review_v1.pdf")
    assert pdf_page_count(directory / "The_Life_You_Already_Inherited_front_cover_print_review_v1.pdf") == 1
    assert pdf_page_count(directory / "The_Life_You_Already_Inherited_back_cover_print_review_v1.pdf") == 1
    assert back_box == (width, height)
    assert width > 6 * 72
    assert height > 9 * 72
    names = [path.name.lower() for path in directory.iterdir()]
    assert not any("spine" in name or "wrap" in name for name in names)
    assert result["record"]["wraparound"] is False
    assert result["record"]["spine_computed"] is False
    assert result["record"]["isbn"] is None
    assert result["record"]["barcode"] is None
    assert result["record"]["openai_calls"] == 0
    assert result["record"]["black_forest_labs_calls"] == 0
    report = validate_package(
        directory,
        result["record"],
        front_layout=result["front_layout"],
        back_layout=result["back_layout"],
        canonical_match=True,
        source_unchanged=True,
        imports_ok=True,
    )
    assert report["ok"], report["checks"]


def test_title_breaks_from_the_available_width():
    lines, size, _tracking = fit_display_title(BOOK_TITLE, 360)
    assert size >= 28
    assert all(len(line) > 0 for line in lines)
    assert " ".join(lines).split() == BOOK_TITLE.upper().split()


def test_front_title_stays_in_the_upper_safe_field():
    layout = layout_front(
        title=BOOK_TITLE,
        subtitle="Resurrection life, union with God, and the practice of spiritual authority",
        author=None,
    )
    assert layout.text_bottom_from_top_pt < layout.page_height_in * 72 * 0.46
    assert any(line.text == "INHERITED" for line in layout.lines)
    back = layout_back(
        title=BOOK_TITLE,
        subtitle=None,
        author=None,
        description=None,
        description_status="MISSING",
        biography=None,
    )
    assert back.rules == ()
    assert back.bottom_in > 1.2


def test_renderer_does_not_import_a_provider():
    hits = forbidden_imports(repo_root() / "app" / "cover_print_ready_4b235")
    assert hits == []


def test_wrong_authorization_scope_is_rejected():
    with pytest.raises(CoverPrintReady4235Error):
        validate_authorization_scope("COVER_GENERATOR_FOUNDATION_4B233_ARCHITECTURE_ONLY")
    assert validate_authorization_scope(AUTHORIZATION_SCOPE) == AUTHORIZATION_SCOPE


def test_canonical_hashes_stay_put_while_a_cover_is_rendered(tmp_path):
    book = production_book_path()
    docx = interior_docx_path()
    pdf = interior_pdf_path()
    before = {
        "book": sha256_file(book),
        "docx": sha256_file(docx),
        "pdf": sha256_file(pdf),
    }
    assert before["book"] == EXPECTED_BOOK_SHA256
    assert before["docx"] == EXPECTED_INTERIOR_DOCX_SHA256
    assert before["pdf"] == EXPECTED_INTERIOR_PDF_SHA256
    source = _png(tmp_path / "art.png")
    assemble(_job(source), tmp_path / "out")
    assert sha256_file(book) == before["book"]
    assert sha256_file(docx) == before["docx"]
    assert sha256_file(pdf) == before["pdf"]
    record = json.loads((tmp_path / "out" / "cover_record.json").read_text(encoding="utf-8"))
    assert "chapters" not in record
    assert "paragraphs" not in record
