"""
Estimation du nombre de tokens AVANT appel.

À ne jamais confondre avec la consommation réelle portée par AIResponse :
une estimation sert uniquement à vérifier qu'un prompt tient dans le budget
de contexte. Elle n'entre jamais dans un calcul de coût.

Pour rendre l'ambiguïté impossible, cette fonction ne retourne pas un entier
nu mais un TokenEstimate qui porte `estimated=True` et la méthode employée.

Priorité des méthodes :

    1. tiktoken, s'il est déjà présent dans l'environnement
    2. heuristique caractères/token, explicitement marquée comme telle

tiktoken n'est PAS une dépendance de ce projet : la Phase 2 ne l'installe
pas pour obtenir une approximation. Le jour où il sera présent (par exemple
tiré par un autre besoin), l'estimation s'affinera d'elle-même.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

METHOD_TIKTOKEN = "tiktoken"
METHOD_HEURISTIC = "heuristic_chars_per_token"

# Approximation usuelle pour du texte latin. Volontairement grossière :
# l'objectif est un garde-fou de contexte, pas une facturation.
CHARS_PER_TOKEN = 4.0

# Encodage tiktoken générique, utilisé seulement si la librairie est présente.
_TIKTOKEN_FALLBACK_ENCODING = "cl100k_base"


@dataclass(frozen=True)
class TokenEstimate:
    """
    Résultat d'une estimation.

    `estimated` vaut toujours True : cet objet ne peut pas, par construction,
    être confondu avec un compteur rapporté par un fournisseur.
    """

    tokens: int
    method: str
    model: str | None = None
    estimated: bool = True

    def __post_init__(self) -> None:
        if not self.estimated:
            raise ValueError(
                "TokenEstimate décrit une estimation : estimated ne peut pas être False."
            )

    def to_dict(self) -> dict:
        return {
            "tokens": self.tokens,
            "method": self.method,
            "model": self.model,
            "estimated": True,
        }


def _tiktoken_count(text: str, model: str | None) -> int | None:
    """Compte via tiktoken si disponible, sinon None. N'installe jamais rien."""
    try:
        import tiktoken  # type: ignore
    except ImportError:
        return None

    try:
        if model:
            encoding = tiktoken.encoding_for_model(model)
        else:
            encoding = tiktoken.get_encoding(_TIKTOKEN_FALLBACK_ENCODING)
    except Exception:
        try:
            encoding = tiktoken.get_encoding(_TIKTOKEN_FALLBACK_ENCODING)
        except Exception:
            return None

    try:
        return len(encoding.encode(text))
    except Exception:
        return None


def heuristic_token_count(text: str) -> int:
    """Approximation par nombre de caractères, arrondie au supérieur."""
    if not text:
        return 0

    return max(1, math.ceil(len(text) / CHARS_PER_TOKEN))


def estimate_tokens(text: str, model: str | None = None) -> TokenEstimate:
    """
    Estime la taille d'un texte en tokens.

    Retourne toujours un TokenEstimate, jamais un entier : l'appelant ne peut
    pas additionner par mégarde une estimation et un compteur réel.
    """
    if text is None:
        text = ""

    exact = _tiktoken_count(text, model)

    if exact is not None:
        return TokenEstimate(tokens=exact, method=METHOD_TIKTOKEN, model=model)

    return TokenEstimate(
        tokens=heuristic_token_count(text),
        method=METHOD_HEURISTIC,
        model=model,
    )


def estimate_request_tokens(request) -> TokenEstimate:
    """
    Estime le coût en contexte d'une AIRequest complète (system + prompt).

    Ne compte pas la surcharge de formatage propre à chaque fournisseur :
    c'est une borne inférieure raisonnable, pas un contrat.
    """
    parts = [request.prompt]

    if request.system_prompt:
        parts.append(request.system_prompt)

    joined = "\n".join(part for part in parts if part)

    return estimate_tokens(joined, model=request.model)


def fits_in_context(
    request,
    capabilities,
    safety_ratio: float | None = None,
) -> tuple[bool, TokenEstimate]:
    """
    Vérifie qu'une requête tient dans le budget d'entrée utilisable.

    Retourne (verdict, estimation) : le verdict repose sur une ESTIMATION et
    doit être traité comme tel par l'appelant.
    """
    estimate = estimate_request_tokens(request)
    budget = capabilities.usable_input_context(safety_ratio)

    return estimate.tokens <= budget, estimate
