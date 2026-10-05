"""Sealed gpt-image-2 adapter.

The default instance refuses every paid call. A mock transport can be
injected in tests. This module does not open a socket.
"""

from __future__ import annotations

import base64
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
from app.cover.image_providers.bfl_budget import ReservationLedger, usd_to_cents
from app.cover.image_providers.bfl_download import DownloadRejected, decode_image
from app.cover.image_providers.bfl_transport import (
    LIVE_HTTP_ENABLED,
    NetworkSealed,
    SealedTransport,
    TransportRequest,
)
from app.cover.image_providers.openai_pricing import TokenBillingPricing
from app.cover.image_providers.openai_spec import (
    ENV_API_KEY,
    GENERATION_URL,
    MAX_IMAGE_BYTES,
    OFFICIAL_MODEL_ID,
    PROVIDER_ID,
    SNAPSHOT_MODEL_ID,
    SpecError,
    request_problems,
    submission_body,
)
from app.cover.image_providers.budget_policy import (
    COST_RECONCILIATION_PENDING,
    POLICY_EXPERIMENTAL,
    STATUS_FAILED,
    STATUS_OUTCOME_UNKNOWN,
    STATUS_SUCCEEDED,
    clock_or_default,
    finalize_policy_reasons,
    finish_authorization,
    observe_provider_cost,
    policy_mode_of,
    record_submission_intent,
    refresh_experimental_status,
    reserve_experimental,
)
from app.cover.image_providers.policy import PaidCallRefused, evaluate_paid_call


class GenerationOutcomeUnknown(RuntimeError):
    """The provider outcome is not known. The reservation is not retried."""

    def __init__(self, status: str) -> None:
        self.status = status
        super().__init__(status)


class GenerationFailed(RuntimeError):
    def __init__(self, status: str) -> None:
        self.status = status
        super().__init__(status)


