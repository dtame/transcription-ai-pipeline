"""Offline cases for the sealed FLUX.2 [pro] adapter. No socket is opened."""

from __future__ import annotations

import ast
import hashlib
import json
import struct
import threading
import zlib
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

from app.cover.art.directions import build_front_cover_directions
from app.cover.constants import PAID_CALLS_AUTHORIZED
from app.cover.content.contract import initial_content, store_biography_draft, store_description_draft
from app.cover.image_providers.base import ImageGenerationRequest
from app.cover.image_providers.bfl_download import (
    DownloadRejected,
    download_delivery_image,
    validate_provenance,
)
from app.cover.image_providers.bfl_pricing import FixturePricing, UnverifiedFluxPricing
from app.cover.image_providers.bfl_spec import (
    ENV_API_KEY,
    SUBMIT_URL,
    largest_portrait_generation_size,
)
from app.cover.image_providers.bfl_transport import (
    LIVE_HTTP_ENABLED,
    NetworkSealed,
    SealedTransport,
    TransportRequest,
    TransportResponse,
    UrllibTransport,
)
from app.cover.image_providers.black_forest_labs import (
    BlackForestLabsImageProvider,
    GenerationFailed,
    GenerationOutcomeUnknown,
)
from app.cover.image_providers.policy import PaidCallRefused, evaluate_paid_call
from app.cover.renderer.back_layout import back_cover_composition
from app.cover.renderer.contract import CoverRenderNotAuthorized, CoverRenderer
from app.cover_flux2_pro_4b234.constants import (
    EXPECTED_BOOK_SHA256,
    EXPECTED_INTERIOR_DOCX_SHA256,
    EXPECTED_INTERIOR_PDF_SHA256,
)
from app.cover_generator_foundation_4b233.hashes import snapshot
from app.cover_generator_foundation_4b233.paths import production_book_path, repo_root

FIXTURE_KEY = "fixture-bfl-key-9f3a"
DELIVERY_URL = "https://delivery.us.bfl.ai/result/sample.png"
POLL_URL = "https://api.bfl.ai/v1/get_result?id=task-1"


def evaluate_cases() -> dict[str, Any]:
    cases = []
    for name, function in CASES:
        try:
            detail = function() or "ok"
            cases.append({"name": name, "passed": True, "detail": _redact(detail)})
        except Exception as exc:
            cases.append(
                {
                    "name": name,
                    "passed": False,
                    "detail": _redact(f"{type(exc).__name__}: {exc}"),
                }
            )
    failed = [case["name"] for case in cases if not case["passed"]]
    return {
        "passed": len(cases) - len(failed),
        "failed": len(failed),
        "failed_names": failed,
        "live_provider_calls": 0,
        "paid_cost_usd": 0,
        "cases": cases,
    }


def case_missing_api_key() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _closed(tmp, transport, env={})
        refused = _must(PaidCallRefused, lambda: provider.generate(_request()))
        assert "api_key_missing" in refused.reasons
        assert transport.calls == []
    return "api_key_missing"


def case_fake_key_still_blocked() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _closed(tmp, transport, env={ENV_API_KEY: FIXTURE_KEY})
        refused = _must(PaidCallRefused, lambda: provider.generate(_request()))
        assert "api_key_missing" not in refused.reasons
        assert "dry_run" in refused.reasons
        assert transport.calls == []
        assert FIXTURE_KEY not in str(refused)
        public = json.dumps(provider.check_availability())
        assert FIXTURE_KEY not in public
    return "fake key does not authorize a call"


def case_dry_run() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport, dry_run=True)
        refused = _must(PaidCallRefused, lambda: provider.generate(_request()))
        assert "dry_run" in refused.reasons
        assert transport.calls == []
    return "dry_run"


def case_authorization_absent() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport, authorization_missing=True)
        refused = _must(PaidCallRefused, lambda: provider.generate(_request()))
        assert "explicit_authorization_missing" in refused.reasons
        assert transport.calls == []
    return "explicit_authorization_missing"


def case_authorization_disabled() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport, auth=_auth(enabled=False))
        refused = _must(PaidCallRefused, lambda: provider.generate(_request()))
        assert "authorization_disabled" in refused.reasons
        assert transport.calls == []
    return "authorization_disabled"


