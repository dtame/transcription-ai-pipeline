"""
Contrat interne de source_map.json — Phase 3.

Ce module définit CE QUE LE SOURCE MAP EST, et rien d'autre : pas d'appel IA,
pas de fichier, pas de prompt. C'est l'équivalent pour la Phase 3 de ce que
app/transcript_models.py est pour la Phase 1.

Frontière architecturale stricte (Phase 3 / Phase 4) :

    ce module décrit          ce module ne décrit JAMAIS
    ----------------          --------------------------
    thème dominant            titre de livre
    intention apparente       sous-titre
    audience apparente        angle éditorial
    thèmes (TOP)              chapitres
    idées (IDEA)              sections
    exemples (EX)             table des matières
    références (REF)          ordre éditorial
    incertitudes (UNC)        plan du livre
    répétitions (REP)
    voix de l'auteur

Le Source Analyzer répond à « que contient et que signifie cette source ? ».
Il ne répond pas à « comment en faire un livre ? » : c'est la Phase 4.

Versionnement : SOURCE_MAP_SCHEMA_VERSION est le contrat de CE fichier. Il est
volontairement indépendant de app.transcript_models.SCHEMA_VERSION — ce sont
deux contrats différents, qui évolueront à des rythmes différents.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

# Version du contrat source_map.json. N'hérite PAS de la version Transcript V2.
SOURCE_MAP_SCHEMA_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Identifiants
# ---------------------------------------------------------------------------
#
# Même politique que SRC/AUDIO de la Phase 1 : séquentiels, préfixés, à largeur
# fixe. Séquentiels et non aléatoires pour que deux analyses du même transcript
# produisent un fichier diffable, et pour qu'un humain puisse citer « IDEA004 »
# dans une discussion.
#
# Les identifiants produits par le modèle ne sont JAMAIS repris tels quels :
# ils servent uniquement de clés de correspondance lors de la normalisation
# (voir app/source_analysis/normalizer.py).

def format_topic_id(index: int) -> str:
    """Identifiant d'un thème : TOP001, TOP002, …"""
    return f"TOP{index:03d}"


def format_idea_id(index: int) -> str:
    """Identifiant d'une idée : IDEA001, IDEA002, …"""
    return f"IDEA{index:03d}"


def format_example_id(index: int) -> str:
    """Identifiant d'un exemple / illustration / anecdote : EX001, EX002, …"""
    return f"EX{index:03d}"


def format_reference_id(index: int) -> str:
    """Identifiant d'une référence citée par l'auteur : REF001, REF002, …"""
    return f"REF{index:03d}"


def format_uncertainty_id(index: int) -> str:
    """Identifiant d'une incertitude : UNC001, UNC002, …"""
    return f"UNC{index:03d}"


def format_repetition_id(index: int) -> str:
    """Identifiant d'une répétition : REP001, REP002, …"""
    return f"REP{index:03d}"


# ---------------------------------------------------------------------------
# Vocabulaires fermés
# ---------------------------------------------------------------------------
#
# Volontairement courts. Une taxonomie de cinquante étiquettes serait ingérable
# à valider et inutilisable par la Phase 4 : mieux vaut peu de catégories
# réellement distinctes.

IDEA_KINDS = (
    "claim",
    "explanation",
    "principle",
    "instruction",
    "observation",
    "question",
    "testimony",
)

# Les questions substantielles de l'orateur sont représentées par une IDEE de
# kind="question" — et par RIEN d'autre. Décision explicite (§23 du cahier des
# charges) : une seule représentation, pas de collection `questions` concurrente
# qui obligerait ensuite à choisir laquelle fait foi.

IMPORTANCE_LEVELS = (
    "central",
    "supporting",
    "minor",
)

EXAMPLE_KINDS = (
    "example",
    "illustration",
    "analogy",
    "anecdote",
    "testimony",
    "case_study",
)

REFERENCE_KINDS = (
    "biblical",
    "book",
    "author",
    "person",
    "study",
    "concept",
    "event",
    "work",
    "quotation",
    "other",
)

