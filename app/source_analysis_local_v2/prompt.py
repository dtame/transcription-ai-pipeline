"""
window-analysis-1.2 — extraction sémantique LOCALE.

Ne modifie pas window-analysis-1.0 / 1.1.
Distinct du prompt global SOURCE_ANALYZER 1.2 / 1.3.
"""

from __future__ import annotations

from typing import Any

from app.ai.estimation import estimate_tokens
from app.file_utils import content_hash
from app.source_analysis.canonical_vocabulary import (
    EXAMPLE_KINDS,
    IDEA_KINDS,
    IMPORTANCE_LEVELS,
    REFERENCE_COMPLETENESS,
    REFERENCE_KINDS,
    RELATION_KINDS,
    SEVERITY_LEVELS,
    UNCERTAINTY_KINDS,
)
from app.source_analysis.models import CONFIDENCE_LEVELS
from app.source_analysis.prompt import (
    FORBIDDEN_STRUCTURE_BLOCK,
    build_language_directive,
    render_segments,
)
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.constants import ESTIMATION_MODEL
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_hybrid.materialize import WindowContent, materialize_window_content
from app.source_analysis_local_v2.constants import (
    CANDIDATE_WINDOW_ANALYSIS_PROMPT_VERSION,
    DEFERRED_KINDS,
    HARD_CEILINGS,
    LOCAL_KINDS,
    OVERFLOW_TOKEN,
    OVERFLOW_UNCERTAINTY_KIND,
    OVERFLOW_UNCERTAINTY_SEVERITY,
    SEMANTIC_TRANSPORT_VERSION_V2,
    SOFT_TARGETS,
    SOURCE_REFS_HARD_MAX,
    TOTAL_HARD_CEILING,
    TOTAL_SOFT_TARGET,
    WINDOW_ANALYSIS_PROMPT_VERSION_V12,
    WINDOW_ANALYSIS_PROMPT_VERSION_V121,
)
from app.source_analysis_local_v2.granularity import TEXT_HARD_LIMITS

WINDOW_PROMPT_ROLE = "LOCAL SEMANTIC EXTRACTOR"


def _budget_lines() -> str:
    rows = [f"{kind} cible {SOFT_TARGETS[kind]} / plafond {HARD_CEILINGS[kind]}" for kind in LOCAL_KINDS]
    rows.append(f"TOTAL cible {TOTAL_SOFT_TARGET} / plafond {TOTAL_HARD_CEILING}")
    return "\n".join(rows)


_ROLE_BLOCK = """RÔLE

Tu es LOCAL SEMANTIC EXTRACTOR. Ceci est une EXTRACTION SÉMANTIQUE LOCALE
d'UNE fenêtre source.

Tu n'es PAS :
- un analyste global de la source entière ;
- un planificateur éditorial ;
- un générateur de livre ;
- un consolidateur ;
- l'auteur.

Tu extraits uniquement le matériau sémantique porté par les sources OWNED
de CETTE fenêtre."""


_SCOPE_BLOCK = """PÉRIMÈTRE

LOCAL, pas global. Pas d'analyse de livre. Pas de planification éditoriale.
Pas de génération de livre.

theme / intent / aud sont des NOTES LOCALES compactes, pas les métadonnées
finales du livre. L'intention d'auteur finale, l'audience finale et la voix
finale sont GLOBALES — ne les déclare pas ici comme records.

N'émets aucun record REPETITION, VOICE, INTENT_KIND, AUDIENCE_KIND.
Ces catégories sont différées : récupération globale ultérieure."""


_COMPACT_BLOCK = """COMPACITÉ

Valeurs sémantiques concises. Un énoncé compact, pas un résumé en prose,
pas une citation, pas une réécriture de paragraphe.

Un record = une unité sémantique distincte. Regroupe dans la fenêtre les
énoncés équivalents. Plusieurs SRC par record sont souhaitables."""


_OWNERSHIP_BLOCK = """SOURCES OWNED

Le contexte de cette fenêtre est NONE. Aucun ancrage context-only.

Chaque record substantif (TOPIC, IDEA, EXAMPLE, REFERENCE, UNCERTAINTY)
doit citer au moins un SRC OWNED réellement présent. RELATION n'a pas de SRC.

N'utilise que les identifiants SRC listés. Un SRC supprimé n'existe pas.
Pas d'expansion d'intervalle. Pas de SRC inventé."""


