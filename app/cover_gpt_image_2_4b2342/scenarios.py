"""Offline cases for the GPT Image 2 adapter. No socket is opened."""

from __future__ import annotations

import base64
import json
import struct
import threading
import zlib
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

from app.cover.constants import (
    IMAGE_GENERATION_AUTHORIZED,
    NETWORK_CALLS_AUTHORIZED,
    PAID_CALLS_AUTHORIZED,
)
from app.cover.content.contract import initial_content
from app.cover.image_providers.base import ImageGenerationRequest
from app.cover.image_providers.bfl_spec import (
    OFFICIAL_MODEL_ID as BFL_MODEL_ID,
    largest_portrait_generation_size,
)
from app.cover.image_providers.bfl_transport import LIVE_HTTP_ENABLED, SealedTransport, TransportRequest, TransportResponse
from app.cover.image_providers.black_forest_labs import BlackForestLabsImageProvider
from app.cover.image_providers.openai_art import PROMPT, prompt_record
from app.cover.image_providers.openai_image import (
    GenerationFailed,
    GenerationOutcomeUnknown,
    OpenAIImageProvider,
    default_openai_authorization,
)
from app.cover.image_providers.openai_pricing import FixtureImagePricing, TokenBillingPricing
from app.cover.image_providers.openai_spec import (
    ENV_API_KEY,
    GENERATION_URL,
    OFFICIAL_MODEL_ID,
    SELECTED_HEIGHT,
    SELECTED_WIDTH,
    SNAPSHOT_MODEL_ID,
    SpecError,
    api_dimension_problems,
    candidate_sizes,
    print_resolution_plan,
    published_image_output_estimate_usd,
    submission_body,
)
from app.cover.image_providers.policy import PaidCallRefused
from app.cover.renderer.contract import CoverRenderNotAuthorized, CoverRenderer
from app.cover_flux2_pro_4b234.constants import (
    EXPECTED_BOOK_SHA256,
    EXPECTED_INTERIOR_DOCX_SHA256,
    EXPECTED_INTERIOR_PDF_SHA256,
)
from app.cover_flux2_pro_4b2341.constants import AUTHORIZATION_SCOPE as PRIOR_SCOPE
from app.cover_flux2_pro_4b2341.scenarios import evaluate_cases as evaluate_prior_cases
from app.cover_generator_foundation_4b233.hashes import snapshot
from app.cover_generator_foundation_4b233.paths import repo_root
from app.cover_gpt_image_2_4b2342.paths import planned_image_path

FIXTURE_KEY = "test-openai-key-not-real"
_PNG_CACHE: dict[tuple[int, int], bytes] = {}


def evaluate_cases() -> dict[str, Any]:
    cases = []
    for name, function in CASES:
        try:
            detail = function() or "ok"
            cases.append({"name": name, "passed": True, "detail": detail})
        except Exception as exc:
            cases.append(
                {
                    "name": name,
                    "passed": False,
                    "detail": f"{type(exc).__name__}: {exc}",
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


def case_openai_selected() -> str:
    provider = OpenAIImageProvider(env={}, ledger_path=_unused_ledger())
    availability = provider.check_availability()
    assert provider.provider_id == "openai"
    assert availability["model_id"] == "gpt-image-2"
    assert availability["endpoint"] == GENERATION_URL
    assert availability["reachable"] == "NOT_CONTACTED"
    assert availability["key_value_recorded"] is False
    return "openai gpt-image-2"


def case_bfl_retained() -> str:
    transport = SealedTransport()
    provider = BlackForestLabsImageProvider(
        transport=transport,
        env={},
        ledger_path=_unused_ledger(),
    )
    assert provider.provider_id == "black_forest_labs"
    assert provider.get_capabilities().model_name == BFL_MODEL_ID == "flux-2-pro"
    assert largest_portrait_generation_size() == (1632, 2448)
    refused = _must(PaidCallRefused, lambda: provider.generate(_bfl_request()))
    assert refused.reasons
    assert transport.calls == []
    return "flux-2-pro retained"


def case_model_id() -> str:
    assert OFFICIAL_MODEL_ID == "gpt-image-2"
    assert SNAPSHOT_MODEL_ID == "gpt-image-2-2026-04-21"
    body = submission_body(_request())
    assert body["model"] == "gpt-image-2"
    assert "gpt-image-2-2026-04-21" not in body.values()
    return "alias selected; snapshot recorded and not sent"


def case_key_absent() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport, env={})
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp)))
        assert "api_key_missing" in refused.reasons
        assert transport.calls == []
        assert provider.check_availability()["key_present"] is False
    return "api_key_missing"


