"""Public cover fields never receive private contact data or an unauthorized photo."""

from __future__ import annotations

from typing import Any

from app.cover.models.author import AuthorProfile, PrivateContact

PRIVATE_KEYS = ("email", "phone", "management_contact")


def public_author_block(profile: AuthorProfile | None) -> dict[str, Any]:
    if profile is None:
        return {
            "author_id": None,
            "display_name": None,
            "photo_path": None,
            "website": None,
        }
    return {
        "author_id": profile.author_id,
        "display_name": profile.display_name if profile.name_publication_authorized else None,
        "photo_path": profile.author_photo_path if profile.photo_publication_authorized else None,
        "website": (
            profile.public_website if profile.personal_details_publication_authorized else None
        ),
    }


def back_cover_author_fields(
    profile: AuthorProfile | None,
    contact: PrivateContact | None = None,
) -> dict[str, Any]:
    del contact
    block = public_author_block(profile)
    for key in PRIVATE_KEYS:
        if key in block:
            raise RuntimeError(f"private field {key} reached the back-cover block")
    block["private_contact_injected"] = False
    return block


def public_payload_contains_private(payload: dict[str, Any]) -> bool:
    return _contains_private_key(payload)


def _contains_private_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key in PRIVATE_KEYS or _contains_private_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_private_key(item) for item in value)
    return False


__all__ = [
    "PRIVATE_KEYS",
    "back_cover_author_fields",
    "public_author_block",
    "public_payload_contains_private",
]
