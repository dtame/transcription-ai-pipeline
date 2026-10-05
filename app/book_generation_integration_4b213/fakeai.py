"""Injected FakeAI transports. Generator and semantic validator stay distinct."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation_integration_4b213.constants import (
    FAKEAI_GENERATOR_ROLE,
    FAKEAI_SEMANTIC_ROLE,
    FAKEAI_SOURCE,
    FIXTURE_KIND,
    NOT_SONNET,
    NOT_TERRA,
    PHASE,
)
from app.book_generation_integration_4b213.fixtures import (
    GENERATION_SCENARIO_NAMES,
    build_synthetic_chapter,
)
from app.book_generation_integration_4b213.guard import (
    BookGenerationIntegration213Error,
    reject_remote_provider,
)
from app.book_semantic_gate_4b212.fakeai import build_scenario_payload

SEMANTIC_SCENARIO_MAP = {
    "fully_supported": "legitimate_paraphrase",
    "invented_causality": "invented_causality",
    "invented_implication": "invented_implication",
    "universal_guarantee": "universal_guarantee",
    "unsupported_reference": "reference_completed_without_proof",
    "legitimate_paraphrase": "legitimate_paraphrase",
    "questionable": "questionable",
    "invalid_json": "invalid_json",
    "missing_response": "missing_response",
    "interruption": "legitimate_paraphrase",
    "invalid_evidence_handle": "unknown_evidence_handle",
    "missing_evidence": "missing_unit",
}

SEMANTIC_SCENARIO_NAMES = tuple(SEMANTIC_SCENARIO_MAP.keys())


class FakeGeneratorTransport:
    """Simulated Book Generator. Never Sonnet. Never a production chapter."""

    source = FAKEAI_SOURCE
    not_terra = NOT_TERRA
    not_sonnet = NOT_SONNET
    role = FAKEAI_GENERATOR_ROLE

    def __init__(self, scenario: str, *, chapter_id: str | None = None) -> None:
        if scenario not in GENERATION_SCENARIO_NAMES:
            raise KeyError(scenario)
        self.scenario = scenario
        self.chapter_id = chapter_id

    def produce_chapter(self, request: Mapping[str, Any] | None = None) -> dict[str, Any]:
        _ = request
        chapter = build_synthetic_chapter(self.scenario, chapter_id=self.chapter_id)
        chapter["generator_transport"] = {
            "source": self.source,
            "role": self.role,
            "not_sonnet": True,
            "not_terra": True,
            "fixture_kind": FIXTURE_KIND,
        }
        return chapter


class FakeSemanticTransport:
    """Simulated Semantic Gate 2.0.2. Never Terra. Never mixed with generation."""

    source = FAKEAI_SOURCE
    not_terra = NOT_TERRA
    not_sonnet = NOT_SONNET
    role = FAKEAI_SEMANTIC_ROLE

    def __init__(
        self,
        scenario: str,
        *,
        missing: bool = False,
        invalid_raw: Any | None = None,
        interrupt_after: int | None = None,
    ) -> None:
        if scenario not in SEMANTIC_SCENARIO_NAMES:
            raise KeyError(scenario)
        self.scenario = scenario
        self.missing = missing or scenario == "missing_response"
        self.invalid_raw = invalid_raw
        self.interrupt_after = interrupt_after
        self.calls = 0

    def evaluate(self, request: Mapping[str, Any]) -> Any:
        self.calls += 1
        if self.interrupt_after is not None and self.calls > self.interrupt_after:
            raise BookGenerationIntegration213Error(
                "Simulated interruption during semantic validation."
            )
        if self.missing:
            return None
        if self.invalid_raw is not None:
            return self.invalid_raw
        prepared = dict(request.get("local_prepared") or {})
        mapped = SEMANTIC_SCENARIO_MAP[self.scenario]
        if mapped == "missing_response":
            return None
        if mapped == "invalid_json":
            return "{not json"
        chapter = str(
            (request.get("model_input") or {}).get("ch")
            or request.get("chapter_id")
            or "SYN-CH001"
        )
        kind = str(request.get("paragraph_kind") or "")
        name = mapped
        if (
            kind == "connective"
            and self.scenario
            not in {"invalid_json", "missing_response", "interruption"}
        ):
            name = "legitimate_paraphrase"
        payload = build_scenario_payload(name, prepared)
        if isinstance(payload, dict):
            payload = dict(payload)
            payload["ch"] = chapter
        return payload


class BlockedRemoteIntegrationTransport:
    """Future-provider placeholder. Always fails in 4B.2.13."""

    source = "BLOCKED_REMOTE"
    not_terra = True
    not_sonnet = True
    role = "blocked_remote"

    def __init__(self, provider: str | None = None, model: str | None = None) -> None:
        self.provider = provider
        self.model = model
        reject_remote_provider(provider)
        reject_remote_provider(model)

    def produce_chapter(self, request: Mapping[str, Any] | None = None) -> dict[str, Any]:
        _ = request
        raise BookGenerationIntegration213Error(
            "Remote book generation is disabled in 4B.2.13. "
            "Inject FakeGeneratorTransport. "
            f"phase={PHASE}"
        )

    def evaluate(self, request: Mapping[str, Any]) -> Any:
        _ = request
        reject_remote_provider(self.provider)
        reject_remote_provider(self.model)
        raise BookGenerationIntegration213Error(
            "Remote semantic providers are disabled in 4B.2.13. "
            "Inject FakeSemanticTransport. "
            f"phase={PHASE}"
        )


def wrap_fakeai(payload: Any, *, role: str, scenario: str) -> dict[str, Any]:
    return {
        "source": FAKEAI_SOURCE,
        "role": role,
        "not_terra": True,
        "not_sonnet": True,
        "fixture_kind": FIXTURE_KIND,
        "scenario": scenario,
        "payload": payload,
    }


__all__ = [
    "BlockedRemoteIntegrationTransport",
    "FakeGeneratorTransport",
    "FakeSemanticTransport",
    "SEMANTIC_SCENARIO_MAP",
    "SEMANTIC_SCENARIO_NAMES",
    "wrap_fakeai",
]
