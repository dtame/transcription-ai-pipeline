"""
Catalogue tarifaire centralisé.

Principe non négociable : aucun calcul de prix ne vit dans un provider.
Un provider rapporte des tokens ; la conversion en argent se fait ici, et
seulement ici, pour qu'une mise à jour de tarif soit un changement à un seul
endroit, daté et sourcé.

Ce que ce module ne fait PAS : inventer des prix. Aucun tarif n'est codé ici.
Les tarifs cloud vivent dans app.config.AI_PRICING_ENTRIES, où chaque ligne
porte sa source et sa date de relevé — un chiffre plausible mais faux dans un
rapport financier est pire que pas de chiffre du tout. Un modèle absent de
cette liste n'est pas tarifé, et son coût est rapporté « unknown ».

Quatre statuts de coût, volontairement distincts :

    known               tarif connu, coût calculé
    base_estimate       tarif de base appliqué, mais le modèle possède des
                        régimes tarifaires que ce catalogue ne modélise pas
                        (voir `unmodeled_regimes`). Le montant est utilisable
                        comme ordre de grandeur, pas comme une facture.
    unknown             aucun tarif, ou usage non rapporté -> coût = None
    local_no_api_cost   exécution locale : facture API nulle, MAIS le coût de
                        calcul (électricité, GPU, temps machine) n'est pas
                        valorisé. Ce n'est pas la même chose que « gratuit ».

Les montants sont des Decimal : additionner des centièmes en binaire produit
des rapports faux à la longue.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Iterator, Mapping

import app.config as config

CURRENCY_USD = "USD"

# Unités facturables. Phase 2 n'implémente que les tokens, mais le catalogue
# et le tracker acceptent déjà les unités dont la Phase 7 (images) aura besoin.
UNIT_TOKENS = "tokens"
UNIT_IMAGE = "image"
UNIT_REQUEST = "request"
UNIT_SECOND = "second"

COST_STATUS_KNOWN = "known"
COST_STATUS_BASE_ESTIMATE = "base_estimate"
COST_STATUS_UNKNOWN = "unknown"
COST_STATUS_LOCAL = "local_no_api_cost"

# Régimes tarifaires dont l'existence est connue mais que le catalogue ne sait
# pas calculer. Un tarif qui en déclare un ne produit plus un coût "known"
# mais un "base_estimate" : le montant reste affiché, sa nature aussi.
REGIME_LONG_CONTEXT = "long_context_not_modeled"

TOKENS_PER_PRICING_UNIT = Decimal(1_000_000)

# Entrée générique d'un provider, tous modèles confondus.
WILDCARD_MODEL = "*"


def _to_decimal(value) -> Decimal:
    """Conversion sûre vers Decimal (jamais via float, qui introduit du bruit)."""
    if value is None:
        return Decimal(0)

    if isinstance(value, Decimal):
        return value

    return Decimal(str(value))


@dataclass(frozen=True)
class ModelPricing:
    """
    Une ligne tarifaire.

    `verified` distingue un tarif vérifié à sa source d'un tarif de test ou
    d'un chiffre repris sans contrôle. `effective_date` et `source` existent
    pour qu'un rapport puisse dire d'où vient un montant.

    `unmodeled_regimes` nomme les régimes tarifaires que cette ligne ne couvre
    pas (par exemple les paliers de très long contexte). Renseigné, il fait
    passer tout coût calculé de "known" à "base_estimate" : le catalogue
    continue de chiffrer, mais ne prétend plus que le chiffre est complet.
    """

    provider: str
    model: str
    currency: str = CURRENCY_USD
    unit: str = UNIT_TOKENS
    input_cost_per_1m_tokens: Decimal = Decimal(0)
    output_cost_per_1m_tokens: Decimal = Decimal(0)
    cost_per_unit: Decimal = Decimal(0)
    is_local: bool = False
    effective_date: str = ""
    source: str = ""
    verified: bool = False
    notes: str = ""
    unmodeled_regimes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", str(self.provider).strip().lower())
        object.__setattr__(self, "model", str(self.model).strip())

        for field_name in (
            "input_cost_per_1m_tokens",
            "output_cost_per_1m_tokens",
            "cost_per_unit",
        ):
            object.__setattr__(self, field_name, _to_decimal(getattr(self, field_name)))

        for field_name in (
            "input_cost_per_1m_tokens",
            "output_cost_per_1m_tokens",
            "cost_per_unit",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(
                    f"{field_name} ne peut pas être négatif "
                    f"({self.provider}:{self.model})."
                )

    @property
    def key(self) -> tuple[str, str]:
        return (self.provider, self.model)

    @classmethod
    def local(cls, provider: str, **kwargs) -> ModelPricing:
        """Fabrique une entrée d'inférence locale : facture API nulle."""
        return cls(
            provider=provider,
            model=kwargs.pop("model", WILDCARD_MODEL),
            is_local=True,
            verified=True,
            notes=kwargs.pop(
                "notes",
                "Inférence locale : aucun coût API. Le coût de calcul "
                "(machine, électricité) n'est pas valorisé.",
            ),
            **kwargs,
        )

    @classmethod
    def from_dict(cls, data: Mapping) -> ModelPricing:
        return cls(
            provider=data["provider"],
            model=data.get("model", WILDCARD_MODEL),
            currency=data.get("currency", CURRENCY_USD),
            unit=data.get("unit", UNIT_TOKENS),
            input_cost_per_1m_tokens=data.get("input_cost_per_1m_tokens", 0),
            output_cost_per_1m_tokens=data.get("output_cost_per_1m_tokens", 0),
            cost_per_unit=data.get("cost_per_unit", 0),
            is_local=bool(data.get("is_local", False)),
            effective_date=str(data.get("effective_date", "")),
            source=str(data.get("source", "")),
            verified=bool(data.get("verified", False)),
            notes=str(data.get("notes", "")),
            unmodeled_regimes=str(data.get("unmodeled_regimes", "")),
        )

    @property
    def cost_status(self) -> str:
        """Statut que produira un coût calculé depuis cette ligne tarifaire."""
        return COST_STATUS_BASE_ESTIMATE if self.unmodeled_regimes else COST_STATUS_KNOWN

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "currency": self.currency,
            "unit": self.unit,
            "input_cost_per_1m_tokens": float(self.input_cost_per_1m_tokens),
            "output_cost_per_1m_tokens": float(self.output_cost_per_1m_tokens),
            "cost_per_unit": float(self.cost_per_unit),
            "is_local": self.is_local,
            "effective_date": self.effective_date,
            "source": self.source,
            "verified": self.verified,
            "notes": self.notes,
            "unmodeled_regimes": self.unmodeled_regimes,
        }


