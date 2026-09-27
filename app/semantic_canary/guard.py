"""
Garde-fou « un seul appel réel » (§12, §32).

RealCallGuard est un compteur EXPLICITE, incrémenté AVANT l'appel — donc même
une exception levée PENDANT l'appel ne peut pas laisser le compteur à zéro
et autoriser une seconde tentative depuis ce même guard. Une nouvelle
exécution du runner (nouveau processus, ou nouvelle instance) recommence à
zéro : ce garde-fou protège UNE exécution du canary, pas l'historique
au long cours (qui reste de la responsabilité de l'opérateur humain, §39).
"""

from __future__ import annotations

from app.ai.contracts import AIRequest, AIResponse
from app.semantic_canary.errors import MaxRealCallsExceededError

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

        Le compteur est incrémenté AVANT l'appel (§32) : un appel qui échoue
        après avoir été compté ne peut donc jamais être « regagné » par un
        appelant qui retenterait via ce même guard.
        """
        if self.call_count >= self.max_calls:
            raise MaxRealCallsExceededError(
                f"Le garde-fou du canary autorise au plus {self.max_calls} "
                f"appel(s) réel(s) ; un {self.call_count + 1}e appel a été "
                "tenté depuis ce runner."
            )

        self.call_count += 1

        return engine.generate(request)
