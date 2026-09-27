"""
Hiérarchie d'erreurs de la couche IA.

Toutes les erreurs dérivent de RuntimeError : les appelants V1
(ai_processor, global_editor_service, editorial_transformer) attrapent
déjà `Exception` / `RuntimeError` autour de send_prompt(). Le contrat de
levée de la V1 est donc préservé, tout en permettant aux nouveaux
appelants de distinguer les cas.

La distinction structurante est **transitoire ou non** :

    AITransientError  -> l'appel PEUT être rejoué (timeout, 429, 5xx, réseau)
    tout le reste     -> rejouer serait inutile ou nuisible

C'est cette distinction, et elle seule, que consulte app/ai/retry.py.
"""

from __future__ import annotations

from typing import Any


class AIError(RuntimeError):
    """
    Racine de toutes les erreurs de la couche IA.

    `response` (Phase 3B.2) : None par défaut. `BaseAIEngine.generate()` y
    attache l'AIResponse partielle (parsed=None, mais usage/latence/provider/
    modèle/request_id déjà connus) lorsqu'une AIError survient APRÈS un appel
    transport réussi — typiquement une AIStructuredOutputError levée par le
    décodage ou la validation de la sortie structurée. Cela permet à
    l'appelant (CostTracker.record_failure) de conserver l'usage RÉEL d'un
    appel qui a été effectué — et potentiellement facturé — même si son
    résultat métier est inexploitable. Reste None pour toute erreur survenue
    AVANT ou PENDANT le transport (aucun ProviderResult n'existe encore).

    `http_envelope` (Phase 3B.7.7A.5) : enveloppe HTTP capturée dès qu'une
    réponse a été reçue, indépendamment de ProviderResult / AIResponse.
    """

    response: Any = None
    http_envelope: Any = None
    classification: str | None = None
    post_attempted: bool | None = None
    response_received: bool | None = None
    http_status: int | None = None
    request_id: str | None = None
    elapsed_ms: int | None = None
    forensic_path: str | None = None
    raw_sha256: str | None = None
    raw_size: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    usage_source: str | None = None
    finish_reason: str | None = None
    provider: str | None = None
    model: str | None = None


# ---------------------------------------------------------------------------
# Erreurs non rejouables — la configuration ou la requête est fautive
# ---------------------------------------------------------------------------

class AIConfigurationError(AIError):
    """Configuration absente ou incohérente (modèle non défini, clé manquante)."""


class AIAuthenticationError(AIConfigurationError):
    """Credentials refusés par le fournisseur (401/403). Rejouer est inutile."""


class AIProviderUnavailableError(AIConfigurationError):
    """SDK ou dépendance du fournisseur absent de l'environnement."""


class AIRequestError(AIError):
    """Requête invalide côté fournisseur (400/404/422). Rejouer est inutile."""


class AIResponseError(AIError):
    """
    Réponse du fournisseur illisible ou de structure inattendue.

    Observabilité (Phase 3B.7.7A.5) — `classification` précise la branche
    (INVALID_RESPONSE_JSON, MISSING_CONTENT, NO_TEXT_BLOCK, …). Le message
    ne contient jamais le corps brut. Les métadonnées sûres (status,
    request_id, usage, SHA, chemin forensics) voyagent sur l'instance.
    """

    def diagnostics(self) -> dict[str, Any]:
        """Métadonnées sérialisables. Jamais le corps brut, jamais de secret."""
        return {
            "error_type": type(self).__name__,
            "classification": self.classification,
            "provider": self.provider,
            "model": self.model,
            "http_status": self.http_status,
            "request_id": self.request_id,
            "elapsed_ms": self.elapsed_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "usage_source": self.usage_source,
            "finish_reason": self.finish_reason,
            "raw_sha256": self.raw_sha256,
            "raw_size": self.raw_size,
            "forensic_path": self.forensic_path,
            "post_attempted": self.post_attempted,
            "response_received": self.response_received,
            "message": str(self),
        }


