"""
Registre unique des moteurs IA.

C'est la factory de la V1, étendue : `get_ai_engine()` sans argument lit
toujours `app.config.AI_PROVIDER` et retourne un moteur prêt à l'emploi.
Il n'existe volontairement qu'UN registre dans le projet pour les moteurs de
texte — en créer un second réintroduirait exactement le problème que la
Phase 2 vient supprimer.

Le choix du provider est explicite ou hérité de la configuration, jamais
deviné. Aucun routage « intelligent » : la couche ne décide pas quel modèle
serait le meilleur pour une tâche, elle exécute ce qu'on lui demande.

Note de compatibilité : un nom de provider inconnu lève ValueError, comme en
V1, et non une erreur de la couche IA — le message et le type restent ceux
que connaissent les appelants existants.
"""

from __future__ import annotations

from typing import Any

import app.config as config

from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.providers.base import BaseAIEngine
from app.ai.providers.fake import FakeAIEngine
from app.ai.providers.lmstudio import LMStudioEngine
from app.ai.providers.ollama import OllamaEngine
from app.ai.providers.openai_engine import OpenAIEngine
from app.ai.settings import StageSettings, resolve_stage_settings

_REGISTRY: dict[str, type[BaseAIEngine]] = {
    "ollama": OllamaEngine,
    "lmstudio": LMStudioEngine,
    "openai": OpenAIEngine,
    "anthropic": AnthropicEngine,
    "fake": FakeAIEngine,
}

# Providers ne nécessitant aucune clé cloud : utilisables hors ligne.
LOCAL_PROVIDERS = frozenset({"ollama", "lmstudio", "fake"})


def available_providers() -> list[str]:
    """Noms de providers enregistrés, triés."""
    return sorted(_REGISTRY)


def register_ai_engine(
    name: str,
    engine_class: type[BaseAIEngine],
    *,
    overwrite: bool = False,
) -> None:
    """Ajoute un moteur au registre (extension, tests, providers futurs)."""
    key = str(name).strip().lower()

    if not overwrite and key in _REGISTRY:
        raise ValueError(f"Provider déjà enregistré : '{key}'.")

    if not issubclass(engine_class, BaseAIEngine):
        raise TypeError(
            f"{engine_class!r} doit hériter de BaseAIEngine pour être enregistré."
        )

    _REGISTRY[key] = engine_class


def unregister_ai_engine(name: str) -> None:
    """Retire un moteur du registre. Utile pour nettoyer après un test."""
    _REGISTRY.pop(str(name).strip().lower(), None)


def get_engine_class(provider: str) -> type[BaseAIEngine]:
    key = str(provider).strip().lower()

    if key not in _REGISTRY:
        raise ValueError(
            f"AI_PROVIDER inconnu : '{provider}'. "
            f"Valeurs acceptées : {available_providers()}"
        )

    return _REGISTRY[key]


def get_ai_engine(provider: str | None = None, **kwargs: Any) -> BaseAIEngine:
    """
    Fabrique le moteur IA demandé, ou celui de AI_PROVIDER par défaut.

    Valeurs supportées :
        "ollama"    -> OllamaEngine     (défaut recommandé, local)
        "lmstudio"  -> LMStudioEngine   (local)
        "openai"    -> OpenAIEngine     (cloud, OPENAI_API_KEY requise)
        "anthropic" -> AnthropicEngine  (cloud, ANTHROPIC_API_KEY requise)
        "fake"      -> FakeAIEngine     (tests, aucun réseau)

    AI_PROVIDER est lu à l'appel et non à l'import : un test peut le
    surcharger sans recharger le module.

    Raises:
        ValueError: si le provider est inconnu.
    """
    name = provider if provider is not None else getattr(config, "AI_PROVIDER", "ollama")

    return get_engine_class(name)(**kwargs)


# Alias : la couche s'appelle « engine » dans ce projet, « provider » dans le
# vocabulaire des fournisseurs. Les deux désignent le même objet.
get_ai_provider = get_ai_engine


def get_engine_for_stage(stage: str, **kwargs: Any) -> tuple[BaseAIEngine, StageSettings]:
    """
    Moteur configuré pour une étape du pipeline, avec ses réglages.

    Retourne le couple (moteur, réglages) : l'appelant a besoin des seconds
    pour construire sa requête (température, plafond de sortie, ratio de
    contexte) sans les redemander à la configuration.

    Les quatre étapes éditoriales sont configurées dans AI_STAGE_SETTINGS
    (voir app/ai/settings.py) ; toute autre étape hérite du provider global
    AI_PROVIDER. Le moteur est construit sans clé API : seule une tentative
    d'appel réel exige les credentials.
    """
    settings = resolve_stage_settings(stage)

    kwargs.setdefault("model", settings.model)
    kwargs.setdefault("temperature", settings.temperature)
    kwargs.setdefault("max_output_tokens", settings.max_output_tokens)

    return get_ai_engine(settings.provider, **kwargs), settings
