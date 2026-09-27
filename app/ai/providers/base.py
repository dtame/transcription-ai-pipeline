"""
BaseAIEngine — interface commune à tous les moteurs IA.

C'est l'abstraction V1 du projet, CONSERVÉE et étendue plutôt que remplacée.
Ce qui change :

    avant   send_prompt(prompt) -> str          était abstraite
    après   generate(request)   -> AIResponse   est le contrat réel
            send_prompt(prompt) -> str          devient un adaptateur legacy

Les quatre appelants V1 (ai_processor, global_editor_service,
editorial_transformer et leurs tests) continuent d'appeler send_prompt() et
de recevoir exactement la même chaîne qu'avant. Aucun d'eux n'est modifié.

Un provider n'implémente qu'une méthode : `_invoke()`. Tout ce qui est commun
— résolution du modèle, chronométrage, rejeu, consignes JSON, décodage de la
sortie structurée, journalisation — vit ici, en un seul exemplaire.

Chaîne d'un appel :

    caller
      ↓  AIRequest
    BaseAIEngine.generate()        latence, retry, structured output, logs
      ↓  ProviderResult
    <Provider>._invoke()           payload et transport spécifiques
      ↓
    AIResponse                     texte + usage réel + métadonnées
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Mapping

import app.config as config

from app.ai.capabilities import ModelCapabilities, resolve_capabilities
from app.ai.contracts import AIRequest, AIResponse
from app.ai.errors import AIConfigurationError, AIError
from app.ai.retry import RetryPolicy, RetryTrace, call_with_retry, default_retry_policy
from app.ai.settings import default_timeout_seconds
from app.ai.timeouts import AITimeoutConfig, resolve_ai_timeouts
from app.ai.structured import build_json_instruction, parse_structured_output
from app.logger import log_event
from app.prompt_manager import build_prompt as _build_prompt


@dataclass(frozen=True)
class ProviderResult:
    """
    Ce qu'un provider extrait de sa réponse brute.

    Les compteurs de tokens sont ceux RAPPORTÉS par le fournisseur. Un
    provider ne re-tokenise jamais le texte pour fabriquer un chiffre :
    absent veut dire None, et le coût sera marqué inconnu plus loin.
    """

    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    finish_reason: str | None = None
    request_id: str | None = None
    model: str | None = None
    raw_usage: Mapping[str, Any] = field(default_factory=dict)
    thinking_tokens: int | None = None
    http_envelope: Any = None


class BaseAIEngine(ABC):
    """Interface commune pour tous les moteurs IA."""

    # Nom sous lequel le provider apparaît dans les rapports et le registre.
    provider_name: str = "base"

    def __init__(
        self,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        timeout_seconds: float | None = None,
        connect_timeout_seconds: float | None = None,
        retry_policy: RetryPolicy | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds
        self._connect_timeout_seconds = connect_timeout_seconds
        self._retry_policy = retry_policy
        # Horloge MONOTONE : la latence mesurée ne doit pas sauter si
        # l'horloge système est ajustée pendant un appel long.
        self._clock = clock or time.monotonic

    # -- Configuration résolue à l'appel ----------------------------------

    def resolve_model(self) -> str:
        """Modèle effectif : celui de l'instance, sinon celui de la configuration."""
        model = self._model or self.config_model()

        if not model:
            raise AIConfigurationError(
                f"Aucun modèle configuré pour le fournisseur « {self.provider_name} »."
            )

        return str(model)

    def config_model(self) -> str | None:
        """Modèle par défaut du provider, lu dans app/config.py."""
        return None

    def resolve_temperature(self, request: AIRequest) -> float | None:
        if request.temperature is not None:
            return float(request.temperature)

        if self._temperature is not None:
            return float(self._temperature)

        return self.config_temperature()

    def config_temperature(self) -> float | None:
        return None

    def resolve_max_output_tokens(self, request: AIRequest) -> int | None:
        if request.max_output_tokens is not None:
            return int(request.max_output_tokens)

        if self._max_output_tokens is not None:
            return int(self._max_output_tokens)

        return None

    def resolve_timeout(self, request: AIRequest) -> float:
        """Read timeout effectif. Conservé pour compatibilité ; préférer resolve_timeouts()."""
        return self.resolve_timeouts(request).read_seconds

    def resolve_timeouts(self, request: AIRequest) -> AITimeoutConfig:
        """Connect et read distincts, avec sources de configuration."""
        provider_timeout = self.config_timeout()
        custom_provider = provider_timeout != default_timeout_seconds()
        return resolve_ai_timeouts(
            stage=request.stage,
            request_timeout_seconds=request.timeout_seconds,
            engine_read_timeout_seconds=self._timeout_seconds,
            engine_connect_timeout_seconds=self._connect_timeout_seconds,
            provider_read_timeout_seconds=provider_timeout if custom_provider else None,
        )

    def config_timeout(self) -> float:
        return default_timeout_seconds()

    @property
    def retry_policy(self) -> RetryPolicy:
        return self._retry_policy or default_retry_policy()

    def capabilities(self, model: str | None = None) -> ModelCapabilities:
        """Capacités du modèle : fenêtre de contexte, plafond de sortie, options."""
        return resolve_capabilities(self.provider_name, model or self.resolve_model())

    # -- Contrat principal -------------------------------------------------

    def generate(self, request: AIRequest) -> AIResponse:
        """
        Exécute une requête et retourne une réponse normalisée.

        La latence mesurée couvre l'appel complet, rejeux compris : c'est le
        temps réellement passé par l'appelant à attendre, qui est ce qu'un
        rapport d'observabilité doit montrer.
        """
        model = request.model or self.resolve_model()
        prepared = self._prepare_request(request, model)
        trace = RetryTrace()
        timeouts = self.resolve_timeouts(prepared)

        self._log(
            "ai_call_started",
            request=request,
            model=model,
            prompt_chars=len(request.prompt),
            connect_timeout_seconds=timeouts.connect_seconds,
            read_timeout_seconds=timeouts.read_seconds,
        )

        started = self._clock()

        try:
            result = call_with_retry(
                lambda: self._invoke(prepared, model),
                self.retry_policy,
                trace,
            )
        except AIError as exc:
            self._log(
                "ai_call_failed",
                request=request,
                model=model,
                latency_ms=self._elapsed_ms(started),
                attempts=trace.attempts,
                error_type=type(exc).__name__,
                classification=getattr(exc, "classification", None),
                http_status=getattr(exc, "http_status", None),
                request_id=getattr(exc, "request_id", None),
                raw_sha256=getattr(exc, "raw_sha256", None),
                raw_size=getattr(exc, "raw_size", None),
                input_tokens=getattr(exc, "input_tokens", None),
                output_tokens=getattr(exc, "output_tokens", None),
                finish_reason=getattr(exc, "finish_reason", None),
                response_received=getattr(exc, "response_received", None),
                post_attempted=getattr(exc, "post_attempted", None),
            )
            raise

        latency_ms = self._elapsed_ms(started)

        # Construite AVANT la tentative de décodage structuré, et volontairement
        # complète (usage, latence, provider, modèle, request_id…) sauf pour
        # `parsed` : le transport a réussi et le fournisseur a été contacté —
        # et potentiellement facturé — quoi qu'il arrive au décodage qui suit.
        # Si celui-ci échoue, cette même AIResponse (parsed=None) est attachée
        # à l'exception levée : c'est ce qui permet à l'appelant de conserver
        # l'usage RÉEL d'un appel dont seule la sortie structurée est en
        # cause, au lieu de le perdre avec l'exception (voir Phase 3B.2).
        envelope = getattr(result, "http_envelope", None)
        if envelope is not None:
            envelope.airesponse_created = True
            if result.request_id is None and getattr(envelope, "request_id", None):
                result = replace(result, request_id=envelope.request_id)

        compact_meta = dict(request.metadata)
        if envelope is not None:
            compact_meta["provider_http"] = {
                "response_received": envelope.response_received,
                "http_success": envelope.http_success,
                "http_status": envelope.http_status,
                "request_id": envelope.request_id,
                "raw_sha256": envelope.raw_sha256,
                "raw_size": envelope.raw_size,
            }

        response = AIResponse(
            text=result.text,
            parsed=None,
            provider=self.provider_name,
            model=result.model or model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
            latency_ms=latency_ms,
            finish_reason=result.finish_reason,
            request_id=result.request_id,
            raw_usage=dict(result.raw_usage),
            thinking_tokens=result.thinking_tokens,
            metadata=compact_meta,
        )

        try:
            parsed = (
                parse_structured_output(result.text, request.response_schema)
                if request.wants_structured_output
                else None
            )
        except AIError as exc:
            # L'appel a réussi côté transport (voir plus haut) : son usage ne
            # doit pas disparaître avec l'exception. Transporté sur l'instance
            # plutôt que dans un type d'exception dédié, pour que TOUTE
            # AIError levée ici — présente ou future — profite du même filet,
            # sans registre de traduction supplémentaire à maintenir.
            exc.response = response
            attach = getattr(exc, "attach_response_diagnostics", None)
            if callable(attach):
                attach(response)
            if envelope is not None:
                from app.ai.provider_forensics import (
                    apply_envelope_to_error,
                    persist_current_failure,
                )

                apply_envelope_to_error(exc, envelope)
                persist_current_failure(
                    classification=getattr(exc, "classification", None)
                )
            self._log(
                "ai_call_failed",
                request=request,
                model=model,
                latency_ms=latency_ms,
                attempts=trace.attempts,
                error_type=type(exc).__name__,
                usage_source=response.usage_source,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                finish_reason=response.finish_reason,
                request_id=response.request_id,
                parse_failure_kind=getattr(exc, "parse_failure_kind", None),
                raw_text_sha256=getattr(exc, "raw_text_sha256", None),
                raw_text_bytes=getattr(exc, "raw_text_bytes", None),
                raw_text_chars=getattr(exc, "raw_text_chars", None),
            )
            raise

        response = replace(response, parsed=parsed)

        self._log(
            "ai_call_completed",
            request=request,
            model=response.model,
            latency_ms=latency_ms,
            attempts=trace.attempts,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            usage_source=response.usage_source,
            finish_reason=response.finish_reason,
        )

        return response

    @abstractmethod
    def _invoke(self, request: AIRequest, model: str) -> ProviderResult:
        """
        Envoie la requête au fournisseur et normalise sa réponse.

        Seule méthode à implémenter par un provider. Doit traduire ses
        incidents en erreurs de app/ai/errors.py — c'est ce qui décide si
        l'appel sera rejoué.
        """

    # -- Préparation -------------------------------------------------------

    def supports_native_structured_output(self, model: str) -> bool:
        """
        True si le fournisseur sait contraindre sa sortie au JSON lui-même.

        Sinon la consigne JSON est annexée au prompt par _prepare_request().
        """
        return self.capabilities(model).supports_structured_output

    def _prepare_request(self, request: AIRequest, model: str) -> AIRequest:
        """
        Adapte la requête aux limites du fournisseur avant transmission.

        N'ajoute la consigne JSON que si le fournisseur ne sait pas contraindre
        sa sortie nativement : sur un modèle qui le sait, la consigne ne ferait
        que consommer du contexte.
        """
        if not request.wants_structured_output:
            return request

        if self.supports_native_structured_output(model):
            return request

        instruction = build_json_instruction(request.response_schema)

        return request.with_prompt(f"{request.prompt}\n\n{instruction}")

    # -- Journalisation ----------------------------------------------------

    def _log(self, event: str, *, request: AIRequest, model: str, **fields) -> None:
        """
        Journalise un événement d'appel IA.

        Ce qui est journalisé : étape, fournisseur, modèle, latence, usage,
        et la TAILLE du prompt. Ce qui ne l'est jamais : la clé API, le
        prompt, le system prompt, le texte généré. Un fichier de log ne doit
        ni fuiter le contenu d'un projet ni peser des mégaoctets par appel.
        """
        payload = {
            "event": event,
            "stage": request.stage,
            "provider": self.provider_name,
            "model": model,
        }
        payload.update({key: value for key, value in fields.items() if value is not None})

        log_event(payload)

    def _elapsed_ms(self, started: float) -> int:
        return max(0, int((self._clock() - started) * 1000))

    # -- Compatibilité V1 --------------------------------------------------

    def send_prompt(self, prompt: str) -> str:
        """
        Envoie un prompt pré-construit au moteur IA et retourne la réponse brute.

        Chemin legacy conservé tel quel pour la V1 : même signature, même type
        de retour, même contenu. Il délègue désormais à generate() et n'expose
        que `.text`, ce qui évite d'avoir deux implémentations de transport.
        """
        return self.generate(AIRequest(prompt=prompt)).text

    def build_prompt(self, text: str, project_name: str | None = None) -> str:
        """
        Construit le prompt final.

        Priorité :
            1. depot/<project_name>/prompt.md si project_name fourni
            2. template AI_TASK défini dans config.py
        """
        return _build_prompt(config.AI_TASK, text, project_name=project_name)

    def process(self, text: str, project_name: str | None = None) -> str:
        """Traite un texte brut et retourne un contenu Markdown structuré."""
        prompt = self.build_prompt(text, project_name=project_name)
        return self.send_prompt(prompt)
