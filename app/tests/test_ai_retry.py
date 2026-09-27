"""
Politique de rejeu.

Deux garanties, et la seconde compte autant que la première :

    on rejoue les incidents transitoires, et RIEN d'autre ;
    aucune attente réelle n'a lieu pendant les tests.

Le second point est vérifié en assertant que la fonction d'attente employée
n'est jamais time.sleep et que la durée mesurée reste négligeable.
"""

from __future__ import annotations

import time

import pytest

import app.config as config

from app.ai.errors import (
    AIAuthenticationError,
    AIRateLimitError,
    AIRequestError,
    AIServerError,
    AIStructuredOutputError,
    AITimeoutError,
    is_retryable,
)
from app.ai.retry import (
    RetryPolicy,
    RetryTrace,
    call_with_retry,
    default_retry_policy,
    no_delay_policy,
)


class _Compteur:
    """Opération scénarisée : lève ce qu'on lui donne, puis réussit."""

    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.appels = 0

    def __call__(self):
        self.appels += 1
        item = self.sequence[min(self.appels - 1, len(self.sequence) - 1)]

        if isinstance(item, BaseException):
            raise item

        return item


class _SleepEspion:
    def __init__(self):
        self.durees = []

    def __call__(self, seconds):
        self.durees.append(seconds)


class TestClassificationDesErreurs:

    @pytest.mark.parametrize(
        "erreur",
        [AITimeoutError("t"), AIRateLimitError("r"), AIServerError("s")],
    )
    def test_transitoires_rejouables(self, erreur):
        assert is_retryable(erreur) is True

    @pytest.mark.parametrize(
        "erreur",
        [
            AIAuthenticationError("clé invalide"),
            AIRequestError("requête invalide"),
            AIStructuredOutputError("json cassé"),
            ValueError("autre chose"),
        ],
    )
    def test_non_transitoires_non_rejouables(self, erreur):
        assert is_retryable(erreur) is False


class TestRejeu:

    def test_timeout_puis_succes(self):
        """Scénario canonique : appel 1 en timeout, appel 2 réussi."""
        operation = _Compteur([AITimeoutError("trop lent"), "ok"])
        espion = _SleepEspion()
        trace = RetryTrace()

        resultat = call_with_retry(
            operation,
            RetryPolicy(max_attempts=3, base_delay_seconds=0.5, sleep=espion),
            trace,
        )

        assert resultat == "ok"
        assert operation.appels == 2
        assert trace.attempts == 2
        assert trace.retried is True
        assert espion.durees == [0.5]

    def test_erreur_auth_non_repetee(self):
        operation = _Compteur([AIAuthenticationError("clé invalide")])
        espion = _SleepEspion()

        with pytest.raises(AIAuthenticationError):
            call_with_retry(
                operation,
                RetryPolicy(max_attempts=5, base_delay_seconds=0.5, sleep=espion),
            )

        assert operation.appels == 1
        assert espion.durees == []

    def test_requete_invalide_non_repetee(self):
        operation = _Compteur([AIRequestError("400")])

        with pytest.raises(AIRequestError):
            call_with_retry(operation, no_delay_policy(max_attempts=4))

        assert operation.appels == 1

    def test_json_invalide_non_repete(self):
        operation = _Compteur([AIStructuredOutputError("json cassé")])

        with pytest.raises(AIStructuredOutputError):
            call_with_retry(operation, no_delay_policy(max_attempts=4))

        assert operation.appels == 1

    def test_tentatives_epuisees_releve_la_derniere_erreur(self):
        operation = _Compteur([AIServerError("500")])

        with pytest.raises(AIServerError):
            call_with_retry(operation, no_delay_policy(max_attempts=3))

        assert operation.appels == 3

    def test_max_attempts_1_desactive_le_rejeu(self):
        operation = _Compteur([AITimeoutError("t")])

        with pytest.raises(AITimeoutError):
            call_with_retry(operation, no_delay_policy(max_attempts=1))

        assert operation.appels == 1

    def test_succes_immediat_sans_attente(self):
        operation = _Compteur(["ok"])
        espion = _SleepEspion()

        assert call_with_retry(
            operation, RetryPolicy(max_attempts=3, sleep=espion)
        ) == "ok"
        assert espion.durees == []

    def test_pas_de_boucle_infinie(self):
        """Un échec permanent s'arrête au plafond, il ne tourne pas sans fin."""
        operation = _Compteur([AIServerError("500")])

        with pytest.raises(AIServerError):
            call_with_retry(operation, no_delay_policy(max_attempts=2))

        assert operation.appels == 2


class TestBackoff:

    def test_progression_exponentielle(self):
        policy = RetryPolicy(base_delay_seconds=0.5, multiplier=2.0, max_delay_seconds=8)

        assert policy.delay_for(1) == 0.5
        assert policy.delay_for(2) == 1.0
        assert policy.delay_for(3) == 2.0

    def test_plafond_respecte(self):
        policy = RetryPolicy(base_delay_seconds=1.0, multiplier=10.0, max_delay_seconds=5)

        assert policy.delay_for(5) == 5.0

    def test_max_attempts_invalide(self):
        with pytest.raises(ValueError, match="max_attempts"):
            RetryPolicy(max_attempts=0)

    def test_delai_negatif_invalide(self):
        with pytest.raises(ValueError, match="base_delay_seconds"):
            RetryPolicy(base_delay_seconds=-1)


class TestAucuneAttenteReelle:

    def test_no_delay_policy_n_utilise_pas_time_sleep(self):
        policy = no_delay_policy()

        assert policy.sleep is not time.sleep
        assert policy.base_delay_seconds == 0.0

    def test_serie_de_rejeux_instantanee(self):
        operation = _Compteur(
            [AITimeoutError("1"), AIServerError("2"), "ok"]
        )

        debut = time.monotonic()
        resultat = call_with_retry(operation, no_delay_policy(max_attempts=3))
        duree = time.monotonic() - debut

        assert resultat == "ok"
        assert duree < 0.5


class TestPolitiqueParDefaut:

    def test_lue_depuis_la_configuration(self, monkeypatch):
        monkeypatch.setattr(config, "AI_MAX_ATTEMPTS", 7)
        monkeypatch.setattr(config, "AI_RETRY_BASE_DELAY_SECONDS", 0.25)
        monkeypatch.setattr(config, "AI_RETRY_MAX_DELAY_SECONDS", 3.0)

        policy = default_retry_policy()

        assert policy.max_attempts == 7
        assert policy.base_delay_seconds == 0.25
        assert policy.max_delay_seconds == 3.0
