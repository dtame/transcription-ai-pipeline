"""
Capacités d'un modèle : fenêtre de contexte, plafond de sortie, options.

Point central de la Phase 2 : il n'existe AUCUNE constante globale du type
`SAFE_CONTEXT = 4096` valable pour toute l'application. Une fenêtre de
contexte appartient à un couple (provider, model) et se résout ainsi :

    1. app.config.AI_MODEL_CAPABILITIES["provider:model"]   (override explicite)
    2. app.config.AI_MODEL_CAPABILITIES["provider:*"]        (défaut du provider)
    3. table interne _BUILTIN_CAPABILITIES                   (valeurs tracées)
    4. repli documenté, marqué known=False

Le champ `known` est ce qui compte : il dit si la valeur a été vérifiée ou
si c'est une hypothèse de repli. Aucune capacité de modèle cloud n'est
inventée de mémoire — la table interne ne contient que ce que le dépôt
sait déjà (le num_ctx d'Ollama) et le provider de test.

Le `safety_ratio` n'est pas décidé ici : il est configurable globalement
(AI_CONTEXT_SAFETY_RATIO) et surchargeable par étape. La Phase 3 décidera
comment le Source Analyzer dépense ce budget.
"""

from __future__ import annotations

from dataclasses import dataclass

import app.config as config

# Provenances possibles d'une capacité, du plus fiable au moins fiable.
SOURCE_CONFIG = "config"
SOURCE_BUILTIN = "builtin"
SOURCE_FALLBACK = "fallback"


@dataclass(frozen=True)
class ModelCapabilities:
    """
    Ce qu'un modèle accepte raisonnablement, et d'où on le sait.

    context_window      total de tokens (entrée + sortie) admis par le modèle
    max_output_tokens   plafond de génération, toujours <= context_window
    known               False -> valeur de repli, à ne pas présenter comme un fait
    source              provenance de la valeur (config / builtin / fallback)
    """

    provider: str
    model: str
    context_window: int
    max_output_tokens: int
    supports_structured_output: bool = False
    supports_system_prompt: bool = True
    supports_temperature: bool = True
    known: bool = False
    source: str = SOURCE_FALLBACK

    def __post_init__(self) -> None:
        if int(self.context_window) <= 0:
            raise ValueError(
                f"context_window doit être > 0 : {self.context_window}"
            )

        if int(self.max_output_tokens) <= 0:
            raise ValueError(
                f"max_output_tokens doit être > 0 : {self.max_output_tokens}"
            )

        if int(self.max_output_tokens) > int(self.context_window):
            raise ValueError(
                "max_output_tokens ne peut pas dépasser context_window "
                f"({self.max_output_tokens} > {self.context_window})."
            )

    def usable_context(self, safety_ratio: float | None = None) -> int:
        """
        Fraction du contexte qu'une étape peut viser sans frôler la limite.

        Exemple : context_window=128000 et safety_ratio=0.70 -> 89600.
        """
        ratio = (
            default_safety_ratio() if safety_ratio is None else float(safety_ratio)
        )
        validate_safety_ratio(ratio)
        return int(self.context_window * ratio)

    def usable_input_context(self, safety_ratio: float | None = None) -> int:
        """
        Budget d'ENTRÉE : contexte utilisable moins la place réservée à la
        génération. Peut valoir 0 si le plafond de sortie absorbe tout le
        budget — l'appelant doit alors réduire max_output_tokens.
        """
        return max(0, self.usable_context(safety_ratio) - int(self.max_output_tokens))

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "supports_structured_output": self.supports_structured_output,
            "supports_system_prompt": self.supports_system_prompt,
            "supports_temperature": self.supports_temperature,
            "known": self.known,
            "source": self.source,
        }


