"""Audit documents for phase 4B.2.34.2. Built from the adapter and the pages read."""

from __future__ import annotations

from typing import Any, Mapping

from app.cover.content.contract import initial_content
from app.cover.image_providers.bfl_transport import LIVE_HTTP_ENABLED
from app.cover.image_providers.openai_art import prompt_record
from app.cover.image_providers.openai_image import default_openai_authorization
from app.cover.image_providers.openai_pricing import pricing_facts, quality_cost_comparison
from app.cover.image_providers.openai_spec import (
    DOC_GUIDE,
    DOC_MODEL,
    DOC_PRICING,
    DOC_PROMPTING,
    DOC_REFERENCE,
    DOC_SERVICE_TERMS,
    DOC_SERVICES,
    GENERATION_URL,
    OFFICIAL_MODEL_ID,
    PROVIDER_ID,
    REQUESTED_OUTPUT_FORMAT,
    REQUESTED_QUALITY,
    SELECTED_HEIGHT,
    SELECTED_WIDTH,
    SNAPSHOT_MODEL_ID,
    VERIFIED_ON,
    candidate_sizes,
    print_resolution_plan,
)
from app.cover_gpt_image_2_4b2342.constants import (
    ART_DIRECTION,
    AUTHORIZATION_SCOPE,
    BOOK_TITLE,
    DECISION,
    EXPECTED_BOOK_SHA256,
    INTERIOR_PDF_PAGES,
    INTERIOR_VERSION,
    PHASE,
    PRIOR_SCOPE,
    PROJECT_NAME,
    RESULT,
)
from app.cover_gpt_image_2_4b2342.paths import planned_image_path


def build_documents(
    *,
    cases: Mapping[str, Any],
    hashes: Mapping[str, Any],
) -> dict[str, Any]:
    content = initial_content()
    plan = print_resolution_plan()
    facts = pricing_facts()
    comparison = quality_cost_comparison()
    art = prompt_record()
    selected = next(row for row in candidate_sizes() if row["selected"])
    readiness = _readiness(cases, selected, content)
    documents: dict[str, Any] = {
        "openai_documentation_verification.md": _documentation(),
        "openai_image_provider_contract.json": _contract(),
        "openai_adapter_implementation.md": _adapter(),
        "supported_resolutions.json": {
            "consulted_on": VERIFIED_ON,
            "model_id": OFFICIAL_MODEL_ID,
            "flux_limits_reused": False,
            "constraints": _constraints(),
            "candidates": candidate_sizes(),
            "selected": selected,
            "print_plan": plan,
        },
        "quality_cost_comparison.json": comparison,
        "pricing_and_budget_analysis.md": _pricing(facts, plan),
        "commercial_use_verification.md": _commercial(),
        "updated_art_prompt.json": art,
        "first_image_test_plan.json": _test_plan(art, selected, facts),
        "offline_test_results.json": {
            "passed": cases["passed"],
            "failed": cases["failed"],
            "failed_names": cases["failed_names"],
            "live_provider_calls": 0,
            "paid_cost_usd": 0,
            "cases": list(cases["cases"]),
        },
        "canonical_hashes_pre_post.json": dict(hashes),
        "readiness.json": readiness,
    }
    documents["report_text"] = _report(readiness, cases, selected, facts, plan)
    return documents


def _readiness(cases: Mapping[str, Any], selected: Mapping[str, Any], content: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "phase": PHASE,
        "result": RESULT,
        "decision": DECISION,
        "provider_calls": 0,
        "paid_cost_usd": 0,
        "primary_provider": "OpenAI",
        "primary_model": OFFICIAL_MODEL_ID,
        "secondary_provider": "Black Forest Labs",
        "secondary_model": "flux-2-pro",
        "api_documentation": "VERIFIED_WITH_GAPS",
        "commercial_use": "VERIFIED_NOT_A_LEGAL_CERTIFICATION",
        "api_adapter": "IMPLEMENTED_SEALED",
        "selected_resolution": selected["size"],
        "selected_quality": REQUESTED_QUALITY,
        "output_format": REQUESTED_OUTPUT_FORMAT,
        "estimated_image_output_usd": selected["published_image_output_estimates_usd"]["medium"],
        "full_request_estimate_usd": None,
        "verified_maximum_cost_usd": None,
        "budget_guard": "PASS",
        "art_direction": ART_DIRECTION,
        "image_generated": False,
        "front_cover_generated": False,
        "back_cover_generated": False,
        "cover_docx_generated": False,
        "cover_pdf_generated": False,
        "offline_tests_passed": cases["passed"],
        "offline_tests_failed": cases["failed"],
        "canonical_hashes": "MATCH",
        "ready_for_first_image_test": False,
        "persistent_authorization_written": False,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "prior_scope_reused": False,
        "prior_scope": PRIOR_SCOPE,
        "live_http_enabled": LIVE_HTTP_ENABLED,
        "author_biography_status": content["author_biography_status"],
        "book_description_status": content["book_description_status"],
        "remaining_blockers": [
            "BLOCKED_BILLING_CEILING",
            "TOKEN_MAXIMUM_NOT_GUARANTEED_BEFORE_REQUEST",
            "USAGE_FIELD_NOT_CONFIRMED_FOR_GPT_IMAGE_2",
            "PER_TOKEN_RATE_TABLES_CONFLICT",
        ],
    }


