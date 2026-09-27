"""
FakeAIEngine — moteur simulé, sans réseau ni modèle.

Deux usages, volontairement séparés :

1. Compatibilité V1
   Sans script, le moteur produit exactement le Markdown simulé de la V1.
   `AI_PROVIDER = "fake"` se comporte comme avant, au caractère près.

2. Banc d'essai des phases suivantes
   Avec un script, il pilote tout ce dont un test a besoin : texte, usage
   tokens, finish_reason, request_id, latence, et erreurs — y compris la
   séquence « échec transitoire puis succès » qui valide le rejeu.

La latence est VIRTUELLE : une horloge interne avance du nombre de secondes
demandé sans que personne n'attende. Une suite de tests ne doit jamais payer
en temps réel la simulation d'un appel lent.

C'est ce provider qui permettra de tester intégralement les Phases 3 à 5
sans OpenAI, sans Anthropic, sans Ollama et sans Internet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Sequence

from app.ai.contracts import AIRequest
from app.ai.providers.base import BaseAIEngine, ProviderResult
from app.ai.retry import no_delay_policy

DEFAULT_FAKE_MODEL = "fake-model"

# Réponse historique de la V1 : conservée telle quelle.
_V1_SEND_PROMPT_HEADER = (
    "# Document traité (simulation)\n\n"
    "> Ce document a été traité par le moteur IA simulé (FakeAIEngine).\n"
    "> Aucune transformation réelle n'a été appliquée.\n\n"
)


@dataclass
class FakeReply:
    """Une réponse programmée. Tous les champs d'AIResponse sont pilotables."""

    text: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    finish_reason: str | None = "stop"
    request_id: str | None = None
    model: str | None = None
    latency_seconds: float = 0.0
    raw_usage: dict = field(default_factory=dict)
    thinking_tokens: int | None = None
    parsed: Any = None


class FakeAIEngine(BaseAIEngine):
    """
    Moteur simulé pour les tests et le développement.
    Ne nécessite aucune API ni modèle local.
    Activer avec : AI_PROVIDER = "fake"
    """

    provider_name = "fake"

    def __init__(
        self,
        *,
        script: Sequence[FakeReply | BaseException] | None = None,
        text: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> None:
        # Sans politique explicite, le fake ne dort jamais : c'est la raison
        # d'être de ce provider dans une suite de tests.
        kwargs.setdefault("retry_policy", no_delay_policy())

        self._virtual_now = 0.0
        kwargs.setdefault("clock", lambda: self._virtual_now)

        super().__init__(model=model or DEFAULT_FAKE_MODEL, **kwargs)

        if script is None and text is not None:
            script = [
                FakeReply(
                    text=text,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
            ]

        self._script: list = list(script) if script else []
        self._index = 0

        # Journal des requêtes reçues : permet de vérifier ce qui a été envoyé
        # (prompt enrichi d'une consigne JSON, température, modèle…).
        self.requests: list[AIRequest] = []

    # -- Introspection de test --------------------------------------------

    @property
    def call_count(self) -> int:
        return len(self.requests)

    @property
    def last_request(self) -> AIRequest | None:
        return self.requests[-1] if self.requests else None

    def config_model(self) -> str:
        return DEFAULT_FAKE_MODEL

    def config_temperature(self) -> float | None:
        return None

    # -- Transport simulé --------------------------------------------------

    def _next_scripted(self):
        """
        Élément suivant du script.

        Le dernier élément est rejoué indéfiniment : un test qui programme
        une seule réponse peut appeler le moteur plusieurs fois sans avoir à
        dupliquer sa fixture.
        """
        if not self._script:
            return None

        index = min(self._index, len(self._script) - 1)
        self._index += 1

        return self._script[index]

    def _invoke(self, request: AIRequest, model: str) -> ProviderResult:
        self.requests.append(request)

        scripted = self._next_scripted()

        if isinstance(scripted, BaseException):
            raise scripted

        if scripted is None:
            return ProviderResult(
                text=_V1_SEND_PROMPT_HEADER + request.prompt[-1000:],
                model=model,
            )

        # Latence virtuelle : on avance l'horloge, on n'attend pas.
        self._virtual_now += float(scripted.latency_seconds)

        text = scripted.text
        if scripted.parsed is not None:
            text = json.dumps(scripted.parsed, ensure_ascii=False)

        return ProviderResult(
            text=text,
            input_tokens=scripted.input_tokens,
            output_tokens=scripted.output_tokens,
            total_tokens=scripted.total_tokens,
            finish_reason=scripted.finish_reason,
            request_id=scripted.request_id,
            model=scripted.model or model,
            raw_usage=dict(scripted.raw_usage),
            thinking_tokens=scripted.thinking_tokens,
        )

    # -- Compatibilité V1 --------------------------------------------------

    def process(self, text: str, project_name: str | None = None) -> str:
        return f"""# Traitement IA simulé

> Ce chunk a été traité par le moteur IA simulé (FakeAIEngine).
> Aucune transformation réelle n'a été appliquée.

## Contenu original

{text}
"""
