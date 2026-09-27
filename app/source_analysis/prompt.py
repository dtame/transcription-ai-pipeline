"""
Prompt du Source Analyzer — V2, dédié, versionné.

Aucun prompt V1 n'est réutilisé : ni `clean_transcript`, ni les prompts de
traitement de chunk, ni `global_harmonization_*`. Ces prompts demandent de
RÉÉCRIRE du texte ; celui-ci demande de DÉCRIRE une source. Les mélanger
produirait exactement la dérive que la Phase 3 doit empêcher.

Le prompt n'est pas rangé dans app/prompt_manager.py : ce registre sert les
tâches de réécriture V1, indexées par nom de tâche et surchargeables par un
fichier depot/<projet>/prompt.md. Le prompt d'analyse, lui, est un CONTRAT
versionné qui entre dans la signature de cache — il ne doit pas pouvoir être
remplacé silencieusement par un fichier projet.

    SOURCE_ANALYZER_PROMPT_VERSION       version du contrat de prompt
    STRUCTURAL_VOCABULARY                vocabulaire de livre interdit en sortie
    FORBIDDEN_STRUCTURE_BLOCK            seul endroit où ce vocabulaire apparaît

Cette dernière propriété est vérifiable : hors du bloc d'interdiction, le
prompt ne prononce jamais le mot « chapitre ». Un test le garantit.
"""

from __future__ import annotations

from typing import Iterable

from app.source_analysis.canonical_vocabulary import (
    CURRENT_PROMPT_VERSION,
    build_canonical_vocabulary_contract,
    build_record_field_contract,
)
from app.source_analysis.transcript_input import SourceSegment, TranscriptInput

# Version du contrat de prompt. Toute modification du texte ci-dessous qui
# change ce que le modèle est censé produire doit l'incrémenter — et de toute
# façon, la signature de cache hache le prompt rendu, donc un oubli de bump
# n'entraîne pas de réutilisation abusive d'une ancienne analyse.
SOURCE_ANALYZER_PROMPT_VERSION = CURRENT_PROMPT_VERSION

# Langues nommées explicitement dans la consigne de sortie. Un code absent de
# cette table est cité tel quel : mieux vaut « rédige en « pt-BR » » qu'un nom
# de langue inventé.
_LANGUAGE_NAMES = {
    "fr": "français",
    "en": "anglais",
    "es": "espagnol",
    "de": "allemand",
    "it": "italien",
    "pt": "portugais",
    "nl": "néerlandais",
    "la": "latin",
}

# Vocabulaire de structure de livre. Le Source Analyzer ne doit JAMAIS en
# produire, et son prompt ne doit jamais en demander. Ces termes n'ont le droit
# d'apparaître que dans FORBIDDEN_STRUCTURE_BLOCK, c'est-à-dire pour être
# interdits.
STRUCTURAL_VOCABULARY = (
    "book title",
    "chapitre",
    "chapter",
    "outline",
    "plan du livre",
    "section éditoriale",
    "sommaire",
    "sous-titre",
    "table des matières",
    "table of contents",
    "titre du livre",
)

FORBIDDEN_STRUCTURE_BLOCK = """INTERDICTIONS DE STRUCTURE — FRONTIÈRE ARCHITECTURALE

Ton analyse ne contient AUCUN des éléments suivants, sous aucune forme, sous
aucun nom de champ :

- chapitre, sous-chapitre, section éditoriale
- titre du livre, sous-titre, slogan, accroche
- table des matières, sommaire, plan du livre, outline
- ordre de lecture, progression éditoriale, découpage de publication
- book title, chapter, table of contents

Décider de la structure d'un livre est le travail d'une étape ultérieure, qui
disposera de ton analyse. Si tu proposes un découpage, tu imposes par accident
une structure que personne n'a choisie, à partir d'un découpage technique qui
n'a aucun sens éditorial. Un thème n'est pas un chapitre. Une idée n'est pas
une section. Un segment n'est pas une unité de publication."""


def language_label(code: str) -> str:
    """Nom lisible d'une langue, ou son code si elle n'est pas répertoriée."""
    return _LANGUAGE_NAMES.get(str(code).strip().lower(), f"« {code} »")


