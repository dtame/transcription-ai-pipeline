"""
Preuve de provenance d'un transcript DERIVED.

Le droit d'avoir des trous de SRC ne vient PAS d'un drapeau `allow_gaps`.
Il vient d'une démonstration :

    clean  ==  original  −  removed_source_refs

où `removed_source_refs` est le jeu publié dans cleanup_application.json
(Phase 3A.2B). Toute autre divergence (texte, timestamps, audio, SRC inventé,
SRC réintroduit, hash incohérent) est un échec, sans repli.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.cleanup_application.constants import POLICY_B_PLUS
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.errors import SourceTranscriptProvenanceError
from app.source_analysis.transcript_input import resolve_original_transcript_path
from app.transcript_models import (
    TranscriptDocument,
    TranscriptSegment,
    TranscriptSource,
    TranscriptStats,
)
from app.transcript_validator import (
    validate_transcript_document,
)

_SURVIVOR_FIELDS = ("id", "source_id", "source_order", "start", "end", "text")


@dataclass(frozen=True)
class DerivedProvenance:
    """Résultat d'une validation DERIVED réussie."""

    original_path: Path
    provenance_path: Path
    original_sha256: str
    derived_sha256: str
    original_segment_count: int
    derived_segment_count: int
    removed_count: int
    removed_source_refs: frozenset[str]
    removed_set_matches: bool
    survivors_unchanged: bool
    policy: str
    original_transcript_id: str
    derived_transcript_id: str
    original_word_count: int
    derived_word_count: int
    duration_seconds: float

    def to_dict(self) -> dict:
        return {
            "valid": True,
            "original_segments": self.original_segment_count,
            "clean_segments": self.derived_segment_count,
            "removed_segments": self.removed_count,
            "removed_set_matches": self.removed_set_matches,
            "survivors_unchanged": self.survivors_unchanged,
            "policy": self.policy,
            "original_transcript_id": self.original_transcript_id,
            "derived_transcript_id": self.derived_transcript_id,
            "original_word_count": self.original_word_count,
            "clean_word_count": self.derived_word_count,
            "duration_seconds": self.duration_seconds,
        }


def validate_derived_provenance(
    *,
    derived_path: Path,
    provenance_path: Path,
    original_transcript_path: Path | None = None,
) -> DerivedProvenance:
    """
    Démontre que `derived_path` est exactement original − removed.

    Fail-closed : une seule incohérence lève SourceTranscriptProvenanceError.
    """
    derived_path = Path(derived_path)
    provenance_path = Path(provenance_path)

    if not provenance_path.exists():
        raise SourceTranscriptProvenanceError(
            f"Provenance introuvable : {provenance_path}. Un transcript DERIVED "
            "exige cleanup_application.json."
        )

    audit = _load_audit(provenance_path)
    policy = _require_policy(audit)
    derivation = audit.get("derivation") if isinstance(audit.get("derivation"), dict) else {}

    original_path = (
        Path(original_transcript_path)
        if original_transcript_path is not None
        else resolve_original_transcript_path(derived_path)
    )

    if not original_path.exists():
        raise SourceTranscriptProvenanceError(
            f"Transcript original de provenance introuvable : {original_path}."
        )

    original_sha = sha256_of_file(original_path)
    derived_sha = sha256_of_file(derived_path)
    _verify_hashes(audit, original_sha=original_sha, derived_sha=derived_sha)

    original = _load_document(original_path)
    derived = _load_document(derived_path)

    original_errors = validate_transcript_document(original, allow_source_id_gaps=False)
    if original_errors:
        raise SourceTranscriptProvenanceError(
            "Le transcript original de provenance viole le contrat SOURCE "
            f"(SRC continus) : {' | '.join(original_errors[:8])}"
        )

    # Structure DERIVED : trous autorisés ici uniquement parce que l'audit
    # existe, que les hashes concordent, et que le mode d'appel est DERIVED.
    derived_errors = validate_transcript_document(derived, allow_source_id_gaps=True)
    if derived_errors:
        raise SourceTranscriptProvenanceError(
            "Le transcript DERIVED viole le contrat de vue dérivée : "
            + " | ".join(derived_errors[:8])
        )

    _verify_identity(original, derived, derivation)

    removed_refs = _removed_source_refs(audit)
    original_ids = {segment.id for segment in original.segments}
    derived_ids = {segment.id for segment in derived.segments}
    missing = original_ids - derived_ids

    if derived_ids - original_ids:
        invented = sorted(derived_ids - original_ids)
        raise SourceTranscriptProvenanceError(
            f"SRC inventé(s) dans le transcript DERIVED : {invented}."
        )

    if missing != removed_refs:
        extra_missing = sorted(missing - removed_refs)
        extra_removed = sorted(removed_refs - missing)
        parts = []
        if extra_missing:
            parts.append(
                "SRC absents du clean sans être déclarés retirés : "
                + ", ".join(extra_missing[:12])
            )
        if extra_removed:
            parts.append(
                "SRC déclarés retirés encore présents (ou jamais dans l'original) : "
                + ", ".join(extra_removed[:12])
            )
        raise SourceTranscriptProvenanceError(
            "Jeu retiré incohérent avec original − clean. " + " | ".join(parts)
        )

    survivors_unchanged = _verify_survivors(original, derived)

    stats = audit.get("stats") if isinstance(audit.get("stats"), dict) else {}
    _verify_audit_counts(
        stats,
        original=original,
        derived=derived,
        removed_count=len(removed_refs),
    )

    return DerivedProvenance(
        original_path=original_path,
        provenance_path=provenance_path,
        original_sha256=original_sha,
        derived_sha256=derived_sha,
        original_segment_count=len(original.segments),
        derived_segment_count=len(derived.segments),
        removed_count=len(removed_refs),
        removed_source_refs=removed_refs,
        removed_set_matches=True,
        survivors_unchanged=survivors_unchanged,
        policy=policy,
        original_transcript_id=original.transcript_id,
        derived_transcript_id=derived.transcript_id,
        original_word_count=original.stats.word_count,
        derived_word_count=derived.stats.word_count,
        duration_seconds=float(derived.stats.duration_seconds),
    )


