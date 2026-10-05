"""Abstract semantic-validation interface. Remote providers fail closed."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from app.book_semantic_gate_4b29.constants import PHASE
from app.book_semantic_gate_4b29.guard import BookSemanticGate29Error, reject_remote_provider


class SemanticModelTransport(Protocol):
    """Injected transport. Must not open a provider connection by default."""

    source: str
    not_terra: bool

    def evaluate(self, request: Mapping[str, Any]) -> Any:
        ...


class BlockedRemoteTransport:
    """Future-provider placeholder. Always fails in 4B.2.9."""

    source = "BLOCKED_REMOTE"
    not_terra = True

    def __init__(self, provider: str | None = None, model: str | None = None) -> None:
        self.provider = provider
        self.model = model
        reject_remote_provider(provider)
        reject_remote_provider(model)

    def evaluate(self, request: Mapping[str, Any]) -> Any:
        reject_remote_provider(self.provider)
        reject_remote_provider(self.model)
        raise BookSemanticGate29Error(
            "Remote semantic providers are disabled in 4B.2.9. "
            "Inject FakeAITransport or RecordedResponseTransport. "
            "API key absence is not the safety mechanism. "
            f"phase={PHASE}"
        )


class RecordedResponseTransport:
    """Replay a locally supplied simulated payload. Not a Terra response."""

    source = "RECORDED_SIMULATED"
    not_terra = True

    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def evaluate(self, request: Mapping[str, Any]) -> Any:
        return self.payload


def require_local_transport(transport: SemanticModelTransport) -> SemanticModelTransport:
    if transport is None:
        raise BookSemanticGate29Error("A local transport must be injected explicitly.")
    if isinstance(transport, BlockedRemoteTransport):
        transport.evaluate({})
    source = str(getattr(transport, "source", "") or "")
    if source in {"openai", "anthropic", "terra", "sonnet"}:
        raise BookSemanticGate29Error(
            f"Remote transport source {source!r} is forbidden in 4B.2.9."
        )
    if getattr(transport, "not_terra", False) is not True:
        raise BookSemanticGate29Error("Transport must declare not_terra=True in 4B.2.9.")
    return transport


__all__ = [
    "BlockedRemoteTransport",
    "RecordedResponseTransport",
    "SemanticModelTransport",
    "require_local_transport",
]
