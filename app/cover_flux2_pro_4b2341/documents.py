"""Audit documents for phase 4B.2.34.1. Built from the code and the pages read."""

from __future__ import annotations

from typing import Any, Mapping

from app.cover.art.directions import build_front_cover_directions
from app.cover.image_providers.bfl_budget import default_authorization
from app.cover.image_providers.bfl_pricing import cost_estimation_examples, official_pro_text_to_image_schedule
from app.cover.image_providers.bfl_spec import (
    DOC_API_TERMS,
    DOC_COMMERCIAL,
    DOC_COSTS,
    DOC_DEVELOPER_TERMS,
    DOC_DIMENSIONS,
    DOC_EU_API_TERMS,
    DOC_EU_DEVELOPER_TERMS,
    DOC_OVERVIEW,
    DOC_PRICING,
    DOC_SPECS,
    DOC_SUBMIT,
    DOC_USAGE_POLICY,
    OFFICIAL_MODEL_ID,
    VERIFIED_ON,
    print_scaling_analysis,
    resolution_constraints,
    selected_generation_record,
)
from app.cover.image_providers.bfl_transport import LIVE_HTTP_ENABLED
from app.cover_flux2_pro_4b2341.constants import (
    ART_DIRECTION,
    BOOK_TITLE,
    DECISION,
    EXPECTED_BOOK_SHA256,
    INTERIOR_PDF_PAGES,
    INTERIOR_VERSION,
    PHASE,
    PROJECT_NAME,
    RESULT,
)
from app.cover_flux2_pro_4b2341.paths import planned_image_path


def build_documents(
    *,
    book: Mapping[str, Any],
    cases: Mapping[str, Any],
    hashes: Mapping[str, Any],
) -> dict[str, Any]:
    selected = selected_generation_record()
    scaling = print_scaling_analysis()
    constraints = resolution_constraints()
    schedule = official_pro_text_to_image_schedule()
    examples = dict(cases.get("cost_examples") or cost_estimation_examples())
    prompt = _updated_prompt(book, selected)
    plan = _first_test_plan(prompt, selected)
    readiness = _readiness(cases, selected, hashes)
    return {
        "official_resolution_constraints.md": _resolution_md(constraints, selected),
        "selected_generation_resolution.json": selected,
        "print_scaling_analysis.md": _scaling_md(scaling),
        "commercial_rights_verification.md": _commercial_md(),
        "official_pricing_verification.md": _pricing_md(schedule, selected),
        "cost_estimation_tests.json": examples,
        "first_image_test_plan.json": plan,
        "updated_art_prompt.json": prompt,
        "offline_test_results.json": {
            "passed": cases["passed"],
            "failed": cases["failed"],
            "failed_names": cases["failed_names"],
            "live_provider_calls": cases["live_provider_calls"],
            "paid_cost_usd": cases["paid_cost_usd"],
            "cases": cases["cases"],
        },
        "canonical_hashes_pre_post.json": dict(hashes),
        "readiness.json": readiness,
        "report_text": _report(readiness, selected, scaling),
    }


def _updated_prompt(book: Mapping[str, Any], selected: Mapping[str, Any]) -> dict[str, Any]:
    direction = build_front_cover_directions(book)[0]
    return {
        "art_direction": ART_DIRECTION,
        "source_direction_name": direction["name"],
        "source_phase": "4B.2.34",
        "prompt_text_changed": False,
        "prompt": direction["prompt"],
        "negative_prompt_editorial_note": direction["negative_prompt"],
        "negative_prompt_transmitted": False,
        "themes": direction["themes"],
        "title_space": direction["title_space"],
        "width": selected["width"],
        "height": selected["height"],
        "output_format": "png",
        "disable_pup": True,
        "embed_text": False,
        "technical_adjustments": [
            "The approved prompt already asks for a vertical two-to-three ratio. 1632×2448 is exactly 2:3, so the picture language stays.",
            "Width and height are request fields. They are not added to the prompt.",
            "disable_pup stays true so the written prompt is not rewritten by the provider.",
            "The image stays text-free. The Cover Renderer adds the title later.",
        ],
        "image_generated": False,
    }


