"""
OpenAIEngine — API cloud OpenAI (SDK officiel, déjà présent dans le projet).

Le provider OpenAI de la V1 est ADAPTÉ, pas doublé : même SDK, même import
tardif, même appel chat.completions. Ce qui s'y ajoute :

    clé API        lue dans la variable d'environnement OPENAI_API_KEY
                   (voir app/ai/settings.py). Plus aucune clé dans le code.

    usage tokens   response.usage est la SOURCE DE VÉRITÉ du coût. Le texte
                   n'est jamais re-tokenisé pour fabriquer un chiffre : quand
                   l'API donne les compteurs, on prend les siens.

    erreurs        les exceptions du SDK sont traduites en erreurs de la
                   couche IA, ce qui rend le rejeu possible pour les seuls
                   incidents transitoires.

Le module `openai` reste importé au moment de l'appel : l'instanciation du
moteur ne doit pas exiger le SDK, pour que le registre reste inspectable sur
une machine qui ne l'a pas installé.
"""

from __future__ import annotations

from typing import Any

import app.config as config

from app.ai.contracts import AIRequest
from app.ai.errors import (
    AIAuthenticationError,
    AIConnectionError,
    AIProviderUnavailableError,
    AIRateLimitError,
    AIRequestError,
    AIResponseError,
    AIServerError,
    AITimeoutError,
)
from app.ai.providers.base import BaseAIEngine, ProviderResult
from app.ai.providers.lmstudio import extract_openai_usage
from app.ai.settings import ENV_OPENAI_API_KEY, require_api_key

# Traduction par NOM de classe : évite d'importer les types du SDK au chargement
# du module, tout en restant lisible.
_ERROR_BY_NAME: dict[str, type[Exception]] = {
    "APITimeoutError": AITimeoutError,
    "APIConnectionError": AIConnectionError,
    "RateLimitError": AIRateLimitError,
    "AuthenticationError": AIAuthenticationError,
    "PermissionDeniedError": AIAuthenticationError,
    "BadRequestError": AIRequestError,
    "NotFoundError": AIRequestError,
    "UnprocessableEntityError": AIRequestError,
    "ConflictError": AIRequestError,
    "InternalServerError": AIServerError,
}


def translate_sdk_error(exc: Exception, provider: str = "OpenAI") -> Exception:
    """
    Traduit une exception de SDK en erreur de la couche IA.

    Le nom de classe prime ; à défaut, le code HTTP porté par l'exception
    tranche. Un incident non reconnu devient AIResponseError — donc NON
    rejouable : mieux vaut s'arrêter que boucler sur un cas inconnu.
    """
    mapped = _ERROR_BY_NAME.get(type(exc).__name__)

    if mapped is not None:
        return mapped(f"{provider} : {exc}")

    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)

    if isinstance(status, int):
        if status in (401, 403):
            return AIAuthenticationError(f"{provider} : authentification refusée ({status}).")
        if status in (408, 429):
            return AIRateLimitError(f"{provider} : quota ou délai dépassé ({status}).")
        if status >= 500:
            return AIServerError(f"{provider} : erreur serveur ({status}).")
        if status >= 400:
            return AIRequestError(f"{provider} : requête refusée ({status}) — {exc}")

    error = AIResponseError(f"{provider} : erreur inattendue — {exc}")
    error.classification = "SDK_UNEXPECTED"
    return error


class OpenAIEngine(BaseAIEngine):
    """
    Moteur IA basé sur l'API OpenAI (cloud).
    Activer avec : AI_PROVIDER = "openai"

    Nécessite la variable d'environnement OPENAI_API_KEY.
    Modèle par défaut : app.config.OPENAI_MODEL

    Note : le package `openai` est importé uniquement à l'appel pour ne pas
    rendre la dépendance obligatoire.
    """

    provider_name = "openai"

    def __init__(self, *, api_key: str | None = None, client: Any = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._api_key = api_key
        # Client injectable : les tests fournissent un double, sans réseau
        # ni clé, et sans monkeypatcher le SDK.
        self._client = client

    def config_model(self) -> str | None:
        return getattr(config, "OPENAI_MODEL", None)

    def config_temperature(self) -> float | None:
        return getattr(config, "OPENAI_TEMPERATURE", 0.2)

    def resolve_api_key(self) -> str:
        if self._api_key:
            return self._api_key

        return require_api_key(
            "openai",
            ENV_OPENAI_API_KEY,
            config_fallback="OPENAI_API_KEY",
        )

    def client(self):
        """Client OpenAI, construit à la demande et mémorisé."""
        if self._client is not None:
            return self._client

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AIProviderUnavailableError(
                "Le package 'openai' n'est pas installé. "
                "Installez-le avec : pip install openai"
            ) from exc

        kwargs: dict[str, Any] = {"api_key": self.resolve_api_key()}

        base_url = getattr(config, "OPENAI_BASE_URL", None)
        if base_url:
            kwargs["base_url"] = base_url

        self._client = OpenAI(**kwargs)
        return self._client

    def build_payload(self, request: AIRequest, model: str) -> dict:
        messages = []

        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        messages.append({"role": "user", "content": request.prompt})

        payload: dict[str, Any] = {"model": model, "messages": messages}

        temperature = self.resolve_temperature(request)
        if temperature is not None:
            payload["temperature"] = temperature

        max_output = self.resolve_max_output_tokens(request)
        if max_output is not None:
            payload["max_tokens"] = max_output

        if request.wants_structured_output:
            payload["response_format"] = {"type": "json_object"}

        return payload

    def _invoke(self, request: AIRequest, model: str) -> ProviderResult:
        client = self.client()
        payload = self.build_payload(request, model)

        # Le SDK OpenAI n'accepte pas le tuple (connect, read) de requests.
        # Comportement effectif inchangé : scalaire = read timeout résolu.
        timeout = self.resolve_timeout(request)
        if timeout:
            payload["timeout"] = timeout

        try:
            completion = client.chat.completions.create(**payload)
        except Exception as exc:
            raise translate_sdk_error(exc) from exc

        return self._normalize(completion, model)

    def _normalize(self, completion: Any, model: str) -> ProviderResult:
        try:
            choice = completion.choices[0]
            content = choice.message.content
        except (AttributeError, IndexError, TypeError) as exc:
            error = AIResponseError(
                "Réponse OpenAI inattendue : aucun message exploitable."
            )
            error.classification = "MISSING_PROVIDER_FIELD"
            raise error from exc

        if content is None:
            error = AIResponseError(
                "Réponse OpenAI vide : le modèle n'a retourné aucun contenu "
                f"(finish_reason={getattr(choice, 'finish_reason', None)})."
            )
            error.classification = "NO_TEXT_BLOCK"
            raise error

        input_tokens, output_tokens, total_tokens, raw_usage = extract_openai_usage(
            {"usage": _usage_as_dict(getattr(completion, "usage", None))}
        )

        return ProviderResult(
            text=str(content).strip(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            finish_reason=getattr(choice, "finish_reason", None),
            request_id=getattr(completion, "id", None),
            model=getattr(completion, "model", None) or model,
            raw_usage=raw_usage,
        )


def _usage_as_dict(usage: Any) -> dict:
    """Normalise le bloc usage du SDK (objet pydantic ou dict) en dict."""
    if usage is None:
        return {}

    if isinstance(usage, dict):
        return usage

    for attribute in ("model_dump", "dict", "to_dict"):
        method = getattr(usage, attribute, None)

        if callable(method):
            try:
                return dict(method())
            except Exception:
                continue

    return {
        key: getattr(usage, key)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if getattr(usage, key, None) is not None
    }
