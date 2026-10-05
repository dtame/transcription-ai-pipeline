"""Offline cases for the two-level image budget policy. No socket is opened."""

from __future__ import annotations

import base64
import json
import struct
import threading
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

from app.cover.constants import (
    IMAGE_GENERATION_AUTHORIZED,
    NETWORK_CALLS_AUTHORIZED,
    PAID_CALLS_AUTHORIZED,
)
from app.cover.content.contract import initial_content
from app.cover.image_providers.base import CoverImageProvider, ImageGenerationRequest
from app.cover.image_providers.bfl_budget import ReservationLedger
from app.cover.image_providers.bfl_transport import (
    LIVE_HTTP_ENABLED,
    NetworkSealed,
    SealedTransport,
    TransportRequest,
    TransportResponse,
    UrllibTransport,
)
from app.cover.image_providers.black_forest_labs import BlackForestLabsImageProvider
from app.cover.image_providers.budget_policy import (
    COST_RECONCILIATION_PENDING,
    DEFAULT_POLICY_MODE,
    EXPLICIT_DECISION,
    EXPERIMENTAL_SUBMISSION_ENABLED,
    POLICY_EXPERIMENTAL,
    POLICY_STRICT,
    STATUS_AUTHORIZED,
    STATUS_CANCELLED,
    STATUS_EXPIRED,
    STATUS_OUTCOME_UNKNOWN,
    STATUS_RESERVED,
    STATUS_SUBMITTED,
    STATUS_SUCCEEDED,
    apply_explicit_approval,
    cancel_authorization,
    documented_cost_components,
    experimental_block_reasons,
    first_experimental_image_plan,
    inactive_authorization_template,
    persist_authorization,
    policy_mode_of,
    record_submission_intent,
    reserve_experimental,
)
from app.cover.image_providers.openai_art import PROMPT, prompt_record
from app.cover.image_providers.openai_image import (
    GenerationOutcomeUnknown,
    OpenAIImageProvider,
    default_openai_authorization,
)
from app.cover.image_providers.openai_pricing import TokenBillingPricing
from app.cover.image_providers.openai_spec import (
    ENV_API_KEY,
    GENERATION_URL,
    OFFICIAL_MODEL_ID,
    SELECTED_HEIGHT,
    SELECTED_WIDTH,
    SNAPSHOT_MODEL_ID,
    published_image_output_estimate_usd,
)
from app.cover.image_providers.policy import PaidCallRefused
from app.cover.renderer.contract import CoverRenderNotAuthorized, CoverRenderer
from app.cover_budget_policy_4b2343.paths import planned_image_path
from app.cover_flux2_pro_4b234.constants import (
    EXPECTED_BOOK_SHA256,
    EXPECTED_INTERIOR_DOCX_SHA256,
    EXPECTED_INTERIOR_PDF_SHA256,
)
from app.cover_generator_foundation_4b233.hashes import snapshot
from app.cover_generator_foundation_4b233.paths import repo_root
from app.cover_gpt_image_2_4b2342.scenarios import evaluate_cases as evaluate_prior_cases

FIXTURE_KEY = "test-openai-key-not-real"
CELL = published_image_output_estimate_usd(SELECTED_WIDTH, SELECTED_HEIGHT, "medium")
_PNG_CACHE: dict[tuple[int, int], bytes] = {}


def evaluate_cases() -> dict[str, Any]:
    cases = []
    for name, function in CASES:
        try:
            detail = function() or "ok"
            cases.append({"name": name, "passed": True, "detail": detail})
        except Exception as exc:
            cases.append({"name": name, "passed": False, "detail": f"{type(exc).__name__}: {exc}"})
    failed = [item for item in cases if not item["passed"]]
    return {
        "passed": len(cases) - len(failed),
        "failed": len(failed),
        "failed_names": [item["name"] for item in failed],
        "cases": cases,
        "live_provider_calls": 0,
        "paid_cost_usd": 0,
    }


