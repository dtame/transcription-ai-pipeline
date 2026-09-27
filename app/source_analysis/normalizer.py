"""
Normalisation de la réponse du modèle en Source Map canonique.

Postulat de départ : ON NE FAIT PAS CONFIANCE AUX IDENTIFIANTS DU LLM. Les
`idea_id` qu'il renvoie peuvent être « idea_7 », « banana » ou « 42 », changer
d'une exécution à l'autre, ou se répéter. Ils ne servent donc qu'une fois, comme
clés de correspondance internes à la réponse, et sont immédiatement remplacés
par des identifiants numérotés par le programme.

Ce module fait trois choses, et seulement celles-là :

    ORDRE       chaque collection est triée par première apparition dans la
                source ; les source_refs de chaque élément sont triées selon
                l'ordre canonique des SRC du transcript

    IDENTITÉ    renumérotation en TOP001/IDEA001/EX001/REF001/UNC001/REP001,
                puis réécriture de TOUTES les références internes

    DÉRIVATION  stats et couverture, calculées depuis le contenu

Ce qu'il ne fait pas : juger la validité sémantique (c'est validator.py), ni
supprimer discrètement ce qui ne va pas. Une référence SRC inexistante est une
erreur, jamais un champ qu'on retire en silence.

Le tri par première apparition dans la source, plutôt qu'alphabétique, est un
choix : trier « Foi dans l'épreuve » avant « Zèle du début » détruirait la
progression du discours, qui est une information réelle.

Identifiants locaux « requis » ou non (Phase 3B.2) : `topic_id` et `idea_id`
sont la CIBLE de références internes (topic_refs, relations[].to_idea,
supports_idea_refs, idea_refs) — un identifiant local absent ou dupliqué y
rendrait la réponse réellement ambiguë, donc `_ordered(..., id_required=True)`
la refuse. `example_id`, `reference_id`, `uncertainty_id` et `repetition_id`
ne sont la cible d'AUCUNE référence dans ce schéma : leur absence ou leur
doublon éventuel ne crée aucune ambiguïté à résoudre, et `_ordered(...,
id_required=False)` leur substitue une clé de correspondance interne
purement positionnelle. Dans les deux cas, l'identifiant FINAL publié
(TOP001, IDEA001, EX001, REF001, UNC001, REP001…) vient uniquement de
`_assign_ids()`, jamais du modèle.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from app.source_analysis.errors import (
    SourceMapEditorialLeakError,
    SourceMapValidationError,
)
from app.source_analysis.models import (
    AnalysisProvenance,
    AuthorVoiceProfile,
    Example,
    Idea,
    IdeaRelation,
    IntentStatement,
    Reference,
    Repetition,
    SourceAnalysisHeader,
    SourceMap,
    SourceMapStats,
    Topic,
    Uncertainty,
    forbidden_editorial_fields,
    format_example_id,
    format_idea_id,
    format_reference_id,
    format_repetition_id,
    format_topic_id,
    format_uncertainty_id,
)
from app.source_analysis.transcript_input import TranscriptInput

# Précision du ratio de couverture. Arrondi fixe pour que deux exécutions
# identiques produisent le même octet : 0.6666666666666666 dépend de la
# représentation flottante, 0.6667 non.
_COVERAGE_DECIMALS = 4


def normalize_source_map(
    payload: Mapping[str, Any],
    transcript: TranscriptInput,
    *,
    provenance: AnalysisProvenance,
) -> SourceMap:
    """
    Transforme la réponse décodée du modèle en SourceMap canonique.

    Lève SourceMapValidationError en rassemblant TOUTES les violations
    détectables à ce stade (SRC inexistants, identifiants dupliqués, références
    internes pendantes) : corriger un prompt est plus simple avec la liste
    complète qu'avec la première erreur rencontrée.
    """
    if not isinstance(payload, Mapping):
        raise SourceMapValidationError(
            [f"réponse du modèle inattendue : {type(payload).__name__} au lieu d'un objet"]
        )

    leaked = forbidden_editorial_fields(payload)

    if leaked:
        raise SourceMapEditorialLeakError(leaked, location="réponse du modèle")

    header_payload = payload.get("source_analysis") or {}
    leaked_header = forbidden_editorial_fields(header_payload)

    if leaked_header:
        raise SourceMapEditorialLeakError(
            leaked_header, location="réponse du modèle / source_analysis"
        )

    errors: list[str] = []
    src_index = transcript.src_index()

    topics_raw = _ordered(
        payload.get("topics"), "topic_id", "topics", src_index, errors, id_required=True
    )
    ideas_raw = _ordered(
        payload.get("ideas"), "idea_id", "ideas", src_index, errors, id_required=True
    )
    examples_raw = _ordered(
        payload.get("examples"),
        "example_id",
        "examples",
        src_index,
        errors,
        id_required=False,
    )
    references_raw = _ordered(
        payload.get("references"),
        "reference_id",
        "references",
        src_index,
        errors,
        id_required=False,
    )
    uncertainties_raw = _ordered(
        payload.get("uncertainties"),
        "uncertainty_id",
        "uncertainties",
        src_index,
        errors,
        id_required=False,
    )
    repetitions_raw = _ordered(
        payload.get("repetitions"),
        "repetition_id",
        "repetitions",
        src_index,
        errors,
        id_required=False,
    )

    if errors:
        raise SourceMapValidationError(errors)

    topic_ids = _assign_ids(topics_raw, format_topic_id)
    idea_ids = _assign_ids(ideas_raw, format_idea_id)
    example_ids = _assign_ids(examples_raw, format_example_id)
    reference_ids = _assign_ids(references_raw, format_reference_id)
    uncertainty_ids = _assign_ids(uncertainties_raw, format_uncertainty_id)
    repetition_ids = _assign_ids(repetitions_raw, format_repetition_id)

    topics = tuple(
        Topic(
            topic_id=topic_ids[entry.local_id],
            label=_text(entry.data.get("label")),
            summary=_text(entry.data.get("summary")),
            source_refs=entry.source_refs,
        )
        for entry in topics_raw
    )

    ideas = tuple(
        Idea(
            idea_id=idea_ids[entry.local_id],
            summary=_text(entry.data.get("summary")),
            kind=_text(entry.data.get("kind")),
            importance=_text(entry.data.get("importance")),
            topic_refs=_remap(
                entry.data.get("topic_refs"),
                topic_ids,
                context=f"ideas[{idea_ids[entry.local_id]}].topic_refs",
                target="topics",
                errors=errors,
            ),
            relations=_remap_relations(
                entry.data.get("relations"),
                idea_ids,
                context=f"ideas[{idea_ids[entry.local_id]}].relations",
                errors=errors,
            ),
            source_refs=entry.source_refs,
        )
        for entry in ideas_raw
    )

    examples = tuple(
        Example(
            example_id=example_ids[entry.local_id],
            kind=_text(entry.data.get("kind")),
            summary=_text(entry.data.get("summary")),
            supports_idea_refs=_remap(
                entry.data.get("supports_idea_refs"),
                idea_ids,
                context=f"examples[{example_ids[entry.local_id]}].supports_idea_refs",
                target="ideas",
                errors=errors,
            ),
            source_refs=entry.source_refs,
        )
        for entry in examples_raw
    )

    references = tuple(
        Reference(
            reference_id=reference_ids[entry.local_id],
            kind=_text(entry.data.get("kind")),
            raw_reference=_text(entry.data.get("raw_reference")),
            normalized_reference=_text(entry.data.get("normalized_reference")),
            completeness=_text(entry.data.get("completeness")),
            source_refs=entry.source_refs,
        )
        for entry in references_raw
    )

    uncertainties = tuple(
        Uncertainty(
            uncertainty_id=uncertainty_ids[entry.local_id],
            kind=_text(entry.data.get("kind")),
            description=_text(entry.data.get("description")),
            severity=_text(entry.data.get("severity")),
            source_refs=entry.source_refs,
        )
        for entry in uncertainties_raw
    )

    repetitions = tuple(
        Repetition(
            repetition_id=repetition_ids[entry.local_id],
            character=_text(entry.data.get("character")),
            description=_text(entry.data.get("description")),
            idea_refs=_remap(
                entry.data.get("idea_refs"),
                idea_ids,
                context=f"repetitions[{repetition_ids[entry.local_id]}].idea_refs",
                target="ideas",
                errors=errors,
            ),
            source_refs=entry.source_refs,
        )
        for entry in repetitions_raw
    )

    if errors:
        raise SourceMapValidationError(errors)

    source_map = SourceMap(
        transcript_id=transcript.transcript_id,
        project_name=transcript.project_name,
        primary_language=transcript.primary_language,
        source_analysis=_build_header(header_payload),
        topics=topics,
        ideas=ideas,
        examples=examples,
        references=references,
        uncertainties=uncertainties,
        repetitions=repetitions,
        author_voice_profile=_build_voice_profile(payload.get("author_voice_profile")),
        stats=_build_stats(
            transcript,
            topics=topics,
            ideas=ideas,
            examples=examples,
            references=references,
            uncertainties=uncertainties,
            repetitions=repetitions,
        ),
        analysis=provenance,
    )

    return source_map


# ---------------------------------------------------------------------------
# Ordre et identifiants
# ---------------------------------------------------------------------------

class _Entry:
    """Élément brut accompagné de ce qui permet de l'ordonner."""

    __slots__ = ("local_id", "data", "source_refs", "first_src", "position")

    def __init__(self, local_id, data, source_refs, first_src, position):
        self.local_id = local_id
        self.data = data
        self.source_refs = source_refs
        self.first_src = first_src
        self.position = position


