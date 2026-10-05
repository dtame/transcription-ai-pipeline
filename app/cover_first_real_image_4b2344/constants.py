"""Phase 4B.2.34.4. One experimental image. The module constant stays sealed."""

from __future__ import annotations

from app.cover.image_providers.budget_policy import EXPERIMENTAL_SUBMISSION_ENABLED
from app.cover.image_providers.openai_art import PROMPT, prompt_record
from app.cover.image_providers.openai_spec import (
    OFFICIAL_MODEL_ID,
    PROVIDER_ID,
    REQUESTED_OUTPUT_FORMAT,
    REQUESTED_QUALITY,
    SELECTED_HEIGHT,
    SELECTED_WIDTH,
    published_image_output_estimate_usd,
)
from app.cover_generator_foundation_4b233.constants import (
    BOOK_TITLE,
    EXPECTED_BOOK_SHA256,
    EXPECTED_INTERIOR_DOCX_SHA256,
    EXPECTED_INTERIOR_PDF_SHA256,
    INTERIOR_PDF_PAGES,
    INTERIOR_VERSION,
    PROJECT_NAME,
)

PHASE = "4B.2.34.4"
PHASE_NAME = "FIRST_REAL_COVER_IMAGE"
AUDIT_DIRNAME = "cover_first_real_image_4b2344"
REPORT_NAME = "PHASE_4B2344_FIRST_REAL_IMAGE_REPORT.md"
AUTHORIZATION_SCOPE = "COVER_FIRST_REAL_IMAGE_4B2344_SINGLE_USE"
ART_DIRECTION = "The Door Already Open"
IMAGE_NAME = "front_the_door_already_open_gpt_image_2_test_001.png"
PLANNING_BUDGET_USD = "0.10"
EXPECTED_PROMPT_SHA256 = "82f92129ec2d67666f288491c5d1b225272c46e6ec30f4f0daadaeef06cc3194"
EXPECTED_WORD_PROFILE_SHA256 = "0124ece6b2639c84784d9f09a48514323ab56d2c85e3779226d1d4959ff46818"
EXPECTED_IMAGE_OUTPUT_CELL_USD = "0.041"
LIVE_TIMEOUT_SECONDS = 240.0
AUTHORIZATION_TTL_HOURS = 2

USER_AUTHORIZATION_STATEMENT = (
    "J'autorise 1 génération expérimentale avec GPT Image 2, en 1024 × 1536, "
    "qualité medium, pour The Door Already Open. J'accepte que 0,10 USD soit "
    "un budget de planification et non un plafond de facturation garanti par OpenAI."
)

assert PROJECT_NAME == "pastoral_retreat_v2_validation"
assert BOOK_TITLE == "The Life You Already Inherited"
assert ART_DIRECTION == "The Door Already Open"
assert INTERIOR_VERSION == "print-review-v1.1"
assert INTERIOR_PDF_PAGES == 67
assert EXPECTED_BOOK_SHA256 == (
    "adde6e2344f4b94da0f7df183341885574e89abc90781c426459e850cc2b6550"
)
assert PROVIDER_ID == "openai"
assert OFFICIAL_MODEL_ID == "gpt-image-2"
assert SELECTED_WIDTH == 1024
assert SELECTED_HEIGHT == 1536
assert REQUESTED_QUALITY == "medium"
assert REQUESTED_OUTPUT_FORMAT == "png"
assert EXPERIMENTAL_SUBMISSION_ENABLED is False
assert prompt_record()["prompt_sha256"] == EXPECTED_PROMPT_SHA256
assert published_image_output_estimate_usd(1024, 1536, "medium") == EXPECTED_IMAGE_OUTPUT_CELL_USD
assert "The Life You Already Inherited" not in PROMPT

__all__ = [
    "ART_DIRECTION",
    "AUDIT_DIRNAME",
    "AUTHORIZATION_SCOPE",
    "AUTHORIZATION_TTL_HOURS",
    "BOOK_TITLE",
    "EXPECTED_BOOK_SHA256",
    "EXPECTED_IMAGE_OUTPUT_CELL_USD",
    "EXPECTED_INTERIOR_DOCX_SHA256",
    "EXPECTED_INTERIOR_PDF_SHA256",
    "EXPECTED_PROMPT_SHA256",
    "EXPECTED_WORD_PROFILE_SHA256",
    "IMAGE_NAME",
    "INTERIOR_PDF_PAGES",
    "INTERIOR_VERSION",
    "LIVE_TIMEOUT_SECONDS",
    "PHASE",
    "PHASE_NAME",
    "PLANNING_BUDGET_USD",
    "PROJECT_NAME",
    "REPORT_NAME",
    "USER_AUTHORIZATION_STATEMENT",
]
