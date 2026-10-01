"""
Politique de langue du livre / du plan éditorial — recommandation générique.

Ce module ne mute pas editorial-planner-1.0. Il n'appelle aucun provider.
Il ne suppose pas qu'une langue source égale la langue du livre.

Les codes de langue sont normalisés, jamais imposés (pas d'anglais ou de
français figé comme défaut mondial).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.editorial_planning.errors import DocumentLanguageBlocked

LANGUAGE_POLICY_VERSION = "editorial-planner-language-policy-1.0"
DOCUMENT_LANGUAGE_POLICY_VERSION = "canonical-document-language-policy-1.0"
DOCUMENT_LANGUAGE_POLICY = "TRANSCRIPTION_DERIVED_PRIMARY_LANGUAGE"
SUCCESSOR_PROMPT_VERSION = "editorial-planner-1.0.1"
ACTIVE_PROMPT_VERSION = "editorial-planner-1.0"

UNRESOLVED_LANGUAGE_TOKENS = frozenset(
    {
        "",
        "unknown",
        "und",
        "undetermined",
        "unresolved",
        "none",
        "null",
        "n/a",
        "na",
        "??",
        "zxx",
    }
)

FIELD_TRANSCRIPT_PRIMARY = "transcript.language.primary"
FIELD_SOURCE_MAP_PRIMARY = "source_map.language.primary"

STATUS_RESOLVED = "RESOLVED"
STATUS_BLOCKED_UNKNOWN = "BLOCKED_UNKNOWN"
STATUS_BLOCKED_MISMATCH = "BLOCKED_MISMATCH"

CONCEPT_SOURCE_PRIMARY = "SOURCE_PRIMARY_LANGUAGE"
CONCEPT_AUTHOR_ORIGINAL = "AUTHOR_ORIGINAL_LANGUAGE"
CONCEPT_EDITORIAL_PLANNING = "EDITORIAL_PLANNING_LANGUAGE"
CONCEPT_FINAL_BOOK = "FINAL_BOOK_LANGUAGE"
CONCEPT_UI_PROJECT = "UI_PROJECT_LANGUAGE"
CONCEPT_PROMPT_INSTRUCTION = "PROMPT_INSTRUCTION_LANGUAGE"

LANGUAGE_CONCEPTS = (
    CONCEPT_SOURCE_PRIMARY,
    CONCEPT_AUTHOR_ORIGINAL,
    CONCEPT_EDITORIAL_PLANNING,
    CONCEPT_FINAL_BOOK,
    CONCEPT_UI_PROJECT,
    CONCEPT_PROMPT_INSTRUCTION,
)

STATUS_EXPLICIT_BOOK = "EXPLICIT_BOOK_LANGUAGE"
STATUS_INHERITED_SOURCE = "INHERITED_SOURCE_PRIMARY"
STATUS_INHERITED_PROJECT = "INHERITED_PROJECT_LANGUAGE"
STATUS_UNRESOLVED = "UNRESOLVED_REQUIRES_HUMAN_DECISION"

INHERIT_REQUIRE_EXPLICIT = "require_explicit"
INHERIT_SOURCE = "inherit_source"
INHERIT_PROJECT = "inherit_project"
INHERIT_MODES = (INHERIT_REQUIRE_EXPLICIT, INHERIT_SOURCE, INHERIT_PROJECT)

RECOMMENDED_ALIGNMENT = "PLAN_LANGUAGE_MUST_MATCH_BOOK_LANGUAGE"
RECOMMENDED_DEFAULT_MODE = INHERIT_REQUIRE_EXPLICIT
RECOMMENDED_SETTING_NAME = "book_language"
SETTING_ALIASES = ("book_language", "output_language")

CONTRACT_UNSPECIFIED = "UNSPECIFIED_POLICY"
CONTRACT_VIOLATION = "EXPLICIT_CONTRACT_VIOLATION"
CONTRACT_ALLOWED = "EXPLICITLY_ALLOWED"
CONTRACT_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"


def normalize_language_code(value: str | None) -> str:
    """Lowercase BCP-like tag. Empty if absent. No global language default."""
    return str(value or "").strip().lower()


def languages_differ(left: str | None, right: str | None) -> bool:
    a = normalize_language_code(left)
    b = normalize_language_code(right)
    return bool(a and b and a != b)


def is_unresolved_language(value: str | None) -> bool:
    return normalize_language_code(value) in UNRESOLVED_LANGUAGE_TOKENS


@dataclass(frozen=True)
class LanguageResolution:
    book_language: str
    status: str
    source: str
    requires_human_decision: bool
    source_primary_language: str
    project_language: str
    requested_book_language: str
    inherit_mode: str
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_version": LANGUAGE_POLICY_VERSION,
            "book_language": self.book_language,
            "status": self.status,
            "source": self.source,
            "requires_human_decision": self.requires_human_decision,
            "source_primary_language": self.source_primary_language,
            "project_language": self.project_language,
            "requested_book_language": self.requested_book_language,
            "inherit_mode": self.inherit_mode,
            "recommended_alignment": RECOMMENDED_ALIGNMENT,
            "recommended_setting": RECOMMENDED_SETTING_NAME,
            "notes": list(self.notes),
        }


def resolve_book_language(
    *,
    book_language: str | None = None,
    project_language: str | None = None,
    source_primary_language: str | None = None,
    inherit_missing: str = RECOMMENDED_DEFAULT_MODE,
) -> LanguageResolution:
    """
    Résolution déterministe.

    1. book_language explicite gagne toujours.
    2. Sinon, inherit_missing choisit le repli — jamais une langue figée.
    """
    requested = normalize_language_code(book_language)
    project = normalize_language_code(project_language)
    source = normalize_language_code(source_primary_language)
    mode = str(inherit_missing or RECOMMENDED_DEFAULT_MODE).strip()
    if mode not in INHERIT_MODES:
        raise ValueError(f"inherit_missing inconnu : {mode!r}")

    notes: list[str] = []
    if requested:
        if languages_differ(requested, source):
            notes.append(
                "book_language differs from SourceMap.primary_language; "
                "that is allowed when explicit."
            )
        return LanguageResolution(
            book_language=requested,
            status=STATUS_EXPLICIT_BOOK,
            source="book_language",
            requires_human_decision=False,
            source_primary_language=source,
            project_language=project,
            requested_book_language=requested,
            inherit_mode=mode,
            notes=tuple(notes),
        )

    if mode == INHERIT_PROJECT and project:
        notes.append("No explicit book_language; inherited project language.")
        return LanguageResolution(
            book_language=project,
            status=STATUS_INHERITED_PROJECT,
            source="project_language",
            requires_human_decision=False,
            source_primary_language=source,
            project_language=project,
            requested_book_language="",
            inherit_mode=mode,
            notes=tuple(notes),
        )

    if mode == INHERIT_SOURCE and source:
        notes.append(
            "No explicit book_language; inherited SourceMap.primary_language. "
            "This must not be assumed to equal the final book language unless "
            "the project accepts that default."
        )
        return LanguageResolution(
            book_language=source,
            status=STATUS_INHERITED_SOURCE,
            source="source_primary_language",
            requires_human_decision=False,
            source_primary_language=source,
            project_language=project,
            requested_book_language="",
            inherit_mode=mode,
            notes=tuple(notes),
        )

    notes.append(
        "No explicit book_language. Recommended default is to require a "
        "project-level book_language before Editorial Planner, rather than "
        "assuming SourceMap.primary_language is the book language."
    )
    return LanguageResolution(
        book_language="",
        status=STATUS_UNRESOLVED,
        source="",
        requires_human_decision=True,
        source_primary_language=source,
        project_language=project,
        requested_book_language="",
        inherit_mode=mode,
        notes=tuple(notes),
    )


@dataclass(frozen=True)
class DocumentLanguageResolution:
    canonical_document_language: str
    status: str
    blocked: bool
    source: str
    policy: str
    transcript_primary_language: str
    source_map_primary_language: str
    observed_fields: tuple[tuple[str, str], ...] = ()
    notes: tuple[str, ...] = ()

    def require(self) -> str:
        if self.blocked or not self.canonical_document_language:
            raise DocumentLanguageBlocked(
                f"Canonical document language blocked ({self.status}): "
                + "; ".join(self.notes)
            )
        return self.canonical_document_language

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_version": DOCUMENT_LANGUAGE_POLICY_VERSION,
            "policy": self.policy,
            "canonical_document_language": self.canonical_document_language,
            "status": self.status,
            "blocked": self.blocked,
            "source": self.source,
            "transcript_primary_language": self.transcript_primary_language,
            "source_map_primary_language": self.source_map_primary_language,
            "observed_fields": [
                {"field": name, "value": value} for name, value in self.observed_fields
            ],
            "notes": list(self.notes),
            "translation_during_source_generation": False,
        }


def resolve_document_language(
    *,
    transcript_primary_language: str | None = None,
    source_map_primary_language: str | None = None,
    extra_validated_languages: Mapping[str, str] | None = None,
) -> DocumentLanguageResolution:
    """
    Langue documentaire canonique = langue principale validée de la transcription.

    Aucun défaut anglais/français. Aucun choix laissé au provider.
    """
    transcript = normalize_language_code(transcript_primary_language)
    source_map = normalize_language_code(source_map_primary_language)
    extras = {
        str(name): normalize_language_code(value)
        for name, value in dict(extra_validated_languages or {}).items()
    }
    observed: list[tuple[str, str]] = []
    if transcript_primary_language is not None:
        observed.append((FIELD_TRANSCRIPT_PRIMARY, transcript))
    if source_map_primary_language is not None:
        observed.append((FIELD_SOURCE_MAP_PRIMARY, source_map))
    for name, value in extras.items():
        observed.append((str(name), value))

    present = [
        (name, value)
        for name, value in observed
        if value and not is_unresolved_language(value)
    ]
    if not present:
        notes = (
            "Canonical document language could not be resolved from validated "
            "transcription-derived metadata. Planner is blocked. No silent "
            "English or French default.",
        )
        return DocumentLanguageResolution(
            canonical_document_language="",
            status=STATUS_BLOCKED_UNKNOWN,
            blocked=True,
            source="",
            policy=DOCUMENT_LANGUAGE_POLICY,
            transcript_primary_language=transcript,
            source_map_primary_language=source_map,
            observed_fields=tuple(observed),
            notes=notes,
        )

    unique = {value for _name, value in present}
    if len(unique) > 1:
        detail = ", ".join(f"{name}={value}" for name, value in present)
        notes = (
            "Validated upstream language fields disagree. Planner is blocked "
            f"before provider choice: {detail}.",
        )
        return DocumentLanguageResolution(
            canonical_document_language="",
            status=STATUS_BLOCKED_MISMATCH,
            blocked=True,
            source="",
            policy=DOCUMENT_LANGUAGE_POLICY,
            transcript_primary_language=transcript,
            source_map_primary_language=source_map,
            observed_fields=tuple(observed),
            notes=notes,
        )

    language = next(iter(unique))
    sources = tuple(name for name, value in present if value == language)
    notes = (
        "Canonical document language is the validated primary language "
        "derived from transcription. Source-document generation preserves "
        "this language. Translation is a later, explicit stage.",
    )
    return DocumentLanguageResolution(
        canonical_document_language=language,
        status=STATUS_RESOLVED,
        blocked=False,
        source="+".join(sources),
        policy=DOCUMENT_LANGUAGE_POLICY,
        transcript_primary_language=transcript,
        source_map_primary_language=source_map,
        observed_fields=tuple(observed),
        notes=notes,
    )


def plan_must_match_book_language() -> dict[str, Any]:
    return {
        "policy": RECOMMENDED_ALIGNMENT,
        "rationale": (
            "EditorialPlan titles, purposes, angle, and reader journey become "
            "the Book Generator's organizing language. A plan in language A "
            "and a manuscript in language B creates avoidable semantic and "
            "style risk (re-translation of editorial framing, title drift, "
            "audience-register mismatch). Plan language must match book language."
        ),
        "mismatch_architecturally_safe": False,
        "successor_prompt_if_instruction_needed": SUCCESSOR_PROMPT_VERSION,
        "do_not_mutate_active_prompt": ACTIVE_PROMPT_VERSION,
        "new_grammar_canary_required_for_language_instruction_only": False,
        "schema_change_required_for_language_policy": False,
        "transport_change_required_for_language_policy": False,
    }


__all__ = [
    "ACTIVE_PROMPT_VERSION",
    "CONCEPT_AUTHOR_ORIGINAL",
    "CONCEPT_EDITORIAL_PLANNING",
    "CONCEPT_FINAL_BOOK",
    "CONCEPT_PROMPT_INSTRUCTION",
    "CONCEPT_SOURCE_PRIMARY",
    "CONCEPT_UI_PROJECT",
    "CONTRACT_ALLOWED",
    "CONTRACT_INSUFFICIENT",
    "CONTRACT_UNSPECIFIED",
    "CONTRACT_VIOLATION",
    "DOCUMENT_LANGUAGE_POLICY",
    "DOCUMENT_LANGUAGE_POLICY_VERSION",
    "DocumentLanguageResolution",
    "FIELD_SOURCE_MAP_PRIMARY",
    "FIELD_TRANSCRIPT_PRIMARY",
    "INHERIT_MODES",
    "INHERIT_PROJECT",
    "INHERIT_REQUIRE_EXPLICIT",
    "INHERIT_SOURCE",
    "LANGUAGE_CONCEPTS",
    "LANGUAGE_POLICY_VERSION",
    "LanguageResolution",
    "RECOMMENDED_ALIGNMENT",
    "RECOMMENDED_DEFAULT_MODE",
    "RECOMMENDED_SETTING_NAME",
    "SETTING_ALIASES",
    "STATUS_BLOCKED_MISMATCH",
    "STATUS_BLOCKED_UNKNOWN",
    "STATUS_EXPLICIT_BOOK",
    "STATUS_INHERITED_PROJECT",
    "STATUS_INHERITED_SOURCE",
    "STATUS_RESOLVED",
    "STATUS_UNRESOLVED",
    "SUCCESSOR_PROMPT_VERSION",
    "UNRESOLVED_LANGUAGE_TOKENS",
    "is_unresolved_language",
    "languages_differ",
    "normalize_language_code",
    "plan_must_match_book_language",
    "resolve_book_language",
    "resolve_document_language",
]
