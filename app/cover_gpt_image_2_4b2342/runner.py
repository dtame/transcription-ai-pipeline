"""Run phase 4B.2.34.2 offline and write the audit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.cover.image_providers.bfl_transport import LIVE_HTTP_ENABLED
from app.cover_generator_foundation_4b233.hashes import (
    assert_protected_hashes,
    hashes_match,
    snapshot,
)
from app.cover_generator_foundation_4b233.paths import production_book_path, repo_root
from app.cover_gpt_image_2_4b2342.constants import EXPECTED_BOOK_SHA256
from app.cover_gpt_image_2_4b2342.documents import build_documents
from app.cover_gpt_image_2_4b2342.guard import GptImage2PhaseError
from app.cover_gpt_image_2_4b2342.paths import planned_image_path
from app.cover_gpt_image_2_4b2342.scenarios import evaluate_cases
from app.cover_gpt_image_2_4b2342.writer import write_documents


def run_phase(*, write_artifacts: bool = True, root: Path | None = None) -> dict[str, Any]:
    if LIVE_HTTP_ENABLED:
        raise GptImage2PhaseError("live HTTP is enabled. STOP.")
    before = snapshot(root=root)
    assert_protected_hashes(before)
    cases = evaluate_cases()
    if cases["failed"]:
        raise GptImage2PhaseError("offline tests failed: " + ", ".join(cases["failed_names"]))
    after = snapshot(root=root)
    if not hashes_match(before, after):
        raise GptImage2PhaseError("book.json, the interior, or the Word profile changed. STOP.")
    book_path = production_book_path(root=root)
    book_bytes = book_path.read_bytes()
    json.loads(book_bytes.decode("utf-8"))
    hashes = {
        "match": True,
        "expected_book_sha256": EXPECTED_BOOK_SHA256,
        "pre": _public_hashes(before),
        "post": _public_hashes(after),
    }
    documents = build_documents(cases=cases, hashes=hashes)
    if documents["first_image_test_plan.json"]["authorized"] is not False:
        raise GptImage2PhaseError("refusing to write an activated test plan")
    if documents["readiness.json"]["ready_for_first_image_test"] is not False:
        raise GptImage2PhaseError("refusing to mark the first image test ready")
    written = write_documents(documents, root=root) if write_artifacts else {}
    planned = Path(root) / planned_image_path() if root is not None else repo_root() / planned_image_path()
    if planned.exists():
        raise GptImage2PhaseError("refusing to leave a generated image on disk")
    final = snapshot(root=root)
    if not hashes_match(before, final):
        raise GptImage2PhaseError("writing the audit changed a protected file. STOP.")
    if book_path.read_bytes() != book_bytes:
        raise GptImage2PhaseError("book.json bytes changed. STOP.")
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