@dataclass(frozen=True)
class CostBreakdown:
    """
    Coût d'un appel. `total_cost is None` signifie « inconnu », jamais « nul ».

    compute_cost_tracked reste False pour les providers locaux : leur facture
    API vaut bien 0, mais personne n'a mesuré le coût machine.
    """

    status: str
    currency: str | None = None
    input_cost: Decimal | None = None
    output_cost: Decimal | None = None
    total_cost: Decimal | None = None
    compute_cost_tracked: bool = False
    pricing_source: str = ""
    effective_date: str = ""
    verified: bool = False
    notes: str = ""
    unmodeled_regimes: str = ""

    @property
    def is_known(self) -> bool:
        """True dès qu'un montant existe — voir `is_complete` pour sa nature."""
        return self.total_cost is not None

    @property
    def is_complete(self) -> bool:
        """
        True si le montant couvre tous les régimes tarifaires du modèle.

        Un base_estimate a bien un montant (`is_known`) sans être complet :
        l'appelant qui présente un chiffre à l'utilisateur doit lire celui-ci
        et non celui-là.
        """
        return self.is_known and not self.unmodeled_regimes

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "currency": self.currency,
            "input_cost": _optional_float(self.input_cost),
            "output_cost": _optional_float(self.output_cost),
            "total_cost": _optional_float(self.total_cost),
            "compute_cost_tracked": self.compute_cost_tracked,
            "pricing_source": self.pricing_source,
            "effective_date": self.effective_date,
            "verified": self.verified,
            "notes": self.notes,
            "unmodeled_regimes": self.unmodeled_regimes,
        }


def _optional_float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def unknown_cost(reason: str) -> CostBreakdown:
    """Coût explicitement inconnu — à ne jamais remplacer par 0."""
    return CostBreakdown(status=COST_STATUS_UNKNOWN, notes=reason)