_FIDELITY_BLOCK = """FIDÉLITÉ

Identifier, classer, relier, signaler une incertitude.
Ne pas inventer. Ne pas compléter. Ne pas corriger en silence.

Si le budget local est insuffisant pour représenter fidèlement la source :
n'omets pas en silence. Émets UNCERTAINTY v EXACTEMENT :
analysis_capacity_exceeded
Ce signal n'arrête pas le provider à lui seul. Il rend le résultat NOT READY."""


_TASK_BLOCK = f"""TÂCHE

Réponds en JSON ultra-compact ({SEMANTIC_TRANSPORT_VERSION_V2}) :

{{"theme":"...","intent":"...","ic":"...","aud":"...","ac":"...","records":[{{"k":"...","v":"...","s":[],"l":[],"m":[]}}]}}

Kinds locaux autorisés uniquement :
{', '.join(LOCAL_KINDS)}

Kinds interdits ici :
{', '.join(DEFERRED_KINDS)}

ic / ac = jetons confidence. Liens l[] = index locaux de CE transport.

CIBLES / PLAFONDS :
{_budget_lines()}

source_refs : SRC réels, maximum {SOURCE_REFS_HARD_MAX} par record.
TOPIC.v ≤ {TEXT_HARD_LIMITS['TOPIC.v']} ; IDEA.v ≤ {TEXT_HARD_LIMITS['IDEA.v']}.

Si capacité insuffisante : UNCERTAINTY v={OVERFLOW_TOKEN}
m=["{OVERFLOW_UNCERTAINTY_KIND}","{OVERFLOW_UNCERTAINTY_SEVERITY}"]
s = au moins un SRC owned.

Sortie : uniquement le transport. Pas de raisonnement écrit."""


def _vocabulary_block() -> str:
    return "\n".join(
        [
            "IDENTIFIANTS CONTRÔLÉS — copie exacte",
            f"idea.kind : {', '.join(IDEA_KINDS)}",
            f"idea.importance : {', '.join(IMPORTANCE_LEVELS)}",
            f"relation.type : {', '.join(RELATION_KINDS)}",
            f"example.kind : {', '.join(EXAMPLE_KINDS)}",
            f"reference.kind : {', '.join(REFERENCE_KINDS)}",
            f"reference.completeness : {', '.join(REFERENCE_COMPLETENESS)}",
            f"uncertainty.kind : {', '.join(UNCERTAINTY_KINDS)}",
            f"uncertainty.severity : {', '.join(SEVERITY_LEVELS)}",
            f"confidence : {', '.join(CONFIDENCE_LEVELS)}",
            "TOPIC : v=label ; m=[summary] ; s=SRC",
            "IDEA : v=summary ; m=[kind, importance] ; l=TOPIC ; s=SRC",
            "RELATION : v=type ; l=[from IDEA, to IDEA] ; s=[]",
            "EXAMPLE : v=summary ; m=[kind] ; l=IDEA ; s=SRC",
            "REFERENCE : v=raw ; m=[kind, completeness, normalized] ; s=SRC",
            "UNCERTAINTY : v=desc ; m=[kind, severity] ; s=SRC",
        ]
    )


def build_window_system_prompt_v12(primary_language: str) -> str:
    return "\n\n".join(
        [
            _ROLE_BLOCK,
            _SCOPE_BLOCK,
            _COMPACT_BLOCK,
            _OWNERSHIP_BLOCK,
            _FIDELITY_BLOCK,
            FORBIDDEN_STRUCTURE_BLOCK,
            _vocabulary_block(),
            build_language_directive(primary_language),
        ]
    )


def _render_owned(content: WindowContent) -> str:
    if not content.owned_segments:
        return "OWNED SOURCES\n\n(none)"
    return "OWNED SOURCES\n\n" + render_segments(content.owned_segments)


def _render_context(content: WindowContent) -> str:
    return (
        "CONTEXT-ONLY SOURCES\n\n"
        "(none — boundary context is NONE for this local extraction)\n"
        "Do not invent context-only grounding."
    )


