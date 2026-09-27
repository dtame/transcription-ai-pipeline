"""
CostTracker : observabilité d'usage et de coût des appels IA.

Un appel IA produit une ligne structurée (AICallRecord) qui relie
stage → appel → usage → coût. Ces lignes s'agrègent par étape, par
fournisseur, par modèle et au total, et vont alimenter le bloc `ai_usage`
de report.json.

Deux règles de prudence gouvernent tout le module :

    un coût inconnu n'est PAS zéro
        estimated_cost vaut None et cost_status vaut "unknown". Un rapport
        qui affiche 0,00 $ pour un appel non tarifé est un rapport faux.

    un appel échoué ne fabrique PAS d'usage
        pas de tokens inventés, pas de coût supposé : on garde la trace de
        la tentative, son étape, sa latence et le type d'erreur. MAIS un
        appel qui a réellement atteint le fournisseur et reçu un usage RÉEL
        avant d'échouer (ex. sortie structurée invalide APRÈS un HTTP 200)
        conserve cet usage : `record_failure(..., response=...)` (Phase 3B.2)
        ne fabrique rien, il refuse seulement d'oublier ce qui est déjà connu.

Le tracker n'est pas exclusivement tokenisé : `record_units()` accepte
déjà les unités (image, requête, seconde) dont la Phase 7 aura besoin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable, Mapping

from app.ai.contracts import AIResponse, USAGE_UNAVAILABLE
from app.ai.pricing import (
    COST_STATUS_BASE_ESTIMATE,
    COST_STATUS_KNOWN,
    COST_STATUS_LOCAL,
    COST_STATUS_UNKNOWN,
    CURRENCY_USD,
    CostBreakdown,
    PricingCatalog,
    UNIT_TOKENS,
    build_default_catalog,
    unknown_cost,
)

CALL_STATUS_COMPLETED = "completed"
CALL_STATUS_FAILED = "failed"

# Étape par défaut d'un appel qui ne s'est pas annoncé.
UNKNOWN_STAGE = "unknown"

# Étapes que le pipeline pourra rapporter. Phase 2 n'en exécute aucune :
# la liste existe pour que le rapport sache les représenter.
KNOWN_STAGES = (
    "transcription",
    "source_analysis",
    "editorial_planning",
    "book_generation",
    "book_validation",
    "visual_design",
    "image_generation",
    "document_rendering",
)

# Statut d'agrégat lorsqu'aucun appel n'a été enregistré.
COST_STATUS_NO_CALLS = "no_calls"
COST_STATUS_PARTIAL = "partial"


def format_call_id(index: int) -> str:
    """
    Identifiant séquentiel d'appel : CALL000001, CALL000002, …

    Séquentiel et non aléatoire, comme SRC/AUDIO du contrat Transcript V2 :
    un rapport reste diffable et lisible.
    """
    return f"CALL{index:06d}"


@dataclass(frozen=True)
class AICallRecord:
    """
    Trace d'un appel IA. Ne contient ni prompt, ni texte généré.

    Seules des métriques y figurent : ce qui est écrit dans report.json ne
    doit jamais exposer le contenu du projet.
    """

    call_id: str
    stage: str
    provider: str
    model: str
    status: str
    cost: CostBreakdown
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    usage_source: str = USAGE_UNAVAILABLE
    unit: str = UNIT_TOKENS
    unit_count: int | None = None
    latency_ms: int = 0
    finish_reason: str | None = None
    request_id: str | None = None
    error_type: str | None = None
    recorded_at: str = ""

    def to_dict(self) -> dict:
        return {
            "call_id": self.call_id,
            "stage": self.stage,
            "provider": self.provider,
            "model": self.model,
            "status": self.status,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "usage_source": self.usage_source,
            "unit": self.unit,
            "unit_count": self.unit_count,
            "latency_ms": self.latency_ms,
            "finish_reason": self.finish_reason,
            "request_id": self.request_id,
            "error_type": self.error_type,
            "recorded_at": self.recorded_at,
            "cost": self.cost.to_dict(),
        }


def _usage_from_error(
    error: BaseException | str | None,
) -> tuple[int | None, int | None, int | None] | None:
    """Usage best-effort porté par une erreur, sans AIResponse."""
    if error is None or isinstance(error, str):
        return None
    input_tokens = getattr(error, "input_tokens", None)
    output_tokens = getattr(error, "output_tokens", None)
    total_tokens = getattr(error, "total_tokens", None)
    if input_tokens is None and output_tokens is None and total_tokens is None:
        return None
    return input_tokens, output_tokens, total_tokens


class CostTracker:
    """
    Accumulateur d'appels IA d'une session ou d'un projet.

    Sans état persistant : la persistance dans project_state.json est le rôle
    de app/ai/usage_store.py.
    """

    def __init__(
        self,
        catalog: PricingCatalog | None = None,
        *,
        currency: str = CURRENCY_USD,
    ) -> None:
        self.catalog = catalog if catalog is not None else build_default_catalog()
        self.currency = currency
        self._records: list[AICallRecord] = []

    # -- Enregistrement ----------------------------------------------------

    @property
    def records(self) -> list[AICallRecord]:
        return list(self._records)

    @property
    def call_count(self) -> int:
        return len(self._records)

    def _next_call_id(self) -> str:
        return format_call_id(len(self._records) + 1)

    def record_response(
        self,
        response: AIResponse,
        *,
        stage: str | None = None,
    ) -> AICallRecord:
        """
        Enregistre un appel réussi à partir de sa réponse normalisée.

        L'étape provient de l'argument explicite, sinon des métadonnées de la
        réponse (héritées de la requête).
        """
        cost = self.catalog.estimate_cost(
            response.provider,
            response.model,
            response.input_tokens,
            response.output_tokens,
        )

        record = AICallRecord(
            call_id=self._next_call_id(),
            stage=stage or response.stage or UNKNOWN_STAGE,
            provider=response.provider,
            model=response.model,
            status=CALL_STATUS_COMPLETED,
            cost=cost,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            usage_source=response.usage_source,
            latency_ms=response.latency_ms,
            finish_reason=response.finish_reason,
            request_id=response.request_id,
            recorded_at=_now(),
        )

        self._records.append(record)
        return record

    def record_failure(
        self,
        *,
        provider: str,
        model: str,
        stage: str | None = None,
        error: BaseException | str | None = None,
        latency_ms: int = 0,
        response: AIResponse | None = None,
    ) -> AICallRecord:
        """
        Enregistre une tentative échouée.

        Deux régimes, distingués par `response` (Phase 3B.2) :

        `response` absent (ou sans aucun usage)
            L'appel n'a produit aucun usage exploitable — échec de transport
            (timeout, 5xx, configuration…), ou fournisseur qui n'a réellement
            rien rapporté. Aucun token n'est inventé et le coût reste
            explicitement inconnu : un échec ne coûte peut-être rien,
            peut-être pas, et le tracker ne prétend pas le savoir.

        `response` fourni, avec usage
            Le transport a réussi et le fournisseur a rapporté des tokens
            RÉELS avant qu'un incident ultérieur (sortie structurée invalide,
            par exemple) ne fasse échouer l'appel métier. Cet usage — et le
            coût qui en découle — sont conservés : l'appel a probablement été
            facturé, et le prétendre gratuit serait aussi faux que lui
            inventer un montant. `status` reste néanmoins `failed` : un usage
            connu ne rend pas l'appel réussi.
        """
        error_type = (
            error if isinstance(error, str)
            else type(error).__name__ if error is not None
            else None
        )

        error_usage = _usage_from_error(error)
        if response is not None and response.has_usage:
            cost = self.catalog.estimate_cost(
                response.provider,
                response.model,
                response.input_tokens,
                response.output_tokens,
            )
            input_tokens = response.input_tokens
            output_tokens = response.output_tokens
            total_tokens = response.total_tokens
            usage_source = response.usage_source
            effective_latency_ms = response.latency_ms or latency_ms
            finish_reason = response.finish_reason
            request_id = response.request_id
        elif error_usage is not None:
            input_tokens, output_tokens, total_tokens = error_usage
            cost = self.catalog.estimate_cost(
                provider,
                model,
                input_tokens,
                output_tokens,
            )
            usage_source = "provider"
            effective_latency_ms = getattr(error, "elapsed_ms", None) or latency_ms
            finish_reason = getattr(error, "finish_reason", None)
            request_id = getattr(error, "request_id", None)
        else:
            cost = unknown_cost("Appel échoué : usage et coût non déterminés.")
            input_tokens = output_tokens = total_tokens = None
            usage_source = USAGE_UNAVAILABLE
            effective_latency_ms = latency_ms
            finish_reason = None
            request_id = None

        record = AICallRecord(
            call_id=self._next_call_id(),
            stage=stage or (response.stage if response is not None else None) or UNKNOWN_STAGE,
            provider=provider,
            model=model,
            status=CALL_STATUS_FAILED,
            cost=cost,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            usage_source=usage_source,
            latency_ms=effective_latency_ms,
            finish_reason=finish_reason,
            request_id=request_id,
            error_type=error_type,
            recorded_at=_now(),
        )

        self._records.append(record)
        return record

    def record_units(
        self,
        *,
        provider: str,
        model: str,
        unit: str,
        unit_count: int,
        stage: str | None = None,
        latency_ms: int = 0,
    ) -> AICallRecord:
        """
        Enregistre un appel facturé à l'unité (image, requête, seconde).

        Aucun appel de ce type n'est produit en Phase 2 ; la méthode existe
        pour que l'ajout de la génération d'images ne demande pas de
        réécrire l'agrégation.
        """
        cost = self.catalog.estimate_unit_cost(provider, model, unit_count, unit)

        record = AICallRecord(
            call_id=self._next_call_id(),
            stage=stage or UNKNOWN_STAGE,
            provider=provider,
            model=model,
            status=CALL_STATUS_COMPLETED,
            cost=cost,
            unit=unit,
            unit_count=unit_count,
            latency_ms=latency_ms,
            recorded_at=_now(),
        )

        self._records.append(record)
        return record

    # -- Agrégation --------------------------------------------------------

    def aggregate(self) -> dict:
        """Agrégats par appel, par étape, par fournisseur, par modèle et total."""
        return aggregate_records(
            (record.to_dict() for record in self._records),
            default_currency=self.currency,
        )

    def to_report_dict(self, *, include_details: bool = True) -> dict:
        """Bloc `ai_usage` prêt à être inséré dans report.json."""
        block = self.aggregate()

        if include_details:
            block["details"] = [record.to_dict() for record in self._records]

        return block

    def serialize(self) -> list[dict]:
        """Lignes brutes, pour persistance dans project_state.json."""
        return [record.to_dict() for record in self._records]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Agrégation — fonction pure, partagée par le tracker et par report_service
# ---------------------------------------------------------------------------

@dataclass
class _Bucket:
    """Accumulateur interne d'un regroupement (étape, fournisseur, modèle)."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    known_cost: Decimal = Decimal(0)
    unknown_cost_calls: int = 0
    local_calls: int = 0
    failed_calls: int = 0
    statuses: set = field(default_factory=set)
    currencies: set = field(default_factory=set)

    def add(self, record: Mapping[str, Any]) -> None:
        self.calls += 1

        self.input_tokens += int(record.get("input_tokens") or 0)
        self.output_tokens += int(record.get("output_tokens") or 0)
        self.total_tokens += int(record.get("total_tokens") or 0)

        if record.get("status") == CALL_STATUS_FAILED:
            self.failed_calls += 1

        cost = record.get("cost") or {}
        status = cost.get("status", COST_STATUS_UNKNOWN)
        self.statuses.add(status)

        if status == COST_STATUS_LOCAL:
            self.local_calls += 1

        if status == COST_STATUS_UNKNOWN or cost.get("total_cost") is None:
            self.unknown_cost_calls += 1
            return

        self.known_cost += Decimal(str(cost.get("total_cost")))

        if cost.get("currency"):
            self.currencies.add(cost["currency"])

    def cost_status(self) -> str:
        if self.calls == 0:
            return COST_STATUS_NO_CALLS

        has_unknown = COST_STATUS_UNKNOWN in self.statuses
        has_priced = bool(self.statuses - {COST_STATUS_UNKNOWN})

        if has_unknown and has_priced:
            return COST_STATUS_PARTIAL

        if has_unknown:
            return COST_STATUS_UNKNOWN

        # Un seul appel dont le régime tarifaire n'est pas modélisé suffit à
        # retirer au total le droit de s'annoncer « known » : le montant reste
        # celui calculé, mais l'agrégat dit qu'il est un ordre de grandeur.
        if COST_STATUS_BASE_ESTIMATE in self.statuses:
            return COST_STATUS_BASE_ESTIMATE

        if self.statuses == {COST_STATUS_LOCAL}:
            return COST_STATUS_LOCAL

        return COST_STATUS_KNOWN

    def estimated_cost(self) -> float | None:
        """None lorsqu'aucun coût n'est connu — surtout pas 0.0."""
        if self.calls == 0:
            return 0.0

        if self.cost_status() == COST_STATUS_UNKNOWN:
            return None

        return float(self.known_cost)

    def currency(self, default: str) -> str | None:
        if len(self.currencies) == 1:
            return next(iter(self.currencies))

        if len(self.currencies) > 1:
            return "MIXED"

        return default

    def to_dict(self, default_currency: str) -> dict:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost": self.estimated_cost(),
            "currency": self.currency(default_currency),
            "cost_status": self.cost_status(),
            "unknown_cost_calls": self.unknown_cost_calls,
        }