def case_strict_default() -> str:
    assert DEFAULT_POLICY_MODE == POLICY_STRICT
    assert EXPERIMENTAL_SUBMISSION_ENABLED is False
    assert policy_mode_of(None) == POLICY_STRICT
    assert policy_mode_of(default_openai_authorization()) == POLICY_STRICT
    assert policy_mode_of({}) == POLICY_STRICT
    template = inactive_authorization_template()
    assert template["explicit_user_approval"] is False
    assert template["accepts_unbounded_provider_cost"] is False
    assert template["status"] == "NOT_AUTHORIZED"
    assert template["effective"] is False
    plan = first_experimental_image_plan()
    assert plan["authorized"] is False
    assert plan["image_generated"] is False
    return "strict is the default and the plan is not a grant"


def case_strict_unknown_maximum() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([])
        auth = {
            "enabled": True,
            "explicit": True,
            "provider_id": "openai",
            "model_name": "gpt-image-2",
            "max_images": 1,
            "max_budget_usd": 1000,
            "max_total_cost_usd": 1000,
            "allow_paid_calls": True,
            "network_calls_allowed": True,
            "dry_run": False,
            "policy_mode": POLICY_STRICT,
            "accepts_unbounded_provider_cost": True,
            "explicit_decision": EXPLICIT_DECISION,
            "explicit_user_approval": True,
        }
        provider = _open(
            tmp,
            transport,
            auth=auth,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp)))
        assert "billing_ceiling_not_guaranteed" in refused.reasons
        assert "estimated_cost_unknown" in refused.reasons
        assert transport.calls == []
    return "strict still refuses an unknown ceiling"


def case_experimental_disabled() -> str:
    assert EXPERIMENTAL_SUBMISSION_ENABLED is False
    with TemporaryDirectory() as tmp:
        transport = _script([_image_response()])
        auth, ledger, destination = _grant(tmp)
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=False,
        )
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp, output_paths=[destination])))
        assert "experimental_mode_disabled" in refused.reasons
        assert transport.calls == []
        assert not Path(destination).exists()
    return "the submission switch stays off"


def case_without_approval() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([_image_response()])
        auth = inactive_authorization_template()
        auth["policy_mode"] = POLICY_EXPERIMENTAL
        provider = _open(
            tmp,
            transport,
            auth=auth,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp)))
        assert "explicit_user_approval_missing" in refused.reasons
        assert transport.calls == []
    return "mode selection is not consent"


def case_without_risk_acceptance() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([_image_response()])
        auth, _ledger, destination = _grant(tmp, skip_approval=True)
        auth["explicit_user_approval"] = True
        auth["accepts_unbounded_provider_cost"] = False
        auth["explicit_decision"] = None
        provider = _open(
            tmp,
            transport,
            auth=auth,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp, output_paths=[destination])))
        assert "billing_uncertainty_not_accepted" in refused.reasons
        assert transport.calls == []
    return "billing uncertainty must be accepted"


def case_different_provider() -> str:
    return _mismatch("provider_id", "black_forest_labs", "provider_mismatch")


def case_different_model() -> str:
    return _mismatch("model_name", "flux-2-pro", "model_mismatch")


def case_different_resolution() -> str:
    return _mismatch("width_px", 1536, "resolution_mismatch", height_px=2304)


def case_different_quality() -> str:
    return _mismatch("quality", "low", "quality_mismatch")


def case_different_format() -> str:
    return _mismatch("output_format", "jpeg", "output_format_mismatch")


def case_different_prompt() -> str:
    return _mismatch("prompt", PROMPT + " extra cloud", "prompt_sha256_mismatch")


def case_different_image_count() -> str:
    return _mismatch("image_count", 2, "image_count_mismatch")