def case_key_fictive() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = OpenAIImageProvider(
            transport=transport,
            ledger_path=Path(tmp) / "ledger.json",
            env={ENV_API_KEY: FIXTURE_KEY},
            dry_run=True,
        )
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp)))
        assert "api_key_missing" not in refused.reasons
        assert "dry_run" in refused.reasons
        assert FIXTURE_KEY not in str(refused)
        assert FIXTURE_KEY not in json.dumps(provider.check_availability())
        assert transport.calls == []
    return "fixture key not recorded"


def case_authorization_absent() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport, authorization_missing=True)
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp)))
        assert "explicit_authorization_missing" in refused.reasons
        assert transport.calls == []
    return "explicit_authorization_missing"


def case_authorization_disabled() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport, auth=_auth(enabled=False))
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp)))
        assert "authorization_disabled" in refused.reasons
        assert default_openai_authorization()["enabled"] is False
        assert transport.calls == []
    return "authorization_disabled"


def case_prior_authorization_not_reused() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(
            tmp,
            transport,
            auth=_auth(
                provider_id="black_forest_labs",
                model_name="flux-2-pro",
                scope=PRIOR_SCOPE,
            ),
        )
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp)))
        assert "provider_not_authorized" in refused.reasons
        assert "prior_phase_authorization_reused" in refused.reasons
        assert transport.calls == []
    return "phase 4B.2.34.1 authorization refused"


def case_dry_run() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport, dry_run=True)
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp)))
        assert "dry_run" in refused.reasons
        assert transport.calls == []
    return "dry_run"


def case_budget_zero() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport, auth=_auth(max_budget_usd=0, max_total_cost_usd=0))
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp)))
        assert "budget_zero" in refused.reasons
        assert transport.calls == []
    return "budget_zero"


def case_cost_unknown() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(
            tmp,
            transport,
            pricing=TokenBillingPricing(),
            auth=_auth(max_budget_usd=1000, max_total_cost_usd=1000),
        )
        estimate = provider.estimate_cost(_ready(tmp))
        assert estimate["published_image_output_estimate_usd"] == "0.041"
        assert estimate["estimated_cost_usd"] is None
        assert estimate["verified_maximum_cost_usd"] is None
        assert estimate["estimate_is_a_billing_guarantee"] is False
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp)))
        assert "estimated_cost_unknown" in refused.reasons
        assert "billing_ceiling_not_guaranteed" in refused.reasons
        assert transport.calls == []
    return "published 0.041 is not a ceiling"


def case_estimate_above_cap() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(
            tmp,
            transport,
            pricing=FixtureImagePricing(2.0, verified_maximum_usd=2.0),
            auth=_auth(max_budget_usd=0.5, max_total_cost_usd=0.5),
        )
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp)))
        assert "estimated_cost_exceeds_cap" in refused.reasons
        assert "verified_maximum_exceeds_cap" in refused.reasons
        assert transport.calls == []
    return "estimated_cost_exceeds_cap"


def case_persistent_reservation() -> str:
    with TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "ledger.json"
        destination = Path(tmp) / "door.png"
        first = _open(tmp, _script([_image_response()]), ledger=ledger)
        saved = first.generate(_ready(tmp, output_paths=[str(destination)]))
        assert saved["generated"] is True
        second = _open(tmp, _script([]), ledger=ledger)
        refused = _must(
            PaidCallRefused,
            lambda: second.generate(_ready(tmp, output_paths=[str(Path(tmp) / "other.png")])),
        )
        assert "authorization_already_consumed" in refused.reasons
        assert json.loads(ledger.read_text(encoding="utf-8"))["reservations"]
        assert FIXTURE_KEY not in ledger.read_text(encoding="utf-8")
    return "reservation persisted"


def case_concurrency() -> str:
    with TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "ledger.json"
        transport = _script([_image_response()])
        barrier = threading.Barrier(2)
        outcomes: list[Any] = []

        def worker(index: int) -> None:
            provider = _open(tmp, transport, ledger=ledger)
            try:
                barrier.wait(timeout=5)
                outcomes.append(
                    provider.generate(_ready(tmp, output_paths=[str(Path(tmp) / f"door-{index}.png")]))
                )
            except Exception as exc:
                outcomes.append(exc)

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(2)]
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


