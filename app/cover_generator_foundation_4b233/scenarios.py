"""Offline checks for the cover foundation. No network and no binaries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.cover.author_library.attribution import book_author_ids, register_depositor
from app.cover.author_library.privacy import back_cover_author_fields, public_payload_contains_private
from app.cover.author_library.snapshot import freeze_biography
from app.cover.author_library.store import AuthorLibrary
from app.cover.content.contract import (
    approve,
    back_layout_blocks,
    initial_content,
    store_biography_draft,
    store_description_draft,
)
from app.cover.image_providers.base import (
    CoverImageProvider,
    ImageGenerationRequest,
    ProviderCapabilities,
    validate_image_request,
)
from app.cover.image_providers.compatibility import evaluate_local_models, rate_model
from app.cover.image_providers.compatibility import model_catalog
from app.cover.image_providers.policy import (
    empty_paid_authorization,
    evaluate_paid_call,
    paid_retry_allowed,
)
from app.cover.models.author import AuthorFact, PrivateContact
from app.cover.renderer.contract import CoverRenderer
from app.cover.renderer.geometry import cover_geometry
from app.cover.validation.checks import build_draft_cover
from app.cover_generator_foundation_4b233.constants import (
    BOOK_TITLE,
    EXPECTED_BOOK_SHA256,
    EXPECTED_INTERIOR_DOCX_SHA256,
    EXPECTED_INTERIOR_PDF_SHA256,
    INTERIOR_VERSION,
)


def evaluate_cases(*, library_root: Path, book: dict[str, Any]) -> dict[str, Any]:
    results = []
    for name, function in CASES:
        try:
            detail = function(library_root=library_root, book=book)
            results.append({"name": name, "passed": True, "detail": detail})
        except Exception as exc:
            results.append({"name": name, "passed": False, "detail": str(exc)})
    passed = sum(1 for item in results if item["passed"])
    return {
        "passed": passed,
        "failed": len(results) - passed,
        "cases": results,
        "provider_calls": 0,
        "downloads": 0,
        "network_calls": 0,
    }


def _library(library_root: Path, name: str) -> AuthorLibrary:
    return AuthorLibrary(library_root / name)


def _author_profile_created(*, library_root: Path, book: dict[str, Any]) -> str:
    del book
    library = _library(library_root, "create")
    profile = library.create_author(display_name=None)
    if profile.author_id != "author_000001":
        raise AssertionError(profile.author_id)
    if profile.verification_status != "UNVERIFIED":
        raise AssertionError(profile.verification_status)
    return profile.author_id


def _profile_without_biography(*, library_root: Path, book: dict[str, Any]) -> str:
    del book
    library = _library(library_root, "no-bio")
    profile = library.create_author()
    state = initial_content(profile)
    if state["author_biography"] is not None or state["author_biography_status"] != "MISSING_OPTIONAL":
        raise AssertionError(state["author_biography_status"])
    return state["author_biography_status"]


def _incomplete_profile(*, library_root: Path, book: dict[str, Any]) -> str:
    del book
    library = _library(library_root, "incomplete")
    profile = library.create_author(display_name="Example Author")
    library.add_fact(
        profile.author_id,
        kind="areas_of_expertise",
        text="Supplied expertise that is not approved for print.",
        verification_status="PROVIDED",
        publication_status="NOT_APPROVED",
    )
    library.add_fact(
        profile.author_id,
        kind="public_role",
        text="Approved public role for this fixture.",
        verification_status="VERIFIED",
        publication_status="APPROVED_FOR_PUBLICATION",
    )
    loaded = library.get(profile.author_id)
    approved = loaded.approved_facts()
    if len(approved) != 1:
        raise AssertionError(len(approved))
    state = initial_content(loaded)
    if state["author_biography"] is not None:
        raise AssertionError("incomplete profile produced biography prose")
    if approved[0].fact_id not in state["source_fact_ids"]:
        raise AssertionError("approved fact was dropped")
    _reject_unverified_publication()
    return "approved_facts_only"


def _author_reused(*, library_root: Path, book: dict[str, Any]) -> str:
    del book
    library = _library(library_root, "reuse")
    profile = library.create_author(display_name="Shared Author")
    library.link_project(project_id="book_a", author_id=profile.author_id, role="BOOK_AUTHOR")
    library.link_project(project_id="book_b", author_id=profile.author_id, role="BOOK_AUTHOR")
    projects = library.projects_for_author(profile.author_id)
    if projects != ["book_a", "book_b"]:
        raise AssertionError(projects)
    if library.public_index()["authors"][profile.author_id]["display_name"] != "Shared Author":
        raise AssertionError("profile was copied per book")
    return ",".join(projects)


def _private_separated(*, library_root: Path, book: dict[str, Any]) -> str:
    del book
    library = _library(library_root, "private")
    profile = library.create_author(display_name="Public Name")
    profile.name_publication_authorized = True
    library.update_profile(profile)
    library.set_private_contact(
        profile.author_id,
        PrivateContact(email="person@example.test", phone="555-0100", management_contact="desk"),
    )
    public = library.public_index()
    if public_payload_contains_private(public):
        raise AssertionError("private keys reached the public index")
    block = back_cover_author_fields(library.get(profile.author_id), library.private_contact(profile.author_id))
    if block["display_name"] != "Public Name" or block["private_contact_injected"] is not False:
        raise AssertionError(block)
    if "person@example.test" in str(block):
        raise AssertionError("email reached the back cover")
    return "separated"


def _depositor_not_author(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root, book
    depositor = register_depositor(project_id="book_a", person_ref="depositor_fixture")
    authors = book_author_ids([depositor], "book_a")
    if depositor["implies_book_author"] or depositor["author_id"] is not None or authors:
        raise AssertionError(depositor)
    return "not_implied"


def _biography_snapshot(*, library_root: Path, book: dict[str, Any]) -> str:
    del book
    library = _library(library_root, "snap")
    profile = library.create_author(display_name="Snapshot Author")
    snapshot = freeze_biography(profile, text="Approved biography for this edition.", status="APPROVED")
    if snapshot["text"] != "Approved biography for this edition.":
        raise AssertionError(snapshot["text"])
    return snapshot["status"]


def _cover_survives_edit(*, library_root: Path, book: dict[str, Any]) -> str:
    library = _library(library_root, "survive")
    profile = library.create_author(display_name="Edition Author")
    profile.name_publication_authorized = True
    library.update_profile(profile)
    snapshot = freeze_biography(library.get(profile.author_id), text="Edition biography.", status="APPROVED")
    cover = build_draft_cover(
        book,
        project_id="book_a",
        book_version=INTERIOR_VERSION,
        profile=library.get(profile.author_id),
        biography_snapshot=snapshot,
    )
    profile.display_name = "Changed Later"
    profile.biography_reference = "new-central-bio"
    library.update_profile(profile)
    if cover["biography_snapshot"]["text"] != "Edition biography.":
        raise AssertionError("snapshot followed the central profile")
    if cover["biography_snapshot"]["display_name"] != "Edition Author":
        raise AssertionError("snapshot display name changed")
    return "preserved"


def _description_draft(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root, book
    state = store_description_draft(initial_content(), "A supplied draft, not a generated blurb.")
    if state["book_description_status"] != "DRAFT" or state["auto_approved"]:
        raise AssertionError(state["book_description_status"])
    try:
        approve(state, "book_description", reviewer="editor")
    except Exception:
        return "draft_not_approved"
    raise AssertionError("draft was approved without review")


def _biography_optional(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root, book
    state = initial_content(None)
    blocks = back_layout_blocks(state)
    if state["author_biography_status"] != "MISSING_OPTIONAL" or "author_biography" in blocks:
        raise AssertionError(blocks)
    return "optional"


def _no_invented_biography(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root, book
    state = initial_content(None)
    if state["author_biography"] is not None or state["invented_biography"]:
        raise AssertionError("biography was invented")
    drafted = store_biography_draft(state, "Human supplied this biography.")
    if drafted["author_biography_status"] != "DRAFT":
        raise AssertionError(drafted["author_biography_status"])
    return "not_invented"


def _canonical_title(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root
    cover = build_draft_cover(book, project_id=book["project"]["name"], book_version=INTERIOR_VERSION)
    if cover["front"]["title"] != book["title"] or cover["front"]["title"] != BOOK_TITLE:
        raise AssertionError(cover["front"]["title"])
    return cover["front"]["title"]


def _canonical_subtitle(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root
    cover = build_draft_cover(book, project_id=book["project"]["name"], book_version=INTERIOR_VERSION)
    if cover["front"]["subtitle"] != book["subtitle"]:
        raise AssertionError(cover["front"]["subtitle"])
    return cover["front"]["subtitle"]


def _two_faces(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root
    cover = build_draft_cover(book, project_id="pastoral_retreat_v2_validation", book_version=INTERIOR_VERSION)
    plan = CoverRenderer().compose(cover)
    if plan["faces"] != ["front", "back"] or plan["spine_computed"] or plan["wraparound"]:
        raise AssertionError(plan["cover_mode"])
    required = {"front_docx", "front_pdf", "back_docx", "back_pdf"}
    if not required.issubset(cover["export"]):
        raise AssertionError(sorted(cover["export"]))
    return plan["cover_mode"]


def _format_6x9(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root, book
    geometry = cover_geometry()
    if (geometry.trim_width_px, geometry.trim_height_px) != (1800, 2700):
        raise AssertionError((geometry.trim_width_px, geometry.trim_height_px))
    if (geometry.full_width_px, geometry.full_height_px) != (1871, 2771):
        raise AssertionError((geometry.full_width_px, geometry.full_height_px))
    return "6x9"


def _configurable_bleed(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root, book
    bare = cover_geometry(bleed_mm=0)
    wide = cover_geometry(bleed_mm=5)
    if bare.full_width_px != bare.trim_width_px or wide.full_width_px <= bare.full_width_px:
        raise AssertionError((bare.full_width_px, wide.full_width_px))
    return str(wide.bleed_mm)


def _safety_zone(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root, book
    geometry = cover_geometry(safety_in=0.25)
    if geometry.safety_width_px != 1650 or geometry.safety_height_px != 2550:
        raise AssertionError((geometry.safety_width_px, geometry.safety_height_px))
    return "inside_trim"


def _draft_image_optional(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root
    cover = build_draft_cover(book, project_id="pastoral_retreat_v2_validation", book_version=INTERIOR_VERSION)
    if cover["status"] != "DRAFT" or cover["front"]["background_image_path"] is not None:
        raise AssertionError("draft required an image")
    return "optional"


def _solid_back(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root
    cover = build_draft_cover(
        book,
        project_id="pastoral_retreat_v2_validation",
        book_version=INTERIOR_VERSION,
        background_color=None,
    )
    if cover["back"]["background_mode"] != "SOLID_COLOR":
        raise AssertionError(cover["back"]["background_mode"])
    if cover["back"]["barcode"] or cover["back"]["isbn"] or cover["back"]["testimonials"]:
        raise AssertionError("back cover gained a forbidden element")
    return "solid"


def _provider_interface(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root, book

    class _SilentProvider(CoverImageProvider):
        provider_id = "silent_test"

        def check_availability(self) -> dict[str, Any]:
            return {"available": False, "reason": "foundation"}

        def get_capabilities(self) -> ProviderCapabilities:
            return ProviderCapabilities(
                provider_id=self.provider_id,
                model_name="none",
                model_version=None,
                negative_prompt=True,
                seed=True,
                portrait_ratio=True,
                text_free_generation=True,
                local_execution=True,
                paid=False,
            )

        def estimate_cost(self, request: ImageGenerationRequest) -> dict[str, Any]:
            return {"estimated_cost_usd": None, "image_count": request.image_count}

    provider = _SilentProvider()
    request = ImageGenerationRequest(
        provider_id="silent_test",
        model_name="none",
        model_version=None,
        prompt="portrait landscape without lettering",
        negative_prompt="text, letters",
        width_px=1871,
        height_px=2771,
        aspect_ratio="2:3",
        seed=1,
        image_count=1,
        output_paths=[],
    )
    validate_image_request(request)
    if provider.check_availability()["available"] or provider.estimate_cost(request)["estimated_cost_usd"] is not None:
        raise AssertionError("test provider pretended to be ready")
    try:
        provider.generate(request)
    except Exception as exc:
        if "not authorized" not in str(exc):
            raise
        return "interface_refused_generation"
    raise AssertionError("generate wrote or returned an image")


def _paid_request() -> dict[str, Any]:
    return {"provider_id": "example_paid", "model_name": "example_model", "image_count": 1}


def _unknown_cost(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root, book
    authorization = empty_paid_authorization()
    authorization.update(
        {
            "explicit": True,
            "provider_id": "example_paid",
            "model_name": "example_model",
            "max_images": 1,
            "max_budget_usd": 1,
            "network_calls_allowed": True,
        }
    )
    decision = evaluate_paid_call(
        authorization=authorization,
        request=_paid_request(),
        estimate_usd=None,
        foundation_lock=False,
    )
    if decision["allowed"] or "estimated_cost_unknown" not in decision["reasons"]:
        raise AssertionError(decision["reasons"])
    return "blocked"


def _missing_authorization(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root, book
    authorization = empty_paid_authorization()
    authorization["prior_phase_unspent_budget_usd"] = 25
    decision = evaluate_paid_call(
        authorization=authorization,
        request=_paid_request(),
        estimate_usd=0.04,
        foundation_lock=False,
    )
    if decision["allowed"] or "explicit_authorization_missing" not in decision["reasons"]:
        raise AssertionError(decision["reasons"])
    if "prior_phase_unspent_budget_is_not_authorization" not in decision["reasons"]:
        raise AssertionError(decision["reasons"])
    if paid_retry_allowed():
        raise AssertionError("paid retry is enabled")
    return "blocked"


def _hardware_shape(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root, book
    from app.cover.hardware.diagnostic import collect_hardware

    live = collect_hardware()
    if live["downloads"] != 0 or live["network_calls"] != 0 or live["packages_installed"]:
        raise AssertionError("diagnostic downloaded, installed, or called a network service")
    if not live["operating_system"] or not live["python_version"] or live["system_ram_gib"] is None:
        raise AssertionError("diagnostic did not read the local host")
    if live["benchmark_executed"]:
        raise AssertionError("diagnostic ran a benchmark")
    return str(live["gpu_name"] or "no_gpu")


def _gpu_absent(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root, book
    hardware = {
        "system_ram_gib": 16,
        "discrete_gpu": False,
        "dedicated_vram_gib": None,
        "gpu_present": False,
    }
    ratings = {spec["model_name"]: rate_model(spec, hardware) for spec in model_catalog()}
    if any(rating == "LIKELY_COMPATIBLE" for rating in ratings.values()):
        raise AssertionError(ratings)
    if ratings["FLUX.1 Schnell"] != "NOT_RECOMMENDED":
        raise AssertionError(ratings)
    return ratings["FLUX.1 Schnell"]


def _vram_insufficient(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root, book
    hardware = {
        "system_ram_gib": 32,
        "discrete_gpu": True,
        "dedicated_vram_gib": 4,
        "gpu_present": True,
    }
    ratings = [rate_model(spec, hardware) for spec in model_catalog()]
    if ratings != ["NOT_RECOMMENDED", "NOT_RECOMMENDED"]:
        raise AssertionError(ratings)
    return "not_recommended"


def _hardware_incomplete(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root, book
    hardware = {"system_ram_gib": None, "discrete_gpu": None, "dedicated_vram_gib": None}
    ratings = {spec["model_name"]: rate_model(spec, hardware) for spec in model_catalog()}
    if set(ratings.values()) != {"INSUFFICIENT_INFORMATION"}:
        raise AssertionError(ratings)
    return "insufficient"


def _no_download(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root, book
    report = evaluate_local_models(
        {"system_ram_gib": 15.65, "discrete_gpu": False, "dedicated_vram_gib": None}
    )
    if report["weights_downloaded"] or report["generation_executed"]:
        raise AssertionError("download flag set")
    return "no_download"


def _no_network(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root, book
    decision = evaluate_paid_call(
        authorization=empty_paid_authorization(),
        request=_paid_request(),
        estimate_usd=1,
    )
    if decision["allowed"] or "network_calls_not_authorized" not in decision["reasons"]:
        raise AssertionError(decision["reasons"])
    return "no_network"


def _no_cover_docx(*, library_root: Path, book: dict[str, Any]) -> str:
    cover = build_draft_cover(book, project_id="pastoral_retreat_v2_validation", book_version=INTERIOR_VERSION)
    destination = library_root / "front_cover.docx"
    try:
        CoverRenderer().render_front_docx(cover, destination)
    except Exception:
        if destination.exists():
            raise AssertionError("docx was written")
        return "not_written"
    raise AssertionError("docx export returned")


def _no_cover_pdf(*, library_root: Path, book: dict[str, Any]) -> str:
    cover = build_draft_cover(book, project_id="pastoral_retreat_v2_validation", book_version=INTERIOR_VERSION)
    destination = library_root / "front_cover.pdf"
    try:
        CoverRenderer().render_front_pdf(cover, destination)
    except Exception:
        if destination.exists():
            raise AssertionError("pdf was written")
        return "not_written"
    raise AssertionError("pdf export returned")


def _canonical_unchanged(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root
    from app.cover_generator_foundation_4b233.hashes import file_sha256
    from app.cover_generator_foundation_4b233.paths import production_book_path

    before = file_sha256(production_book_path())
    build_draft_cover(book, project_id="pastoral_retreat_v2_validation", book_version=INTERIOR_VERSION)
    after = file_sha256(production_book_path())
    if before.get("sha256") != EXPECTED_BOOK_SHA256 or before != after:
        raise AssertionError(after.get("sha256"))
    return "match"


def _interior_unchanged(*, library_root: Path, book: dict[str, Any]) -> str:
    del library_root, book
    from app.cover_generator_foundation_4b233.hashes import file_sha256
    from app.cover_generator_foundation_4b233.paths import interior_docx_path, interior_pdf_path

    docx = file_sha256(interior_docx_path())
    pdf = file_sha256(interior_pdf_path())
    if docx.get("sha256") != EXPECTED_INTERIOR_DOCX_SHA256:
        raise AssertionError(docx.get("sha256"))
    if pdf.get("sha256") != EXPECTED_INTERIOR_PDF_SHA256:
        raise AssertionError(pdf.get("sha256"))
    return "match"


def _reject_unverified_publication() -> None:
    try:
        AuthorFact(
            fact_id="bad",
            kind="public_role",
            text="Unverified claim",
            verification_status="UNVERIFIED",
            publication_status="APPROVED_FOR_PUBLICATION",
        )
    except ValueError:
        return
    raise AssertionError("unverified fact was approved")


def reference_book_view(payload: dict[str, Any]) -> dict[str, Any]:
    project = payload.get("project") if isinstance(payload.get("project"), dict) else {}
    absent = payload.get("absent_editorial_fields")
    author = None
    if isinstance(absent, dict):
        author = absent.get("author")
    return {
        "title": payload.get("title"),
        "subtitle": payload.get("subtitle"),
        "document_version": payload.get("document_version"),
        "editorial_status": payload.get("editorial_status"),
        "language": payload.get("language"),
        "project": {"name": project.get("name")},
        "absent_editorial_fields": {"author": author},
        "title_status": payload.get("title_status"),
    }


CASES = (
    ("author_profile_created", _author_profile_created),
    ("profile_without_biography", _profile_without_biography),
    ("incomplete_profile", _incomplete_profile),
    ("author_reused_across_books", _author_reused),
    ("private_data_separated", _private_separated),
    ("depositor_is_not_author", _depositor_not_author),
    ("approved_biography_snapshot", _biography_snapshot),
    ("cover_survives_profile_edit", _cover_survives_edit),
    ("description_stays_draft", _description_draft),
    ("biography_optional", _biography_optional),
    ("no_invented_biography", _no_invented_biography),
    ("canonical_title", _canonical_title),
    ("canonical_subtitle", _canonical_subtitle),
    ("two_independent_faces", _two_faces),
    ("format_6x9", _format_6x9),
    ("configurable_bleed", _configurable_bleed),
    ("safety_zone", _safety_zone),
    ("draft_image_optional", _draft_image_optional),
    ("solid_back_cover", _solid_back),
    ("image_provider_interface", _provider_interface),
    ("unknown_cost_blocks_paid_call", _unknown_cost),
    ("missing_authorization_blocks_paid_call", _missing_authorization),
    ("hardware_diagnostic_shape", _hardware_shape),
    ("gpu_absent", _gpu_absent),
    ("vram_insufficient", _vram_insufficient),
    ("hardware_incomplete", _hardware_incomplete),
    ("no_download", _no_download),
    ("no_network", _no_network),
    ("no_cover_docx", _no_cover_docx),
    ("no_cover_pdf", _no_cover_pdf),
    ("canonical_book_unchanged", _canonical_unchanged),
    ("interior_unchanged", _interior_unchanged),
)

CASE_NAMES = tuple(name for name, _function in CASES)

__all__ = ["CASE_NAMES", "evaluate_cases", "reference_book_view"]