class OpenAIImageProvider(CoverImageProvider):
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
        experimental_submission_enabled: bool = False,
        clock: Any | None = None,
    ) -> None:
        self.transport = transport if transport is not None else SealedTransport()
        if authorization_missing:
            self.authorization = None
        elif authorization is None:
            self.authorization = default_openai_authorization()
        else:
            self.authorization = dict(authorization)
        self.ledger = ReservationLedger(Path(ledger_path or _default_ledger_path()))
        self._env = env if env is not None else os.environ
        self.dry_run = dry_run
        self.pricing = pricing if pricing is not None else TokenBillingPricing()
        self.phase_lock = phase_lock
        self.allow_mock_submission = allow_mock_submission
        self.experimental_submission_enabled = experimental_submission_enabled
        self.clock = clock

    def check_availability(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": OFFICIAL_MODEL_ID,
            "snapshot_model_id": SNAPSHOT_MODEL_ID,
            "snapshot_selected": False,
            "endpoint": GENERATION_URL,
            "key_present": self._api_key() is not None,
            "key_value_recorded": False,
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
            model_version=SNAPSHOT_MODEL_ID,
            negative_prompt=False,
            seed=False,
            portrait_ratio=True,
            text_free_generation=True,
            local_execution=False,
            paid=True,
            max_images=1,
        )

    def estimate_cost(self, request: ImageGenerationRequest) -> dict[str, Any]:
        estimate = dict(self.pricing.estimate(request))
        estimate["actual_cost_usd"] = None
        estimate.pop("api_key", None)
        return estimate

    def generate(self, request: ImageGenerationRequest) -> dict[str, Any]:
        validate_image_request(request)
        estimate = self.estimate_cost(request)
        reasons = self._reasons(request, estimate)
        if reasons:
            raise PaidCallRefused(list(dict.fromkeys(reasons)))
        if policy_mode_of(self.authorization) == POLICY_EXPERIMENTAL:
            return self._generate_experimental(request, estimate)
        reservation = self.ledger.reserve(
            estimate_usd=float(estimate["verified_maximum_cost_usd"]),
            image_count=1,
            max_images=int(self.authorization.get("max_images") or 0),
            max_budget_usd=float(
                self.authorization.get("max_budget_usd", self.authorization.get("max_total_cost_usd")) or 0
            ),
        )
        try:
            body = submission_body(request)
            response = self._exchange(body)
        except TimeoutError as exc:
            self.ledger.mark(reservation["reservation_id"], "outcome_unknown")
            raise GenerationOutcomeUnknown("timeout") from exc
        except NetworkSealed:
            self.ledger.mark(reservation["reservation_id"], "outcome_unknown")
            raise
        except SpecError as exc:
            self.ledger.mark(reservation["reservation_id"], "outcome_unknown")
            raise GenerationOutcomeUnknown("request_rejected_before_body") from exc
        return self._accept(reservation["reservation_id"], request, estimate, response)

    def _accept(
        self,
        reservation_id: str,
        request: ImageGenerationRequest,
        estimate: dict[str, Any],
        response: Any,
    ) -> dict[str, Any]:
        payload, status = _decode_http(response)
        if status != 200 or not isinstance(payload, dict):
            self.ledger.mark(reservation_id, "outcome_unknown", http_status=status)
            raise GenerationOutcomeUnknown(f"http_{status}")
        images = payload.get("data")
        if not isinstance(images, list) or len(images) != 1 or not isinstance(images[0], dict):
            self.ledger.mark(reservation_id, "outcome_unknown")
            raise GenerationOutcomeUnknown("ambiguous_image_response")
        encoded = images[0].get("b64_json")
        if not isinstance(encoded, str) or not encoded.strip():
            self.ledger.mark(reservation_id, "outcome_unknown")
            raise GenerationOutcomeUnknown("b64_json_missing")
        if images[0].get("url"):
            self.ledger.mark(reservation_id, "outcome_unknown")
            raise GenerationOutcomeUnknown("remote_url_refused")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            self.ledger.mark(reservation_id, "outcome_unknown")
            raise GenerationOutcomeUnknown("b64_json_invalid") from exc
        try:
            destination = _destination(request)
        except GenerationFailed:
            self.ledger.mark(reservation_id, "outcome_unknown")
            raise
        try:
            stored = _store_png(
                payload=raw,
                destination=destination,
                expected_width=request.width_px,
                expected_height=request.height_px,
            )
        except DownloadRejected as exc:
            self.ledger.mark(reservation_id, "outcome_unknown", rejection=exc.reason)
            raise GenerationFailed(exc.reason) from exc
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else None
        self.ledger.mark(
            reservation_id,
            "generated",
            sha256=stored["sha256"],
            automatic_retry=False,
            retry_count=0,
        )
        return _public_result(
            status="generated",
            generation_status="generated",
            reservation_id=reservation_id,
            estimated_cost_usd=estimate.get("estimated_cost_usd"),
            observed_cost_usd=None,
            generated=True,
            output_path=stored["path"],
            output_paths=[stored["path"]],
            image_sha256=stored["sha256"],
            provider_metadata=_metadata(request, payload, stored, usage),
        )

    def _reasons(self, request: ImageGenerationRequest, estimate: dict[str, Any]) -> list[str]:
        persisted = None
        moment = None
        if policy_mode_of(self.authorization) == POLICY_EXPERIMENTAL:
            moment = clock_or_default(self.clock)
            authorization_id = (self.authorization or {}).get("authorization_id")
            if authorization_id:
                persisted = refresh_experimental_status(self.ledger, str(authorization_id), moment)
        return collect_openai_block_reasons(
            authorization=self.authorization,
            request=request,
            estimate=estimate,
            api_key_present=self._api_key() is not None,
            dry_run=self.dry_run,
            honor_global_paid_lock=self.phase_lock,
            allow_mock_submission=self.allow_mock_submission,
            ledger_summary=self.ledger.summary(),
            persisted_authorization=persisted,
            experimental_submission_enabled=self.experimental_submission_enabled,
            now=moment,
        )

    def _generate_experimental(
        self,
        request: ImageGenerationRequest,
        estimate: dict[str, Any],
    ) -> dict[str, Any]:
        """One submission under an already-open experimental gate. No retry and no fallback."""

        moment = clock_or_default(self.clock)
        reservation = reserve_experimental(
            self.ledger,
            self.authorization or {},
            request,
            now=moment,
        )
        authorization_id = str((self.authorization or {}).get("authorization_id"))
        record_submission_intent(self.ledger, authorization_id, now=moment)
        try:
            body = submission_body(request)
            response = self._exchange(body)
        except TimeoutError as exc:
            self._close_experimental(authorization_id, reservation["reservation_id"], STATUS_OUTCOME_UNKNOWN)
            raise GenerationOutcomeUnknown("timeout") from exc
        except NetworkSealed:
            self._close_experimental(authorization_id, reservation["reservation_id"], STATUS_OUTCOME_UNKNOWN)
            raise
        except SpecError as exc:
            self._close_experimental(authorization_id, reservation["reservation_id"], STATUS_OUTCOME_UNKNOWN)
            raise GenerationOutcomeUnknown("request_rejected_before_body") from exc
        except Exception:
            self._close_experimental(authorization_id, reservation["reservation_id"], STATUS_OUTCOME_UNKNOWN)
            raise
        try:
            result = self._accept(reservation["reservation_id"], request, estimate, response)
        except GenerationOutcomeUnknown:
            self._close_experimental(
                authorization_id,
                reservation["reservation_id"],
                STATUS_OUTCOME_UNKNOWN,
                reconciliation=_reconciliation(response),
            )
            raise
        except GenerationFailed:
            self._close_experimental(authorization_id, reservation["reservation_id"], STATUS_FAILED)
            raise
        observed = observe_provider_cost(_payload_of(response))
        self._close_experimental(
            authorization_id,
            reservation["reservation_id"],
            STATUS_SUCCEEDED,
            usage_present=observed["usage_present"],
        )
        result["estimated_cost_usd"] = None
        result["observed_cost_usd"] = None
        result["verified_maximum_cost_usd"] = None
        result["documented_image_output_estimate_usd"] = estimate.get(
            "published_image_output_estimate_usd"
        )
        result["cost_reconciliation_status"] = COST_RECONCILIATION_PENDING
        result["automatic_retry"] = False
        result["automatic_fallback"] = False
        result["policy_mode"] = POLICY_EXPERIMENTAL
        return result

    def _close_experimental(
        self,
        authorization_id: str,
        reservation_id: str,
        status: str,
        **fields: Any,
    ) -> None:
        if status == STATUS_OUTCOME_UNKNOWN:
            self.ledger.mark(reservation_id, "outcome_unknown", automatic_retry=False, retry_count=0)
        elif status == STATUS_FAILED:
            self.ledger.mark(reservation_id, "failed", automatic_retry=False, retry_count=0)
        finish_authorization(
            self.ledger,
            authorization_id,
            status,
            observed_cost_usd=None,
            verified_maximum_cost_usd=None,
            estimated_cost_usd=None,
            cost_reconciliation_status=COST_RECONCILIATION_PENDING,
            automatic_retry=False,
            automatic_fallback=False,
            **fields,
        )

    def _api_key(self) -> str | None:
        raw = self._env.get(ENV_API_KEY)
        if raw is None or not str(raw).strip():
            return None
        return str(raw).strip()

    def _exchange(self, body: dict[str, Any]) -> Any:
        key = self._api_key()
        if key is None:
            raise PaidCallRefused(["api_key_missing"])
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        encoded = json.dumps(body).encode("utf-8")
        return self.transport.exchange(
            TransportRequest(method="POST", url=GENERATION_URL, headers=headers, body=encoded)
        )