def case_image_count() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport, auth=_auth(max_images=1))
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp, image_count=2)))
        assert "image_count_exceeds_authorization" in refused.reasons
        assert "endpoint_sends_one_image" in refused.reasons
        assert transport.calls == []
    return "image_count_exceeds_authorization"


def case_invalid_quality() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport)
        refused = _must(
            PaidCallRefused,
            lambda: provider.generate(_ready(tmp, metadata=_meta(quality="xhigh"))),
        )
        assert "quality_not_accepted" in refused.reasons
        assert transport.calls == []
        auto = _must(
            PaidCallRefused,
            lambda: provider.generate(_ready(tmp, metadata=_meta(quality="auto"))),
        )
        assert "quality_not_accepted" in auto.reasons
    return "xhigh and auto refused"


def case_invalid_resolution() -> str:
    assert "not_multiple_of_16" in api_dimension_problems(1000, 1500)
    assert "below_655360_pixels" in api_dimension_problems(640, 960)
    assert "edge_above_3840" in api_dimension_problems(4000, 4000)
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport)
        refused = _must(
            PaidCallRefused,
            lambda: provider.generate(_ready(tmp, width_px=1000, height_px=1500)),
        )
        assert "not_multiple_of_16" in refused.reasons
        assert transport.calls == []
    _must(SpecError, lambda: submission_body(_request(width_px=1000, height_px=1500)))
    return "1000x1500 refused"


def case_invalid_format() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        provider = _open(tmp, transport)
        refused = _must(
            PaidCallRefused,
            lambda: provider.generate(_ready(tmp, metadata=_meta(output_format="gif"))),
        )
        assert "output_format_not_accepted" in refused.reasons
        assert transport.calls == []
    return "gif refused"


def case_simulated_request() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([_image_response()])
        provider = _open(tmp, transport)
        result = provider.generate(_ready(tmp))
        assert len(transport.calls) == 1
        sent = transport.calls[0]
        assert sent.method == "POST"
        assert sent.url == GENERATION_URL
        body = json.loads(sent.body.decode("utf-8"))
        assert body["model"] == "gpt-image-2"
        assert body["size"] == "1024x1536"
        assert body["quality"] == "medium"
        assert body["output_format"] == "png"
        assert body["background"] == "opaque"
        assert body["n"] == 1
        assert body["prompt"] == PROMPT
        for absent in ("stream", "partial_images", "response_format", "seed", "negative_prompt", "image"):
            assert absent not in body
        assert sent.headers["Authorization"] == f"Bearer {FIXTURE_KEY}"
        assert result["generated"] is True
        assert FIXTURE_KEY not in json.dumps({key: value for key, value in result.items() if key != "provider_metadata"})
        assert FIXTURE_KEY not in json.dumps(result["provider_metadata"])
    return "one mocked POST"


def case_simulated_valid_response() -> str:
    with TemporaryDirectory() as tmp:
        destination = Path(tmp) / "door.png"
        provider = _open(tmp, _script([_image_response()]))
        result = provider.generate(_ready(tmp, output_paths=[str(destination)]))
        assert result["generation_status"] == "generated"
        assert result["generated"] is True
        assert result["observed_cost_usd"] is None
        assert destination.is_file()
        digest = destination.read_bytes()
        import hashlib

        assert hashlib.sha256(digest).hexdigest() == result["image_sha256"]
        assert result["provider_metadata"]["width"] == 1024
        assert result["provider_metadata"]["height"] == 1536
    return "png stored after validation"


def case_simulated_invalid_response() -> str:
    with TemporaryDirectory() as tmp:
        destination = Path(tmp) / "door.png"
        payload = {"data": [{"revised_prompt": "changed"}]}
        provider = _open(tmp, _script([_json_response(payload)]))
        unknown = _must(
            GenerationOutcomeUnknown,
            lambda: provider.generate(_ready(tmp, output_paths=[str(destination)])),
        )
        assert unknown.status == "b64_json_missing"
        assert not destination.exists()
        assert provider.ledger.summary()["outcome_unknown"] is True
    return "b64_json_missing"


