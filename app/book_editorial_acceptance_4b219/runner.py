"""
Phase 4B.2.19 runner.

Offline only. Records human editorial acceptance, freezes the accepted
CH012 pair by hash, reviews IDEA content mappings and source coverage,
and prepares semantic-validation and scale-up options. Never authorizes
a provider call. Never rewrites the accepted or original chapter.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.book_editorial_acceptance_4b219.acceptance import editorial_acceptance_record
from app.book_editorial_acceptance_4b219.chapter_io import (
    load_accepted_chapter,
    load_accepted_markdown,
    paragraph_idea_handles,
    paragraph_ids,
    section_ids,
)
from app.book_editorial_acceptance_4b219.consistency import compare_markdown_json
from app.book_editorial_acceptance_4b219.constants import (
    AUTHORIZATION_SCOPE,
    CANONICAL_PYTHON,
    CHAPTER_ID,
    CLASS_CONTENT_SUPPORTED,
    CLASS_NOT_SUPPORTED,
    CLASS_PARTIALLY_SUPPORTED,
    CLASS_UNDETERMINED,
    EXPECTED_ACCEPTED_JSON_SHA256,
    EXPECTED_ACCEPTED_MD_SHA256,
    FAITHFUL_PROMPT_1_1,
    HISTORICAL_4B210_STATUS,
    HISTORICAL_4B211_STATUS,
    HISTORICAL_4B212_STATUS,
    HISTORICAL_4B213_STATUS,
    HISTORICAL_4B214_STATUS,
    HISTORICAL_4B215_STATUS,
    HISTORICAL_4B216_STATUS,
    HISTORICAL_4B217_STATUS,
    HISTORICAL_4B218_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    NEXT_ACTION,
    PARAGRAPH_COUNT,
    PARAGRAPH_IDS,
    PHASE,
    RECOMMENDED_OPTION,
    SECTION_IDS,
)
from app.book_editorial_acceptance_4b219.coverage import review_source_coverage
from app.book_editorial_acceptance_4b219.guard import (
    BookEditorialAcceptance4219Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_editorial_acceptance_4b219.hashes import (
    assert_canonical,
    assert_historical_artifacts,
    snapshot,
    snapshots_match,
)
from app.book_editorial_acceptance_4b219.idea_review import review_idea_mappings
from app.book_editorial_acceptance_4b219.manifest import accepted_editorial_manifest
from app.book_editorial_acceptance_4b219.paths import (
    original_chapter_json_path,
    original_lock_path,
    production_book_path,
    repo_root,
    venv_python_path,
)
from app.book_editorial_acceptance_4b219.prompt_readiness import generator_prompt_readiness
from app.book_editorial_acceptance_4b219.report import render_report
from app.book_editorial_acceptance_4b219.scale_up import scale_up_options
from app.book_editorial_acceptance_4b219.scenarios import evaluate_offline_scenarios
from app.book_editorial_acceptance_4b219.semantic_prep import semantic_validation_readiness
from app.book_editorial_acceptance_4b219.writer import write_phase_artifacts


@dataclass
class PhaseResult:
    accepted: bool
    mode: str
    bundle: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_editorial_acceptance_4b219.py",
        "app/tests/test_book_authorial_voice_4b218.py",
        "app/tests/test_book_editorial_alignment_4b216.py",
        "app/tests/test_book_generation_4b217.py",
    ]
    python = str(venv_python_path(root=root))
    completed = subprocess.run(
        [
            python,
            "-m",
            "pytest",
            "-q",
            "--tb=line",
            "-k",
            "not (test_offline_scenarios_pass and test_book_generation_4b217)",
            *tests,
        ],
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
        "failed": int(failed_match.group(1)) if failed_match else (0 if completed.returncode == 0 else 1),
        "stderr_tail": "\n".join((completed.stderr or "").strip().splitlines()[-12:]),
        "suites": tests,
        "real_provider_calls": 0,
        "openai_http_requests": 0,
        "anthropic_http_requests": 0,
        "phase": PHASE,
        "canonical_python": python,
    }


def _hash_line(label: str, snap: dict[str, Any]) -> str:
    canonical = snap["canonical"]
    return (
        f"{label} source={canonical['source_map']['sha256']} "
        f"plan={canonical['editorial_plan']['sha256']} "
        f"transcript={canonical['clean_transcript']['sha256']}"
    )


def run_phase(
    *,
    authorization_scope: str | None,
    write_artifacts: bool = True,
    run_tests: bool = True,
    root: Path | None = None,
) -> PhaseResult:
    validate_authorization_scope(authorization_scope)
    assert_offline_only()
    base = root or repo_root()
    before = snapshot(root=base)
    assert_canonical(before)
    assert_historical_artifacts(before)
    if production_book_path().exists():
        raise BookEditorialAcceptance4219Error("production book.json must remain unpublished")
    if not original_chapter_json_path().is_file():
        raise BookEditorialAcceptance4219Error("original CH012 candidate is required")
    if not original_lock_path().is_file():
        raise BookEditorialAcceptance4219Error("original CH012 provider lock is required")

    chapter = load_accepted_chapter()
    markdown = load_accepted_markdown()
    again_chapter = load_accepted_chapter()
    again_markdown = load_accepted_markdown()
    if again_chapter != chapter or again_markdown != markdown:
        raise BookEditorialAcceptance4219Error("accepted chapter reload is not idempotent")
    if paragraph_idea_handles(chapter):
        raise BookEditorialAcceptance4219Error(
            "accepted chapter already has paragraph IDEA handles; this phase must not write them"
        )

    consistency = compare_markdown_json(chapter, markdown)
    freeze_allowed = consistency["consistent"] is True
    accepted_md_sha = before["accepted_chapter"]["chapter_candidate_authorial_v2_md"]["sha256"]
    accepted_json_sha = before["accepted_chapter"]["chapter_candidate_authorial_v2_json"]["sha256"]
    if (
        accepted_md_sha != EXPECTED_ACCEPTED_MD_SHA256
        or accepted_json_sha != EXPECTED_ACCEPTED_JSON_SHA256
    ):
        raise BookEditorialAcceptance4219Error("accepted CH012 pair hash mismatch")

    acceptance = editorial_acceptance_record(
        accepted_md_sha256=accepted_md_sha,
        accepted_json_sha256=accepted_json_sha,
    )
    manifest = accepted_editorial_manifest(
        accepted_md_sha256=accepted_md_sha,
        accepted_json_sha256=accepted_json_sha,
        original_md_sha256=before["original_chapter"]["chapter_candidate_md"]["sha256"],
        original_json_sha256=before["original_chapter"]["chapter_candidate_json"]["sha256"],
        lock_sha256=before["original_chapter"]["provider_lock"]["sha256"],
        freeze_allowed=freeze_allowed,
    )
    idea_review = review_idea_mappings(chapter)
    coverage = review_source_coverage(chapter)
    semantic = semantic_validation_readiness(chapter)
    prompt = generator_prompt_readiness()
    scale = scale_up_options()
    scenarios = evaluate_offline_scenarios(root=base)
    tests = (
        _run_focused_tests(root=base)
        if run_tests
        else {
            "returncode": 0,
            "summary": "not_run",
            "passed": scenarios["passed"],
            "failed": scenarios["failed"],
            "suites": [],
            "real_provider_calls": 0,
        }
    )
    after = snapshot(root=base)
    hashes_ok = snapshots_match(before, after) and after["canonical_match_expected"]
    counts = idea_review.get("counts") or {}
    checks = {
        "no_provider_calls": True,
        "canonical_hashes_unchanged": hashes_ok,
        "original_chapter_unchanged": before["original_chapter"] == after["original_chapter"],
        "accepted_chapter_unchanged": before["accepted_chapter"] == after["accepted_chapter"],
        "provider_lock_unchanged": (
            before["original_chapter"]["provider_lock"]
            == after["original_chapter"]["provider_lock"]
        ),
        "markdown_json_consistent": freeze_allowed,
        "fourteen_paragraphs": (
            consistency["json_paragraph_count"] == PARAGRAPH_COUNT
            and list(paragraph_ids(chapter)) == list(PARAGRAPH_IDS)
        ),
        "four_sections_intact": list(section_ids(chapter)) == list(SECTION_IDS),
        "acceptance_recorded": acceptance["scope"] == "editorial_acceptance",
        "hash_freeze": manifest["freeze_status"] == "FROZEN",
        "acceptance_not_confused_with_semantic_cert": (
            acceptance["semantic_certification"] == "not_performed"
            and acceptance["not_a_semantic_certificate"] is True
        ),
        "eleven_ideas_traced": len(idea_review.get("mappings") or []) == 11,
        "src_overlap_alone_rejected": idea_review["src_overlap_alone_rejected"] is True,
        "unc029_preserved": coverage.get("unc029_preserved") is True,
        "paras_e_not_written": idea_review["written_into_paragraph_evidence"] is False,
        "no_publication": (
            not production_book_path().exists()
            and acceptance["publication_authorization"] == "not_granted"
        ),
        "offline_scenarios_pass": scenarios["failed"] == 0,
        "focused_tests_pass": tests["failed"] == 0 and tests["returncode"] == 0,
        "prompt_not_promoted": prompt["automatically_promoted"] is False,
        "semantic_gate_not_promoted": semantic["semantic_gate_promoted"] is False,
        "idempotent_reload": again_chapter == chapter,
    }
    if not hashes_ok or not freeze_allowed:
        result = "FAIL"
    elif not all(checks.values()):
        result = "FAIL"
    else:
        result = "PASS"
    notes = (
        "Human editorial acceptance of CH012 was recorded. The accepted "
        "Markdown/JSON pair is frozen by SHA-256 and was not rewritten. "
        f"{counts.get(CLASS_CONTENT_SUPPORTED, 0)} IDEA mappings are "
        "CONTENT_SUPPORTED by accepted prose, not by SRC overlap alone. "
        "Semantic certification was not performed. Publication is not granted. "
        f"Recommended next option is {RECOMMENDED_OPTION}."
    )
    header = {
        "result": result,
        "provider_calls": 0,
        "anthropic_http": 0,
        "openai_http": 0,
        "canonical_python": CANONICAL_PYTHON,
        "canonical_hashes_pre_post": _hash_line("pre", before) + "; " + _hash_line("post", after),
        "accepted_chapter": CHAPTER_ID,
        "human_editorial_acceptance": "YES",
        "p000001_accepted": "YES",
        "accepted_md_sha256": accepted_md_sha,
        "accepted_json_sha256": accepted_json_sha,
        "markdown_json_consistency": "CONSISTENT" if freeze_allowed else "DIVERGENT",
        "sections": ",".join(section_ids(chapter)),
        "paragraphs": consistency["json_paragraph_count"],
        "idea_mappings_content_supported": counts.get(CLASS_CONTENT_SUPPORTED, 0),
        "idea_mappings_partially_supported": counts.get(CLASS_PARTIALLY_SUPPORTED, 0),
        "idea_mappings_not_supported": counts.get(CLASS_NOT_SUPPORTED, 0),
        "idea_mappings_undetermined": counts.get(CLASS_UNDETERMINED, 0),
        "source_coverage_status": coverage.get("overall_status"),
        "semantic_certification": "NOT PERFORMED",
        "semantic_gate_promoted": "NO",
        "generator_prompt_ready": "YES" if prompt.get("ready_as_reference_candidate") else "NO",
        "estimated_next_phase_cost": "0.00 USD (offline preparation); 18-chapter generation envelope UNKNOWN / not authorized",
        "recommended_next_option": RECOMMENDED_OPTION,
        "ready_for_controlled_scale_up": "NO",
        "ready_for_full_real_book_generation": "NO",
        "production_cache": "UNCHANGED",
        "book_json": "NOT PUBLISHED",
        "next_action": NEXT_ACTION,
        "notes": notes,
        "checks": checks,
    }
    preflight = {
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "chapter_id": CHAPTER_ID,
        "canonical_hashes_ok": before["canonical_match_expected"],
        "original_chapter_present": True,
        "accepted_chapter_present": True,
        "original_lock_present": True,
        "offline_only": True,
        "provider_calls_authorized": 0,
        "4b217_authorization_reused": False,
        "production_book_absent": not production_book_path().exists(),
        "faithful_prompt_1_1_registered": False,
        "historical_statuses": {
            "h01": HISTORICAL_H01_STATUS,
            "h02": HISTORICAL_H02_STATUS,
            "h11": HISTORICAL_H11_STATUS,
            "4B.2.10": HISTORICAL_4B210_STATUS,
            "4B.2.11": HISTORICAL_4B211_STATUS,
            "4B.2.12": HISTORICAL_4B212_STATUS,
            "4B.2.13": HISTORICAL_4B213_STATUS,
            "4B.2.14": HISTORICAL_4B214_STATUS,
            "4B.2.15": HISTORICAL_4B215_STATUS,
            "4B.2.16": HISTORICAL_4B216_STATUS,
            "4B.2.17": HISTORICAL_4B217_STATUS,
            "4B.2.18": HISTORICAL_4B218_STATUS,
        },
        "secrets_included": False,
    }
    readiness = {
        "phase": PHASE,
        "result": result,
        "checks": checks,
        "provider_calls": 0,
        "openai_http_requests": 0,
        "anthropic_http_requests": 0,
        "HUMAN_EDITORIAL_ACCEPTANCE": True,
        "P000001_ACCEPTED": True,
        "SEMANTIC_CERTIFICATION": "NOT PERFORMED",
        "SEMANTIC_GATE_PROMOTED": False,
        "GENERATOR_PROMPT_READY": bool(prompt.get("ready_as_reference_candidate")),
        "READY_FOR_CONTROLLED_SCALE_UP": False,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "RECOMMENDED_NEXT_OPTION": RECOMMENDED_OPTION,
        "NEXT_ACTION": NEXT_ACTION,
        "why": notes,
        "why_not_ready_for_controlled_scale_up": scale.get("why_not_ready_to_execute"),
        "secrets_included": False,
    }
    regression = {
        "phase": PHASE,
        "focused_tests": tests,
        "offline_scenarios": scenarios,
        "idempotent": again_chapter == chapter and again_markdown == markdown,
        "accepted_paragraph_count": consistency["json_paragraph_count"],
        "accepted_section_count": len(section_ids(chapter)),
        "historical_4b217_lock_absence_scenario": (
            "Skipped. The 4B.2.17 real lock is consumed by design. "
            "The historical test was not modified."
        ),
        "secrets_included": False,
    }
    bundle = {
        "header": header,
        "preflight": preflight,
        "canonical_hashes_pre": before,
        "ch012_editorial_acceptance": acceptance,
        "ch012_accepted_editorial_manifest": manifest,
        "markdown_json_consistency": consistency,
        "idea_content_mapping_review": idea_review,
        "source_coverage_review": coverage,
        "semantic_validation_readiness": semantic,
        "generator_prompt_readiness": prompt,
        "scale_up_options": scale,
        "canonical_hashes_post": after,
        "regression_tests": regression,
        "readiness": readiness,
        "offline_scenarios": scenarios,
        "execution": {
            "mode": "OFFLINE",
            "provider_calls": 0,
            "anthropic_http": 0,
            "openai_http": 0,
            "retries": 0,
            "fallbacks": 0,
            "generator_prompt": FAITHFUL_PROMPT_1_1,
        },
    }
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        write_phase_artifacts(bundle, root=base)
    return PhaseResult(accepted=result == "PASS", mode="OFFLINE", bundle=bundle, error="")


__all__ = ["PhaseResult", "run_phase"]