def default_openai_authorization() -> dict[str, Any]:
    return {
        "enabled": False,
        "explicit": False,
        "provider_id": PROVIDER_ID,
        "model_name": OFFICIAL_MODEL_ID,
        "max_images": 0,
        "max_budget_usd": 0,
        "max_total_cost_usd": 0,
        "allow_paid_calls": False,
        "network_calls_allowed": False,
        "dry_run": True,
        "prior_phase_unspent_budget_usd": None,
        "scope": "COVER_GPT_IMAGE_2_4B2342_OFFLINE_ONLY",
    }


def collect_openai_block_reasons(
    *,
    authorization: dict[str, Any] | None,
    request: ImageGenerationRequest,
    estimate: dict[str, Any],
    api_key_present: bool,
    dry_run: bool,
    honor_global_paid_lock: bool,
    allow_mock_submission: bool,
    ledger_summary: dict[str, Any],
    persisted_authorization: dict[str, Any] | None = None,
    experimental_submission_enabled: bool = False,
    now: Any | None = None,
) -> list[str]:
    auth = authorization or {}
    reasons: list[str] = []
    if authorization is None or not auth.get("explicit"):
        reasons.append("explicit_authorization_missing")
    if not auth.get("enabled"):
        reasons.append("authorization_disabled")
    if auth.get("allow_paid_calls") is not True:
        reasons.append("paid_calls_not_allowed")
    if dry_run or auth.get("dry_run") is True:
        reasons.append("dry_run")
    if not api_key_present:
        reasons.append("api_key_missing")
    if honor_global_paid_lock:
        reasons.append("paid_calls_disabled")
    if not allow_mock_submission:
        reasons.append("network_transport_sealed")
    if auth.get("scope") in {
        "COVER_FLUX2_PRO_4B234_OFFLINE_ONLY",
        "COVER_FLUX2_PRO_4B2341_OFFLINE_ONLY",
    }:
        reasons.append("prior_phase_authorization_reused")
    estimate_usd = estimate.get("estimated_cost_usd")
    if not isinstance(estimate_usd, (int, float)) or isinstance(estimate_usd, bool):
        estimate_usd = None
    shared = evaluate_paid_call(
        authorization={
            "explicit": bool(auth.get("explicit")),
            "provider_id": auth.get("provider_id"),
            "model_name": auth.get("model_name"),
            "max_images": auth.get("max_images"),
            "max_budget_usd": auth.get("max_budget_usd", auth.get("max_total_cost_usd")),
            "network_calls_allowed": auth.get("network_calls_allowed"),
            "prior_phase_unspent_budget_usd": auth.get("prior_phase_unspent_budget_usd"),
        },
        request={
            "provider_id": request.provider_id,
            "model_name": request.model_name,
            "image_count": request.image_count,
        },
        estimate_usd=estimate_usd,
        foundation_lock=False,
    )
    reasons.extend(reason for reason in shared["reasons"] if reason not in reasons)
    reasons.extend(problem for problem in request_problems(request) if problem not in reasons)
    budget = auth.get("max_budget_usd", auth.get("max_total_cost_usd"))
    if budget is not None and float(budget) <= 0:
        reasons.append("budget_zero")
    if estimate.get("verified_maximum_cost_usd") is None:
        reasons.append("billing_ceiling_not_guaranteed")
    if not request.output_paths:
        reasons.append("output_path_missing")
    images_reserved = int(ledger_summary.get("images_reserved") or 0)
    max_images = auth.get("max_images")
    if max_images is not None and images_reserved >= int(max_images):
        reasons.append("images_exhausted")
    if images_reserved > 0:
        reasons.append("authorization_already_consumed")
    if ledger_summary.get("outcome_unknown"):
        reasons.append("prior_outcome_unknown")
    reserved_cents = int(ledger_summary.get("reserved_cents") or 0)
    maximum = estimate.get("verified_maximum_cost_usd")
    if budget is not None and isinstance(maximum, (int, float)) and not isinstance(maximum, bool):
        maximum_cents = usd_to_cents(float(maximum))
        if maximum_cents > usd_to_cents(float(budget)):
            reasons.append("verified_maximum_exceeds_cap")
        elif reserved_cents + maximum_cents > usd_to_cents(float(budget)):
            reasons.append("budget_exhausted")
    return finalize_policy_reasons(
        authorization=auth,
        request=request,
        reasons=list(dict.fromkeys(reasons)),
        persisted=persisted_authorization,
        experimental_submission_enabled=experimental_submission_enabled,
        now=now,
    )


