"""Inventory of the existing cover and publication stack. Nothing here is replaced."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.cover_generator_foundation_4b233.paths import repo_root


def existing_architecture_inventory(*, root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    components = [
        _component(
            base,
            "app/image_engine/image_provider_base.py",
            "Local image provider ABC and a test fake that writes a PNG.",
            "Keep. The new CoverImageProvider adds cost, capabilities, and an authorization gate. This phase does not call it.",
        ),
        _component(
            base,
            "app/image_engine/image_service.py",
            "SDXL/fake cover generation into sortie/<project>/images/.",
            "Keep. Generation and weight download stay outside this phase.",
        ),
        _component(
            base,
            "app/image_engine/sdxl_provider.py",
            "Stable Diffusion XL via diffusers. First use downloads weights.",
            "Keep. Not selected and not invoked.",
        ),
        _component(
            base,
            "app/cover_engine.py",
            "Workshop engines for SD WebUI, DALL-E, and a typographic fallback.",
            "Keep. Paid and local generation paths are not the print-cover contract.",
        ),
        _component(
            base,
            "app/cover_image_engine.py",
            "Optional cover image modes, including a local WebUI.",
            "Keep. It writes project publication state.",
        ),
        _component(
            base,
            "app/cover_generation_service.py",
            "Cover strategy, cache, and project_state updates.",
            "Keep. The new cover record is not project_state and not book.json.",
        ),
        _component(
            base,
            "app/cover_builder.py",
            "Offline typographic cover orchestrator.",
            "Keep. It renders a single cover PDF/PNG and is not the two-page print contract.",
        ),
        _component(
            base,
            "app/cover_renderer.py",
            "ReportLab/Pillow typographic cover renderer.",
            "Keep. The new CoverRenderer is a separate export contract and does not call it.",
        ),
        _component(
            base,
            "app/cover_layout.py",
            "Eight-zone typographic grid.",
            "Keep. Print bleed and safety are calculated in app/cover/renderer/geometry.py.",
        ),
        _component(
            base,
            "app/cover_layout_service.py",
            "Trim pixel table. 6×9 at 300 dpi is 1800×2700, without bleed.",
            "Reference only. Bleed is recalculated independently.",
        ),
        _component(
            base,
            "app/cover_composition.py",
            "Typographic composition balance.",
            "Keep. Not used for the print-review cover.",
        ),
        _component(
            base,
            "app/cover_theme.py",
            "Typographic palettes and textures.",
            "Keep. Back-cover color stays unset until a later visual decision.",
        ),
        _component(
            base,
            "app/word_renderer/cover.py",
            "Interior profile hook. Cover image is optional and a spine is not computed.",
            "Keep. The interior renderer does not gain a cover export.",
        ),
        _component(
            base,
            "app/word_renderer/document.py",
            "Interior 6×9 DOCX builder.",
            "Keep unchanged. Cover files stay independent of the interior DOCX.",
        ),
        _component(
            base,
            "app/publication_docx_engine.py",
            "Workshop DOCX publication with an optional cover page.",
            "Keep. Print covers are not inserted into the interior document.",
        ),
        _component(
            base,
            "app/publication_pdf_engine.py",
            "Workshop PDF publication.",
            "Keep. No second publication engine is introduced.",
        ),
        _component(
            base,
            "app/config.py",
            "COVER_PROVIDER defaults to sdxl_local and can name an OpenAI image provider.",
            "Keep. The new module does not read a paid provider as selected.",
        ),
    ]
    return {
        "inspected": True,
        "existing_services_replaced": False,
        "second_publication_engine_created": False,
        "decision": (
            "Add app/cover as an independent print-cover module. "
            "Leave the workshop image and typographic cover stack in place."
        ),
        "components": components,
        "new_package": "app/cover",
        "components_present": sum(1 for item in components if item["exists"]),
        "components_missing": [item["path"] for item in components if not item["exists"]],
    }


def architecture_decisions_markdown() -> str:
    return """# Cover architecture decisions — 4B.2.33

## Decision

The print cover is a new module, `app/cover`. The workshop cover stack stays in place and is not called.

## Why it is not an extension of the current engines

`app/cover_engine.py`, `app/cover_builder.py`, `app/cover_renderer.py`, and `app/image_engine/` already generate images or typographic covers. Several of those paths can call a local WebUI or a paid image API, write `project_state`, and produce one cover file inside a project's publication folder.

The print cover needs different guarantees:

- two separate pages, with no spine and no wraparound
- an author library shared across books
- a biography snapshot that does not follow later profile edits
- private contact data kept off the back cover
- a paid-call gate with an explicit budget
- no image, DOCX, or PDF during this phase

Folding that into the workshop engines would mix those behaviors with the interior publication path. `app/word_renderer` remains the interior renderer. `app/publication_docx_engine.py` and `app/publication_pdf_engine.py` remain the workshop publishers.

## Module boundaries

- `app/cover/author_library` stores reusable public profiles and a separate private contact file.
- `app/cover/content` defines description and biography states. It does not call a model.
- `app/cover/image_providers` defines the provider interface, the free-model rating, and the paid-call policy.
- `app/cover/renderer` defines geometry and the two-page export contract. Export methods refuse to write files.
- `app/cover/validation` builds a draft record from the book title and subtitle only.

## Storage

Author profiles live under `data/author_library`, outside `sortie/<project>`. A cover record for this book lives under `sortie/pastoral_retreat_v2_validation/publication/covers/draft_v1/`. `book.json` is not the cover store.

## What this phase does not claim

Local model licenses were not re-checked online. Hardware compatibility is a planning judgment. No professional cover quality is demonstrated, because no image was generated.
"""


def _component(base: Path, relative: str, role: str, decision: str) -> dict[str, Any]:
    path = base / relative
    return {
        "path": relative,
        "exists": path.is_file(),
        "role": role,
        "decision": decision,
        "modified_in_this_phase": False,
    }


__all__ = ["architecture_decisions_markdown", "existing_architecture_inventory"]
