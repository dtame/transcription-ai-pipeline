"""Run Phase 4B.2.35 and write the print-review covers."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from app.cover_generator_foundation_4b233.hashes import (
    assert_protected_hashes,
    hashes_match,
    snapshot,
)
from app.cover_print_ready_4b235.constants import (
    AUTHORIZATION_SCOPE,
    BOOK_TITLE,
    EXPECTED_BOOK_SHA256,
    EXPECTED_IMAGE_SHA256,
    PHASE,
)
from app.cover_print_ready_4b235.content import (
    find_approved_descriptions,
    load_book_fields,
    resolve_author,
    resolve_biography,
    resolve_description,
    resolve_subtitle,
)
from app.cover_print_ready_4b235.guard import (
    CoverPrintReady4235Error,
    assert_no_provider_calls,
    forbidden_imports,
    validate_authorization_scope,
)
from app.cover_print_ready_4b235.package import CoverJob, assemble
from app.cover_print_ready_4b235.paths import (
    author_library_root,
    generated_image_path,
    output_dir,
    phase_audit_dir,
    production_book_path,
    report_path,
    repo_root,
    validation_path,
    venv_python_path,
)
from app.cover_print_ready_4b235.report import render_report
from app.cover_print_ready_4b235.validation import validate_package


def run_phase(
    *,
    authorization_scope: str | None,
    root: Path | None = None,
    run_tests: bool = True,
) -> dict[str, Any]:
    validate_authorization_scope(authorization_scope)
    assert_no_provider_calls()
    base = root or repo_root()
    before = snapshot()
    assert_protected_hashes(before)
    book = load_book_fields(production_book_path(root=base))
    if book["title"] != BOOK_TITLE:
        raise CoverPrintReady4235Error("book title does not match the print-review canonical title. STOP.")
    library_path = author_library_root(root=base) / "index.json"
    library = json.loads(library_path.read_text(encoding="utf-8")) if library_path.is_file() else {}
    subtitle = resolve_subtitle(book)
    author = resolve_author(book, library)
    biography = resolve_biography(library, author.get("author_id"))
    description = resolve_description(
        find_approved_descriptions(base),
        allow_proposal=True,
    )
    job = CoverJob(
        title=book["title"],
        subtitle=subtitle["text"],
        subtitle_status=subtitle["status"],
        author_name=author["name"],
        author_status=author["status"],
        description=description["text"],
        description_status=description["status"],
        description_canonical=bool(description["canonical"]),
        biography=biography["text"],
        biography_status=biography["status"],
        source_image=generated_image_path(root=base),
        expected_sha256=EXPECTED_IMAGE_SHA256,
        book_sha256=EXPECTED_BOOK_SHA256,
        project_id=book["project_id"] or "pastoral_retreat_v2_validation",
    )
    destination = output_dir(root=base)
    built = assemble(job, destination)
    after = snapshot()
    if not hashes_match(before, after):
        raise CoverPrintReady4235Error(
            "book.json or the interior changed while the covers were written. STOP."
        )
    imports = forbidden_imports(Path(__file__).resolve().parent)
    validation = validate_package(
        destination,
        built["record"],
        front_layout=built["front_layout"],
        back_layout=built["back_layout"],
        geometry=built["geometry"],
        canonical_match=True,
        source_unchanged=True,
        imports_ok=not imports,
    )
    phase_audit_dir(root=base).mkdir(parents=True, exist_ok=True)
    validation_path(root=base).write_text(
        json.dumps(validation, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    tests = _run_tests(base) if run_tests else {"passed": 0, "failed": 0, "summary": "not run"}
    record = built["record"]
    ready = validation["ok"] and tests["failed"] == 0
    if not validation["ok"] or tests["failed"]:
        result = "FAIL"
    elif record["book_description_status"] == "PROPOSED_NOT_EDITORIALLY_APPROVED":
        result = "PASS_WITH_EDITORIAL_REVIEW"
    else:
        result = "PASS"
    header = {
        "result": result,
        "art_image": record["human_approval_status"],
        "ai_generation_calls": 0,
        "original_image": record["front_image_source"],
        "original_image_sha256": record["original_image_sha256"],
        "prepared_image": record["prepared_image"],
        "prepared_resolution": " × ".join(str(item) for item in record["prepared_resolution_px"]),
        "front_title": " / ".join(record["front_title_lines"]),
        "subtitle": record["subtitle"] or "ABSENT",
        "author": record["author"] or record["author_status"],
        "background_color": (
            f"{record['background_color']['hex']} RGB {record['background_color']['rgb']}"
        ),
        "book_description": record["book_description_status"],
        "author_biography": record["author_biography_status"],
        "front_docx": record["front_docx"],
        "front_pdf": record["front_pdf"],
        "back_docx": record["back_docx"],
        "back_pdf": record["back_pdf"],
        "canonical_hashes": "MATCH",
        "tests_passed": tests["passed"],
        "tests_failed": tests["failed"],
        "ready_for_print_review": "YES" if ready else "NO",
        "remaining_human_review": _remaining(record),
        "composition": _composition(record),
    }
    report = render_report(header)
    report_path(root=base).write_text(report, encoding="utf-8")
    return {
        "phase": PHASE,
        "result": result,
        "provider_calls": 0,
        "validation": validation,
        "tests": tests,
        "header": header,
        "authorization_scope": AUTHORIZATION_SCOPE,
    }


def _remaining(record: dict[str, Any]) -> str:
    parts = ["visual inspection of the four cover files"]
    if record["book_description_status"] != "APPROVED":
        parts.append("back-cover description is proposed and not editorially approved")
    if record["author_status"] == "MISSING_OPTIONAL":
        parts.append("author name is optional and absent")
    if record["author_biography_status"] == "MISSING_OPTIONAL":
        parts.append("author biography is optional and absent")
    return "; ".join(parts)


def _composition(record: dict[str, Any]) -> str:
    crop = record["image_preparation"]["crop_px"]
    color = record["background_color"]
    return (
        f"The front uses the approved image, enlarged with Lanczos and placed with a cover fit. "
        f"Crop in pixels: left {crop['left']}, top {crop['top']}, right {crop['right']}, "
        f"bottom {crop['bottom']}. The document is {record['document_size_in']['width']} × "
        f"{record['document_size_in']['height']} in, including 3 mm bleed around a 6 × 9 in trim. "
        f"Text sits inside the 0.25 in safe area. The back field is {color['hex']} "
        f"({color['method']}). No spine and no wraparound were made."
    )


def _run_tests(root: Path) -> dict[str, Any]:
    python = str(venv_python_path(root=root))
    completed = subprocess.run(
        [python, "-m", "pytest", "-q", "--tb=line", "app/tests/test_cover_print_ready_4b235.py"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    combined = (completed.stdout or "") + "\n" + (completed.stderr or "")
    summary = next(
        (
            line.strip()
            for line in reversed(combined.splitlines())
            if "passed" in line or "failed" in line or "error" in line
        ),
        "",
    )
    passed = int(re.search(r"(\d+) passed", summary).group(1)) if re.search(r"(\d+) passed", summary) else 0
    failed_match = re.search(r"(\d+) failed", summary)
    failed = int(failed_match.group(1)) if failed_match else (0 if completed.returncode == 0 else 1)
    return {"passed": passed, "failed": failed, "summary": summary, "returncode": completed.returncode}


__all__ = ["run_phase"]