def case_provider_mismatch() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport, auth=_auth(provider_id="other_vendor"))
        refused = _must(PaidCallRefused, lambda: provider.generate(_request()))
        assert "provider_not_authorized" in refused.reasons
        assert transport.calls == []
    return "provider_not_authorized"


def case_model_mismatch() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport)
        refused = _must(
            PaidCallRefused,
            lambda: provider.generate(_request(model_name="flux-2-pro-preview")),
        )
        assert "model_not_authorized" in refused.reasons
        assert transport.calls == []
    return "model_not_authorized"


def case_zero_budget() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport, auth=_auth(max_budget_usd=0, max_total_cost_usd=0))
        refused = _must(PaidCallRefused, lambda: provider.generate(_request()))
        assert "budget_zero" in refused.reasons
        assert transport.calls == []
    return "budget_zero"


def case_insufficient_budget() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(
            tmp,
            transport,
            auth=_auth(max_budget_usd=0.01, max_total_cost_usd=0.01),
        )
        refused = _must(PaidCallRefused, lambda: provider.generate(_request()))
        assert "estimated_cost_exceeds_cap" in refused.reasons
        assert transport.calls == []
    return "estimated_cost_exceeds_cap"


def case_unknown_cost() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport, pricing=UnverifiedFluxPricing())
        refused = _must(PaidCallRefused, lambda: provider.generate(_request()))
        assert "estimated_cost_unknown" in refused.reasons
        assert transport.calls == []
    return "estimated_cost_unknown"


def case_image_count_exceeded() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport, auth=_auth(max_images=1))
        refused = _must(PaidCallRefused, lambda: provider.generate(_request(image_count=2)))
        assert "image_count_exceeds_authorization" in refused.reasons
        assert transport.calls == []
    return "image_count_exceeds_authorization"


def case_budget_exhausted() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport, auth=_auth(max_budget_usd=1, max_images=1))
        provider.ledger.reserve(estimate_usd=1, image_count=1, max_images=1, max_budget_usd=1)
        refused = _must(PaidCallRefused, lambda: provider.generate(_request()))
        assert "budget_exhausted" in refused.reasons
        assert transport.calls == []
    return "budget_exhausted"


def case_authorization_consumed() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([_submit_response()])
        provider = _open(tmp, transport)
        first = provider.generate(_request())
        assert first["status"] == "submitted"
        assert first["generated"] is False
        refused = _must(PaidCallRefused, lambda: provider.generate(_request()))
        assert "authorization_already_consumed" in refused.reasons
        assert len(transport.calls) == 1
    return "authorization_already_consumed"


def case_persistent_reservation() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([_submit_response()])
        ledger = Path(tmp) / "ledger.json"
        first = _open(tmp, transport, ledger=ledger)
        first.generate(_request())
        second = _open(tmp, _script([]), ledger=ledger)
        refused = _must(PaidCallRefused, lambda: second.generate(_request()))
        assert "authorization_already_consumed" in refused.reasons
        assert json.loads(ledger.read_text(encoding="utf-8"))["reservations"]
    return "reservation persisted"


def case_concurrent_calls() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([_submit_response()])
        ledger = Path(tmp) / "ledger.json"
        barrier = threading.Barrier(2)
        outcomes: list[Any] = []

        def worker() -> None:
            provider = _open(tmp, transport, ledger=ledger)
            try:
                barrier.wait(timeout=5)
                outcomes.append(provider.generate(_request()))
            except Exception as exc:
                outcomes.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        successes = [item for item in outcomes if isinstance(item, dict)]
        refusals = [item for item in outcomes if isinstance(item, PaidCallRefused)]
        assert len(successes) == 1, outcomes
        assert len(refusals) == 1, outcomes
        assert len(transport.calls) == 1
        assert "authorization_already_consumed" in refusals[0].reasons
    return "one reservation, one submission"


def case_timeout() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([TimeoutError("timed out")])
        provider = _open(tmp, transport)
        unknown = _must(GenerationOutcomeUnknown, lambda: provider.generate(_request()))
        assert unknown.status == "timeout"
        assert len(transport.calls) == 1
        assert provider.ledger.summary()["outcome_unknown"] is True
    return "timeout"


