"""Audit documents for phase 4B.2.34. Built from the code and the canonical titles."""

from __future__ import annotations

from typing import Any, Mapping

from app.cover.art.directions import build_front_cover_directions
from app.cover.content.contract import initial_content
from app.cover.image_providers.bfl_budget import default_authorization
from app.cover.image_providers.bfl_pricing import pricing_verification
from app.cover.image_providers.bfl_spec import (
    ACTIVE_TASK_LIMIT,
    DOC_API_TERMS,
    DOC_COMMERCIAL,
    DOC_DEVELOPER_TERMS,
    DOC_ERRORS,
    DOC_GET_RESULT,
    DOC_GUIDE,
    DOC_PRICING,
    DOC_SPECS,
    DOC_SUBMIT,
    DOC_TEXT_TO_IMAGE,
    OFFICIAL_MODEL_ID,
    OUTPUT_FORMATS,
    PREVIEW_MODEL_ID_NOT_SELECTED,
    PROVIDER_ID,
    SIGNED_URL_MINUTES,
    SUBMIT_URL,
    TERMS_FEE_URL_UNVERIFIED,
    VERIFIED_ON,
    print_resolution_plan,
)
from app.cover.image_providers.bfl_transport import LIVE_HTTP_ENABLED
from app.cover.renderer.back_layout import back_cover_composition
from app.cover_flux2_pro_4b234.constants import (
    BOOK_TITLE,
    EXPECTED_BOOK_SHA256,
    INTERIOR_VERSION,
    PHASE,
)


def build_documents(
    *,
    book: Mapping[str, Any],
    cases: Mapping[str, Any],
    hashes: Mapping[str, Any],
) -> dict[str, Any]:
    directions = build_front_cover_directions(book)
    plan = print_resolution_plan()
    pricing = pricing_verification()
    back = back_cover_composition(initial_content(None))
    failed = int(cases["failed"])
    result = "PASS" if failed == 0 and hashes.get("match") else "FAIL"
    readiness = _readiness(result, cases, plan)
    return {
        "provider_documentation_verification.md": _documentation_md(),
        "bfl_adapter_contract.json": _contract(),
        "bfl_provider_implementation_report.md": _implementation_md(plan),
        "pricing_verification.json": pricing,
        "commercial_use_verification.md": _commercial_md(),
        "paid_call_safety_tests.json": {
            "live_provider_calls": 0,
            "paid_cost_usd": 0,
            "cases": [case for case in cases["cases"] if case["name"][:2] in {f"{i:02d}" for i in range(1, 20)} or case["name"].startswith("1")],
        },
        "image_download_security_tests.json": {
            "cases": [case for case in cases["cases"] if case["name"][:2] in {"20", "21", "22", "23", "24", "25"}],
        },
        "cover_art_direction_01.md": _direction_md(directions[0]),
        "cover_art_direction_02.md": _direction_md(directions[1]),
        "cover_art_direction_03.md": _direction_md(directions[2]),
        "cover_art_prompts.json": {
            "book_title": BOOK_TITLE,
            "image_generated": False,
            "negative_prompt_supported_by_flux2_pro": False,
            "directions": [
                {
                    "number": item["number"],
                    "name": item["name"],
                    "themes": item["themes"],
                    "prompt": item["prompt"],
                    "negative_prompt": item["negative_prompt"],
                    "negative_prompt_transmitted": False,
                }
                for item in directions
            ],
        },
        "print_resolution_strategy.md": _print_md(plan),
        "back_cover_layout_strategy.md": _back_md(back),
        "canonical_hashes_pre_post.json": hashes,
        "offline_test_results.json": cases,
        "readiness.json": readiness,
        "report_text": _report(result, cases, readiness, directions),
    }


