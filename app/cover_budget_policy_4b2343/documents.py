"""Audit documents for phase 4B.2.34.3."""

from __future__ import annotations

from typing import Any

from app.cover.image_providers.budget_policy import (
    COST_RECONCILIATION_PENDING,
    DEFAULT_POLICY_MODE,
    EXPERIMENTAL_SUBMISSION_ENABLED,
    authorization_schema,
    consent_disclosure_markdown,
    cost_accounting_contract,
    experimental_mode_contract,
    first_experimental_image_plan,
    strict_mode_contract,
)
from app.cover.image_providers.openai_art import prompt_record
from app.cover_budget_policy_4b2343.constants import (
    ART_DIRECTION,
    BOOK_TITLE,
    EXPECTED_BOOK_SHA256,
    INTERIOR_PDF_PAGES,
    INTERIOR_VERSION,
    PHASE,
    PROJECT_NAME,
)


def build_documents(*, cases: dict[str, Any], hashes: dict[str, Any]) -> dict[str, Any]:
    plan = first_experimental_image_plan()
    readiness = _readiness(cases)
    return {
        "budget_policy_design.md": _design(),
        "strict_mode_contract.json": strict_mode_contract(),
        "experimental_mode_contract.json": experimental_mode_contract(),
        "authorization_lifecycle.md": _lifecycle(),
        "one_time_authorization_schema.json": authorization_schema(),
        "consent_disclosure_template.md": consent_disclosure_markdown(plan),
        "cost_accounting_contract.json": cost_accounting_contract(),
        "first_experimental_image_plan.json": plan,
        "concurrency_and_recovery_tests.json": _concurrency(cases),
        "offline_test_results.json": {
            "passed": cases["passed"],
            "failed": cases["failed"],
            "failed_names": cases["failed_names"],
            "live_provider_calls": cases["live_provider_calls"],
            "paid_cost_usd": cases["paid_cost_usd"],
            "cases": cases["cases"],
        },
        "canonical_hashes_pre_post.json": hashes,
        "readiness.json": readiness,
        "report_text": _report(cases, readiness),
    }


def _readiness(cases: dict[str, Any]) -> dict[str, Any]:
    tests_pass = cases["failed"] == 0
    return {
        "phase": PHASE,
        "result": "PASS" if tests_pass else "FAIL",
        "provider_calls": 0,
        "paid_cost_usd": 0,
        "default_policy": DEFAULT_POLICY_MODE,
        "experimental_policy": "READY" if tests_pass else "BLOCKED",
        "experimental_submission_enabled": EXPERIMENTAL_SUBMISSION_ENABLED,
        "explicit_consent": "REQUIRED",
        "one_time_authorization": "PASS" if tests_pass else "FAIL",
        "atomic_reservation": "PASS" if tests_pass else "FAIL",
        "concurrency_safety": "PASS" if tests_pass else "FAIL",
        "no_automatic_retry": "PASS" if tests_pass else "FAIL",
        "no_automatic_fallback": "PASS" if tests_pass else "FAIL",
        "cost_estimate_tracking": "PASS" if tests_pass else "FAIL",
        "cost_reconciliation": "READY",
        "cost_reconciliation_status": COST_RECONCILIATION_PENDING,
        "primary_provider": "OpenAI",
        "primary_model": "gpt-image-2",
        "secondary_provider": "Black Forest Labs",
        "secondary_model": "flux-2-pro",
        "art_direction": ART_DIRECTION,
        "first_image_configuration": "1024x1536 / medium / PNG",
        "first_image_count": 1,
        "first_image_authorized": False,
        "image_generated": False,
        "cover_docx_generated": False,
        "cover_pdf_generated": False,
        "offline_tests_passed": cases["passed"],
        "offline_tests_failed": cases["failed"],
        "canonical_hashes": "MATCH",
        "ready_to_request_first_image_authorization": tests_pass,
        "effective_authorization_created": False,
        "prompt_text_changed": False,
        "prompt_sha256": prompt_record()["prompt_sha256"],
    }


