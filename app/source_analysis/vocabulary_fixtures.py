"""
Fixtures locales 3B.4.4 — aucun LLM.

    1. transport 3B.4.3 avec les trois jetons d'incertitude inventés
    2. transport doré qui exerce tous les jetons contrôlés
    3. transport de confiance restante (low)
    4. chargement optionnel de la réponse historique 3B.4.3 (lecture seule)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.source_analysis.canonical_vocabulary import (
    OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS,
    controlled_vocabularies,
)
from app.source_analysis.models import (
    CONFIDENCE_LEVELS,
    EXAMPLE_KINDS,
    IDEA_KINDS,
    IMPORTANCE_LEVELS,
    REFERENCE_COMPLETENESS,
    REFERENCE_KINDS,
    RELATION_KINDS,
    REPETITION_CHARACTERS,
    SEVERITY_LEVELS,
    UNCERTAINTY_KINDS,
)
from app.source_analysis.ultra_compact_schema import (
    KIND_AUDIENCE_KIND,
    KIND_EXAMPLE,
    KIND_IDEA,
    KIND_INTENT_KIND,
    KIND_REFERENCE,
    KIND_RELATION,
    KIND_REPETITION,
    KIND_TOPIC,
    KIND_UNCERTAINTY,
    KIND_VOICE,
    VOICE_FIELDS,
    VOICE_LIST_FIELDS,
)
from app.source_analysis.writer import transcripts_dir

HISTORICAL_3B43_TRANSPORT_RELATIVE = (
    "audit/source_analysis_ultra_compact_canary_transport.json"
)


def _record(
    kind: str,
    value: str,
    source_refs: list[str] | None = None,
    links: list[int] | None = None,
    metadata: list[str] | None = None,
) -> dict:
    return {
        "k": kind,
        "v": value,
        "s": list(source_refs or []),
        "l": list(links or []),
        "m": list(metadata or []),
    }


def default_src(index: int = 1) -> str:
    return f"SRC{index:06d}"


def build_observed_3b43_invalid_transport(src: str | None = None) -> dict:
    """
    Reproduit exactement les trois kinds d'incertitude inventés en 3B.4.3.

    Le decoder DOIT les refuser. Aucune réparation de synonyme.
    """
    ref = src or default_src(1)
    return {
        "theme": "Fragment isolé au sujet d'une phrase conditionnelle.",
        "intent": "Négation d'une phrase attribuée à un référent non nommé.",
        "ic": "low",
        "aud": "Aucune marque d'audience dans le fragment.",
        "ac": "low",
        "records": [
            _record(
                KIND_TOPIC,
                "Ce qu'il n'a pas dit",
                [ref],
                [],
                ["Phrase répétée au sujet du père."],
            ),
            _record(
                KIND_IDEA,
                "L'orateur nie qu'il ait dit cette phrase.",
                [ref],
                [0],
                ["claim", "central"],
            ),
            _record(
                KIND_UNCERTAINTY,
                "Répétition identique trop brève : artefact possible.",
                [ref],
                [],
                [OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS[0], "high"],
            ),
            _record(
                KIND_UNCERTAINTY,
                "Le référent de he n'est pas nommé.",
                [ref],
                [],
                [OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS[1], "medium"],
            ),
            _record(
                KIND_UNCERTAINTY,
                "La pensée reste inachevée dans l'extrait.",
                [ref],
                [],
                [OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS[2], "medium"],
            ),
        ],
    }


def load_historical_3b43_transport(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict | None:
    """Lecture seule de l'artefact historique — jamais modifié."""
    root = Path(transcripts_dir(project_name, sortie_dir=sortie_dir)).parent
    path = root / HISTORICAL_3B43_TRANSPORT_RELATIVE
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    transport = payload.get("transport")
    return dict(transport) if isinstance(transport, dict) else None


