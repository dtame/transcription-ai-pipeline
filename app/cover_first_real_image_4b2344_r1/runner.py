"""One new gpt-image-2 generation. The previous authorization stays consumed.

Running this module contacts OpenAI at most once. A second exchange is refused.
The live HTTP flag is raised only around that exchange and is lowered again.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

from app.ai.settings import load_env_file
from app.cover.constants import AUTOMATIC_PAID_RETRIES, PAID_CALLS_AUTHORIZED
from app.cover.image_providers.base import CoverImageProvider, ImageGenerationRequest
from app.cover.image_providers.bfl_budget import ReservationLedger
from app.cover.image_providers.bfl_transport import TransportRequest, TransportResponse
from app.cover.image_providers.black_forest_labs import BlackForestLabsImageProvider
from app.cover.image_providers.budget_policy import (
    COST_RECONCILIATION_PENDING,
    EXPERIMENTAL_SUBMISSION_ENABLED,
    EXPLICIT_DECISION,
    ApprovalRefused,
    apply_explicit_approval,
    cancel_authorization,
    documented_cost_components,
    inactive_authorization_template,
    prompt_sha256,
)
from app.cover.image_providers.openai_image import (
    GenerationFailed,
    GenerationOutcomeUnknown,
    OpenAIImageProvider,
)
from app.cover.image_providers.openai_spec import (
    GENERATION_URL,
    OFFICIAL_MODEL_ID,
    REQUESTED_BACKGROUND,
    REQUESTED_OUTPUT_FORMAT,
    REQUESTED_QUALITY,
    SELECTED_HEIGHT,
    SELECTED_WIDTH,
    SNAPSHOT_MODEL_ID,
    submission_body,
)
from app.cover.image_providers.policy import PaidCallRefused
from app.cover_first_real_image_4b2344.redact import assert_text_file_clean, dump_json, dump_text, scrub_text
from app.cover_first_real_image_4b2344.transport import SingleUseLiveTransport
from app.cover_first_real_image_4b2344_r1.art import PROMPT, prompt_record
from app.cover_first_real_image_4b2344_r1.constants import (
    ART_DIRECTION,
    AUTHORIZATION_SCOPE,
    AUTHORIZATION_TTL_HOURS,
    BOOK_TITLE,
    EXPECTED_BOOK_SHA256,
    EXPECTED_IMAGE_OUTPUT_CELL_USD,
    EXPECTED_INTERIOR_DOCX_SHA256,
    EXPECTED_INTERIOR_PDF_SHA256,
    EXPECTED_PROMPT_SHA256,
    EXPECTED_WORD_PROFILE_SHA256,
    OLD_AUTHORIZATION_ID,
    OLD_PROMPT_SHA256,
    PHASE,
    PLANNING_BUDGET_USD,
    PROJECT_NAME,
    PURPOSE,
    USER_AUTHORIZATION_STATEMENT,
)
from app.cover_first_real_image_4b2344_r1.network_preflight import verify_network_fix
from app.cover_first_real_image_4b2344_r1.paths import (
    generated_dir,
    image_path,
    ledger_path,
    phase_audit_dir,
    previous_phase_ledger_path,
    quarantine_path,
    report_path,
    sidecar_path,
)
from app.cover_first_real_image_4b2344_r1.report import render
from app.cover_first_real_image_4b2344_r1.validation import inspect_received_png
from app.cover_generator_foundation_4b233.hashes import hashes_match, snapshot
from app.cover_generator_foundation_4b233.paths import repo_root
import app.cover.image_providers.bfl_transport as transport_module
from app.cover.image_providers.bfl_transport import NetworkSealed

_REQUIRED_PROMPT_PHRASES = (
    "spiritual access to a reality already given",
    "rather than achievement or striving",
    "The Door Already Open",
    "is metaphorical",
    "Do not depict a literal household door",
    "unseen spiritual reality is already accessible",
    "without relying on obvious religious clichés",
    "Access rather than achievement",
    "No text.",
    "No letters.",
    "No words.",
    "No title.",
    "No subtitle.",
    "No author name.",
    "No typography.",
    "No logo.",
    "No ISBN.",
    "No barcode.",
    "No watermark.",
)
_TERMINAL = {"SUCCEEDED", "FAILED", "OUTCOME_UNKNOWN", "EXPIRED", "CANCELLED"}
_RAN = False


def main() -> dict[str, Any]:
    global _RAN
    if _RAN:
        raise RuntimeError("this phase already ran in this process")
    _RAN = True
    os.chdir(repo_root())
    try:
        return _run()
    finally:
        transport_module.LIVE_HTTP_ENABLED = False


def _run() -> dict[str, Any]:
    outcome = _blank()
    pre_compact, pre_full = _capture()
    outcome["hashes"]["pre"] = pre_compact
    outcome["previous_ledger_pre"] = _ledger_fingerprint(previous_phase_ledger_path())
    if ledger_path().resolve() == previous_phase_ledger_path().resolve():
        outcome["result"] = "BLOCKED_BEFORE_SUBMISSION"
        outcome["block_reason"] = "new ledger path collides with the consumed authorization ledger"
        outcome["narrative"] = "Le registre de la nouvelle tentative pointe vers l'ancienne autorisation. Aucun appel."
        return _finish(outcome, pre_full)
    if not _canonical_preflight(pre_compact):
        outcome["result"] = "BLOCKED_BEFORE_SUBMISSION"
        outcome["block_reason"] = "canonical_hash_mismatch"
        outcome["narrative"] = (
            "Le SHA-256 de book.json ou d'un fichier intérieur print-review-v1.1 "
            "ne correspond pas à la valeur attendue. Aucune autorisation n'a été créée. "
            "OpenAI n'a pas été contacté."
        )
        return _finish(outcome, pre_full)
    if (
        transport_module.LIVE_HTTP_ENABLED
        or EXPERIMENTAL_SUBMISSION_ENABLED
        or PAID_CALLS_AUTHORIZED
    ):
        outcome["result"] = "BLOCKED_BEFORE_SUBMISSION"
        outcome["block_reason"] = "persistent_network_unlock_detected"
        outcome["narrative"] = "Un verrou permanent de réseau ou d'autorisation est déjà ouvert. Aucun appel."
        return _finish(outcome, pre_full)
    try:
        outcome["network_fix"] = verify_network_fix()
    except Exception as exc:
        transport_module.LIVE_HTTP_ENABLED = False
        outcome["network_fix"] = {"passed": False, "provider_contacted": False, "error": type(exc).__name__}
    if transport_module.LIVE_HTTP_ENABLED or not (outcome.get("network_fix") or {}).get("passed"):
        transport_module.LIVE_HTTP_ENABLED = False
        outcome["result"] = "BLOCKED_BEFORE_SUBMISSION"
        outcome["block_reason"] = "network_seal_fix_not_verified"
        outcome["narrative"] = (
            "Le correctif NetworkSealed n'est pas confirmé localement. "
            "Aucun appel fournisseur n'a été fait pour tester cette condition."
        )
        return _finish(outcome, pre_full)
    load_env_file()
    outcome["preflight"]["api_key_present"] = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    outcome["preflight"]["api_key_value_recorded"] = False
    if not outcome["preflight"]["api_key_present"]:
        outcome["result"] = "BLOCKED_MISSING_API_KEY"
        outcome["block_reason"] = "OPENAI_API_KEY absent"
        outcome["narrative"] = "La clé API est absente. Aucune autorisation n'a été créée. Aucun appel."
        return _finish(outcome, pre_full)
    outcome["preflight"]["prompt_phrases"] = {phrase: phrase in PROMPT for phrase in _REQUIRED_PROMPT_PHRASES}
    outcome["preflight"]["prompt_sha256"] = prompt_sha256(PROMPT)
    outcome["preflight"]["previous_prompt_sha256"] = OLD_PROMPT_SHA256
    outcome["preflight"]["previous_prompt_reused"] = False
    outcome["preflight"]["title_embedded_in_prompt"] = "The Life You Already Inherited" in PROMPT
    problems = _configuration_problems()
    outcome["preflight"]["configuration_problems"] = problems
    if problems or not all(outcome["preflight"]["prompt_phrases"].values()):
        outcome["result"] = "BLOCKED_AUTHORIZATION_MISMATCH"
        outcome["block_reason"] = "request configuration does not match the authorization"
        outcome["narrative"] = "La configuration ou le prompt spirituel ne correspond pas. Aucun appel."
        return _finish(outcome, pre_full)
    if not _previous_authorization_still_consumed():
        outcome["result"] = "BLOCKED_BEFORE_SUBMISSION"
        outcome["block_reason"] = "previous authorization is missing or was reactivated"
        outcome["narrative"] = (
            "L'autorisation 063a16a7ea284329b944339265d26e8c n'est pas restée consommée. "
            "Elle n'est pas réactivée. Aucun appel."
        )
        return _finish(outcome, pre_full)
    outcome["preflight"]["adapter"] = _adapter_report()
    existing = _existing_ledger_block(ledger_path())
    if existing:
        outcome["result"] = "BLOCKED_BEFORE_SUBMISSION"
        outcome["block_reason"] = existing
        outcome["narrative"] = "Le registre de cette reprise contient déjà une autorisation. Aucun nouvel appel."
        return _finish(outcome, pre_full)
    probe = _policy_probe()
    outcome["preflight"]["policy_probe"] = probe
    if not probe.get("passed"):
        outcome["result"] = "BLOCKED_BEFORE_SUBMISSION"
        outcome["block_reason"] = "prepared prompt gate refused the spiritual revision or accepted an arbitrary prompt"
        outcome["narrative"] = "Le contrôle local du hash de prompt a échoué. Aucun appel."
        return _finish(outcome, pre_full)
    rehearsal = _rehearse()
    outcome["preflight"]["rehearsal"] = rehearsal
    if not rehearsal.get("passed"):
        outcome["result"] = "BLOCKED_BEFORE_SUBMISSION"
        outcome["block_reason"] = "offline rehearsal refused the experimental gate"
        outcome["narrative"] = "La répétition locale a refusé la soumission. OpenAI n'a pas été contacté."
        return _finish(outcome, pre_full)
    destination = image_path().resolve().as_posix()
    now = datetime.now(timezone.utc)
    authorization_id = uuid4().hex
    if authorization_id == OLD_AUTHORIZATION_ID:
        outcome["result"] = "BLOCKED_BEFORE_SUBMISSION"
        outcome["block_reason"] = "new authorization id collided with the consumed authorization"
        outcome["narrative"] = "L'identifiant neuf a coïncidé avec l'ancienne autorisation. Aucun appel."
        return _finish(outcome, pre_full)
    auth = _authorize(destination=destination, authorization_id=authorization_id, now=now)
    outcome["authorization_id"] = auth["authorization_id"]
    outcome["new_authorization"] = "VERIFIED"
    outcome["user_authorization"] = "VERIFIED"
    outcome["old_authorization_reused"] = "NO"
    ledger = ledger_path()
    generated_dir().mkdir(parents=True, exist_ok=True)
    persist_error = _persist(ledger, auth)
    if persist_error:
        outcome["result"] = "BLOCKED_BEFORE_SUBMISSION"
        outcome["block_reason"] = persist_error
        outcome["narrative"] = "L'autorisation n'a pas pu être enregistrée. Aucun appel."
        return _finish(outcome, pre_full)
    request = _request(destination)
    body = submission_body(request)
    outcome["submission_body"] = body
    mismatch = _body_mismatch(body, auth)
    if mismatch:
        _cancel_if_possible(ledger, auth["authorization_id"])
        outcome["result"] = "BLOCKED_AUTHORIZATION_MISMATCH"
        outcome["block_reason"] = mismatch
        outcome["authorization_use"] = "CANCELLED_BEFORE_SUBMISSION"
        outcome["narrative"] = "Le hash du prompt ou le corps de la requête ne correspond pas. Aucun appel."
        return _finish(outcome, pre_full)
    transport = SingleUseLiveTransport(quarantine=quarantine_path())
    provider = _provider(auth, ledger, transport, os.environ)
    reasons = provider._reasons(request, provider.estimate_cost(request))
    outcome["preflight"]["block_reasons_before_socket"] = list(reasons)
    _write_progress(outcome, auth)
    if reasons:
        _cancel_if_possible(ledger, auth["authorization_id"])
        outcome["result"] = "BLOCKED_BEFORE_SUBMISSION"
        outcome["block_reason"] = ",".join(reasons)
        outcome["authorization_use"] = "CANCELLED_BEFORE_SUBMISSION"
        outcome["authorization_status"] = _auth_status(ledger, auth["authorization_id"])
        outcome["narrative"] = "Une vérification a échoué avant le réseau. L'autorisation a été annulée."
        outcome["consumption"] = _consumption_test(auth, ledger, destination)
        return _finish(outcome, pre_full)
    _submit_once(outcome, provider, request, transport)
    outcome["authorization_status"] = _auth_status(ledger, auth["authorization_id"])
    if outcome["authorization_status"] == "AUTHORIZED":
        _cancel_if_possible(ledger, auth["authorization_id"])
        outcome["authorization_status"] = _auth_status(ledger, auth["authorization_id"])
        outcome["authorization_use"] = "CANCELLED_BEFORE_SUBMISSION"
    elif outcome["submission_started"] or outcome["authorization_status"] in _TERMINAL:
        outcome["authorization_use"] = "CONSUMED"
    outcome["consumption"] = _consumption_test(auth, ledger, destination)
    return _finish(outcome, pre_full)


def _submit_once(
    outcome: dict[str, Any],
    provider: OpenAIImageProvider,
    request: ImageGenerationRequest,
    transport: SingleUseLiveTransport,
) -> None:
    if outcome.get("real_provider_calls"):
        raise RuntimeError("second paid generate refused")
    if transport_module.LIVE_HTTP_ENABLED:
        raise RuntimeError("live http was already enabled")
    transport_module.LIVE_HTTP_ENABLED = True
    started = datetime.now(timezone.utc)
    result: dict[str, Any] | None = None
    caught: BaseException | None = None
    try:
        result = provider.generate(request)
    except (PaidCallRefused, GenerationOutcomeUnknown, GenerationFailed, NetworkSealed, Exception) as exc:
        caught = exc
    finally:
        transport_module.LIVE_HTTP_ENABLED = False
    completed = datetime.now(timezone.utc)
    outcome["submission_started_at"] = started.isoformat()
    outcome["completion_at"] = completed.isoformat()
    outcome["socket_opened"] = bool(transport.trace.get("socket_opened"))
    outcome["real_provider_calls"] = 1 if outcome["socket_opened"] else 0
    outcome["http_status"] = transport.trace.get("http_status")
    outcome["provider_request_id"] = transport.trace.get("provider_request_id")
    outcome["transport_trace"] = transport.trace
    outcome["http_request_sent"] = "YES" if outcome["socket_opened"] else "NO"
    outcome["openai_http_response_received"] = "YES" if outcome["http_status"] is not None else "NO"
    outcome["submission_started"] = bool(outcome["socket_opened"] or outcome["real_provider_calls"])
    row = _auth_row(ledger_path(), str(outcome["authorization_id"]))
    outcome["submission_intent_recorded"] = bool(row and (row.get("submitted_at") or int(row.get("submission_count") or 0) >= 1))
    if row and int(row.get("submission_count") or 0) >= 1:
        outcome["submission_started"] = True
        outcome["submitted_at"] = row.get("submitted_at")
    if transport.exchange_count > 1:
        outcome["second_exchange_attempted"] = True
    if caught is None and result is not None:
        _accept_result(outcome, result, transport)
        return
    _accept_exception(outcome, caught, transport)


def _accept_result(
    outcome: dict[str, Any],
    result: dict[str, Any],
    transport: SingleUseLiveTransport,
) -> None:
    official = image_path()
    inspection = inspect_received_png(official)
    outcome["image_inspection"] = inspection
    outcome["generation_result"] = _public_generation(result)
    outcome["image_count_received"] = 1 if inspection.get("exists") else 0
    outcome["resolution_received"] = _resolution(inspection)
    outcome["image_sha256"] = inspection.get("sha256")
    outcome["image_path"] = str(official) if inspection.get("exists") else None
    outcome["technical_image_validation"] = inspection.get("technical_validation")
    outcome["output_dimension_status"] = inspection.get("output_dimension_status")
    outcome["human_visual_review"] = (
        "PENDING_HUMAN_VISUAL_REVIEW" if inspection.get("exists") else "NOT_APPLICABLE"
    )
    outcome["billing_known"] = False
    outcome["observed_cost_usd"] = None
    outcome["cost_reconciliation"] = COST_RECONCILIATION_PENDING
    if inspection.get("technical_validation") == "PASS":
        outcome["result"] = "PASS_PENDING_VISUAL_REVIEW"
        outcome["next_step"] = "HUMAN_VISUAL_REVIEW"
        outcome["narrative"] = (
            "Une image PNG a été reçue, validée techniquement et stockée. "
            "L'examen visuel humain reste à faire. Aucune couverture n'a été composée. "
            "Aucun second appel n'a été fait."
        )
    else:
        outcome["result"] = "FAILED_AFTER_SUBMISSION"
        outcome["next_step"] = "STOP"
        outcome["narrative"] = (
            "Le fournisseur a répondu, mais la validation technique du fichier a échoué. "
            "Aucun second appel n'a été fait."
        )
    if transport.trace.get("dimension_mismatch"):
        outcome["output_dimension_status"] = "OUTPUT_DIMENSION_MISMATCH"
        outcome["result"] = "FAILED_AFTER_SUBMISSION"
        outcome["next_step"] = "STOP"


def _accept_exception(
    outcome: dict[str, Any],
    caught: BaseException | None,
    transport: SingleUseLiveTransport,
) -> None:
    outcome["exception_type"] = type(caught).__name__ if caught else None
    status = getattr(caught, "status", None) if caught else None
    outcome["exception_status"] = status if isinstance(status, str) else None
    outcome["exception_message"] = scrub_text(str(caught)) if caught else None
    reasons = getattr(caught, "reasons", None) if caught else None
    if isinstance(reasons, list):
        outcome["exception_reasons"] = [scrub_text(str(item)) for item in reasons]
    row = _auth_row(ledger_path(), str(outcome.get("authorization_id")))
    auth_status = str((row or {}).get("status") or "")
    outcome["billing_known"] = False
    outcome["observed_cost_usd"] = None
    submitted = int((row or {}).get("submission_count") or 0) >= 1 or auth_status in {
        "SUBMITTED",
        "SUCCEEDED",
        "FAILED",
        "OUTCOME_UNKNOWN",
    }
    outcome["submission_started"] = submitted or bool(outcome.get("socket_opened"))
    outcome["submission_intent_recorded"] = submitted
    if not submitted and not outcome.get("socket_opened"):
        outcome["result"] = "BLOCKED_BEFORE_SUBMISSION"
        outcome["cost_reconciliation"] = "NOT_SUBMITTED"
        outcome["next_step"] = "STOP"
        outcome["http_request_sent"] = "NO"
        outcome["narrative"] = "L'appel réseau n'a pas commencé. Aucun second essai n'a été fait."
        return
    quarantine = quarantine_path()
    if transport.trace.get("dimension_mismatch") or status == "dimension_mismatch":
        inspection = inspect_received_png(quarantine) if quarantine.exists() else {"exists": False}
        outcome["image_inspection"] = inspection
        outcome["output_dimension_status"] = "OUTPUT_DIMENSION_MISMATCH"
        outcome["image_path"] = str(quarantine) if inspection.get("exists") else None
        outcome["image_sha256"] = inspection.get("sha256")
        outcome["resolution_received"] = _resolution(inspection) if inspection.get("exists") else (
            f"{transport.trace.get('received_width')}x{transport.trace.get('received_height')}"
        )
        outcome["image_count_received"] = (transport.trace.get("response_summary") or {}).get("data_count")
        outcome["technical_image_validation"] = "FAIL"
        outcome["human_visual_review"] = (
            "PENDING_HUMAN_VISUAL_REVIEW" if inspection.get("exists") else "NOT_APPLICABLE"
        )
        outcome["result"] = "FAILED_AFTER_SUBMISSION"
        outcome["cost_reconciliation"] = COST_RECONCILIATION_PENDING
        outcome["next_step"] = "STOP"
        outcome["narrative"] = (
            "L'image reçue n'a pas les dimensions autorisées. "
            "Elle est conservée en quarantaine lorsque le fichier a pu être écrit. "
            "Aucune seconde génération n'a été lancée."
        )
        return
    if auth_status == "FAILED":
        outcome["result"] = "FAILED_AFTER_SUBMISSION"
    else:
        outcome["result"] = "OUTCOME_UNKNOWN"
    outcome["cost_reconciliation"] = COST_RECONCILIATION_PENDING
    outcome["technical_image_validation"] = "FAIL"
    outcome["human_visual_review"] = "NOT_APPLICABLE"
    outcome["next_step"] = "STOP"
    outcome["image_count_received"] = (transport.trace.get("response_summary") or {}).get("data_count")
    outcome["narrative"] = (
        "La tentative potentiellement facturable est terminée sans image exploitable. "
        "Le coût réel n'est pas connu. Aucun nouvel essai n'a été fait."
    )


def _finish(outcome: dict[str, Any], pre_full: dict[str, Any]) -> dict[str, Any]:
    transport_module.LIVE_HTTP_ENABLED = False
    post_compact, post_full = _capture()
    outcome["hashes"]["post"] = post_compact
    outcome["hashes"]["match"] = hashes_match(pre_full, post_full) and _canonical_preflight(post_compact)
    outcome["canonical_hashes"] = "MATCH" if outcome["hashes"]["match"] else "MISMATCH"
    outcome["previous_ledger_post"] = _ledger_fingerprint(previous_phase_ledger_path())
    outcome["previous_ledger_unchanged"] = outcome["previous_ledger_pre"] == outcome["previous_ledger_post"]
    if not outcome["previous_ledger_unchanged"]:
        outcome["narrative"] = (
            str(outcome.get("narrative") or "")
            + " Le registre de l'autorisation précédente a changé."
        )
    if outcome["canonical_hashes"] == "MISMATCH" and outcome["result"] == "PASS_PENDING_VISUAL_REVIEW":
        outcome["narrative"] = (
            str(outcome.get("narrative") or "")
            + " Le hash canonique relevé après l'opération ne correspond pas."
        )
    _classify_cost(outcome)
    outcome["consumption"] = outcome.get("consumption") or {"performed": False}
    _write_all(outcome)
    print(
        f"PHASE 4B.2.34.4-R1 {outcome['result']} "
        f"calls={outcome['real_provider_calls']} "
        f"authorization={outcome.get('authorization_status')} "
        f"hashes={outcome['canonical_hashes']}"
    )
    return outcome


def _write_all(outcome: dict[str, Any]) -> None:
    audit = phase_audit_dir()
    audit.mkdir(parents=True, exist_ok=True)
    auth_row = _auth_row(ledger_path(), outcome.get("authorization_id"))
    dump_json(audit / "new_authorization_record_redacted.json", _authorization_document(outcome, auth_row))
    dump_json(audit / "revised_spiritual_art_prompt.json", prompt_record())
    dump_json(audit / "prompt_sha256.json", _prompt_hash_document(outcome, auth_row))
    dump_json(audit / "network_fix_preflight.json", outcome.get("network_fix") or {"passed": False, "performed": False})
    dump_json(audit / "preflight_report.json", outcome.get("preflight"))
    dump_json(audit / "submission_record_redacted.json", _submission_document(outcome))
    dump_json(audit / "generation_result.json", _generation_document(outcome))
    dump_json(audit / "image_validation.json", outcome.get("image_inspection") or {"performed": False})
    dump_json(audit / "cost_reconciliation.json", _cost_document(outcome))
    dump_json(audit / "authorization_consumption_test.json", outcome.get("consumption"))
    dump_json(audit / "canonical_hashes_pre_post.json", _hash_document(outcome))
    dump_json(audit / "readiness.json", _readiness(outcome))
    dump_text(report_path(), render(outcome))
    if outcome.get("image_path") or outcome.get("submission_started"):
        dump_json(sidecar_path(), _generation_document(outcome))
    paths = list(audit.glob("*.json")) + [report_path(), sidecar_path(), ledger_path()]
    for path in paths:
        if path.exists() and path.suffix.lower() in {".json", ".md"}:
            assert_text_file_clean(path)


def _write_progress(outcome: dict[str, Any], auth: dict[str, Any]) -> None:
    audit = phase_audit_dir()
    audit.mkdir(parents=True, exist_ok=True)
    dump_json(audit / "new_authorization_record_redacted.json", _authorization_document(outcome, auth))
    dump_json(audit / "revised_spiritual_art_prompt.json", prompt_record())
    dump_json(audit / "prompt_sha256.json", _prompt_hash_document(outcome, auth))
    dump_json(audit / "network_fix_preflight.json", outcome.get("network_fix") or {"performed": False})
    dump_json(audit / "preflight_report.json", outcome.get("preflight"))
    dump_json(
        audit / "submission_record_redacted.json",
        {"sent": False, "body": outcome.get("submission_body"), "automatic_retry": False, "fallback": False},
    )


def _blank() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "result": None,
        "block_reason": None,
        "real_provider_calls": 0,
        "new_authorization": "NOT_CREATED",
        "user_authorization": "NOT_BOUND",
        "old_authorization_reused": "NO",
        "authorization_use": "NOT_CREATED",
        "image_count_requested": 1,
        "image_count_received": None,
        "resolution_received": None,
        "image_sha256": None,
        "image_path": None,
        "estimated_cost_usd": None,
        "observed_cost_usd": None,
        "verified_maximum_cost_usd": None,
        "documented_image_output_estimate_usd": EXPECTED_IMAGE_OUTPUT_CELL_USD,
        "estimated_cost_display": "unknown; published image-output cell 0.041 USD is not a total",
        "cost_reconciliation": "NOT_SUBMITTED",
        "technical_image_validation": "NOT_RUN",
        "human_visual_review": "NOT_APPLICABLE",
        "canonical_hashes": None,
        "next_step": "STOP",
        "authorization_id": None,
        "authorization_status": None,
        "http_status": None,
        "provider_request_id": None,
        "submission_started": False,
        "submission_intent_recorded": False,
        "socket_opened": False,
        "http_request_sent": "NO",
        "openai_http_response_received": "NO",
        "billing_known": False,
        "exception_type": None,
        "exception_status": None,
        "exception_message": None,
        "output_dimension_status": None,
        "narrative": "",
        "network_fix": {"performed": False},
        "preflight": {
            "provider": "openai",
            "model": "gpt-image-2",
            "image_count": 1,
            "size": "1024x1536",
            "quality": "medium",
            "output_format": "png",
            "background": REQUESTED_BACKGROUND,
            "purpose": PURPOSE,
            "experimental_submission_module_constant": EXPERIMENTAL_SUBMISSION_ENABLED,
            "live_http_enabled_at_start": transport_module.LIVE_HTTP_ENABLED,
            "global_paid_calls_authorized": PAID_CALLS_AUTHORIZED,
            "automatic_retries_enabled": bool(AUTOMATIC_PAID_RETRIES),
            "old_authorization_id": OLD_AUTHORIZATION_ID,
            "old_authorization_reused": False,
        },
        "hashes": {},
        "consumption": {"performed": False},
    }


def _capture() -> tuple[dict[str, Any], dict[str, Any]]:
    full = snapshot()
    profile = (full.get("word_profile") or {}).get("sha256")
    compact = {
        "book_json": full.get("book_json"),
        "interior_docx": full.get("interior_docx"),
        "interior_pdf": full.get("interior_pdf"),
        "word_profile": full.get("word_profile"),
        "book_json_match_expected": full.get("book_json_match_expected"),
        "interior_match_expected": full.get("interior_match_expected"),
        "word_profile_match_expected": profile == EXPECTED_WORD_PROFILE_SHA256,
        "expected_book_sha256": EXPECTED_BOOK_SHA256,
        "expected_interior_docx_sha256": EXPECTED_INTERIOR_DOCX_SHA256,
        "expected_interior_pdf_sha256": EXPECTED_INTERIOR_PDF_SHA256,
        "expected_word_profile_sha256": EXPECTED_WORD_PROFILE_SHA256,
    }
    return compact, full


def _canonical_preflight(compact: dict[str, Any]) -> bool:
    book = (compact.get("book_json") or {}).get("sha256")
    docx = (compact.get("interior_docx") or {}).get("sha256")
    pdf = (compact.get("interior_pdf") or {}).get("sha256")
    profile = (compact.get("word_profile") or {}).get("sha256")
    return (
        book == EXPECTED_BOOK_SHA256
        and docx == EXPECTED_INTERIOR_DOCX_SHA256
        and pdf == EXPECTED_INTERIOR_PDF_SHA256
        and profile == EXPECTED_WORD_PROFILE_SHA256
    )


def _configuration_problems() -> list[str]:
    problems: list[str] = []
    if prompt_sha256(PROMPT) != EXPECTED_PROMPT_SHA256:
        problems.append("prompt_sha256")
    if EXPECTED_PROMPT_SHA256 == OLD_PROMPT_SHA256:
        problems.append("previous_prompt_hash_reused")
    if documented_cost_components()["image_output_usd"] != EXPECTED_IMAGE_OUTPUT_CELL_USD:
        problems.append("documented_image_output_estimate")
    if "The Life You Already Inherited" in PROMPT:
        problems.append("title_embedded_in_prompt")
    if "already standing open" in PROMPT or "domestic doorway" in PROMPT:
        problems.append("literal_door_prompt_reused")
    return problems


def _adapter_report() -> dict[str, Any]:
    return {
        "openai_provider": OpenAIImageProvider.__name__,
        "openai_provider_available": issubclass(OpenAIImageProvider, CoverImageProvider),
        "black_forest_labs_provider_present": issubclass(BlackForestLabsImageProvider, CoverImageProvider),
        "black_forest_labs_used": False,
        "automatic_fallback": False,
        "automatic_retry": False,
        "module_experimental_submission_enabled": EXPERIMENTAL_SUBMISSION_ENABLED,
        "instance_experimental_submission_enabled_for_this_execution": True,
        "paid_call_transport": "UrllibTransport",
        "mock_used_for_paid_call": False,
    }


def _existing_ledger_block(path: Path) -> str | None:
    if path.with_suffix(".lock").exists():
        return "authorization lock is already held"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if OLD_AUTHORIZATION_ID in path.read_text(encoding="utf-8"):
        return "new ledger contains the consumed authorization id"
    authorizations = list(payload.get("authorizations") or [])
    reservations = list(payload.get("reservations") or [])
    if reservations:
        return "phase ledger already has a reservation"
    for row in authorizations:
        status = str(row.get("status") or "")
        if status != "CANCELLED" or row.get("submitted_at") or int(row.get("submission_count") or 0):
            return "phase ledger already has an authorization that must not be replaced"
    if authorizations:
        return "phase ledger already has a cancelled authorization"
    return None


def _previous_authorization_still_consumed() -> bool:
    path = previous_phase_ledger_path()
    if not path.is_file():
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    for row in payload.get("authorizations") or []:
        if row.get("authorization_id") != OLD_AUTHORIZATION_ID:
            continue
        status = str(row.get("status") or "")
        return status in _TERMINAL and status != "AUTHORIZED" and row.get("effective") is not True
    return False


def _policy_probe() -> dict[str, Any]:
    with TemporaryDirectory() as tmp:
        destination = (Path(tmp) / "probe.png").resolve().as_posix()
        now = datetime.now(timezone.utc)
        spiritual = _authorize(
            destination=destination,
            authorization_id=uuid4().hex,
            now=now,
        )
        original = _authorize(
            destination=destination,
            authorization_id=uuid4().hex,
            now=now,
            prompt_digest=OLD_PROMPT_SHA256,
        )
        refused = False
        reason = None
        try:
            _authorize(
                destination=destination,
                authorization_id=uuid4().hex,
                now=now,
                prompt_digest="0" * 64,
            )
        except ApprovalRefused as exc:
            refused = exc.reason == "prompt_sha256_not_prepared"
            reason = exc.reason
        return {
            "passed": bool(
                spiritual.get("prompt_sha256") == EXPECTED_PROMPT_SHA256
                and spiritual.get("explicit_user_approval") is True
                and spiritual.get("purpose") == PURPOSE
                and original.get("prompt_sha256") == OLD_PROMPT_SHA256
                and refused
                and spiritual.get("authorization_id") != OLD_AUTHORIZATION_ID
            ),
            "spiritual_hash_accepted": spiritual.get("prompt_sha256") == EXPECTED_PROMPT_SHA256,
            "original_hash_still_prepared": original.get("prompt_sha256") == OLD_PROMPT_SHA256,
            "arbitrary_hash_refused": refused,
            "arbitrary_refusal": reason,
            "persisted": False,
            "provider_contacted": False,
        }


def _rehearse() -> dict[str, Any]:
    if transport_module.LIVE_HTTP_ENABLED:
        return {"passed": False, "reason": "live http was already enabled"}
    with TemporaryDirectory() as tmp:
        destination = (Path(tmp) / "door.png").resolve().as_posix()
        ledger = Path(tmp) / "ledger.json"
        auth = _authorize(destination=destination, authorization_id=uuid4().hex, now=datetime.now(timezone.utc))
        persist_error = _persist(ledger, auth)
        if persist_error:
            return {"passed": False, "reason": persist_error}

        class _Mock:
            def __init__(self) -> None:
                self.calls = 0

            def exchange(self, request: TransportRequest) -> TransportResponse:
                self.calls += 1
                if transport_module.LIVE_HTTP_ENABLED:
                    raise RuntimeError("rehearsal refused while live http is enabled")
                encoded = base64.b64encode(_png(SELECTED_WIDTH, SELECTED_HEIGHT)).decode("ascii")
                return TransportResponse(
                    status=200,
                    headers={"content-type": "application/json"},
                    body=json.dumps(
                        {
                            "created": 1,
                            "data": [{"b64_json": encoded}],
                            "output_format": "png",
                            "quality": "medium",
                            "size": "1024x1536",
                        }
                    ).encode("utf-8"),
                    url=GENERATION_URL,
                )

        mock = _Mock()
        provider = _provider(auth, ledger, mock, {"OPENAI_API_KEY": "rehearsal-key-not-sent"})
        try:
            result = provider.generate(_request(destination))
        except PaidCallRefused as exc:
            return {"passed": False, "reasons": list(exc.reasons), "mock_calls": mock.calls}
        stored = Path(destination).is_file()
        return {
            "passed": bool(
                result.get("generated")
                and stored
                and mock.calls == 1
                and not transport_module.LIVE_HTTP_ENABLED
                and auth["authorization_id"] != OLD_AUTHORIZATION_ID
            ),
            "mock_calls": mock.calls,
            "live_http_enabled": transport_module.LIVE_HTTP_ENABLED,
            "openai_contacted": False,
        }


def _authorize(
    *,
    destination: str,
    authorization_id: str,
    now: datetime,
    prompt_digest: str | None = None,
) -> dict[str, Any]:
    auth = inactive_authorization_template()
    components = documented_cost_components()
    digest = prompt_digest or prompt_sha256(PROMPT)
    auth.update(
        {
            "authorization_id": authorization_id,
            "scope": AUTHORIZATION_SCOPE,
            "planning_budget_usd": PLANNING_BUDGET_USD,
            "max_budget_usd": PLANNING_BUDGET_USD,
            "max_total_cost_usd": PLANNING_BUDGET_USD,
            "destination": destination,
            "expires_at": (now + timedelta(hours=AUTHORIZATION_TTL_HOURS)).isoformat(),
            "created_at": now.isoformat(),
            "status": "NOT_AUTHORIZED",
            "effective": False,
            "explicit_user_approval": False,
            "accepts_unbounded_provider_cost": False,
            "explicit_decision": None,
            "documented_image_output_estimate_usd": components["image_output_usd"],
            "prompt_sha256": digest,
            "prompt_text_changed": digest != OLD_PROMPT_SHA256,
            "purpose": PURPOSE,
            "project_id": PROJECT_NAME,
            "user_authorization_statement": USER_AUTHORIZATION_STATEMENT,
            "art_direction": ART_DIRECTION,
            "book_title": BOOK_TITLE,
            "previous_authorization_id": OLD_AUTHORIZATION_ID,
            "previous_authorization_reactivated": False,
        }
    )
    return apply_explicit_approval(
        auth,
        decision=EXPLICIT_DECISION,
        disable_dry_run=True,
        now=now,
    )


def _request(destination: str) -> ImageGenerationRequest:
    return ImageGenerationRequest(
        provider_id="openai",
        model_name=OFFICIAL_MODEL_ID,
        model_version=SNAPSHOT_MODEL_ID,
        prompt=PROMPT,
        negative_prompt=None,
        width_px=SELECTED_WIDTH,
        height_px=SELECTED_HEIGHT,
        aspect_ratio="2:3",
        seed=None,
        image_count=1,
        output_paths=[destination],
        metadata={
            "quality": REQUESTED_QUALITY,
            "output_format": REQUESTED_OUTPUT_FORMAT,
            "background": REQUESTED_BACKGROUND,
        },
        embed_text=False,
        estimated_cost_usd=None,
    )


def _body_mismatch(body: dict[str, Any], auth: dict[str, Any]) -> str | None:
    if prompt_sha256(str(body.get("prompt") or "")) != auth.get("prompt_sha256"):
        return "prompt hash changed between authorization and body"
    if prompt_sha256(str(body.get("prompt") or "")) != EXPECTED_PROMPT_SHA256:
        return "prompt hash is not the revised spiritual prompt"
    if body.get("prompt") != PROMPT:
        return "submission prompt is not the revised spiritual prompt"
    if body.get("model") != "gpt-image-2":
        return "model_mismatch"
    if body.get("size") != "1024x1536":
        return "resolution_mismatch"
    if body.get("quality") != "medium":
        return "quality_mismatch"
    if body.get("output_format") != "png":
        return "format_mismatch"
    if body.get("n") != 1:
        return "image_count_mismatch"
    if auth.get("authorization_id") == OLD_AUTHORIZATION_ID:
        return "old authorization reused"
    if auth.get("purpose") != PURPOSE:
        return "purpose_mismatch"
    return None


def _provider(auth: dict[str, Any], ledger: Path, transport: Any, env: Any) -> OpenAIImageProvider:
    return OpenAIImageProvider(
        transport=transport,
        authorization=auth,
        ledger_path=ledger,
        env=env,
        dry_run=False,
        phase_lock=False,
        allow_mock_submission=True,
        experimental_submission_enabled=True,
    )


def _persist(ledger: Path, auth: dict[str, Any]) -> str | None:
    from app.cover.image_providers.budget_policy import persist_authorization

    if auth.get("authorization_id") == OLD_AUTHORIZATION_ID:
        return "refusing to persist the consumed authorization id"
    try:
        persist_authorization(ReservationLedger(ledger), auth, allow_effective=True)
    except (PaidCallRefused, Exception) as exc:
        return scrub_text(type(exc).__name__ + ": " + str(exc))
    return None


def _cancel_if_possible(ledger: Path, authorization_id: str) -> None:
    if authorization_id == OLD_AUTHORIZATION_ID:
        return
    try:
        cancel_authorization(ReservationLedger(ledger), authorization_id)
    except PaidCallRefused:
        return


def _consumption_test(auth: dict[str, Any], ledger: Path, destination: str) -> dict[str, Any]:
    if _auth_status(ledger, auth.get("authorization_id")) == "AUTHORIZED":
        _cancel_if_possible(ledger, str(auth.get("authorization_id")))
    before = ledger.read_bytes() if ledger.exists() else b""
    transport_module.LIVE_HTTP_ENABLED = False

    class _Refuse:
        def __init__(self) -> None:
            self.calls = 0

        def exchange(self, request: TransportRequest) -> TransportResponse:
            self.calls += 1
            raise RuntimeError("consumption test refuses every exchange")

    mock = _Refuse()
    provider = _provider(auth, ledger, mock, {"OPENAI_API_KEY": "consumption-test-not-a-real-key"})
    refused = False
    reasons: list[str] = []
    try:
        provider.generate(_request(destination))
    except PaidCallRefused as exc:
        refused = True
        reasons = [scrub_text(str(item)) for item in exc.reasons]
    except Exception as exc:
        reasons = [scrub_text(type(exc).__name__)]
    after = ledger.read_bytes() if ledger.exists() else b""
    status = _auth_status(ledger, auth.get("authorization_id"))
    return {
        "performed": True,
        "method": "offline_mock",
        "openai_contacted": False,
        "live_http_enabled": transport_module.LIVE_HTTP_ENABLED,
        "second_generate_refused": refused and mock.calls == 0,
        "mock_exchange_count": mock.calls,
        "reasons": reasons,
        "authorization_status": status,
        "reusable": False if refused and mock.calls == 0 else True,
        "ledger_unchanged": before == after,
        "old_authorization_reused": False,
    }


def _auth_row(ledger: Path, authorization_id: str | None) -> dict[str, Any] | None:
    if not authorization_id or not ledger.exists():
        return None
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    for row in payload.get("authorizations") or []:
        if row.get("authorization_id") == authorization_id:
            return row
    return None


def _auth_status(ledger: Path, authorization_id: str | None) -> str | None:
    row = _auth_row(ledger, authorization_id)
    if row is None:
        return None
    return str(row.get("status") or "")


def _classify_cost(outcome: dict[str, Any]) -> None:
    outcome["estimated_cost_usd"] = None
    outcome["observed_cost_usd"] = None
    outcome["verified_maximum_cost_usd"] = None
    outcome["documented_image_output_estimate_usd"] = EXPECTED_IMAGE_OUTPUT_CELL_USD
    if not outcome.get("submission_started"):
        outcome["cost_reconciliation"] = "NOT_SUBMITTED"
    else:
        outcome["cost_reconciliation"] = COST_RECONCILIATION_PENDING
    outcome["billing_known"] = False


def _authorization_document(outcome: dict[str, Any], row: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "record": row,
        "authorization_id": outcome.get("authorization_id"),
        "authorization_status": outcome.get("authorization_status") or (row or {}).get("status"),
        "new_authorization": outcome.get("new_authorization"),
        "old_authorization_id": OLD_AUTHORIZATION_ID,
        "old_authorization_reused": "NO",
        "previous_authorization_reactivated": False,
        "user_authorization": outcome.get("user_authorization"),
        "statement_recorded": bool((row or {}).get("user_authorization_statement")),
        "explicit_user_approval": (row or {}).get("explicit_user_approval"),
        "accepts_unbounded_provider_cost": (row or {}).get("accepts_unbounded_provider_cost"),
        "purpose": (row or {}).get("purpose"),
        "prompt_sha256": (row or {}).get("prompt_sha256"),
        "api_key_recorded": False,
    }


def _prompt_hash_document(outcome: dict[str, Any], row: dict[str, Any] | None) -> dict[str, Any]:
    digest = prompt_sha256(PROMPT)
    authorized = (row or {}).get("prompt_sha256")
    return {
        "prompt_sha256": digest,
        "previous_prompt_sha256": OLD_PROMPT_SHA256,
        "previous_prompt_reused": False,
        "authorization_prompt_sha256": authorized,
        "matches_authorization": authorized in (None, digest),
        "matches_prepared_prompt": digest == EXPECTED_PROMPT_SHA256,
    }


def _submission_document(outcome: dict[str, Any]) -> dict[str, Any]:
    trace = dict(outcome.get("transport_trace") or {})
    summary = dict(trace.get("response_summary") or {})
    return {
        "sent": bool(outcome.get("submission_started")),
        "body": outcome.get("submission_body"),
        "prompt_sha256": prompt_sha256(PROMPT),
        "previous_prompt_sha256": OLD_PROMPT_SHA256,
        "previous_prompt_reused": False,
        "model_snapshot_recorded": SNAPSHOT_MODEL_ID,
        "model_snapshot_sent": False,
        "submitted_at": outcome.get("submitted_at"),
        "started_at": outcome.get("submission_started_at"),
        "completed_at": outcome.get("completion_at"),
        "http_status": outcome.get("http_status"),
        "provider_request_id": outcome.get("provider_request_id"),
        "socket_opened": outcome.get("socket_opened"),
        "http_request_sent": outcome.get("http_request_sent"),
        "openai_http_response_received": outcome.get("openai_http_response_received"),
        "exchange_count": trace.get("exchange_count") if "exchange_count" in trace else outcome.get("real_provider_calls"),
        "response_summary": summary,
        "automatic_retry": False,
        "automatic_fallback": False,
        "fallback_provider": None,
    }


def _generation_document(outcome: dict[str, Any]) -> dict[str, Any]:
    inspection = outcome.get("image_inspection") or {}
    return {
        "provider": "openai",
        "model": OFFICIAL_MODEL_ID,
        "model_snapshot": SNAPSHOT_MODEL_ID,
        "project": PROJECT_NAME,
        "book": BOOK_TITLE,
        "purpose": PURPOSE,
        "art_direction": ART_DIRECTION,
        "interpretation": "spiritual_metaphor",
        "prompt_sha256": prompt_sha256(PROMPT),
        "resolution_requested": "1024x1536",
        "resolution_received": outcome.get("resolution_received"),
        "quality": "medium",
        "format": "png",
        "image_count_requested": 1,
        "image_count_received": outcome.get("image_count_received"),
        "authorization_id": outcome.get("authorization_id"),
        "authorization_status": outcome.get("authorization_status"),
        "old_authorization_reused": "NO",
        "submission_timestamp": outcome.get("submitted_at") or outcome.get("submission_started_at"),
        "completion_timestamp": outcome.get("completion_at"),
        "image_sha256": outcome.get("image_sha256"),
        "image_path": outcome.get("image_path"),
        "color_mode": inspection.get("color_mode"),
        "alpha": inspection.get("alpha"),
        "bytes": inspection.get("bytes"),
        "metadata": inspection.get("metadata"),
        "estimated_cost_usd": None,
        "observed_cost_usd": None,
        "verified_maximum_cost_usd": None,
        "documented_image_output_estimate_usd": EXPECTED_IMAGE_OUTPUT_CELL_USD,
        "documented_estimate_is_invoice": False,
        "documented_estimate_is_provider_ceiling": False,
        "planning_budget_usd": PLANNING_BUDGET_USD,
        "planning_budget_is_provider_cap": False,
        "cost_reconciliation_status": outcome.get("cost_reconciliation"),
        "provider_request_id": outcome.get("provider_request_id"),
        "http_status": outcome.get("http_status"),
        "final_generation_status": outcome.get("result"),
        "technical_validation": outcome.get("technical_image_validation"),
        "human_visual_review": outcome.get("human_visual_review"),
        "output_dimension_status": outcome.get("output_dimension_status"),
        "provider_result": outcome.get("generation_result"),
        "exception_type": outcome.get("exception_type"),
        "exception_status": outcome.get("exception_status"),
        "automatic_retry": False,
        "automatic_fallback": False,
    }


def _public_generation(result: dict[str, Any]) -> dict[str, Any]:
    hidden = {"api_key", "authorization", "Authorization", "bearer", "secret", "token"}
    return {key: value for key, value in result.items() if key not in hidden and "api_key" not in key.lower()}


def _cost_document(outcome: dict[str, Any]) -> dict[str, Any]:
    summary = (outcome.get("transport_trace") or {}).get("response_summary") or {}
    return {
        "estimated_cost_usd": None,
        "observed_cost_usd": None,
        "verified_maximum_cost_usd": None,
        "documented_image_output_estimate_usd": EXPECTED_IMAGE_OUTPUT_CELL_USD,
        "documented_estimate_is_invoice": False,
        "documented_estimate_is_provider_ceiling": False,
        "documented_estimate_is_total_request_cost": False,
        "planning_budget_usd": PLANNING_BUDGET_USD,
        "planning_budget_is_provider_cap": False,
        "cost_reconciliation_status": outcome.get("cost_reconciliation"),
        "billing_known": False,
        "usage_token_counts": summary.get("usage"),
        "usage_is_an_invoice": False,
        "note": (
            "0.041 USD is the published image-output cell for medium 1024x1536. "
            "Text input tokens are not included. No invoice amount was invented. "
            "0.10 USD is an internal planning budget, not an OpenAI billing cap."
        ),
    }


def _hash_document(outcome: dict[str, Any]) -> dict[str, Any]:
    return {
        "match": outcome.get("canonical_hashes") == "MATCH",
        "canonical_hashes": outcome.get("canonical_hashes"),
        "expected_book_sha256": EXPECTED_BOOK_SHA256,
        "pre": (outcome.get("hashes") or {}).get("pre"),
        "post": (outcome.get("hashes") or {}).get("post"),
        "previous_ledger_unchanged": outcome.get("previous_ledger_unchanged"),
        "previous_ledger_pre": outcome.get("previous_ledger_pre"),
        "previous_ledger_post": outcome.get("previous_ledger_post"),
    }


def _readiness(outcome: dict[str, Any]) -> dict[str, Any]:
    return {
        "phase": PHASE,
        "result": outcome.get("result"),
        "real_provider_calls": outcome.get("real_provider_calls"),
        "provider": "OpenAI",
        "model": "gpt-image-2",
        "art_direction": ART_DIRECTION,
        "policy": "EXPERIMENTAL_AUTHORIZED",
        "new_authorization": outcome.get("new_authorization"),
        "old_authorization_reused": "NO",
        "authorization_use": outcome.get("authorization_use"),
        "image_count_requested": 1,
        "image_count_received": outcome.get("image_count_received"),
        "resolution_requested": "1024x1536",
        "resolution_received": outcome.get("resolution_received"),
        "quality": "medium",
        "format": "PNG",
        "image_sha256": outcome.get("image_sha256"),
        "image_path": outcome.get("image_path"),
        "estimated_cost_usd": None,
        "observed_cost_usd": None,
        "verified_maximum_cost_usd": None,
        "documented_image_output_estimate_usd": EXPECTED_IMAGE_OUTPUT_CELL_USD,
        "cost_reconciliation": outcome.get("cost_reconciliation"),
        "automatic_retries": 0,
        "fallback_calls": 0,
        "second_paid_call": "NO",
        "technical_image_validation": outcome.get("technical_image_validation"),
        "human_visual_review": outcome.get("human_visual_review"),
        "front_cover_generated": "NO",
        "back_cover_generated": "NO",
        "cover_docx_generated": "NO",
        "cover_pdf_generated": "NO",
        "canonical_hashes": outcome.get("canonical_hashes"),
        "next_step": outcome.get("next_step"),
        "experimental_submission_module_constant": EXPERIMENTAL_SUBMISSION_ENABLED,
        "live_http_enabled_after": transport_module.LIVE_HTTP_ENABLED,
        "global_paid_calls_authorized": PAID_CALLS_AUTHORIZED,
    }


def _resolution(inspection: dict[str, Any]) -> str | None:
    if inspection.get("width") and inspection.get("height"):
        return f"{inspection['width']}x{inspection['height']}"
    return None


def _ledger_fingerprint(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "exists": False, "sha256": None}
    payload = path.read_bytes()
    return {
        "path": str(path),
        "exists": True,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
    }


def _png(width: int, height: int) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + (b"\x10\x20\x30" * width)
    raw = row * height
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 1)) + chunk(b"IEND", b"")


__all__ = ["main"]