def _ordered(
    raw: Any,
    id_field: str,
    collection: str,
    src_index: Mapping[str, int],
    errors: list[str],
    *,
    id_required: bool,
) -> list[_Entry]:
    """
    Lit une collection brute, valide ses SRC et ses identifiants, puis l'ordonne.

    Clé de tri : (premier SRC cité, position dans la réponse). Un élément arrive
    donc dans le Source Map à la place où la SOURCE l'introduit, et non à celle
    où le modèle a choisi de le mentionner. La position d'origine ne sert qu'à
    départager deux éléments introduits par le même segment, ce qui garde un
    ordre total et donc reproductible.

    `id_required` distingue deux régimes (voir le docstring du module) :

    True    `id_field` est la cible d'au moins une référence interne ailleurs
            dans la réponse (topic_refs, to_idea, supports_idea_refs,
            idea_refs). Absent ou dupliqué, il rendrait une réécriture
            ultérieure ambiguë : c'est une erreur, collectée comme les autres.

    False   `id_field` n'est la cible d'aucune référence. Le programme n'a
            besoin d'aucune valeur venant du modèle pour identifier l'entrée à
            ce stade : la clé de correspondance interne est purement
            positionnelle, donc toujours présente et toujours unique — que le
            modèle ait fourni un identifiant, l'ait oublié, ou l'ait dupliqué
            par accident.
    """
    if raw is None:
        return []

    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        errors.append(f"{collection} : une liste est attendue")
        return []

    entries: list[_Entry] = []
    seen: set[str] = set()

    for position, item in enumerate(raw):
        if not isinstance(item, Mapping):
            errors.append(f"{collection}[{position}] : un objet est attendu")
            continue

        if id_required:
            local_id = _text(item.get(id_field))

            if not local_id:
                errors.append(
                    f"{collection}[{position}] : {id_field} absent ou vide — "
                    "requis pour réécrire les références internes qui le ciblent"
                )
                continue

            if local_id in seen:
                errors.append(
                    f"{collection}[{position}] : identifiant local dupliqué "
                    f"« {local_id} » — toute référence interne serait ambiguë"
                )
                continue

            seen.add(local_id)
        else:
            # Aucune référence de cette réponse ne cible cet identifiant :
            # sa valeur éventuelle est ignorée pour la clé interne, qui reste
            # positionnelle et donc toujours valide.
            local_id = f"__pos{position:06d}__"

        refs = _normalize_source_refs(
            item.get("source_refs"),
            src_index,
            context=f"{collection}[{local_id}]" if id_required else f"{collection}[{position}]",
            errors=errors,
        )

        if not refs:
            errors.append(
                (
                    f"{collection}[{local_id}]" if id_required else f"{collection}[{position}]"
                )
                + " : aucun source_ref valide — "
                "tout élément du Source Map doit être traçable à un SRC"
            )
            continue

        entries.append(
            _Entry(
                local_id=local_id,
                data=item,
                source_refs=refs,
                first_src=src_index[refs[0]],
                position=position,
            )
        )

    entries.sort(key=lambda entry: (entry.first_src, entry.position))

    return entries