def build_language_directive(primary_language: str) -> str:
    """
    Consigne de langue de sortie, dérivée de transcript_data.language.primary.

    L'analyse suit la langue de la source : un transcript français produit des
    résumés français. Traduire automatiquement la source serait déjà une
    transformation, et la Phase 3 ne transforme rien.
    """
    label = language_label(primary_language)

    return (
        f"LANGUE DE SORTIE OBLIGATOIRE : {label} (code « {primary_language} »).\n"
        f"main_theme, author_intent, target_audience, labels, résumés et "
        f"descriptions sont rédigés en {label}.\n"
        "Tu ne traduis pas la source. Les citations, noms propres et références "
        "restent dans leur langue d'origine, même si elle diffère de la langue "
        "de sortie."
    )


def build_system_prompt(primary_language: str) -> str:
    """
    Consigne système du Source Analyzer.

    Trois idées portent tout le reste : fidélité, traçabilité, et refus de la
    casquette d'auteur ou d'éditeur.
    """
    return "\n\n".join(
        [
            _ROLE_BLOCK,
            _FIDELITY_BLOCK,
            _TRACEABILITY_BLOCK,
            _UNCERTAINTY_BLOCK,
            FORBIDDEN_STRUCTURE_BLOCK,
            _GLOBAL_UNDERSTANDING_BLOCK,
            build_canonical_vocabulary_contract(),
            build_language_directive(primary_language),
        ]
    )


_ROLE_BLOCK = """RÔLE

Tu es ANALYSTE DE SOURCE. Tu reçois la transcription d'un discours oral et tu
produis une description structurée de ce qu'elle contient et de ce qu'elle
signifie.

Tu réponds à une seule question : « que contient et que signifie cette
source ? »

Tu n'es pas :
- l'auteur — tu ne complètes, ne prolonges et n'améliores rien ;
- l'éditeur du livre — tu ne décides d'aucune mise en forme de publication ;
- un vérificateur de faits — tu n'as accès à aucune source externe et tu ne
  contrôles pas si l'auteur a raison."""


_FIDELITY_BLOCK = """FIDÉLITÉ — LA RÈGLE LA PLUS IMPORTANTE

Grande liberté d'analyse, liberté sémantique nulle.

Tu as le droit de : identifier, classer, résumer, regrouper, relier,
caractériser, signaler.

Tu n'as pas le droit de :
- inventer une idée, un argument, un fait, un exemple ou une référence ;
- ajouter une citation, un verset, une statistique ou une date absents ;
- compléter une pensée avec tes connaissances générales ;
- corriger silencieusement une affirmation factuelle ou doctrinale ;
- développer ce que l'auteur « aurait probablement voulu dire ».

Si l'auteur se trompe, tu décris ce qu'il a dit. Si l'auteur est vague, tu
restes vague et tu le signales. Le désaccord et le doute se documentent ; ils
ne se réparent pas."""


_TRACEABILITY_BLOCK = """TRAÇABILITÉ

La transcription t'est fournie segment par segment, chacun précédé de son
identifiant :

    [SRC000001 | AUDIO001 | 0.000-11.420]
    texte du segment…

Chaque élément de ton analyse cite les identifiants SRC dont il provient, dans
`source_refs`.

- n'utilise que des SRC réellement présents ci-dessous ;
- n'invente jamais un identifiant, même plausible ;
- cite les segments qui portent réellement l'élément, pas un intervalle large ;
- un élément sans aucun SRC n'a pas sa place dans l'analyse.

Les horodatages servent uniquement à la provenance. Ils ne déterminent ni les
thèmes, ni les idées, ni l'importance : le découpage temporel est un accident
d'enregistrement, pas une organisation du sens."""


