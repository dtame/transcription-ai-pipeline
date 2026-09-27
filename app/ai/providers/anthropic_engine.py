"""
AnthropicEngine — API Messages d'Anthropic, via HTTP direct.

Le SDK `anthropic` n'est pas installé dans ce projet et la Phase 2 ne
l'installe pas : le provider parle directement à l'API Messages avec
`requests`, déjà présent dans requirements.txt. Aucune dépendance nouvelle,
et le provider est réellement fonctionnel dès qu'une clé est fournie — pas
seulement « préparé ».

Trois particularités d'Anthropic, prises en charge ici :

    max_tokens est OBLIGATOIRE dans la requête. À défaut de valeur explicite,
    on utilise le plafond de sortie des capacités du modèle.

    le system prompt est un champ de premier niveau, pas un message.

    Structured Outputs natif (Phase 3B.3) : lorsqu'un AIRequest porte un
    response_schema, celui-ci part RÉELLEMENT dans le payload HTTP sous
    output_config.format = {"type": "json_schema", "schema": ...} — pas
    seulement annexé au prompt. Avant Phase 3B.3, ce moteur ne transmettait
    le schéma NULLE PART (ni ici, ni dans le prompt, faute de mécanisme
    natif), alors que `capabilities.supports_structured_output = True`
    laissait croire le contraire à BaseAIEngine._prepare_request(), qui
    sautait alors le filet de secours (consigne JSON annexée au prompt). Voir
    le rapport Phase 3B.3 pour l'analyse complète des deux échecs réels que
    cette absence a causés. La validation locale (app/ai/structured.py)
    reste néanmoins active dans tous les cas : le contrat provider et le
    contrat applicatif sont vérifiés séparément (défense en profondeur).

    Adaptation du schéma provider (Phase 3B.3.1) : le schéma transmis dans
    output_config.format.schema n'est plus le schéma canonique tel quel,
    mais une copie fermée par prepare_anthropic_json_schema() (voir
    app/ai/providers/_anthropic_schema.py) — Anthropic exige
    "additionalProperties": false sur chaque noeud objet, alors que le
    schéma canonique reste volontairement permissif (pour qu'un champ
    éditorial comme "chapters" produise une fuite explicite plutôt qu'un
    rejet de schéma générique). Le schéma canonique de la requête n'est lui
    jamais modifié : la validation locale (BaseAIEngine.generate()) continue
    de s'appuyer sur request.response_schema original, pas sur cette copie.

Aucun nom de modèle n'est codé en dur : `ANTHROPIC_MODEL` vaut "" par défaut
et l'appel échoue avec un message clair tant qu'un modèle n'a pas été choisi
explicitement. La Phase 2 ne décide pas quel modèle est « le meilleur ».
"""

from __future__ import annotations

import app.config as config

from app.ai.contracts import AIRequest
from app.ai.errors import AIConfigurationError, AIResponseError
from app.ai.provider_forensics import (
    CLASS_INVALID_CONTENT_TYPE,
    CLASS_INVALID_TEXT_BLOCK,
    CLASS_MISSING_CONTENT,
    CLASS_NO_TEXT_BLOCK,
    ProviderHttpEnvelope,
    apply_envelope_to_error,
    anthropic_content_metadata,
    extract_usage_best_effort,
    persist_current_failure,
)
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.ai.providers._anthropic_thinking import attach_request_output_controls
from app.ai.providers._http import execute_provider_post
from app.ai.providers.base import BaseAIEngine, ProviderResult
from app.ai.settings import ENV_ANTHROPIC_API_KEY, require_api_key
from app.ai.thinking import extract_thinking_tokens_from_usage

DEFAULT_BASE_URL = "https://api.anthropic.com"

# Version d'API exigée dans l'en-tête des requêtes Messages.
DEFAULT_API_VERSION = "2023-06-01"


