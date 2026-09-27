"""
Budget de contexte et stratégie d'analyse.

Principe directeur, dit une fois pour toutes : la structure TECHNIQUE de
traitement ne doit jamais devenir, par accident, une structure sémantique ou
éditoriale. C'est la faute originelle de la V1, où les chunks de découpage sont
devenus des chapitres. Donc :

    le transcript tient dans le budget   ->  une seule analyse globale
    le transcript dépasse                ->  fenêtres PUREMENT techniques

et dans le second cas, les fenêtres ne sont ni des thèmes, ni des chapitres, ni
des sections : elles n'existent que parce qu'un modèle a une limite.

Rien n'est codé en dur. Le budget vient des capacités du couple
(provider, modèle) de la Phase 2B, la taille du prompt d'une estimation de la
Phase 2, et le ratio de sécurité de la configuration :

    usable_input_context = context_window * safety_ratio - max_output_tokens

Il n'existe aucune constante « 4096 », « 8000 caractères » ou « 100000 tokens »
valable universellement dans ce module.

Séparation stricte des deux comptages de tokens :

    estimation (ici)            planification du contexte, jamais le coût
    usage réel (AIResponse)     coût, jamais la planification
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.capabilities import ModelCapabilities
from app.ai.estimation import estimate_tokens
from app.source_analysis.models import STRATEGY_GLOBAL, STRATEGY_WINDOWED
from app.source_analysis.transcript_input import SourceSegment, TranscriptInput

# Recouvrement entre deux fenêtres techniques, en segments source. Un segment
# partagé donne au modèle de quoi comprendre la phrase qui commence une fenêtre
# sans avoir à couper au milieu d'un SRC.
DEFAULT_WINDOW_OVERLAP_SEGMENTS = 1


@dataclass(frozen=True)
class AnalysisWindow:
    """
    Fenêtre technique de lecture. Artefact de budget, rien de plus.

    Découpée sur des FRONTIÈRES DE SRC : un segment n'est jamais scindé, ses
    identifiants et ses horodatages restent ceux du transcript. Une fenêtre ne
    porte aucun titre, aucun thème, aucune place dans un ordre éditorial.
    """

    index: int
    segments: tuple[SourceSegment, ...]

    @property
    def first_src(self) -> str:
        return self.segments[0].src_id

    @property
    def last_src(self) -> str:
        return self.segments[-1].src_id

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "segment_count": len(self.segments),
            "first_src": self.first_src,
            "last_src": self.last_src,
        }


@dataclass(frozen=True)
class ContextPlan:
    """
    Décision de stratégie, prise AVANT le moindre appel.

    `estimated_input_tokens` est une ESTIMATION assumée comme telle, méthode
    incluse : elle sert à choisir une stratégie, jamais à facturer.

    `capabilities_known` vaut False lorsque les capacités du modèle sont une
    hypothèse de repli et non un fait relevé. L'information est propagée
    jusqu'aux logs : décider d'un budget sur une hypothèse doit se voir.
    """

    strategy: str
    estimated_input_tokens: int
    estimation_method: str
    usable_input_context: int
    context_window: int
    max_output_tokens: int
    safety_ratio: float
    capabilities_known: bool
    provider: str
    model: str
    windows: tuple[AnalysisWindow, ...] = ()

    @property
    def fits_globally(self) -> bool:
        return self.strategy == STRATEGY_GLOBAL

    @property
    def window_count(self) -> int:
        return len(self.windows)

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "estimated_input_tokens": self.estimated_input_tokens,
            "estimation_method": self.estimation_method,
            "estimated": True,
            "usable_input_context": self.usable_input_context,
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "safety_ratio": self.safety_ratio,
            "capabilities_known": self.capabilities_known,
            "provider": self.provider,
            "model": self.model,
            "window_count": self.window_count,
            "windows": [window.to_dict() for window in self.windows],
        }

    def budget_summary(self) -> str:
        """Résumé de budget destiné aux messages d'erreur et aux logs."""
        return (
            f"{self.estimated_input_tokens} tokens estimés "
            f"({self.estimation_method}) pour un budget d'entrée utilisable de "
            f"{self.usable_input_context} tokens "
            f"[{self.provider}:{self.model}, context_window="
            f"{self.context_window}, max_output_tokens={self.max_output_tokens}, "
            f"safety_ratio={self.safety_ratio}, "
            f"capabilities_known={self.capabilities_known}]"
        )


