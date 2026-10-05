"""Run phase 4B.2.34 offline and write the audit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.cover_flux2_pro_4b234.constants import EXPECTED_BOOK_SHA256
from app.cover_flux2_pro_4b234.documents import build_documents
from app.cover_flux2_pro_4b234.guard import Flux2PhaseError
from app.cover_flux2_pro_4b234.scenarios import evaluate_cases
from app.cover_flux2_pro_4b234.writer import write_documents
from app.cover_generator_foundation_4b233.hashes import (
    assert_protected_hashes,
    hashes_match,
    snapshot,
)
from app.cover_generator_foundation_4b233.paths import production_book_path


def run_phase(*, write_artifacts: bool = True, root: Path | None = None) -> dict[str, Any]:
    before = snapshot(root=root)
    assert_protected_hashes(before)
    cases = evaluate_cases()
    after = snapshot(root=root)
    if not hashes_match(before, after):
        raise Flux2PhaseError("book.json, the interior, or the Word profile changed. STOP.")
    book = json.loads(production_book_path(root=root).read_text(encoding="utf-8"))
    documents = build_documents(
        book=book,
        cases=cases,
        hashes={
            "match": True,
            "expected_book_sha256": EXPECTED_BOOK_SHA256,
            "pre": _public_hashes(before),
            "post": _public_hashes(after),
        },
    )
    written = write_documents(documents, root=root) if write_artifacts else {}
    final = snapshot(root=root)
    if not hashes_match(before, final):
        raise Flux2PhaseError("writing the audit changed a protected file. STOP.")
    return {
        "result": documents["readiness.json"]["result"],
        "written": written,
        "offline_tests": {
            "passed": cases["passed"],
            "failed": cases["failed"],
            "failed_names": cases["failed_names"],
        },
        "provider_calls": 0,
        "paid_cost_usd": 0,
    }


def _public_hashes(snap: dict[str, Any]) -> dict[str, Any]:
    return {
        "book_json": snap.get("book_json"),
        "interior_docx": snap.get("interior_docx"),
        "interior_pdf": snap.get("interior_pdf"),
        "word_profile": snap.get("word_profile"),
    }


__all__ = ["run_phase"]