def _destination(request: ImageGenerationRequest) -> Path:
    if len(request.output_paths) != 1:
        raise GenerationFailed("output_path_missing")
    path = Path(request.output_paths[0])
    if path.suffix.lower() != ".png":
        raise GenerationFailed("output_path_suffix")
    return path


def _store_png(
    *,
    payload: bytes,
    destination: Path,
    expected_width: int,
    expected_height: int,
) -> dict[str, Any]:
    if len(payload) > MAX_IMAGE_BYTES:
        raise DownloadRejected("file_too_large")
    decoded = decode_image(payload, "png")
    if decoded["width"] != expected_width or decoded["height"] != expected_height:
        raise DownloadRejected("dimension_mismatch")
    digest = hashlib.sha256(payload).hexdigest()
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".partial")
    try:
        partial.write_bytes(payload)
        os.replace(partial, destination)
        written = destination.read_bytes()
    except BaseException:
        partial.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise
    finally:
        if partial.exists():
            partial.unlink(missing_ok=True)
    if hashlib.sha256(written).hexdigest() != digest:
        destination.unlink(missing_ok=True)
        raise DownloadRejected("sha256_mismatch_after_write")
    return {
        "path": str(destination),
        "sha256": digest,
        "width": decoded["width"],
        "height": decoded["height"],
        "bytes": len(payload),
    }


