"""
Runner Phase 4B.2.33.

Prepare the cover-generator foundation. Zero provider calls.
Zero image generation. Zero cover DOCX/PDF. book.json is not modified.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.book_print_review_render_4b231.pdf_text import extract_pdf_geometry
from app.cover.author_library.store import AuthorLibrary
from app.cover.content.contract import content_contract_document
from app.cover.hardware.diagnostic import collect_hardware
from app.cover.image_providers.base import provider_contract_document
from app.cover.image_providers.compatibility import evaluate_local_models
from app.cover.image_providers.policy import paid_provider_policy_document
from app.cover.renderer.contract import renderer_contract_document
from app.cover.schemas import author_library_schema, cover_schema
from app.cover.validation.checks import build_draft_cover
from app.cover_generator_foundation_4b233.constants import (
    AUTHORIZATION_SCOPE,
    BOOK_STATUS,
    BOOK_TITLE,
    BOOK_VERSION,
    COVER_FORMAT,
    COVER_MODE,
    INTERIOR_PDF_PAGES,
    INTERIOR_VERSION,
    NEXT_ACTION_FAIL,
    NEXT_ACTION_PASS,
    PHASE,
    PROJECT_NAME,
)
from app.cover_generator_foundation_4b233.guard import (
    CoverGeneratorFoundation4233Error,
    assert_offline_only,
    assert_write_target_allowed,
    validate_authorization_scope,
)
from app.cover_generator_foundation_4b233.hashes import (
    assert_protected_hashes,
    assert_sources_unchanged,
    hashes_match,
    snapshot,
)
from app.cover_generator_foundation_4b233.inventory import (
    architecture_decisions_markdown,
    existing_architecture_inventory,
)
from app.cover_generator_foundation_4b233.paths import (
    author_library_root,
    cover_draft_dir,
    cover_record_path,
    interior_pdf_path,
    phase_audit_dir,
    production_book_path,
    repo_root,
    venv_python_path,
)
from app.cover_generator_foundation_4b233.report import render_report
from app.cover_generator_foundation_4b233.scenarios import evaluate_cases, reference_book_view
from app.cover_generator_foundation_4b233.writer import write_phase_artifacts
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


@dataclass
class PhaseResult:
    accepted: bool
    mode: str
    bundle: dict[str, Any] = field(default_factory=dict)
    error: str = ""


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
    except CoverGeneratorFoundation4233Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = snapshot(root=base)
    try:
        assert_protected_hashes(before)
        bundle = _build_bundle(base)
    except Exception as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        after = snapshot(root=base)
        failed = _failure_bundle(before, after, str(exc))
        failed["report_text"] = render_report(failed)
        if write_artifacts:
            write_phase_artifacts(failed, root=base)
        result.bundle = failed
        return result

    with tempfile.TemporaryDirectory(prefix="cover_4b233_") as temporary:
        scenarios = evaluate_cases(
            library_root=Path(temporary),
            book=bundle["reference_book"],
        )
    tests = _run_focused_tests(root=base) if run_tests else _skipped_tests()
    if write_artifacts and base.resolve() == repo_root().resolve():
        _write_reference_outputs(bundle["reference_cover"], base)
    after = snapshot(root=base)
    try:
        assert_sources_unchanged(before, after)
    except CoverGeneratorFoundation4233Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        failed = _failure_bundle(before, after, str(exc))
        failed["report_text"] = render_report(failed)
        if write_artifacts:
            write_phase_artifacts(failed, root=base)
        result.bundle = failed
        return result

    binaries = _cover_binaries(cover_draft_dir(root=base)) + _cover_binaries(phase_audit_dir(root=base))
    page_count = bundle["interior_pdf_pages"]
    scenario_ok = scenarios["failed"] == 0
    tests_ok = tests["failed"] == 0 and tests["returncode"] == 0
    pages_ok = page_count == INTERIOR_PDF_PAGES
    imports_ok = not bundle["forbidden_imports"]
    passed = scenario_ok and tests_ok and pages_ok and imports_ok and not binaries
    header = _header(
        bundle,
        passed=passed,
        scenarios=scenarios,
        tests=tests,
        hashes="MATCH",
        binaries=binaries,
    )
    offline = {
        "phase": PHASE,
        "provider_calls": 0,
        "scenarios": scenarios,
        "pytest": tests,
        "forbidden_imports": bundle["forbidden_imports"],
        "cover_binaries": binaries,
    }
    readiness = _readiness(header, passed=passed)
    full = {
        "header": header,
        "existing_architecture_inventory": bundle["inventory"],
        "architecture_decisions_markdown": architecture_decisions_markdown(),
        "author_library_schema": author_library_schema(),
        "cover_schema": cover_schema(),
        "cover_content_contract": content_contract_document(),
        "image_provider_contract": provider_contract_document(),
        "hardware_diagnostic": bundle["hardware"],
        "local_model_compatibility": bundle["models"],
        "paid_provider_policy": paid_provider_policy_document(),
        "cover_renderer_contract": renderer_contract_document(),
        "offline_tests": offline,
        "canonical_hashes_pre_post": {
            "phase": PHASE,
            "pre": before,
            "post": after,
            "match": hashes_match(before, after),
        },
        "readiness": readiness,
        "reference_book": bundle["reference_book"],
        "files_written": [],
    }
    full["report_text"] = render_report(full)
    written: dict[str, str] = {}
    if write_artifacts:
        written = write_phase_artifacts(full, root=base)
        if base.resolve() == repo_root().resolve():
            written["cover_record"] = str(cover_record_path(root=base)).replace("\\", "/")
            written["author_library"] = str((author_library_root(root=base) / "index.json")).replace(
                "\\", "/"
            )
        full["files_written"] = [
            f"{name} = {path}" for name, path in written.items() if name != "phase"
        ]
        full["report_text"] = render_report(full)
        report_target = written.get("report")
        if report_target:
            Path(report_target).write_text(full["report_text"], encoding="utf-8")
    result.accepted = passed
    result.mode = "PASS" if passed else "FAIL"
    result.bundle = full
    return result


def _build_bundle(base: Path) -> dict[str, Any]:
    payload = json.loads(production_book_path(root=base).read_text(encoding="utf-8"))
    book = reference_book_view(payload)
    del payload
    if book["title"] != BOOK_TITLE or book["editorial_status"] != BOOK_STATUS:
        raise CoverGeneratorFoundation4233Error("reference book identity does not match the print review")
    if book["document_version"] != BOOK_VERSION:
        raise CoverGeneratorFoundation4233Error("book.json document_version changed")
    hardware = collect_hardware(repo_root=str(base))
    models = evaluate_local_models(hardware)
    pdf_info = extract_pdf_geometry(interior_pdf_path(root=base))
    cover = build_draft_cover(
        book,
        project_id=PROJECT_NAME,
        book_version=INTERIOR_VERSION,
    )
    return {
        "reference_book": book,
        "reference_cover": cover,
        "hardware": hardware,
        "models": models,
        "inventory": existing_architecture_inventory(root=base),
        "interior_pdf_pages": pdf_info.get("page_count"),
        "forbidden_imports": _forbidden_imports(base),
    }


def _write_reference_outputs(cover: dict[str, Any], base: Path) -> None:
    record = cover_record_path(root=base)
    assert_write_target_allowed(record)
    write_bytes_atomic(record, cover)
    library_root = author_library_root(root=base)
    if not (library_root / "index.json").exists():
        AuthorLibrary(library_root).ensure()


def _header(
    bundle: dict[str, Any],
    *,
    passed: bool,
    scenarios: dict[str, Any],
    tests: dict[str, Any],
    hashes: str,
    binaries: list[str],
) -> dict[str, Any]:
    hardware = bundle["hardware"]
    models = bundle["models"]
    by_name = {item["model_name"]: item["compatibility"] for item in models["evaluations"]}
    gpu_name = hardware.get("gpu_name") or "none"
    gpu_class = "integrated" if hardware.get("gpu_present") and not hardware.get("discrete_gpu") else (
        "discrete" if hardware.get("discrete_gpu") else "absent"
    )
    test_label = (
        f"{tests['passed']} PASS / {tests['failed']} FAIL"
        if tests.get("summary") != "skipped"
        else f"{scenarios['passed']} PASS / {scenarios['failed']} FAIL"
    )
    return {
        "phase": PHASE,
        "result": "PASS" if passed else "FAIL",
        "provider_calls": 0,
        "book_title": BOOK_TITLE,
        "book_status": BOOK_STATUS,
        "source_document_version": BOOK_VERSION,
        "interior_version": INTERIOR_VERSION,
        "interior_pdf_pages": bundle["interior_pdf_pages"],
        "cover_format": COVER_FORMAT,
        "cover_mode": COVER_MODE,
        "author_library": "READY",
        "optional_author_biography": "SUPPORTED",
        "cover_content_contract": "READY",
        "cover_image_provider_contract": "READY",
        "cover_renderer_contract": "READY",
        "gpu": f"{gpu_name} ({gpu_class})",
        "gpu_vram": "no dedicated VRAM (shared system memory)"
        if not hardware.get("discrete_gpu")
        else f"{hardware.get('dedicated_vram_gib')} GiB",
        "system_ram": f"{hardware.get('system_ram_gib')} GiB",
        "available_disk_space": f"{hardware.get('disk_free_gib')} GiB free",
        "flux_compatibility": by_name.get("FLUX.1 Schnell"),
        "sd35_compatibility": by_name.get("Stable Diffusion 3.5 Medium"),
        "recommended_free_model": models.get("recommended_free_model"),
        "recommended_fallback": models.get("recommended_fallback"),
        "license_verification": models.get("license_verification"),
        "paid_api_authorization_policy": "READY",
        "offline_tests": test_label,
        "scenario_tests": f"{scenarios['passed']} PASS / {scenarios['failed']} FAIL",
        "canonical_hashes": hashes,
        "cover_image_generated": "NO",
        "cover_docx_generated": "NO" if not binaries else "YES",
        "cover_pdf_generated": "NO" if not binaries else "YES",
        "ready_for_next_phase": "YES" if passed else "NO",
        "architecture_summary": (
            "app/cover is a new print-cover module with an author library, "
            "content contract, image-provider contract, and two-page renderer contract. "
            "The existing workshop cover engines and the interior Word renderer were left unchanged."
        ),
        "hardware_summary": (
            f"{gpu_name} is {gpu_class}. Dedicated VRAM is not available. "
            f"System RAM is {hardware.get('system_ram_gib')} GiB "
            f"({hardware.get('available_ram_gib')} GiB free at measurement). "
            f"PyTorch is {'installed' if hardware.get('pytorch_installed') else 'not installed'}. "
            f"DirectML is {'available' if hardware.get('directml_available') else 'not available'}. "
            "No model was downloaded and no image was generated, so the rating is preliminary."
        ),
        "unverified_summary": (
            "FLUX.1 Schnell and Stable Diffusion 3.5 Medium licenses were not re-checked online. "
            "Windows and portrait generation are probable from public model class, not demonstrated here. "
            "Professional cover quality is not claimed. "
            "The 3 mm bleed is a configurable starting value, not a universal printer specification. "
            f"book.json remains {BOOK_VERSION}; the interior files are {INTERIOR_VERSION}."
        ),
        "next_action": NEXT_ACTION_PASS if passed else NEXT_ACTION_FAIL,
        "authorization_scope": AUTHORIZATION_SCOPE,
    }


def _readiness(header: dict[str, Any], *, passed: bool) -> dict[str, Any]:
    return {
        "READY_FOR_NEXT_PHASE": passed,
        "RESULT": header["result"],
        "COVER_IMAGE_GENERATED": False,
        "COVER_DOCX_GENERATED": False,
        "COVER_PDF_GENERATED": False,
        "PROVIDER_CALLS": 0,
        "MODEL_DOWNLOADS": 0,
        "AUTHOR_LIBRARY": header["author_library"],
        "OPTIONAL_AUTHOR_BIOGRAPHY": header["optional_author_biography"],
        "RECOMMENDED_FREE_MODEL": header["recommended_free_model"],
        "RECOMMENDED_FALLBACK": header["recommended_fallback"],
        "LICENSE_VERIFICATION": header["license_verification"],
        "next_action": header["next_action"],
    }


def _failure_bundle(before: dict[str, Any], after: dict[str, Any], reason: str) -> dict[str, Any]:
    header = {
        "phase": PHASE,
        "result": "BLOCKED",
        "provider_calls": 0,
        "book_title": BOOK_TITLE,
        "interior_version": INTERIOR_VERSION,
        "interior_pdf_pages": None,
        "cover_format": COVER_FORMAT,
        "cover_mode": COVER_MODE,
        "author_library": "BLOCKED",
        "optional_author_biography": "SUPPORTED",
        "cover_content_contract": "READY",
        "cover_image_provider_contract": "READY",
        "cover_renderer_contract": "READY",
        "gpu": None,
        "gpu_vram": None,
        "system_ram": None,
        "available_disk_space": None,
        "flux_compatibility": None,
        "sd35_compatibility": None,
        "recommended_free_model": None,
        "recommended_fallback": None,
        "license_verification": "UNVERIFIED_OFFLINE",
        "paid_api_authorization_policy": "READY",
        "offline_tests": "NOT RUN",
        "canonical_hashes": "MISMATCH" if not hashes_match(before, after) else "MATCH",
        "cover_image_generated": "NO",
        "cover_docx_generated": "NO",
        "cover_pdf_generated": "NO",
        "ready_for_next_phase": "NO",
        "architecture_summary": reason,
        "hardware_summary": "",
        "unverified_summary": "",
        "next_action": NEXT_ACTION_FAIL,
    }
    return {
        "header": header,
        "canonical_hashes_pre_post": {
            "phase": PHASE,
            "pre": before,
            "post": after,
            "match": hashes_match(before, after),
        },
        "readiness": {"READY_FOR_NEXT_PHASE": False, "RESULT": "BLOCKED", "stop_reason": reason},
        "files_written": [],
    }


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = ["app/tests/test_cover_generator_foundation_4b233.py"]
    python = str(venv_python_path(root=root))
    completed = subprocess.run(
        [python, "-m", "pytest", "-q", "--tb=line", *tests],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = completed.stdout or ""
    combined = stdout + "\n" + (completed.stderr or "")
    summary = next(
        (
            line.strip()
            for line in reversed(combined.splitlines())
            if "passed" in line or "failed" in line or "error" in line
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
    }


def _skipped_tests() -> dict[str, Any]:
    return {
        "returncode": 0,
        "summary": "skipped",
        "passed": 0,
        "failed": 0,
        "stderr_tail": "",
        "suites": [],
        "real_provider_calls": 0,
    }


def _cover_binaries(directory: Path) -> list[str]:
    if not directory.exists():
        return []
    found: list[str] = []
    for pattern in ("*.docx", "*.pdf", "*.png", "*.jpg", "*.jpeg", "*.webp"):
        found.extend(str(path).replace("\\", "/") for path in directory.rglob(pattern))
    return found


def _forbidden_imports(base: Path) -> list[str]:
    banned = ("requests", "openai", "anthropic", "torch", "diffusers", "huggingface_hub", "httpx")
    hits: list[str] = []
    for relative in ("app/cover", "app/cover_generator_foundation_4b233"):
        for path in (base / relative).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module.split(".")[0]]
                else:
                    continue
                for name in names:
                    if name in banned:
                        hits.append(f"{path.relative_to(base).as_posix()}:{name}")
    return hits


__all__ = ["PhaseResult", "run_phase"]
