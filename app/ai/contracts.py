"""
Contrats normalisés d'un appel IA : AIRequest et AIResponse.

Ce sont les deux seuls objets que les étapes éditoriales futures
(Source Analyzer, Editorial Planner, Book Generator, Book Validator,
Visual Director) auront besoin de connaître. Aucune d'elles ne doit
importer openai, anthropic ou requests.

Règle de séparation stricte, appliquée dans tout le module :

    input_tokens / output_tokens / total_tokens
        = consommation RÉELLE rapportée par le fournisseur.
          Source de vérité du coût. Valent None si le fournisseur
          ne les rapporte pas — jamais 0 « par défaut ».

    app/ai/estimation.py
        = estimation AVANT appel, toujours marquée comme telle.

Les deux ne se mélangent jamais : usage_source dit laquelle on tient.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.ai.thinking import validate_request_thinking_fields

# Provenance des compteurs de tokens portés par AIResponse.
USAGE_FROM_PROVIDER = "provider"
USAGE_UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class AIRequest:
    """
    Une demande adressée à la couche IA, indépendante du fournisseur.

    Champs :
        prompt              contenu utilisateur (obligatoire)
        system_prompt       consigne système, si le modèle la supporte
        model               None -> modèle par défaut du provider
        temperature         None -> valeur par défaut du provider
        max_output_tokens   plafond de génération, None -> défaut provider
        response_schema     demande une sortie structurée JSON (voir structured.py)
        timeout_seconds     None -> timeout par défaut du provider
        thinking_mode       None / provider_default -> défaut fournisseur
        effort              None -> omettre (pas de cap thinking déterministe)
        thinking_budget_tokens
                            None -> omettre. Si présent, rejet local si le
                            modèle ne le supporte pas (jamais envoyé pour
                            claude-sonnet-5).
        metadata            observabilité INTERNE uniquement

    `metadata` n'est jamais transmis au fournisseur : il sert à rattacher
    l'appel à une étape du pipeline (`stage`) pour le CostTracker et les
    logs. Les providers construisent leur payload champ par champ, jamais
    par sérialisation de la requête entière.
    """

    prompt: str
    system_prompt: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    response_schema: Mapping[str, Any] | None = None
    timeout_seconds: float | None = None
    thinking_mode: str | None = None
    effort: str | None = None
    thinking_budget_tokens: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ValueError("AIRequest.prompt doit être une chaîne non vide.")

        if self.temperature is not None and not 0.0 <= float(self.temperature) <= 2.0:
            raise ValueError(
                f"AIRequest.temperature hors plage [0, 2] : {self.temperature}"
            )

        if self.max_output_tokens is not None and int(self.max_output_tokens) <= 0:
            raise ValueError(
                f"AIRequest.max_output_tokens doit être > 0 : {self.max_output_tokens}"
            )

        if self.timeout_seconds is not None and float(self.timeout_seconds) <= 0:
            raise ValueError(
                f"AIRequest.timeout_seconds doit être > 0 : {self.timeout_seconds}"
            )

        mode, effort, budget = validate_request_thinking_fields(
            self.thinking_mode, self.effort, self.thinking_budget_tokens
        )
        object.__setattr__(self, "thinking_mode", mode if self.thinking_mode else None)
        object.__setattr__(self, "effort", effort)
        object.__setattr__(self, "thinking_budget_tokens", budget)

    @property
    def stage(self) -> str | None:
        """Étape du pipeline à l'origine de l'appel, si elle s'est annoncée."""
        value = self.metadata.get("stage")
        return str(value) if value is not None else None

    @property
    def wants_structured_output(self) -> bool:
        return self.response_schema is not None

    def with_prompt(self, prompt: str) -> AIRequest:
        """Copie de la requête avec un prompt réécrit (ajout de consignes JSON)."""
        return AIRequest(
            prompt=prompt,
            system_prompt=self.system_prompt,
            model=self.model,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            response_schema=self.response_schema,
            timeout_seconds=self.timeout_seconds,
            thinking_mode=self.thinking_mode,
            effort=self.effort,
            thinking_budget_tokens=self.thinking_budget_tokens,
            metadata=dict(self.metadata),
        )


@dataclass(frozen=True)
class AIResponse:
    """
    Réponse normalisée, identique quel que soit le fournisseur.

    `text` est toujours le texte brut renvoyé par le modèle : même lorsqu'une
    sortie structurée est demandée et décodée dans `parsed`, le texte reste
    accessible pour l'audit.

    Les compteurs de tokens sont ceux du fournisseur. `usage_source` vaut
    USAGE_UNAVAILABLE lorsqu'aucun compteur n'a été rapporté — auquel cas les
    trois champs valent None, et surtout pas 0.
    """

    text: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int = 0
    finish_reason: str | None = None
    request_id: str | None = None
    parsed: Any = None
    raw_usage: Mapping[str, Any] = field(default_factory=dict)
    usage_source: str = USAGE_UNAVAILABLE
    thinking_tokens: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # total_tokens dérivé seulement si les deux moitiés sont connues :
        # une somme partielle serait un chiffre faux dans un rapport de coût.
        if (
            self.total_tokens is None
            and self.input_tokens is not None
            and self.output_tokens is not None
        ):
            object.__setattr__(
                self, "total_tokens", int(self.input_tokens) + int(self.output_tokens)
            )

        if self.has_usage and self.usage_source == USAGE_UNAVAILABLE:
            object.__setattr__(self, "usage_source", USAGE_FROM_PROVIDER)

    @property
    def has_usage(self) -> bool:
        """True si le fournisseur a rapporté au moins un compteur réel."""
        return any(
            value is not None
            for value in (self.input_tokens, self.output_tokens, self.total_tokens)
        )

    @property
    def stage(self) -> str | None:
        value = self.metadata.get("stage")
        return str(value) if value is not None else None

    def to_dict(self) -> dict:
        """Sérialisation de la réponse SANS le texte généré ni le prompt."""
        return {
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "usage_source": self.usage_source,
            "latency_ms": self.latency_ms,
            "finish_reason": self.finish_reason,
            "request_id": self.request_id,
            "thinking_tokens": self.thinking_tokens,
            "text_chars": len(self.text),
        }