def empty_usage_block(currency: str = CURRENCY_USD) -> dict:
    """
    Bloc `ai_usage` d'un projet sans aucun appel IA.

    Ici estimated_cost vaut bien 0.0 : zéro appel coûte zéro, ce qui est un
    fait — à la différence d'un appel non tarifé, qui vaut None.
    """
    return {
        "calls": 0,
        "completed_calls": 0,
        "failed_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_cost": 0.0,
        "currency": currency,
        "cost_status": COST_STATUS_NO_CALLS,
        "unknown_cost_calls": 0,
        "local_calls": 0,
        "compute_cost_tracked": False,
        "by_stage": {},
        "by_provider": {},
        "by_model": {},
    }


def aggregate_records(
    records: Iterable[Mapping[str, Any]],
    *,
    default_currency: str = CURRENCY_USD,
) -> dict:
    """
    Agrège des lignes d'appel sérialisées en bloc `ai_usage`.

    Fonction pure sur des dicts : le même code sert au tracker en mémoire et
    à report_service qui relit project_state.json.
    """
    total = _Bucket()
    by_stage: dict[str, _Bucket] = {}
    by_provider: dict[str, _Bucket] = {}
    by_model: dict[str, _Bucket] = {}

    for record in records:
        total.add(record)

        for grouping, key in (
            (by_stage, record.get("stage") or UNKNOWN_STAGE),
            (by_provider, record.get("provider") or "unknown"),
            (by_model, _model_key(record)),
        ):
            grouping.setdefault(str(key), _Bucket()).add(record)

    block = empty_usage_block(default_currency)
    block.update(total.to_dict(default_currency))

    block["completed_calls"] = total.calls - total.failed_calls
    block["failed_calls"] = total.failed_calls
    block["local_calls"] = total.local_calls
    block["compute_cost_tracked"] = total.calls > 0 and total.local_calls == 0

    block["by_stage"] = _render(by_stage, default_currency)
    block["by_provider"] = _render(by_provider, default_currency)
    block["by_model"] = _render(by_model, default_currency)

    return block


def _model_key(record: Mapping[str, Any]) -> str:
    """Un modèle se lit toujours avec son fournisseur : « ollama:qwen3:8b »."""
    provider = record.get("provider") or "unknown"
    model = record.get("model") or "unknown"

    return f"{provider}:{model}"


def _render(buckets: Mapping[str, _Bucket], default_currency: str) -> dict:
    return {
        key: bucket.to_dict(default_currency)
        for key, bucket in sorted(buckets.items())
    }


def cost_per_1000_words(
    total_cost: float | Decimal | None,
    word_count: int,
) -> float | None:
    """
    Coût pour 1000 mots produits.

    Retourne None tant que le livre n'existe pas ou que le coût est inconnu :
    aucune valeur artificielle n'est fabriquée pour remplir un champ.
    """
    if total_cost is None or not word_count or int(word_count) <= 0:
        return None

    return float(Decimal(str(total_cost)) / Decimal(word_count) * Decimal(1000))
