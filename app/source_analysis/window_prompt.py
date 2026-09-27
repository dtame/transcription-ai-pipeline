"""
Prompts versionnés window-analysis-1.0 (historique) et 1.1 (successeur).

Distinct de Prompt 1.3 (SOURCE_ANALYZER_PROMPT_VERSION).
Ne pas modifier prompt.py depuis ce module.
Les blocs 1.0 restent byte-identiques. 1.1 ajoute la granularité.
"""

from __future__ import annotations

from typing import Any

from app.ai.estimation import estimate_tokens
from app.file_utils import content_hash
from app.source_analysis.canonical_vocabulary import (
    build_canonical_vocabulary_contract,
    build_record_field_contract,
)
from app.source_analysis.prompt import (
    FORBIDDEN_STRUCTURE_BLOCK,
    build_language_directive,
    render_segments,
)
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_granularity import (
    HARD_CEILINGS,
    OVERFLOW_TOKEN,
    OVERFLOW_UNCERTAINTY_KIND,
    OVERFLOW_UNCERTAINTY_SEVERITY,
    SOFT_TARGETS,
    SOURCE_REFS_HARD_MAX,
    TEXT_HARD_LIMITS,
    TOTAL_HARD_CEILING,
    TOTAL_SOFT_TARGET,
)
from app.source_analysis_hybrid.constants import (
    ESTIMATION_MODEL,
    WINDOW_PROMPT_VERSION,
    WINDOW_TRANSPORT_VERSION,
)
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_hybrid.materialize import WindowContent, materialize_window_content
from app.source_analysis.window_models import STAGE_WINDOW

WINDOW_ANALYSIS_PROMPT_VERSION_V10 = WINDOW_PROMPT_VERSION
WINDOW_ANALYSIS_PROMPT_VERSION = "window-analysis-1.1"
WINDOW_PROMPT_ROLE = "SOURCE WINDOW ANALYST"
KNOWN_WINDOW_PROMPT_VERSIONS = frozenset(
    {
        WINDOW_ANALYSIS_PROMPT_VERSION_V10,
        WINDOW_ANALYSIS_PROMPT_VERSION,
    }
)


_ROLE_BLOCK = """RÔLE

Tu es SOURCE WINDOW ANALYST. Tu reçois UNE fenêtre de transcription et tu
extraits l'évidence sémantique portée par les sources OWNED de cette fenêtre.

Tu n'es pas :
- l'auteur — tu ne complètes, ne prolonges et n'améliores rien ;
- l'éditeur du livre — tu ne décides d'aucune mise en forme de publication ;
- un planificateur de livre — tu ne proposes ni titre, ni chapitres, ni plan ;
- un vérificateur de faits — tu n'as accès à aucune source externe ;
- un consolidateur global — tu ne tranches pas le thème, l'intention,
  l'audience ou la voix du livre entier.

Tu réponds à une seule question : « que contient et que signifie CETTE
fenêtre, d'après les sources qu'elle possède ? »"""


_WINDOW_SCOPE_BLOCK = """PÉRIMÈTRE DE LA FENÊTRE

Analyse uniquement la fenêtre fournie. N'invente aucun contexte global
manquant. N'extrapole pas au-delà des segments fournis.

Le thème, l'intention, l'audience et la voix que tu observes ici sont des
CANDIDATS / ÉVIDENCES de fenêtre. Ils ne constituent PAS la décision
globale finale du livre. Un thème local n'est pas le thème du livre.

N'émets :
- aucun chapitre, aucune section de livre ;
- aucun titre ni sous-titre de livre ;
- aucun plan éditorial, aucune prose de publication ;
- aucun SourceMap final ;
- aucun identifiant canonique final (TOP001, IDEA001, EX001, REF001,
  UNC001, REP001). Les identités finales seront attribuées plus tard,
  localement, après consolidation."""


_OWNERSHIP_BLOCK = """SOURCES OWNED ET CONTEXT-ONLY

La fenêtre distingue deux ensembles :

OWNED SOURCES — ce sont les seules sources qui peuvent fonder un élément
sémantique substantif (TOPIC, IDEA, EXAMPLE, REFERENCE, UNCERTAINTY,
REPETITION). Chaque record substantif doit citer au moins un SRC owned
qui le porte réellement.

CONTEXT-ONLY SOURCES — contexte de frontière uniquement. Elles aident à
comprendre le bord de la fenêtre. Elles ne créent jamais, à elles seules,
un record substantif. Un record dont tous les source_refs sont
context-only est interdit.

Un record peut citer owned + context SI au moins un SRC owned porte
réellement l'élément.

N'utilise que les identifiants SRC réellement présents ci-dessous.
N'invente jamais un identifiant, même si son numéro tombe entre le
premier et le dernier SRC de la fenêtre. Un SRC supprimé n'existe pas."""


