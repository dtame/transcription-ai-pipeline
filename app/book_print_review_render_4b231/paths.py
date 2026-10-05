"""4B.2.31 paths. book.json is read-only. Official print-review lives under publication/."""

from __future__ import annotations

from pathlib import Path

from app.book_print_review_canonical_4b229.paths import (
    production_book_path as _production_book_path,
    repo_root as _repo_root,
    venv_python_path as _venv_python_path,
)
from app.book_print_review_render_4b231.constants import (
    AUDIT_DIRNAME,
    DOCX_FILENAME,
    PDF_FILENAME,
    PROJECT_NAME,
    PUBLICATION_REL,
    REPORT_NAME,
    UNFINALIZED_DOCX_FILENAME,
    WORKING_DOCX_FILENAME,
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
    del root
    return _production_book_path()


def official_publication_root() -> Path:
    return repo_root() / "sortie" / PROJECT_NAME / "publication" / "print_review_v1"


def publication_dir(*, root: Path | None = None) -> Path:
    base = root or repo_root()
    return base / "sortie" / PROJECT_NAME / "publication" / "print_review_v1"


def official_docx_path(*, root: Path | None = None) -> Path:
    return publication_dir(root=root) / DOCX_FILENAME


def official_pdf_path(*, root: Path | None = None) -> Path:
    return publication_dir(root=root) / PDF_FILENAME


def unfinalized_docx_path(*, root: Path | None = None) -> Path:
    return phase_audit_dir(root=root) / UNFINALIZED_DOCX_FILENAME


def working_docx_path(*, root: Path | None = None) -> Path:
    return phase_audit_dir(root=root) / WORKING_DOCX_FILENAME


def print_profile_path() -> Path:
    return default_profile_path()


def venv_python_path(*, root: Path | None = None) -> Path:
    return _venv_python_path(root=root)


def is_official_publication_path(path: Path) -> bool:
    official = official_publication_root().resolve()
    resolved = Path(path).resolve()
    return resolved == official or official in resolved.parents or resolved.parent == official


assert _PROJECT_ROOT == repo_root()
assert PUBLICATION_REL.endswith("print_review_v1")

__all__ = [
    "audit_root",
    "is_official_publication_path",
    "official_docx_path",
    "official_pdf_path",
    "official_publication_root",
    "phase_audit_dir",
    "print_profile_path",
    "production_book_path",
    "publication_dir",
    "repo_root",
    "report_path",
    "unfinalized_docx_path",
    "venv_python_path",
    "working_docx_path",
]
