"""Phase 4B.2.34.3 constants. Offline. Zero USD. No image."""

from __future__ import annotations

from app.cover_gpt_image_2_4b2342.constants import (
    ART_DIRECTION,
    BOOK_TITLE,
    EXPECTED_BOOK_SHA256,
    EXPECTED_INTERIOR_DOCX_SHA256,
    EXPECTED_INTERIOR_PDF_SHA256,
    INTERIOR_VERSION,
    PROJECT_NAME,
)
from app.cover_generator_foundation_4b233.constants import INTERIOR_PDF_PAGES

PHASE = "4B.2.34.3"
PHASE_NAME = "IMAGE_BUDGET_POLICY"
AUTHORIZATION_SCOPE = "COVER_BUDGET_POLICY_4B2343_OFFLINE_ONLY"
AUDIT_DIRNAME = "cover_generator_budget_policy_4b2343"
REPORT_NAME = "PHASE_4B2343_IMAGE_BUDGET_POLICY_REPORT.md"

assert PROJECT_NAME == "pastoral_retreat_v2_validation"
assert BOOK_TITLE == "The Life You Already Inherited"
assert ART_DIRECTION == "The Door Already Open"
assert INTERIOR_VERSION == "print-review-v1.1"
assert INTERIOR_PDF_PAGES == 67
assert EXPECTED_BOOK_SHA256 == (
    "adde6e2344f4b94da0f7df183341885574e89abc90781c426459e850cc2b6550"
)

__all__ = [
    "ART_DIRECTION",
    "AUDIT_DIRNAME",
    "AUTHORIZATION_SCOPE",
    "BOOK_TITLE",
    "EXPECTED_BOOK_SHA256",
    "EXPECTED_INTERIOR_DOCX_SHA256",
    "EXPECTED_INTERIOR_PDF_SHA256",
    "INTERIOR_PDF_PAGES",
    "INTERIOR_VERSION",
    "PHASE",
    "PHASE_NAME",
    "PROJECT_NAME",
    "REPORT_NAME",
]
