"""Sealed FLUX.2 [pro] adapter.

The default instance refuses every paid call. A mock transport can be
injected in tests. The live urllib client stays behind LIVE_HTTP_ENABLED.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from app.cover.constants import PAID_CALLS_AUTHORIZED
from app.cover.image_providers.base import (
    CoverImageProvider,
    ImageGenerationRequest,
    ProviderCapabilities,
    validate_image_request,
)
from app.cover.image_providers.bfl_budget import (
    ReservationLedger,
    collect_block_reasons,
    default_authorization,
)
from app.cover.image_providers.bfl_download import DownloadRejected, download_delivery_image
from app.cover.image_providers.bfl_pricing import UnverifiedFluxPricing, credits_to_usd
from app.cover.image_providers.bfl_spec import (
    ENV_API_KEY,
    OFFICIAL_MODEL_ID,
    PROVIDER_ID,
    REQUESTED_OUTPUT_FORMAT,
    SUBMIT_URL,
    SpecError,
    dimension_problem,
    submission_body,
    validate_polling_url,
)
from app.cover.image_providers.bfl_transport import (
    LIVE_HTTP_ENABLED,
    NetworkSealed,
    SealedTransport,
    TransportRequest,
)
from app.cover.image_providers.policy import PaidCallRefused


class GenerationOutcomeUnknown(RuntimeError):
    """The provider outcome is not known. The reservation is not retried."""

    def __init__(self, status: str) -> None:
        self.status = status
        super().__init__(status)


class GenerationFailed(RuntimeError):
    def __init__(self, status: str) -> None:
        self.status = status
        super().__init__(status)


class BlackForestLabsImageProvider(CoverImageProvider):
    provider_id = PROVIDER_ID

    def __init__(
        self,
        *,
        transport: Any | None = None,
        authorization: dict[str, Any] | None = None,
        authorization_missing: bool = False,
        ledger_path: Path | None = None,
        env: Mapping[str, str] | None = None,
        dry_run: bool = True,
        pricing: Any | None = None,
        phase_lock: bool = True,
        allow_mock_submission: bool = False,
    ) -> None:
        self.transport = transport if transport is not None else SealedTransport()
        if authorization_missing:
            self.authorization = None
        elif authorization is None:
            self.authorization = default_authorization()
        else:
            self.authorization = dict(authorization)
        self.ledger = ReservationLedger(Path(ledger_path or _default_ledger_path()))
        self._env = env if env is not None else os.environ
        self.dry_run = dry_run
        self.pricing = pricing if pricing is not None else UnverifiedFluxPricing()
        self.phase_lock = phase_lock
        self.allow_mock_submission = allow_mock_submission
        self._sample_urls: dict[str, str] = {}

    def check_availability(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": OFFICIAL_MODEL_ID,
            "endpoint": SUBMIT_URL,
            "key_present": self._api_key() is not None,
            "network_checked": False,
            "live_http_enabled": LIVE_HTTP_ENABLED,
            "paid_calls_authorized": PAID_CALLS_AUTHORIZED,
            "dry_run": self.dry_run,
            "reachable": "NOT_CONTACTED",
        }

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            model_name=OFFICIAL_MODEL_ID,
            model_version="pinned-snapshot",
            negative_prompt=False,
            seed=True,
            portrait_ratio=True,
            text_free_generation=True,
            local_execution=False,
            paid=True,
            max_images=1,
        )

    def estimate_cost(self, request: ImageGenerationRequest) -> dict[str, Any]:
        estimate = dict(self.pricing.estimate(request))
        estimate["actual_cost_usd"] = None
        return estimate

    def generate(self, request: ImageGenerationRequest) -> dict[str, Any]:
        validate_image_request(request)
        estimate = self.estimate_cost(request)
        reasons = self._reasons(request, estimate.get("estimated_cost_usd"))
        problem = dimension_problem(request.width_px, request.height_px)
        if problem:
            reasons.append("dimensions_not_accepted_by_api")
        if request.model_name != OFFICIAL_MODEL_ID:
            reasons.append("model_not_authorized")
        if _experimental_mode(self.authorization):
            reasons.append("experimental_submission_not_available_for_this_adapter")
        if reasons:
            raise PaidCallRefused(list(dict.fromkeys(reasons)))
        if estimate.get("estimated_cost_usd") is None:
            raise PaidCallRefused(["estimated_cost_unknown"])
        reservation = self.ledger.reserve(
            estimate_usd=float(estimate["estimated_cost_usd"]),
            image_count=1,
            max_images=int(self.authorization.get("max_images") or 0),
            max_budget_usd=float(
                self.authorization.get("max_budget_usd", self.authorization.get("max_total_cost_usd")) or 0
            ),
        )
        try:
            body = submission_body(request)
            response = self._exchange(
                "POST",
                SUBMIT_URL,
                body,
            )
        except TimeoutError as exc:
            self.ledger.mark(reservation["reservation_id"], "outcome_unknown")
            raise GenerationOutcomeUnknown("timeout") from exc
        except NetworkSealed:
            self.ledger.mark(reservation["reservation_id"], "outcome_unknown")
            raise
        payload, status = _decode_http(response)
        if status != 200 or not isinstance(payload, dict):
            self.ledger.mark(reservation["reservation_id"], "outcome_unknown", http_status=status)
            raise GenerationOutcomeUnknown(f"http_{status}")
        task_id = payload.get("id")
        polling_url = payload.get("polling_url")
        if not isinstance(task_id, str) or not task_id or not isinstance(polling_url, str):
            self.ledger.mark(reservation["reservation_id"], "outcome_unknown")
            raise GenerationOutcomeUnknown("ambiguous_submit_response")
        try:
            validate_polling_url(polling_url)
        except SpecError as exc:
            self.ledger.mark(reservation["reservation_id"], "outcome_unknown", task_id=task_id)
            raise GenerationOutcomeUnknown("polling_url_rejected") from exc
        observed = credits_to_usd(payload.get("cost")) if "cost" in payload else None
        self.ledger.mark(
            reservation["reservation_id"],
            "submitted",
            task_id=task_id,
            polling_url=polling_url,
            observed_cost_usd=observed,
        )
        return _public_result(
            status="submitted",
            reservation_id=reservation["reservation_id"],
            task_id=task_id,
            estimated_cost_usd=estimate.get("estimated_cost_usd"),
            actual_cost_usd=observed,
            generated=False,
            output_paths=[],
        )

    def poll(self, reservation_id: str) -> dict[str, Any]:
        record = self._record(reservation_id)
        if record.get("status") not in {"submitted", "pending"}:
            raise GenerationOutcomeUnknown("poll_requires_a_submitted_task")
        polling_url = str(record.get("polling_url") or "")
        try:
            validate_polling_url(polling_url)
        except SpecError as exc:
            self.ledger.mark(reservation_id, "outcome_unknown")
            raise GenerationOutcomeUnknown("polling_url_rejected") from exc
        try:
            response = self._exchange("GET", polling_url, None)
        except TimeoutError as exc:
            self.ledger.mark(reservation_id, "outcome_unknown")
            raise GenerationOutcomeUnknown("timeout") from exc
        payload, status = _decode_http(response)
        if status != 200 or not isinstance(payload, dict) or not isinstance(payload.get("status"), str):
            self.ledger.mark(reservation_id, "outcome_unknown")
            raise GenerationOutcomeUnknown("ambiguous_poll_response")
        provider_status = payload["status"]
        if provider_status in {"Pending", "Reasoning", "Generating"}:
            self.ledger.mark(reservation_id, "pending")
            return _public_result(status="pending", reservation_id=reservation_id, task_id=record.get("task_id"))
        if provider_status == "Ready":
            sample = ((payload.get("result") or {}) if isinstance(payload.get("result"), dict) else {}).get("sample")
            if not isinstance(sample, str):
                self.ledger.mark(reservation_id, "outcome_unknown")
                raise GenerationOutcomeUnknown("ambiguous_ready_response")
            self._sample_urls[reservation_id] = sample
            self.ledger.mark(reservation_id, "ready")
            return _public_result(
                status="ready",
                reservation_id=reservation_id,
                task_id=record.get("task_id"),
                generated=False,
            )
        if provider_status in {"Error", "Failed", "Request Moderated", "Content Moderated", "Task not found"}:
            self.ledger.mark(reservation_id, "failed", provider_status=provider_status)
            raise GenerationFailed(provider_status)
        self.ledger.mark(reservation_id, "outcome_unknown", provider_status=provider_status)
        raise GenerationOutcomeUnknown("ambiguous_provider_status")

    def download(self, reservation_id: str, destination: Path, request: ImageGenerationRequest) -> dict[str, Any]:
        record = self._record(reservation_id)
        if record.get("status") != "ready":
            raise GenerationOutcomeUnknown("download_requires_ready")
        sample = self._sample_urls.get(reservation_id)
        if not sample:
            self.ledger.mark(reservation_id, "result_expired_requires_human")
            raise DownloadRejected("result_expired_requires_human")
        provenance = {
            "provider_id": PROVIDER_ID,
            "model_id": OFFICIAL_MODEL_ID,
            "task_id": record.get("task_id"),
            "prompt_sha256": hashlib.sha256(request.prompt.encode("utf-8")).hexdigest(),
            "output_format": REQUESTED_OUTPUT_FORMAT,
        }
        try:
            stored = download_delivery_image(
                transport=self.transport,
                url=sample,
                destination=destination,
                provenance=provenance,
            )
        except DownloadRejected as exc:
            if exc.reason == "result_expired_requires_human":
                self.ledger.mark(reservation_id, "result_expired_requires_human")
            raise
        self.ledger.mark(reservation_id, "downloaded", sha256=stored["sha256"])
        return _public_result(
            status="downloaded",
            reservation_id=reservation_id,
            task_id=record.get("task_id"),
            estimated_cost_usd=None,
            actual_cost_usd=record.get("observed_cost_usd"),
            generated=True,
            output_paths=[stored["path"]],
            sha256=stored["sha256"],
            metadata=stored["metadata"],
        )

    def _reasons(self, request: ImageGenerationRequest, estimate_usd: float | None) -> list[str]:
        return collect_block_reasons(
            authorization=self.authorization,
            request={
                "provider_id": request.provider_id,
                "model_name": request.model_name,
                "image_count": request.image_count,
            },
            estimate_usd=estimate_usd,
            api_key_present=self._api_key() is not None,
            dry_run=self.dry_run,
            honor_global_paid_lock=self.phase_lock,
            allow_mock_submission=self.allow_mock_submission,
            ledger_summary=self.ledger.summary(),
        )

    def _api_key(self) -> str | None:
        raw = self._env.get(ENV_API_KEY)
        if raw is None or not str(raw).strip():
            return None
        return str(raw).strip()

    def _exchange(self, method: str, url: str, body: dict[str, Any] | None) -> Any:
        key = self._api_key()
        headers = {"accept": "application/json", "Content-Type": "application/json"}
        if key is not None:
            headers["x-key"] = key
        encoded = None if body is None else json.dumps(body).encode("utf-8")
        return self.transport.exchange(
            TransportRequest(method=method, url=url, headers=headers, body=encoded)
        )

    def _record(self, reservation_id: str) -> dict[str, Any]:
        for record in self.ledger.summary()["reservations"]:
            if record.get("reservation_id") == reservation_id:
                return record
        raise GenerationOutcomeUnknown("reservation_missing")


def _experimental_mode(authorization: dict[str, Any] | None) -> bool:
    from app.cover.image_providers.budget_policy import POLICY_EXPERIMENTAL, policy_mode_of

    return policy_mode_of(authorization) == POLICY_EXPERIMENTAL


def _default_ledger_path() -> Path:
    return Path.cwd() / ".cover_bfl_ledger" / "reservations.json"


def _decode_http(response: Any) -> tuple[Any, int]:
    status = int(getattr(response, "status", 0) or 0)
    raw = getattr(response, "body", b"") or b""
    if not raw:
        return None, status
    try:
        return json.loads(raw.decode("utf-8")), status
    except (UnicodeError, json.JSONDecodeError):
        return None, status


def _public_result(**fields: Any) -> dict[str, Any]:
    result = {
        "provider_id": PROVIDER_ID,
        "model_name": OFFICIAL_MODEL_ID,
        "model_version": "pinned-snapshot",
        "negative_prompt_transmitted": False,
        "output_paths": [],
        "metadata": {},
        "license": "see_commercial_use_verification",
        "estimated_cost_usd": None,
        "actual_cost_usd": None,
        "error": None,
        "history": [],
        "generated": False,
        "task_id": None,
        "reservation_id": None,
        "status": None,
        "sha256": None,
    }
    result.update(fields)
    result.pop("api_key", None)
    return result


__all__ = [
    "BlackForestLabsImageProvider",
    "GenerationFailed",
    "GenerationOutcomeUnknown",
]