def _test_plan(art: Mapping[str, Any], selected: Mapping[str, Any], facts: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "activated": False,
        "authorized": False,
        "persistent_authorization_written": False,
        "provider": PROVIDER_ID,
        "model": OFFICIAL_MODEL_ID,
        "snapshot_recorded_not_sent": SNAPSHOT_MODEL_ID,
        "concept": ART_DIRECTION,
        "prompt_sha256": art["prompt_sha256"],
        "image_count": 1,
        "quality": REQUESTED_QUALITY,
        "resolution": f"{SELECTED_WIDTH}x{SELECTED_HEIGHT}",
        "output_format": REQUESTED_OUTPUT_FORMAT,
        "background": "opaque",
        "reference_images": 0,
        "published_image_output_estimate_usd": facts["published_image_output_estimate_usd"],
        "full_request_estimate_usd": None,
        "verified_maximum_cost_usd": None,
        "estimate_is_a_billing_guarantee": False,
        "destination": planned_image_path(),
        "destination_created": False,
        "exact_two_to_three": selected["exact_two_to_three"],
        "experimental": selected["experimental"],
    }


def _contract() -> dict[str, Any]:
    return {
        "interface": "CoverImageProvider",
        "implementation": "OpenAIImageProvider",
        "provider_id": PROVIDER_ID,
        "model_id": OFFICIAL_MODEL_ID,
        "endpoint": GENERATION_URL,
        "authentication": "Authorization: Bearer $OPENAI_API_KEY",
        "key_environment_variable": "OPENAI_API_KEY",
        "key_written_to_repository": False,
        "production_fake_provider": False,
        "mocks_allowed_in": "tests_only",
        "methods": ["check_availability", "get_capabilities", "estimate_cost", "generate"],
        "request_controls": [
            "provider_id",
            "model_id",
            "prompt",
            "quality",
            "width",
            "height",
            "output_format",
            "image_count",
            "estimated_cost_usd",
        ],
        "result_controls": [
            "observed_cost_usd",
            "generation_status",
            "output_path",
            "image_sha256",
            "provider_metadata",
        ],
        "generated_only_after_png_validation": True,
        "automatic_paid_retry": False,
        "default_authorization": default_openai_authorization(),
        "live_http_client": False,
    }


def _constraints() -> dict[str, Any]:
    return {
        "edges_multiple_of": 16,
        "max_edge_px": 3840,
        "long_to_short_max": "3:1",
        "min_pixels": 655_360,
        "max_pixels": 8_294_400,
        "experimental_above_pixels": 3_686_400,
        "experimental_wording": "Outputs with more than 3,686,400 total pixels (2560x1440) are experimental.",
        "recommended_portrait": "1024x1536",
        "documented_4k_portrait": "2160x3840",
        "qualities_for_gpt_image_2": ["low", "medium", "high", "auto"],
        "qualities_sent_by_this_adapter": ["low", "medium", "high"],
        "auto_refused_because": "the guide says auto depends on the generated image",
        "xhigh_and_max": "documented for gpt-image-2.5, not for gpt-image-2",
    }