def case_ambiguous_response() -> str:
    with TemporaryDirectory() as tmp:
        body = json.dumps({"unexpected": True}).encode("utf-8")
        transport = _script([TransportResponse(200, {"content-type": "application/json"}, body, SUBMIT_URL)])
        provider = _open(tmp, transport)
        unknown = _must(GenerationOutcomeUnknown, lambda: provider.generate(_request()))
        assert unknown.status == "ambiguous_submit_response"
        assert len(transport.calls) == 1
    return "ambiguous_submit_response"


def case_generation_error() -> str:
    with TemporaryDirectory() as tmp:
        error = json.dumps({"id": "task-1", "status": "Error", "result": None}).encode("utf-8")
        transport = _script(
            [
                _submit_response(),
                TransportResponse(200, {"content-type": "application/json"}, error, POLL_URL),
            ]
        )
        provider = _open(tmp, transport)
        submitted = provider.generate(_request())
        failed = _must(GenerationFailed, lambda: provider.poll(submitted["reservation_id"]))
        assert failed.status == "Error"
        posts = [call for call in transport.calls if call["method"] == "POST"]
        assert len(posts) == 1
    return "generation error does not submit again"


def case_no_automatic_paid_retry() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([TimeoutError("timed out")])
        provider = _open(tmp, transport)
        _must(GenerationOutcomeUnknown, lambda: provider.generate(_request()))
        _must(PaidCallRefused, lambda: provider.generate(_request()))
        assert len(transport.calls) == 1
        assert provider.ledger.summary()["reservations"][0]["retry_count"] == 0
    return "no automatic retry"


def case_invalid_result_url() -> str:
    with TemporaryDirectory() as tmp:
        refused = _must(
            DownloadRejected,
            lambda: download_delivery_image(
                transport=_script([]),
                url="https://example.com/cover.png",
                destination=Path(tmp) / "cover.png",
                provenance=_provenance(),
            ),
        )
        assert refused.reason == "delivery_url_not_allowed"
        assert not (Path(tmp) / "cover.png").exists()
    return "delivery_url_not_allowed"


def case_unauthorized_redirect() -> str:
    transport = _script(
        [
            TransportResponse(
                302,
                {"location": "https://evil.example/cover.png"},
                b"",
                DELIVERY_URL,
            )
        ]
    )
    with TemporaryDirectory() as tmp:
        refused = _must(
            DownloadRejected,
            lambda: download_delivery_image(
                transport=transport,
                url=DELIVERY_URL,
                destination=Path(tmp) / "cover.png",
                provenance=_provenance(),
            ),
        )
        assert refused.reason == "unauthorized_redirect"
        assert len(transport.calls) == 1
    return "unauthorized_redirect"


def case_corrupt_image() -> str:
    payload = b"\x89PNG\r\n\x1a\nnot-a-png"
    transport = _script([TransportResponse(200, {"content-type": "image/png"}, payload, DELIVERY_URL)])
    with TemporaryDirectory() as tmp:
        destination = Path(tmp) / "cover.png"
        refused = _must(
            DownloadRejected,
            lambda: download_delivery_image(
                transport=transport,
                url=DELIVERY_URL,
                destination=destination,
                provenance=_provenance(),
            ),
        )
        assert refused.reason == "corrupt_image"
        assert not destination.exists()
        assert not Path(str(destination) + ".partial").exists()
    return "corrupt_image"


def case_file_too_large() -> str:
    payload = _png()
    transport = _script(
        [TransportResponse(200, {"content-type": "image/png", "content-length": "999999"}, payload, DELIVERY_URL)]
    )
    with TemporaryDirectory() as tmp:
        refused = _must(
            DownloadRejected,
            lambda: download_delivery_image(
                transport=transport,
                url=DELIVERY_URL,
                destination=Path(tmp) / "cover.png",
                provenance=_provenance(),
                max_bytes=64,
            ),
        )
        assert refused.reason == "file_too_large"
    return "file_too_large"


def case_missing_metadata() -> str:
    refused = _must(DownloadRejected, lambda: validate_provenance({}))
    assert refused.reason.startswith("metadata_missing")
    return "metadata_missing"


