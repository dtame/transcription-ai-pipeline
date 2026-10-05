"""Phase 4B.2.33 report."""

from __future__ import annotations

from typing import Any, Mapping


def render_report(bundle: Mapping[str, Any]) -> str:
    header = bundle.get("header") or {}
    lines = [
        f"**PHASE {header.get('phase')} — COVER GENERATOR FOUNDATION**",
        "",
        f"RESULT = {header.get('result')}",
        f"PROVIDER CALLS = {header.get('provider_calls')}",
        f"BOOK TITLE = {header.get('book_title')}",
        f"INTERIOR VERSION = {header.get('interior_version')}",
        f"INTERIOR PDF PAGES = {header.get('interior_pdf_pages')}",
        f"COVER FORMAT = {header.get('cover_format')}",
        f"COVER MODE = {header.get('cover_mode')}",
        f"AUTHOR LIBRARY = {header.get('author_library')}",
        f"OPTIONAL AUTHOR BIOGRAPHY = {header.get('optional_author_biography')}",
        f"COVER CONTENT CONTRACT = {header.get('cover_content_contract')}",
        f"COVER IMAGE PROVIDER CONTRACT = {header.get('cover_image_provider_contract')}",
        f"COVER RENDERER CONTRACT = {header.get('cover_renderer_contract')}",
        f"GPU = {header.get('gpu')}",
        f"GPU VRAM = {header.get('gpu_vram')}",
        f"SYSTEM RAM = {header.get('system_ram')}",
        f"AVAILABLE DISK SPACE = {header.get('available_disk_space')}",
        f"FLUX.1 SCHNELL COMPATIBILITY = {header.get('flux_compatibility')}",
        f"SD 3.5 MEDIUM COMPATIBILITY = {header.get('sd35_compatibility')}",
        f"RECOMMENDED FREE MODEL = {header.get('recommended_free_model')}",
        f"RECOMMENDED FALLBACK = {header.get('recommended_fallback')}",
        f"LICENSE VERIFICATION = {header.get('license_verification')}",
        f"PAID API AUTHORIZATION POLICY = {header.get('paid_api_authorization_policy')}",
        f"OFFLINE TESTS = {header.get('offline_tests')}",
        f"CANONICAL HASHES PRE/POST = {header.get('canonical_hashes')}",
        f"COVER IMAGE GENERATED = {header.get('cover_image_generated')}",
        f"COVER DOCX GENERATED = {header.get('cover_docx_generated')}",
        f"COVER PDF GENERATED = {header.get('cover_pdf_generated')}",
        f"READY_FOR_NEXT_PHASE = {header.get('ready_for_next_phase')}",
        "",
        "## Architecture",
        "",
        str(header.get("architecture_summary") or ""),
        "",
        "## Hardware",
        "",
        str(header.get("hardware_summary") or ""),
        "",
        "## Unverified",
        "",
        str(header.get("unverified_summary") or ""),
        "",
        "## Files",
        "",
    ]
    for item in bundle.get("files_written") or []:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Next action",
            "",
            str(header.get("next_action") or ""),
            "",
        ]
    )
    return "\n".join(lines)


__all__ = ["render_report"]
