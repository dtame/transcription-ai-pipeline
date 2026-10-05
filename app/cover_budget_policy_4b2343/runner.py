"""Run phase 4B.2.34.3 offline and write the audit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.cover.image_providers.bfl_transport import LIVE_HTTP_ENABLED
from app.cover.image_providers.budget_policy import (
    EXPERIMENTAL_SUBMISSION_ENABLED,
    first_experimental_image_plan,
)
from app.cover_budget_policy_4b2343.constants import EXPECTED_BOOK_SHA256
from app.cover_budget_policy_4b2343.documents import build_documents
from app.cover_budget_policy_4b2343.guard import BudgetPolicyPhaseError
from app.cover_budget_policy_4b2343.paths import planned_image_path
from app.cover_budget_policy_4b2343.scenarios import evaluate_cases
from app.cover_budget_policy_4b2343.writer import write_documents
from app.cover_generator_foundation_4b233.hashes import (
    assert_protected_hashes,
    hashes_match,
    snapshot,
)
from app.cover_generator_foundation_4b233.paths import production_book_path, repo_root


def run_phase(*, write_artifacts: bool = True, root: Path | None = None) -> dict[str, Any]:
    if LIVE_HTTP_ENABLED:
        raise BudgetPolicyPhaseError("live HTTP is enabled. STOP.")
    if EXPERIMENTAL_SUBMISSION_ENABLED:
        raise BudgetPolicyPhaseError("experimental submission is enabled. STOP.")
    plan = first_experimental_image_plan()
    if plan["authorized"] is not False or plan["effective"] is not False:
        raise BudgetPolicyPhaseError("refusing to write an effective authorization")
    if plan["explicit_user_approval"] is not False or plan["accepts_unbounded_provider_cost"] is not False:
        raise BudgetPolicyPhaseError("refusing to pre-approve the experimental plan")
    before = snapshot(root=root)
    assert_protected_hashes(before)
    cases = evaluate_cases()
    if cases["failed"]:
        raise BudgetPolicyPhaseError("offline tests failed: " + ", ".join(cases["failed_names"]))
    after = snapshot(root=root)
    if not hashes_match(before, after):
        raise BudgetPolicyPhaseError("book.json, the interior, or the Word profile changed. STOP.")
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
    if documents["first_experimental_image_plan.json"]["authorized"] is not False:
        raise BudgetPolicyPhaseError("refusing to write an activated test plan")
    if documents["readiness.json"]["first_image_authorized"] is not False:
        raise BudgetPolicyPhaseError("refusing to mark the first image authorized")
    if documents["readiness.json"]["experimental_submission_enabled"] is not False:
        raise BudgetPolicyPhaseError("refusing to enable experimental submission")
    written = write_documents(documents, root=root) if write_artifacts else {}
    planned = Path(root) / planned_image_path() if root is not None else repo_root() / planned_image_path()
    if planned.exists():
        raise BudgetPolicyPhaseError("refusing to leave a generated image on disk")
    final = snapshot(root=root)
    if not hashes_match(before, final):
        raise BudgetPolicyPhaseError("writing the audit changed a protected file. STOP.")
    if book_path.read_bytes() != book_bytes:
        raise BudgetPolicyPhaseError("book.json bytes changed. STOP.")
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
