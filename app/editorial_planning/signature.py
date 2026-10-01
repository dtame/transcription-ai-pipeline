"""Signature déterministe et cache d'idempotence du Editorial Planner."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from app.editorial_planning.constants import (
    EDITORIAL_PLAN_SCHEMA_VERSION,
    EDITORIAL_PLAN_TRANSPORT_VERSION,
    EDITORIAL_PLANNER_PROMPT_VERSION,
    IDEA_COVERAGE_POLICY_VERSION,
    PLANNER_SETTINGS_VERSION,
)
from app.file_utils import content_hash


@dataclass(frozen=True)
class PlannerSignatureInputs:
    source_map_sha256: str
    prompt_version: str
    prompt_sha256: str
    transport_version: str
    schema_version: str
    response_schema_sha256: str
    coverage_policy_version: str
    settings_version: str
    provider: str
    model: str
    thinking_mode: str
    effort: str
    max_output_tokens: int | None
    strategy: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage_policy_version": self.coverage_policy_version,
            "effort": self.effort,
            "max_output_tokens": self.max_output_tokens,
            "model": self.model,
            "prompt_sha256": self.prompt_sha256,
            "prompt_version": self.prompt_version,
            "provider": self.provider,
            "response_schema_sha256": self.response_schema_sha256,
            "schema_version": self.schema_version,
            "settings_version": self.settings_version,
            "source_map_sha256": self.source_map_sha256,
            "strategy": self.strategy,
            "thinking_mode": self.thinking_mode,
            "transport_version": self.transport_version,
        }


def build_planner_signature(inputs: PlannerSignatureInputs) -> str:
    payload = json.dumps(inputs.to_dict(), ensure_ascii=False, sort_keys=True)
    return content_hash(payload)


def default_signature_inputs(
    *,
    source_map_sha256: str,
    prompt_sha256: str,
    response_schema_sha256: str,
    provider: str,
    model: str,
    thinking_mode: str,
    effort: str | None,
    max_output_tokens: int | None,
    strategy: str,
) -> PlannerSignatureInputs:
    return PlannerSignatureInputs(
        source_map_sha256=source_map_sha256,
        prompt_version=EDITORIAL_PLANNER_PROMPT_VERSION,
        prompt_sha256=prompt_sha256,
        transport_version=EDITORIAL_PLAN_TRANSPORT_VERSION,
        schema_version=EDITORIAL_PLAN_SCHEMA_VERSION,
        response_schema_sha256=response_schema_sha256,
        coverage_policy_version=IDEA_COVERAGE_POLICY_VERSION,
        settings_version=PLANNER_SETTINGS_VERSION,
        provider=provider,
        model=model,
        thinking_mode=thinking_mode or "",
        effort=effort or "",
        max_output_tokens=max_output_tokens,
        strategy=strategy,
    )


class EditorialPlanCache:
    """
    Cache local : signature identique => ne pas rappeler le provider.
    Ne publie pas editorial_plan.json. Phase 4A n'écrit pas de cache production.
    """

    def __init__(self) -> None:
        self._hits: dict[str, str] = {}

    def remember(self, signature: str, plan_sha256: str) -> None:
        self._hits[signature] = plan_sha256

    def lookup(self, signature: str) -> str | None:
        return self._hits.get(signature)

    def is_hit(self, signature: str) -> bool:
        return signature in self._hits

    def to_dict(self) -> dict[str, str]:
        return dict(self._hits)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "EditorialPlanCache":
        cache = cls()
        if isinstance(payload, Mapping):
            for key, value in payload.items():
                cache.remember(str(key), str(value))
        return cache


def load_cache_file(path: Path) -> EditorialPlanCache:
    path = Path(path)
    if not path.is_file():
        return EditorialPlanCache()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return EditorialPlanCache()
    records = payload.get("signatures") if isinstance(payload, Mapping) else None
    return EditorialPlanCache.from_mapping(records if isinstance(records, Mapping) else {})