def case_corrupt_image() -> str:
    with TemporaryDirectory() as tmp:
        destination = Path(tmp) / "door.png"
        encoded = base64.b64encode(b"\x89PNG\r\n\x1a\nnot-a-png").decode("ascii")
        provider = _open(tmp, _script([_json_response({"data": [{"b64_json": encoded}]})]))
        failed = _must(
            GenerationFailed,
            lambda: provider.generate(_ready(tmp, output_paths=[str(destination)])),
        )
        assert failed.status == "corrupt_image"
        assert not destination.exists()
        assert list(Path(tmp).glob("*.png")) == []
        assert provider.ledger.summary()["outcome_unknown"] is True
    return "corrupt_image"


def case_timeout() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([TimeoutError("timed out"), _image_response()])
        provider = _open(tmp, transport)
        unknown = _must(GenerationOutcomeUnknown, lambda: provider.generate(_ready(tmp)))
        assert unknown.status == "timeout"
        assert len(transport.calls) == 1
        assert provider.ledger.summary()["outcome_unknown"] is True
    return "timeout"


def case_http_error() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([_json_response({"error": {"code": "rate_limit_exceeded"}}, status=429)])
        provider = _open(tmp, transport)
        unknown = _must(GenerationOutcomeUnknown, lambda: provider.generate(_ready(tmp)))
        assert unknown.status == "http_429"
        assert len(transport.calls) == 1
    return "http_429"


def case_no_automatic_retry() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([TimeoutError("timed out"), _image_response()])
        provider = _open(tmp, transport)
        _must(GenerationOutcomeUnknown, lambda: provider.generate(_ready(tmp)))
        refused = _must(
            PaidCallRefused,
            lambda: provider.generate(_ready(tmp, output_paths=[str(Path(tmp) / "retry.png")])),
        )
        assert "prior_outcome_unknown" in refused.reasons
        assert len(transport.calls) == 1
        assert provider.ledger.summary()["reservations"][0]["retry_count"] == 0
        assert provider.ledger.summary()["reservations"][0]["automatic_retry"] is False
    return "no second paid call"


def case_no_key_leak() -> str:
    with TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "ledger.json"
        destination = Path(tmp) / "door.png"
        transport = _script([_image_response()])
        provider = _open(tmp, transport, ledger=ledger)
        result = provider.generate(_ready(tmp, output_paths=[str(destination)]))
        blob = "\n".join(
            [
                ledger.read_text(encoding="utf-8"),
                json.dumps(result),
                json.dumps(provider.check_availability()),
                json.dumps(provider.estimate_cost(_ready(tmp))),
            ]
        )
        assert FIXTURE_KEY not in blob
        assert "Bearer" not in blob
        assert transport.calls[0].headers["Authorization"].endswith(FIXTURE_KEY)
    return "fixture key stayed in the mock header only"


def case_no_real_call() -> str:
    assert LIVE_HTTP_ENABLED is False
    assert IMAGE_GENERATION_AUTHORIZED is False
    assert PAID_CALLS_AUTHORIZED is False
    assert NETWORK_CALLS_AUTHORIZED is False
    source = Path(__file__).resolve().parents[1] / "cover" / "image_providers" / "openai_image.py"
    text = source.read_text(encoding="utf-8")
    assert "urlopen" not in text
    assert "import urllib" not in text
    with TemporaryDirectory() as tmp:
        transport = SealedTransport()
        provider = OpenAIImageProvider(transport=transport, ledger_path=Path(tmp) / "ledger.json", env={})
        _must(PaidCallRefused, lambda: provider.generate(_ready(tmp)))
        assert transport.calls == []
    return "live http sealed"


def case_no_image_file() -> str:
    planned = repo_root() / planned_image_path()
    assert not planned.exists()
    assert prompt_record()["image_generated"] is False
    return "planned image absent"


def case_no_cover_files() -> str:
    with TemporaryDirectory() as tmp:
        docx = Path(tmp) / "front_cover.docx"
        pdf = Path(tmp) / "front_cover.pdf"
        _must(CoverRenderNotAuthorized, lambda: CoverRenderer().render_front_docx({}, docx))
        _must(CoverRenderNotAuthorized, lambda: CoverRenderer().render_front_pdf({}, pdf))
        _must(CoverRenderNotAuthorized, lambda: CoverRenderer().render_back_docx({}, Path(tmp) / "back.docx"))
        assert not docx.exists() and not pdf.exists()
    content = initial_content()
    assert content["author_biography_status"] == "MISSING_OPTIONAL"
    assert content["book_description_status"] == "NOT_STARTED"
    assert content["author_biography"] is None
    assert content["book_description"] is None
    return "docx pdf and back cover refused"


