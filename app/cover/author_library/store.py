"""Global author library, separate from any one book project."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.cover.constants import AUTHOR_LIBRARY_SCHEMA_VERSION
from app.cover.models.author import AuthorFact, AuthorProfile, PrivateContact


class AuthorLibraryError(ValueError):
    """Author library operation rejected."""


class AuthorLibrary:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.index_path = self.root / "index.json"
        self.private_dir = self.root / "private"
        self._authors: dict[str, AuthorProfile] = {}
        self._private: dict[str, PrivateContact] = {}
        self._attributions: list[dict[str, Any]] = []
        if self.index_path.exists():
            self._load()

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.private_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self.save()

    def create_author(
        self,
        *,
        display_name: str | None = None,
        biography_reference: str | None = None,
        public_website: str | None = None,
        author_photo_path: str | None = None,
    ) -> AuthorProfile:
        self.ensure()
        now = _now()
        profile = AuthorProfile(
            author_id=self._next_id(),
            display_name=display_name,
            biography_reference=biography_reference,
            public_website=public_website,
            author_photo_path=author_photo_path,
            verification_status="UNVERIFIED",
            created_at=now,
            updated_at=now,
        )
        self._authors[profile.author_id] = profile
        self.save()
        return profile

    def get(self, author_id: str) -> AuthorProfile:
        profile = self._authors.get(author_id)
        if profile is None:
            raise AuthorLibraryError(f"unknown author_id {author_id!r}")
        return profile

    def update_profile(self, profile: AuthorProfile) -> AuthorProfile:
        if profile.author_id not in self._authors:
            raise AuthorLibraryError(f"unknown author_id {profile.author_id!r}")
        profile.updated_at = _now()
        self._authors[profile.author_id] = profile
        self.save()
        return profile

    def add_fact(
        self,
        author_id: str,
        *,
        kind: str,
        text: str,
        verification_status: str = "PROVIDED",
        publication_status: str = "NOT_APPROVED",
    ) -> AuthorFact:
        profile = self.get(author_id)
        fact = AuthorFact(
            fact_id=f"{author_id}_fact_{len(profile.facts()) + 1:03d}",
            kind=kind,
            text=text,
            provenance="PROVIDED",
            verification_status=verification_status,
            publication_status=publication_status,
        )
        bucket = _bucket(profile, kind)
        bucket.append(fact)
        self.update_profile(profile)
        return fact

    def set_private_contact(self, author_id: str, contact: PrivateContact) -> None:
        self.get(author_id)
        self.ensure()
        self._private[author_id] = contact
        path = self.private_dir / f"{author_id}.json"
        path.write_text(
            json.dumps(
                {"author_id": author_id, "contact": contact.to_dict()},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def private_contact(self, author_id: str) -> PrivateContact | None:
        if author_id in self._private:
            return self._private[author_id]
        path = self.private_dir / f"{author_id}.json"
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        contact = PrivateContact.from_dict(payload.get("contact"))
        self._private[author_id] = contact
        return contact

    def link_project(
        self,
        *,
        project_id: str,
        author_id: str,
        role: str,
    ) -> dict[str, Any]:
        self.get(author_id)
        if role == "DEPOSITOR":
            raise AuthorLibraryError("a depositor link cannot be stored as an author role")
        record = {
            "project_id": project_id,
            "author_id": author_id,
            "role": role,
            "copied_profile": False,
        }
        self._attributions.append(record)
        self.save()
        return record

    def projects_for_author(self, author_id: str) -> list[str]:
        found: list[str] = []
        for item in self._attributions:
            if item.get("author_id") == author_id and item.get("project_id") not in found:
                found.append(str(item["project_id"]))
        return found

    def authors_for_project(self, project_id: str, *, role: str | None = None) -> list[str]:
        found: list[str] = []
        for item in self._attributions:
            if item.get("project_id") != project_id:
                continue
            if role is not None and item.get("role") != role:
                continue
            author_id = str(item.get("author_id") or "")
            if author_id and author_id not in found:
                found.append(author_id)
        return found

    def public_index(self) -> dict[str, Any]:
        return {
            "schema_version": AUTHOR_LIBRARY_SCHEMA_VERSION,
            "authors": {
                author_id: profile.to_public_dict()
                for author_id, profile in sorted(self._authors.items())
            },
            "attributions": list(self._attributions),
            "private_store": "private",
            "private_fields_included": False,
        }

    def save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.private_dir.mkdir(parents=True, exist_ok=True)
        payload = self.public_index()
        if _has_private_key(payload):
            raise AuthorLibraryError("refusing to write private contact fields into the public index")
        encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        self.index_path.write_text(encoded, encoding="utf-8")

    def _load(self) -> None:
        payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        authors = payload.get("authors") or {}
        self._authors = {
            key: AuthorProfile.from_public_dict(value)
            for key, value in authors.items()
            if isinstance(value, dict)
        }
        self._attributions = [
            dict(item) for item in payload.get("attributions") or [] if isinstance(item, dict)
        ]

    def _next_id(self) -> str:
        numbers = []
        for key in self._authors:
            if not key.startswith("author_"):
                continue
            try:
                numbers.append(int(key.split("_", 1)[1]))
            except ValueError:
                continue
        return f"author_{max(numbers, default=0) + 1:06d}"


def _bucket(profile: AuthorProfile, kind: str) -> list[AuthorFact]:
    if kind == "professional_background":
        return profile.professional_background
    if kind == "areas_of_expertise":
        return profile.areas_of_expertise
    if kind == "public_role":
        return profile.public_roles
    raise AuthorLibraryError(f"unsupported fact kind {kind!r}")


def _has_private_key(value: Any) -> bool:
    private = {"email", "phone", "management_contact"}
    if isinstance(value, dict):
        return any(key in private or _has_private_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_has_private_key(item) for item in value)
    return False


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


__all__ = ["AuthorLibrary", "AuthorLibraryError"]
