"""Reusable author profile. Public facts stay separate from private contact data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.cover.models.statuses import (
    require_publication_status,
    require_verification_status,
)


@dataclass
class AuthorFact:
    fact_id: str
    kind: str
    text: str
    provenance: str = "PROVIDED"
    verification_status: str = "UNVERIFIED"
    publication_status: str = "NOT_APPROVED"

    def __post_init__(self) -> None:
        self.fact_id = str(self.fact_id or "").strip()
        self.kind = str(self.kind or "").strip()
        self.text = str(self.text or "").strip()
        self.provenance = str(self.provenance or "PROVIDED").strip() or "PROVIDED"
        self.verification_status = require_verification_status(self.verification_status)
        self.publication_status = require_publication_status(self.publication_status)
        if not self.fact_id or not self.kind or not self.text:
            raise ValueError("an author fact needs an id, a kind, and text")
        if self.publication_status == "APPROVED_FOR_PUBLICATION" and self.verification_status == "UNVERIFIED":
            raise ValueError("an unverified fact cannot be approved for publication")

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "kind": self.kind,
            "text": self.text,
            "provenance": self.provenance,
            "verification_status": self.verification_status,
            "publication_status": self.publication_status,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AuthorFact:
        return cls(
            fact_id=str(payload.get("fact_id") or ""),
            kind=str(payload.get("kind") or ""),
            text=str(payload.get("text") or ""),
            provenance=str(payload.get("provenance") or "PROVIDED"),
            verification_status=str(payload.get("verification_status") or "UNVERIFIED"),
            publication_status=str(payload.get("publication_status") or "NOT_APPROVED"),
        )


@dataclass
class PrivateContact:
    """Internal contact data. Never copied onto a cover."""

    email: str | None = None
    phone: str | None = None
    management_contact: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "email": self.email,
            "phone": self.phone,
            "management_contact": self.management_contact,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> PrivateContact:
        payload = payload or {}
        return cls(
            email=_optional_text(payload.get("email")),
            phone=_optional_text(payload.get("phone")),
            management_contact=_optional_text(payload.get("management_contact")),
        )


@dataclass
class AuthorProfile:
    author_id: str
    display_name: str | None = None
    biography_reference: str | None = None
    professional_background: list[AuthorFact] = field(default_factory=list)
    areas_of_expertise: list[AuthorFact] = field(default_factory=list)
    public_roles: list[AuthorFact] = field(default_factory=list)
    public_website: str | None = None
    author_photo_path: str | None = None
    name_publication_authorized: bool = False
    photo_publication_authorized: bool = False
    personal_details_publication_authorized: bool = False
    verification_status: str = "UNVERIFIED"
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        self.author_id = str(self.author_id or "").strip()
        self.display_name = _optional_text(self.display_name)
        self.biography_reference = _optional_text(self.biography_reference)
        self.public_website = _optional_text(self.public_website)
        self.author_photo_path = _optional_text(self.author_photo_path)
        self.verification_status = require_verification_status(self.verification_status)
        if not self.author_id:
            raise ValueError("author_id is required")

    def facts(self) -> tuple[AuthorFact, ...]:
        return tuple(self.professional_background + self.areas_of_expertise + self.public_roles)

    def approved_facts(self) -> tuple[AuthorFact, ...]:
        return tuple(
            fact
            for fact in self.facts()
            if fact.publication_status == "APPROVED_FOR_PUBLICATION"
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "author_id": self.author_id,
            "display_name": self.display_name,
            "biography_reference": self.biography_reference,
            "professional_background": [fact.to_dict() for fact in self.professional_background],
            "areas_of_expertise": [fact.to_dict() for fact in self.areas_of_expertise],
            "public_roles": [fact.to_dict() for fact in self.public_roles],
            "public_website": self.public_website,
            "author_photo_path": self.author_photo_path,
            "name_publication_authorized": self.name_publication_authorized,
            "photo_publication_authorized": self.photo_publication_authorized,
            "personal_details_publication_authorized": self.personal_details_publication_authorized,
            "verification_status": self.verification_status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_public_dict(cls, payload: dict[str, Any]) -> AuthorProfile:
        return cls(
            author_id=str(payload.get("author_id") or ""),
            display_name=_optional_text(payload.get("display_name")),
            biography_reference=_optional_text(payload.get("biography_reference")),
            professional_background=[
                AuthorFact.from_dict(item)
                for item in payload.get("professional_background") or []
                if isinstance(item, dict)
            ],
            areas_of_expertise=[
                AuthorFact.from_dict(item)
                for item in payload.get("areas_of_expertise") or []
                if isinstance(item, dict)
            ],
            public_roles=[
                AuthorFact.from_dict(item)
                for item in payload.get("public_roles") or []
                if isinstance(item, dict)
            ],
            public_website=_optional_text(payload.get("public_website")),
            author_photo_path=_optional_text(payload.get("author_photo_path")),
            name_publication_authorized=bool(payload.get("name_publication_authorized")),
            photo_publication_authorized=bool(payload.get("photo_publication_authorized")),
            personal_details_publication_authorized=bool(
                payload.get("personal_details_publication_authorized")
            ),
            verification_status=str(payload.get("verification_status") or "UNVERIFIED"),
            created_at=_optional_text(payload.get("created_at")),
            updated_at=_optional_text(payload.get("updated_at")),
        )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = ["AuthorFact", "AuthorProfile", "PrivateContact"]
