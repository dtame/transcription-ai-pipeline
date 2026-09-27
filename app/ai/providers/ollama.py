"""
OllamaEngine — moteur local principal (endpoint /api/generate).

Adapté, pas réécrit : le payload, l'URL, le timeout et le texte retourné
sont ceux de la V1. Trois choses seulement changent, toutes additives :

    num_ctx        vient désormais des capacités du modèle. Sa valeur par
                   défaut est celle de app.config.OLLAMA_OPTIONS, donc
                   inchangée — mais elle cesse d'être une vérité universelle
                   et devient surchargeable par modèle.

    usage tokens   prompt_eval_count et eval_count, rapportés par Ollama,
                   sont remontés dans AIResponse au lieu d'être ignorés.

    erreurs        traduites en AIConnectionError / AITimeoutError / …
                   (toutes filles de RuntimeError, comme en V1), ce qui rend
                   le rejeu possible sans changer ce que voient les appelants.
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

_CONNECTION_HINT = "Vérifiez qu'Ollama est bien lancé (`ollama serve`)."
_TIMEOUT_HINT = "Augmentez le timeout ou essayez un modèle plus léger."


class OllamaEngine(BaseAIEngine):
    """
    Moteur IA principal basé sur Ollama (local).
    Activer avec : AI_PROVIDER = "ollama"

    Modèle par défaut : app.config.OLLAMA_MODEL
    URL par défaut    : app.config.OLLAMA_BASE_URL

    Prérequis :
        - Ollama installé et lancé
        - Modèle téléchargé : ollama pull <modèle>
    """

    provider_name = "ollama"

    def __init__(self, *, base_url: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._base_url = base_url

    def base_url(self) -> str:
        return str(self._base_url or config.OLLAMA_BASE_URL).rstrip("/")

    def config_model(self) -> str | None:
        return getattr(config, "OLLAMA_MODEL", None)

    def config_temperature(self) -> float | None:
        return getattr(config, "OLLAMA_OPTIONS", {}).get("temperature")

    def config_timeout(self) -> float:
        return float(getattr(config, "OLLAMA_TIMEOUT_SECONDS", 1200))

    def build_options(self, request: AIRequest, model: str) -> dict:
        """
        Options Ollama de l'appel.

        Part des OLLAMA_OPTIONS de la V1 puis applique, dans cet ordre, la
        fenêtre de contexte du modèle et les réglages propres à la requête.
        """
        options = dict(getattr(config, "OLLAMA_OPTIONS", {}) or {})
        options["num_ctx"] = self.capabilities(model).context_window

        temperature = self.resolve_temperature(request)
        if temperature is not None:
            options["temperature"] = temperature

        max_output = self.resolve_max_output_tokens(request)
        if max_output is not None:
            options["num_predict"] = max_output

        return options

    def build_payload(self, request: AIRequest, model: str) -> dict:
        """
        Payload envoyé à /api/generate.

        Construit champ par champ : `request.metadata` sert à l'observabilité
        interne et n'a rien à faire dans un appel réseau.
        """
        payload = {
            "model": model,
            "prompt": request.prompt,
            "stream": False,
            "options": self.build_options(request, model),
        }

        if request.system_prompt:
            payload["system"] = request.system_prompt

        if request.wants_structured_output:
            # Contraint la sortie au JSON ; le schéma lui-même reste porté par
            # la consigne annexée au prompt par BaseAIEngine._prepare_request.
            payload["format"] = "json"

        return payload

    def _invoke(self, request: AIRequest, model: str) -> ProviderResult:
        exchange = execute_provider_post(
            f"{self.base_url()}/api/generate",
            self.build_payload(request, model),
            provider="Ollama",
            timeout=self.resolve_timeouts(request),
            connection_hint=_CONNECTION_HINT,
            timeout_hint=_TIMEOUT_HINT,
            model=model,
        )
        data = exchange.payload
        envelope = exchange.envelope

        if "response" not in data:
            error = AIResponseError(
                "Réponse Ollama inattendue : champ 'response' absent. "
                f"Clés reçues : {sorted(data.keys())}"
            )
            error.classification = CLASS_MISSING_PROVIDER_FIELD
            apply_envelope_to_error(error, envelope)
            persist_current_failure(classification=CLASS_MISSING_PROVIDER_FIELD)
            raise error

        input_tokens = data.get("prompt_eval_count")
        output_tokens = data.get("eval_count")

        envelope.provider_envelope_valid = True
        return ProviderResult(
            text=str(data["response"]).strip(),
            input_tokens=int(input_tokens) if input_tokens is not None else None,
            output_tokens=int(output_tokens) if output_tokens is not None else None,
            finish_reason=data.get("done_reason"),
            model=data.get("model") or model,
            http_envelope=envelope,
            raw_usage={
                key: data[key]
                for key in (
                    "prompt_eval_count",
                    "eval_count",
                    "total_duration",
                    "load_duration",
                    "eval_duration",
                )
                if key in data
            },
        )
