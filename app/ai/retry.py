"""
Politique de rejeu des appels IA.

Périmètre volontairement étroit : on rejoue les incidents passagers
(timeout, 429, 5xx, service injoignable) et rien d'autre. Une clé invalide,
une requête malformée ou un JSON métier cassé ne s'améliorent pas en les
répétant — les répéter ne fait que brûler du quota.

La décision « rejouable ou non » n'est pas prise ici : elle est portée par
la hiérarchie d'erreurs (AITransientError), donc par le provider qui a
traduit l'incident.

Le temps d'attente passe par `RetryPolicy.sleep`, injectable. Les tests
fournissent une fonction qui n'attend pas : aucune suite pytest ne doit
payer un backoff réel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

import time

import app.config as config

from app.ai.errors import is_retryable


@dataclass(frozen=True)
class RetryPolicy:
    """
    max_attempts        nombre TOTAL de tentatives (1 = aucun rejeu)
    base_delay_seconds  attente après la 1re tentative
    multiplier          facteur d'augmentation entre deux attentes
    max_delay_seconds   plafond d'attente
    sleep               fonction d'attente, remplaçable dans les tests
    """

    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    multiplier: float = 2.0
    max_delay_seconds: float = 8.0
    sleep: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        if int(self.max_attempts) < 1:
            raise ValueError(
                f"RetryPolicy.max_attempts doit être >= 1 : {self.max_attempts}"
            )

        if float(self.base_delay_seconds) < 0:
            raise ValueError(
                "RetryPolicy.base_delay_seconds doit être >= 0 : "
                f"{self.base_delay_seconds}"
            )

    def delay_for(self, attempt: int) -> float:
        """Attente avant la tentative n° `attempt` + 1 (attempt est 1-based)."""
        raw = float(self.base_delay_seconds) * (
            float(self.multiplier) ** max(0, attempt - 1)
        )

        return min(raw, float(self.max_delay_seconds))


def no_delay_policy(max_attempts: int = 3) -> RetryPolicy:
    """Politique sans attente réelle — destinée aux tests et aux mocks."""
    return RetryPolicy(
        max_attempts=max_attempts,
        base_delay_seconds=0.0,
        sleep=lambda _seconds: None,
    )


def default_retry_policy() -> RetryPolicy:
    """Politique globale, lue depuis la configuration à chaque appel."""
    return RetryPolicy(
        max_attempts=int(getattr(config, "AI_MAX_ATTEMPTS", 3)),
        base_delay_seconds=float(getattr(config, "AI_RETRY_BASE_DELAY_SECONDS", 0.5)),
        max_delay_seconds=float(getattr(config, "AI_RETRY_MAX_DELAY_SECONDS", 8.0)),
    )


@dataclass
class RetryTrace:
    """Journal des rejeux d'un appel, pour l'observabilité et les tests."""

    attempts: int = 0
    errors: list[BaseException] = field(default_factory=list)
    delays: list[float] = field(default_factory=list)

    @property
    def retried(self) -> bool:
        return self.attempts > 1


def call_with_retry(
    operation: Callable[[], object],
    policy: RetryPolicy | None = None,
    trace: RetryTrace | None = None,
) -> object:
    """
    Exécute `operation`, en la rejouant sur erreur transitoire uniquement.

    Relève systématiquement la dernière erreur rencontrée lorsque toutes les
    tentatives sont épuisées : un appel qui échoue ne renvoie jamais un
    résultat de substitution.
    """
    policy = policy or default_retry_policy()
    trace = trace if trace is not None else RetryTrace()

    last_error: BaseException | None = None

    for attempt in range(1, int(policy.max_attempts) + 1):
        trace.attempts = attempt

        try:
            return operation()
        except BaseException as exc:  # noqa: BLE001 - relevé plus bas si non rejouable
            last_error = exc
            trace.errors.append(exc)

            if not is_retryable(exc) or attempt >= int(policy.max_attempts):
                raise

            delay = policy.delay_for(attempt)
            trace.delays.append(delay)

            if delay > 0:
                policy.sleep(delay)

    # Inatteignable : la boucle relève toujours. Garde-fou explicite.
    raise last_error if last_error else RuntimeError("call_with_retry: état impossible")


def transient_error_types() -> Iterable[str]:
    """Noms des erreurs rejouées, pour la documentation et les rapports."""
    return ("AITimeoutError", "AIConnectionError", "AIRateLimitError", "AIServerError")
