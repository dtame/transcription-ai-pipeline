"""4B.2.33 paths. book.json and the interior publication stay read-only."""

from __future__ import annotations

from pathlib import Path

from app.book_print_review_canonical_4b229.paths import (
    production_book_path as _production_book_path,
    repo_root as _repo_root,
    venv_python_path as _venv_python_path,
)
from app.book_print_review_pagination_fix_4b232.paths import (
    official_docx_path,
    official_pdf_path,
)
from app.cover.paths import default_library_root
from app.cover_generator_foundation_4b233.constants import (
    AUDIT_DIRNAME,
    COVER_RECORD_NAME,
    PROJECT_NAME,
    REPORT_NAME,
)
from app.word_renderer.profile import default_profile_path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return _repo_root()


def audit_root(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit"


def phase_audit_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_DIRNAME


def report_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / REPORT_NAME


def production_book_path(*, root: Path | None = None) -> Path:
    if root is None:
        return _production_book_path()
    return root / "sortie" / PROJECT_NAME / "analysis" / "book.json"


def interior_docx_path(*, root: Path | None = None) -> Path:
    if root is None:
        return official_docx_path()
    from app.cover_generator_foundation_4b233.constants import DOCX_FILENAME

    return root / "sortie" / PROJECT_NAME / "publication" / "print_review_v1_1" / DOCX_FILENAME


def interior_pdf_path(*, root: Path | None = None) -> Path:
    if root is None:
        return official_pdf_path()
    from app.cover_generator_foundation_4b233.constants import PDF_FILENAME

    return root / "sortie" / PROJECT_NAME / "publication" / "print_review_v1_1" / PDF_FILENAME


def word_profile_path() -> Path:
    return default_profile_path()


def cover_draft_dir(*, root: Path | None = None) -> Path:
    return (
        (root or repo_root())
        / "sortie"
        / PROJECT_NAME
        / "publication"
        / "covers"
        / "draft_v1"
    )


def cover_record_path(*, root: Path | None = None) -> Path:
    return cover_draft_dir(root=root) / COVER_RECORD_NAME


def author_library_root(*, root: Path | None = None) -> Path:
    return default_library_root(root=root or repo_root())


def venv_python_path(*, root: Path | None = None) -> Path:
    return _venv_python_path(root=root)


def is_protected_publication_path(path: Path) -> bool:
    text = str(path).replace("\\", "/").lower()
    return "/publication/print_review_v1/" in text or "/publication/print_review_v1_1/" in text


assert _PROJECT_ROOT == repo_root()

__all__ = [
    "author_library_root",
    "audit_root",
    "cover_draft_dir",
    "cover_record_path",
    "interior_docx_path",
    "interior_pdf_path",
    "is_protected_publication_path",
    "phase_audit_dir",
    "production_book_path",
    "repo_root",
    "report_path",
    "venv_python_path",
    "word_profile_path",
]