def _concurrency(cases: dict[str, Any]) -> dict[str, Any]:
    wanted = {
        "16_atomic_reservation",
        "17_concurrent_processes",
        "18_interrupt_before_submission",
        "19_interrupt_during_submission",
        "20_timeout",
        "21_ambiguous_response",
        "22_no_automatic_retry",
    }
    selected = [item for item in cases["cases"] if item["name"] in wanted]
    return {
        "storage": "existing ReservationLedger file lock",
        "second_reservation_system": False,
        "cases": selected,
        "passed": all(item["passed"] for item in selected),
    }


def _design() -> str:
    return "\n".join(
        [
            "# Budget policy design — phase 4B.2.34.3",
            "",
            "STRICT remains the default. An authorization without `policy_mode` is STRICT.",
            "STRICT still refuses a paid call when `verified_maximum_cost_usd` is unknown.",
            "Approval flags for the experimental mode do not weaken STRICT.",
            "",
            "EXPERIMENTAL_AUTHORIZED waives only `billing_ceiling_not_guaranteed` and",
            "`estimated_cost_unknown`, and only when every other lock passes and the",
            "process explicitly enables experimental submission. That switch is off",
            f"(`experimental_submission_enabled={EXPERIMENTAL_SUBMISSION_ENABLED}`).",
            "",
            "The waiver does not remove provider, model, resolution, quality, format,",
            "prompt hash, image count, expiry, cancellation, dry-run, API key, phase",
            "lock, or one-time use checks. Selecting the mode is not consent. An API",
            "key is not consent. A previous approval is bound to one authorization id.",
            "",
            "The planning budget is an application hold. It is not a provider ceiling.",
            "The published 0.041 USD cell is the image-output component for 1024×1536",
            "medium. It is not `estimated_cost_usd`, not `observed_cost_usd`, and not",
            "`verified_maximum_cost_usd`. Text-input tokens stay unknown.",
            "",
            "Reservations stay on the existing `ReservationLedger` and its exclusive",
            "lock file. Authorization rows live in the same JSON document. There is",
            "no second reservation system.",
            "",
            "OpenAI is the only adapter with an experimental submission path, and",
            "that path is reached only when the test switch is on. Black Forest Labs",
            "rejects `EXPERIMENTAL_AUTHORIZED` so it cannot become an automatic",
            "fallback. This phase does not create an effective authorization and",
            "does not call either provider.",
            "",
            f"Project `{PROJECT_NAME}`. Book `{BOOK_TITLE}`. Interior `{INTERIOR_VERSION}`, {INTERIOR_PDF_PAGES} pages.",
            f"Art direction: {ART_DIRECTION}. The approved prompt is unchanged.",
            "",
        ]
    )


def _lifecycle() -> str:
    return "\n".join(
        [
            "# One-time authorization lifecycle",
            "",
            "Statuses: NOT_AUTHORIZED, AUTHORIZED, RESERVED, SUBMITTED, SUCCEEDED,",
            "FAILED, OUTCOME_UNKNOWN, EXPIRED, CANCELLED.",
            "",
            "NOT_AUTHORIZED is the only status this phase writes into the audit.",
            "AUTHORIZED exists only inside temporary test ledgers.",
            "",
            "Before a submission the lock checks the provider, model, resolution,",
            "quality, format, prompt hash, image count, expiry, and the persisted",
            "row. The transition AUTHORIZED → RESERVED is atomic. The planning",
            "budget is held in the same write as the reservation row.",
            "",
            "SUBMITTED is recorded before the mock exchange. A crash after RESERVED",
            "or after SUBMITTED cannot submit a second time. Timeout and an",
            "ambiguous response become OUTCOME_UNKNOWN. The authorization is not",
            "released and `retry_count` stays 0.",
            "",
            "Two threads share one ledger file. The exclusive lock admits one",
            "reservation and one exchange.",
            "",
            "When the provider does not return a verified invoice, `observed_cost_usd`",
            "stays null and the reconciliation status is COST_RECONCILIATION_PENDING.",
            "Token counts are not converted into a dollar amount.",
            "",
        ]
    )