def validate_safety_ratio(ratio: float) -> float:
    """Un ratio de sécurité vit dans ]0, 1]. 0 ou 1.2 sont des bugs, pas des choix."""
    value = float(ratio)

    if not 0.0 < value <= 1.0:
        raise ValueError(
            f"context safety ratio doit être dans ]0, 1] : {ratio}"
        )

    return value


def default_safety_ratio() -> float:
    """Ratio global, lu à l'appel pour rester surchargeable par les tests."""
    return validate_safety_ratio(getattr(config, "AI_CONTEXT_SAFETY_RATIO", 0.70))


# ---------------------------------------------------------------------------
# Table interne — uniquement des valeurs dont la provenance est traçable
# ---------------------------------------------------------------------------

def _builtin_capabilities() -> dict[str, dict]:
    """
    Capacités connues sans supposition.

    Ollama : num_ctx réellement envoyé par la V1 (app.config.OLLAMA_OPTIONS),
    donc vrai par construction plutôt que par mémoire.

    Aucune entrée OpenAI / Anthropic : leurs fenêtres de contexte dépendent du
    modèle exact et doivent être renseignées dans AI_MODEL_CAPABILITIES après
    vérification, pas devinées ici.
    """
    ollama_num_ctx = int(getattr(config, "OLLAMA_OPTIONS", {}).get("num_ctx", 4096))

    return {
        "ollama:*": {
            "context_window": ollama_num_ctx,
            "max_output_tokens": max(1, ollama_num_ctx // 4),
            "supports_structured_output": False,
            "known": True,
            "source": SOURCE_BUILTIN,
        },
        "fake:*": {
            "context_window": 128_000,
            "max_output_tokens": 8_000,
            "supports_structured_output": True,
            "known": True,
            "source": SOURCE_BUILTIN,
        },
    }


def _fallback_capabilities(provider: str, model: str) -> ModelCapabilities:
    context_window = int(getattr(config, "AI_FALLBACK_CONTEXT_WINDOW", 4096))
    max_output = int(getattr(config, "AI_FALLBACK_MAX_OUTPUT_TOKENS", 1024))

    return ModelCapabilities(
        provider=provider,
        model=model,
        context_window=context_window,
        max_output_tokens=min(max_output, context_window),
        supports_structured_output=False,
        known=False,
        source=SOURCE_FALLBACK,
    )


def resolve_capabilities(provider: str, model: str) -> ModelCapabilities:
    """
    Capacités du couple (provider, model), override de configuration prioritaire.

    Ne lève jamais : un modèle inconnu reçoit le repli documenté avec
    known=False, ce qui laisse l'appelant décider s'il fait confiance.
    """
    provider = str(provider).strip().lower()
    model = str(model)

    overrides = dict(getattr(config, "AI_MODEL_CAPABILITIES", {}) or {})
    builtin = _builtin_capabilities()

    for key, source in (
        (f"{provider}:{model}", SOURCE_CONFIG),
        (f"{provider}:*", SOURCE_CONFIG),
    ):
        if key in overrides:
            return _from_mapping(provider, model, overrides[key], default_source=source)

    for key in (f"{provider}:{model}", f"{provider}:*"):
        if key in builtin:
            return _from_mapping(provider, model, builtin[key], default_source=SOURCE_BUILTIN)

    return _fallback_capabilities(provider, model)


def _from_mapping(
    provider: str,
    model: str,
    data: dict,
    *,
    default_source: str,
) -> ModelCapabilities:
    fallback = _fallback_capabilities(provider, model)

    return ModelCapabilities(
        provider=provider,
        model=model,
        context_window=int(data.get("context_window", fallback.context_window)),
        max_output_tokens=int(
            data.get("max_output_tokens", fallback.max_output_tokens)
        ),
        supports_structured_output=bool(data.get("supports_structured_output", False)),
        supports_system_prompt=bool(data.get("supports_system_prompt", True)),
        supports_temperature=bool(data.get("supports_temperature", True)),
        known=bool(data.get("known", True)),
        source=str(data.get("source", default_source)),
    )
