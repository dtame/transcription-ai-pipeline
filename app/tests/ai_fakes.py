"""
Doubles de test de la couche IA — aucun réseau, aucun SDK réel.

Deux familles :

    FakeHttpResponse / RecordingPost
        remplacent requests.post pour Ollama, LM Studio et Anthropic.
        RecordingPost enregistre url, payload, headers et timeout : c'est ce
        qui permet de vérifier qu'aucune métadonnée interne ne part sur le
        réseau, et que num_ctx vient bien des capacités du modèle.

    FakeOpenAIClient
        reproduit la forme d'objet du SDK OpenAI (choices/message/usage)
        sans importer openai ni posséder de clé.

Aucun de ces doubles n'ouvre de socket : la suite pytest tourne sans OpenAI,
sans Anthropic, sans Ollama, sans LM Studio et sans Internet.
"""

from __future__ import annotations

import json
from typing import Any, Sequence


# ---------------------------------------------------------------------------
# Transport HTTP simulé
# ---------------------------------------------------------------------------

class FakeHttpResponse:
    """Réponse minimale compatible avec ce que lit app/ai/providers/_http.py."""

    def __init__(
        self,
        payload: Any = None,
        *,
        status_code: int = 200,
        text: str | None = None,
        json_error: bool = False,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
    ) -> None:
        self._payload = payload if payload is not None else {}
        self.status_code = status_code
        self._json_error = json_error
        self.headers = {str(key): str(value) for key, value in (headers or {}).items()}
        if content is not None:
            self._content = content
        elif json_error:
            self._content = (text or "{not-valid-json").encode("utf-8")
        elif text is not None:
            self._content = text.encode("utf-8")
        else:
            self._content = json.dumps(self._payload).encode("utf-8")
        self.text = text if text is not None else self._content.decode("utf-8", errors="replace")

    @property
    def content(self) -> bytes:
        return self._content

    def json(self) -> Any:
        if self._json_error:
            raise ValueError("corps non JSON")

        return self._payload


class RecordingPost:
    """
    Remplaçant de requests.post qui enregistre les appels.

    `responses` est consommée dans l'ordre ; un élément Exception est levé au
    lieu d'être retourné, ce qui permet de scénariser « timeout puis succès ».
    Le dernier élément est rejoué si la liste est épuisée.
    """

    def __init__(self, responses: Sequence[Any]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.calls: list[dict] = []

    def __call__(self, url, json=None, timeout=None, headers=None, **kwargs):
        self.calls.append(
            {
                "url": url,
                "payload": json,
                "timeout": timeout,
                "headers": headers,
            }
        )

        index = min(self._index, len(self._responses) - 1)
        self._index += 1
        item = self._responses[index]

        if isinstance(item, BaseException):
            raise item

        return item

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def last_payload(self) -> dict:
        return self.calls[-1]["payload"]

    @property
    def last_headers(self) -> dict:
        return self.calls[-1]["headers"] or {}


def ollama_response(
    text: str = "texte généré",
    *,
    prompt_eval_count: int | None = 120,
    eval_count: int | None = 45,
    done_reason: str = "stop",
    model: str = "qwen3:8b",
) -> FakeHttpResponse:
    payload: dict = {"response": text, "model": model, "done_reason": done_reason}

    if prompt_eval_count is not None:
        payload["prompt_eval_count"] = prompt_eval_count

    if eval_count is not None:
        payload["eval_count"] = eval_count

    return FakeHttpResponse(payload)


def openai_style_response(
    text: str = "texte généré",
    *,
    usage: dict | None = None,
    finish_reason: str = "stop",
    model: str = "local-model",
    response_id: str = "chatcmpl-test",
) -> FakeHttpResponse:
    payload: dict = {
        "id": response_id,
        "model": model,
        "choices": [
            {
                "message": {"role": "assistant", "content": text},
                "finish_reason": finish_reason,
            }
        ],
    }

    if usage is not None:
        payload["usage"] = usage

    return FakeHttpResponse(payload)


def anthropic_response(
    text: str = "texte généré",
    *,
    input_tokens: int | None = 200,
    output_tokens: int | None = 80,
    stop_reason: str = "end_turn",
    model: str = "test-model",
    response_id: str = "msg_test",
) -> FakeHttpResponse:
    payload: dict = {
        "id": response_id,
        "model": model,
        "stop_reason": stop_reason,
        "content": [{"type": "text", "text": text}],
    }

    usage: dict = {}
    if input_tokens is not None:
        usage["input_tokens"] = input_tokens
    if output_tokens is not None:
        usage["output_tokens"] = output_tokens

    if usage:
        payload["usage"] = usage

    return FakeHttpResponse(payload)


# ---------------------------------------------------------------------------
# SDK OpenAI simulé
# ---------------------------------------------------------------------------

class FakeUsage:
    def __init__(self, prompt_tokens=None, completion_tokens=None, total_tokens=None):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content, finish_reason="stop"):
        self.message = FakeMessage(content)
        self.finish_reason = finish_reason


class FakeCompletion:
    def __init__(
        self,
        content="texte généré",
        *,
        finish_reason="stop",
        usage=None,
        response_id="chatcmpl-test",
        model="gpt-4o-mini",
    ):
        self.choices = [FakeChoice(content, finish_reason)]
        self.usage = usage
        self.id = response_id
        self.model = model


class _FakeCompletions:
    def __init__(self, owner):
        self._owner = owner

    def create(self, **kwargs):
        self._owner.calls.append(kwargs)

        if self._owner.error is not None:
            raise self._owner.error

        return self._owner.completion


class _FakeChat:
    def __init__(self, owner):
        self.completions = _FakeCompletions(owner)


class FakeOpenAIClient:
    """
    Double du client OpenAI, injecté via OpenAIEngine(client=...).

    N'exige aucune clé et n'ouvre aucune connexion : la construction du vrai
    client n'a jamais lieu.
    """

    def __init__(self, completion=None, error: BaseException | None = None):
        self.completion = completion if completion is not None else FakeCompletion()
        self.error = error
        self.calls: list[dict] = []
        self.chat = _FakeChat(self)


class FakeRateLimitError(Exception):
    """Reproduit le NOM de classe du SDK, seul critère de traduction."""


class RateLimitError(FakeRateLimitError):
    """Nom exact attendu par la table de traduction d'erreurs."""


class AuthenticationError(Exception):
    pass


class APITimeoutError(Exception):
    pass


class BadRequestError(Exception):
    pass


class StatusOnlyError(Exception):
    """Erreur inconnue de la table, reconnue par son seul code HTTP."""

    def __init__(self, message="erreur", status_code=503):
        super().__init__(message)
        self.status_code = status_code