def case_sha256() -> str:
    payload = _png()
    transport = _script([TransportResponse(200, {"content-type": "image/png"}, payload, DELIVERY_URL)])
    with TemporaryDirectory() as tmp:
        destination = Path(tmp) / "cover.png"
        stored = download_delivery_image(
            transport=transport,
            url=DELIVERY_URL,
            destination=destination,
            provenance=_provenance(),
        )
        assert stored["sha256"] == hashlib.sha256(payload).hexdigest()
        assert hashlib.sha256(destination.read_bytes()).hexdigest() == stored["sha256"]
        assert stored["generated"] is True
        assert stored["metadata"]["signed_url_stored"] is False
    return "sha256 matches the stored file"


def case_no_real_generation() -> str:
    with TemporaryDirectory() as tmp:
        transport = SealedTransport()
        provider = BlackForestLabsImageProvider(transport=transport, ledger_path=Path(tmp) / "ledger.json", env={})
        _must(PaidCallRefused, lambda: provider.generate(_request()))
        assert transport.calls == []
        assert provider.check_availability()["reachable"] == "NOT_CONTACTED"
        assert LIVE_HTTP_ENABLED is False
    return "not contacted"


def case_no_paid_endpoint_calls() -> str:
    import urllib.request

    hits: list[str] = []

    def boom(*args: Any, **kwargs: Any) -> Any:
        hits.append("urlopen")
        raise AssertionError("live socket")

    original = urllib.request.urlopen
    urllib.request.urlopen = boom
    try:
        sealed = _must(
            NetworkSealed,
            lambda: UrllibTransport().exchange(
                TransportRequest(method="POST", url=SUBMIT_URL, headers={}, body=b"{}")
            ),
        )
        assert "No socket" in str(sealed)
        assert hits == []
        assert LIVE_HTTP_ENABLED is False
    finally:
        urllib.request.urlopen = original
    return "urllib sealed"


def case_no_cover_docx() -> str:
    with TemporaryDirectory() as tmp:
        destination = Path(tmp) / "front_cover.docx"
        _must(CoverRenderNotAuthorized, lambda: CoverRenderer().render_front_docx({}, destination))
        _must(CoverRenderNotAuthorized, lambda: CoverRenderer().render_back_docx({}, destination))
        assert not destination.exists()
    return "docx refused"


def case_no_cover_pdf() -> str:
    with TemporaryDirectory() as tmp:
        destination = Path(tmp) / "front_cover.pdf"
        _must(CoverRenderNotAuthorized, lambda: CoverRenderer().render_front_pdf({}, destination))
        _must(CoverRenderNotAuthorized, lambda: CoverRenderer().render_back_pdf({}, destination))
        assert not destination.exists()
    return "pdf refused"


def case_canonical_unchanged() -> str:
    snap = snapshot()
    assert snap["book_json"]["sha256"] == EXPECTED_BOOK_SHA256
    return "book.json matches"


def case_interior_unchanged() -> str:
    snap = snapshot()
    assert snap["interior_docx"]["sha256"] == EXPECTED_INTERIOR_DOCX_SHA256
    assert snap["interior_pdf"]["sha256"] == EXPECTED_INTERIOR_PDF_SHA256
    return "interior matches"


def case_foundation_lock_and_import_scan() -> str:
    decision = evaluate_paid_call(
        authorization={
            "explicit": True,
            "provider_id": "black_forest_labs",
            "model_name": "flux-2-pro",
            "max_images": 1,
            "max_budget_usd": 1,
            "network_calls_allowed": True,
        },
        request={"provider_id": "black_forest_labs", "model_name": "flux-2-pro", "image_count": 1},
        estimate_usd=0.05,
    )
    assert decision["allowed"] is False
    assert "paid_calls_disabled" in decision["reasons"]
    assert PAID_CALLS_AUTHORIZED is False
    banned = {"requests", "openai", "anthropic", "torch", "diffusers", "huggingface_hub", "httpx"}
    hits: list[str] = []
    for path in (repo_root() / "app" / "cover").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            hits.extend(name for name in names if name in banned)
    assert hits == []
    return "foundation lock and import scan"