def _first_test_plan(prompt: Mapping[str, Any], selected: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "activated": False,
        "authorized": False,
        "persistent_authorization_written": False,
        "provider": "Black Forest Labs",
        "model_id": OFFICIAL_MODEL_ID,
        "endpoint": "https://api.bfl.ai/v1/flux-2-pro",
        "resolution": {"width": selected["width"], "height": selected["height"]},
        "output_format": "png",
        "disable_pup": True,
        "prompt": prompt["prompt"],
        "negative_prompt_transmitted": False,
        "image_count": 1,
        "max_cost_usd": None,
        "max_cost_verified": False,
        "destination": planned_image_path(),
        "destination_created": False,
        "checks_after_download": [
            "HTTPS delivery host matching delivery.<region>.bfl.ai",
            "PNG signature and decoded size 1632×2448",
            "SHA-256 stored beside the file",
            "Observed cost recorded when the response includes one",
            "Stop if the observed cost exceeds the budget named in a later explicit authorization",
            "Human inspection for text, church imagery, and title-field contrast",
        ],
        "visual_acceptance": [
            "An ordinary interior door already open",
            "Light already in the room",
            "Calm domestic atmosphere",
            "Upper third kept as a quiet field for later title type",
            "No words, letters, logo, or author name in the image",
        ],
        "stop_conditions": [
            "Maximum cost still unknown",
            "No explicit user authorization for the paid call",
            "API key missing",
            "Dry-run still on",
            "Resolution rejected by the local validator",
            "Provider status other than Ready",
            "Delivery URL host not allowed",
        ],
        "will_not_run_in_this_phase": True,
    }


def _readiness(
    cases: Mapping[str, Any],
    selected: Mapping[str, Any],
    hashes: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "phase": PHASE,
        "result": RESULT,
        "decision": DECISION,
        "provider_calls": 0,
        "paid_cost_usd": 0,
        "provider": "Black Forest Labs",
        "model_id": OFFICIAL_MODEL_ID,
        "art_direction": ART_DIRECTION,
        "resolution_constraints": "VERIFIED",
        "selected_width": selected["width"],
        "selected_height": selected["height"],
        "total_pixels": selected["pixels"],
        "aspect_ratio": selected["aspect_ratio"],
        "width_over_height": selected["width_over_height"],
        "commercial_use": "VERIFIED",
        "canadian_use_conditions": "VERIFIED",
        "pricing": "UNVERIFIED",
        "max_cost_per_image_usd": None,
        "cost_estimator": "BLOCKED",
        "paid_call_guard": "PASS",
        "first_test_image_count": 1,
        "first_test_authorized": False,
        "image_generated": False,
        "cover_docx_generated": False,
        "cover_pdf_generated": False,
        "offline_tests_passed": cases["passed"],
        "offline_tests_failed": cases["failed"],
        "canonical_hashes": "MATCH" if hashes.get("match") else "MISMATCH",
        "ready_for_first_image_test": False,
        "remaining_blockers": [DECISION],
        "live_http_enabled": LIVE_HTTP_ENABLED,
        "default_authorization_enabled": default_authorization()["enabled"],
        "legal_certification": False,
        "professional_print_quality_guaranteed": False,
    }