def build_window_user_prompt_v12(
    transcript: TranscriptInput,
    window: WindowInput,
    content: WindowContent | None = None,
) -> str:
    materialized = content or materialize_window_content(transcript, window)
    return "\n\n".join(
        [
            _TASK_BLOCK,
            build_language_directive(transcript.primary_language),
            (
                f"WINDOW — {window.window_id} — transcript {transcript.transcript_id} — "
                f"{window.owned_src_count} owned SRC, "
                f"{window.context_src_count} context-only SRC"
            ),
            "Notes locales compactes seulement. Pas de métadonnées globales finales.",
            _render_owned(materialized),
            _render_context(materialized),
        ]
    )


def window_prompt_v12_sha256(system_prompt: str) -> str:
    return content_hash(system_prompt)


def window_prompt_v12_fingerprint(system_prompt: str, user_prompt: str) -> str:
    return content_hash(
        "\n<<<LOCAL_V2_SYSTEM>>>\n"
        + (system_prompt or "")
        + "\n<<<LOCAL_V2_USER>>>\n"
        + (user_prompt or "")
    )


def estimate_v12_request_tokens(
    transcript: TranscriptInput,
    window: WindowInput,
    *,
    content: WindowContent | None = None,
    model: str = ESTIMATION_MODEL,
) -> dict[str, Any]:
    materialized = content or materialize_window_content(transcript, window)
    system = build_window_system_prompt_v12(transcript.primary_language)
    user = build_window_user_prompt_v12(transcript, window, materialized)
    total = estimate_tokens("\n".join([system, user]), model=model)
    return {
        "model": model,
        "method": total.method,
        "estimated": True,
        "total_tokens": total.tokens,
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V12,
        "transport_version": SEMANTIC_TRANSPORT_VERSION_V2,
    }


_LINK_RULES_BLOCK = """LINK RULES

l = 0-based TARGET record indexes in THIS transport.
l is NEVER the current record's own index.
l is NEVER a canonical ID. Provider does not invent IDs.
Index 0 = first record. Self-link (record → same record) is FORBIDDEN.
Forward and backward targets are legal. Duplicate indexes in one l[] are FORBIDDEN.
Cycles across distinct records are legal.

TOPIC : l=[] required
IDEA : l = TOPIC indexes only ; empty allowed
RELATION : l = exactly 2 distinct IDEA indexes [from, to] ; type in v
EXAMPLE : l = IDEA indexes only ; empty allowed only if no local IDEA
REFERENCE : l=[] required
UNCERTAINTY : l=[] required

Correct:
{"k":"TOPIC","v":"Planning","s":["SRC999001"],"l":[],"m":["Careful plans."]}
{"k":"IDEA","v":"Planning reduces mistakes.","s":["SRC999001"],"l":[0],"m":["claim","central"]}
{"k":"EXAMPLE","v":"Check the plan twice.","s":["SRC999002"],"l":[1],"m":["anecdote"]}

Recommended order: TOPIC, IDEA, RELATION, EXAMPLE, REFERENCE, UNCERTAINTY.
Order is not required. Resolve links after the full records[] list."""


def _vocabulary_block_v121() -> str:
    return "\n".join(
        [
            "IDENTIFIANTS CONTRÔLÉS — copie exacte",
            f"idea.kind : {', '.join(IDEA_KINDS)}",
            f"idea.importance : {', '.join(IMPORTANCE_LEVELS)}",
            f"relation.type : {', '.join(RELATION_KINDS)}",
            f"example.kind : {', '.join(EXAMPLE_KINDS)}",
            f"reference.kind : {', '.join(REFERENCE_KINDS)}",
            f"reference.completeness : {', '.join(REFERENCE_COMPLETENESS)}",
            f"uncertainty.kind : {', '.join(UNCERTAINTY_KINDS)}",
            f"uncertainty.severity : {', '.join(SEVERITY_LEVELS)}",
            f"confidence : {', '.join(CONFIDENCE_LEVELS)}",
            "TOPIC : v=label ; m=[summary] ; s=SRC ; l=[]",
            "IDEA : v=summary ; m=[kind, importance] ; l=0-based TOPIC target indexes ; s=SRC",
            "RELATION : v=type ; l=[from IDEA index, to IDEA index] ; s=[]",
            "EXAMPLE : v=summary ; m=[kind] ; l=0-based IDEA target indexes ; s=SRC",
            "REFERENCE : v=raw ; m=[kind, completeness, normalized] ; s=SRC ; l=[]",
            "UNCERTAINTY : v=desc ; m=[kind, severity] ; s=SRC ; l=[]",
        ]
    )


