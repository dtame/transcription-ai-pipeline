"""
LMStudioEngine — serveur local exposant une API compatible OpenAI.

Adapté de la V1 sans changer son comportement : même URL, même forme de
payload, même texte retourné. Le timeout, qui était la valeur magique 300
écrite dans le code, vient maintenant de app.config.AI_DEFAULT_TIMEOUT_SECONDS
(dont la valeur par défaut est 300 : rien ne bouge, tout devient réglable).

LM Studio renvoie un bloc `usage` compatible OpenAI ; il est remonté tel quel
quand il est présent, et reste à None sinon — jamais remplacé par des zéros.
"""

from __future__ import annotations

import app.config as config

from app.ai.contracts import AIRequest
from app.ai.errors import AIResponseError
from app.ai.provider_forensics import (
    CLASS_MISSING_PROVIDER_FIELD,
    apply_envelope_to_error,
    persist_current_failure,
)
from app.ai.providers._http import execute_provider_post
from app.ai.providers.base import BaseAIEngine, ProviderResult

_CONNECTION_HINT = "Vérifiez que le serveur local LM Studio est démarré."
_TIMEOUT_HINT = "Augmentez le timeout ou essayez un modèle plus léger."


def extract_openai_usage(data: dict) -> tuple[int | None, int | None, int | None, dict]:
    """
    Extrait le bloc `usage` du format OpenAI (partagé par LM Studio).

    Retourne (input, output, total, brut). Un champ absent vaut None : c'est
    la différence entre « le fournisseur n'a rien dit » et « zéro token ».
    """
    usage = data.get("usage") or {}

    def _optional_int(key: str) -> int | None:
        value = usage.get(key)
        return int(value) if value is not None else None

    return (
        _optional_int("prompt_tokens"),
        _optional_int("completion_tokens"),
        _optional_int("total_tokens"),
        dict(usage),
    )


class LMStudioEngine(BaseAIEngine):
    """
    Moteur IA basé sur LM Studio (API compatible OpenAI).
    Activer avec : AI_PROVIDER = "lmstudio"

    URL par défaut    : app.config.LMSTUDIO_BASE_URL
    Modèle par défaut : app.config.LMSTUDIO_MODEL

    Prérequis :
        - LM Studio installé et serveur local démarré
        - Un modèle chargé dans LM Studio
    """

    provider_name = "lmstudio"

    def __init__(self, *, base_url: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._base_url = base_url

    def base_url(self) -> str:
        return str(self._base_url or config.LMSTUDIO_BASE_URL).rstrip("/")

    def config_model(self) -> str | None:
        return getattr(config, "LMSTUDIO_MODEL", None)

    def config_temperature(self) -> float | None:
        return getattr(config, "LMSTUDIO_TEMPERATURE", 0.2)

    def build_payload(self, request: AIRequest, model: str) -> dict:
        messages = []

        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": model,
            "messages": messages,
        }

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
        exchange = execute_provider_post(
            f"{self.base_url()}/chat/completions",
            self.build_payload(request, model),
            provider="LM Studio",
            timeout=self.resolve_timeouts(request),
            connection_hint=_CONNECTION_HINT,
            timeout_hint=_TIMEOUT_HINT,
            model=model,
        )
        data = exchange.payload
        envelope = exchange.envelope

        try:
            choice = data["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            error = AIResponseError(
                "Réponse LM Studio inattendue : structure de réponse invalide. "
                f"Clés reçues : {sorted(data.keys())}"
            )
            error.classification = CLASS_MISSING_PROVIDER_FIELD
            apply_envelope_to_error(error, envelope)
            persist_current_failure(classification=CLASS_MISSING_PROVIDER_FIELD)
            raise error from exc

        input_tokens, output_tokens, total_tokens, raw_usage = extract_openai_usage(data)

        envelope.provider_envelope_valid = True
        return ProviderResult(
            text=str(content).strip(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            finish_reason=choice.get("finish_reason"),
            request_id=data.get("id") or envelope.request_id,
            model=data.get("model") or model,
            raw_usage=raw_usage,
            http_envelope=envelope,
        )