def case_expired() -> str:
    approval_now = datetime(2026, 10, 4, tzinfo=timezone.utc)
    later = approval_now + timedelta(days=2)
    with TemporaryDirectory() as tmp:
        transport = _script([_image_response()])
        auth, ledger, destination = _grant(
            tmp,
            now=approval_now,
            expires_at=(approval_now + timedelta(hours=1)).isoformat(),
        )
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
            clock=lambda: later,
        )
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp, output_paths=[destination])))
        assert "authorization_expired" in refused.reasons
        stored = _auth_row(ledger, auth["authorization_id"])
        assert stored["status"] == STATUS_EXPIRED
        assert transport.calls == []
    return "expired grant cannot be submitted"


def case_cancelled() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([_image_response()])
        auth, ledger, destination = _grant(tmp)
        cancel_authorization(ReservationLedger(ledger), auth["authorization_id"])
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp, output_paths=[destination])))
        assert "authorization_cancelled" in refused.reasons
        assert _auth_row(ledger, auth["authorization_id"])["status"] == STATUS_CANCELLED
        assert transport.calls == []
    return "cancelled grant cannot be submitted"


def case_already_consumed() -> str:
    with TemporaryDirectory() as tmp:
        transport = _script([_image_response()])
        auth, ledger, destination = _grant(tmp)
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        saved = provider.generate(_ready(tmp, output_paths=[destination]))
        assert saved["generated"] is True
        again = _script([_image_response()])
        second = _open(
            tmp,
            again,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        refused = _must(PaidCallRefused, lambda: second.generate(_ready(tmp, output_paths=[destination])))
        assert "authorization_already_consumed" in refused.reasons
        assert _auth_row(ledger, auth["authorization_id"])["status"] == STATUS_SUCCEEDED
        assert again.calls == []
    return "a consumed grant cannot be reused"


def case_atomic_reservation() -> str:
    with TemporaryDirectory() as tmp:
        auth, ledger, destination = _grant(tmp)
        request = _ready(tmp, output_paths=[destination])
        store = ReservationLedger(ledger)
        first = reserve_experimental(store, auth, request)
        refused = _must(PaidCallRefused, lambda: reserve_experimental(store, auth, request))
        assert "authorization_already_reserved" in refused.reasons
        payload = json.loads(Path(ledger).read_text(encoding="utf-8"))
        assert len(payload["reservations"]) == 1
        assert payload["reservations"][0]["reservation_id"] == first["reservation_id"]
        assert payload["reservations"][0]["automatic_retry"] is False
        assert _auth_row(ledger, auth["authorization_id"])["status"] == STATUS_RESERVED
        assert not Path(destination).exists()
    return "one atomic reservation"


def case_concurrency() -> str:
    with TemporaryDirectory() as tmp:
        auth, ledger, destination = _grant(tmp)
        transport = _script([_image_response()])
        barrier = threading.Barrier(2)
        outcomes: list[Any] = []

        def worker() -> None:
            provider = _open(
                tmp,
                transport,
                auth=auth,
                ledger=ledger,
                pricing=TokenBillingPricing(),
                experimental_submission_enabled=True,
            )
            try:
                barrier.wait(timeout=5)
                outcomes.append(provider.generate(_ready(tmp, output_paths=[destination])))
            except Exception as exc:
                outcomes.append(exc)

        threads = [threading.Thread(target=worker) for _index in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        successes = [item for item in outcomes if isinstance(item, dict)]
        refusals = [item for item in outcomes if isinstance(item, PaidCallRefused)]
        assert len(successes) == 1, outcomes
        assert len(refusals) == 1, outcomes
        assert len(transport.calls) == 1
        assert _auth_row(ledger, auth["authorization_id"])["submission_count"] == 1
    return "two processes, one submission"


def case_interrupt_before_submission() -> str:
    with TemporaryDirectory() as tmp:
        auth, ledger, destination = _grant(tmp)
        reserve_experimental(ReservationLedger(ledger), auth, _ready(tmp, output_paths=[destination]))
        transport = _script([_image_response()])
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp, output_paths=[destination])))
        assert "authorization_already_reserved" in refused.reasons
        assert transport.calls == []
        assert _auth_row(ledger, auth["authorization_id"])["status"] == STATUS_RESERVED
        assert not Path(destination).exists()
    return "a reserved grant is not submitted again"