def _documentation() -> str:
    return f"""# OpenAI documentation verification

Consulted on {VERIFIED_ON}. No API call. No account inspection.

## Sources

- {DOC_MODEL}
- {DOC_GUIDE}
- {DOC_PRICING}
- {DOC_REFERENCE}
- {DOC_PROMPTING}
- {DOC_SERVICES}
- {DOC_SERVICE_TERMS}

## Confirmed

- Model id: `gpt-image-2`. Snapshot also listed: `gpt-image-2-2026-04-21`. This adapter sends the alias the phase names, and records the snapshot without sending it.
- Direct generation endpoint: `POST {GENERATION_URL}`.
- The image guide says the Image API is the choice for one image from one prompt. The Responses API adds a conversational model and is not used.
- Authentication in the reference curl: `Authorization: Bearer $OPENAI_API_KEY`.
- Generation parameters read on the reference: `model`, `prompt` (maximum 32,000 characters), `n` (1 to 10), `size`, `quality`, `output_format` (`png`, `jpeg`, `webp`), `output_compression` (jpeg and webp), `background` (`transparent`, `opaque`, `auto`), `moderation` (`low`, `auto`), `stream`, `partial_images` (0 to 3), `user`.
- `response_format` and `style` are documented as unsupported for GPT image models. They are not sent.
- GPT Image models return base64 in `data[].b64_json`. A URL response is documented as unsupported for those models.
- Qualities for `gpt-image-2`: `low`, `medium`, `high`, and `auto`. `xhigh` and `max` are documented for the 2.5 models.
- Size constraints for `gpt-image-2`: both edges multiples of 16, neither edge above 3,840, long-to-short ratio at most 3:1, total pixels from 655,360 through 8,294,400.
- Popular sizes include `1024x1024`, `1536x1024`, `1024x1536`, `2048x2048`, `2048x1152`, `3840x2160`, and `2160x3840`.
- The prompting guide says outputs with more than 3,686,400 pixels (`2560x1440`) are experimental.
- Default output format in the guide: `png`.
- `partial_images` adds 100 image output tokens per partial. This adapter does not stream.
- Cached input pricing applies to the Responses API image tool and does not apply to direct Images API requests.
- Rate limits on the model page, images per minute: Free not supported; tier 1 is 5; tier 2 is 20; tier 3 is 50; tier 4 is 150; tier 5 is 250. Tokens per minute are listed beside those tiers. A rate limit is not a per-image dollar cap.
- The guide says organization verification may be required before GPT Image models can be used.
- The guide says not to retry quota errors or `image_generation_user_error` automatically. This adapter retries nothing.
- Pricing page, in the table that names `gpt-image-2`, per 1M tokens: image input $4.00, cached image input $1.00, image output $15.00, text input $2.50, cached text input $0.625.
- The guide's comparison table gives rounded image-output estimates for `1024x1024`, `1024x1536`, and `1536x1024` at low, medium, and high. It says to still account for text input tokens. It says a larger non-square size can use fewer output tokens than a smaller size.
- Services Agreement, effective January 1, 2026: the customer owns Output, and OpenAI assigns its interest in Output to the customer. Section 1.5 says usage-based fees are calculated by OpenAI. Section 6.6 says price changes take effect fourteen days after they are posted, and that OpenAI may correct pricing errors after an invoice.

## Not confirmed

- Whether this OpenAI organization has completed API Organization Verification. The phase did not open the account.
- Whether `gpt-image-2` returns `usage`. The reference schema says the usage object is for `gpt-image-1` only. A curl example that includes `usage` names `gpt-image-2.5-flare`, not `gpt-image-2`.
- A token count, or a dollar maximum, that is guaranteed before the request for a chosen size and quality. The published dollar cells are estimates.
- A request field that tells the provider to stop at a dollar amount. None was found on the Images generation reference.
- Which output-token rate is the invoice rate. The pricing page prints $15 beside `gpt-image-2` and also prints $30 for `gpt-image-2.5`. The guide states the $30 schedule for 2.5 and says the models can share the same price per image output token.
- That the character limit of 32,000 is a token ceiling. It is a character ceiling.
- A Canada-specific output clause. None was found on the pages read.
- That the Services Agreement names printed books. It does not.

## Adapter choice

One text prompt, one image, no reference image, no conversational model. The call, when a later phase unlocks it, is `POST /v1/images/generations`.
"""


def _adapter() -> str:
    return """# OpenAI adapter

`OpenAIImageProvider` implements `CoverImageProvider`. `BlackForestLabsImageProvider` is unchanged.

The default instance uses `TokenBillingPricing`, a disabled authorization, `dry_run=True`, and `phase_lock=True`. It refuses before a reservation and before the transport. The module does not import `urllib`. Tests inject a mock transport. There is no production fake provider.

`OPENAI_API_KEY` is read from the environment mapping passed to the provider. The value is placed only in the `Authorization` header of a call that has already passed the guard. It is not written to `book.json`, a cover record, the reservation ledger, a result object, or a prompt.

An image is marked generated only after the base64 payload decodes as a PNG of the requested width and height and the bytes just written hash to the same SHA-256. A corrupt payload, a remote URL, a missing `b64_json`, a non-200 status, or a timeout marks the reservation `outcome_unknown` and does not start another paid call.

The body sends `model`, `prompt`, `n=1`, `size`, `quality`, `output_format`, and `background=opaque`. It does not send a negative prompt, a seed, `stream`, `partial_images`, `response_format`, or a reference image. `disable_pup` belongs to Black Forest Labs and is not sent.
"""


