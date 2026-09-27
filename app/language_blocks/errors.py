"""Erreurs du paquet d'analyse structurelle des blocs FR (Phase 3A.1.1)."""

from __future__ import annotations


class LanguageBlocksError(RuntimeError):
    """Base des erreurs de l'analyse structurelle des blocs FR."""


class SourceIntegrityError(LanguageBlocksError):
    """
    transcript_data.json et language_cleanup.json ne concordent pas assez pour
    être analysés ensemble en toute sécurité (SHA incohérent, SRC absent,
    ordre différent, decision hors vocabulaire...).
    """


class BlocksValidationError(LanguageBlocksError):
    """language_blocks.json ne satisfait pas son propre contrat."""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__(
            f"{len(self.errors)} violation(s) du manifeste language_blocks.json : "
            + " | ".join(self.errors)
        )