def case_interrupt_during_submission() -> str:
    with TemporaryDirectory() as tmp:
        auth, ledger, destination = _grant(tmp)
        reserve_experimental(ReservationLedger(ledger), auth, _ready(tmp, output_paths=[destination]))
        record_submission_intent(ReservationLedger(ledger), auth["authorization_id"])
        transport = _script([_image_response()])
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp, output_paths=[destination])))
        assert "authorization_already_submitted" in refused.reasons
        assert transport.calls == []
        row = _auth_row(ledger, auth["authorization_id"])
        assert row["status"] == STATUS_SUBMITTED
        assert row["submission_count"] == 1
    return "a started submission is not repeated"


def case_timeout() -> str:
    with TemporaryDirectory() as tmp:
        auth, ledger, destination = _grant(tmp)
        transport = _script([TimeoutError("timed out"), _image_response()])
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        unknown = _must(
            GenerationOutcomeUnknown,
            lambda: provider.generate(_ready(tmp, output_paths=[destination])),
        )
        assert unknown.status == "timeout"
        assert len(transport.calls) == 1
        row = _auth_row(ledger, auth["authorization_id"])
        assert row["status"] == STATUS_OUTCOME_UNKNOWN
        assert row["observed_cost_usd"] is None
        assert row["automatic_retry"] is False
        assert not Path(destination).exists()
    return "timeout becomes OUTCOME_UNKNOWN"


def case_ambiguous() -> str:
    with TemporaryDirectory() as tmp:
        auth, ledger, destination = _grant(tmp)
        transport = _script([_json_response({"data": [], "usage": {"total_tokens": 10}})])
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        unknown = _must(
            GenerationOutcomeUnknown,
            lambda: provider.generate(_ready(tmp, output_paths=[destination])),
        )
        assert unknown.status == "ambiguous_image_response"
        row = _auth_row(ledger, auth["authorization_id"])
        assert row["status"] == STATUS_OUTCOME_UNKNOWN
        assert row["observed_cost_usd"] is None
        assert row["cost_reconciliation_status"] == COST_RECONCILIATION_PENDING
        assert row["reconciliation"]["body_retained"] is False
        assert "data" in row["reconciliation"]["response_keys"]
        assert FIXTURE_KEY not in Path(ledger).read_text(encoding="utf-8")
        assert len(transport.calls) == 1
    return "ambiguous response kept for manual reconciliation"


def case_no_retry() -> str:
    with TemporaryDirectory() as tmp:
        auth, ledger, destination = _grant(tmp)
        transport = _script([TimeoutError("timed out"), _image_response()])
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        _must(GenerationOutcomeUnknown, lambda: provider.generate(_ready(tmp, output_paths=[destination])))
        refused = _must(
            PaidCallRefused,
            lambda: provider.generate(_ready(tmp, output_paths=[destination])),
        )
        assert "authorization_outcome_unknown" in refused.reasons
        assert len(transport.calls) == 1
        assert provider.ledger.summary()["reservations"][0]["retry_count"] == 0
        assert provider.ledger.summary()["reservations"][0]["automatic_retry"] is False
    return "no second paid attempt"