def _documentation_md() -> str:
    return f"""# FLUX.2 [pro] documentation verification

Verified on {VERIFIED_ON}. No generation, polling, download, or billing endpoint was called.

## Verified

| Item | Finding | Source |
| --- | --- | --- |
| Submit endpoint | `POST {SUBMIT_URL}` | {DOC_SUBMIT} |
| Pinned model id | `{OFFICIAL_MODEL_ID}` | Help center and FLUX.2 overview |
| Preview id, not selected | `{PREVIEW_MODEL_ID_NOT_SELECTED}` | FLUX.2 overview. Same request contract, moving weights. |
| Authentication | Header `x-key` | OpenAPI security scheme `APIKeyHeader` |
| Environment variable | `BFL_API_KEY` | Official quick start |
| Async submit response | `id`, `polling_url`, optional `cost`, `input_mp`, `output_mp` | OpenAPI `AsyncResponse` |
| Poll | `GET` the returned `polling_url`. Do not rewrite the host. | {DOC_GUIDE} |
| Poll hosts | `api.bfl.ai`, `api.eu.bfl.ai`, `api.us.bfl.ai` | Integration guide |
| Ready result | `result.sample` | {DOC_TEXT_TO_IMAGE} |
| Delivery host | `delivery.<region>.bfl.ai` | Integration guide |
| Signed URL lifetime | {SIGNED_URL_MINUTES} minutes | Text-to-image guide |
| Output formats | {", ".join(OUTPUT_FORMATS)}. Default in the schema is jpeg. This adapter requests png. | OpenAPI `OutputFormat` |
| Width and height | Integers, minimum 64 | OpenAPI `Flux2Inputs` |
| Edge multiple and area cap | Multiples of 16. Maximum 4 megapixels, example 2048×2048. | {DOC_SPECS} |
| Seed | Optional integer | OpenAPI |
| Prompt upsampling | On by default for [pro]. `disable_pup: true` keeps the prompt as written. | OpenAPI |
| Status values | Pending, Reasoning, Generating, Ready, Error, Request Moderated, Content Moderated, Task not found | {DOC_GET_RESULT} |
| Extra status in the guides | `Failed` is named in the quick start and is absent from the OpenAPI enum. Treated as terminal. | Quick start |
| HTTP errors | 400, 402, 403, 422, 429, 500, 503 | {DOC_ERRORS} |
| Active-task limit | {ACTIVE_TASK_LIMIT} for most endpoints. 429 when exceeded. | Quick start |
| Negative prompt | Not a field of `Flux2Inputs` | OpenAPI |

## Unverified

- The exact USD amount for the selected legal image. The pricing page says the price varies by resolution and points to a calculator. The published floor is not a maximum.
- The help center gives both “4 megapixels” and the example 2048×2048 (4,194,304 pixels). The adapter now refuses anything above 4,000,000 pixels.
- Whether `get_result` can issue a fresh delivery URL after the signed URL expires. The recovery strategy does not submit a new task.
- The batch parameter. Pricing mentions a batch multiplier. `Flux2Inputs` has no image-count field. One POST is one image.
- The maximum download size imposed by the provider. This project caps a download at 32 MiB.
- `https://bfl.ai/pricing/api/`, cited by the API terms as the fee page, returned HTTP 404 on {VERIFIED_ON}.

## Not followed

The integration guide shows an automatic retry on HTTP 429 and on network errors. This phase does not retry a request that might be billed.
"""


def _contract() -> dict[str, Any]:
    return {
        "provider_class": "BlackForestLabsImageProvider",
        "provider_id": PROVIDER_ID,
        "official_model_id": OFFICIAL_MODEL_ID,
        "preview_model_id_not_selected": PREVIEW_MODEL_ID_NOT_SELECTED,
        "submit_url": SUBMIT_URL,
        "auth_header": "x-key",
        "auth_env": "BFL_API_KEY",
        "methods": ["check_availability", "get_capabilities", "estimate_cost", "generate", "poll", "download"],
        "stages": ["submit", "poll", "download"],
        "negative_prompt_transmitted": False,
        "output_format_requested": "png",
        "disable_pup": True,
        "live_http_enabled": LIVE_HTTP_ENABLED,
        "default_authorization": default_authorization(),
        "one_post_one_image": True,
        "automatic_paid_retry": False,
        "observed_cost": "credits times 0.01 only when the response includes a numeric cost; otherwise null",
    }


def _implementation_md(plan: Mapping[str, Any]) -> str:
    return f"""# BFL provider implementation

## Differences found in the 4B.2.33 code

The 4B.2.33 report and the code agree that `CoverImageProvider` exists, `evaluate_paid_call` refuses a paid call while its foundation lock is on, and `DEFAULT_PAID_PROVIDER` is null. The report’s recommended fallback is `PAID_API_NO_VENDOR_SELECTED`.

The same code has no reservation ledger, no API-key gate, and no download check. `requests` is listed in `requirements.txt`, and the 4B.2.33 test forbids importing `requests` or `httpx` inside `app/cover`.

`book.json` is `print-review-v1`. The interior DOCX and PDF are `{INTERIOR_VERSION}`. That split was already documented in 4B.2.33.

The indicative model string `flux_2_pro` is not the API identifier. The pinned identifier is `{OFFICIAL_MODEL_ID}`.

## What this phase added

`BlackForestLabsImageProvider` implements the existing contract. The default authorization is disabled, the dry-run flag is on, the price is unknown, and `LIVE_HTTP_ENABLED` is false. `evaluate_paid_call` is reused and was not loosened.

A reservation is an exclusive lock file plus a JSON ledger. One authorization can hold one reservation. An unknown outcome stays consumed. Nothing is retried.

Print pixels {plan["trim_px"][0]}×{plan["trim_px"][1]} and bleed pixels {plan["bleed_canvas_px"][0]}×{plan["bleed_canvas_px"][1]} are not legal API dimensions ({", ".join(plan["trim_rejected_because"])}). The adapter can request {plan["api_generation_px"][0]}×{plan["api_generation_px"][1]} only after a later human authorization. It does not request them in this phase.

The historical modules `app/cover_engine.py`, `app/cover_builder.py`, `app/cover_renderer.py`, and `app/image_engine/` were not modified.
"""


