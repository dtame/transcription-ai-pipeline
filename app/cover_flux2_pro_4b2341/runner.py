"""Run phase 4B.2.34.1 offline and write the audit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.cover.image_providers.bfl_transport import LIVE_HTTP_ENABLED
from app.cover_flux2_pro_4b2341.constants import EXPECTED_BOOK_SHA256
from app.cover_flux2_pro_4b2341.documents import build_documents
from app.cover_flux2_pro_4b2341.guard import Flux2UnblockError
from app.cover_flux2_pro_4b2341.scenarios import evaluate_cases
from app.cover_flux2_pro_4b2341.writer import write_documents
from app.cover_generator_foundation_4b233.hashes import (
    assert_protected_hashes,
    hashes_match,
    snapshot,
)
from app.cover_generator_foundation_4b233.paths import production_book_path


def run_phase(*, write_artifacts: bool = True, root: Path | None = None) -> dict[str, Any]:
    if LIVE_HTTP_ENABLED:
        raise Flux2UnblockError("live HTTP is enabled. STOP.")
    before = snapshot(root=root)
    assert_protected_hashes(before)
    cases = evaluate_cases()
    if cases["failed"]:
        raise Flux2UnblockError("offline tests failed: " + ", ".join(cases["failed_names"]))
    after = snapshot(root=root)
    if not hashes_match(before, after):
        raise Flux2UnblockError("book.json, the interior, or the Word profile changed. STOP.")
    book = json.loads(production_book_path(root=root).read_text(encoding="utf-8"))
    hashes = {
        "match": True,
        "expected_book_sha256": EXPECTED_BOOK_SHA256,
        "pre": _public_hashes(before),
        "post": _public_hashes(after),
    }
    documents = build_documents(book=book, cases=cases, hashes=hashes)
    if documents["first_image_test_plan.json"]["authorized"] is not False:
        raise Flux2UnblockError("refusing to write an activated test plan")
    if documents["readiness.json"]["ready_for_first_image_test"] is not False:
        raise Flux2UnblockError("refusing to mark the first image test ready")
    written = write_documents(documents, root=root) if write_artifacts else {}
    final = snapshot(root=root)
    if not hashes_match(before, final):
        raise Flux2UnblockError("writing the audit changed a protected file. STOP.")
    return {
        "result": documents["readiness.json"]["result"],
        "decision": documents["readiness.json"]["decision"],
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
