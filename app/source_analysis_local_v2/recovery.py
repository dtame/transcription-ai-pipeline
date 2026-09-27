"""
consolidation-recovery-v1 — métadonnées globales depuis FakeAI.

Python ne les invente pas. FakeAI les fournit. Ancrage SRC obligatoire.
Ne mute pas consolidation-1.0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.source_analysis.errors import HybridReconstructionError
from app.source_analysis.models import CONFIDENCE_LEVELS
from app.source_analysis.ultra_compact_schema import (
    VOICE_FIELDS,
    VOICE_LIST_FIELDS,
    VOICE_SCALAR_FIELDS,
)
from app.source_analysis.window_models import WindowIntermediateRecord
from app.source_analysis_local_v2.constants import CONSOLIDATION_RECOVERY_VERSION


class LocalV2RecoveryError(HybridReconstructionError):
    """Recovery globale invalide — fail-closed."""


@dataclass(frozen=True)
class GlobalRecoveryPayload:
    version: str
    intent_kinds: tuple[str, ...]
    audience_kinds: tuple[str, ...]
    voice_profile: Mapping[str, Any]
    intent_kind_evidence: tuple[str, ...]
    audience_kind_evidence: tuple[str, ...]
    voice_evidence: tuple[str, ...]
    intent_confidence: str | None = None
    audience_confidence: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "intent_kinds": list(self.intent_kinds),
            "audience_kinds": list(self.audience_kinds),
            "voice_profile": dict(self.voice_profile),
            "intent_kind_evidence": list(self.intent_kind_evidence),
            "audience_kind_evidence": list(self.audience_kind_evidence),
            "voice_evidence": list(self.voice_evidence),
            "intent_confidence": self.intent_confidence,
            "audience_confidence": self.audience_confidence,
        }


def parse_recovery_payload(raw: Mapping[str, Any]) -> GlobalRecoveryPayload:
    if not isinstance(raw, Mapping):
        raise LocalV2RecoveryError("recovery n'est pas un objet")
    version = str(raw.get("version") or CONSOLIDATION_RECOVERY_VERSION)
    if version != CONSOLIDATION_RECOVERY_VERSION:
        raise LocalV2RecoveryError(f"recovery version inconnue {version}")
    voice = raw.get("voice_profile")
    if not isinstance(voice, Mapping):
        raise LocalV2RecoveryError("voice_profile absent")
    return GlobalRecoveryPayload(
        version=version,
        intent_kinds=tuple(raw.get("intent_kinds") or ()),
        audience_kinds=tuple(raw.get("audience_kinds") or ()),
        voice_profile=dict(voice),
        intent_kind_evidence=tuple(raw.get("intent_kind_evidence") or ()),
        audience_kind_evidence=tuple(raw.get("audience_kind_evidence") or ()),
        voice_evidence=tuple(raw.get("voice_evidence") or ()),
        intent_confidence=raw.get("intent_confidence"),
        audience_confidence=raw.get("audience_confidence"),
    )


def _require_grounded(
    evidence_ids: Sequence[str],
    table: Mapping[str, WindowIntermediateRecord],
    *,
    label: str,
) -> None:
    if not evidence_ids:
        raise LocalV2RecoveryError(f"{label} sans évidence")
    for record_id in evidence_ids:
        record = table.get(record_id)
        if record is None:
            raise LocalV2RecoveryError(f"{label} évidence absente {record_id}")
        if record.kind in {"RELATION"}:
            raise LocalV2RecoveryError(
                f"{label} ne peut pas s'ancrer sur RELATION {record_id}"
            )
        if not record.source_refs and record.kind != "RELATION":
            if record.kind in {"TOPIC", "IDEA", "EXAMPLE", "REFERENCE", "UNCERTAINTY"}:
                raise LocalV2RecoveryError(
                    f"{label} évidence {record_id} sans SRC"
                )


def apply_recovery_to_raw(
    raw: dict[str, Any],
    recovery: GlobalRecoveryPayload,
    table: Mapping[str, WindowIntermediateRecord],
) -> dict[str, Any]:
    """
    Overlay FakeAI recovery. Python copie après validation d'ancrage.
    """
    _require_grounded(recovery.intent_kind_evidence, table, label="intent")
    _require_grounded(recovery.audience_kind_evidence, table, label="audience")
    _require_grounded(recovery.voice_evidence, table, label="voice")
    if not recovery.intent_kinds:
        raise LocalV2RecoveryError("intent_kinds vides — FakeAI doit les fournir")
    if not recovery.audience_kinds:
        raise LocalV2RecoveryError("audience_kinds vides — FakeAI doit les fournir")

    voice = {
        field: [] if field in VOICE_LIST_FIELDS else "" for field in VOICE_FIELDS
    }
    for field in VOICE_LIST_FIELDS:
        values = recovery.voice_profile.get(field) or []
        if not isinstance(values, list):
            raise LocalV2RecoveryError(f"voice.{field} n'est pas une liste")
        voice[field] = [str(item) for item in values if str(item).strip()]
    for field in VOICE_SCALAR_FIELDS:
        voice[field] = str(recovery.voice_profile.get(field) or "")
    if not any(voice[field] for field in VOICE_FIELDS):
        raise LocalV2RecoveryError("voice_profile vide — FakeAI doit le fournir")

    header = dict(raw.get("source_analysis") or {})
    intent = dict(header.get("author_intent") or {})
    audience = dict(header.get("target_audience") or {})
    intent["kinds"] = list(recovery.intent_kinds)
    audience["kinds"] = list(recovery.audience_kinds)
    if recovery.intent_confidence:
        if recovery.intent_confidence not in CONFIDENCE_LEVELS:
            raise LocalV2RecoveryError("intent_confidence invalide")
        intent["confidence"] = recovery.intent_confidence
    if recovery.audience_confidence:
        if recovery.audience_confidence not in CONFIDENCE_LEVELS:
            raise LocalV2RecoveryError("audience_confidence invalide")
        audience["confidence"] = recovery.audience_confidence
    header["author_intent"] = intent
    header["target_audience"] = audience
    out = dict(raw)
    out["source_analysis"] = header
    out["author_voice_profile"] = voice
    return out


def recovery_ownership() -> dict[str, Any]:
    return {
        "version": CONSOLIDATION_RECOVERY_VERSION,
        "python_invents_metadata": False,
        "fake_ai_must_supply": True,
        "repetition": {
            "local": False,
            "recovered_by": "global consolidation REP ops",
            "grounding": "member IDEA source_refs",
        },
        "voice": {
            "local": False,
            "recovered_by": "consolidation-recovery-v1 voice_profile",
            "grounding": "TOPIC/IDEA evidence ids with SRC",
        },
        "intent": {
            "local": False,
            "recovered_by": "consolidation-1.0 gm.in + recovery intent_kinds",
            "grounding": "TOPIC/IDEA evidence ids with SRC",
        },
        "audience": {
            "local": False,
            "recovered_by": "consolidation-1.0 gm.au + recovery audience_kinds",
            "grounding": "TOPIC/IDEA evidence ids with SRC",
        },
        "no_full_transcript_resend": True,
    }
