"""Phase 4B.2.33 — offline cover-generator foundation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.cover.author_library.store import AuthorLibrary
from app.cover.content.contract import (
    ContentContractError,
    approve,
    back_layout_blocks,
    initial_content,
    store_biography_draft,
    store_description_draft,
    submit_for_review,
)
from app.cover.image_providers.policy import empty_paid_authorization, evaluate_paid_call
from app.cover.paths import default_library_root
from app.cover.validation.checks import build_draft_cover
from app.cover_generator_foundation_4b233.constants import (
    AUTHORIZATION_SCOPE,
    BOOK_TITLE,
    EXPECTED_BOOK_SHA256,
    INTERIOR_VERSION,
)
from app.cover_generator_foundation_4b233.guard import (
    CoverGeneratorFoundation4233Error,
    validate_authorization_scope,
)
from app.cover_generator_foundation_4b233.paths import repo_root
from app.cover_generator_foundation_4b233.runner import run_phase
from app.cover_generator_foundation_4b233.scenarios import (
    CASE_NAMES,
    evaluate_cases,
    reference_book_view,
)


def _reference_book() -> dict:
    import json

    payload = json.loads(
        (repo_root() / "sortie" / "pastoral_retreat_v2_validation" / "analysis" / "book.json").read_text(
            encoding="utf-8"
        )
    )
    book = reference_book_view(payload)
    assert "chapters" not in book
    return book


@pytest.fixture(scope="module")
def case_report(tmp_path_factory):
    return evaluate_cases(library_root=tmp_path_factory.mktemp("authors"), book=_reference_book())


@pytest.mark.parametrize("case_name", CASE_NAMES)
def test_offline_case(case_name, case_report):
    case = next(item for item in case_report["cases"] if item["name"] == case_name)
    assert case["passed"], case["detail"]
    assert case_report["provider_calls"] == 0
    assert case_report["downloads"] == 0
    assert case_report["network_calls"] == 0


def test_case_count_covers_required_matrix(case_report):
    assert len(CASE_NAMES) == 32
    assert case_report["failed"] == 0
    assert case_report["passed"] == 32


def test_author_library_is_outside_the_project():
    library = default_library_root()
    assert library.name == "author_library"
    assert "sortie" not in library.parts
    assert "pastoral_retreat_v2_validation" not in library.parts


def test_production_library_is_not_seeded_by_import(tmp_path):
    library = AuthorLibrary(tmp_path / "empty")
    library.ensure()
    assert library.public_index()["authors"] == {}


def test_biography_reflow_omits_empty_slot():
    missing = initial_content(None)
    assert back_layout_blocks(missing) == []
    with_bio = store_biography_draft(missing, "A human supplied this optional biography.")
    with_both = store_description_draft(with_bio, "A human supplied this description draft.")
    assert back_layout_blocks(with_both) == ["book_description", "author_biography"]


def test_short_draft_cannot_skip_review():
    state = store_description_draft(initial_content(), " ".join(["word"] * 100))
    reviewed = submit_for_review(state, "book_description")
    with pytest.raises(ContentContractError):
        approve(reviewed, "book_description", reviewer="editor")


def test_foundation_lock_refuses_a_complete_paid_authorization():
    authorization = empty_paid_authorization()
    authorization.update(
        {
            "explicit": True,
            "provider_id": "example_paid",
            "model_name": "example_model",
            "max_images": 1,
            "max_budget_usd": 2,
            "network_calls_allowed": True,
        }
    )
    decision = evaluate_paid_call(
        authorization=authorization,
        request={"provider_id": "example_paid", "model_name": "example_model", "image_count": 1},
        estimate_usd=0.04,
    )
    assert decision["allowed"] is False
    assert "paid_calls_disabled" in decision["reasons"]


def test_cover_record_keeps_canonical_text_and_drops_manuscript():
    book = _reference_book()
    cover = build_draft_cover(
        book,
        project_id="pastoral_retreat_v2_validation",
        book_version=INTERIOR_VERSION,
    )
    assert cover["front"]["title"] == BOOK_TITLE
    assert cover["front"]["subtitle"]
    assert cover["book_version"] == "print-review-v1.1"
    assert cover["source_document_version"] == "print-review-v1"
    assert "chapters" not in cover
    assert cover["export"]["front_docx"] is None
    assert cover["export"]["front_pdf"] is None


def test_new_modules_do_not_import_providers_or_torch():
    banned = {"requests", "openai", "anthropic", "torch", "diffusers", "huggingface_hub", "httpx"}
    hits = []
    root = repo_root()
    for relative in ("app/cover", "app/cover_generator_foundation_4b233"):
        for path in (root / relative).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module.split(".")[0]]
                hits.extend(name for name in names if name in banned)
    assert hits == []


def test_rejected_scope_does_not_run():
    with pytest.raises(CoverGeneratorFoundation4233Error):
        validate_authorization_scope("BOOK_PRINT_REVIEW_RENDER_4B231_DOCX_PDF_ONLY")
    result = run_phase(authorization_scope="not-this-phase", write_artifacts=False, run_tests=False)
    assert result.mode == "REJECTED"
    assert result.bundle == {}


def test_phase_stays_offline_without_writing_covers():
    before = Path(
        repo_root()
        / "sortie"
        / "pastoral_retreat_v2_validation"
        / "analysis"
        / "book.json"
    ).read_bytes()
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        write_artifacts=False,
        run_tests=False,
    )
    after = Path(
        repo_root()
        / "sortie"
        / "pastoral_retreat_v2_validation"
        / "analysis"
        / "book.json"
    ).read_bytes()
    header = result.bundle["header"]
    assert before == after
    assert result.mode == "PASS"
    assert header["provider_calls"] == 0
    assert header["canonical_hashes"] == "MATCH"
    assert header["cover_image_generated"] == "NO"
    assert header["cover_docx_generated"] == "NO"
    assert header["cover_pdf_generated"] == "NO"
    assert header["book_title"] == BOOK_TITLE
    hashes = result.bundle["canonical_hashes_pre_post"]
    assert hashes["match"] is True
    assert hashes["post"]["book_json"]["sha256"] == EXPECTED_BOOK_SHA256