def _resolution_md(constraints: Mapping[str, Any], selected: Mapping[str, Any]) -> str:
    prior = selected["rejected_prior_size"]
    square = selected["documented_square_example"]
    return f"""# Official resolution constraints

Consulted on {VERIFIED_ON}. No generation request was sent.

## Sources

- {DOC_SPECS}
- {DOC_DIMENSIONS}
- {DOC_SUBMIT}

## What the pages state

| Constraint | Official statement |
| --- | --- |
| Minimum | 64 × 64 pixels. OpenAPI `minimum: 64` on width and height. |
| Maximum | 4 megapixels, with 2048 × 2048 given as the example. |
| Step | Width and height must be multiples of 16. |
| Default | 1024 × 1024. |
| Aspect ratio | Any. Portrait is allowed. There is no separate portrait limit. |
| Over 4MP | “Images over 4MP are automatically resized.” The page does not promise a rejection. |
| Below 64 | Schema validation. The errors page says an invalid body returns HTTP 422. |
| Not a multiple of 16 | Required by the help center. The published OpenAPI schema does not repeat the rule, and the pages read do not name the HTTP status for that case. |
| Quality note | The help center recommends staying at or below 2MP for quality and speed. |

## How “4 megapixels” is applied

The billing article treats 1920 × 1080 as 2.07MP, which is pixels / 1,000,000. On that decimal reading, 4 megapixels is 4,000,000 pixels.

The same help center calls 2048 × 2048 the maximum example. That square is {square["pixels"]} pixels, above 4,000,000. The phase does not send it.

The previous candidate {prior["width"]} × {prior["height"]} is {prior["pixels"]} pixels. It is above 4,000,000 and is refused before any call. Problems: {prior["problems"]}.

The local validator also refuses a size the API might otherwise accept and silently resize. A silent resize could change the billed output.

## Selected size

{selected["width_times_height"]}

width / height = {selected["width_over_height"]}

Exact 2:3: {selected["exact_two_to_three"]}.
"""


def _scaling_md(scaling: Mapping[str, Any]) -> str:
    risks = "\n".join(f"- {item}" for item in scaling["risks"])
    return f"""# Print scaling

Finished cover: 6 × 9 inches. Bleed: 3 mm, configurable later by the printer. Canvas target: 300 ppi. This phase does not change the interior.

## Generation

- Size: {scaling["generation_px"][0]} × {scaling["generation_px"][1]} px
- Pixels: {scaling["generation_pixels"]}
- Source ratio width / height: {scaling["source_ratio_width_over_height"]}

## Printed area

- Trim ratio width / height: {scaling["trim_ratio_width_over_height"]}
- Bleed canvas: {scaling["bleed_canvas_px"][0]} × {scaling["bleed_canvas_px"][1]} px
- Bleed ratio width / height: {scaling["bleed_ratio_width_over_height"]}
- Physical size with 3 mm bleed, inches: {scaling["physical_bleed_inches"][0]} × {scaling["physical_bleed_inches"][1]}

## Placement

- Uniform cover scale: {scaling["uniform_cover_scale_exact"]}
- Scale is driven by the {scaling["scale_driven_by"]}.
- Source pixels used: {scaling["source_pixels_used"][0]} × {scaling["source_pixels_used"][1]}
- Source pixels cropped: {scaling["source_pixels_cropped"][0]} × {scaling["source_pixels_cropped"][1]}
- {scaling["crop"]}

## Effective sampling

- About {scaling["effective_ppi_across_width"]} ppi across the physical width
- Target canvas: {scaling["target_canvas_ppi"]} ppi
- Professional print quality guaranteed: {scaling["professional_print_quality_guaranteed"]}

## Risks

{risks}
"""


