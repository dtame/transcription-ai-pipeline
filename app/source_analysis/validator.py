"""
Validateur du Source Map.

Distinct du normalizer à dessein : celui-ci fabrique, celui-là juge. Un
validateur qui répare n'est plus un validateur, et un Source Map réparé
discrètement est pire qu'un Source Map refusé — on croirait l'analyse fidèle.

Style repris de app/transcript_validator.py (Phase 1) : les violations sont
COLLECTÉES puis levées ensemble, plutôt que de s'arrêter à la première.

Invariants vérifiés :

    en-tête            schema_version, transcript_id, projet, langue
    thème              main_theme non vide
    identifiants       uniques, continus, conformes à leur préfixe
    vocabulaires       kind / importance / severity / character / relation
    traçabilité        chaque source_ref existe dans le transcript
    références internes  topic_refs, supports_idea_refs, idea_refs, relations
    stats              compteurs et couverture recalculés
    complétude         une source substantielle ne produit pas zéro idée
    frontière          aucun champ éditorial de premier niveau

La couverture est vérifiée pour son EXACTITUDE, jamais pour atteindre un seuil :
une couverture de 60 % est un fait à rapporter, pas un échec.
"""

from __future__ import annotations

from typing import Mapping

from app.source_analysis.errors import (
    SourceMapEditorialLeakError,
    SourceMapValidationError,
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
    SOURCE_MAP_SCHEMA_VERSION,
    UNCERTAINTY_KINDS,
    SourceMap,
    forbidden_editorial_fields,
    format_example_id,
    format_idea_id,
    format_reference_id,
    format_repetition_id,
    format_topic_id,
    format_uncertainty_id,
)
from app.source_analysis.transcript_input import TranscriptInput


def ensure_no_editorial_fields(payload: Mapping, *, location: str = "source_map") -> None:
    """
    Barrière architecturale Phase 3 / Phase 4.

    Appelée sur la réponse brute du modèle ET sur le dictionnaire publié : si un
    `chapters` survit aux deux contrôles, c'est que le code lui-même a fabriqué
    une structure de livre, ce qui doit être aussi bruyant qu'une hallucination
    du modèle.
    """
    leaked = forbidden_editorial_fields(payload)

    if leaked:
        raise SourceMapEditorialLeakError(leaked, location=location)


def validate_source_map(
    source_map: SourceMap,
    transcript: TranscriptInput,
) -> list[str]:
    """Liste des violations du contrat. Vide = valide. Ne lève jamais."""
    errors: list[str] = []

    _validate_header(source_map, transcript, errors)
    _validate_ids(source_map, errors)
    _validate_topics(source_map, errors)
    _validate_ideas(source_map, errors)
    _validate_examples(source_map, errors)
    _validate_references(source_map, errors)
    _validate_uncertainties(source_map, errors)
    _validate_repetitions(source_map, errors)
    _validate_source_refs(source_map, transcript, errors)
    _validate_stats(source_map, transcript, errors)
    _validate_completeness(source_map, transcript, errors)

    return errors


def validate_published_payload(
    payload: Mapping,
    transcript: TranscriptInput,
) -> list[str]:
    """
    Valide un source_map.json déjà écrit sur le disque.

    Relit le fichier avec SourceMap.from_dict() puis applique le MÊME validateur
    qu'une analyse fraîche. C'est ce qui rend un « cache hit » digne de
    confiance : réutiliser une analyse sans la revalider reviendrait à supposer
    qu'un fichier posé sur un disque ne change jamais.
    """
    if not isinstance(payload, Mapping):
        return ["source_map publié illisible : un objet JSON est attendu"]

    leaked = forbidden_editorial_fields(payload)

    if leaked:
        return [
            f"champ éditorial interdit dans le source_map publié : « {name} »"
            for name in leaked
        ]

    try:
        source_map = SourceMap.from_dict(payload)
    except Exception as exc:  # payload arbitraire : on rapporte, on ne casse pas
        return [f"source_map publié illisible : {type(exc).__name__}"]

    return validate_source_map(source_map, transcript)


