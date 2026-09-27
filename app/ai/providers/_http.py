"""
Transport HTTP commun aux providers qui parlent à une API REST.

Ollama, LM Studio et Anthropic partagent le même besoin : poster du JSON et
traduire les incidents réseau en erreurs de la couche IA. Sans ce module,
chaque provider réécrirait sa propre table de correspondance et finirait par
diverger sur ce qui est rejouable.

Seul `requests` est utilisé : déjà présent dans requirements.txt, donc la
Phase 2 n'ajoute aucune dépendance de transport.

La traduction des codes HTTP est la frontière entre « rejouable » et « non
rejouable » :

    401 / 403      AIAuthenticationError   jamais rejoué
    408 / 429      transitoire             rejoué
    5xx            AIServerError           rejoué
    autres 4xx     AIRequestError          jamais rejoué

Timeouts (Phase 3B.5.1) : requests reçoit toujours un tuple
(connect, read). Un scalaire historique est normalisé en
(connect_défaut, scalaire) pour ne plus transformer un read long en
connect long. requests n'offre pas de timeout total wall-clock ici.

Phase 3B.7.7A.5 : dès qu'une réponse HTTP est reçue, une enveloppe
forensique est capturée AVANT interprétation (JSON, content, AIResponse).
"""

from __future__ import annotations

import time
from typing import Any, Mapping

import requests

from app.ai.errors import (
    AIAuthenticationError,
    AIConnectionError,
    AIRateLimitError,
    AIRequestError,
    AIServerError,
    AITimeoutError,
)
from app.ai.provider_forensics import (
    CLASS_HTTP_ERROR,
    ProviderHttpEnvelope,
    ProviderHttpExchange,
    apply_envelope_to_error,
    capture_http_response,
    decode_json_from_envelope,
    persist_current_failure,
    persist_interrupt_forensics,
)
from app.ai.timeouts import (
    AITimeoutConfig,
    classify_requests_timeout,
    requests_timeout_argument,
)


def _raise_for_status(response, provider: str, envelope: ProviderHttpEnvelope) -> None:
    status = getattr(response, "status_code", 0)

    if status < 400:
        return

    envelope.classification = CLASS_HTTP_ERROR
    detail = f"{provider} a répondu {status}."

    if status in (401, 403):
        error = AIAuthenticationError(
            f"Authentification refusée par {provider} ({status}). "
            "Vérifiez la clé API dans les variables d'environnement."
        )
    elif status in (408, 429):
        error = AIRateLimitError(detail)
    elif status >= 500:
        error = AIServerError(detail)
    else:
        error = AIRequestError(detail)

    error.classification = CLASS_HTTP_ERROR
    apply_envelope_to_error(error, envelope)
    persist_current_failure(classification=CLASS_HTTP_ERROR)
    raise error


def execute_provider_post(
    url: str,
    payload: Mapping[str, Any],
    *,
    provider: str,
    timeout: float | tuple[float, float] | AITimeoutConfig,
    headers: Mapping[str, str] | None = None,
    connection_hint: str = "",
    timeout_hint: str = "",
    model: str | None = None,
) -> ProviderHttpExchange:
    """
    POST JSON + enveloppe HTTP.

    Ordre :
        requests.post
        → réponse reçue
        → capture forensique (mémoire)
        → statut HTTP
        → décodage JSON depuis les bytes
        → objet JSON attendu
    """
    timeout_arg = requests_timeout_argument(timeout)
    connect_seconds, read_seconds = timeout_arg
    started = time.monotonic()
    envelope: ProviderHttpEnvelope | None = None

    try:
        response = requests.post(
            url,
            json=dict(payload),
            timeout=timeout_arg,
            headers=dict(headers) if headers else None,
        )
    except requests.exceptions.Timeout as exc:
        elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
        kind = classify_requests_timeout(exc)
        error = AITimeoutError(
            f"{provider} n'a pas répondu dans les délais "
            f"(connect={connect_seconds} s, read={read_seconds} s, "
            f"kind={kind}). {timeout_hint}".strip(),
            timeout_kind=kind,
            connect_timeout_seconds=connect_seconds,
            read_timeout_seconds=read_seconds,
            elapsed_ms=elapsed_ms,
        )
        error.post_attempted = True
        error.response_received = False
        raise error from exc
    except requests.exceptions.ConnectionError as exc:
        error = AIConnectionError(
            f"Impossible de joindre {provider} sur {url}. {connection_hint}".strip()
        )
        error.post_attempted = True
        error.response_received = False
        raise error from exc
    except requests.exceptions.RequestException as exc:
        error = AIConnectionError(f"Erreur de transport vers {provider} : {exc}")
        error.post_attempted = True
        error.response_received = False
        raise error from exc

    elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
    envelope = capture_http_response(
        response,
        provider=provider,
        model=model,
        elapsed_ms=elapsed_ms,
    )

    try:
        _raise_for_status(response, provider, envelope)
        data = decode_json_from_envelope(envelope)
    except KeyboardInterrupt:
        persist_interrupt_forensics()
        raise
    except Exception:
        if envelope.classification:
            persist_current_failure(classification=envelope.classification)
        raise

    return ProviderHttpExchange(payload=data, envelope=envelope)


def post_json(
    url: str,
    payload: Mapping[str, Any],
    *,
    provider: str,
    timeout: float | tuple[float, float] | AITimeoutConfig,
    headers: Mapping[str, str] | None = None,
    connection_hint: str = "",
    timeout_hint: str = "",
    model: str | None = None,
) -> dict:
    """
    POST JSON et retour du corps décodé, incidents traduits en erreurs IA.

    Les `hint` permettent aux providers locaux de conserver leurs messages
    d'aide V1 (« vérifiez qu'Ollama est bien lancé ») sans réécrire la
    gestion d'erreurs.

    `timeout` est normalisé en (connect, read) avant requests.post.
    """
    return execute_provider_post(
        url,
        payload,
        provider=provider,
        timeout=timeout,
        headers=headers,
        connection_hint=connection_hint,
        timeout_hint=timeout_hint,
        model=model,
    ).payload