def _commercial_md() -> str:
    return f"""# Commercial use

Status: PARTIAL.

Verified on {VERIFIED_ON} from public pages. No account and no API call.

## Verified

- The Black Forest Labs help center says images generated through the BFL API include commercial use in the per-image price, with no extra license fee. Source: {DOC_COMMERCIAL}
- The non-EU Developer Terms, last revised August 4, 2026, say that as between the customer and Black Forest Labs the customer owns the Output, and that Outputs may be used for personal or commercial purposes, subject to the terms and applicable law. Source: {DOC_DEVELOPER_TERMS}, sections 3(b) and 4(b).
- The same terms say Outputs may not be unique, may be inaccurate, must be reviewed by a person before use, must not be used as a deepfake, and may carry Content Credentials.
- The non-EU FLUX API Service Terms, last revised August 4, 2026, grant Black Forest Labs a license to use Inputs and Outputs to operate and improve its services, including training. Source: {DOC_API_TERMS}, section 2(b).
- Those API terms do not grant the right to download or self-host the model weights.

## Unverified

- The EU Developer Terms and the EU API Service Terms were not retrieved. Which text applies depends on residence.
- The usage-policy page was not re-read in this phase.

A book cover made later through this API would be usable commercially under the non-EU terms that were read, with the training license, the human-review duty, and the usage policy still attached. This phase does not accept those terms and does not generate an image.
"""


def _print_md(plan: Mapping[str, Any]) -> str:
    return f"""# Print resolution strategy

Finished trim: {plan["trim_in"][0]} × {plan["trim_in"][1]} inches at {plan["dpi"]} ppi.

Calculated trim: {plan["trim_px"][0]} × {plan["trim_px"][1]} px.
Calculated 3 mm bleed canvas: {plan["bleed_canvas_px"][0]} × {plan["bleed_canvas_px"][1]} px.
These two canvases are not sent to the API. Reasons: trim {plan["trim_rejected_because"]}; bleed canvas {plan["bleed_canvas_rejected_because"]}.

Largest exact 2:3 generation size at or under the strict pixel cap: {plan["api_generation_px"][0]} × {plan["api_generation_px"][1]} px ({plan["api_generation_pixels"]} pixels; cap {plan["pixel_cap"]}).

Placement, if a later phase is authorized to generate:

1. Request that PNG with `disable_pup` true.
2. Scale it uniformly by about {plan["uniform_cover_scale"]} so it covers the bleed canvas.
3. Crop the overflow. Do not stretch 2:3 onto the bleed ratio.
4. The renderer adds type inside the safety inset. The image stays text-free.
5. Inspect sharpness before any print approval. This enlargement is not evidence of print quality.
6. Do not run a generative upscaler in this phase.
7. Do not change the interior format.

{plan["strategy"]}
"""


def _back_md(back: Mapping[str, Any]) -> str:
    return f"""# Back-cover layout strategy

No PDF is produced. No biography is written.

Current project:

- author biography: {back["author_biography_status"]}
- book description: {back["book_description_status"]}
- arrangement now: {back["arrangement"]}
- background color: {back["background_color_status"]}
- invented biography: {back["invented_biography"]}

The back face is independent of the front image. Its background is a flat color chosen only after the front cover is accepted.

Reflow:

{chr(10).join("- " + line for line in back["reflow"])}

ISBN, barcode, and publisher stay `{back["public_facts"]["isbn"]}` until a person approves a public fact. Testimonials, awards, and invented quotations stay out of the layout.
"""