def case_no_fallback() -> str:
    with TemporaryDirectory() as tmp:
        auth, ledger, destination = _grant(tmp)
        transport = _script([TimeoutError("timed out"), _image_response()])
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        _must(GenerationOutcomeUnknown, lambda: provider.generate(_ready(tmp, output_paths=[destination])))
        assert len(transport.calls) == 1
        assert transport.calls[0].url == GENERATION_URL
        bfl_transport = _script([_image_response()])
        bfl = BlackForestLabsImageProvider(
            transport=bfl_transport,
            authorization=auth,
            ledger_path=Path(tmp) / "bfl-ledger.json",
            env={ENV_API_KEY: FIXTURE_KEY},
            dry_run=False,
            phase_lock=False,
            allow_mock_submission=True,
        )
        refused = _must(PaidCallRefused, lambda: bfl.generate(_ready(tmp, output_paths=[destination])))
        assert "experimental_submission_not_available_for_this_adapter" in refused.reasons
        assert bfl_transport.calls == []
    return "no automatic fallback"


def case_api_key_missing() -> str:
    with TemporaryDirectory() as tmp:
        auth, ledger, destination = _grant(tmp)
        transport = _script([_image_response()])
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            env={},
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp, output_paths=[destination])))
        assert "api_key_missing" in refused.reasons
        assert transport.calls == []
    return "a missing key still blocks"


def case_dry_run() -> str:
    with TemporaryDirectory() as tmp:
        auth, ledger, destination = _grant(tmp)
        transport = _script([_image_response()])
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            dry_run=True,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp, output_paths=[destination])))
        assert "dry_run" in refused.reasons
        assert transport.calls == []
    return "dry-run still blocks"


def case_estimate_missing() -> str:
    with TemporaryDirectory() as tmp:
        auth, ledger, destination = _grant(tmp)
        _tamper(ledger, auth, documented_image_output_estimate_usd=None)
        transport = _script([_image_response()])
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp, output_paths=[destination])))
        assert "documented_estimate_missing" in refused.reasons
        assert transport.calls == []
    return "a documented estimate is required"


def case_planning_budget_missing() -> str:
    with TemporaryDirectory() as tmp:
        auth, ledger, destination = _grant(tmp)
        _tamper(ledger, auth, planning_budget_usd=None, max_budget_usd=None)
        transport = _script([_image_response()])
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp, output_paths=[destination])))
        assert "planning_budget_missing" in refused.reasons
        assert transport.calls == []
    return "a planning budget is required"


def case_unbounded_cost_accepted() -> str:
    with TemporaryDirectory() as tmp:
        auth, ledger, destination = _grant(tmp)
        assert auth["accepts_unbounded_provider_cost"] is True
        assert auth["verified_maximum_cost_usd"] is None
        assert auth["estimated_cost_usd"] is None
        assert auth["documented_image_output_estimate_usd"] == CELL == "0.041"
        transport = _script([_image_response()])
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        estimate = provider.estimate_cost(_ready(tmp, output_paths=[destination]))
        assert estimate["verified_maximum_cost_usd"] is None
        assert estimate["estimated_cost_usd"] is None
        assert estimate["published_image_output_estimate_usd"] == "0.041"
        saved = provider.generate(_ready(tmp, output_paths=[destination]))
        assert saved["generated"] is True
        assert saved["verified_maximum_cost_usd"] is None
        assert saved["estimated_cost_usd"] is None
        assert saved["documented_image_output_estimate_usd"] == "0.041"
        assert len(transport.calls) == 1
        row = _auth_row(ledger, auth["authorization_id"])
        assert row["verified_maximum_cost_usd"] is None
        assert row["status"] == STATUS_SUCCEEDED
    return "unknown ceiling accepted once, 0.041 is not a maximum"


def case_observed_cost_absent() -> str:
    with TemporaryDirectory() as tmp:
        auth, ledger, destination = _grant(tmp)
        transport = _script([_image_response()])
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        saved = provider.generate(_ready(tmp, output_paths=[destination]))
        assert saved["observed_cost_usd"] is None
        assert _auth_row(ledger, auth["authorization_id"])["observed_cost_usd"] is None
    return "no invented observed cost"


