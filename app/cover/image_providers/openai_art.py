"""The Door Already Open, prepared for gpt-image-2.

The pictorial sentences are the prompt approved in phase 4B.2.34.1.
Size, quality, format, and background are API fields, not extra picture language.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.cover.image_providers.openai_spec import (
    OFFICIAL_MODEL_ID,
    PROVIDER_ID,
    REQUESTED_BACKGROUND,
    REQUESTED_OUTPUT_FORMAT,
    REQUESTED_QUALITY,
    SELECTED_HEIGHT,
    SELECTED_WIDTH,
)

ART_DIRECTION = "The Door Already Open"
SOURCE_PHASE = "4B.2.34"

PROMPT = (
    "Editorial photograph for a book cover, vertical two-to-three ratio. "
    "A plain domestic doorway already standing open, warm dawn light already "
    "inside the room, a small oil lamp already burning on a walnut table. "
    "Upper third is an even plaster wall in exact color #E7D7C1 with no objects "
    "and no texture that resembles writing. Flame in #E0A15A, shadows in #3E4A3A. "
    "Photographed, calm, sharp, no people. no words, no letters, no numerals, "
    "no title, no subtitle, no author name, no logo, no barcode, no ISBN, "
    "no watermark, no signature, no cross, no crucifix, no stained glass, "
    "no halo, no angel, no church interior, no crowd, no celebrity face, "
    "no skeleton, no open tomb."
)

FORBIDDEN_RENDERED_TEXT = (
    "title",
    "subtitle",
    "author name",
    "logo",
    "watermark",
    "ISBN",
    "barcode",
)


def prompt_record() -> dict[str, Any]:
    digest = hashlib.sha256(PROMPT.encode("utf-8")).hexdigest()
    return {
        "art_direction": ART_DIRECTION,
        "source_direction_name": "The door already open",
        "source_phase": SOURCE_PHASE,
        "provider_id": PROVIDER_ID,
        "model_id": OFFICIAL_MODEL_ID,
        "prompt_text_changed": False,
        "prompt": PROMPT,
        "prompt_sha256": digest,
        "prompt_characters": len(PROMPT),
        "language": "en",
        "negative_prompt_transmitted": False,
        "embed_text": False,
        "rendered_text_forbidden": list(FORBIDDEN_RENDERED_TEXT),
        "title_space": "Upper third, low detail, #E7D7C1, dark type to be added by the renderer.",
        "width": SELECTED_WIDTH,
        "height": SELECTED_HEIGHT,
        "quality": REQUESTED_QUALITY,
        "output_format": REQUESTED_OUTPUT_FORMAT,
        "background": REQUESTED_BACKGROUND,
        "reference_images": [],
        "technical_adjustments": [
            "The approved pictorial prompt is unchanged.",
            "Width, height, quality, format, and background are Images API fields.",
            "disable_pup is a Black Forest Labs field and is not sent.",
            "No reference image is attached.",
            "The Cover Renderer adds the title later.",
        ],
        "image_generated": False,
    }


__all__ = ["ART_DIRECTION", "PROMPT", "prompt_record"]