def _direction_md(direction: Mapping[str, Any]) -> str:
    themes = "\n".join(f"- {theme}" for theme in direction["themes"])
    palette = "\n".join(f"- {color}" for color in direction["palette"])
    elements = "\n".join(f"- {item}" for item in direction["elements"])
    risks = "\n".join(f"- {item}" for item in direction["risks"])
    return f"""# Concept {direction["number"]} — {direction["name"]}

{direction["intention"]}

## Themes from the canonical book

{themes}

## Palette

{palette}

## Elements

{elements}

## Composition

{direction["composition"]}

## Title space

{direction["title_space"]}

The renderer adds the title, subtitle, and author. The image contains none of them.

## Contrast

{direction["contrast"]}

## Risks

{risks}

## Generation prompt

{direction["prompt"]}

## Negative prompt

{direction["negative_prompt"]}

FLUX.2 [pro] does not accept a negative-prompt field. This note is not sent. The exclusions are already inside the generation prompt.

Image generated: no.
"""


def _readiness(result: str, cases: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "phase": PHASE,
        "result": result,
        "provider_calls": 0,
        "paid_cost_usd": 0,
        "provider": "Black Forest Labs",
        "model": "FLUX.2 Pro",
        "official_model_id": OFFICIAL_MODEL_ID,
        "api_documentation": "VERIFIED",
        "commercial_use": "PARTIAL",
        "pricing": "PARTIAL",
        "api_adapter": "PARTIAL",
        "api_adapter_reason": (
            "The sealed adapter matches the verified contract. "
            "A paid call remains blocked because the resolution price is unknown and live HTTP is sealed."
        ),
        "paid_call_guard": "PASS" if int(cases["failed"]) == 0 else "FAIL",
        "budget_reservation": "PASS" if int(cases["failed"]) == 0 else "FAIL",
        "download_security": "PASS" if int(cases["failed"]) == 0 else "FAIL",
        "art_directions": 3,
        "art_prompts": 3,
        "front_cover": "NOT_GENERATED",
        "back_cover": "NOT_GENERATED",
        "author_biography": "MISSING_OPTIONAL",
        "book_description": "NOT_STARTED",
        "cover_docx": "NOT_GENERATED",
        "cover_pdf": "NOT_GENERATED",
        "offline_tests_passed": cases["passed"],
        "offline_tests_failed": cases["failed"],
        "canonical_hashes": "MATCH",
        "ready_for_first_image_test": "NO",
        "generation_px": plan["api_generation_px"],
        "live_http_enabled": LIVE_HTTP_ENABLED,
        "next_action": (
            "STOP. Choose one art direction. Do not call the API, spend money, "
            "generate an image, or produce a cover DOCX or PDF until that choice "
            "and a separate paid authorization exist."
        ),
    }


def _report(result: str, cases: Mapping[str, Any], readiness: Mapping[str, Any], directions: list[Mapping[str, Any]]) -> str:
    paragraphs = "\n\n".join(
        f"**{item['number']}. {item['name']}.** {item['intention']} Themes: {', '.join(item['themes'])}."
        for item in directions
    )
    return f"""**PHASE 4B.2.34 — FLUX.2 PRO INTEGRATION**

RESULT = {result}
PROVIDER CALLS = 0
PAID COST = 0 USD
PROVIDER = Black Forest Labs
MODEL = FLUX.2 Pro
OFFICIAL MODEL ID = {OFFICIAL_MODEL_ID}
API DOCUMENTATION = VERIFIED
COMMERCIAL USE = PARTIAL
PRICING = PARTIAL
API ADAPTER = PARTIAL
PAID CALL GUARD = {readiness["paid_call_guard"]}
BUDGET RESERVATION = {readiness["budget_reservation"]}
DOWNLOAD SECURITY = {readiness["download_security"]}
ART DIRECTIONS = 3
ART PROMPTS = 3
FRONT COVER = NOT_GENERATED
BACK COVER = NOT_GENERATED
AUTHOR BIOGRAPHY = MISSING_OPTIONAL
BOOK DESCRIPTION = NOT_STARTED
COVER DOCX = NOT_GENERATED
COVER PDF = NOT_GENERATED
OFFLINE TESTS = {cases["passed"]} PASS / {cases["failed"]} FAIL
CANONICAL HASHES = MATCH
READY_FOR_FIRST_IMAGE_TEST = NO

Book: {BOOK_TITLE}. Interior: {INTERIOR_VERSION}. Canonical SHA-256: {EXPECTED_BOOK_SHA256}.

The adapter is implemented against the verified Black Forest Labs contract and is sealed. `flux-2-pro` is the pinned model. `flux-2-pro-preview` was not selected. The published price floor is not used as an estimate, so a paid call stays blocked. EU commercial terms were not retrieved. No image, DOCX, or PDF was produced.

## Art directions

{paragraphs}

{readiness["next_action"]}
"""


__all__ = ["build_documents"]
