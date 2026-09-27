"""
WindowPlannerConfig — configuration immuable et validée.

Aucun magic number hors de ce contrat. Les budgets sont des tokens
d'entrée ESTIMÉS de requête complète (voir tokens.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.source_analysis.errors import SourceAnalysisWindowPlannerConfigError
from app.source_analysis_hybrid.constants import (
    HARD_MAX_INPUT_TOKENS,
    OVERLAP_POLICY,
    PLANNER_VERSION,
    RECOGNIZED_OVERLAP_POLICIES,
    TARGET_INPUT_TOKENS,
)


def _require_positive_int(name: str, value: object) -> int:
    if isinstance(value, bool):
        raise SourceAnalysisWindowPlannerConfigError(
            f"{name} interdit en booléen : {value!r}."
        )
    if type(value) is not int:
        raise SourceAnalysisWindowPlannerConfigError(
            f"{name} doit être un int strict, reçu {type(value).__name__}={value!r}."
        )
    if value <= 0:
        raise SourceAnalysisWindowPlannerConfigError(
            f"{name} doit être > 0, reçu {value}."
        )
    return value


def _require_version(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceAnalysisWindowPlannerConfigError(
            f"version non vide requise, reçu {value!r}."
        )
    return value


def _require_overlap_policy(value: object) -> str:
    if not isinstance(value, str) or value not in RECOGNIZED_OVERLAP_POLICIES:
        raise SourceAnalysisWindowPlannerConfigError(
            f"overlap_policy non reconnue : {value!r}. "
            f"Politiques v2.0 : {sorted(RECOGNIZED_OVERLAP_POLICIES)}."
        )
    return value


@dataclass(frozen=True)
class WindowPlannerConfig:
    """
    Politique de planification window-planner-v2.0.

    target_input_tokens et hard_max_input_tokens mesurent la requête
    complète estimée (system + cadrage user + contenu SRC), pas le
    seul payload transcript.
    """

    version: str = PLANNER_VERSION
    target_input_tokens: int = TARGET_INPUT_TOKENS
    hard_max_input_tokens: int = HARD_MAX_INPUT_TOKENS
    overlap_policy: str = OVERLAP_POLICY

    def __post_init__(self) -> None:
        version = _require_version(self.version)
        target = _require_positive_int("target_input_tokens", self.target_input_tokens)
        hard_max = _require_positive_int(
            "hard_max_input_tokens", self.hard_max_input_tokens
        )
        policy = _require_overlap_policy(self.overlap_policy)
        if target > hard_max:
            raise SourceAnalysisWindowPlannerConfigError(
                f"target_input_tokens ({target}) > hard_max_input_tokens ({hard_max})."
            )
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "target_input_tokens", target)
        object.__setattr__(self, "hard_max_input_tokens", hard_max)
        object.__setattr__(self, "overlap_policy", policy)

    def to_dict(self) -> dict[str, str | int]:
        return {
            "version": self.version,
            "target_input_tokens": self.target_input_tokens,
            "hard_max_input_tokens": self.hard_max_input_tokens,
            "overlap_policy": self.overlap_policy,
        }
