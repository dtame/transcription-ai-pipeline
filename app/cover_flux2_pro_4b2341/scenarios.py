"""Offline cases for the FLUX.2 [pro] unblock. No socket is opened."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from app.cover.art.directions import build_front_cover_directions
from app.cover.image_providers.base import ImageGenerationRequest
from app.cover.image_providers.bfl_budget import default_authorization
from app.cover.image_providers.bfl_pricing import (
    UnverifiedFluxPricing,
    billed_megapixels,
    cost_estimation_examples,
    decimal_megapixels,
    maximum_cost_usd,
)
from app.cover.image_providers.bfl_spec import (
    MAX_PIXELS,
    REJECTED_PRIOR_GENERATION_SIZE,
    SpecError,
    dimension_problems,
    largest_portrait_generation_size,
    selected_generation_record,
    submission_body,
)
from app.cover.image_providers.bfl_transport import LIVE_HTTP_ENABLED, SealedTransport
from app.cover.image_providers.black_forest_labs import BlackForestLabsImageProvider
from app.cover.image_providers.policy import PaidCallRefused
from app.cover.renderer.contract import CoverRenderNotAuthorized, CoverRenderer
from app.cover_flux2_pro_4b234 import scenarios as prior
from app.cover_flux2_pro_4b234.constants import (
    EXPECTED_BOOK_SHA256,
    EXPECTED_INTERIOR_DOCX_SHA256,
    EXPECTED_INTERIOR_PDF_SHA256,
)
from app.cover_flux2_pro_4b2341.constants import ART_DIRECTION, DECISION
from app.cover_generator_foundation_4b233.hashes import snapshot
from app.cover_generator_foundation_4b233.paths import production_book_path


def evaluate_cases() -> dict[str, Any]:
    cases = []
    for name, function in CASES:
        try:
            detail = function() or "ok"
            cases.append({"name": name, "passed": True, "detail": detail})
        except Exception as exc:
            cases.append(
                {
                    "name": name,
                    "passed": False,
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            )
    failed = [case["name"] for case in cases if not case["passed"]]
    return {
        "passed": len(cases) - len(failed),
        "failed": len(failed),
        "failed_names": failed,
        "live_provider_calls": 0,
        "paid_cost_usd": 0,
        "cases": cases,
        "cost_examples": cost_estimation_examples(),
    }


def case_valid_resolution() -> str:
    width, height = largest_portrait_generation_size()
    record = selected_generation_record()
    assert (width, height) == (1632, 2448)
    assert record["pixels"] == 3_995_136
    assert record["pixels"] <= MAX_PIXELS
    assert record["exact_two_to_three"] is True
    assert dimension_problems(width, height) == []
    body = submission_body(_request(width, height))
    assert body["width"] == 1632 and body["height"] == 2448
    assert body["output_format"] == "png"
    assert "negative_prompt" not in body
    return "1632x2448 accepted"


def case_invalid_resolution() -> str:
    problems = dimension_problems(32, 48)
    assert "below_minimum_edge" in problems
    prior._must(SpecError, lambda: submission_body(_request(32, 48)))
    return "below_minimum_edge"


def case_pixel_cap() -> str:
    prior_w, prior_h = REJECTED_PRIOR_GENERATION_SIZE
    assert prior_w * prior_h == 4_153_344
    assert prior_w * prior_h > MAX_PIXELS
    problems = dimension_problems(prior_w, prior_h)
    assert problems == ["above_4_000_000_pixel_cap"]
    prior._must(SpecError, lambda: submission_body(_request(prior_w, prior_h)))
    square = dimension_problems(2048, 2048)
    assert "above_4_000_000_pixel_cap" in square
    return "1664x2496 and 2048x2048 refused"


def case_not_multiple() -> str:
    problems = dimension_problems(1630, 2448)
    assert "not_multiple_of_16" in problems
    prior._must(SpecError, lambda: submission_body(_request(1630, 2448)))
    return "not_multiple_of_16"


def case_portrait_ratio() -> str:
    assert "not_portrait" in dimension_problems(2448, 1632)
    assert "not_portrait" not in dimension_problems(1632, 2448)
    assert largest_portrait_generation_size()[1] > largest_portrait_generation_size()[0]
    return "portrait required"


def case_megapixels() -> str:
    width, height = largest_portrait_generation_size()
    assert decimal_megapixels(width, height) == decimal_megapixels(1632, 2448)
    assert format(decimal_megapixels(1632, 2448), "f") == "3.995136"
    assert format(decimal_megapixels(1920, 1080), "f") == "2.0736"
    return "3.995136 decimal MP"


def case_cost_calculation() -> str:
    official = maximum_cost_usd(1632, 2448)
    assert official["known"] is False
    assert official["max_cost_usd"] is None
    assert official["blocks_paid_call"] is True
    worked = maximum_cost_usd(
        1632,
        2448,
        {"status": "VERIFIED_MAXIMUM", "first_megapixel_usd": "0.030", "additional_megapixel_usd": "0.015"},
    )
    assert worked["billed_megapixels_ceiling"] == 4
    assert worked["max_cost_usd"] == "0.075"
    assert cost_estimation_examples()["floor_times_billed_megapixels_not_used"]["used_as_maximum"] is False
    return "official maximum unknown; fixture schedule 0.075"


def case_billing_rounding() -> str:
    assert billed_megapixels(1920, 1080) == 3
    assert int(decimal_megapixels(1920, 1080)) == 2
    assert billed_megapixels(1632, 2448) == 4
    assert billed_megapixels(1024, 1024) == 2
    return "1920x1080 charges 3 MP; truncation to 2 is rejected"


def case_unknown_maximum() -> str:
    with TemporaryDirectory() as tmp:
        transport = prior._script([])
        provider = prior._open(
            tmp,
            transport,
            pricing=UnverifiedFluxPricing(),
            auth=prior._auth(max_budget_usd=1000, max_total_cost_usd=1000),
        )
        refused = prior._must(PaidCallRefused, lambda: provider.generate(prior._request()))
        assert "estimated_cost_unknown" in refused.reasons
        assert transport.calls == []
    return "user cap does not replace an unknown provider maximum"


def case_unverified_pricing() -> str:
    schedule = maximum_cost_usd(1632, 2448)
    assert schedule["schedule_status"] == "UNVERIFIED_MAXIMUM"
    assert schedule["reason"] == "published_floor_is_not_a_maximum"
    assert DECISION == "BLOCKED_PRICING"
    return "BLOCKED_PRICING"


def case_authorization_absent() -> str:
    with TemporaryDirectory() as tmp:
        transport = prior._script([])
        provider = prior._open(tmp, transport, authorization_missing=True)
        refused = prior._must(PaidCallRefused, lambda: provider.generate(prior._request()))
        assert "explicit_authorization_missing" in refused.reasons
        assert transport.calls == []
    return "explicit_authorization_missing"


def case_authorization_disabled() -> str:
    with TemporaryDirectory() as tmp:
        transport = prior._script([])
        provider = prior._open(tmp, transport, auth=prior._auth(enabled=False))
        refused = prior._must(PaidCallRefused, lambda: provider.generate(prior._request()))
        assert "authorization_disabled" in refused.reasons
        assert transport.calls == []
        assert default_authorization()["enabled"] is False
    return "authorization_disabled"


def case_insufficient_budget() -> str:
    return prior.case_insufficient_budget()


def case_image_count() -> str:
    return prior.case_image_count_exceeded()


def case_persistent_reservation() -> str:
    return prior.case_persistent_reservation()


def case_concurrency() -> str:
    return prior.case_concurrent_calls()


def case_api_key_absent() -> str:
    with TemporaryDirectory() as tmp:
        transport = prior._script([])
        provider = prior._closed(tmp, transport, env={})
        refused = prior._must(PaidCallRefused, lambda: provider.generate(prior._request()))
        assert "api_key_missing" in refused.reasons
        assert transport.calls == []
    return "api_key_missing"


def case_dry_run() -> str:
    with TemporaryDirectory() as tmp:
        transport = prior._script([])
        provider = prior._open(tmp, transport, dry_run=True)
        refused = prior._must(PaidCallRefused, lambda: provider.generate(prior._request()))
        assert "dry_run" in refused.reasons
        assert transport.calls == []
    return "dry_run"


def case_no_generation_call() -> str:
    assert LIVE_HTTP_ENABLED is False
    detail = prior.case_no_paid_endpoint_calls()
    with TemporaryDirectory() as tmp:
        transport = SealedTransport()
        provider = BlackForestLabsImageProvider(
            transport=transport,
            ledger_path=Path(tmp) / "ledger.json",
            env={},
        )
        prior._must(PaidCallRefused, lambda: provider.generate(prior._request()))
        assert transport.calls == []
        assert provider.check_availability()["reachable"] == "NOT_CONTACTED"
    return detail


def case_no_image_download() -> str:
    with TemporaryDirectory() as tmp:
        destination = Path(tmp) / "door_already_open.png"
        transport = SealedTransport()
        provider = BlackForestLabsImageProvider(
            transport=transport,
            ledger_path=Path(tmp) / "ledger.json",
            env={},
        )
        prior._must(PaidCallRefused, lambda: provider.generate(prior._request()))
        assert not destination.exists()
        assert transport.calls == []
    return "no download"


def case_no_cover_files() -> str:
    with TemporaryDirectory() as tmp:
        docx = Path(tmp) / "front_cover.docx"
        pdf = Path(tmp) / "front_cover.pdf"
        prior._must(CoverRenderNotAuthorized, lambda: CoverRenderer().render_front_docx({}, docx))
        prior._must(CoverRenderNotAuthorized, lambda: CoverRenderer().render_front_pdf({}, pdf))
        assert not docx.exists()
        assert not pdf.exists()
    return "docx and pdf refused"


def case_canonical_unchanged() -> str:
    snap = snapshot()
    assert snap["book_json"]["sha256"] == EXPECTED_BOOK_SHA256
    return "book.json matches"


def case_interior_unchanged() -> str:
    snap = snapshot()
    assert snap["interior_docx"]["sha256"] == EXPECTED_INTERIOR_DOCX_SHA256
    assert snap["interior_pdf"]["sha256"] == EXPECTED_INTERIOR_PDF_SHA256
    return "interior matches"


def case_previous_tests() -> str:
    report = prior.evaluate_cases()
    assert report["failed"] == 0, report["failed_names"]
    assert report["passed"] == 36
    assert report["live_provider_calls"] == 0
    book = production_book_path()
    directions = build_front_cover_directions(json.loads(book.read_text(encoding="utf-8")))
    chosen = directions[0]
    assert chosen["name"] == "The door already open"
    assert ART_DIRECTION.casefold() == chosen["name"].casefold()
    assert "no words" in chosen["prompt"]
    return "36 previous cases passed"


def _request(width: int, height: int) -> ImageGenerationRequest:
    return prior._request(width_px=width, height_px=height)


CASES = [
    ("01_valid_resolution", case_valid_resolution),
    ("02_invalid_resolution", case_invalid_resolution),
    ("03_pixel_cap_exceeded", case_pixel_cap),
    ("04_not_multiple_of_16", case_not_multiple),
    ("05_portrait_ratio", case_portrait_ratio),
    ("06_megapixel_calculation", case_megapixels),
    ("07_cost_calculation", case_cost_calculation),
    ("08_billing_rounding", case_billing_rounding),
    ("09_unknown_maximum_cost", case_unknown_maximum),
    ("10_unverified_pricing", case_unverified_pricing),
    ("11_authorization_absent", case_authorization_absent),
    ("12_authorization_disabled", case_authorization_disabled),
    ("13_insufficient_budget", case_insufficient_budget),
    ("14_image_count_exceeded", case_image_count),
    ("15_persistent_reservation", case_persistent_reservation),
    ("16_concurrency", case_concurrency),
    ("17_api_key_absent", case_api_key_absent),
    ("18_dry_run", case_dry_run),
    ("19_no_generation_call", case_no_generation_call),
    ("20_no_image_download", case_no_image_download),
    ("21_no_cover_docx_pdf", case_no_cover_files),
    ("22_canonical_unchanged", case_canonical_unchanged),
    ("23_interior_unchanged", case_interior_unchanged),
    ("24_previous_tests_no_regression", case_previous_tests),
]
CASE_NAMES = [name for name, _function in CASES]


__all__ = ["CASE_NAMES", "evaluate_cases"]
