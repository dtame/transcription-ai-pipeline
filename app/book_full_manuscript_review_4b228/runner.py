"""
Runner Phase 4B.2.28.

Assemble the 19 existing chapters into one reading manuscript and
consolidate offline editorial observations. Zero provider calls.
Zero generation. Zero rewrite.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from app.ai.provider_preflight import redact_secrets
from app.book_full_manuscript_review_4b228.assemble import (
    assemble_manuscript,
    manuscript_digest,
)
from app.book_full_manuscript_review_4b228.constants import (
    AUTHORIZATION_SCOPE,
    CANONICAL_PYTHON,
    EXPECTED_IDEA_COUNT,
    EXPECTED_SECTION_COUNT,
    HUMAN_ACCEPTANCE_STATUS,
    HUMAN_REVIEW_PENDING_STATUS,
    NEXT_ACTION,
    PHASE,
)
from app.book_full_manuscript_review_4b228.guard import (
    BookFullManuscriptReview4228Error,
    _is_later_print_review_draft,
    assert_no_publication,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_full_manuscript_review_4b228.hashes import (
    assert_accepted_unchanged,
    assert_candidates_present,
    assert_canonical,
    snapshot,
    snapshots_match,
)
from app.book_full_manuscript_review_4b228.human import (
    human_review_checklist,
    render_human_review_guide,
)
from app.book_full_manuscript_review_4b228.integrity import validate_manuscript_integrity
from app.book_full_manuscript_review_4b228.inventory import build_chapters_inventory
from app.book_full_manuscript_review_4b228.paths import (
    manuscript_path,
    production_book_path,
    repo_root,
    venv_python_path,
)
from app.book_full_manuscript_review_4b228.report import render_report
from app.book_full_manuscript_review_4b228.review import editorial_global_review
from app.book_full_manuscript_review_4b228.scenarios import evaluate_offline_scenarios
from app.book_full_manuscript_review_4b228.writer import write_phase_artifacts
from app.book_scale_up_preparation_4b220.corpus import load_canonical_corpus


@dataclass
class PhaseResult:
    accepted: bool
    mode: str
    bundle: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = ["app/tests/test_book_full_manuscript_review_4b228.py"]
    python = str(venv_python_path(root=root))
    completed = subprocess.run(
        [python, "-m", "pytest", "-q", "--tb=line", *tests],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = completed.stdout or ""
    summary = next(
        (
            line.strip()
            for line in reversed((stdout + "\n" + (completed.stderr or "")).splitlines())
            if "passed" in line or "failed" in line
        ),
        "",
    )
    passed_match = re.search(r"(\d+) passed", summary)
    failed_match = re.search(r"(\d+) failed", summary)
    return {
        "returncode": completed.returncode,
        "summary": summary,
        "passed": int(passed_match.group(1)) if passed_match else 0,
        "failed": int(failed_match.group(1))
        if failed_match
        else (0 if completed.returncode == 0 else 1),
        "stderr_tail": "\n".join((completed.stderr or "").strip().splitlines()[-12:]),
        "suites": tests,
        "real_provider_calls": 0,
        "openai_http_requests": 0,
        "anthropic_http_requests": 0,
        "phase": PHASE,
        "canonical_python": python,
    }


def run_phase(
    *,
    authorization_scope: str | None,
    write_artifacts: bool = True,
    run_tests: bool = True,
    root: Path | None = None,
) -> PhaseResult:
    result = PhaseResult(accepted=False, mode="OFFLINE")
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
        assert_no_publication(production_book_path())
    except BookFullManuscriptReview4228Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = snapshot(root=base)
    try:
        assert_canonical(before)
        assert_accepted_unchanged(before)
        assert_candidates_present(before)
        corpus = load_canonical_corpus()
        inventory = build_chapters_inventory(corpus=corpus, root=base)
        assembly = assemble_manuscript(inventory)
        integrity = validate_manuscript_integrity(
            inventory=inventory, assembly=assembly
        )
        editorial = editorial_global_review(inventory=inventory, corpus=corpus)
        checklist = human_review_checklist(inventory)
        guide = render_human_review_guide(
            inventory=inventory,
            editorial=editorial,
            integrity=integrity,
        )
        scenarios = evaluate_offline_scenarios(
            inventory=inventory,
            assembly=assembly,
            integrity=integrity,
            root=base,
        )
    except Exception as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        after = snapshot(root=base)
        bundle = {
            "header": {
                "result": "BLOCKED",
                "stop_reason": str(exc),
                "next_action": NEXT_ACTION,
            },
            "canonical_hashes_pre": before,
            "canonical_hashes_post": after,
            "readiness": {"READY_FOR_GLOBAL_HUMAN_REVIEW": False},
        }
        bundle["report_text"] = render_report(bundle)
        if write_artifacts:
            write_phase_artifacts(bundle, root=base)
        result.bundle = redact_secrets(bundle)
        return result

    tests = (
        _run_focused_tests(root=base)
        if run_tests
        else {
            "returncode": 0,
            "summary": "skipped",
            "passed": 0,
            "failed": 0,
            "suites": [],
            "real_provider_calls": 0,
        }
    )
    after = snapshot(root=base)
    hashes_ok = snapshots_match(before, after) and after["canonical_match_expected"]
    six_ok = bool(after.get("six_accepted_immutable"))
    thirteen_ok = before.get("remaining_chapters") == after.get("remaining_chapters")
    integrity_ok = integrity.get("status") == "PASS"
    paragraph_ok = integrity.get("paragraph_integrity") == "PASS"
    provenance_ok = integrity.get("provenance_integrity") == "PASS"
    pending_still_pending = all(
        row["human_status_exact"] == HUMAN_REVIEW_PENDING_STATUS
        for row in inventory["chapters"]
        if row["pending_human_review"]
    )
    accepted_still_accepted = all(
        row["human_status_exact"] == HUMAN_ACCEPTANCE_STATUS
        for row in inventory["chapters"]
        if row["accepted"]
    )
    test_failures = int(tests.get("failed") or 0) + int(scenarios.get("failed") or 0)
    ready = all(
        (
            integrity_ok,
            paragraph_ok,
            provenance_ok,
            hashes_ok,
            six_ok,
            thirteen_ok,
            pending_still_pending,
            accepted_still_accepted,
            test_failures == 0,
            (
                not production_book_path().is_file()
                or _is_later_print_review_draft(production_book_path())
            ),
            inventory["chapter_count"] == 19,
            inventory["section_count"] == EXPECTED_SECTION_COUNT,
            inventory["idea_coverage_count"] == EXPECTED_IDEA_COUNT,
        )
    )
    if not hashes_ok or not six_ok or not thirteen_ok:
        result_label = "FAIL"
    elif not integrity_ok:
        result_label = "FAIL"
    elif ready:
        result_label = "PASS"
    else:
        result_label = "PARTIAL"

    manuscript_text = assembly["manuscript_text"]
    digest = manuscript_digest(manuscript_text)
    markdown_path = str(manuscript_path(root=base)).replace("\\", "/")
    header = {
        "result": result_label,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "provider_calls": 0,
        "anthropic_http": 0,
        "openai_http": 0,
        "chapters_assembled": f"{inventory['chapter_count']} / 19",
        "sections_assembled": f"{inventory['section_count']} / {EXPECTED_SECTION_COUNT}",
        "idea_coverage": f"{inventory['idea_coverage_count']} / {EXPECTED_IDEA_COUNT}",
        "accepted_chapters": ", ".join(inventory["accepted_chapter_ids"]),
        "human_review_pending_chapters": ", ".join(inventory["pending_chapter_ids"]),
        "manuscript_markdown_path": markdown_path,
        "manuscript_word_count": assembly["manuscript_word_count"],
        "manuscript_sha256": digest,
        "paragraph_integrity": integrity.get("paragraph_integrity"),
        "provenance_integrity": integrity.get("provenance_integrity"),
        "strengthened_claim_observations": editorial["strengthened_claims"][
            "observation_count"
        ],
        "references_examples_observations": (
            len(editorial["references_examples"]["historical_observations"])
            + editorial["references_examples"]["similar_observation_count"]
        ),
        "continuity_observations": editorial["continuity"]["observation_count"],
        "human_review_guide": str(
            (manuscript_path(root=base).parent / "human_review_guide.md")
        ).replace("\\", "/"),
        "canonical_hashes_pre_post": "MATCH" if hashes_ok else "MISMATCH",
        "six_accepted_chapters_immutable": _yn(six_ok),
        "thirteen_candidates_immutable": _yn(thirteen_ok),
        "ready_for_global_human_review": _yn(ready),
        "next_action": NEXT_ACTION,
        "canonical_python": CANONICAL_PYTHON,
        "notes": (
            "The 19 existing chapters were assembled into one Markdown reading "
            "manuscript. Chapter prose was not rewritten. The six accepted "
            "chapters remain accepted. The thirteen new chapters remain pending "
            "human review. No provider was called."
        ),
    }
    readiness = {
        "READY_FOR_GLOBAL_HUMAN_REVIEW": ready,
        "CHAPTERS_ASSEMBLED": inventory["chapter_count"],
        "SECTIONS_ASSEMBLED": inventory["section_count"],
        "IDEA_COVERAGE": inventory["idea_coverage_count"],
        "PARAGRAPH_INTEGRITY": integrity.get("paragraph_integrity"),
        "PROVENANCE_INTEGRITY": integrity.get("provenance_integrity"),
        "SIX_ACCEPTED_CHAPTERS_IMMUTABLE": six_ok,
        "THIRTEEN_CANDIDATES_IMMUTABLE": thirteen_ok,
        "HUMAN_REVIEW_PENDING": pending_still_pending,
        "CANONICAL_HASHES": "MATCH" if hashes_ok else "MISMATCH",
        "SEMANTIC_CERTIFICATION": "NOT PERFORMED",
        "book_json": "NOT PUBLISHED",
        "DOCX": "NOT GENERATED",
        "PDF": "NOT GENERATED",
        "NEXT_ACTION": NEXT_ACTION,
        "why": "MANUSCRIPT_ASSEMBLED_FOR_HUMAN_REVIEW" if ready else result_label,
    }
    preflight = {
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "offline": True,
        "provider_calls": 0,
        "canonical_hashes_ok": before["canonical_match_expected"],
        "real_generation_authorized": False,
        "secrets_included": False,
    }
    hashes_pre_post = {
        "phase": PHASE,
        "pre": before,
        "post": after,
        "match": hashes_ok,
        "status": "MATCH" if hashes_ok else "MISMATCH",
        "six_accepted_immutable": six_ok,
        "thirteen_candidates_immutable": thirteen_ok,
        "secrets_included": False,
    }
    inventory_public = dict(inventory)
    slim_chapters = []
    for row in inventory["chapters"]:
        public = dict(row)
        public.pop("paragraphs", None)
        slim_chapters.append(public)
    inventory_public["chapters"] = slim_chapters
    bundle = {
        "header": header,
        "preflight": preflight,
        "canonical_hashes_pre": before,
        "chapters_inventory": inventory_public,
        "manuscript_text": manuscript_text,
        "manuscript_provenance_manifest": assembly["provenance"],
        "manuscript_integrity_validation": integrity,
        "manuscript_assembly_spec": assembly["assembly_spec"],
        "paragraph_traceability": {
            "phase": PHASE,
            "paragraphs": assembly["paragraphs"],
            "count": len(assembly["paragraphs"]),
            "secrets_included": False,
        },
        "editorial_global_review": editorial,
        "editorial_global_review_payload": editorial["payload"],
        "editorial_global_review_markdown": editorial["markdown"],
        "strengthened_claims_review": editorial["strengthened_claims"],
        "references_examples_review": editorial["references_examples"],
        "continuity_review": editorial["continuity"],
        "human_review_checklist": checklist,
        "human_review_guide_text": guide,
        "canonical_hashes_pre_post": hashes_pre_post,
        "canonical_hashes_post": after,
        "offline_regression_tests": {
            "pytest": tests,
            "scenarios": scenarios,
        },
        "readiness": readiness,
    }
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        write_phase_artifacts(bundle, root=base)
    result.bundle = redact_secrets(bundle)
    result.accepted = result_label == "PASS"
    result.mode = result_label
    result.error = "" if result_label == "PASS" else result_label
    return result


def _unused_mapping_probe(value: Mapping[str, Any] | None) -> None:
    del value


__all__ = ["PhaseResult", "run_phase"]