_FIDELITY_BLOCK = """FIDÉLITÉ

Grande liberté d'analyse, liberté sémantique nulle.

Tu as le droit de : identifier, classer, résumer, relier, caractériser,
signaler une incertitude de frontière.

Tu n'as pas le droit de :
- inventer une idée, un argument, un fait, un exemple ou une référence ;
- compléter une pensée avec tes connaissances générales ;
- corriger silencieusement une affirmation ;
- traiter un thème de fenêtre comme vérité globale du livre.

Si l'auteur se trompe, tu décris ce qu'il a dit. Si le bord de fenêtre
coupe une pensée, signale une UNCERTAINTY — n'invente pas la suite."""


_TRACEABILITY_BLOCK = """TRAÇABILITÉ

Chaque segment est précédé de son identifiant :

    [SRC000001 | AUDIO001 | 0.000-11.420]
    texte du segment…

Chaque élément substantif cite les identifiants SRC dont il provient,
dans `s` (source_refs). Préserve les SRC réels. Ne fabrique pas d'intervalle
large. Un élément sans SRC owned n'a pas sa place ici."""


_TASK_HEADER = """TÂCHE

Analyse CETTE fenêtre et réponds en JSON ultra-compact (semantic-transport-v1) :

{"theme":"...","intent":"...","ic":"...","aud":"...","ac":"...","records":[{"k":"...","v":"...","s":[],"l":[],"m":[]}]}

Tous les champs racine sont requis. Jamais null.
theme / intent / aud = CANDIDATS de fenêtre, pas métadonnées globales.
ic / ac = jetons contrôlés `confidence`.
Collections : records locaux seulement. Les liens `l[]` sont des index
locaux de CE transport, pas des identifiants globaux.

Utilise uniquement les jetons du contrat IDENTIFIANTS CONTRÔLÉS.
Copie exacte : aucun synonyme, aucune réparation de casse, aucun trait
d'union inventé, aucune traduction de jeton.

Les questions substantielles = IDEA de kind="question".
Aucune hypothèse sur la personnalité de l'auteur.
Reste sobre : un record par unité réellement distincte.
Une fenêtre peut légitimement n'avoir aucun example, aucune reference,
aucune uncertainty, aucune repetition. N'invente rien pour remplir."""


def _budget_lines() -> str:
    rows = []
    for kind in (
        "TOPIC",
        "IDEA",
        "RELATION",
        "EXAMPLE",
        "REFERENCE",
        "UNCERTAINTY",
        "REPETITION",
        "VOICE",
        "INTENT_KIND",
        "AUDIENCE_KIND",
    ):
        rows.append(f"{kind} cible {SOFT_TARGETS[kind]} / plafond {HARD_CEILINGS[kind]}")
    rows.append(f"TOTAL cible {TOTAL_SOFT_TARGET} / plafond {TOTAL_HARD_CEILING}")
    return "\n".join(rows)