def ensure_valid_source_map(
    source_map: SourceMap,
    transcript: TranscriptInput,
) -> None:
    """
    Valide, ou refuse la publication.

    Contrôle d'abord la frontière éditoriale sur le dictionnaire publié, puis
    les invariants de contenu.
    """
    ensure_no_editorial_fields(source_map.to_dict())

    errors = validate_source_map(source_map, transcript)

    if errors:
        raise SourceMapValidationError(errors)


# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------

def _validate_header(
    source_map: SourceMap,
    transcript: TranscriptInput,
    errors: list[str],
) -> None:
    if source_map.schema_version != SOURCE_MAP_SCHEMA_VERSION:
        errors.append(
            f"schema_version inattendue : « {source_map.schema_version} » "
            f"au lieu de « {SOURCE_MAP_SCHEMA_VERSION} »"
        )

    if source_map.transcript_id != transcript.transcript_id:
        errors.append(
            f"transcript_id incohérent : « {source_map.transcript_id} » "
            f"alors que le transcript analysé est « {transcript.transcript_id} »"
        )

    if not source_map.project_name:
        errors.append("nom de projet absent")

    if source_map.primary_language != transcript.primary_language:
        errors.append(
            f"langue principale incohérente : « {source_map.primary_language} » "
            f"alors que le transcript déclare « {transcript.primary_language} »"
        )

    header = source_map.source_analysis

    if not header.main_theme:
        errors.append(
            "main_theme vide — le thème dominant de la source est obligatoire"
        )

    for label, statement in (
        ("author_intent", header.author_intent),
        ("target_audience", header.target_audience),
    ):
        if not statement.summary:
            errors.append(f"{label}.summary vide")

        if statement.confidence not in CONFIDENCE_LEVELS:
            errors.append(
                f"{label}.confidence invalide : « {statement.confidence} » "
                f"(attendu parmi {', '.join(CONFIDENCE_LEVELS)})"
            )


# ---------------------------------------------------------------------------
# Identifiants
# ---------------------------------------------------------------------------

def _validate_ids(source_map: SourceMap, errors: list[str]) -> None:
    """
    Les identifiants doivent être uniques, continus et conformes.

    « Continus » veut dire TOP001, TOP002, TOP003 sans trou : un saut
    signifierait qu'un élément a été perdu entre la normalisation et la
    publication.
    """
    expected = {
        "topics": format_topic_id,
        "ideas": format_idea_id,
        "examples": format_example_id,
        "references": format_reference_id,
        "uncertainties": format_uncertainty_id,
        "repetitions": format_repetition_id,
    }

    for collection, ids in source_map.declared_ids().items():
        formatter = expected[collection]

        if len(set(ids)) != len(ids):
            errors.append(f"{collection} : identifiants dupliqués")

        for position, identifier in enumerate(ids, start=1):
            wanted = formatter(position)

            if identifier != wanted:
                errors.append(
                    f"{collection} : identifiant « {identifier} » en position "
                    f"{position} alors que « {wanted} » est attendu — "
                    "numérotation non déterministe"
                )


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------

def _validate_topics(source_map: SourceMap, errors: list[str]) -> None:
    for topic in source_map.topics:
        if not topic.label:
            errors.append(f"{topic.topic_id} : label vide")

        if not topic.summary:
            errors.append(f"{topic.topic_id} : summary vide")

        if not topic.source_refs:
            errors.append(f"{topic.topic_id} : aucun source_ref")


