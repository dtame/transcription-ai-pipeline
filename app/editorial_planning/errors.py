"""Erreurs du Editorial Planner. Distinctes de la couche IA et du Source Analyzer."""

from __future__ import annotations


class EditorialPlanningError(RuntimeError):
    """Racine des échecs du Editorial Planner."""


class EditorialPlanValidationError(EditorialPlanningError):
    """Le plan canonique viole le contrat (FAIL dur)."""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        preview = "; ".join(self.errors[:8])
        extra = f" (+{len(self.errors) - 8})" if len(self.errors) > 8 else ""
        super().__init__(f"EditorialPlan invalide : {preview}{extra}")


class EditorialPlanTransportError(EditorialPlanningError):
    """Transport provider illisible ou hors contrat de reconstruction."""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        preview = "; ".join(self.errors[:8])
        extra = f" (+{len(self.errors) - 8})" if len(self.errors) > 8 else ""
        super().__init__(f"Transport éditorial invalide : {preview}{extra}")


class EditorialPlanPublicationBlocked(EditorialPlanningError):
    """Phase 4A : aucune publication de editorial_plan.json."""

    def __init__(self, message: str | None = None):
        super().__init__(
            message
            or "Publication de editorial_plan.json interdite en Phase 4A."
        )


class EditorialPlanSourceMapIntegrityError(EditorialPlanningError):
    """Le SourceMap lu n'est pas l'identité attendue, ou est illisible."""


class EditorialPlannerNotAuthorized(EditorialPlanningError):
    """Appel provider réel non autorisé en Phase 4A."""


class DocumentLanguageBlocked(EditorialPlanningError):
    """Langue documentaire canonique absente, inconnue ou contradictoire."""