def case_resolution_choice() -> str:
    selected = next(row for row in candidate_sizes() if row["selected"])
    assert selected["size"] == "1024x1536"
    assert selected["exact_two_to_three"] is True
    assert selected["experimental"] is False
    assert selected["published_image_output_estimates_usd"]["medium"] == "0.041"
    assert published_image_output_estimate_usd(1536, 2304, "high") is None
    plan = print_resolution_plan()
    assert plan["placement"]["below_300_ppi_on_trim"] is True
    assert plan["professional_print_quality_guaranteed"] is False
    assert plan["flux_limits_reused"] is False
    assert (SELECTED_WIDTH, SELECTED_HEIGHT) == (1024, 1536)
    return "1024x1536 selected"


def case_art_prompt() -> str:
    record = prompt_record()
    assert record["prompt_text_changed"] is False
    assert record["prompt"] == PROMPT
    assert "The Life You Already Inherited" not in PROMPT
    assert "no words" in PROMPT
    assert "already standing open" in PROMPT
    assert record["embed_text"] is False
    return "approved prompt kept"


def case_canonical_unchanged() -> str:
    snap = snapshot()
    assert snap["book_json"]["sha256"] == EXPECTED_BOOK_SHA256
    return "book.json matches"


def case_interior_unchanged() -> str:
    snap = snapshot()
    assert snap["interior_docx"]["sha256"] == EXPECTED_INTERIOR_DOCX_SHA256
    assert snap["interior_pdf"]["sha256"] == EXPECTED_INTERIOR_PDF_SHA256
    return "interior matches"


def case_previous_tests() -> str:
    report = evaluate_prior_cases()
    assert report["failed"] == 0, report["failed_names"]
    assert report["live_provider_calls"] == 0
    assert report["paid_cost_usd"] == 0
    return f"{report['passed']} previous cases passed"


CASES = [
    ("01_openai_selected", case_openai_selected),
    ("02_bfl_retained", case_bfl_retained),
    ("03_model_id", case_model_id),
    ("04_key_absent", case_key_absent),
    ("05_key_fictive", case_key_fictive),
    ("06_authorization_absent", case_authorization_absent),
    ("07_authorization_disabled", case_authorization_disabled),
    ("08_dry_run", case_dry_run),
    ("09_budget_zero", case_budget_zero),
    ("10_cost_unknown", case_cost_unknown),
    ("11_estimate_above_cap", case_estimate_above_cap),
    ("12_persistent_reservation", case_persistent_reservation),
    ("13_concurrency", case_concurrency),
    ("14_image_count", case_image_count),
    ("15_invalid_quality", case_invalid_quality),
    ("16_invalid_resolution", case_invalid_resolution),
    ("17_invalid_format", case_invalid_format),
    ("18_simulated_request", case_simulated_request),
    ("19_simulated_valid_response", case_simulated_valid_response),
    ("20_simulated_invalid_response", case_simulated_invalid_response),
    ("21_corrupt_image", case_corrupt_image),
    ("22_timeout", case_timeout),
    ("23_http_error", case_http_error),
    ("24_no_automatic_retry", case_no_automatic_retry),
    ("25_no_key_leak", case_no_key_leak),
    ("26_no_real_call", case_no_real_call),
    ("27_no_image_file", case_no_image_file),
    ("28_no_cover_docx_pdf", case_no_cover_files),
    ("29_canonical_unchanged", case_canonical_unchanged),
    ("30_interior_unchanged", case_interior_unchanged),
    ("31_prior_authorization_not_reused", case_prior_authorization_not_reused),
    ("32_resolution_choice", case_resolution_choice),
    ("33_art_prompt", case_art_prompt),
    ("34_previous_tests_no_regression", case_previous_tests),
]
CASE_NAMES = [name for name, _function in CASES]


def _auth(**overrides: Any) -> dict[str, Any]:
    auth = {
        "enabled": True,
        "explicit": True,
        "provider_id": "openai",
        "model_name": "gpt-image-2",
        "max_images": 1,
        "max_budget_usd": 1,
        "max_total_cost_usd": 1,
        "allow_paid_calls": True,
        "network_calls_allowed": True,
        "dry_run": False,
        "prior_phase_unspent_budget_usd": None,
        "scope": "COVER_GPT_IMAGE_2_4B2342_OFFLINE_ONLY",
    }
    auth.update(overrides)
    return auth


