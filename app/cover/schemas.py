"""Declarative schemas exported to the phase audit."""

from __future__ import annotations

from typing import Any

from app.cover.constants import (
    ATTRIBUTION_ROLES,
    AUTHOR_LIBRARY_SCHEMA_VERSION,
    CONTENT_STATUSES,
    COVER_MODE,
    PUBLICATION_FACT_STATUSES,
    SCHEMA_VERSION,
    VERIFICATION_STATUSES,
)


def author_library_schema() -> dict[str, Any]:
    return {
        "schema_version": AUTHOR_LIBRARY_SCHEMA_VERSION,
        "storage": "data/author_library",
        "separated_from_project_files": True,
        "profile": {
            "author_id": "author_000001",
            "display_name": None,
            "biography_reference": None,
            "professional_background": [],
            "areas_of_expertise": [],
            "public_roles": [],
            "public_website": None,
            "author_photo_path": None,
            "name_publication_authorized": False,
            "photo_publication_authorized": False,
            "personal_details_publication_authorized": False,
            "verification_status": "UNVERIFIED",
            "created_at": None,
            "updated_at": None,
        },
        "fact": {
            "provenance": ["PROVIDED"],
            "verification_status": list(VERIFICATION_STATUSES),
            "publication_status": list(PUBLICATION_FACT_STATUSES),
            "unverified_cannot_be_approved": True,
        },
        "private_contact": {
            "stored_in": "data/author_library/private",
            "fields": ["email", "phone", "management_contact"],
            "copied_to_back_cover": False,
        },
        "roles": list(ATTRIBUTION_ROLES),
        "depositor_implies_author": False,
        "project_link_copies_profile": False,
        "published_cover_stores": "biography_snapshot",
        "central_profile_edits_rewrite_existing_covers": False,
        "production_profiles_seeded": False,
    }


def cover_schema() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "stored_apart_from_book_json": True,
        "manuscript_keys_forbidden": ["chapters", "paragraphs", "transcript"],
        "record": {
            "cover_id": None,
            "project_id": None,
            "book_version": "print-review-v1.1",
            "source_document_version": "print-review-v1",
            "cover_version": "draft-v1",
            "status": "DRAFT",
            "cover_mode": COVER_MODE,
            "wraparound": False,
            "spine_computed": False,
            "format": {
                "width_in": 6,
                "height_in": 9,
                "bleed_mm": 3,
                "safety_in": 0.25,
                "dpi": 300,
            },
            "front": {
                "background_image_path": None,
                "image_generation_id": None,
                "title": "resolved_from_book.title",
                "subtitle": "resolved_from_book.subtitle",
                "author_display_name": None,
                "text_baked_into_image": False,
            },
            "back": {
                "background_mode": "SOLID_COLOR",
                "background_color": None,
                "book_description": None,
                "author_biography": None,
            },
            "author_id": None,
            "biography_snapshot": None,
            "content_statuses": list(CONTENT_STATUSES),
            "export": {
                "front_docx": None,
                "front_pdf": None,
                "back_docx": None,
                "back_pdf": None,
            },
        },
    }


__all__ = ["author_library_schema", "cover_schema"]