def _load_audit(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SourceTranscriptProvenanceError(
            f"Provenance illisible ({path}) : JSON invalide ligne {exc.lineno}."
        ) from exc

    if not isinstance(payload, dict):
        raise SourceTranscriptProvenanceError(
            f"Provenance invalide ({path}) : un objet JSON est attendu."
        )

    return payload


def _require_policy(audit: dict) -> str:
    policy_block = audit.get("policy")
    policy_id = ""

    if isinstance(policy_block, dict):
        policy_id = str(policy_block.get("policy_id") or "").strip()
    elif isinstance(policy_block, str):
        policy_id = policy_block.strip()

    derivation = audit.get("derivation") if isinstance(audit.get("derivation"), dict) else {}
    derivation_policy = str(derivation.get("policy") or "").strip()

    declared = policy_id or derivation_policy

    if declared != POLICY_B_PLUS:
        raise SourceTranscriptProvenanceError(
            f"Politique de provenance inattendue : « {declared} » "
            f"(attendu {POLICY_B_PLUS})."
        )

    if derivation_policy and derivation_policy != POLICY_B_PLUS:
        raise SourceTranscriptProvenanceError(
            f"derivation.policy incohérente : « {derivation_policy} » "
            f"(attendu {POLICY_B_PLUS})."
        )

    return POLICY_B_PLUS


def _verify_hashes(audit: dict, *, original_sha: str, derived_sha: str) -> None:
    source_hashes = audit.get("source_hashes")
    clean_hashes = audit.get("clean_hashes")

    if not isinstance(source_hashes, dict) or not source_hashes.get("transcript_data"):
        raise SourceTranscriptProvenanceError(
            "Provenance incomplète : source_hashes.transcript_data absent."
        )

    if not isinstance(clean_hashes, dict) or not clean_hashes.get(
        "clean_transcript_data_sha256"
    ):
        raise SourceTranscriptProvenanceError(
            "Provenance incomplète : clean_hashes.clean_transcript_data_sha256 absent."
        )

    expected_original = str(source_hashes["transcript_data"]).strip().lower()
    expected_clean = str(clean_hashes["clean_transcript_data_sha256"]).strip().lower()

    if expected_original != original_sha.lower():
        raise SourceTranscriptProvenanceError(
            "Hash du transcript original incohérent avec source_hashes.transcript_data."
        )

    if expected_clean != derived_sha.lower():
        raise SourceTranscriptProvenanceError(
            "Hash du transcript DERIVED incohérent avec "
            "clean_hashes.clean_transcript_data_sha256."
        )


def _verify_identity(
    original: TranscriptDocument,
    derived: TranscriptDocument,
    derivation: dict,
) -> None:
    if original.transcript_id != derived.transcript_id:
        raise SourceTranscriptProvenanceError(
            f"transcript_id incohérent : original={original.transcript_id!r} "
            f"derived={derived.transcript_id!r}."
        )

    declared = str(derivation.get("source_transcript_id") or "").strip()
    if declared and declared != original.transcript_id:
        raise SourceTranscriptProvenanceError(
            f"derivation.source_transcript_id={declared!r} ≠ "
            f"original {original.transcript_id!r}."
        )

    if original.project_name != derived.project_name:
        raise SourceTranscriptProvenanceError(
            "nom de projet derived ≠ original."
        )


def _removed_source_refs(audit: dict) -> frozenset[str]:
    removed = audit.get("removed")

    if not isinstance(removed, list):
        raise SourceTranscriptProvenanceError(
            "Provenance invalide : champ « removed » absent ou malformé."
        )

    refs: list[str] = []
    for index, entry in enumerate(removed):
        if not isinstance(entry, dict):
            raise SourceTranscriptProvenanceError(
                f"Provenance invalide : removed[{index}] n'est pas un objet."
            )
        ref = str(entry.get("source_ref") or "").strip()
        if not ref:
            raise SourceTranscriptProvenanceError(
                f"Provenance invalide : removed[{index}] sans source_ref."
            )
        refs.append(ref)

    if len(refs) != len(set(refs)):
        raise SourceTranscriptProvenanceError(
            "Provenance invalide : source_ref dupliqué dans removed."
        )

    return frozenset(refs)


def _verify_survivors(
    original: TranscriptDocument,
    derived: TranscriptDocument,
) -> bool:
    original_by_id = {segment.id: segment for segment in original.segments}

    for segment in derived.segments:
        source = original_by_id.get(segment.id)
        if source is None:
            continue
        for field in _SURVIVOR_FIELDS:
            actual = getattr(segment, field)
            expected = getattr(source, field)
            if actual != expected:
                raise SourceTranscriptProvenanceError(
                    f"{segment.id} : champ survivant « {field} » modifié "
                    f"({actual!r} ≠ {expected!r})."
                )

    return True


def _verify_audit_counts(
    stats: dict,
    *,
    original: TranscriptDocument,
    derived: TranscriptDocument,
    removed_count: int,
) -> None:
    checks = (
        ("original_segment_count", original.stats.segment_count),
        ("clean_segment_count", derived.stats.segment_count),
        ("original_word_count", original.stats.word_count),
        ("clean_word_count", derived.stats.word_count),
        ("removed_source_count", removed_count),
    )

    for key, expected in checks:
        if key not in stats:
            continue
        actual = stats[key]
        if actual != expected:
            raise SourceTranscriptProvenanceError(
                f"stats.{key} de la provenance ({actual}) ≠ {expected}."
            )

    if original.stats.segment_count - derived.stats.segment_count != removed_count:
        raise SourceTranscriptProvenanceError(
            "Comptage incohérent : "
            f"original {original.stats.segment_count} − "
            f"clean {derived.stats.segment_count} ≠ "
            f"removed {removed_count}."
        )


def _load_document(path: Path) -> TranscriptDocument:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise SourceTranscriptProvenanceError(
            f"Transcript illisible pour la provenance : {path}."
        )

    sources = [
        TranscriptSource(
            source_id=str(item.get("source_id") or ""),
            order=int(item.get("order") or 0),
            filename=str(item.get("filename") or ""),
            duration_seconds=float(item.get("duration_seconds") or 0.0),
            detected_language=str(item.get("detected_language") or ""),
        )
        for item in payload.get("sources") or []
        if isinstance(item, dict)
    ]

    segments = [
        TranscriptSegment(
            id=str(item.get("id") or ""),
            source_id=str(item.get("source_id") or ""),
            source_order=int(item.get("source_order") or 0),
            start=float(item.get("start") or 0.0),
            end=float(item.get("end") or 0.0),
            text=str(item.get("text") or ""),
        )
        for item in payload.get("segments") or []
        if isinstance(item, dict)
    ]

    stats_raw = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
    stats = TranscriptStats(
        source_count=int(stats_raw.get("source_count") or 0),
        segment_count=int(stats_raw.get("segment_count") or 0),
        duration_seconds=float(stats_raw.get("duration_seconds") or 0.0),
        word_count=int(stats_raw.get("word_count") or 0),
    )

    language = payload.get("language") if isinstance(payload.get("language"), dict) else {}

    return TranscriptDocument(
        project_name=str((payload.get("project") or {}).get("name") or ""),
        sources=sources,
        segments=segments,
        stats=stats,
        primary_language=str(language.get("primary") or ""),
        detected_languages=list(language.get("detected") or []),
        transcript_id=str(payload.get("transcript_id") or ""),
        schema_version=str(payload.get("schema_version") or ""),
    )