# Complétude d'une référence TELLE QUE L'AUTEUR L'A DONNÉE. « Paul dit quelque
# part » reste "vague" : le Source Analyzer ne comble jamais une référence avec
# ses propres connaissances.
REFERENCE_COMPLETENESS = (
    "complete",
    "partial",
    "vague",
)

UNCERTAINTY_KINDS = (
    "ambiguous_transcription",
    "possible_wrong_word",
    "incomplete_reference",
    "uncertain_attribution",
    "interrupted_thought",
    "ambiguous_meaning",
    "apparent_contradiction",
    "verification_needed",
)

SEVERITY_LEVELS = (
    "low",
    "medium",
    "high",
)

# Caractère d'une reprise. « accidental » et « oral » sont des scories ;
# « rhetorical », « recap » et « development » sont des procédés volontaires.
# La distinction existe parce que deux passages proches ne sont pas forcément
# des doublons : la Phase 4 décidera quoi fusionner, la Phase 3 documente.
REPETITION_CHARACTERS = (
    "accidental",
    "oral",
    "rhetorical",
    "recap",
    "development",
)

RELATION_KINDS = (
    "supports",
    "explains",
    "illustrates",
    "contrasts_with",
    "develops",
    "qualifies",
)

CONFIDENCE_LEVELS = (
    "high",
    "medium",
    "low",
)

# Stratégies de contexte possibles (voir context_strategy.py).
STRATEGY_GLOBAL = "global"
STRATEGY_WINDOWED = "windowed"


# ---------------------------------------------------------------------------
# Lecture défensive d'un payload
# ---------------------------------------------------------------------------
#
# Employées par les `from_dict` : elles CONVERTISSENT sans jamais compléter.
# Un champ manquant devient vide ou nul, jamais une valeur plausible, pour que
# le validateur puisse refuser ce qui doit l'être.

def _read_text(data: Mapping, key: str) -> str:
    if not isinstance(data, Mapping):
        return ""

    value = data.get(key)

    if value is None:
        return ""

    return value.strip() if isinstance(value, str) else str(value).strip()


def _read_text_tuple(data: Mapping, key: str) -> tuple[str, ...]:
    if not isinstance(data, Mapping):
        return ()

    value = data.get(key)

    if not isinstance(value, (list, tuple)):
        return ()

    return tuple(
        item.strip() if isinstance(item, str) else str(item)
        for item in value
        if item is not None
    )


def _read_mapping(data: Mapping, key: str) -> Mapping:
    if not isinstance(data, Mapping):
        return {}

    value = data.get(key)

    return value if isinstance(value, Mapping) else {}