def _validate_ideas(source_map: SourceMap, errors: list[str]) -> None:
    topic_ids = set(source_map.declared_ids()["topics"])
    idea_ids = set(source_map.declared_ids()["ideas"])

    for idea in source_map.ideas:
        if not idea.summary:
            errors.append(f"{idea.idea_id} : summary vide")

        if idea.kind and idea.kind not in IDEA_KINDS:
            errors.append(
                f"{idea.idea_id} : kind invalide « {idea.kind} » "
                f"(attendu parmi {', '.join(IDEA_KINDS)})"
            )

        if idea.importance not in IMPORTANCE_LEVELS:
            errors.append(
                f"{idea.idea_id} : importance invalide « {idea.importance} » "
                f"(attendu parmi {', '.join(IMPORTANCE_LEVELS)})"
            )

        if not idea.source_refs:
            errors.append(f"{idea.idea_id} : aucun source_ref")

        for ref in idea.topic_refs:
            if ref not in topic_ids:
                errors.append(
                    f"{idea.idea_id}.topic_refs : « {ref} » ne correspond à "
                    "aucun thème déclaré"
                )

        for relation in idea.relations:
            if relation.relation not in RELATION_KINDS:
                errors.append(
                    f"{idea.idea_id}.relations : relation invalide "
                    f"« {relation.relation} » (attendu parmi "
                    f"{', '.join(RELATION_KINDS)})"
                )

            if relation.to_idea not in idea_ids:
                errors.append(
                    f"{idea.idea_id}.relations : « {relation.to_idea} » ne "
                    "correspond à aucune idée déclarée"
                )

            if relation.to_idea == idea.idea_id:
                errors.append(
                    f"{idea.idea_id}.relations : relation sur elle-même"
                )


def _validate_examples(source_map: SourceMap, errors: list[str]) -> None:
    idea_ids = set(source_map.declared_ids()["ideas"])

    for example in source_map.examples:
        if not example.summary:
            errors.append(f"{example.example_id} : summary vide")

        if example.kind not in EXAMPLE_KINDS:
            errors.append(
                f"{example.example_id} : kind invalide « {example.kind} » "
                f"(attendu parmi {', '.join(EXAMPLE_KINDS)})"
            )

        if not example.source_refs:
            errors.append(f"{example.example_id} : aucun source_ref")

        for ref in example.supports_idea_refs:
            if ref not in idea_ids:
                errors.append(
                    f"{example.example_id}.supports_idea_refs : « {ref} » ne "
                    "correspond à aucune idée déclarée"
                )


def _validate_references(source_map: SourceMap, errors: list[str]) -> None:
    for reference in source_map.references:
        if not reference.raw_reference:
            errors.append(
                f"{reference.reference_id} : raw_reference vide — ce que "
                "l'auteur a dit est obligatoire"
            )

        if reference.kind not in REFERENCE_KINDS:
            errors.append(
                f"{reference.reference_id} : kind invalide « {reference.kind} » "
                f"(attendu parmi {', '.join(REFERENCE_KINDS)})"
            )

        if reference.completeness not in REFERENCE_COMPLETENESS:
            errors.append(
                f"{reference.reference_id} : completeness invalide "
                f"« {reference.completeness} » (attendu parmi "
                f"{', '.join(REFERENCE_COMPLETENESS)})"
            )

        if not reference.source_refs:
            errors.append(f"{reference.reference_id} : aucun source_ref")


def _validate_uncertainties(source_map: SourceMap, errors: list[str]) -> None:
    for uncertainty in source_map.uncertainties:
        if not uncertainty.description:
            errors.append(f"{uncertainty.uncertainty_id} : description vide")

        if uncertainty.kind not in UNCERTAINTY_KINDS:
            errors.append(
                f"{uncertainty.uncertainty_id} : kind invalide "
                f"« {uncertainty.kind} » (attendu parmi "
                f"{', '.join(UNCERTAINTY_KINDS)})"
            )

        if uncertainty.severity not in SEVERITY_LEVELS:
            errors.append(
                f"{uncertainty.uncertainty_id} : severity invalide "
                f"« {uncertainty.severity} » (attendu parmi "
                f"{', '.join(SEVERITY_LEVELS)})"
            )

        if not uncertainty.source_refs:
            errors.append(f"{uncertainty.uncertainty_id} : aucun source_ref")


def _validate_repetitions(source_map: SourceMap, errors: list[str]) -> None:
    idea_ids = set(source_map.declared_ids()["ideas"])

    for repetition in source_map.repetitions:
        if not repetition.description:
            errors.append(f"{repetition.repetition_id} : description vide")

        if repetition.character not in REPETITION_CHARACTERS:
            errors.append(
                f"{repetition.repetition_id} : character invalide "
                f"« {repetition.character} » (attendu parmi "
                f"{', '.join(REPETITION_CHARACTERS)})"
            )

        if len(repetition.idea_refs) < 2:
            errors.append(
                f"{repetition.repetition_id} : une reprise relie au moins deux "
                f"idées, {len(repetition.idea_refs)} référencée(s)"
            )

        for ref in repetition.idea_refs:
            if ref not in idea_ids:
                errors.append(
                    f"{repetition.repetition_id}.idea_refs : « {ref} » ne "
                    "correspond à aucune idée déclarée"
                )

        if not repetition.source_refs:
            errors.append(f"{repetition.repetition_id} : aucun source_ref")