class AnthropicEngine(BaseAIEngine):
    """
    Moteur IA basé sur l'API Messages d'Anthropic (cloud).
    Activer avec : AI_PROVIDER = "anthropic"

    Nécessite la variable d'environnement ANTHROPIC_API_KEY.
    Le modèle doit être choisi explicitement via app.config.ANTHROPIC_MODEL
    ou à la construction du moteur.
    """

    provider_name = "anthropic"

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._api_key = api_key
        self._base_url = base_url

    def base_url(self) -> str:
        return str(
            self._base_url or getattr(config, "ANTHROPIC_BASE_URL", None) or DEFAULT_BASE_URL
        ).rstrip("/")

    def config_model(self) -> str | None:
        return getattr(config, "ANTHROPIC_MODEL", None) or None

    def config_temperature(self) -> float | None:
        return getattr(config, "ANTHROPIC_TEMPERATURE", None)

    def resolve_model(self) -> str:
        try:
            return super().resolve_model()
        except AIConfigurationError as exc:
            raise AIConfigurationError(
                "Aucun modèle Anthropic configuré. Renseignez ANTHROPIC_MODEL "
                "dans app/config.py (ou passez model=... au moteur) après avoir "
                "vérifié le nom exact et le tarif du modèle voulu."
            ) from exc

    def resolve_api_key(self) -> str:
        if self._api_key:
            return self._api_key

        return require_api_key("anthropic", ENV_ANTHROPIC_API_KEY)

    def resolve_max_output_tokens(self, request: AIRequest) -> int:
        """
        Anthropic exige max_tokens : on retombe sur le plafond des capacités.

        Jamais None, à la différence des autres providers où le champ est
        facultatif.
        """
        explicit = super().resolve_max_output_tokens(request)

        if explicit is not None:
            return explicit

        return self.capabilities(request.model or self.resolve_model()).max_output_tokens

    def build_payload(self, request: AIRequest, model: str) -> dict:
        payload = {
            "model": model,
            "max_tokens": self.resolve_max_output_tokens(request),
            "messages": [{"role": "user", "content": request.prompt}],
        }

        if request.system_prompt:
            payload["system"] = request.system_prompt

        temperature = self.resolve_temperature(request)
        if temperature is not None:
            payload["temperature"] = temperature

        if request.wants_structured_output:
            # Structured Outputs natif Anthropic (Phase 3B.3) : le schéma part
            # RÉELLEMENT dans la requête HTTP, sous output_config.format — pas
            # seulement annexé au prompt. Avant cette phase, BaseAIEngine
            # supposait ce mécanisme actif (capabilities.supports_structured_output
            # = True pour anthropic:claude-sonnet-5) et sautait donc l'injection
            # de la consigne JSON dans le prompt (voir base.py._prepare_request),
            # SANS que ce moteur ne transmette jamais le schéma à Anthropic. Le
            # modèle recevait alors une simple phrase (« renvoie ta réponse au
            # format JSON demandé », voir app/source_analysis/prompt.py) sans
            # jamais voir le schéma réel : c'est la cause structurelle des deux
            # échecs réels documentés en Phase 3B.3 (champ requis absent, puis
            # JSON syntaxiquement invalide sur une sortie volumineuse).
            #
            # Le schéma est adapté à la frontière Anthropic (Phase 3B.3.1) :
            # prepare_anthropic_json_schema() en construit une COPIE avec
            # "additionalProperties": false sur chaque objet, exigé par
            # Anthropic Structured Outputs mais volontairement absent du
            # schéma canonique (voir app/ai/providers/_anthropic_schema.py et
            # app/source_analysis/schema.py). request.response_schema — le
            # schéma canonique — n'est jamais modifié : BaseAIEngine.generate()
            # valide toujours la réponse contre l'original, pas contre cette
            # copie (voir app/ai/providers/base.py).
            payload["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": prepare_anthropic_json_schema(request.response_schema),
                }
            }

        attach_request_output_controls(payload, request, model)
        return payload

    def build_headers(self) -> dict:
        return {
            "x-api-key": self.resolve_api_key(),
            "anthropic-version": str(
                getattr(config, "ANTHROPIC_VERSION", None) or DEFAULT_API_VERSION
            ),
            "content-type": "application/json",
        }

    def _invoke(self, request: AIRequest, model: str) -> ProviderResult:
        exchange = execute_provider_post(
            f"{self.base_url()}/v1/messages",
            self.build_payload(request, model),
            provider="Anthropic",
            timeout=self.resolve_timeouts(request),
            headers=self.build_headers(),
            connection_hint="Vérifiez la connectivité réseau vers api.anthropic.com.",
            model=model,
        )
        data = exchange.payload
        envelope = exchange.envelope
        try:
            text = extract_anthropic_text(data, envelope=envelope)
        except AIResponseError as exc:
            apply_envelope_to_error(exc, envelope)
            persist_current_failure(classification=exc.classification)
            raise

        usage = data.get("usage") or {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        envelope.provider_envelope_valid = True

        return ProviderResult(
            text=text,
            input_tokens=int(input_tokens) if input_tokens is not None else None,
            output_tokens=int(output_tokens) if output_tokens is not None else None,
            finish_reason=data.get("stop_reason"),
            request_id=envelope.request_id or data.get("id"),
            model=data.get("model") or model,
            raw_usage=dict(usage) if isinstance(usage, dict) else {},
            thinking_tokens=extract_thinking_tokens_from_usage(usage),
            http_envelope=envelope,
        )


def extract_anthropic_text(
    data: dict,
    *,
    envelope: ProviderHttpEnvelope | None = None,
) -> str:
    """
    Concatène les blocs de texte de la réponse Messages.

    Usage / stop_reason / métadonnées de content sont extraits en best-effort
    AVANT le rejet. Un bloc `text` n'est valide que si `text` est une chaîne.
    """
    if envelope is not None:
        extract_usage_best_effort(envelope, data)
        try:
            envelope.content_metadata = anthropic_content_metadata(data)
        except Exception:
            pass

    if not isinstance(data, dict):
        error = AIResponseError(
            "Réponse Anthropic inattendue : objet JSON attendu, "
            f"{type(data).__name__} reçu."
        )
        error.classification = "INVALID_RESPONSE_TOP_LEVEL"
        raise error

    if "content" not in data:
        error = AIResponseError(
            "Réponse Anthropic inattendue : champ 'content' absent. "
            f"Clés reçues : {sorted(data.keys())}"
        )
        error.classification = CLASS_MISSING_CONTENT
        if envelope is not None:
            apply_envelope_to_error(error, envelope)
        raise error

    blocks = data.get("content")
    if not isinstance(blocks, list):
        error = AIResponseError(
            "Réponse Anthropic inattendue : champ 'content' absent ou non listé. "
            f"Clés reçues : {sorted(data.keys())}"
        )
        error.classification = CLASS_INVALID_CONTENT_TYPE
        if envelope is not None:
            apply_envelope_to_error(error, envelope)
        raise error

    text_blocks = [
        block
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    if not text_blocks:
        error = AIResponseError(
            "Réponse Anthropic sans bloc de texte exploitable "
            f"(stop_reason={data.get('stop_reason')})."
        )
        error.classification = CLASS_NO_TEXT_BLOCK
        if envelope is not None:
            apply_envelope_to_error(error, envelope)
        raise error

    parts: list[str] = []
    malformed = False
    for block in text_blocks:
        text = block.get("text")
        if not isinstance(text, str):
            malformed = True
            continue
        parts.append(text)

    if malformed or not parts:
        error = AIResponseError(
            "Réponse Anthropic : bloc de texte malformé "
            f"(stop_reason={data.get('stop_reason')})."
        )
        error.classification = CLASS_INVALID_TEXT_BLOCK
        if envelope is not None:
            apply_envelope_to_error(error, envelope)
        raise error

    return "".join(parts).strip()


def _extract_text(data: dict) -> str:
    """Alias production historique — même parseur que extract_anthropic_text."""
    return extract_anthropic_text(data)
