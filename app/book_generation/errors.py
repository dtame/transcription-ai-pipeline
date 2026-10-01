"""Book Generator errors. Fail closed. Do not repair."""

from __future__ import annotations


class BookGenerationError(Exception):
    """Base Book Generator error."""


class BookGenerationBlocked(BookGenerationError):
    """Identity or contract mismatch. Do not proceed."""


class BookGenerationTransportError(BookGenerationError):
    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__(" ; ".join(self.errors))


class BookGenerationValidationError(BookGenerationError):
    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__(" ; ".join(self.errors))


class BookPublicationBlocked(BookGenerationError):
    """book.json publication is forbidden in this phase."""