# ---------------------------------------------------------------------------
# Traçabilité, statistiques, complétude
# ---------------------------------------------------------------------------

def _validate_source_refs(
    source_map: SourceMap,
    transcript: TranscriptInput,
    errors: list[str],
) -> None:
    """
    Chaque SRC cité doit exister parmi les SRC PRÉSENTS du transcript.

    L'appartenance est `source_ref ∈ set(src_ids présents)`, jamais une
    plage numérique continue. Un transcript DERIVED peut donc citer
    SRC002719 et SRC002721 sans que SRC002720 existe.
    """
    src_index = transcript.src_index()

    collections = (
        ("topics", source_map.topics, "topic_id"),
        ("ideas", source_map.ideas, "idea_id"),
        ("examples", source_map.examples, "example_id"),
        ("references", source_map.references, "reference_id"),
        ("uncertainties", source_map.uncertainties, "uncertainty_id"),
        ("repetitions", source_map.repetitions, "repetition_id"),
    )

    for _, collection, id_field in collections:
        for item in collection:
            identifier = getattr(item, id_field)
            positions: list[int] = []

            for ref in item.source_refs:
                if ref not in src_index:
                    errors.append(
                        f"{identifier}.source_refs : « {ref} » n'existe pas "
                        "dans le transcript"
                    )
                    continue

                positions.append(src_index[ref])

            if len(set(positions)) != len(positions):
                errors.append(f"{identifier}.source_refs : références dupliquées")

            if positions != sorted(positions):
                errors.append(
                    f"{identifier}.source_refs : ordre non canonique — les SRC "
                    "doivent suivre l'ordre de la source"
                )


def _validate_stats(
    source_map: SourceMap,
    transcript: TranscriptInput,
    errors: list[str],
) -> None:
    stats = source_map.stats

    expected_counts = {
        "topic_count": len(source_map.topics),
        "idea_count": len(source_map.ideas),
        "example_count": len(source_map.examples),
        "reference_count": len(source_map.references),
        "uncertainty_count": len(source_map.uncertainties),
        "repetition_count": len(source_map.repetitions),
        "source_segment_count": transcript.segment_count,
    }

    for name, expected in expected_counts.items():
        actual = getattr(stats, name)

        if actual != expected:
            errors.append(
                f"stats.{name} incohérent : {actual} déclaré, {expected} attendu"
            )

    referenced = set(source_map.all_source_refs())

    if stats.referenced_source_segments != len(referenced):
        errors.append(
            f"stats.referenced_source_segments incohérent : "
            f"{stats.referenced_source_segments} déclaré, {len(referenced)} attendu"
        )

    total = transcript.segment_count
    expected_ratio = round(len(referenced) / total, 4) if total else 0.0

    if abs(stats.source_coverage_ratio - expected_ratio) > 1e-9:
        errors.append(
            f"stats.source_coverage_ratio incohérent : "
            f"{stats.source_coverage_ratio} déclaré, {expected_ratio} attendu"
        )


def _validate_completeness(
    source_map: SourceMap,
    transcript: TranscriptInput,
    errors: list[str],
) -> None:
    """
    Garde-fou de complétude, volontairement grossier.

    La seule règle est : une source qui contient du discours ne peut pas
    produire zéro idée. Aucune densité n'est imposée — « une idée pour trois
    SRC » serait une invention, puisque la densité dépend entièrement du
    contenu. Un exposé dense et une conversation décousue de même durée n'ont
    aucune raison de produire le même nombre d'idées.
    """
    if transcript.is_substantial and not source_map.ideas:
        errors.append(
            f"aucune idée pour une source substantielle "
            f"({transcript.word_count} mots, {transcript.segment_count} segments) — "
            "analyse anormalement pauvre"
        )