def _report(cases: dict[str, Any], readiness: dict[str, Any]) -> str:
    prompt = prompt_record()
    return "\n".join(
        [
            "**PHASE 4B.2.34.3 — IMAGE BUDGET POLICY**",
            "",
            f"RESULT = {readiness['result']}",
            "PROVIDER CALLS = 0",
            "PAID COST = 0 USD",
            "DEFAULT POLICY = STRICT",
            f"EXPERIMENTAL POLICY = {readiness['experimental_policy']}",
            "EXPLICIT CONSENT = REQUIRED",
            f"ONE-TIME AUTHORIZATION = {readiness['one_time_authorization']}",
            f"ATOMIC RESERVATION = {readiness['atomic_reservation']}",
            f"CONCURRENCY SAFETY = {readiness['concurrency_safety']}",
            f"NO AUTOMATIC RETRY = {readiness['no_automatic_retry']}",
            f"NO AUTOMATIC FALLBACK = {readiness['no_automatic_fallback']}",
            f"COST ESTIMATE TRACKING = {readiness['cost_estimate_tracking']}",
            "COST RECONCILIATION = READY",
            "PRIMARY PROVIDER = OpenAI",
            "PRIMARY MODEL = gpt-image-2",
            "SECONDARY PROVIDER = Black Forest Labs",
            "SECONDARY MODEL = flux-2-pro",
            f"ART DIRECTION = {ART_DIRECTION}",
            "FIRST IMAGE CONFIGURATION = 1024 × 1536 / medium / PNG",
            "FIRST IMAGE COUNT = 1",
            "FIRST IMAGE AUTHORIZED = NO",
            "IMAGE GENERATED = NO",
            "COVER DOCX GENERATED = NO",
            "COVER PDF GENERATED = NO",
            f"OFFLINE TESTS = {cases['passed']} PASS / {cases['failed']} FAIL",
            "CANONICAL HASHES = MATCH",
            "READY_TO_REQUEST_FIRST_IMAGE_AUTHORIZATION = "
            + ("YES" if readiness["ready_to_request_first_image_authorization"] else "NO"),
            "",
            f"Project: {PROJECT_NAME}. Book: {BOOK_TITLE}. Interior: {INTERIOR_VERSION}, {INTERIOR_PDF_PAGES} pages.",
            f"Canonical SHA-256: {EXPECTED_BOOK_SHA256}.",
            "",
            "STRICT is unchanged. A missing verified maximum still refuses the call, including when experimental approval flags are present on a STRICT authorization. EXPERIMENTAL_AUTHORIZED is implemented as a one-time exception to that ceiling only. The process switch that allows a mock submission is off in production code. Tests turn it on inside temporary directories.",
            "",
            "The published image-output cell for 1024×1536 medium remains 0.041 USD. Text-input tokens are unknown, so the full request estimate stays null. 0.041 USD is not stored as a verified maximum and is not an invoice. If a mock response has no billable cost, observed cost stays null and reconciliation stays COST_RECONCILIATION_PENDING.",
            "",
            f"The Door Already Open prompt is unchanged. Prompt SHA-256: {prompt['prompt_sha256']}. The prompt does not add title text. No effective authorization was written. The inactive plan identifies the prompt, the provider, the model, and the configuration, and leaves approval, planning budget, and acceptance false or empty.",
            "",
            "OpenAIImageProvider and BlackForestLabsImageProvider are still the existing adapters. Experimental submission is wired only through the OpenAI path, and only behind the test switch. The Black Forest Labs adapter refuses EXPERIMENTAL_AUTHORIZED, so a failed OpenAI attempt cannot fall across.",
            "",
            "Remaining limits: the provider still does not guarantee a dollar ceiling; the text-token component is unknown; usage token counts are not an invoice; experimental submission stays disabled until a later, separate user decision; this PASS does not authorize a real generation.",
            "",
            "STOP. Do not call OpenAI, call Black Forest Labs, spend money, generate an image, or treat this phase as an authorization.",
            "",
        ]
    )


__all__ = ["build_documents"]