def case_reconciliation_pending() -> str:
    with TemporaryDirectory() as tmp:
        auth, ledger, destination = _grant(tmp)
        transport = _script([_image_response()])
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        saved = provider.generate(_ready(tmp, output_paths=[destination]))
        assert saved["cost_reconciliation_status"] == COST_RECONCILIATION_PENDING
        row = _auth_row(ledger, auth["authorization_id"])
        assert row["cost_reconciliation_status"] == COST_RECONCILIATION_PENDING
        assert row["estimated_cost_usd"] is None
    return "reconciliation stays pending"


def case_no_key_leak() -> str:
    with TemporaryDirectory() as tmp:
        auth, ledger, destination = _grant(tmp)
        transport = _script([_image_response()])
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        saved = provider.generate(_ready(tmp, output_paths=[destination]))
        blob = "\n".join(
            [
                Path(ledger).read_text(encoding="utf-8"),
                json.dumps(saved),
                json.dumps(provider.check_availability()),
                json.dumps(provider.estimate_cost(_ready(tmp, output_paths=[destination]))),
                json.dumps(auth),
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
    assert issubclass(OpenAIImageProvider, CoverImageProvider)
    assert issubclass(BlackForestLabsImageProvider, CoverImageProvider)
    source = Path(__file__).resolve().parents[1] / "cover" / "image_providers" / "budget_policy.py"
    text = source.read_text(encoding="utf-8")
    assert "urlopen" not in text
    assert "import urllib" not in text
    sealed = UrllibTransport()
    _must(NetworkSealed, lambda: sealed.exchange(TransportRequest("POST", GENERATION_URL, {}, b"{}")))
    with TemporaryDirectory() as tmp:
        transport = SealedTransport()
        provider = OpenAIImageProvider(transport=transport, ledger_path=Path(tmp) / "ledger.json", env={})
        _must(PaidCallRefused, lambda: provider.generate(_ready(tmp)))
        assert transport.calls == []
    return "live http sealed"


def case_no_image() -> str:
    planned = repo_root() / planned_image_path()
    assert not planned.exists()
    assert prompt_record()["image_generated"] is False
    assert prompt_record()["prompt"] == PROMPT
    assert first_experimental_image_plan()["image_generated"] is False
    components = documented_cost_components()
    assert components["image_output_usd"] == "0.041"
    assert components["estimated_cost_usd"] is None
    assert "text_input_tokens" in components["unknown_components"]
    return "no cover image written"


def case_no_cover_files() -> str:
    with TemporaryDirectory() as tmp:
        docx = Path(tmp) / "front_cover.docx"
        pdf = Path(tmp) / "front_cover.pdf"
        _must(CoverRenderNotAuthorized, lambda: CoverRenderer().render_front_docx({}, docx))
        _must(CoverRenderNotAuthorized, lambda: CoverRenderer().render_front_pdf({}, pdf))
        assert not docx.exists() and not pdf.exists()
    content = initial_content()
    assert content["author_biography_status"] == "MISSING_OPTIONAL"
    assert content["book_description_status"] == "NOT_STARTED"
    return "no cover docx or pdf"


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


def case_block_reasons_are_specific() -> str:
    """Keep the matrix honest: a prepared grant with a mismatched request is the lock under test."""

    auth, _ledger, destination = _grant_in_memory()
    request = _ready_for(destination, model_name="flux-2-pro")
    reasons = experimental_block_reasons(authorization=auth, request=request, persisted=auth)
    assert "model_mismatch" in reasons
    assert "authorization_not_persisted" not in reasons
    return "parameter locks are explicit"


CASES = [
    ("01_strict_default", case_strict_default),
    ("02_strict_unknown_maximum", case_strict_unknown_maximum),
    ("03_experimental_disabled", case_experimental_disabled),
    ("04_experimental_without_approval", case_without_approval),
    ("05_experimental_without_risk_acceptance", case_without_risk_acceptance),
    ("06_different_provider", case_different_provider),
    ("07_different_model", case_different_model),
    ("08_different_resolution", case_different_resolution),
    ("09_different_quality", case_different_quality),
    ("10_different_format", case_different_format),
    ("11_different_prompt_hash", case_different_prompt),
    ("12_different_image_count", case_different_image_count),
    ("13_authorization_expired", case_expired),
    ("14_authorization_cancelled", case_cancelled),
    ("15_authorization_consumed", case_already_consumed),
    ("16_atomic_reservation", case_atomic_reservation),
    ("17_concurrent_processes", case_concurrency),
    ("18_interrupt_before_submission", case_interrupt_before_submission),
    ("19_interrupt_during_submission", case_interrupt_during_submission),
    ("20_timeout", case_timeout),
    ("21_ambiguous_response", case_ambiguous),
    ("22_no_automatic_retry", case_no_retry),
    ("23_no_automatic_fallback", case_no_fallback),
    ("24_api_key_missing", case_api_key_missing),
    ("25_dry_run", case_dry_run),
    ("26_estimate_missing", case_estimate_missing),
    ("27_planning_budget_missing", case_planning_budget_missing),
    ("28_unbounded_cost_explicitly_accepted", case_unbounded_cost_accepted),
    ("29_observed_cost_absent", case_observed_cost_absent),
    ("30_reconciliation_pending", case_reconciliation_pending),
    ("31_no_key_leak", case_no_key_leak),
    ("32_no_real_provider_call", case_no_real_call),
    ("33_no_image_generated", case_no_image),
    ("34_no_cover_docx_pdf", case_no_cover_files),
    ("35_canonical_unchanged", case_canonical_unchanged),
    ("36_interior_unchanged", case_interior_unchanged),
    ("37_previous_tests_no_regression", case_previous_tests),
    ("38_parameter_locks", case_block_reasons_are_specific),
]
CASE_NAMES = [name for name, _function in CASES]


def _mismatch(field: str, value: Any, reason: str, **extra: Any) -> str:
    with TemporaryDirectory() as tmp:
        auth, ledger, destination = _grant(tmp)
        transport = _script([_image_response()])
        provider = _open(
            tmp,
            transport,
            auth=auth,
            ledger=ledger,
            pricing=TokenBillingPricing(),
            experimental_submission_enabled=True,
        )
        overrides: dict[str, Any] = {"output_paths": [destination]}
        if field == "quality":
            overrides["metadata_quality"] = value
        elif field == "output_format":
            overrides["metadata_format"] = value
        elif field == "width_px":
            overrides["width_px"] = value
            overrides.update(extra)
        else:
            overrides[field] = value
        refused = _must(PaidCallRefused, lambda: provider.generate(_ready(tmp, **overrides)))
        assert reason in refused.reasons, refused.reasons
        assert transport.calls == []
        assert _auth_row(ledger, auth["authorization_id"])["status"] == STATUS_AUTHORIZED
    return reason


def _grant(tmp: str, *, skip_approval: bool = False, now: datetime | None = None, **overrides: Any) -> tuple[dict[str, Any], Path, str]:
    destination = str(Path(tmp) / "door.png")
    ledger = Path(tmp) / "ledger.json"
    auth = _prepared(destination, **overrides)
    if skip_approval:
        return auth, ledger, destination
    approved = apply_explicit_approval(
        auth,
        decision=EXPLICIT_DECISION,
        disable_dry_run=True,
        now=now,
    )
    persist_authorization(ReservationLedger(ledger), approved, allow_effective=True)
    return approved, ledger, destination


def _grant_in_memory() -> tuple[dict[str, Any], Path, str]:
    destination = "audit/cover_generator_budget_policy_4b2343/planned_first_image/door_already_open.png"
    auth = apply_explicit_approval(
        _prepared(destination, scope="TEST_ONLY_EXPERIMENTAL_MECHANISM"),
        decision=EXPLICIT_DECISION,
        disable_dry_run=True,
    )
    return auth, Path("unused"), destination


def _prepared(destination: str, **overrides: Any) -> dict[str, Any]:
    auth = inactive_authorization_template()
    auth.update(
        {
            "authorization_id": "test-auth",
            "scope": "TEST_ONLY_EXPERIMENTAL_MECHANISM",
            "planning_budget_usd": "5.00",
            "max_budget_usd": "5.00",
            "max_total_cost_usd": "5.00",
            "destination": destination,
            "expires_at": "2099-01-01T00:00:00+00:00",
            "status": "NOT_AUTHORIZED",
            "effective": False,
            "explicit_user_approval": False,
            "accepts_unbounded_provider_cost": False,
            "explicit_decision": None,
            "documented_image_output_estimate_usd": CELL,
            "prompt_sha256": prompt_record()["prompt_sha256"],
        }
    )
    auth.update(overrides)
    return auth


def _tamper(ledger: Path, auth: dict[str, Any], **fields: Any) -> None:
    auth.update(fields)

    def mutate(state: dict[str, Any]) -> dict[str, Any]:
        for row in state["authorizations"]:
            if row.get("authorization_id") == auth.get("authorization_id"):
                row.update(fields)
        return {"write": True, "result": True}

    ReservationLedger(ledger).mutate(mutate)


def _auth_row(ledger: Path, authorization_id: str) -> dict[str, Any]:
    payload = json.loads(Path(ledger).read_text(encoding="utf-8"))
    for row in payload["authorizations"]:
        if row["authorization_id"] == authorization_id:
            return row
    raise AssertionError("authorization row missing")


def _ready(tmp: str, **overrides: Any) -> ImageGenerationRequest:
    quality = overrides.pop("metadata_quality", "medium")
    output_format = overrides.pop("metadata_format", "png")
    if "output_paths" not in overrides:
        overrides["output_paths"] = [str(Path(tmp) / "door.png")]
    metadata = {"quality": quality, "output_format": output_format, "background": "opaque"}
    values: dict[str, Any] = {
        "provider_id": "openai",
        "model_name": OFFICIAL_MODEL_ID,
        "model_version": SNAPSHOT_MODEL_ID,
        "prompt": PROMPT,
        "negative_prompt": None,
        "width_px": SELECTED_WIDTH,
        "height_px": SELECTED_HEIGHT,
        "aspect_ratio": "2:3",
        "seed": None,
        "image_count": 1,
        "output_paths": overrides.pop("output_paths"),
        "metadata": metadata,
        "embed_text": False,
        "estimated_cost_usd": None,
    }
    values.update(overrides)
    return ImageGenerationRequest(**values)


def _ready_for(destination: str, **overrides: Any) -> ImageGenerationRequest:
    return _ready("unused", output_paths=[destination], **overrides)


def _open(tmp: str, transport: Any, **overrides: Any) -> OpenAIImageProvider:
    ledger = overrides.pop("ledger", Path(tmp) / "ledger.json")
    auth = overrides.pop("auth")
    env = overrides.pop("env", {ENV_API_KEY: FIXTURE_KEY})
    return OpenAIImageProvider(
        transport=transport,
        authorization=auth,
        ledger_path=ledger,
        env=env,
        dry_run=overrides.pop("dry_run", False),
        pricing=overrides.pop("pricing", TokenBillingPricing()),
        phase_lock=False,
        allow_mock_submission=True,
        experimental_submission_enabled=overrides.pop("experimental_submission_enabled", False),
        clock=overrides.pop("clock", None),
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
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 1))
        + chunk(b"IEND", b"")
    )
    _PNG_CACHE[(width, height)] = payload
    return payload


def _must(exc_type: type[BaseException], function: Callable[[], Any]) -> Any:
    try:
        function()
    except exc_type as exc:
        return exc
    raise AssertionError(f"{exc_type.__name__} was not raised")


__all__ = ["CASE_NAMES", "evaluate_cases"]