def _normalize_source_refs(
    raw: Any,
    src_index: Mapping[str, int],
    *,
    context: str,
    errors: list[str],
) -> tuple[str, ...]:
    """
    Valide, dédoublonne et ordonne les SRC d'un élément.

    Un SRC inexistant (« SRC999999 ») est une ERREUR, pas un champ à retirer :
    le supprimer laisserait croire à une analyse traçable alors que le modèle a
    cité une source imaginaire. Le doublon, lui, est bénin et simplement
    fusionné.
    """
    if raw is None:
        return ()

    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        errors.append(f"{context}.source_refs : une liste est attendue")
        return ()

    unique: dict[str, None] = {}

    for value in raw:
        ref = _text(value)

        if not ref:
            errors.append(f"{context}.source_refs : référence vide")
            continue

        if ref not in src_index:
            errors.append(
                f"{context}.source_refs : « {ref} » n'existe pas dans le "
                "transcript — référence inventée"
            )
            continue

        unique.setdefault(ref, None)

    return tuple(sorted(unique, key=lambda ref: src_index[ref]))


def _assign_ids(
    entries: Sequence[_Entry],
    formatter: Callable[[int], str],
) -> dict[str, str]:
    """
    Associe à chaque identifiant local un identifiant canonique séquentiel.

    Les entrées étant déjà triées, la numérotation est continue, sans trou, et
    suit l'ordre d'apparition dans la source. Les formateurs viennent de
    models.py : la forme des identifiants est définie par le contrat, pas ici.
    """
    return {
        entry.local_id: formatter(position)
        for position, entry in enumerate(entries, start=1)
    }