def plan_context(
    transcript: TranscriptInput,
    capabilities: ModelCapabilities,
    *,
    system_prompt: str,
    user_prompt: str,
    safety_ratio: float | None = None,
    overlap_segments: int = DEFAULT_WINDOW_OVERLAP_SEGMENTS,
) -> ContextPlan:
    """
    Décide comment le transcript sera lu, sans rien tronquer.

    L'estimation porte sur les prompts RÉELLEMENT construits (système + tâche +
    transcription rendue) et non sur le seul texte des segments : la consigne
    occupe du contexte elle aussi, et l'ignorer reviendrait à se croire dans le
    budget alors qu'on le dépasse.
    """
    estimate = estimate_tokens(
        "\n".join([system_prompt, user_prompt]),
        model=capabilities.model,
    )

    budget = capabilities.usable_input_context(safety_ratio)
    effective_ratio = _effective_safety_ratio(capabilities, safety_ratio)

    if estimate.tokens <= budget:
        return ContextPlan(
            strategy=STRATEGY_GLOBAL,
            estimated_input_tokens=estimate.tokens,
            estimation_method=estimate.method,
            usable_input_context=budget,
            context_window=capabilities.context_window,
            max_output_tokens=capabilities.max_output_tokens,
            safety_ratio=effective_ratio,
            capabilities_known=capabilities.known,
            provider=capabilities.provider,
            model=capabilities.model,
        )

    windows = plan_windows(
        transcript,
        estimated_tokens=estimate.tokens,
        budget_tokens=budget,
        overlap_segments=overlap_segments,
    )

    return ContextPlan(
        strategy=STRATEGY_WINDOWED,
        estimated_input_tokens=estimate.tokens,
        estimation_method=estimate.method,
        usable_input_context=budget,
        context_window=capabilities.context_window,
        max_output_tokens=capabilities.max_output_tokens,
        safety_ratio=effective_ratio,
        capabilities_known=capabilities.known,
        provider=capabilities.provider,
        model=capabilities.model,
        windows=windows,
    )


def _effective_safety_ratio(
    capabilities: ModelCapabilities,
    safety_ratio: float | None,
) -> float:
    from app.ai.capabilities import default_safety_ratio

    return float(default_safety_ratio() if safety_ratio is None else safety_ratio)


def plan_windows(
    transcript: TranscriptInput,
    *,
    estimated_tokens: int,
    budget_tokens: int,
    overlap_segments: int = DEFAULT_WINDOW_OVERLAP_SEGMENTS,
) -> tuple[AnalysisWindow, ...]:
    """
    Découpe technique sur frontières de SRC, déterministe.

    Le nombre de fenêtres est déduit du rapport entre la taille estimée et le
    budget, puis les segments sont répartis en parts égales : le découpage ne
    dépend ni d'un seuil arbitraire de caractères, ni du contenu, ni de
    l'horodatage. Deux planifications du même transcript donnent le même
    découpage.

    Aucun SRC n'est scindé et aucun n'est omis : la réunion des fenêtres couvre
    l'intégralité du transcript. Un léger recouvrement donne le contexte de la
    phrase précédente à chaque fenêtre suivante.

    Cette fonction PRÉPARE la stratégie longue. Elle ne l'exécute pas : voir
    la note de dette dans analyzer.py.
    """
    # Liste ordonnée des SRC réellement présents — jamais une plage
    # numérique SRC000001…SRC000N qui inventerait des trous.
    segments = transcript.segments

    if not segments:
        return ()

    if budget_tokens <= 0:
        # Budget nul : aucune fenêtre ne peut tenir. Une fenêtre par segment est
        # la décomposition maximale possible, et signale l'impasse au lieu de
        # boucler sur un calcul impossible.
        return tuple(
            AnalysisWindow(index=index, segments=(segment,))
            for index, segment in enumerate(segments, start=1)
        )

    parts = max(2, -(-int(estimated_tokens) // int(budget_tokens)))
    per_window = max(1, -(-len(segments) // parts))
    overlap = max(0, min(int(overlap_segments), per_window - 1))

    windows: list[AnalysisWindow] = []
    start = 0
    index = 0

    while start < len(segments):
        stop = min(start + per_window, len(segments))
        index += 1
        windows.append(
            AnalysisWindow(index=index, segments=tuple(segments[start:stop]))
        )

        if stop >= len(segments):
            break

        start = stop - overlap

    return tuple(windows)