class PricingCatalog:
    """
    Table (provider, model) -> ModelPricing.

    La résolution essaie le modèle exact puis l'entrée générique du provider,
    ce qui permet de tarifer « tout Ollama » d'une seule ligne tout en
    surchargeant un modèle précis.
    """

    def __init__(self, entries: Iterable[ModelPricing] = ()) -> None:
        self._entries: dict[tuple[str, str], ModelPricing] = {}

        for entry in entries:
            self.register(entry)

    def register(self, pricing: ModelPricing, *, overwrite: bool = True) -> ModelPricing:
        if not overwrite and pricing.key in self._entries:
            raise ValueError(
                f"Tarif déjà enregistré pour {pricing.provider}:{pricing.model}."
            )

        self._entries[pricing.key] = pricing
        return pricing

    def register_many(self, entries: Iterable[ModelPricing]) -> None:
        for entry in entries:
            self.register(entry)

    def get(self, provider: str, model: str) -> ModelPricing | None:
        provider = str(provider).strip().lower()
        model = str(model).strip()

        return self._entries.get((provider, model)) or self._entries.get(
            (provider, WILDCARD_MODEL)
        )

    def __iter__(self) -> Iterator[ModelPricing]:
        return iter(sorted(self._entries.values(), key=lambda p: p.key))

    def __len__(self) -> int:
        return len(self._entries)

    def to_list(self) -> list[dict]:
        return [entry.to_dict() for entry in self]

    # -- Calcul -----------------------------------------------------------

    def estimate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> CostBreakdown:
        """
        Coût d'un appel facturé aux tokens.

            input_cost  = input_tokens  / 1_000_000 × input_rate
            output_cost = output_tokens / 1_000_000 × output_rate

        Aucun arrondi n'est appliqué : l'affichage arrondira si besoin.
        """
        pricing = self.get(provider, model)

        if pricing is None:
            return unknown_cost(
                f"Aucun tarif connu pour {provider}:{model}."
            )

        if pricing.is_local:
            return CostBreakdown(
                status=COST_STATUS_LOCAL,
                currency=pricing.currency,
                input_cost=Decimal(0),
                output_cost=Decimal(0),
                total_cost=Decimal(0),
                compute_cost_tracked=False,
                pricing_source=pricing.source,
                effective_date=pricing.effective_date,
                verified=pricing.verified,
                notes=pricing.notes,
            )

        if input_tokens is None and output_tokens is None:
            return unknown_cost(
                f"Tarif connu pour {provider}:{model} mais aucun usage "
                "rapporté par le fournisseur."
            )

        input_cost = (
            _to_decimal(input_tokens or 0) / TOKENS_PER_PRICING_UNIT
        ) * pricing.input_cost_per_1m_tokens

        output_cost = (
            _to_decimal(output_tokens or 0) / TOKENS_PER_PRICING_UNIT
        ) * pricing.output_cost_per_1m_tokens

        return CostBreakdown(
            status=pricing.cost_status,
            currency=pricing.currency,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=input_cost + output_cost,
            compute_cost_tracked=True,
            pricing_source=pricing.source,
            effective_date=pricing.effective_date,
            verified=pricing.verified,
            notes=pricing.notes,
            unmodeled_regimes=pricing.unmodeled_regimes,
        )

    def estimate_unit_cost(
        self,
        provider: str,
        model: str,
        unit_count: int,
        unit: str = UNIT_IMAGE,
    ) -> CostBreakdown:
        """
        Coût d'un appel facturé à l'unité (image, requête, seconde).

        Présent pour que la Phase 7 (génération d'images) n'ait pas à
        réécrire le tracker. Aucun tarif image n'est fourni en Phase 2.
        """
        pricing = self.get(provider, model)

        if pricing is None:
            return unknown_cost(f"Aucun tarif connu pour {provider}:{model}.")

        if pricing.is_local:
            return CostBreakdown(
                status=COST_STATUS_LOCAL,
                currency=pricing.currency,
                total_cost=Decimal(0),
                compute_cost_tracked=False,
                pricing_source=pricing.source,
                notes=pricing.notes,
            )

        if pricing.unit != unit:
            return unknown_cost(
                f"Tarif {provider}:{model} exprimé en « {pricing.unit} », "
                f"appel facturé en « {unit} »."
            )

        total = _to_decimal(unit_count) * pricing.cost_per_unit

        return CostBreakdown(
            status=pricing.cost_status,
            currency=pricing.currency,
            total_cost=total,
            compute_cost_tracked=True,
            pricing_source=pricing.source,
            effective_date=pricing.effective_date,
            verified=pricing.verified,
            notes=pricing.notes,
            unmodeled_regimes=pricing.unmodeled_regimes,
        )


# ---------------------------------------------------------------------------
# Catalogue par défaut
# ---------------------------------------------------------------------------

def _local_entries() -> list[ModelPricing]:
    """
    Seules entrées fournies d'office : les runtimes locaux.

    Leur tarif API est nul par nature — ce n'est pas une donnée commerciale
    susceptible de changer, donc l'inscrire ici ne fabrique aucune illusion.
    """
    return [
        ModelPricing.local(
            provider="ollama",
            source="Runtime local (Ollama) — aucune facturation API.",
        ),
        ModelPricing.local(
            provider="lmstudio",
            source="Runtime local (LM Studio) — aucune facturation API.",
        ),
    ]


def build_default_catalog() -> PricingCatalog:
    """
    Catalogue par défaut = runtimes locaux + AI_PRICING_ENTRIES.

    Les tarifs cloud réels se déclarent dans app/config.py, vérifiés et datés.
    Un couple (provider, modèle) absent de cette liste est rapporté avec un
    coût « unknown », ce qui est la réponse honnête.
    """
    catalog = PricingCatalog(_local_entries())

    for raw in getattr(config, "AI_PRICING_ENTRIES", []) or []:
        catalog.register(ModelPricing.from_dict(raw))

    return catalog


def round_cost_for_display(value: Decimal | float | None, places: int = 4):
    """Arrondi d'AFFICHAGE. Ne jamais l'utiliser avant une agrégation."""
    if value is None:
        return None

    return round(float(value), places)