def _metadata(
    request: ImageGenerationRequest,
    payload: dict[str, Any],
    stored: dict[str, Any],
    usage: dict[str, Any] | None,
) -> dict[str, Any]:
    echoed_size = payload.get("size")
    echoed_quality = payload.get("quality")
    echoed_format = payload.get("output_format")
    return {
        "provider_id": PROVIDER_ID,
        "model_id": OFFICIAL_MODEL_ID,
        "prompt_sha256": hashlib.sha256(request.prompt.encode("utf-8")).hexdigest(),
        "output_format": request.metadata.get("output_format"),
        "quality": request.metadata.get("quality"),
        "background": request.metadata.get("background"),
        "width": stored["width"],
        "height": stored["height"],
        "echoed_size": echoed_size if isinstance(echoed_size, str) else None,
        "echoed_quality": echoed_quality if isinstance(echoed_quality, str) else None,
        "echoed_output_format": echoed_format if isinstance(echoed_format, str) else None,
        "usage_present": usage is not None,
        "usage_documented_for_gpt_image_2": False,
        "observed_cost_usd": None,
        "observed_cost_reason": "token_rates_conflict_so_usage_is_not_an_invoice",
        "usage_token_counts": _token_counts(usage),
        "image_sha256": stored["sha256"],
        "negative_prompt_transmitted": False,
        "seed_transmitted": False,
        "reference_images": 0,
        "automatic_retry": False,
    }


def _token_counts(usage: dict[str, Any] | None) -> dict[str, int] | None:
    if not isinstance(usage, dict):
        return None
    counts: dict[str, int] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            counts[key] = value
    details = usage.get("input_tokens_details")
    if isinstance(details, dict):
        for key in ("text_tokens", "image_tokens"):
            value = details.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                counts[key] = value
    return counts or None


def _default_ledger_path() -> Path:
    return Path.cwd() / ".cover_openai_ledger" / "reservations.json"


def _payload_of(response: Any) -> dict[str, Any] | None:
    payload, _status = _decode_http(response)
    if isinstance(payload, dict):
        return payload
    return None


def _reconciliation(response: Any) -> dict[str, Any]:
    payload, status = _decode_http(response)
    keys = sorted(str(key) for key in payload) if isinstance(payload, dict) else []
    return {
        "http_status": status,
        "response_keys": keys,
        "body_retained": False,
    }


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
        "model_id": OFFICIAL_MODEL_ID,
        "model_name": OFFICIAL_MODEL_ID,
        "model_version": SNAPSHOT_MODEL_ID,
        "quality": None,
        "width": None,
        "height": None,
        "output_format": None,
        "image_count": 1,
        "estimated_cost_usd": None,
        "observed_cost_usd": None,
        "generation_status": None,
        "output_path": None,
        "output_paths": [],
        "image_sha256": None,
        "provider_metadata": {},
        "metadata": {},
        "license": "see_commercial_use_verification",
        "error": None,
        "history": [],
        "generated": False,
        "reservation_id": None,
        "status": None,
        "sha256": None,
        "automatic_retry": False,
    }
    result.update(fields)
    result["metadata"] = dict(result.get("provider_metadata") or {})
    result["sha256"] = result.get("image_sha256")
    for secret in ("api_key", "authorization", "Authorization"):
        result.pop(secret, None)
    return result


__all__ = [
    "GenerationFailed",
    "GenerationOutcomeUnknown",
    "OpenAIImageProvider",
    "collect_openai_block_reasons",
    "default_openai_authorization",
]