_TASK_BLOCK_V121 = f"""TÂCHE

Réponds en JSON ultra-compact ({SEMANTIC_TRANSPORT_VERSION_V2}) :

{{"theme":"...","intent":"...","ic":"...","aud":"...","ac":"...","records":[{{"k":"...","v":"...","s":[],"l":[],"m":[]}}]}}

Kinds locaux autorisés uniquement :
{', '.join(LOCAL_KINDS)}

Kinds interdits ici :
{', '.join(DEFERRED_KINDS)}

ic / ac = jetons confidence.
l[] = 0-based TARGET record indexes in THIS transport.
Never put the current record index in l. Never self-link.

CIBLES / PLAFONDS :
{_budget_lines()}

source_refs : SRC réels, maximum {SOURCE_REFS_HARD_MAX} par record.
TOPIC.v ≤ {TEXT_HARD_LIMITS['TOPIC.v']} ; IDEA.v ≤ {TEXT_HARD_LIMITS['IDEA.v']}.

Si capacité insuffisante : UNCERTAINTY v={OVERFLOW_TOKEN}
m=["{OVERFLOW_UNCERTAINTY_KIND}","{OVERFLOW_UNCERTAINTY_SEVERITY}"]
s = au moins un SRC owned.

Sortie : uniquement le transport. Pas de raisonnement écrit."""


def build_window_system_prompt_v121(primary_language: str) -> str:
    return "\n\n".join(
        [
            _ROLE_BLOCK,
            _SCOPE_BLOCK,
            _COMPACT_BLOCK,
            _OWNERSHIP_BLOCK,
            _FIDELITY_BLOCK,
            FORBIDDEN_STRUCTURE_BLOCK,
            _vocabulary_block_v121(),
            _LINK_RULES_BLOCK,
            build_language_directive(primary_language),
        ]
    )


def build_window_user_prompt_v121(
    transcript: TranscriptInput,
    window: WindowInput,
    content: WindowContent | None = None,
) -> str:
    materialized = content or materialize_window_content(transcript, window)
    return "\n\n".join(
        [
            _TASK_BLOCK_V121,
            _LINK_RULES_BLOCK,
            build_language_directive(transcript.primary_language),
            (
                f"WINDOW — {window.window_id} — transcript {transcript.transcript_id} — "
                f"{window.owned_src_count} owned SRC, "
                f"{window.context_src_count} context-only SRC"
            ),
            "Notes locales compactes seulement. Pas de métadonnées globales finales.",
            _render_owned(materialized),
            _render_context(materialized),
        ]
    )


def window_prompt_v121_sha256(system_prompt: str) -> str:
    return content_hash(system_prompt)


def window_prompt_v121_fingerprint(system_prompt: str, user_prompt: str) -> str:
    return content_hash(
        "\n<<<LOCAL_V2_SYSTEM>>>\n"
        + (system_prompt or "")
        + "\n<<<LOCAL_V2_USER>>>\n"
        + (user_prompt or "")
    )


def estimate_v121_request_tokens(
    transcript: TranscriptInput,
    window: WindowInput,
    *,
    content: WindowContent | None = None,
    model: str = ESTIMATION_MODEL,
) -> dict[str, Any]:
    materialized = content or materialize_window_content(transcript, window)
    system = build_window_system_prompt_v121(transcript.primary_language)
    user = build_window_user_prompt_v121(transcript, window, materialized)
    total = estimate_tokens("\n".join([system, user]), model=model)
    return {
        "model": model,
        "method": total.method,
        "estimated": True,
        "total_tokens": total.tokens,
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V121,
        "transport_version": SEMANTIC_TRANSPORT_VERSION_V2,
    }


__all__ = [
    "WINDOW_PROMPT_ROLE",
    "build_window_system_prompt_v12",
    "build_window_system_prompt_v121",
    "build_window_user_prompt_v12",
    "build_window_user_prompt_v121",
    "estimate_v12_request_tokens",
    "estimate_v121_request_tokens",
    "window_prompt_v12_fingerprint",
    "window_prompt_v12_sha256",
    "window_prompt_v121_fingerprint",
    "window_prompt_v121_sha256",
    "CANDIDATE_WINDOW_ANALYSIS_PROMPT_VERSION",
]