class AIStructuredOutputError(AIError):
    """
    Une sortie structurée a été demandée mais le texte reçu n'est pas un JSON
    valide, ou ne respecte pas le schéma fourni.

    Jamais rejouée automatiquement en Phase 2 : aucune « réparation » de JSON
    par un second appel LLM n'est tentée.

    Observabilité (Phase 3B.7.7A.1) — attributs optionnels, None par défaut.
    Ils ne changent pas le contrat sémantique. `response` (hérité) reste le
    porteur du texte brut ; les champs ci-dessous sont des métadonnées
    extractibles sans relire le texte :

        parse_failure_kind    empty / json_decode / schema
        finish_reason         stop_reason provider, si connu
        request_id            id provider, si connu
        input_tokens / output_tokens / total_tokens / usage_source
        raw_text_sha256 / raw_text_bytes / raw_text_chars
        json_decode_msg / json_decode_lineno / json_decode_colno
    """

    parse_failure_kind: str | None = None
    raw_text_sha256: str | None = None
    raw_text_bytes: int | None = None
    raw_text_chars: int | None = None
    json_decode_msg: str | None = None
    json_decode_lineno: int | None = None
    json_decode_colno: int | None = None

    def attach_response_diagnostics(self, response: Any) -> None:
        """Copie les métadonnées provider depuis une AIResponse. Pas le texte."""
        if response is None:
            return
        self.finish_reason = getattr(response, "finish_reason", None)
        self.request_id = getattr(response, "request_id", None)
        self.input_tokens = getattr(response, "input_tokens", None)
        self.output_tokens = getattr(response, "output_tokens", None)
        self.total_tokens = getattr(response, "total_tokens", None)
        self.usage_source = getattr(response, "usage_source", None)
        text = getattr(response, "text", None)
        if isinstance(text, str):
            encoded = text.encode("utf-8")
            self.raw_text_chars = len(text)
            self.raw_text_bytes = len(encoded)
            if self.raw_text_sha256 is None:
                import hashlib

                self.raw_text_sha256 = hashlib.sha256(encoded).hexdigest()

    def diagnostics(self) -> dict[str, Any]:
        """Métadonnées sérialisables. Jamais le texte brut, jamais de secret."""
        return {
            "error_type": type(self).__name__,
            "parse_failure_kind": self.parse_failure_kind,
            "finish_reason": self.finish_reason,
            "request_id": self.request_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "usage_source": self.usage_source,
            "raw_text_sha256": self.raw_text_sha256,
            "raw_text_bytes": self.raw_text_bytes,
            "raw_text_chars": self.raw_text_chars,
            "json_decode_msg": self.json_decode_msg,
            "json_decode_lineno": self.json_decode_lineno,
            "json_decode_colno": self.json_decode_colno,
            "message": str(self),
        }


# ---------------------------------------------------------------------------
# Erreurs transitoires — rejouables
# ---------------------------------------------------------------------------

class AITransientError(AIError):
    """Incident passager : l'appel peut être rejoué avec un backoff."""


class AITimeoutError(AITransientError):
    """
    Le fournisseur n'a pas répondu dans le délai imparti.

    Métadonnées optionnelles (Phase 3B.5.1), backward-compatibles :

        timeout_kind              connect / read / unknown
        connect_timeout_seconds   timeout connect effectif, si connu
        read_timeout_seconds      timeout read effectif, si connu
        elapsed_ms                durée monotone du transport HTTP, si mesurée

    `response` reste None lorsqu'aucun body n'a été reçu.
    """

    timeout_kind: str = "unknown"
    connect_timeout_seconds: float | None = None
    read_timeout_seconds: float | None = None
    elapsed_ms: int | None = None

    def __init__(
        self,
        message: str,
        *,
        timeout_kind: str = "unknown",
        connect_timeout_seconds: float | None = None,
        read_timeout_seconds: float | None = None,
        elapsed_ms: int | None = None,
    ) -> None:
        super().__init__(message)
        self.timeout_kind = timeout_kind
        self.connect_timeout_seconds = connect_timeout_seconds
        self.read_timeout_seconds = read_timeout_seconds
        self.elapsed_ms = elapsed_ms
        self.response_received = False
        self.classification = "HTTP_TRANSPORT_FAILURE"


class AIConnectionError(AITransientError):
    """Le fournisseur est injoignable (service local arrêté, réseau coupé)."""

    response_received = False
    classification = "HTTP_TRANSPORT_FAILURE"


class AIRateLimitError(AITransientError):
    """Quota temporairement dépassé (429)."""


class AIServerError(AITransientError):
    """Erreur interne du fournisseur (5xx)."""


def is_retryable(error: BaseException) -> bool:
    """Seules les erreurs transitoires de la couche IA sont rejouables."""
    return isinstance(error, AITransientError)