def build_golden_full_vocabulary_transport(
    src_ids: list[str] | None = None,
    *,
    intent_confidence: str = "high",
    audience_confidence: str = "medium",
) -> dict:
    """
    Transport synthétique qui exerce tous les jetons contrôlés finis,
    sauf le niveau de confiance restant (couvert par le fixture low).
    """
    srcs = list(src_ids) if src_ids else [default_src(1), default_src(2), default_src(3)]
    primary = srcs[0]
    secondary = srcs[1] if len(srcs) > 1 else srcs[0]
    tertiary = srcs[2] if len(srcs) > 2 else srcs[0]

    records: list[dict] = [
        _record(KIND_INTENT_KIND, "enseigner"),
        _record(KIND_AUDIENCE_KIND, "croyants"),
        _record(KIND_TOPIC, "Foi dans l'épreuve", [primary], [], ["Ce que la foi modifie."]),
        _record(
            KIND_TOPIC,
            "Confiance révélée",
            [secondary],
            [],
            ["L'épreuve révèle une confiance déjà là."],
        ),
    ]
    topic_a = 2
    topic_b = 3

    idea_start = len(records)
    idea_indexes: list[int] = []
    for offset, kind in enumerate(IDEA_KINDS):
        importance = IMPORTANCE_LEVELS[offset % len(IMPORTANCE_LEVELS)]
        topic = topic_a if offset % 2 == 0 else topic_b
        idea_indexes.append(len(records))
        records.append(
            _record(
                KIND_IDEA,
                f"Idée {kind}.",
                [primary if offset % 2 == 0 else secondary],
                [topic],
                [kind, importance],
            )
        )

    first_idea = idea_indexes[0]
    second_idea = idea_indexes[1]
    for offset, relation in enumerate(RELATION_KINDS):
        origin = idea_indexes[offset % len(idea_indexes)]
        target = idea_indexes[(offset + 1) % len(idea_indexes)]
        if origin == target:
            target = idea_indexes[(offset + 2) % len(idea_indexes)]
        records.append(_record(KIND_RELATION, relation, [], [origin, target], []))

    for offset, kind in enumerate(EXAMPLE_KINDS):
        records.append(
            _record(
                KIND_EXAMPLE,
                f"Exemple {kind}.",
                [tertiary],
                [idea_indexes[offset % len(idea_indexes)]],
                [kind],
            )
        )

    for offset, kind in enumerate(REFERENCE_KINDS):
        completeness = REFERENCE_COMPLETENESS[offset % len(REFERENCE_COMPLETENESS)]
        records.append(
            _record(
                KIND_REFERENCE,
                f"Référence {kind}",
                [primary],
                [],
                [kind, completeness, "" if completeness == "vague" else kind],
            )
        )

    for offset, kind in enumerate(UNCERTAINTY_KINDS):
        severity = SEVERITY_LEVELS[offset % len(SEVERITY_LEVELS)]
        records.append(
            _record(
                KIND_UNCERTAINTY,
                f"Incertitude {kind}.",
                [secondary],
                [],
                [kind, severity],
            )
        )

    for offset, character in enumerate(REPETITION_CHARACTERS):
        records.append(
            _record(
                KIND_REPETITION,
                f"Reprise {character}.",
                [primary, secondary],
                [first_idea, second_idea],
                [character],
            )
        )

    for field in VOICE_FIELDS:
        value = f"observé {field}" if field in VOICE_LIST_FIELDS else f"valeur {field}"
        records.append(_record(KIND_VOICE, value, [], [], [field]))

    if idea_start < 0:  # pragma: no cover — garde structurelle
        raise RuntimeError("golden fixture sans IDEA")

    return {
        "theme": "Le rôle de la foi dans la manière de traverser les épreuves",
        "intent": "Enseigner ce que la foi change dans l'épreuve.",
        "ic": intent_confidence,
        "aud": "Audience croyante intéressée par la foi.",
        "ac": audience_confidence,
        "records": records,
    }


def build_remaining_confidence_transport(src_ids: list[str] | None = None) -> dict:
    """Couvre le jeton de confiance restant (`low`) sur ic et ac."""
    payload = build_golden_full_vocabulary_transport(
        src_ids,
        intent_confidence="low",
        audience_confidence="low",
    )
    payload["theme"] = "Lecture prudente d'une intention peu marquée."
    payload["intent"] = "Intention apparente faible."
    payload["aud"] = "Audience peu identifiable."
    return payload


def inject_invalid_token(
    payload: dict,
    *,
    vocab_key: str,
    invalid_value: str,
) -> dict:
    """
    Injecte une valeur non canonique dans une copie du transport doré.

    Ne répare rien. Sert uniquement aux tests négatifs.
    """
    clone: dict[str, Any] = json.loads(json.dumps(payload))
    if vocab_key == "confidence":
        clone["ic"] = invalid_value
        return clone
    if vocab_key == "record.kind":
        clone["records"][2]["k"] = invalid_value
        return clone

    kind_field = {
        "idea.kind": (KIND_IDEA, 0),
        "idea.importance": (KIND_IDEA, 1),
        "example.kind": (KIND_EXAMPLE, 0),
        "reference.kind": (KIND_REFERENCE, 0),
        "reference.completeness": (KIND_REFERENCE, 1),
        "uncertainty.kind": (KIND_UNCERTAINTY, 0),
        "uncertainty.severity": (KIND_UNCERTAINTY, 1),
        "repetition.character": (KIND_REPETITION, 0),
        "voice.field": (KIND_VOICE, 0),
    }
    if vocab_key == "relation.type":
        for record in clone["records"]:
            if record["k"] == KIND_RELATION:
                record["v"] = invalid_value
                break
        return clone

    target_kind, index = kind_field[vocab_key]
    for record in clone["records"]:
        if record["k"] == target_kind:
            metadata = list(record["m"])
            while len(metadata) <= index:
                metadata.append("")
            metadata[index] = invalid_value
            record["m"] = metadata
            break
    return clone


def exercised_controlled_values(payload: dict) -> set[tuple[str, str]]:
    """Jetons contrôlés réellement présents dans un transport."""
    seen: set[tuple[str, str]] = set()
    if payload.get("ic") in CONFIDENCE_LEVELS:
        seen.add(("confidence", payload["ic"]))
    if payload.get("ac") in CONFIDENCE_LEVELS:
        seen.add(("confidence", payload["ac"]))

    for record in payload.get("records") or []:
        kind = record.get("k")
        metadata = list(record.get("m") or [])
        if kind in controlled_vocabularies()["record.kind"].values:
            seen.add(("record.kind", kind))
        if kind == KIND_IDEA and len(metadata) >= 2:
            seen.add(("idea.kind", metadata[0]))
            seen.add(("idea.importance", metadata[1]))
        elif kind == KIND_RELATION:
            seen.add(("relation.type", record.get("v", "")))
        elif kind == KIND_EXAMPLE and metadata:
            seen.add(("example.kind", metadata[0]))
        elif kind == KIND_REFERENCE and len(metadata) >= 2:
            seen.add(("reference.kind", metadata[0]))
            seen.add(("reference.completeness", metadata[1]))
        elif kind == KIND_UNCERTAINTY and len(metadata) >= 2:
            seen.add(("uncertainty.kind", metadata[0]))
            seen.add(("uncertainty.severity", metadata[1]))
        elif kind == KIND_REPETITION and metadata:
            seen.add(("repetition.character", metadata[0]))
        elif kind == KIND_VOICE and metadata:
            seen.add(("voice.field", metadata[0]))
    return seen
