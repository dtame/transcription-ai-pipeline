"""Two-level cover-image budget policy.

STRICT is the default and still requires a verified provider maximum.
EXPERIMENTAL_AUTHORIZED can waive only that ceiling, and only after a
one-time explicit approval. This module does not call a provider, does not
enable experimental submission, and does not create an effective grant.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable
from uuid import uuid4

from app.cover.image_providers.bfl_budget import ReservationLedger, usd_to_cents
from app.cover.image_providers.openai_art import PROMPT, prompt_record
from app.cover.image_providers.openai_spec import (
    OFFICIAL_MODEL_ID,
    PROVIDER_ID,
    REQUESTED_OUTPUT_FORMAT,
    REQUESTED_QUALITY,
    SELECTED_HEIGHT,
    SELECTED_WIDTH,
    published_image_output_estimate_usd,
    size_label,
)

POLICY_STRICT = "STRICT"
POLICY_EXPERIMENTAL = "EXPERIMENTAL_AUTHORIZED"
DEFAULT_POLICY_MODE = POLICY_STRICT
EXPERIMENTAL_SUBMISSION_ENABLED = False

STATUS_NOT_AUTHORIZED = "NOT_AUTHORIZED"
STATUS_AUTHORIZED = "AUTHORIZED"
STATUS_RESERVED = "RESERVED"
STATUS_SUBMITTED = "SUBMITTED"
STATUS_SUCCEEDED = "SUCCEEDED"
STATUS_FAILED = "FAILED"
STATUS_OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
STATUS_EXPIRED = "EXPIRED"
STATUS_CANCELLED = "CANCELLED"
AUTHORIZATION_STATUSES = (
    STATUS_NOT_AUTHORIZED,
    STATUS_AUTHORIZED,
    STATUS_RESERVED,
    STATUS_SUBMITTED,
    STATUS_SUCCEEDED,
    STATUS_FAILED,
    STATUS_OUTCOME_UNKNOWN,
    STATUS_EXPIRED,
    STATUS_CANCELLED,
)
TERMINAL_STATUSES = (
    STATUS_SUCCEEDED,
    STATUS_FAILED,
    STATUS_OUTCOME_UNKNOWN,
    STATUS_EXPIRED,
    STATUS_CANCELLED,
)
COST_RECONCILIATION_PENDING = "COST_RECONCILIATION_PENDING"
EXPLICIT_DECISION = "APPROVE_BILLING_UNCERTAINTY"
PROJECT_ID = "pastoral_retreat_v2_validation"
PURPOSE_FIRST_IMAGE = "FIRST_COVER_IMAGE_TEST"
PLANNED_IMAGE_RELATIVE = (
    "audit/cover_generator_budget_policy_4b2343/"
    "planned_first_image/door_already_open.png"
)
WAIVED_WHEN_EXPERIMENTAL_GATE_PASSES = frozenset(
    {"billing_ceiling_not_guaranteed", "estimated_cost_unknown"}
)

DISCLOSURE_STATEMENTS = (
    "Le fournisseur nommé dans cette autorisation est le seul qui pourra être contacté.",
    "Le modèle nommé est le seul modèle qui pourra être demandé.",
    "Le nombre d'images est fixé et ne peut pas être augmenté.",
    "La résolution est fixée.",
    "La qualité est fixée.",
    "Le format de sortie est fixé.",
    "Le coût affiché est une estimation documentée. Ce n'est pas une facture.",
    "Le budget de planification contrôle seulement l'application. Ce n'est pas un plafond garanti par le fournisseur.",
    "Des frais peuvent être absents de l'estimation, notamment les jetons de texte en entrée.",
    "Le fournisseur ne garantit pas un plafond exact pour cette requête.",
    "La facture réelle peut dépasser l'estimation et le budget de planification.",
    "Aucun nouvel essai automatique ne sera effectué, y compris après un délai dépassé ou une réponse ambiguë.",
    "Aucun repli automatique vers un autre fournisseur ne sera effectué.",
    "Le fichier généré serait écrit uniquement à la destination nommée.",
    "Une approbation antérieure ne vaut pas pour une nouvelle génération.",
    "La présence d'une clé API n'est pas une autorisation.",
    "Choisir le mode expérimental dans une configuration ne suffit pas.",
)


class PolicyError(RuntimeError):
    """A budget-policy operation was refused before any provider call."""


class ApprovalRefused(PolicyError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def policy_mode_of(authorization: dict[str, Any] | None) -> str:
    raw = (authorization or {}).get("policy_mode")
    if raw in (None, "", POLICY_STRICT):
        return POLICY_STRICT
    return str(raw)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _money(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str, Decimal)):
        return None
    try:
        parsed = Decimal(str(value))
    except Exception:
        return None
    if not parsed.is_finite():
        return None
    return parsed


def _aware(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def prompt_sha256(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def prepared_prompt_sha256_values() -> frozenset[str]:
    """Hashes prepared before approval. Any other text is still refused.

    The original pictorial prompt remains prepared. The spiritual revision is a
    second prepared text for one later authorization. It does not replace the
    original, and it does not accept an arbitrary prompt.
    """

    from app.cover_first_real_image_4b2344_r1.art import PROMPT as spiritual_prompt

    return frozenset({prompt_sha256(PROMPT), prompt_sha256(spiritual_prompt)})


def documented_cost_components(
    *,
    width_px: int = SELECTED_WIDTH,
    height_px: int = SELECTED_HEIGHT,
    quality: str = REQUESTED_QUALITY,
    reference_images: int = 0,
) -> dict[str, Any]:
    """Separate the published image-output cell from the unknown remainder."""

    image_output = published_image_output_estimate_usd(width_px, height_px, quality)
    unknown = ["text_input_tokens"]
    if image_output is None:
        unknown.insert(0, "image_output")
    image_input_status = "NO_REFERENCE_IMAGES" if reference_images == 0 else "UNKNOWN"
    if reference_images:
        unknown.append("image_input")
    return {
        "image_output_usd": image_output,
        "image_output_is_total_request_cost": False,
        "image_output_is_provider_ceiling": False,
        "image_output_is_invoice": False,
        "text_input_usd": None,
        "text_input_status": "UNKNOWN",
        "image_input_usd": "0" if reference_images == 0 else None,
        "image_input_status": image_input_status,
        "estimated_cost_usd": None,
        "observed_cost_usd": None,
        "verified_maximum_cost_usd": None,
        "unknown_components": unknown,
        "currency": "USD",
        "source": "published_image_guide_cell_plus_unknown_text_tokens",
    }


def inactive_authorization_template() -> dict[str, Any]:
    """A schema example. Every approval field stays negative or empty."""

    components = documented_cost_components()
    return {
        "authorization_id": None,
        "policy_mode": POLICY_EXPERIMENTAL,
        "provider_id": PROVIDER_ID,
        "model_name": OFFICIAL_MODEL_ID,
        "project_id": PROJECT_ID,
        "purpose": PURPOSE_FIRST_IMAGE,
        "image_count": 1,
        "resolution": size_label(SELECTED_WIDTH, SELECTED_HEIGHT),
        "quality": REQUESTED_QUALITY,
        "output_format": REQUESTED_OUTPUT_FORMAT,
        "prompt_sha256": prompt_record()["prompt_sha256"],
        "prompt_text_changed": False,
        "estimated_cost_usd": None,
        "documented_image_output_estimate_usd": components["image_output_usd"],
        "documented_estimate_is_invoice": False,
        "documented_estimate_is_provider_ceiling": False,
        "unknown_cost_components": list(components["unknown_components"]),
        "planning_budget_usd": None,
        "max_budget_usd": None,
        "max_total_cost_usd": None,
        "max_images": 1,
        "local_budget_is_a_provider_cap": False,
        "verified_maximum_cost_usd": None,
        "observed_cost_usd": None,
        "cost_reconciliation_status": None,
        "accepts_unbounded_provider_cost": False,
        "explicit": False,
        "explicit_user_approval": False,
        "explicit_decision": None,
        "approval_bound_to_authorization_id": None,
        "consent_disclosure_sha256": None,
        "automatic_retry": False,
        "automatic_fallback": False,
        "fallback_provider": None,
        "dry_run": True,
        "enabled": False,
        "allow_paid_calls": False,
        "network_calls_allowed": False,
        "status": STATUS_NOT_AUTHORIZED,
        "created_at": None,
        "expires_at": None,
        "approved_at": None,
        "reserved_at": None,
        "submitted_at": None,
        "consumed_at": None,
        "destination": PLANNED_IMAGE_RELATIVE,
        "experimental_submission_enabled": False,
        "effective": False,
        "prior_phase_unspent_budget_usd": None,
        "scope": "COVER_BUDGET_POLICY_4B2343_OFFLINE_ONLY",
    }


def disclosure_document(authorization: dict[str, Any]) -> dict[str, Any]:
    components = documented_cost_components(
        width_px=_width(authorization),
        height_px=_height(authorization),
        quality=str(authorization.get("quality") or ""),
    )
    return {
        "provider_id": authorization.get("provider_id"),
        "model_name": authorization.get("model_name"),
        "image_count": authorization.get("image_count"),
        "resolution": authorization.get("resolution"),
        "quality": authorization.get("quality"),
        "output_format": authorization.get("output_format"),
        "prompt_sha256": authorization.get("prompt_sha256"),
        "estimated_cost_usd": None,
        "documented_image_output_estimate_usd": authorization.get(
            "documented_image_output_estimate_usd"
        ),
        "documented_estimate_is_invoice": False,
        "documented_estimate_is_provider_ceiling": False,
        "unknown_cost_components": components["unknown_components"],
        "planning_budget_usd": _plain_money(authorization.get("planning_budget_usd")),
        "planning_budget_is_provider_cap": False,
        "verified_maximum_cost_usd": None,
        "automatic_retry": False,
        "automatic_fallback": False,
        "destination": authorization.get("destination"),
        "expires_at": authorization.get("expires_at"),
        "statements": list(DISCLOSURE_STATEMENTS),
    }


def disclosure_sha256(authorization: dict[str, Any]) -> str:
    encoded = json.dumps(
        disclosure_document(authorization),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def consent_disclosure_markdown(authorization: dict[str, Any] | None = None) -> str:
    auth = authorization or inactive_authorization_template()
    document = disclosure_document(auth)
    lines = [
        "# Consentement — génération d'image expérimentale",
        "",
        "Cette fiche décrit une génération qui n'est pas encore autorisée.",
        "Choisir le mode expérimental ne constitue pas une acceptation.",
        "La présence d'une clé API ne constitue pas une autorisation.",
        "Une approbation antérieure ne peut pas être réutilisée.",
        "",
        f"- Fournisseur : {document['provider_id']}",
        f"- Modèle : {document['model_name']}",
        f"- Nombre d'images : {document['image_count']}",
        f"- Résolution : {document['resolution']}",
        f"- Qualité : {document['quality']}",
        f"- Format : {document['output_format']}",
        f"- Hash du prompt : {document['prompt_sha256']}",
        "- Coût estimé de la requête complète : inconnu",
        (
            "- Composante documentée de sortie image : "
            f"{document['documented_image_output_estimate_usd']} USD"
        ),
        "- Cette composante n'est pas une facture et n'est pas un plafond fournisseur.",
        "- Composante inconnue : jetons de texte en entrée.",
        f"- Budget de planification : {document['planning_budget_usd']}",
        "- Le budget de planification ne garantit pas la facture du fournisseur.",
        "- Le fournisseur ne garantit pas un plafond exact.",
        "- La facture réelle peut dépasser l'estimation.",
        "- Aucun nouvel essai automatique.",
        "- Aucun repli automatique vers un autre fournisseur.",
        f"- Destination prévue : {document['destination']}",
        "",
        "Le texte suivant doit être accepté explicitement :",
        "",
    ]
    for statement in document["statements"]:
        lines.append(f"- {statement}")
    lines.extend(
        [
            "",
            "Décision requise, inchangée : `APPROVE_BILLING_UNCERTAINTY`.",
            "Sans cette décision, le statut reste `NOT_AUTHORIZED`.",
            "",
        ]
    )
    return "\n".join(lines)


def apply_explicit_approval(
    authorization: dict[str, Any],
    *,
    decision: str,
    disable_dry_run: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Bind one approval to one authorization id. Does not contact a provider."""

    if decision != EXPLICIT_DECISION:
        raise ApprovalRefused("explicit_decision_mismatch")
    if disable_dry_run is not True:
        raise ApprovalRefused("dry_run_disable_not_explicit")
    auth = deepcopy(authorization)
    _reject_secret_fields(auth)
    problems = _approval_prerequisites(auth, now or utc_now())
    if problems:
        raise ApprovalRefused(problems[0])
    moment = now or utc_now()
    auth["explicit_decision"] = EXPLICIT_DECISION
    auth["explicit"] = True
    auth["explicit_user_approval"] = True
    auth["accepts_unbounded_provider_cost"] = True
    auth["approval_bound_to_authorization_id"] = auth["authorization_id"]
    auth["consent_disclosure_sha256"] = disclosure_sha256(auth)
    auth["status"] = STATUS_AUTHORIZED
    auth["enabled"] = True
    auth["allow_paid_calls"] = True
    auth["network_calls_allowed"] = True
    auth["dry_run"] = False
    auth["effective"] = True
    auth["approved_at"] = moment.astimezone(timezone.utc).isoformat()
    auth["created_at"] = auth.get("created_at") or auth["approved_at"]
    auth["experimental_submission_enabled"] = False
    return auth


