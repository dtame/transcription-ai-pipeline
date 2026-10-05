"""Local proof that the live-HTTP flag is read at call time.

This probe never lets urllib open a socket. A patched opener raises before
any provider request is sent.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from app.cover.image_providers.bfl_transport import (
    NetworkSealed,
    TransportRequest,
    UrllibTransport,
)
from app.cover.image_providers.openai_spec import GENERATION_URL
from app.cover_first_real_image_4b2344.transport import SingleUseLiveTransport
import app.cover.image_providers.bfl_transport as live_transport


def verify_network_fix() -> dict[str, Any]:
    """Return a local report. ``passed`` is false if the sealed-flag bug remains."""

    source = Path(live_transport.__file__).read_text(encoding="utf-8")
    single_source = inspect.getsource(SingleUseLiveTransport.exchange)
    init_source = inspect.getsource(SingleUseLiveTransport.__init__)
    urllib_source = inspect.getsource(UrllibTransport.exchange)
    report: dict[str, Any] = {
        "provider_contacted": False,
        "socket_opened_to_openai": False,
        "source_assigns_live_http_enabled_false": "LIVE_HTTP_ENABLED = False" in source,
        "source_assigns_live_http_enabled_true": "LIVE_HTTP_ENABLED = True" in source,
        "single_use_reads_module_attribute": "live_transport.LIVE_HTTP_ENABLED" in single_source,
        "single_use_copies_flag_at_init": "LIVE_HTTP_ENABLED" in init_source,
        "urllib_reads_module_global_at_exchange": "if not LIVE_HTTP_ENABLED:" in urllib_source,
        "urllib_captures_flag_as_default_argument": "LIVE_HTTP_ENABLED" in (
            inspect.signature(UrllibTransport.exchange).parameters
        ),
        "flag_at_start": live_transport.LIVE_HTTP_ENABLED,
        "sealed_path_refused_before_urllib": False,
        "enabled_after_import_reaches_urllib": False,
        "urllib_sealed_path_does_not_open": False,
        "urllib_enabled_after_import_reaches_opener": False,
        "flag_after": None,
        "passed": False,
    }
    if live_transport.LIVE_HTTP_ENABLED:
        report["failure"] = "LIVE_HTTP_ENABLED was already true before the local probe"
        report["flag_after"] = live_transport.LIVE_HTTP_ENABLED
        return report

    sealed_calls = {"urllib": 0}
    original_urllib = UrllibTransport.exchange

    def _count_urllib(self: UrllibTransport, request: TransportRequest) -> Any:
        sealed_calls["urllib"] += 1
        raise AssertionError("urllib was entered while the live flag was false")

    UrllibTransport.exchange = _count_urllib  # type: ignore[method-assign]
    try:
        transport = SingleUseLiveTransport()
        try:
            transport.exchange(_probe_request())
        except NetworkSealed:
            report["sealed_path_refused_before_urllib"] = (
                sealed_calls["urllib"] == 0 and transport.trace.get("socket_opened") is False
            )
    finally:
        UrllibTransport.exchange = original_urllib  # type: ignore[method-assign]
        live_transport.LIVE_HTTP_ENABLED = False

    enabled_calls = {"urllib": 0}

    def _count_enabled(self: UrllibTransport, request: TransportRequest) -> Any:
        enabled_calls["urllib"] += 1
        raise RuntimeError("local probe refused the socket")

    UrllibTransport.exchange = _count_enabled  # type: ignore[method-assign]
    try:
        live_transport.LIVE_HTTP_ENABLED = True
        transport = SingleUseLiveTransport()
        try:
            transport.exchange(_probe_request())
        except RuntimeError as exc:
            report["enabled_after_import_reaches_urllib"] = (
                str(exc) == "local probe refused the socket" and enabled_calls["urllib"] == 1
            )
        else:
            report["enabled_after_import_reaches_urllib"] = False
    finally:
        UrllibTransport.exchange = original_urllib  # type: ignore[method-assign]
        live_transport.LIVE_HTTP_ENABLED = False

    import urllib.request

    opener_calls = {"open": 0}
    original_open = urllib.request.OpenerDirector.open

    def _refuse_open(self: Any, *args: Any, **kwargs: Any) -> Any:
        opener_calls["open"] += 1
        raise RuntimeError("local probe refused the socket")

    urllib.request.OpenerDirector.open = _refuse_open  # type: ignore[method-assign]
    try:
        try:
            UrllibTransport().exchange(_probe_request())
        except NetworkSealed:
            report["urllib_sealed_path_does_not_open"] = opener_calls["open"] == 0
        live_transport.LIVE_HTTP_ENABLED = True
        try:
            UrllibTransport().exchange(_probe_request())
        except RuntimeError as exc:
            report["urllib_enabled_after_import_reaches_opener"] = (
                str(exc) == "local probe refused the socket" and opener_calls["open"] == 1
            )
    finally:
        urllib.request.OpenerDirector.open = original_open  # type: ignore[method-assign]
        live_transport.LIVE_HTTP_ENABLED = False

    report["flag_after"] = live_transport.LIVE_HTTP_ENABLED
    report["passed"] = bool(
        report["source_assigns_live_http_enabled_false"]
        and not report["source_assigns_live_http_enabled_true"]
        and report["single_use_reads_module_attribute"]
        and not report["single_use_copies_flag_at_init"]
        and report["urllib_reads_module_global_at_exchange"]
        and not report["urllib_captures_flag_as_default_argument"]
        and report["flag_at_start"] is False
        and report["sealed_path_refused_before_urllib"]
        and report["enabled_after_import_reaches_urllib"]
        and report["urllib_sealed_path_does_not_open"]
        and report["urllib_enabled_after_import_reaches_opener"]
        and report["flag_after"] is False
        and report["provider_contacted"] is False
        and report["socket_opened_to_openai"] is False
    )
    return report


def _probe_request() -> TransportRequest:
    return TransportRequest(method="POST", url=GENERATION_URL, headers={}, body=b"{}")


__all__ = ["verify_network_fix"]