_GRANULARITY_BLOCK = f"""GRANULARITÉ SÉMANTIQUE

Un record = une unité sémantique substantielle DISTINCTE.
Ce n'est pas une phrase, un SRC, un paragraphe, ni une reprise orale.

Regroupe dans CETTE fenêtre les énoncés équivalents ou qui développent
la même idée. Une IDEA ou un TOPIC peut citer PLUSIEURS SRC. Souhaitable.

Le Python local ne fusionne rien. Le regroupement dans la fenêtre est
ton travail. La déduplication entre fenêtres appartient au consolidateur.

VALEURS : énoncé sémantique concis. Pas de citation, pas de réécriture
de paragraphe, pas de récit transcrit.

RELATIONS : seulement les liens nécessaires à la structure.
Interdit : graphe exhaustif, toutes les paires d'idées.

RÉPÉTITIONS : un record par motif répété, pas une paire par occurrence.

QUESTIONS : IDEA kind=question seulement si substantielle.
Témoignages : résumé concis, pas le récit.

COUVERTURE : régions et idées centrales représentées. Tous les SRC
n'ont pas à apparaître. Ne transforme pas chaque phrase mineure en
IDEA minor. Les incertitudes significatives restent.

PRIORITÉ si le budget est serré : thèmes centraux, idées centrales
et de soutien, explications / principes / instructions / questions /
témoignages, exemples utiles, références explicites, incertitudes
significatives — avant remplissage oral et quasi-doublons.

CIBLES SOUPLES / PLAFONDS DURS :
{_budget_lines()}

source_refs : cite les SRC qui portent réellement l'unité. Plusieurs
références encouragées. Pas d'intervalle inventé. Pas toute la fenêtre.
Maximum {SOURCE_REFS_HARD_MAX} SRC par record.

Longueur : TOPIC.v ≤ {TEXT_HARD_LIMITS['TOPIC.v']} ; IDEA.v ≤ {TEXT_HARD_LIMITS['IDEA.v']} ;
EXAMPLE.v ≤ {TEXT_HARD_LIMITS['EXAMPLE.v']} ; REFERENCE.v ≤ {TEXT_HARD_LIMITS['REFERENCE.v']}.

Si une analyse fidèle EXIGE plus que ces plafonds : n'omets pas en
silence. Émets un UNCERTAINTY dont v est EXACTEMENT :
{OVERFLOW_TOKEN}
m=["{OVERFLOW_UNCERTAINTY_KIND}","{OVERFLOW_UNCERTAINTY_SEVERITY}"]
s = au moins un SRC owned. Le résultat ne sera pas READY.

Avant le JSON : vérifie intérieurement (sans rien écrire d'autre)
régions majeures, idées centrales, incertitudes, exemples/références
non surexpansés, répétitions consolidées, plafonds respectés.
Sortie : uniquement le transport demandé. Pas de raisonnement."""


_GRANULARITY_TASK_BLOCK = f"""GRANULARITÉ (rappel)

Unités sémantiques, pas unités SRC. Regroupe dans la fenêtre.
Plusieurs SRC par record encouragés. Pas de graphe exhaustif.
Cibles souples, plafonds durs, total ≤ {TOTAL_HARD_CEILING}.
Si capacité insuffisante : UNCERTAINTY v={OVERFLOW_TOKEN}.
Pas d'omission silencieuse. Pas de faits nouveaux."""


def _system_blocks_v10(primary_language: str) -> list[str]:
    return [
        _ROLE_BLOCK,
        _WINDOW_SCOPE_BLOCK,
        _OWNERSHIP_BLOCK,
        _FIDELITY_BLOCK,
        _TRACEABILITY_BLOCK,
        FORBIDDEN_STRUCTURE_BLOCK,
        build_canonical_vocabulary_contract(),
        build_language_directive(primary_language),
    ]


def resolve_window_prompt_version(version: str | None = None) -> str:
    chosen = version or WINDOW_ANALYSIS_PROMPT_VERSION
    if chosen not in KNOWN_WINDOW_PROMPT_VERSIONS:
        raise ValueError(f"prompt fenêtre inconnu : {chosen!r}")
    return chosen


def build_window_system_prompt(
    primary_language: str,
    *,
    version: str | None = None,
) -> str:
    chosen = resolve_window_prompt_version(version)
    blocks = _system_blocks_v10(primary_language)
    if chosen == WINDOW_ANALYSIS_PROMPT_VERSION:
        blocks = list(blocks)
        blocks.insert(-2, _GRANULARITY_BLOCK)
    return "\n\n".join(blocks)


def build_window_system_prompt_v10(primary_language: str) -> str:
    """Prompt historique 1.0 — byte-identique à la construction d'origine."""
    return build_window_system_prompt(
        primary_language, version=WINDOW_ANALYSIS_PROMPT_VERSION_V10
    )


def _task_instructions(version: str | None = None) -> str:
    chosen = resolve_window_prompt_version(version)
    parts = [_TASK_HEADER]
    if chosen == WINDOW_ANALYSIS_PROMPT_VERSION:
        parts.append(_GRANULARITY_TASK_BLOCK)
    parts.append(build_record_field_contract())
    return "\n\n".join(parts)


def _render_owned_section(content: WindowContent) -> str:
    if not content.owned_segments:
        return "OWNED SOURCES\n\n(none)"
    return "OWNED SOURCES\n\n" + render_segments(content.owned_segments)


def _render_context_section(content: WindowContent) -> str:
    if not content.context_segments:
        return (
            "CONTEXT-ONLY SOURCES\n\n"
            "(none — boundary context empty for this window)\n"
            "These sources, when present, are boundary context only. "
            "They must not be the sole source_refs of a substantive record."
        )
    return (
        "CONTEXT-ONLY SOURCES — boundary context only; "
        "do not create a substantive record from these alone\n\n"
        + render_segments(content.context_segments)
    )