def _commercial_md() -> str:
    return f"""# Commercial rights

Status: VERIFIED for the texts below. This is not a legal certification. Consulted on {VERIFIED_ON}. No account and no API call.

Canadian use conditions: VERIFIED for the residence rule the pages themselves state. A person who resides in Canada resides outside the European Union, so the non-EU Developer Terms and the non-EU API Terms are the documents those pages select. The usage policy’s EU AI Act clauses are addressed to users based in or established in the European Union. If the same person uses the service through an EU establishment, the EU terms say they apply. Both the non-EU and the EU output clauses that were read grant the customer ownership of Output and allow commercial use, subject to the terms.

## Sources and dates

| Document | URL | Date on the page |
| --- | --- | --- |
| Commercial-use article | {DOC_COMMERCIAL} | Last updated 3 months before {VERIFIED_ON} |
| Developer Terms, non-EU | {DOC_DEVELOPER_TERMS} | Last revised August 4, 2026 |
| FLUX API Service Terms, non-EU | {DOC_API_TERMS} | Last revised August 4, 2026 |
| EU Developer Terms | {DOC_EU_DEVELOPER_TERMS} | Retrieved {VERIFIED_ON} |
| EU API Service Terms | {DOC_EU_API_TERMS} | Retrieved {VERIFIED_ON} |
| Usage Policy | {DOC_USAGE_POLICY} | Last revised August 4, 2026 |

The open-weight licences are a different question. FLUX.2 [pro] is used here through the API. The API terms do not grant the right to download or self-host the model weights.

## Short excerpts

Help center: “Yes. All images generated through the BFL API include full commercial usage rights. You can use them in products, services, marketing, and any other commercial context.”

Help center: “No additional licensing fees: commercial use is included in the per-image cost.”

Developer Terms, opening: “These Developer Terms of Service apply if you reside outside the European Union (EU).”

Developer Terms, section 3(b): “As between you and us, you own all right, title, and interest in and to Output.”

Developer Terms, section 4(b): “You and your End Users may use Outputs for your or their own personal or commercial purposes, subject to any restrictions set forth in these Terms or applicable law.”

Developer Terms, section 3(b), also: Outputs may not be unique, must be reviewed by a person before use, must not be used as a Deepfake, and may carry Content Credentials.

API Terms, section 2(b): the customer grants Black Forest Labs a licence to use Inputs and Outputs to operate and improve the services, “including” training its models.

API Terms, section 8: these API terms do not grant the right to download or self-host the FLUX [dev] model.

Usage Policy: the customer must not “circumvent, remove, alter, suppress, or otherwise interfere with any C2PA Credentials, digital watermarks, or other content provenance signals” attached to Outputs.

## Application to this book

A sold printed book fits the help center’s “products” and “any other commercial context,” and the terms’ “commercial purposes.” The pages do not contain a separate sentence that names books. Cropping and later title type are consistent with owning the Output. They are not separately itemized. A later crop must not strip Content Credentials if the file carries them. No image is cropped in this phase.

No sentence requiring a printed credit to Black Forest Labs was found in the pages read. That absence is not a certification that no other contract imposes one.

## Still not a certification

This note records the public pages. It does not accept the terms, create an account, or approve the book description.
"""


def _pricing_md(schedule: Mapping[str, Any], selected: Mapping[str, Any]) -> str:
    return f"""# Official pricing

Status: UNVERIFIED as a maximum. Consulted on {VERIFIED_ON}. No billing endpoint and no generation endpoint was called.

## Sources

- {DOC_PRICING}
- {DOC_COSTS}
- {DOC_OVERVIEW}
- {DOC_API_TERMS}
- Fee URL named in the API terms: {schedule["terms_fee_url"]} — {schedule["terms_fee_url_status"]}

## What is published for FLUX.2 [pro]

| Item | Published statement |
| --- | --- |
| Unit | 1 credit = 0.01 USD. Pricing is the same for the API and the Playground. |
| Text-to-image | “from $0.03/MP” |
| Image editing | “from $0.045/MP” |
| Resolution effect | “FLUX.2 pricing scales with output resolution.” |
| Rounding | “Resolution always rounds UP to the next megapixel. For example, 1920×1080 = 2.07MP → charged as 3MP.” |
| Klein, not Pro | The first megapixel is a flat rate and each additional megapixel adds to it. The worked Klein 4B example is $0.014 + $0.001 = $0.015 for 2MP. |
| Calculator | “Use the pricing calculator for exact costs.” |
| Contract | Fees are the then-current prices. The API and the models may be changed at the company’s discretion. |

The words “from $0.03” are a floor. They are not used as a maximum. The additional-megapixel rate for [pro] is not published. The Klein formula is not applied to [pro].

The overview table says [pro] is “from $0.03 / MP” and [flex] is “$0.06 / MP”. The help-center cost article lists [flex] as “$0.05/MP”. Those two official pages disagree about [flex]. That disagreement is not used to invent a [pro] rate.

The static pricing page fetched on {VERIFIED_ON} showed a calculator whose visible rate was a FLUX 3 image price. It did not publish a static dollar amount for one {selected["width"]} × {selected["height"]} `flux-2-pro` image.

## Selected image

{selected["width"]} × {selected["height"]} = {selected["pixels"]} pixels = 3.995136 decimal megapixels.

The published round-up charges that as {schedule["selected_billed_megapixels"]} megapixels. Dividing by 1024 × 1024 and rounding up also yields 4. The help center’s label “1024×1024 = 1 megapixel” conflicts with a decimal ceiling of 1.048576, which is 2. The ceiling is kept because truncation would bill the published 2.07MP example as 2MP.

The dollar amount for those 4 billed megapixels is not determined. 0.03 × 4 = 0.12 is not a verified maximum.

A budget chosen by the user does not, by itself, limit what the provider charges. The API terms point at then-current prices, and the fee URL returned HTTP 404.

## If a later call is still wanted

Ask Black Forest Labs for the written maximum, in USD, of one text-to-image request to `{OFFICIAL_MODEL_ID}` at {selected["width"]} × {selected["height"]}, including rounding. Until that figure exists, the estimator refuses the call.

FLUX.2 [klein] 4B publishes “$0.014 + $0.001/MP” on the model overview, together with the same round-up example. That is a different model and it is not selected. FLUX.2 [flex] is not a safer substitute while its two official rates disagree. FLUX.1 Kontext [pro] is a fixed $0.04 per image at about 1MP and is not the chosen model.
"""