def _pricing(facts: Mapping[str, Any], plan: Mapping[str, Any]) -> str:
    placement = plan["placement"]
    return f"""# Pricing and budget

Consulted on {VERIFIED_ON}. No API call.

## What is billed

The pricing page bills tokens. A text-only generation can include text input tokens and image output tokens. Image input tokens apply when reference images are sent. This phase attaches none. Cached input rates are documented for the Responses API and are documented as not applying to `POST /v1/images/generations`.

Partial images add 100 output tokens each. This adapter does not stream, so that extra is not requested. Omitting it does not cap the final image.

## Published image-output estimates

These are the guide's rounded comparison cells. They exclude text tokens. They are not ceilings.

| Size | Low | Medium | High |
| --- | --- | --- | --- |
| 1024×1024 | 0.006 | 0.053 | 0.211 |
| 1024×1536 | 0.005 | 0.041 | 0.165 |
| 1536×1024 | 0.005 | 0.041 | 0.165 |

Custom sizes, including 1536×2304 and 2160×3840, have no cell in that table. Their full request estimate is unknown.

The selected first-test quality is medium at 1024×1536. The published image-output component is {facts["published_image_output_estimate_usd"]} USD. The guide calls `low` a draft setting and says final assets should be compared at higher settings. Medium is the explicit middle setting for a first look. High's published image-output component at the same size is 0.165 USD. Neither figure is a guaranteed invoice.

Text input is additional, at the rate printed beside the model, once the token count exists. The count is not known before the provider tokenizes the prompt.

## Why the call stays blocked

- No page states a maximum output-token count for a size and quality.
- The guide says a larger size can cost fewer output tokens than a smaller one, so pixel count is not a ceiling.
- The $15 and $30 output rates are both printed in the official pages, for different named models, with a sentence that the models can share a rate. That conflict means a token count would still not produce one invoice amount.
- The usage object is not confirmed for `gpt-image-2`, so a cost might not be observable after the call either.
- No Images API field was found that stops billing at a dollar amount.
- Rate limits cap throughput. They do not cap the price of one image.
- A local `max_budget_usd` reserves money in this repository's ledger. It does not bind OpenAI. Section 1.5 of the Services Agreement says usage-based fees are calculated by OpenAI. Section 6.6 allows a later price correction.

`TokenBillingPricing` therefore returns `estimated_cost_usd = null` and `verified_maximum_cost_usd = null`. The guard adds `billing_ceiling_not_guaranteed` and `estimated_cost_unknown`. A local budget of 1000 USD does not remove those reasons.

The reservation ledger, the one-shot lock, the ban on automatic retries, and the refusal to reuse the phase 4B.2.34.1 authorization are unchanged in spirit and are applied to this provider. No authorization file is written for a later automatic run.

## Print note for the selected size

1024×1536 is exact 2:3. Placed on the 6×9 trim it is about {placement["trim_effective_ppi"]} ppi, with an enlargement of about {placement["upscale_factor_to_trim"]} toward 300 ppi. The bleed canvas needs a small cover-crop. Professional sharpness is not guaranteed. A later visual inspection decides whether a larger legal size is worth a separate, still-capped test. Those larger sizes have no published dollar cell, so they are not selected while the ceiling is unknown.
"""


def _commercial() -> str:
    return f"""# Commercial use

Status: VERIFIED for the clauses below. This is not a legal certification. Consulted on {VERIFIED_ON}. No account and no API call.

## Sources

| Document | URL | Date on the page |
| --- | --- | --- |
| Services Agreement | {DOC_SERVICES} | Updated December 1, 2025. Effective January 1, 2026. |
| Service terms | {DOC_SERVICE_TERMS} | Retrieved {VERIFIED_ON} |

The Services Agreement says it applies to OpenAI's APIs and to services for businesses and developers, and that it does not apply to consumer services unless specified. The consumer Terms of Use are a different document. They were not used as the API grant.

## Clauses read

Section 2.2 grants the customer a non-exclusive right to access and use the Services, including the right to use the API in customer applications and to make those applications available to end users.

Section 4.1: as between the customer and OpenAI, to the extent permitted by law, the customer retains ownership of Input and owns Output. OpenAI assigns to the customer all OpenAI's right, title, and interest, if any, in Output.

Section 4.3: the customer is responsible for Input and for evaluating Output for the use case.

Section 4.4: Output may not be unique.

Section 3.3 restricts competing-model training, key resale, and circumvention of limits. It does not forbid selling a book that contains an image the customer owns.

The service-terms excerpt that was read says the output-infringement indemnity does not apply where Output was modified, transformed, or combined with products OpenAI did not provide. Cropping and later title type are modifications. The indemnity is not relied on for the finished cover.

## Application to this book

A sold book is a customer application of Output the agreement says the customer owns. The pages do not name books, Canada, or a required printed credit. No Canada-specific output clause was found. No image was generated, cropped, or published in this phase.

The Black Forest Labs commercial verification from phase 4B.2.34.1 still applies to `flux-2-pro`. It is not the grant for OpenAI output.
"""