def build_window_user_prompt(
    transcript: TranscriptInput,
    window: WindowInput,
    content: WindowContent | None = None,
    *,
    version: str | None = None,
) -> str:
    materialized = content or materialize_window_content(transcript, window)
    chosen = resolve_window_prompt_version(version)
    return "\n\n".join(
        [
            _task_instructions(chosen),
            build_language_directive(transcript.primary_language),
            (
                f"WINDOW — {window.window_id} — transcript {transcript.transcript_id} — "
                f"{window.owned_src_count} owned SRC, "
                f"{window.context_src_count} context-only SRC"
            ),
            "Ces champs globaux de fenêtre sont des CANDIDATS, pas la vérité du livre.",
            _render_owned_section(materialized),
            _render_context_section(materialized),
        ]
    )


def build_window_user_prompt_v10(
    transcript: TranscriptInput,
    window: WindowInput,
    content: WindowContent | None = None,
) -> str:
    return build_window_user_prompt(
        transcript, window, content, version=WINDOW_ANALYSIS_PROMPT_VERSION_V10
    )


def window_prompt_fingerprint(system_prompt: str, user_prompt: str) -> str:
    return content_hash(
        "\n<<<WINDOW_ANALYZER_SYSTEM>>>\n"
        + (system_prompt or "")
        + "\n<<<WINDOW_ANALYZER_USER>>>\n"
        + (user_prompt or "")
    )


def window_prompt_sha256(system_prompt: str) -> str:
    """SHA du texte système versionné (indépendant du contenu SRC)."""
    return content_hash(system_prompt)


def estimate_window_request_tokens(
    transcript: TranscriptInput,
    window: WindowInput,
    *,
    content: WindowContent | None = None,
    model: str = ESTIMATION_MODEL,
    version: str | None = None,
) -> dict[str, Any]:
    """
    Même estimateur que WindowPlannerV2 : estimate_tokens(system + user).

    Le budget planner et cette requête doivent rester comparables.
    """
    chosen = resolve_window_prompt_version(version)
    materialized = content or materialize_window_content(transcript, window)
    system = build_window_system_prompt(transcript.primary_language, version=chosen)
    user = build_window_user_prompt(transcript, window, materialized, version=chosen)
    framing = "\n\n".join(
        [
            _task_instructions(chosen),
            build_language_directive(transcript.primary_language),
            (
                f"WINDOW — {window.window_id} — transcript {transcript.transcript_id} — "
                f"{window.owned_src_count} owned SRC, "
                f"{window.context_src_count} context-only SRC"
            ),
            "Ces champs globaux de fenêtre sont des CANDIDATS, pas la vérité du livre.",
            _render_owned_section(
                type(materialized)(window_id=window.window_id, owned=(), context=())
            ),
            _render_context_section(
                type(materialized)(window_id=window.window_id, owned=(), context=())
            ),
        ]
    )
    owned_text = render_segments(materialized.owned_segments) if materialized.owned_segments else ""
    context_text = (
        render_segments(materialized.context_segments) if materialized.context_segments else ""
    )
    system_est = estimate_tokens(system, model=model)
    user_est = estimate_tokens(user, model=model)
    framing_est = estimate_tokens(framing, model=model)
    owned_est = estimate_tokens(owned_text, model=model) if owned_text else None
    context_est = estimate_tokens(context_text, model=model) if context_text else None
    total_est = estimate_tokens("\n".join([system, user]), model=model)
    return {
        "model": model,
        "method": total_est.method,
        "estimated": True,
        "system_tokens": system_est.tokens,
        "user_tokens": user_est.tokens,
        "framing_tokens": framing_est.tokens,
        "owned_content_tokens": owned_est.tokens if owned_est else 0,
        "context_content_tokens": context_est.tokens if context_est else 0,
        "total_tokens": total_est.tokens,
        "prompt_version": chosen,
        "transport_version": WINDOW_TRANSPORT_VERSION,
        "stage": STAGE_WINDOW,
    }


__all__ = [
    "KNOWN_WINDOW_PROMPT_VERSIONS",
    "WINDOW_ANALYSIS_PROMPT_VERSION",
    "WINDOW_ANALYSIS_PROMPT_VERSION_V10",
    "WINDOW_PROMPT_ROLE",
    "build_window_system_prompt",
    "build_window_system_prompt_v10",
    "build_window_user_prompt",
    "build_window_user_prompt_v10",
    "estimate_window_request_tokens",
    "resolve_window_prompt_version",
    "window_prompt_fingerprint",
    "window_prompt_sha256",
]
