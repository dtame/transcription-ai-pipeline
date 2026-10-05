"""Spiritual revision of The Door Already Open.

The name stays. The picture does not illustrate a household door.
This module does not contact a provider.
"""

from __future__ import annotations

import hashlib
from typing import Any

ART_DIRECTION = "The Door Already Open — Spiritual Interpretation"
CONCEPT_NAME = "The Door Already Open"
PREVIOUS_ART_DIRECTION = "The Door Already Open"

PROMPT = (
    "Create a premium vertical book-cover background that communicates spiritual access "
    "to a reality already given, rather than achievement or striving. "
    'The concept "The Door Already Open" is metaphorical. '
    "Do not depict a literal household door, room, hallway, or domestic interior. "
    "Use light, depth, atmosphere and a sense of revelation to suggest that an unseen "
    "spiritual reality is already accessible. "
    "The scene should feel contemplative, powerful, peaceful and spiritually significant "
    "without relying on obvious religious clichés. "
    "Access rather than achievement. "
    "Editorial cinematic photograph, vertical two-to-three ratio, refined photographic realism, "
    "premium publishing quality. "
    "A vast natural landscape of quiet depth: layered mist, distant ridges, and cloud, "
    "with an extraordinary luminous opening beyond the visible weather, as if a higher reality "
    "is already present and can be entered without conquest. "
    "The light feels like a revelation already given, not a prize to be won. "
    "Foreground shadow is still and deep. The distance is already illuminated, drawing the eye "
    "forward into peace, hope, presence, and a destiny that has already been prepared. "
    "Credible atmosphere, subtle supernatural quality, strong depth, elegant and sophisticated. "
    "Not a tourist landscape photograph. Not a fantasy illustration. "
    "Leave the upper area of the vertical frame visually quiet, with open sky, mist, or soft "
    "shadow and enough tonal contrast for a title to be added later by a separate cover process. "
    "Do not crowd fine detail into that upper zone. The composition must remain strong if type "
    "is placed over it afterward. "
    "No text. No letters. No words. No title. No subtitle. No author name. No typography. "
    "No logo. No ISBN. No barcode. No watermark. No signature. No numerals. "
    "No giant cross, no floating Bible, no visible angel, no physical depiction of Jesus, "
    "no stairway to heaven, no fantasy portal, no magic circle, no occult symbol, "
    "no fantasy temple, no winged figure, no giant hand in the sky, no artificially glowing dove, "
    "no household door, no architectural door as the subject, no person opening a door, "
    "no people, no human figures, no faces, no church interior, no stained glass, no halo, "
    "no crowd, no celebrity face."
)


def prompt_sha256() -> str:
    return hashlib.sha256(PROMPT.encode("utf-8")).hexdigest()


def prompt_record() -> dict[str, Any]:
    return {
        "art_direction": ART_DIRECTION,
        "concept_name": CONCEPT_NAME,
        "interpretation": "spiritual_metaphor",
        "literal_door_depiction": False,
        "previous_art_direction": PREVIOUS_ART_DIRECTION,
        "previous_prompt_reused": False,
        "prompt": PROMPT,
        "prompt_sha256": prompt_sha256(),
        "prompt_characters": len(PROMPT),
        "language": "en",
        "embed_text": False,
        "title_rendered_in_image": False,
        "title_space": (
            "Upper area kept visually quiet, with mist, sky, or soft shadow, "
            "so a later cover process can place the title."
        ),
    }


__all__ = [
    "ART_DIRECTION",
    "CONCEPT_NAME",
    "PREVIOUS_ART_DIRECTION",
    "PROMPT",
    "prompt_record",
    "prompt_sha256",
]