def case_print_size_not_submitted() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport)
        refused = _must(
            PaidCallRefused,
            lambda: provider.generate(_request(width_px=1800, height_px=2700)),
        )
        assert "dimensions_not_accepted_by_api" in refused.reasons
        assert transport.calls == []
    return "print pixels are not submitted"


def case_negative_prompt_not_transmitted() -> str:
    seen: dict[str, Any] = {}

    def capture(request: TransportRequest) -> TransportResponse:
        seen["body"] = json.loads(request.body.decode("utf-8"))
        seen["has_key_header"] = "x-key" in request.headers
        return _submit_response()

    with TemporaryDirectory() as tmp:
        transport = _script([capture])
        provider = _open(tmp, transport)
        result = provider.generate(_request(negative_prompt="text, letters, logo"))
        assert result["negative_prompt_transmitted"] is False
        assert "negative_prompt" not in seen["body"]
        assert seen["body"]["output_format"] == "png"
        assert seen["body"]["disable_pup"] is True
        assert seen["has_key_header"] is True
        assert FIXTURE_KEY not in json.dumps(result)
    return "negative prompt omitted from the body"


def case_art_directions_follow_the_book() -> str:
    book = json.loads(production_book_path().read_text(encoding="utf-8"))
    directions = build_front_cover_directions(book)
    assert len(directions) == 3
    blob = json.dumps(directions)
    assert "The Life You Already Inherited" not in "".join(item["prompt"] for item in directions)
    for phrase in ("no words", "no letters", "no logo", "no barcode", "no watermark"):
        assert phrase in blob
    assert all(item["negative_prompt_transmitted"] is False for item in directions)
    assert all(item["image_generated"] is False for item in directions)
    return "3 directions, no image"


def case_back_cover_reflow() -> str:
    missing = back_cover_composition(initial_content(None))
    assert missing["author_biography_status"] == "MISSING_OPTIONAL"
    assert missing["book_description_status"] == "NOT_STARTED"
    assert missing["arrangement"] == "color_field_only"
    assert missing["background_color"] is None
    assert missing["invented_biography"] is False
    described = store_description_draft(initial_content(None), "A human supplied this description draft.")
    described_plan = back_cover_composition(described)
    assert described_plan["arrangement"] == "description_uses_the_full_text_column"
    both = store_biography_draft(described, "A human supplied this optional biography.")
    both_plan = back_cover_composition(both)
    assert both_plan["blocks"] == ["book_description", "author_biography"]
    assert both_plan["arrangement"] == "description_then_biography"
    assert missing["pdf_generated"] is False
    return "back cover reflows and is not exported"


CASES: list[tuple[str, Callable[[], str]]] = [
    ("01_missing_api_key", case_missing_api_key),
    ("02_fake_api_key", case_fake_key_still_blocked),
    ("03_dry_run", case_dry_run),
    ("04_authorization_absent", case_authorization_absent),
    ("05_authorization_disabled", case_authorization_disabled),
    ("06_provider_not_authorized", case_provider_mismatch),
    ("07_model_not_authorized", case_model_mismatch),
    ("08_zero_budget", case_zero_budget),
    ("09_insufficient_budget", case_insufficient_budget),
    ("10_unknown_cost", case_unknown_cost),
    ("11_image_count_exceeded", case_image_count_exceeded),
    ("12_budget_exhausted", case_budget_exhausted),
    ("13_authorization_consumed", case_authorization_consumed),
    ("14_persistent_reservation", case_persistent_reservation),
    ("15_concurrent_calls", case_concurrent_calls),
    ("16_timeout", case_timeout),
    ("17_ambiguous_response", case_ambiguous_response),
    ("18_generation_error", case_generation_error),
    ("19_no_automatic_paid_retry", case_no_automatic_paid_retry),
    ("20_invalid_result_url", case_invalid_result_url),
    ("21_unauthorized_redirect", case_unauthorized_redirect),
    ("22_corrupt_image", case_corrupt_image),
    ("23_file_too_large", case_file_too_large),
    ("24_missing_metadata", case_missing_metadata),
    ("25_sha256", case_sha256),
    ("26_no_real_generation", case_no_real_generation),
    ("27_no_paid_endpoint_calls", case_no_paid_endpoint_calls),
    ("28_no_cover_docx", case_no_cover_docx),
    ("29_no_cover_pdf", case_no_cover_pdf),
    ("30_canonical_unchanged", case_canonical_unchanged),
    ("31_interior_unchanged", case_interior_unchanged),
    ("32_foundation_lock", case_foundation_lock_and_import_scan),
    ("33_print_size_not_submitted", case_print_size_not_submitted),
    ("34_negative_prompt_not_transmitted", case_negative_prompt_not_transmitted),
    ("35_art_directions", case_art_directions_follow_the_book),
    ("36_back_cover_reflow", case_back_cover_reflow),
]
CASE_NAMES = [name for name, _function in CASES]