def _report(
    readiness: Mapping[str, Any],
    selected: Mapping[str, Any],
    scaling: Mapping[str, Any],
) -> str:
    return f"""**PHASE 4B.2.34.1 — FLUX.2 PRO UNBLOCK**

RESULT = {readiness["result"]}
PROVIDER CALLS = 0
PAID COST = 0 USD
PROVIDER = Black Forest Labs
MODEL = flux-2-pro
ART DIRECTION = {ART_DIRECTION}
RESOLUTION CONSTRAINTS = VERIFIED
SELECTED WIDTH = {selected["width"]}
SELECTED HEIGHT = {selected["height"]}
TOTAL PIXELS = {selected["pixels"]}
ASPECT RATIO = {selected["aspect_ratio"]} ({selected["width_over_height"]})
COMMERCIAL USE = VERIFIED
CANADIAN USE CONDITIONS = VERIFIED
PRICING = UNVERIFIED
MAX COST PER IMAGE = UNKNOWN
COST ESTIMATOR = BLOCKED
PAID CALL GUARD = PASS
FIRST TEST IMAGE COUNT = 1
FIRST TEST AUTHORIZED = NO
IMAGE GENERATED = NO
COVER DOCX GENERATED = NO
COVER PDF GENERATED = NO
OFFLINE TESTS = {readiness["offline_tests_passed"]} PASS / {readiness["offline_tests_failed"]} FAIL
CANONICAL HASHES = {readiness["canonical_hashes"]}
READY_FOR_FIRST_IMAGE_TEST = NO
REMAINING BLOCKERS = BLOCKED_PRICING

Project: {PROJECT_NAME}. Book: {BOOK_TITLE}. Interior: {INTERIOR_VERSION}, {INTERIOR_PDF_PAGES} pages. Canonical SHA-256: {EXPECTED_BOOK_SHA256}.

The strict pixel cap is 4,000,000. 1664 × 2496 (4,153,344) is refused. The selected portrait is 1632 × 2448, exactly 2:3, at 3,995,136 pixels. Placed on the 3 mm bleed canvas it samples the cover at about {scaling["effective_ppi_across_width"]} ppi. Print sharpness is not guaranteed.

API outputs include commercial use, and a customer outside the EU owns the Output as between the parties, subject to the terms, human review, the training licence, and Content Credentials. That is not a legal certification.

The published “from $0.03/MP” is a floor. The additional-megapixel rate for flux-2-pro is not on the official pages, and https://bfl.ai/pricing/api/ returned HTTP 404. The estimator therefore refuses every paid call. No persistent authorization was written.

## Official references

- {DOC_SPECS}
- {DOC_DIMENSIONS}
- {DOC_SUBMIT}
- {DOC_PRICING}
- {DOC_COSTS}
- {DOC_OVERVIEW}
- {DOC_COMMERCIAL}
- {DOC_DEVELOPER_TERMS}
- {DOC_API_TERMS}
- {DOC_EU_DEVELOPER_TERMS}
- {DOC_EU_API_TERMS}
- {DOC_USAGE_POLICY}

STOP. Do not call the API, spend money, generate an image, download a model, or produce a cover until the maximum cost is known and a separate explicit authorization exists.
"""


__all__ = ["build_documents"]