_UNCERTAINTY_BLOCK = """INCERTITUDE

L'incertitude est une information, pas un défaut à masquer.

Signale dans `uncertainties` : une transcription ambiguë, un mot probablement
mal transcrit, une référence incomplète, une attribution incertaine, une pensée
interrompue, un sens ambigu, une contradiction apparente.

Exemple décisif : si l'auteur dit « Paul dit quelque part que… », la référence
reste vague. Tu ne la transformes pas en « Romains 8:28 » à partir de ce que tu
sais par ailleurs. Tu enregistres la référence telle qu'elle a été prononcée,
avec completeness="vague", et tu ajoutes une incertitude."""


_GLOBAL_UNDERSTANDING_BLOCK = """COMPRÉHENSION GLOBALE

La transcription t'est donnée en entier. Lis-la d'abord dans son ensemble, puis
analyse-la comme un tout.

Un thème qui revient en début et en fin est un seul thème. Une idée reprise
trois fois est une idée avec des reprises — et ces reprises ne sont pas
forcément des doublons : une affirmation, puis son développement, puis son
application constituent une progression voulue. Qualifie le caractère de la
reprise au lieu de la déclarer redondante.

Ne supprime rien, ne fusionne rien de ce qui est réellement distinct."""


_TASK_HEADER = """TÂCHE

Analyse la transcription et réponds en JSON ultra-compact (semantic-transport-v1) :

{"theme":"...","intent":"...","ic":"...","aud":"...","ac":"...","records":[{"k":"...","v":"...","s":[],"l":[],"m":[]}]}

Tous les champs sont requis. Jamais null. Si un champ de record ne s'applique
pas : s=[], l=[], m=[] ; v="" seulement pour un VOICE scalaire non observé.

theme = source_analysis.main_theme : sujet dominant, DESCRIPTION neutre.
Collections canoniques reconstruites : topics, ideas, examples, references,
uncertainties, repetitions, author_voice_profile — plus author_intent et
target_audience.
« Le rôle de la foi dans la manière de traverser les épreuves » est correct.
« Libérez la puissance extraordinaire de votre foi » est un slogan : refusé.
intent / ic = author_intent.summary / confidence — jeton contrôlé `confidence`.
aud / ac = target_audience.summary / confidence. Seulement ce que le discours
permet d'inférer.

Les identifiants contrôlés sont des jetons de protocole. Utilise uniquement
ceux du contrat IDENTIFIANTS CONTRÔLÉS. Les questions substantielles =
IDEA de kind="question".
Il n'existe pas d'autre emplacement pour elles.

Aucune hypothèse sur la personnalité ou l'état d'esprit de l'auteur, et aucun
conseil d'amélioration : tu constates.

Reste sobre : un record par unité réellement distincte."""


def _task_instructions() -> str:
    return _TASK_HEADER + "\n\n" + build_record_field_contract()


def render_segment(segment: SourceSegment) -> str:
    """Un segment source, en-tête de provenance puis texte."""
    return (
        f"[{segment.src_id} | {segment.source_id} | "
        f"{segment.start:.3f}-{segment.end:.3f}]\n"
        f"{segment.text}"
    )


def render_segments(segments: Iterable[SourceSegment]) -> str:
    """
    Représentation compacte mais traçable de la transcription.

    Le JSON canonique n'est PAS envoyé tel quel : sa décoration (clés répétées,
    source_order, accolades) coûterait du contexte sans rien apporter au
    modèle. Ce qui est obligatoirement conservé, c'est l'identifiant SRC de
    chaque segment — sans lui, aucune citation exacte n'est possible.
    """
    return "\n\n".join(render_segment(segment) for segment in segments)


def build_user_prompt(
    transcript: TranscriptInput,
    segments: Iterable[SourceSegment] | None = None,
) -> str:
    """
    Prompt utilisateur : consignes de tâche, puis la transcription.

    `segments` permet de soumettre un sous-ensemble (fenêtre technique) sans
    dupliquer la construction du prompt. Par défaut, la transcription entière.
    """
    chosen = tuple(segments) if segments is not None else transcript.segments

    return "\n\n".join(
        [
            _task_instructions(),
            build_language_directive(transcript.primary_language),
            (
                f"TRANSCRIPTION — {transcript.transcript_id} — "
                f"{len(chosen)} segment(s) source"
            ),
            render_segments(chosen),
        ]
    )
