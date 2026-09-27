"""
Estimation de tokens du planner v2.0.

Réutilise les primitives approuvées en 3B.7 :

    estimate_tokens(system + user)
    render_segment(SRC)
    build_system_prompt / build_user_prompt

Aucun nouvel estimateur. Aucun hardcode de 2922.

Sémantique du budget
--------------------
target_input_tokens et hard_max_input_tokens sont des plafonds de
REQUÊTE COMPLÈTE estimée, pas du seul texte SRC :

    system prompt
    + cadrage user (tâche, langue, en-tête TRANSCRIPTION)
    + contenu SRC rendu
    + le schéma structuré n'est compté que s'il apparaît déjà dans
      ce texte de prompt (l'en-tête de tâche 1.3 le mentionne).

Deux grandeurs distinctes :

    content_tokens          somme estimate(render_segment(SRC_i))
    prompt_overhead         estimate(system + user avec 0 segment)
    planner_estimate        overhead + content_tokens
    estimated_input_tokens  re-mesure de la fenêtre réelle
                            (system + user avec les SRC owned)

La re-mesure n'est pas forcément égale à planner_estimate : l'en-tête
user porte le nombre de segments, et le jointoyage ``\\n\\n`` n'est pas
une somme exacte des rendus isolés.
"""

from __future__ import annotations

from typing import Sequence

from app.ai.estimation import estimate_tokens
from app.source_analysis.prompt import (
    build_system_prompt,
    build_user_prompt,
    render_segment,
)
from app.source_analysis.transcript_input import SourceSegment, TranscriptInput
from app.source_analysis_hybrid.constants import ESTIMATION_MODEL


def estimate_prompt_overhead(
    transcript: TranscriptInput, *, model: str = ESTIMATION_MODEL
) -> int:
    """Coût fixe : system + user sans aucun SRC."""
    system = build_system_prompt(transcript.primary_language)
    user = build_user_prompt(transcript, segments=())
    return estimate_tokens("\n".join([system, user]), model=model).tokens


def estimate_segment_content_tokens(
    segment: SourceSegment, *, model: str = ESTIMATION_MODEL
) -> int:
    """Tokens du SRC rendu, sans le cadrage de prompt."""
    return estimate_tokens(render_segment(segment), model=model).tokens


def estimate_window_input_tokens(
    transcript: TranscriptInput,
    segments: Sequence[SourceSegment],
    *,
    model: str = ESTIMATION_MODEL,
) -> int:
    """Requête complète estimée pour une fenêtre (system + user réel)."""
    system = build_system_prompt(transcript.primary_language)
    user = build_user_prompt(transcript, segments=segments)
    return estimate_tokens("\n".join([system, user]), model=model).tokens


def content_weights_for(
    transcript: TranscriptInput, *, model: str = ESTIMATION_MODEL
) -> tuple[int, ...]:
    return tuple(
        estimate_segment_content_tokens(segment, model=model)
        for segment in transcript.segments
    )
