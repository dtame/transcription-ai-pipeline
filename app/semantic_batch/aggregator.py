"""
Agrégation finale de la Phase 3A.1.2B (§26-34).

Construit `semantic_translation_classification.json` à partir des lots déjà
validés (cache ou appel réel) : AUCUN appel réseau ici. Les métadonnées
LOCALES d'un bloc (audio_id, structure, phase_3a1_status, word_count,
fr_segment_count, bridge_source_refs) ne sont jamais envoyées au modèle
(§15), mais sont légitimement exploitables ICI, après coup, pour le rapport
et les listes de risque — exactement comme app.semantic_canary.report le
fait déjà pour le canary (§22-25).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from app.semantic_batch.models import (
    SCHEMA_VERSION,
    STATUS_ALREADY_RESOLVED,
    STATUS_NO_ENGLISH_CONTEXT,
    TRANSLATION_CLASSIFICATIONS,
)
from app.semantic_canary.models import CLASSIFICATIONS, CanaryClassification, SelectedBlock

if TYPE_CHECKING:  # pragma: no cover - annotations seulement
    from app.semantic_batch.runner import BatchOutcome
    from app.semantic_batch.integrity import IntegritySnapshot

# §33 : bloc FR > 60 mots classifié TRANSLATION_* -> jamais auto-supprimable
# sans revue humaine, quelle que soit la confiance rapportée.
LONG_BLOCK_WORD_THRESHOLD = 60

# §32 : seuils déterministes des critères d'inclusion dans la liste de
# risque. Chaque critère est documenté séparément ci-dessous, et un bloc
# inclus porte toujours la liste des raisons qui l'y ont fait entrer
# (`risk_reasons`), pour qu'une revue humaine future comprenne pourquoi sans
# devoir relire le code.
RISK_CONFIDENCE_THRESHOLD = 0.90
RISK_WORD_COUNT_THRESHOLD = 30

# "Blocs multi-SRC importants" (§32) : au moins ce nombre de segments FR
# fusionnés dans le bloc. Choisi à la frontière du histogramme publié par
# language_blocks.json (block_size_segments_histogram : buckets 1, 2, 3,
# "4-5", "6-10", ">10") — un bloc de 5 segments ou plus sort du cas courant
# (single/pair de segments) et mérite une revue, indépendamment de sa
# classification (interprétation prudente : §5, asymétrie de sécurité).
RISK_MULTI_SRC_SEGMENT_THRESHOLD = 5

# §32 : mots-clés (bilingue — la justification observée en Phase 3A.1.2A est
# rédigée en français, alors que le cahier des charges cite ces mots en
# anglais) signalant une justification qui évoque un contenu potentiellement
# excédentaire. Recherche insensible à la casse, sous-chaîne simple —
# volontairement large : un faux positif n'ajoute qu'une ligne à revoir
# humainement, un faux négatif laisserait passer un cas risqué (§5).
RISK_REASON_KEYWORDS = (
    "additional content",
    "contenu supplémentaire",
    "contenu additionnel",
    "partial",
    "partiel",
    "partielle",
    "unclear",
    "incertain",
    "pas clair",
    "ambigu",
    "different",
    "différent",
    "différente",
    "extra",
    "commentary",
    "commentaire",
    "développe",
    "developpe",
    "digression",
)

CONFIDENCE_RANGE_LABELS = ("<0.70", "0.70-0.79", "0.80-0.89", "0.90-0.94", ">=0.95")


def confidence_range_label(confidence: float) -> str:
    """§30 : bornes exactes des tranches de confiance du rapport final."""
    if confidence < 0.70:
        return "<0.70"
    if confidence < 0.80:
        return "0.70-0.79"
    if confidence < 0.90:
        return "0.80-0.89"
    if confidence < 0.95:
        return "0.90-0.94"
    return ">=0.95"


def requires_human_review(*, classification: str, word_count: int) -> bool:
    """§33 : règle locale et déterministe, jamais dépendante de la confidence."""
    return word_count > LONG_BLOCK_WORD_THRESHOLD and classification in TRANSLATION_CLASSIFICATIONS


def _risk_reasons(
    *,
    classification: str,
    confidence: float,
    word_count: int,
    fr_segment_count: int,
    bridge_source_refs: list[str],
    reason: str,
) -> list[str]:
    reasons: list[str] = []

    if classification in TRANSLATION_CLASSIFICATIONS and confidence < RISK_CONFIDENCE_THRESHOLD:
        reasons.append(
            f"TRANSLATION_* avec confidence={confidence} < {RISK_CONFIDENCE_THRESHOLD}."
        )

    if fr_segment_count >= RISK_MULTI_SRC_SEGMENT_THRESHOLD:
        reasons.append(
            "bloc multi-SRC important "
            f"(fr_segment_count={fr_segment_count} >= {RISK_MULTI_SRC_SEGMENT_THRESHOLD})."
        )

    if classification in TRANSLATION_CLASSIFICATIONS and word_count > RISK_WORD_COUNT_THRESHOLD:
        reasons.append(
            f"bloc > {RISK_WORD_COUNT_THRESHOLD} mots classifié TRANSLATION_* "
            f"(word_count={word_count})."
        )

    if bridge_source_refs:
        reasons.append(
            f"bloc contenant des bridge_source_refs MIXED/UNKNOWN ({len(bridge_source_refs)})."
        )

    reason_lower = (reason or "").lower()
    matched_keywords = sorted({kw for kw in RISK_REASON_KEYWORDS if kw in reason_lower})
    if matched_keywords:
        reasons.append(f"justification évoque un contenu excédentaire : {matched_keywords}.")

    return reasons


def build_result_entry(selected_block: SelectedBlock, result: CanaryClassification) -> dict:
    """Une ligne de `results[]` de l'artefact final : classification + contexte local."""
    raw = selected_block.raw_block
    word_count = int(raw.get("word_count", 0))
    fr_segment_count = int(raw.get("fr_segment_count", 0))
    bridge_refs = list(raw.get("bridge_source_refs") or [])

    entry = result.to_dict()
    entry["audio_id"] = raw.get("audio_id")
    entry["structure"] = raw.get("structure")
    entry["phase_3a1_status"] = raw.get("phase_3a1_status")
    entry["word_count"] = word_count
    entry["fr_segment_count"] = fr_segment_count
    entry["confidence_range"] = confidence_range_label(result.confidence)
    entry["requires_human_review"] = requires_human_review(
        classification=result.classification, word_count=word_count
    )

    risk_reasons = _risk_reasons(
        classification=result.classification,
        confidence=result.confidence,
        word_count=word_count,
        fr_segment_count=fr_segment_count,
        bridge_source_refs=bridge_refs,
        reason=result.reason,
    )
    entry["risk_reasons"] = risk_reasons
    entry["is_high_risk_for_deletion_review"] = bool(risk_reasons)

    return entry