def persist_authorization(
    ledger: ReservationLedger,
    authorization: dict[str, Any],
    *,
    allow_effective: bool = False,
) -> dict[str, Any]:
    record = deepcopy(authorization)
    _reject_secret_fields(record)
    if record.get("status") == STATUS_AUTHORIZED and allow_effective is not True:
        raise PolicyError("refusing to persist an effective authorization")
    if record.get("effective") is True and allow_effective is not True:
        raise PolicyError("refusing to persist an effective authorization")

    def mutate(state: dict[str, Any]) -> dict[str, Any]:
        rows = state["authorizations"]
        if any(row.get("authorization_id") == record.get("authorization_id") for row in rows):
            return {"write": False, "error": ["authorization_id_already_persisted"]}
        rows.append(record)
        return {"write": True, "result": deepcopy(record)}

    return ledger.mutate(mutate)


def cancel_authorization(ledger: ReservationLedger, authorization_id: str) -> dict[str, Any]:
    def mutate(state: dict[str, Any]) -> dict[str, Any]:
        row = _find(state, authorization_id)
        if row is None:
            return {"write": False, "error": ["authorization_not_persisted"]}
        if row.get("status") not in {STATUS_NOT_AUTHORIZED, STATUS_AUTHORIZED}:
            return {"write": False, "error": ["authorization_not_cancellable"]}
        row["status"] = STATUS_CANCELLED
        row["consumed_at"] = utc_now().isoformat()
        row["effective"] = False
        return {"write": True, "result": deepcopy(row)}

    return ledger.mutate(mutate)


