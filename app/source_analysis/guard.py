"""
Garde-fou « un seul appel réel » pour le Source Analyzer.

RealCallGuard est un compteur EXPLICITE, incrémenté AVANT engine.generate()
— donc même une exception levée PENDANT l'appel ne peut pas laisser le
compteur à zéro et autoriser une seconde tentative depuis ce même guard.

Une nouvelle exécution (nouveau processus, nouvelle instance) recommence
à zéro : ce garde-fou protège UNE exécution, pas l'historique au long cours.
"""

from __future__ import annotations

from app.ai.contracts import AIRequest, AIResponse
from app.source_analysis.errors import MaxRealCallsExceededError

MAX_REAL_CALLS = 1


class RealCallGuard:
    """Compte les appels réels tentés à travers ce garde, et les plafonne."""

    def __init__(self, max_calls: int = MAX_REAL_CALLS) -> None:
        self.max_calls = int(max_calls)
        self.call_count = 0

    def guarded_generate(self, engine, request: AIRequest) -> AIResponse:
        """
        Exécute `engine.generate(request)`, en refusant toute tentative
        au-delà de `max_calls`.

        Le compteur est incrémenté AVANT l'appel : un appel qui échoue
        après avoir été compté ne peut donc jamais être « regagné ».
        """
        if self.call_count >= self.max_calls:
            raise MaxRealCallsExceededError(
                f"Le garde-fou Source Analyzer autorise au plus {self.max_calls} "
                f"appel(s) réel(s) ; un {self.call_count + 1}e appel a été "
                "tenté depuis ce runner."
            )

        self.call_count += 1

        return engine.generate(request)