def _read_int(data: Mapping, key: str) -> int:
    if not isinstance(data, Mapping):
        return 0

    try:
        return int(data.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _read_float(data: Mapping, key: str) -> float:
    if not isinstance(data, Mapping):
        return 0.0

    try:
        return float(data.get(key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _read_items(data: Mapping, key: str, factory) -> tuple:
    if not isinstance(data, Mapping):
        return ()

    value = data.get(key)

    if not isinstance(value, (list, tuple)):
        return ()

    return tuple(
        factory.from_dict(item) for item in value if isinstance(item, Mapping)
    )


# ---------------------------------------------------------------------------
# Éléments du Source Map
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Topic:
    """
    Domaine thématique récurrent ou substantiel de la source.

    Un topic n'est PAS un chapitre : il ne porte ni ordre éditorial, ni
    hiérarchie, ni intention de publication.
    """

    topic_id: str
    label: str
    summary: str
    source_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "label": self.label,
            "summary": self.summary,
            "source_refs": list(self.source_refs),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "Topic":
        return cls(
            topic_id=_read_text(data, "topic_id"),
            label=_read_text(data, "label"),
            summary=_read_text(data, "summary"),
            source_refs=_read_text_tuple(data, "source_refs"),
        )


@dataclass(frozen=True)
class IdeaRelation:
    """
    Lien orienté entre deux idées de la source.

    Porté par l'idée de départ plutôt que par une collection `relations` de
    premier niveau : une idée et ses liens se lisent d'un seul coup d'œil, et
    on évite un graphe séparé à maintenir en cohérence.
    """

    relation: str
    to_idea: str

    def to_dict(self) -> dict:
        return {
            "relation": self.relation,
            "to_idea": self.to_idea,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "IdeaRelation":
        return cls(
            relation=_read_text(data, "relation"),
            to_idea=_read_text(data, "to_idea"),
        )


@dataclass(frozen=True)
class Idea:
    """
    Unité de sens substantielle exprimée par l'auteur.

    `importance` décrit le poids de l'idée DANS LA SOURCE (temps consacré,
    reprises, mise en évidence par l'orateur, rôle dans le raisonnement), et
    non l'intérêt que l'IA lui trouve.

    `kind` (claim / explanation / …) is optional at publication when local
    extraction used semantic-transport-v3.1-local-lite. Absence is empty
    string. A present value must still belong to IDEA_KINDS. Importance is
    never a kind.
    """

    idea_id: str
    summary: str
    kind: str
    importance: str
    topic_refs: tuple[str, ...] = ()
    relations: tuple[IdeaRelation, ...] = ()
    source_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "idea_id": self.idea_id,
            "summary": self.summary,
            "kind": self.kind,
            "importance": self.importance,
            "topic_refs": list(self.topic_refs),
            "relations": [relation.to_dict() for relation in self.relations],
            "source_refs": list(self.source_refs),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "Idea":
        raw_relations = data.get("relations")
        relations = (
            tuple(
                IdeaRelation.from_dict(item)
                for item in raw_relations
                if isinstance(item, Mapping)
            )
            if isinstance(raw_relations, list)
            else ()
        )

        return cls(
            idea_id=_read_text(data, "idea_id"),
            summary=_read_text(data, "summary"),
            kind=_read_text(data, "kind"),
            importance=_read_text(data, "importance"),
            topic_refs=_read_text_tuple(data, "topic_refs"),
            relations=relations,
            source_refs=_read_text_tuple(data, "source_refs"),
        )


@dataclass(frozen=True)
class Example:
    """
    Exemple, illustration, analogie, anecdote, témoignage ou cas pratique.

    Séparé des idées à dessein : un exemple sert une idée, il n'en est pas une.
    Le promouvoir automatiquement en idée principale déformerait la source.
    """

    example_id: str
    kind: str
    summary: str
    supports_idea_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "example_id": self.example_id,
            "kind": self.kind,
            "summary": self.summary,
            "supports_idea_refs": list(self.supports_idea_refs),
            "source_refs": list(self.source_refs),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "Example":
        return cls(
            example_id=_read_text(data, "example_id"),
            kind=_read_text(data, "kind"),
            summary=_read_text(data, "summary"),
            supports_idea_refs=_read_text_tuple(data, "supports_idea_refs"),
            source_refs=_read_text_tuple(data, "source_refs"),
        )


@dataclass(frozen=True)
class Reference:
    """
    Référence explicitement présente dans la source.

    `raw_reference` est ce que l'auteur a dit. `normalized_reference` se limite
    à une mise en forme de CE QUI A ÉTÉ DIT : jamais un complètement depuis des
    connaissances externes. « Paul dit quelque part » ne devient pas
    « Romains 8:28 » — l'incertitude est conservée, et signalée via une UNC.
    """

    reference_id: str
    kind: str
    raw_reference: str
    normalized_reference: str
    completeness: str
    source_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "reference_id": self.reference_id,
            "kind": self.kind,
            "raw_reference": self.raw_reference,
            "normalized_reference": self.normalized_reference,
            "completeness": self.completeness,
            "source_refs": list(self.source_refs),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "Reference":
        return cls(
            reference_id=_read_text(data, "reference_id"),
            kind=_read_text(data, "kind"),
            raw_reference=_read_text(data, "raw_reference"),
            normalized_reference=_read_text(data, "normalized_reference"),
            completeness=_read_text(data, "completeness"),
            source_refs=_read_text_tuple(data, "source_refs"),
        )


@dataclass(frozen=True)
class Uncertainty:
    """
    Point que le Source Analyzer signale SANS le résoudre.

    Transcription ambiguë, mot douteux, référence incomplète, attribution
    incertaine, pensée interrompue, contradiction apparente. Résoudre
    silencieusement une de ces zones serait une invention.
    """

    uncertainty_id: str
    kind: str
    description: str
    severity: str
    source_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "uncertainty_id": self.uncertainty_id,
            "kind": self.kind,
            "description": self.description,
            "severity": self.severity,
            "source_refs": list(self.source_refs),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "Uncertainty":
        return cls(
            uncertainty_id=_read_text(data, "uncertainty_id"),
            kind=_read_text(data, "kind"),
            description=_read_text(data, "description"),
            severity=_read_text(data, "severity"),
            source_refs=_read_text_tuple(data, "source_refs"),
        )


@dataclass(frozen=True)
class Repetition:
    """
    Reprise sémantique entre plusieurs idées de la source.

    Rien n'est supprimé en Phase 3. `character` dit s'il s'agit d'une scorie
    orale ou d'une progression voulue (affirmation, puis développement, puis
    application) : c'est la Phase 4 qui décidera quoi fusionner.
    """

    repetition_id: str
    character: str
    description: str
    idea_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "repetition_id": self.repetition_id,
            "character": self.character,
            "description": self.description,
            "idea_refs": list(self.idea_refs),
            "source_refs": list(self.source_refs),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "Repetition":
        return cls(
            repetition_id=_read_text(data, "repetition_id"),
            character=_read_text(data, "character"),
            description=_read_text(data, "description"),
            idea_refs=_read_text_tuple(data, "idea_refs"),
            source_refs=_read_text_tuple(data, "source_refs"),
        )


@dataclass(frozen=True)
class IntentStatement:
    """
    Élément interprétatif assorti d'un niveau de confiance.

    Sert à author_intent et target_audience : l'incertitude doit être
    REPRÉSENTABLE plutôt que gommée par une affirmation nette. Une intention
    ambiguë se déclare confidence="low", elle ne se devine pas.
    """

    summary: str
    confidence: str
    kinds: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "confidence": self.confidence,
            "kinds": list(self.kinds),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "IntentStatement":
        return cls(
            summary=_read_text(data, "summary"),
            confidence=_read_text(data, "confidence"),
            kinds=_read_text_tuple(data, "kinds"),
        )


@dataclass(frozen=True)
class SourceAnalysisHeader:
    """
    Lecture globale de la source : sujet dominant, intention, audience.

    `main_theme` DÉCRIT le sujet dominant ; ce n'est pas un titre, pas un
    slogan, pas une promesse commerciale. « Le rôle de la foi dans la manière
    de traverser les épreuves », pas « Libérez la puissance de votre foi ».
    """

    main_theme: str
    author_intent: IntentStatement
    target_audience: IntentStatement

    def to_dict(self) -> dict:
        return {
            "main_theme": self.main_theme,
            "author_intent": self.author_intent.to_dict(),
            "target_audience": self.target_audience.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "SourceAnalysisHeader":
        return cls(
            main_theme=_read_text(data, "main_theme"),
            author_intent=IntentStatement.from_dict(_read_mapping(data, "author_intent")),
            target_audience=IntentStatement.from_dict(
                _read_mapping(data, "target_audience")
            ),
        )


@dataclass(frozen=True)
class AuthorVoiceProfile:
    """
    Description des caractéristiques ORALES ET TEXTUELLES observées.

    Deux interdits structurants :

    1. aucun diagnostic psychologique — pas de personnalité, pas d'état mental,
       pas d'intention cachée ; seulement ce que le texte montre ;
    2. aucune consigne de réécriture — « improve by… », « should avoid… »,
       « rewrite as… » n'ont rien à faire ici. Ce n'est pas encore un guide de
       style, c'est un constat.
    """

    tone: tuple[str, ...] = ()
    register: str = ""
    sentence_style: str = ""
    rhetorical_patterns: tuple[str, ...] = ()
    use_of_questions: str = ""
    use_of_repetition: str = ""
    use_of_examples: str = ""
    direct_address: str = ""
    teaching_style: str = ""
    distinctive_traits: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "tone": list(self.tone),
            "register": self.register,
            "sentence_style": self.sentence_style,
            "rhetorical_patterns": list(self.rhetorical_patterns),
            "use_of_questions": self.use_of_questions,
            "use_of_repetition": self.use_of_repetition,
            "use_of_examples": self.use_of_examples,
            "direct_address": self.direct_address,
            "teaching_style": self.teaching_style,
            "distinctive_traits": list(self.distinctive_traits),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "AuthorVoiceProfile":
        return cls(
            tone=_read_text_tuple(data, "tone"),
            register=_read_text(data, "register"),
            sentence_style=_read_text(data, "sentence_style"),
            rhetorical_patterns=_read_text_tuple(data, "rhetorical_patterns"),
            use_of_questions=_read_text(data, "use_of_questions"),
            use_of_repetition=_read_text(data, "use_of_repetition"),
            use_of_examples=_read_text(data, "use_of_examples"),
            direct_address=_read_text(data, "direct_address"),
            teaching_style=_read_text(data, "teaching_style"),
            distinctive_traits=_read_text_tuple(data, "distinctive_traits"),
        )


@dataclass(frozen=True)
class SourceMapStats:
    """
    Compteurs et couverture, tous DÉRIVÉS du contenu du Source Map.

    Aucun horodatage : deux analyses identiques doivent produire deux fichiers
    identiques octet pour octet, ce qu'un `generated_at` rendrait impossible.

    `source_coverage_ratio` est descriptif, pas normatif : des hésitations et
    des passages sans contenu substantiel peuvent légitimement n'être
    référencés par rien. La métrique sert à repérer une analyse anormalement
    pauvre, pas à exiger 100 %.
    """

    topic_count: int
    idea_count: int
    example_count: int
    reference_count: int
    uncertainty_count: int
    repetition_count: int
    source_segment_count: int
    referenced_source_segments: int
    source_coverage_ratio: float

    def to_dict(self) -> dict:
        return {
            "topic_count": self.topic_count,
            "idea_count": self.idea_count,
            "example_count": self.example_count,
            "reference_count": self.reference_count,
            "uncertainty_count": self.uncertainty_count,
            "repetition_count": self.repetition_count,
            "source_segment_count": self.source_segment_count,
            "referenced_source_segments": self.referenced_source_segments,
            "source_coverage_ratio": self.source_coverage_ratio,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "SourceMapStats":
        return cls(
            topic_count=_read_int(data, "topic_count"),
            idea_count=_read_int(data, "idea_count"),
            example_count=_read_int(data, "example_count"),
            reference_count=_read_int(data, "reference_count"),
            uncertainty_count=_read_int(data, "uncertainty_count"),
            repetition_count=_read_int(data, "repetition_count"),
            source_segment_count=_read_int(data, "source_segment_count"),
            referenced_source_segments=_read_int(data, "referenced_source_segments"),
            source_coverage_ratio=_read_float(data, "source_coverage_ratio"),
        )


@dataclass(frozen=True)
class AnalysisProvenance:
    """
    Provenance de l'analyse, embarquée dans le fichier publié.

    Tous les champs sont déterministes : ils décrivent AVEC QUOI l'analyse a
    été produite (version de prompt, de schéma, provider, modèle, stratégie,
    signature de cache), jamais QUAND. C'est ce qui permet de vérifier la
    validité du cache en relisant le seul source_map.json, sans dépendre de
    project_state.json.
    """

    prompt_version: str
    schema_version: str
    provider: str
    model: str
    strategy: str
    signature: str

    def to_dict(self) -> dict:
        return {
            "prompt_version": self.prompt_version,
            "schema_version": self.schema_version,
            "provider": self.provider,
            "model": self.model,
            "strategy": self.strategy,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "AnalysisProvenance":
        return cls(
            prompt_version=_read_text(data, "prompt_version"),
            schema_version=_read_text(data, "schema_version"),
            provider=_read_text(data, "provider"),
            model=_read_text(data, "model"),
            strategy=_read_text(data, "strategy"),
            signature=_read_text(data, "signature"),
        )


@dataclass(frozen=True)
class SourceMap:
    """
    Représentation complète et publiable de la compréhension de la source.

    `to_dict()` fixe l'ordre des clés de premier niveau : le JSON publié est un
    artefact que des humains relisent et que git diffe.
    """

    transcript_id: str
    project_name: str
    primary_language: str
    source_analysis: SourceAnalysisHeader
    topics: tuple[Topic, ...]
    ideas: tuple[Idea, ...]
    examples: tuple[Example, ...]
    references: tuple[Reference, ...]
    uncertainties: tuple[Uncertainty, ...]
    repetitions: tuple[Repetition, ...]
    author_voice_profile: AuthorVoiceProfile
    stats: SourceMapStats
    analysis: AnalysisProvenance
    schema_version: str = SOURCE_MAP_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "transcript_id": self.transcript_id,
            "project": {
                "name": self.project_name,
            },
            "language": {
                "primary": self.primary_language,
            },
            "source_analysis": self.source_analysis.to_dict(),
            "topics": [topic.to_dict() for topic in self.topics],
            "ideas": [idea.to_dict() for idea in self.ideas],
            "examples": [example.to_dict() for example in self.examples],
            "references": [reference.to_dict() for reference in self.references],
            "uncertainties": [item.to_dict() for item in self.uncertainties],
            "repetitions": [item.to_dict() for item in self.repetitions],
            "author_voice_profile": self.author_voice_profile.to_dict(),
            "stats": self.stats.to_dict(),
            "analysis": self.analysis.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "SourceMap":
        """
        Relit un source_map.json publié.

        Sert à deux choses : revalider une analyse mise en cache avec le MÊME
        validateur que celui d'une analyse fraîche (plutôt qu'un second contrôle
        approximatif qui divergerait), et donner à la Phase 4 un lecteur du
        contrat sans qu'elle ait à réinterpréter le JSON.

        Aucune valeur par défaut « réparatrice » : un champ absent devient vide,
        et c'est le validateur qui le refuse. Un lecteur ne doit pas rendre
        valide un fichier qui ne l'est pas.
        """
        return cls(
            schema_version=_read_text(data, "schema_version"),
            transcript_id=_read_text(data, "transcript_id"),
            project_name=_read_text(_read_mapping(data, "project"), "name"),
            primary_language=_read_text(_read_mapping(data, "language"), "primary"),
            source_analysis=SourceAnalysisHeader.from_dict(
                _read_mapping(data, "source_analysis")
            ),
            topics=_read_items(data, "topics", Topic),
            ideas=_read_items(data, "ideas", Idea),
            examples=_read_items(data, "examples", Example),
            references=_read_items(data, "references", Reference),
            uncertainties=_read_items(data, "uncertainties", Uncertainty),
            repetitions=_read_items(data, "repetitions", Repetition),
            author_voice_profile=AuthorVoiceProfile.from_dict(
                _read_mapping(data, "author_voice_profile")
            ),
            stats=SourceMapStats.from_dict(_read_mapping(data, "stats")),
            analysis=AnalysisProvenance.from_dict(_read_mapping(data, "analysis")),
        )

    def all_source_refs(self) -> tuple[str, ...]:
        """
        Tous les SRC cités par le Source Map, dédoublonnés, en ordre canonique
        d'apparition dans les collections déjà normalisées.
        """
        seen: dict[str, None] = {}

        collections: Sequence[Sequence] = (
            self.topics,
            self.ideas,
            self.examples,
            self.references,
            self.uncertainties,
            self.repetitions,
        )

        for collection in collections:
            for item in collection:
                for ref in item.source_refs:
                    seen.setdefault(ref, None)

        return tuple(seen)

    def declared_ids(self) -> dict[str, tuple[str, ...]]:
        """Identifiants déclarés par catégorie, dans l'ordre du fichier."""
        return {
            "topics": tuple(topic.topic_id for topic in self.topics),
            "ideas": tuple(idea.idea_id for idea in self.ideas),
            "examples": tuple(example.example_id for example in self.examples),
            "references": tuple(item.reference_id for item in self.references),
            "uncertainties": tuple(item.uncertainty_id for item in self.uncertainties),
            "repetitions": tuple(item.repetition_id for item in self.repetitions),
        }


# ---------------------------------------------------------------------------
# Champs éditoriaux interdits
# ---------------------------------------------------------------------------
#
# Barrière architecturale entre Phase 3 et Phase 4, appliquée par le validateur
# (voir validator.py). Un modèle qui renvoie `chapters` a mal compris son rôle,
# et publier ce fichier contaminerait le Source Map avec une structure de livre
# décidée par hasard. Les chunks techniques ne doivent jamais devenir des
# chapitres — c'est précisément l'erreur de la V1.

FORBIDDEN_EDITORIAL_FIELDS = (
    "book_subtitle",
    "book_title",
    "chapter_titles",
    "chapters",
    "editorial_plan",
    "outline",
    "section_titles",
    "sections",
    "subchapters",
    "table_of_contents",
    "toc",
)


# Singular / nested structural aliases inspected in addition to the canonical
# top-level names. These are KEY names, never substrings of semantic text.
EXTRA_STRUCTURAL_EDITORIAL_KEYS = (
    "book_part",
    "book_parts",
    "chapter",
    "chapter_title",
    "editorial_structure",
    "section",
)


def editorial_structure_key_set() -> frozenset[str]:
    return frozenset(FORBIDDEN_EDITORIAL_FIELDS + EXTRA_STRUCTURAL_EDITORIAL_KEYS)


def _walk_editorial_keys(payload: object) -> set[str]:
    found: set[str] = set()
    keys = editorial_structure_key_set()

    def _walk(node: object) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                name = str(key)
                if name in keys or name in FORBIDDEN_EDITORIAL_FIELDS:
                    found.add(name)
                _walk(value)
        elif isinstance(node, (list, tuple)):
            for item in node:
                _walk(item)

    _walk(payload)
    return found


def forbidden_editorial_fields(payload: Mapping) -> tuple[str, ...]:
    """Champs éditoriaux interdits, y compris imbriqués, en ordre stable.

    Inspecte les *clés* d'objets/tableaux, jamais le texte sémantique.
    Un IDEA dont le résumé contient « chapter 17 » n'est pas une structure
    de livre.
    """
    if not isinstance(payload, Mapping):
        return ()

    found = _walk_editorial_keys(payload)
    return tuple(
        name
        for name in FORBIDDEN_EDITORIAL_FIELDS + EXTRA_STRUCTURAL_EDITORIAL_KEYS
        if name in found
    )


def scan_editorial_structure(payload: object) -> dict:
    """Scanner structurel : objets, clés, hiérarchie. Pas de ban lexical."""
    hits: list[dict[str, str]] = []
    keys = editorial_structure_key_set()

    def _walk(node: object, path: str) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                name = str(key)
                loc = f"{path}.{name}" if path else name
                if name in keys:
                    hits.append({"path": loc, "key": name, "kind": "structural_key"})
                _walk(value, loc)
        elif isinstance(node, (list, tuple)):
            for index, item in enumerate(node):
                _walk(item, f"{path}[{index}]")

    _walk(payload, "$")
    ordered = tuple(
        name
        for name in FORBIDDEN_EDITORIAL_FIELDS + EXTRA_STRUCTURAL_EDITORIAL_KEYS
        if name in {hit["key"] for hit in hits}
    )
    return {
        "ok": not hits,
        "status": "PASS" if not hits else "FAIL",
        "hits": hits,
        "keys": ordered,
        "mode": "STRUCTURAL",
        "scans_text_values": False,
    }