def build_classification_totals(entries: list[dict]) -> dict[str, int]:
    counts = {label: 0 for label in CLASSIFICATIONS}
    for entry in entries:
        counts[entry["classification"]] += 1
    return counts


def build_distribution(entries: list[dict], key: str) -> dict[str, dict[str, int]]:
    """Distribution des classifications par valeur de `key` (§30)."""
    distribution: dict[str, dict[str, int]] = {}
    for entry in entries:
        bucket = str(entry.get(key))
        counts = distribution.setdefault(bucket, {label: 0 for label in CLASSIFICATIONS})
        counts[entry["classification"]] += 1
    return distribution


def build_confidence_distribution(entries: list[dict]) -> dict[str, int]:
    counts = {label: 0 for label in CONFIDENCE_RANGE_LABELS}
    for entry in entries:
        counts[entry["confidence_range"]] += 1
    return counts


def build_divergence_report(entries: list[dict]) -> dict:
    """§31 : croisement phase_3a1_status (Phase 3A.1) x classification (cette phase)."""
    matrix: dict[str, dict[str, int]] = {}
    for entry in entries:
        status = str(entry.get("phase_3a1_status"))
        counts = matrix.setdefault(status, {label: 0 for label in CLASSIFICATIONS})
        counts[entry["classification"]] += 1

    highlights = {
        "ALL_KEEP_to_TRANSLATION": sum(
            matrix.get("ALL_KEEP", {}).get(c, 0) for c in TRANSLATION_CLASSIFICATIONS
        ),
        "ALL_REVIEW_to_NOT_TRANSLATION": matrix.get("ALL_REVIEW", {}).get(
            "NOT_TRANSLATION", 0
        ),
        "HAS_REVIEW_to_UNCERTAIN": matrix.get("HAS_REVIEW", {}).get("UNCERTAIN", 0),
    }

    return {"matrix": matrix, "highlights": highlights}


def build_long_blocks_section(entries: list[dict]) -> list[dict]:
    """§33 : tous les blocs > 60 mots, quelle que soit leur classification."""
    return sorted(
        (
            {
                "block_id": entry["block_id"],
                "word_count": entry["word_count"],
                "classification": entry["classification"],
                "confidence": entry["confidence"],
                "requires_human_review": entry["requires_human_review"],
            }
            for entry in entries
            if entry["word_count"] > LONG_BLOCK_WORD_THRESHOLD
        ),
        key=lambda item: item["block_id"],
    )


def build_risk_list(entries: list[dict]) -> list[dict]:
    """§32 : `high_risk_for_deletion_review`."""
    return sorted(
        (
            {
                "block_id": entry["block_id"],
                "classification": entry["classification"],
                "confidence": entry["confidence"],
                "risk_reasons": entry["risk_reasons"],
            }
            for entry in entries
            if entry["is_high_risk_for_deletion_review"]
        ),
        key=lambda item: item["block_id"],
    )