def _meta(**overrides: Any) -> dict[str, Any]:
    metadata = {"quality": "medium", "output_format": "png", "background": "opaque"}
    metadata.update(overrides)
    return metadata


def _request(**overrides: Any) -> ImageGenerationRequest:
    values: dict[str, Any] = {
        "provider_id": "openai",
        "model_name": "gpt-image-2",
        "model_version": SNAPSHOT_MODEL_ID,
        "prompt": PROMPT,
        "negative_prompt": "text, letters, logo",
        "width_px": SELECTED_WIDTH,
        "height_px": SELECTED_HEIGHT,
        "aspect_ratio": "2:3",
        "seed": 7,
        "image_count": 1,
        "output_paths": [],
        "metadata": _meta(),
        "embed_text": False,
        "estimated_cost_usd": None,
    }
    values.update(overrides)
    return ImageGenerationRequest(**values)


def _ready(tmp: str, **overrides: Any) -> ImageGenerationRequest:
    if "output_paths" not in overrides:
        overrides["output_paths"] = [str(Path(tmp) / "door.png")]
    return _request(**overrides)


def _open(tmp: str, transport: Any, **overrides: Any) -> OpenAIImageProvider:
    ledger = overrides.pop("ledger", Path(tmp) / "ledger.json")
    missing = overrides.pop("authorization_missing", False)
    auth = overrides.pop("auth", _auth())
    env = overrides.pop("env", {ENV_API_KEY: FIXTURE_KEY})
    return OpenAIImageProvider(
        transport=transport,
        authorization=None if missing else auth,
        authorization_missing=missing,
        ledger_path=ledger,
        env=env,
        dry_run=overrides.pop("dry_run", False),
        pricing=overrides.pop("pricing", FixtureImagePricing(0.05, verified_maximum_usd=0.05)),
        phase_lock=False,
        allow_mock_submission=True,
        **overrides,
    )


def _script(items: list[Any]) -> Any:
    class _Script:
        def __init__(self) -> None:
            self.script = list(items)
            self.calls: list[TransportRequest] = []

        def exchange(self, request: TransportRequest) -> TransportResponse:
            self.calls.append(request)
            if not self.script:
                raise AssertionError("unexpected http exchange")
            item = self.script.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

    return _Script()


def _image_response() -> TransportResponse:
    encoded = base64.b64encode(_png(SELECTED_WIDTH, SELECTED_HEIGHT)).decode("ascii")
    return _json_response(
        {
            "created": 1,
            "data": [{"b64_json": encoded}],
            "output_format": "png",
            "quality": "medium",
            "size": "1024x1536",
        }
    )


def _json_response(payload: dict[str, Any], *, status: int = 200) -> TransportResponse:
    return TransportResponse(
        status=status,
        headers={"content-type": "application/json"},
        body=json.dumps(payload).encode("utf-8"),
        url=GENERATION_URL,
    )


def _png(width: int, height: int) -> bytes:
    cached = _PNG_CACHE.get((width, height))
    if cached is not None:
        return cached

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + (b"\x10\x20\x30" * width)
    raw = row * height
    payload = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 1)) + chunk(b"IEND", b"")
    _PNG_CACHE[(width, height)] = payload
    return payload


def _bfl_request() -> ImageGenerationRequest:
    return ImageGenerationRequest(
        provider_id="black_forest_labs",
        model_name="flux-2-pro",
        model_version="pinned-snapshot",
        prompt="A quiet doorway. No text.",
        negative_prompt=None,
        width_px=1632,
        height_px=2448,
        aspect_ratio="2:3",
        seed=None,
        image_count=1,
        output_paths=[],
        metadata={},
        embed_text=False,
    )


def _unused_ledger() -> Path:
    return Path(TemporaryDirectory().name) / "ledger.json"


def _must(exc_type: type[BaseException], function: Callable[[], Any]) -> Any:
    try:
        function()
    except exc_type as exc:
        return exc
    raise AssertionError(f"{exc_type.__name__} was not raised")


__all__ = ["CASE_NAMES", "evaluate_cases"]