def reserve_experimental(
    ledger: ReservationLedger,
    authorization: dict[str, Any],
    request: Any,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Atomically move AUTHORIZED to RESERVED and hold the planning budget."""

    moment = now or utc_now()
    hold = _money(authorization.get("planning_budget_usd"))
    if hold is None:
        from app.cover.image_providers.policy import PaidCallRefused

        raise PaidCallRefused(["planning_budget_missing"])

    def mutate(state: dict[str, Any]) -> dict[str, Any]:
        row = _find(state, authorization.get("authorization_id"))
        if row is None:
            return {"write": False, "error": ["authorization_not_persisted"]}
        expired = _expire_row(row, moment)
        if expired:
            return {"write": True, "error": ["authorization_expired"], "result": deepcopy(row)}
        problems = experimental_block_reasons(
            authorization=authorization,
            request=request,
            persisted=row,
            now=moment,
        )
        if problems:
            return {"write": False, "error": problems}
        if row.get("status") != STATUS_AUTHORIZED:
            return {"write": False, "error": [_status_reason(str(row.get("status")))]}
        incoming = usd_to_cents(float(hold))
        current = _reservation_summary(state)
        max_images = int(authorization.get("max_images") or 0)
        if current["images_reserved"] or current["images_reserved"] + 1 > max_images:
            return {"write": False, "error": ["authorization_already_consumed"]}
        budget = _money(authorization.get("max_budget_usd"))
        if budget is None or current["reserved_cents"] + incoming > usd_to_cents(float(budget)):
            return {"write": False, "error": ["budget_exhausted"]}
        reservation = {
            "reservation_id": uuid4().hex,
            "authorization_id": row["authorization_id"],
            "status": "reserved",
            "image_count": 1,
            "reserved_cents": incoming,
            "hold_kind": "planning_budget",
            "hold_is_provider_ceiling": False,
            "documented_image_output_estimate_usd": row.get(
                "documented_image_output_estimate_usd"
            ),
            "estimated_cost_usd": None,
            "observed_cost_usd": None,
            "verified_maximum_cost_usd": None,
            "task_id": None,
            "retry_count": 0,
            "automatic_retry": False,
            "automatic_fallback": False,
        }
        state["reservations"].append(reservation)
        row["status"] = STATUS_RESERVED
        row["reserved_at"] = moment.isoformat()
        row["consumed_at"] = moment.isoformat()
        row["effective"] = False
        row["reservation_id"] = reservation["reservation_id"]
        return {"write": True, "result": deepcopy(reservation)}

    return ledger.mutate(mutate)


def record_submission_intent(
    ledger: ReservationLedger,
    authorization_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Record the single billable attempt before any network call."""

    moment = now or utc_now()

    def mutate(state: dict[str, Any]) -> dict[str, Any]:
        row = _find(state, authorization_id)
        if row is None:
            return {"write": False, "error": ["authorization_not_persisted"]}
        if row.get("status") != STATUS_RESERVED:
            return {"write": False, "error": [_status_reason(str(row.get("status")))]}
        if int(row.get("submission_count") or 0) != 0:
            return {"write": False, "error": ["submission_already_recorded"]}
        row["status"] = STATUS_SUBMITTED
        row["submitted_at"] = moment.isoformat()
        row["submission_count"] = 1
        row["automatic_retry"] = False
        row["automatic_fallback"] = False
        reservation_id = row.get("reservation_id")
        for reservation in state["reservations"]:
            if reservation.get("reservation_id") == reservation_id:
                reservation["status"] = "submitted"
                reservation["retry_count"] = 0
                reservation["automatic_retry"] = False
        return {"write": True, "result": deepcopy(row)}

    return ledger.mutate(mutate)


def finish_authorization(
    ledger: ReservationLedger,
    authorization_id: str,
    status: str,
    **fields: Any,
) -> dict[str, Any]:
    if status not in {STATUS_SUCCEEDED, STATUS_FAILED, STATUS_OUTCOME_UNKNOWN}:
        raise PolicyError("unsupported authorization outcome")
    _reject_secret_fields(fields)

    def mutate(state: dict[str, Any]) -> dict[str, Any]:
        row = _find(state, authorization_id)
        if row is None:
            return {"write": False, "error": ["authorization_not_persisted"]}
        if row.get("status") != STATUS_SUBMITTED:
            return {"write": False, "error": ["submission_intent_missing"]}
        row["status"] = status
        row["effective"] = False
        row["automatic_retry"] = False
        row["automatic_fallback"] = False
        row.update(fields)
        return {"write": True, "result": deepcopy(row)}

    return ledger.mutate(mutate)


def experimental_block_reasons(
    *,
    authorization: dict[str, Any] | None,
    request: Any,
    persisted: dict[str, Any] | None,
    now: datetime | None = None,
) -> list[str]:
    """Extra locks for the experimental ceiling exception. Empty means the exception may be considered."""

    auth = authorization or {}
    moment = now or utc_now()
    reasons: list[str] = []
    if policy_mode_of(auth) != POLICY_EXPERIMENTAL:
        reasons.append("experimental_mode_not_selected")
    if auth.get("explicit_user_approval") is not True:
        reasons.append("explicit_user_approval_missing")
    if auth.get("explicit_decision") != EXPLICIT_DECISION:
        reasons.append("explicit_decision_missing")
    if auth.get("accepts_unbounded_provider_cost") is not True:
        reasons.append("billing_uncertainty_not_accepted")
    if not auth.get("authorization_id"):
        reasons.append("authorization_id_missing")
    elif auth.get("approval_bound_to_authorization_id") != auth.get("authorization_id"):
        reasons.append("approval_not_bound_to_this_authorization")
    expected_hash = disclosure_sha256(auth) if auth.get("authorization_id") else None
    if not auth.get("consent_disclosure_sha256") or auth.get("consent_disclosure_sha256") != expected_hash:
        reasons.append("consent_disclosure_not_acknowledged")
    if persisted is None:
        reasons.append("authorization_not_persisted")
    else:
        if persisted.get("authorization_id") != auth.get("authorization_id"):
            reasons.append("persisted_authorization_mismatch")
        status = str(persisted.get("status") or "")
        if status == STATUS_EXPIRED or _is_expired(persisted, moment):
            reasons.append("authorization_expired")
        elif status == STATUS_CANCELLED:
            reasons.append("authorization_cancelled")
        elif status == STATUS_RESERVED:
            reasons.append("authorization_already_reserved")
        elif status == STATUS_SUBMITTED:
            reasons.append("authorization_already_submitted")
        elif status == STATUS_OUTCOME_UNKNOWN:
            reasons.append("authorization_outcome_unknown")
        elif status in TERMINAL_STATUSES or persisted.get("consumed_at"):
            reasons.append("authorization_already_consumed")
        elif status != STATUS_AUTHORIZED:
            reasons.append("authorization_not_granted")
        if _locked_view(persisted) != _locked_view(auth):
            reasons.append("persisted_parameters_mismatch")
    reasons.extend(_locked_request_reasons(auth, request))
    if str(auth.get("scope") or "").endswith("OFFLINE_ONLY"):
        reasons.append("offline_scope_is_not_a_paid_authorization")
    if auth.get("dry_run") is not False:
        reasons.append("dry_run_not_explicitly_disabled")
    if auth.get("automatic_retry") is not False:
        reasons.append("automatic_retry_not_explicitly_disabled")
    if auth.get("automatic_fallback") is not False or auth.get("fallback_provider") not in (None, ""):
        reasons.append("automatic_fallback_not_explicitly_disabled")
    if auth.get("local_budget_is_a_provider_cap") is not False:
        reasons.append("provider_cap_claim_not_explicitly_denied")
    if auth.get("verified_maximum_cost_usd") is not None:
        reasons.append("verified_maximum_must_stay_unknown")
    if auth.get("estimated_cost_usd") is not None:
        reasons.append("full_request_estimate_must_stay_unknown")
    published = published_image_output_estimate_usd(
        _width(auth), _height(auth), str(auth.get("quality") or "")
    )
    documented = auth.get("documented_image_output_estimate_usd")
    if documented in (None, ""):
        reasons.append("documented_estimate_missing")
    elif published is None or str(documented) != str(published):
        reasons.append("documented_estimate_mismatch")
    if str(documented) == "0.041" and auth.get("verified_maximum_cost_usd") not in (None,):
        reasons.append("published_cell_recorded_as_verified_maximum")
    planning = _money(auth.get("planning_budget_usd"))
    if planning is None or planning <= 0:
        reasons.append("planning_budget_missing")
    elif published is not None and planning < Decimal(published):
        reasons.append("planning_budget_below_documented_component")
    maximum = _money(auth.get("max_budget_usd"))
    if planning is not None and maximum != planning:
        reasons.append("planning_budget_mismatch")
    if not auth.get("purpose"):
        reasons.append("purpose_missing")
    if auth.get("project_id") != PROJECT_ID:
        reasons.append("project_mismatch")
    if not _aware(auth.get("expires_at")):
        reasons.append("expires_at_missing")
    elif _aware(auth.get("expires_at")) <= moment:
        reasons.append("authorization_expired")
    return list(dict.fromkeys(reasons))


def finalize_policy_reasons(
    *,
    authorization: dict[str, Any] | None,
    request: Any,
    reasons: list[str],
    persisted: dict[str, Any] | None,
    experimental_submission_enabled: bool,
    now: datetime | None = None,
) -> list[str]:
    """Keep STRICT unchanged. Waive only the ceiling pair when the experimental gate is fully open."""

    mode = policy_mode_of(authorization)
    merged = list(reasons)
    if mode == POLICY_STRICT:
        return list(dict.fromkeys(merged))
    if mode != POLICY_EXPERIMENTAL:
        merged.append("unknown_policy_mode")
        return list(dict.fromkeys(merged))
    extra = experimental_block_reasons(
        authorization=authorization,
        request=request,
        persisted=persisted,
        now=now,
    )
    merged.extend(extra)
    if extra or not experimental_submission_enabled:
        if not experimental_submission_enabled:
            merged.append("experimental_mode_disabled")
        return list(dict.fromkeys(merged))
    return [
        reason
        for reason in dict.fromkeys(merged)
        if reason not in WAIVED_WHEN_EXPERIMENTAL_GATE_PASSES
    ]


def first_experimental_image_plan() -> dict[str, Any]:
    """Inactive plan. Identifying the approved prompt is not an approval."""

    plan = inactive_authorization_template()
    plan["art_direction"] = "The Door Already Open"
    plan["book_title"] = "The Life You Already Inherited"
    plan["prompt_text_changed"] = False
    plan["prompt_sha256"] = prompt_sha256(PROMPT)
    plan["image_generated"] = False
    plan["authorized"] = False
    plan["effective"] = False
    plan["provider_calls"] = 0
    plan["paid_cost_usd"] = 0
    plan["submission_count"] = 0
    plan["automatic_retry"] = False
    plan["automatic_fallback"] = False
    return plan


def refresh_experimental_status(
    ledger: ReservationLedger,
    authorization_id: str,
    now: datetime,
) -> dict[str, Any] | None:
    """Expire an unused grant. A read of any other status does not rewrite the ledger."""

    def mutate(state: dict[str, Any]) -> dict[str, Any]:
        row = _find(state, authorization_id)
        if row is None:
            return {"write": False, "result": None}
        if _expire_row(row, now):
            return {"write": True, "result": deepcopy(row)}
        return {"write": False, "result": deepcopy(row)}

    return ledger.mutate(mutate)


def observe_provider_cost(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Record a provider cost only when the payload actually carries one.

    GPT Image responses in this adapter do not carry a verified invoice.
    Token counts, when present, stay counts. They are not converted into dollars.
    """

    usage = payload.get("usage") if isinstance(payload, dict) else None
    observed = None
    if isinstance(payload, dict):
        for key in ("observed_cost_usd", "cost_usd", "billed_usd"):
            if key in payload and payload.get(key) is not None:
                candidate = payload.get(key)
                if isinstance(candidate, (int, float, str)) and not isinstance(candidate, bool):
                    observed = candidate
                break
    return {
        "observed_cost_usd": observed,
        "usage_present": isinstance(usage, dict),
        "usage_is_an_invoice": False,
        "cost_reconciliation_status": COST_RECONCILIATION_PENDING,
    }


def redact(value: Any) -> Any:
    secret_names = {
        "api_key",
        "authorization",
        "Authorization",
        "bearer",
        "secret",
        "token",
    }
    if isinstance(value, dict):
        return {
            key: redact(item)
            for key, item in value.items()
            if key not in secret_names and "api_key" not in key.lower()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def strict_mode_contract() -> dict[str, Any]:
    return {
        "policy_mode": POLICY_STRICT,
        "default": True,
        "experimental_submission_enabled": EXPERIMENTAL_SUBMISSION_ENABLED,
        "requires_verified_maximum_cost_usd": True,
        "unknown_verified_maximum_reason": "billing_ceiling_not_guaranteed",
        "accepts_unbounded_provider_cost": False,
        "experimental_approval_flags_are_ignored": True,
        "automatic_retry": False,
        "automatic_fallback": False,
        "prior_phase_budget_is_authorization": False,
        "api_key_is_authorization": False,
    }


def experimental_mode_contract() -> dict[str, Any]:
    return {
        "policy_mode": POLICY_EXPERIMENTAL,
        "default": False,
        "experimental_submission_enabled": EXPERIMENTAL_SUBMISSION_ENABLED,
        "waives_only": sorted(WAIVED_WHEN_EXPERIMENTAL_GATE_PASSES),
        "does_not_waive": [
            "provider_match",
            "model_match",
            "resolution_match",
            "quality_match",
            "output_format_match",
            "prompt_sha256",
            "image_count",
            "explicit_user_approval",
            "billing_uncertainty_acceptance",
            "planning_budget",
            "documented_component_estimate",
            "one_time_use",
            "expiry",
            "dry_run",
            "api_key",
            "phase_lock",
            "automatic_retry",
            "automatic_fallback",
        ],
        "mode_selection_is_consent": False,
        "api_key_is_authorization": False,
        "prior_approval_is_reusable": False,
        "planning_budget_is_provider_cap": False,
        "documented_image_output_cell_usd": documented_cost_components()["image_output_usd"],
        "documented_cell_is_verified_maximum": False,
        "full_request_estimate_usd": None,
        "verified_maximum_cost_usd": None,
    }


def cost_accounting_contract() -> dict[str, Any]:
    components = documented_cost_components()
    return {
        "values_are_not_interchangeable": [
            "estimated_cost_usd",
            "observed_cost_usd",
            "verified_maximum_cost_usd",
        ],
        "estimated_cost_usd": None,
        "observed_cost_usd": None,
        "verified_maximum_cost_usd": None,
        "documented_components": components,
        "published_image_output_cell_is_verified_maximum": False,
        "published_image_output_cell_is_invoice": False,
        "missing_observed_cost": None,
        "reconciliation_status_when_bill_is_unknown": COST_RECONCILIATION_PENDING,
        "local_budget_is_a_provider_cap": False,
    }


def authorization_schema() -> dict[str, Any]:
    template = inactive_authorization_template()
    return {
        "schema": "cover-image-one-time-authorization-v1",
        "effective": False,
        "statuses": list(AUTHORIZATION_STATUSES),
        "template": template,
        "approval_fields_preset_positive": False,
    }


def _approval_prerequisites(auth: dict[str, Any], now: datetime) -> list[str]:
    reasons: list[str] = []
    if not isinstance(auth.get("authorization_id"), str) or not auth.get("authorization_id"):
        reasons.append("authorization_id_missing")
    if auth.get("status") not in (None, STATUS_NOT_AUTHORIZED, ""):
        reasons.append("approval_requires_a_new_authorization")
    if auth.get("provider_id") != PROVIDER_ID:
        reasons.append("provider_not_prepared")
    if auth.get("model_name") != OFFICIAL_MODEL_ID:
        reasons.append("model_not_prepared")
    if auth.get("image_count") != 1 or auth.get("max_images") != 1:
        reasons.append("image_count_not_prepared")
    if auth.get("resolution") != size_label(SELECTED_WIDTH, SELECTED_HEIGHT):
        reasons.append("resolution_not_prepared")
    if auth.get("quality") != REQUESTED_QUALITY:
        reasons.append("quality_not_prepared")
    if auth.get("output_format") != REQUESTED_OUTPUT_FORMAT:
        reasons.append("output_format_not_prepared")
    if auth.get("prompt_sha256") not in prepared_prompt_sha256_values():
        reasons.append("prompt_sha256_not_prepared")
    published = published_image_output_estimate_usd(SELECTED_WIDTH, SELECTED_HEIGHT, REQUESTED_QUALITY)
    if str(auth.get("documented_image_output_estimate_usd") or "") != str(published):
        reasons.append("documented_estimate_not_prepared")
    if auth.get("estimated_cost_usd") is not None or auth.get("verified_maximum_cost_usd") is not None:
        reasons.append("cost_fields_must_stay_unknown")
    planning = _money(auth.get("planning_budget_usd"))
    if planning is None or planning <= 0:
        reasons.append("planning_budget_missing")
    elif _money(auth.get("max_budget_usd")) != planning:
        reasons.append("planning_budget_mismatch")
    if auth.get("local_budget_is_a_provider_cap") is not False:
        reasons.append("provider_cap_claim_not_explicitly_denied")
    if auth.get("automatic_retry") is not False or auth.get("automatic_fallback") is not False:
        reasons.append("retry_or_fallback_not_disabled")
    if auth.get("fallback_provider") not in (None, ""):
        reasons.append("fallback_provider_not_empty")
    if auth.get("project_id") != PROJECT_ID or not auth.get("purpose"):
        reasons.append("project_or_purpose_missing")
    if not auth.get("destination"):
        reasons.append("destination_missing")
    expires = _aware(auth.get("expires_at"))
    if expires is None or expires <= now:
        reasons.append("expires_at_not_in_the_future")
    if str(auth.get("scope") or "").endswith("OFFLINE_ONLY"):
        reasons.append("offline_scope_is_not_a_paid_authorization")
    return reasons


def _locked_request_reasons(auth: dict[str, Any], request: Any) -> list[str]:
    reasons: list[str] = []
    if getattr(request, "provider_id", None) != auth.get("provider_id"):
        reasons.append("provider_mismatch")
    if getattr(request, "model_name", None) != auth.get("model_name"):
        reasons.append("model_mismatch")
    requested = size_label(int(getattr(request, "width_px", 0) or 0), int(getattr(request, "height_px", 0) or 0))
    if requested != auth.get("resolution"):
        reasons.append("resolution_mismatch")
    metadata = getattr(request, "metadata", None) or {}
    if metadata.get("quality") != auth.get("quality"):
        reasons.append("quality_mismatch")
    if metadata.get("output_format") != auth.get("output_format"):
        reasons.append("output_format_mismatch")
    if prompt_sha256(str(getattr(request, "prompt", "") or "")) != auth.get("prompt_sha256"):
        reasons.append("prompt_sha256_mismatch")
    if int(getattr(request, "image_count", 0) or 0) != int(auth.get("image_count") or 0):
        reasons.append("image_count_mismatch")
    destination = auth.get("destination")
    paths = list(getattr(request, "output_paths", None) or [])
    if destination and paths and _same_path(paths[0], destination) is False:
        reasons.append("destination_mismatch")
    return reasons


def _locked_view(auth: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider_id": auth.get("provider_id"),
        "model_name": auth.get("model_name"),
        "resolution": auth.get("resolution"),
        "quality": auth.get("quality"),
        "output_format": auth.get("output_format"),
        "prompt_sha256": auth.get("prompt_sha256"),
        "image_count": auth.get("image_count"),
        "planning_budget_usd": _plain_money(auth.get("planning_budget_usd")),
        "documented_image_output_estimate_usd": auth.get("documented_image_output_estimate_usd"),
        "destination": auth.get("destination"),
        "expires_at": auth.get("expires_at"),
        "project_id": auth.get("project_id"),
        "purpose": auth.get("purpose"),
    }


def _plain_money(value: Any) -> str | None:
    parsed = _money(value)
    if parsed is None:
        return None
    return format(parsed, "f")


def _width(auth: dict[str, Any]) -> int:
    resolution = str(auth.get("resolution") or "0x0")
    try:
        return int(resolution.split("x", 1)[0])
    except (ValueError, IndexError):
        return 0


def _height(auth: dict[str, Any]) -> int:
    resolution = str(auth.get("resolution") or "0x0")
    try:
        return int(resolution.split("x", 1)[1])
    except (ValueError, IndexError):
        return 0


def _is_expired(auth: dict[str, Any], now: datetime) -> bool:
    expires = _aware(auth.get("expires_at"))
    return expires is not None and expires <= now


def _expire_row(row: dict[str, Any], now: datetime) -> bool:
    if row.get("status") == STATUS_AUTHORIZED and _is_expired(row, now):
        row["status"] = STATUS_EXPIRED
        row["effective"] = False
        row["expired_at"] = now.isoformat()
        return True
    return False


def _status_reason(status: str) -> str:
    return {
        STATUS_RESERVED: "authorization_already_reserved",
        STATUS_SUBMITTED: "authorization_already_submitted",
        STATUS_SUCCEEDED: "authorization_already_consumed",
        STATUS_FAILED: "authorization_already_consumed",
        STATUS_OUTCOME_UNKNOWN: "authorization_outcome_unknown",
        STATUS_EXPIRED: "authorization_expired",
        STATUS_CANCELLED: "authorization_cancelled",
        STATUS_NOT_AUTHORIZED: "authorization_not_granted",
    }.get(status, "authorization_not_granted")


def _find(state: dict[str, Any], authorization_id: str | None) -> dict[str, Any] | None:
    for row in state.get("authorizations") or []:
        if row.get("authorization_id") == authorization_id:
            return row
    return None


def _reservation_summary(state: dict[str, Any]) -> dict[str, int]:
    rows = list(state.get("reservations") or [])
    return {
        "images_reserved": sum(int(row.get("image_count") or 0) for row in rows),
        "reserved_cents": sum(int(row.get("reserved_cents") or 0) for row in rows),
    }


def _same_path(left: Any, right: Any) -> bool:
    return str(left).replace("\\", "/").rstrip("/") == str(right).replace("\\", "/").rstrip("/")


def _reject_secret_fields(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if "api_key" in lowered or lowered in {"authorization", "bearer", "secret", "token"}:
                raise PolicyError("refusing to store a secret in an authorization")
            _reject_secret_fields(item)
    elif isinstance(value, list):
        for item in value:
            _reject_secret_fields(item)


def clock_or_default(clock: Callable[[], datetime] | None) -> datetime:
    moment = clock() if clock is not None else utc_now()
    if moment.tzinfo is None:
        raise PolicyError("clock must return a timezone-aware datetime")
    return moment.astimezone(timezone.utc)


__all__ = [
    "AUTHORIZATION_STATUSES",
    "COST_RECONCILIATION_PENDING",
    "DEFAULT_POLICY_MODE",
    "EXPERIMENTAL_SUBMISSION_ENABLED",
    "POLICY_EXPERIMENTAL",
    "POLICY_STRICT",
    "ApprovalRefused",
    "PolicyError",
    "apply_explicit_approval",
    "authorization_schema",
    "cancel_authorization",
    "consent_disclosure_markdown",
    "cost_accounting_contract",
    "documented_cost_components",
    "experimental_block_reasons",
    "experimental_mode_contract",
    "finalize_policy_reasons",
    "finish_authorization",
    "first_experimental_image_plan",
    "inactive_authorization_template",
    "observe_provider_cost",
    "persist_authorization",
    "policy_mode_of",
    "record_submission_intent",
    "redact",
    "refresh_experimental_status",
    "reserve_experimental",
    "strict_mode_contract",
]