def _report(
    readiness: Mapping[str, Any],
    cases: Mapping[str, Any],
    selected: Mapping[str, Any],
    facts: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> str:
    blockers = ", ".join(readiness["remaining_blockers"])
    placement = plan["placement"]
    return f"""**PHASE 4B.2.34.2 — GPT IMAGE 2 INTEGRATION**

RESULT = {readiness["result"]}
PROVIDER CALLS = 0
PAID COST = 0 USD
PRIMARY PROVIDER = OpenAI
PRIMARY MODEL = gpt-image-2
SECONDARY PROVIDER = Black Forest Labs
SECONDARY MODEL = flux-2-pro
API DOCUMENTATION = VERIFIED WITH GAPS
COMMERCIAL USE = VERIFIED, NOT A LEGAL CERTIFICATION
API ADAPTER = IMPLEMENTED, SEALED
SELECTED RESOLUTION = {selected["width"]} × {selected["height"]}
SELECTED QUALITY = {REQUESTED_QUALITY}
OUTPUT FORMAT = {REQUESTED_OUTPUT_FORMAT}
ESTIMATED COST PER IMAGE = {facts["published_image_output_estimate_usd"]} USD published image-output component only; full request estimate UNKNOWN
VERIFIED MAXIMUM COST = UNKNOWN
BUDGET GUARD = PASS
ART DIRECTION = The Door Already Open
IMAGE GENERATED = NO
FRONT COVER GENERATED = NO
BACK COVER GENERATED = NO
COVER DOCX GENERATED = NO
COVER PDF GENERATED = NO
OFFLINE TESTS = {cases["passed"]} PASS / {cases["failed"]} FAIL
CANONICAL HASHES = MATCH
READY_FOR_FIRST_IMAGE_TEST = NO
REMAINING BLOCKERS = {blockers}

Project: {PROJECT_NAME}. Book: {BOOK_TITLE}. Interior: {INTERIOR_VERSION}, {INTERIOR_PDF_PAGES} pages. Canonical SHA-256: {EXPECTED_BOOK_SHA256}.

`OpenAIImageProvider` sits on `CoverImageProvider`. The Black Forest Labs adapter is still installed and still sealed. The direct Images endpoint is `POST {GENERATION_URL}` with model `gpt-image-2`. The snapshot `{SNAPSHOT_MODEL_ID}` is recorded and not sent. No conversational model is added.

1024×1536 is the documented portrait size, exact 2:3, and the only portrait candidate with a published image-output estimate. On the 6×9 trim that image is about {placement["trim_effective_ppi"]} ppi. The enlargement toward 300 ppi is about {placement["upscale_factor_to_trim"]}. Sharpness is not guaranteed. Larger legal sizes have no published dollar cell and were not selected. FLUX pixel limits were not reused.

The guide's medium cell for this size is {facts["published_image_output_estimate_usd"]} USD of image output, excluding text tokens. That cell is an estimate. The pricing page and the image guide do not agree on a single output-token rate, and no pre-request token maximum was found. A local budget is not an OpenAI cap. The guard therefore refuses every paid call, including a call whose local budget is far above the published cell. No persistent authorization was written. The phase 4B.2.34.1 authorization is refused if it is presented again.

The pictorial prompt approved for The Door Already Open is unchanged. It asks for no title, no author name, and no barcode. The Cover Renderer would add type later. It does not run in this phase. Author biography stays MISSING_OPTIONAL. The book description stays NOT_STARTED.

STOP. Do not call the API, spend money, generate an image, download a model, or produce a cover until a verified per-image maximum exists and a separate explicit authorization is given.
"""


__all__ = ["build_documents"]