def _remap(
    raw: Any,
    mapping: Mapping[str, str],
    *,
    context: str,
    target: str,
    errors: list[str],
) -> tuple[str, ...]:
    """
    Réécrit une liste de références internes vers les identifiants canoniques.

    Une référence qui ne correspond à aucun élément déclaré est signalée : un
    `supports_idea_refs: ["IDEA999"]` laissé passer produirait un Source Map
    dont les liens mènent nulle part.
    """
    if raw is None:
        return ()

    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        errors.append(f"{context} : une liste est attendue")
        return ()

    resolved: dict[str, None] = {}

    for value in raw:
        local = _text(value)

        if not local:
            errors.append(f"{context} : référence vide")
            continue

        if local not in mapping:
            errors.append(
                f"{context} : « {local} » ne correspond à aucun élément déclaré "
                f"dans {target} — référence pendante"
            )
            continue

        resolved.setdefault(mapping[local], None)

    # Tri sur l'identifiant canonique : les cibles sont déjà numérotées dans
    # l'ordre de la source, donc l'ordre alphabétique des IDs EST l'ordre de la
    # source. Déterministe sans destruction de progression.
    return tuple(sorted(resolved))


def _remap_relations(
    raw: Any,
    idea_ids: Mapping[str, str],
    *,
    context: str,
    errors: list[str],
) -> tuple[IdeaRelation, ...]:
    """Réécrit les relations d'une idée vers les identifiants canoniques."""
    if raw is None:
        return ()

    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        errors.append(f"{context} : une liste est attendue")
        return ()

    relations: list[IdeaRelation] = []
    seen: set[tuple[str, str]] = set()

    for position, item in enumerate(raw):
        if not isinstance(item, Mapping):
            errors.append(f"{context}[{position}] : un objet est attendu")
            continue

        relation = _text(item.get("relation"))
        target_local = _text(item.get("to_idea"))

        if not relation:
            errors.append(f"{context}[{position}] : relation absente")
            continue

        if target_local not in idea_ids:
            errors.append(
                f"{context}[{position}] : « {target_local} » ne correspond à "
                "aucune idée déclarée — référence pendante"
            )
            continue

        key = (relation, idea_ids[target_local])

        if key in seen:
            continue

        seen.add(key)
        relations.append(IdeaRelation(relation=relation, to_idea=idea_ids[target_local]))

    relations.sort(key=lambda item: (item.to_idea, item.relation))

    return tuple(relations)


