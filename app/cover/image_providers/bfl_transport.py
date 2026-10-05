"""HTTP boundary for Black Forest Labs.

The live transport is sealed by a module constant. Tests inject a mock.
Importing this module does not open a socket and does not import requests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LIVE_HTTP_ENABLED = False


class NetworkSealed(RuntimeError):
    """A live provider socket was requested while this phase seals it."""


@dataclass
class TransportRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes | None = None
    timeout_seconds: float = 30.0

    def public_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "url": self.url,
            "header_names": sorted(self.headers),
            "body_present": self.body is not None,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class TransportResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    url: str
    redirected_to: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def header(self, name: str) -> str | None:
        wanted = name.lower()
        for key, value in self.headers.items():
            if key.lower() == wanted:
                return value
        return None


class SealedTransport:
    """Default transport. exchange() is a bug if production code reaches it."""

    def __init__(self) -> None:
        self.calls: list[TransportRequest] = []

    def exchange(self, request: TransportRequest) -> TransportResponse:
        self.calls.append(request)
        raise NetworkSealed("live network is sealed in phase 4B.2.34")


class UrllibTransport:
    """Stdlib client. The phase constant refuses the call before urlopen."""

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds

    def exchange(self, request: TransportRequest) -> TransportResponse:
        if not LIVE_HTTP_ENABLED:
            raise NetworkSealed("LIVE_HTTP_ENABLED is false. No socket will be opened.")
        import urllib.request

        class _RefuseRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
                raise NetworkSealed("urllib must not follow a provider redirect")

        opener = urllib.request.build_opener(_RefuseRedirect)
        http_request = urllib.request.Request(
            request.url,
            data=request.body,
            headers=dict(request.headers),
            method=request.method,
        )
        with opener.open(http_request, timeout=request.timeout_seconds) as response:
            return TransportResponse(
                status=int(response.status),
                headers=dict(response.headers.items()),
                body=response.read(),
                url=response.geturl(),
            )


__all__ = [
    "LIVE_HTTP_ENABLED",
    "NetworkSealed",
    "SealedTransport",
    "TransportRequest",
    "TransportResponse",
    "UrllibTransport",
]