def _auth(**overrides: Any) -> dict[str, Any]:
    auth = {
        "enabled": True,
        "explicit": True,
        "provider_id": "black_forest_labs",
        "model_name": "flux-2-pro",
        "max_images": 1,
        "max_budget_usd": 1,
        "max_total_cost_usd": 1,
        "allow_paid_calls": True,
        "network_calls_allowed": True,
        "dry_run": False,
        "prior_phase_unspent_budget_usd": None,
    }
    auth.update(overrides)
    return auth


def _request(**overrides: Any) -> ImageGenerationRequest:
    width, height = largest_portrait_generation_size()
    values: dict[str, Any] = {
        "provider_id": "black_forest_labs",
        "model_name": "flux-2-pro",
        "model_version": "pinned-snapshot",
        "prompt": "A quiet plaster wall and an already lit lamp. No text.",
        "negative_prompt": "text, letters, logo",
        "width_px": width,
        "height_px": height,
        "aspect_ratio": "2:3",
        "seed": 7,
        "image_count": 1,
        "output_paths": [],
        "metadata": {},
        "embed_text": False,
        "estimated_cost_usd": None,
    }
    values.update(overrides)
    return ImageGenerationRequest(**values)


def _open(tmp: str, transport: Any, **overrides: Any) -> BlackForestLabsImageProvider:
    ledger = overrides.pop("ledger", Path(tmp) / "ledger.json")
    auth = overrides.pop("auth", _auth())
    missing = overrides.pop("authorization_missing", False)
    return BlackForestLabsImageProvider(
        transport=transport,
        authorization=None if missing else auth,
        authorization_missing=missing,
        ledger_path=ledger,
        env={ENV_API_KEY: FIXTURE_KEY},
        dry_run=overrides.pop("dry_run", False),
        pricing=overrides.pop("pricing", FixturePricing(0.05)),
        phase_lock=False,
        allow_mock_submission=True,
        **overrides,
    )


def _closed(tmp: str, transport: Any, *, env: dict[str, str]) -> BlackForestLabsImageProvider:
    return BlackForestLabsImageProvider(
        transport=transport,
        ledger_path=Path(tmp) / "ledger.json",
        env=env,
    )


def _script(items: list[Any]) -> Any:
    class _Script:
        def __init__(self) -> None:
            self.script = list(items)
            self.calls: list[dict[str, str]] = []

        def exchange(self, request: TransportRequest) -> TransportResponse:
            self.calls.append({"method": request.method, "url": request.url})
            if not self.script:
                raise AssertionError("unexpected http exchange")
            item = self.script.pop(0)
            if isinstance(item, Exception):
                raise item
            if callable(item):
                return item(request)
            return item

    return _Script()


def _submit_response() -> TransportResponse:
    body = {"id": "task-1", "polling_url": POLL_URL, "cost": None}
    return TransportResponse(
        status=200,
        headers={"content-type": "application/json"},
        body=json.dumps(body).encode("utf-8"),
        url=SUBMIT_URL,
    )


def _provenance() -> dict[str, str]:
    return {
        "provider_id": "black_forest_labs",
        "model_id": "flux-2-pro",
        "task_id": "task-1",
        "prompt_sha256": "abc",
        "output_format": "png",
    }


def _png() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\x10\x20\x30"
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def _must(exc_type: type[BaseException], function: Callable[[], Any]) -> Any:
    try:
        function()
    except exc_type as exc:
        return exc
    raise AssertionError(f"{exc_type.__name__} was not raised")


def _redact(text: str) -> str:
    return text.replace(FIXTURE_KEY, "[redacted]")


__all__ = ["CASE_NAMES", "evaluate_cases"]