# ---------------------------------------------------------------------------
# Blocs descriptifs
# ---------------------------------------------------------------------------

def _build_header(raw: Any) -> SourceAnalysisHeader:
    data = raw if isinstance(raw, Mapping) else {}

    return SourceAnalysisHeader(
        main_theme=_text(data.get("main_theme")),
        author_intent=_build_intent(data.get("author_intent")),
        target_audience=_build_intent(data.get("target_audience")),
    )


def _build_intent(raw: Any) -> IntentStatement:
    data = raw if isinstance(raw, Mapping) else {}

    return IntentStatement(
        summary=_text(data.get("summary")),
        confidence=_text(data.get("confidence")),
        kinds=_text_tuple(data.get("kinds")),
    )


def _build_voice_profile(raw: Any) -> AuthorVoiceProfile:
    data = raw if isinstance(raw, Mapping) else {}

    return AuthorVoiceProfile(
        tone=_text_tuple(data.get("tone")),
        register=_text(data.get("register")),
        sentence_style=_text(data.get("sentence_style")),
        rhetorical_patterns=_text_tuple(data.get("rhetorical_patterns")),
        use_of_questions=_text(data.get("use_of_questions")),
        use_of_repetition=_text(data.get("use_of_repetition")),
        use_of_examples=_text(data.get("use_of_examples")),
        direct_address=_text(data.get("direct_address")),
        teaching_style=_text(data.get("teaching_style")),
        distinctive_traits=_text_tuple(data.get("distinctive_traits")),
    )


def _build_stats(
    transcript: TranscriptInput,
    *,
    topics,
    ideas,
    examples,
    references,
    uncertainties,
    repetitions,
) -> SourceMapStats:
    """
    Compteurs et couverture, tous dérivés du contenu déjà normalisé.

    La couverture mesure la proportion de segments source cités par au moins un
    élément. Elle est DESCRIPTIVE : une source pleine d'hésitations aura
    légitimement moins de 100 %, et le forcer à 100 % obligerait à référencer du
    vide. Elle sert à repérer une analyse anormalement pauvre.
    """
    referenced: set[str] = set()

    for collection in (topics, ideas, examples, references, uncertainties, repetitions):
        for item in collection:
            referenced.update(item.source_refs)

    total = transcript.segment_count
    ratio = round(len(referenced) / total, _COVERAGE_DECIMALS) if total else 0.0

    return SourceMapStats(
        topic_count=len(topics),
        idea_count=len(ideas),
        example_count=len(examples),
        reference_count=len(references),
        uncertainty_count=len(uncertainties),
        repetition_count=len(repetitions),
        source_segment_count=total,
        referenced_source_segments=len(referenced),
        source_coverage_ratio=ratio,
    )


def _text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    return str(value).strip()


def _text_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()

    if isinstance(value, (str, bytes)):
        return (_text(value),) if _text(value) else ()

    if not isinstance(value, Sequence):
        return ()

    return tuple(_text(item) for item in value if _text(item))