def build_previously_resolved_section(blocks: list[dict]) -> list[dict]:
    """§27 : les 15 ALREADY_RESOLVED — statut existant seulement, jamais une nouvelle classification."""
    return [
        {"block_id": str(block["block_id"]), "existing_status": STATUS_ALREADY_RESOLVED}
        for block in sorted(
            (b for b in blocks if b.get("semantic_review_status") == STATUS_ALREADY_RESOLVED),
            key=lambda b: str(b["block_id"]),
        )
    ]


def build_no_english_context_section(blocks: list[dict]) -> list[dict]:
    """§28 : les 4 NO_ENGLISH_CONTEXT — statut séparé, jamais envoyés au modèle."""
    return [
        {"block_id": str(block["block_id"]), "status": STATUS_NO_ENGLISH_CONTEXT}
        for block in sorted(
            (
                b
                for b in blocks
                if b.get("semantic_review_status") == STATUS_NO_ENGLISH_CONTEXT
            ),
            key=lambda b: str(b["block_id"]),
        )
    ]


def aggregate_usage_and_cost(outcomes: list["BatchOutcome"]) -> tuple[dict, dict]:
    """§24, §39 : totaux réseau + coût, cache hits compris (§26)."""
    total_real_calls = sum(1 for o in outcomes if o.source == "REAL_CALL")
    total_cache_hits = sum(1 for o in outcomes if o.source == "CACHE_HIT")

    total_input = 0
    total_output = 0
    total_tokens = 0
    total_latency_ms = 0

    known_cost = Decimal(0)
    any_known = False
    any_unknown = False
    currency: str | None = None

    for outcome in outcomes:
        usage = outcome.usage or {}
        total_input += int(usage.get("input_tokens") or 0)
        total_output += int(usage.get("output_tokens") or 0)
        total_tokens += int(usage.get("total_tokens") or 0)
        total_latency_ms += int(outcome.latency_ms or 0)

        cost = outcome.cost or {}
        if cost.get("total_cost") is None:
            any_unknown = True
        else:
            any_known = True
            known_cost += Decimal(str(cost["total_cost"]))
            currency = cost.get("currency") or currency

    if any_known and any_unknown:
        cost_status = "partial"
    elif any_unknown:
        cost_status = "unknown"
    elif any_known:
        cost_status = "known"
    else:
        cost_status = "no_calls"

    usage_summary = {
        "total_real_calls": total_real_calls,
        "total_cache_hits": total_cache_hits,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
        "total_latency_ms": total_latency_ms,
    }

    cost_summary = {
        "total_cost": float(known_cost) if any_known else (None if any_unknown else 0.0),
        "currency": currency,
        "cost_status": cost_status,
    }

    return usage_summary, cost_summary


def build_classification_artifact(
    *,
    project_name: str,
    blocks: list[dict],
    selected_blocks: list[SelectedBlock],
    outcomes: list["BatchOutcome"],
    prompt_version: str,
    provider: str,
    model: str,
    schema_fingerprint: str,
    integrity_before: "IntegritySnapshot",
    integrity_after: "IntegritySnapshot",
) -> dict:
    """Contenu canonique de semantic_translation_classification.json (§26)."""
    by_block_id = {block.block_id: block for block in selected_blocks}

    entries: list[dict] = []
    for outcome in outcomes:
        for result in outcome.results:
            selected = by_block_id[result.block_id]
            entries.append(build_result_entry(selected, result))

    entries.sort(key=lambda entry: entry["block_id"])

    usage_summary, cost_summary = aggregate_usage_and_cost(outcomes)

    return {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": prompt_version,
        "provider": provider,
        "model": model,
        "response_schema_fingerprint": schema_fingerprint,
        "project": project_name,
        "source_hashes": integrity_before.to_dict(),
        "source_hashes_after": integrity_after.to_dict(),
        "stats": {
            "total_classified": len(entries),
            "classification_totals": build_classification_totals(entries),
            "distribution_by_audio": build_distribution(entries, "audio_id"),
            "distribution_by_structure": build_distribution(entries, "structure"),
            "distribution_by_phase_3a1_status": build_distribution(
                entries, "phase_3a1_status"
            ),
            "confidence_distribution": build_confidence_distribution(entries),
        },
        "results": entries,
        "previously_resolved_blocks": build_previously_resolved_section(blocks),
        "no_english_context_blocks": build_no_english_context_section(blocks),
        "divergences_with_phase_3a1": build_divergence_report(entries),
        "high_risk_for_deletion_review": build_risk_list(entries),
        "long_blocks": build_long_blocks_section(entries),
        "batches": [outcome.to_dict() for outcome in outcomes],
        "usage_summary": usage_summary,
        "cost_summary": cost_summary,
    }
