"""
Estimation HORS-LIGNE de la charge IA future (§27-28 du cahier des charges).

AUCUN APPEL IA ICI. Cette phase ne choisit pas de modèle et n'invente aucun
prix (§20, §27) : elle mesure seulement combien de blocs nécessiteraient une
future revue sémantique, quelle taille de texte cela représente, et combien de
requêtes seraient nécessaires selon différentes tailles de lot.

`app.ai.estimation.estimate_tokens` est réutilisé tel quel (méthode
tiktoken si disponible, sinon heuristique caractères/token documentée dans ce
module) — jamais recalculé ici.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from app.ai.estimation import estimate_tokens
from app.language_blocks.models import LanguageBlock

BATCH_SIZES = (1, 5, 10, 20, 50)

# Estimation d'ORDRE DE GRANDEUR pour un futur prompt système commun
# (instructions + schéma de réponse attendu). C'est une HYPOTHÈSE DE TRAVAIL
# documentée, pas une décision de conception de Phase 3A.2 : elle sert
# uniquement à ne pas sous-estimer grossièrement le nombre de requêtes futures
# lors de la comparaison entre tailles de lot. Aucun modèle n'est choisi, ni
# ici ni ailleurs dans cette phase.
ASSUMED_SYSTEM_PROMPT_TOKENS = 300


def build_future_payload_text(block: LanguageBlock) -> str:
    """
    Texte brut qu'un futur appel IA recevrait pour CE bloc (§27) : le FR, puis
    son contexte anglais avant/après s'il existe. Aucune mise en forme JSON
    n'est décidée ici — seulement le contenu textuel à estimer en tokens.
    """
    parts = [f"[FR]\n{block.text}"]

    if block.english_before is not None:
        parts.append(f"[EN_BEFORE]\n{block.english_before.text}")

    if block.english_after is not None:
        parts.append(f"[EN_AFTER]\n{block.english_after.text}")

    return "\n\n".join(parts)


@dataclass(frozen=True)
class BlockTokenEstimate:
    block_id: str
    tokens: int
    method: str


def estimate_blocks_needing_review(
    blocks: tuple[LanguageBlock, ...],
) -> tuple[BlockTokenEstimate, ...]:
    from app.language_blocks.models import SEMANTIC_STATUS_NEEDED

    estimates = []

    for block in blocks:
        if block.semantic_review_status != SEMANTIC_STATUS_NEEDED:
            continue

        payload = build_future_payload_text(block)
        estimate = estimate_tokens(payload)
        estimates.append(
            BlockTokenEstimate(block_id=block.block_id, tokens=estimate.tokens, method=estimate.method)
        )

    return tuple(estimates)


def compute_ai_estimation(blocks: tuple[LanguageBlock, ...]) -> dict:
    """
    §27-28 : nombre de blocs à revoir, volume de tokens, requêtes par taille de
    lot. Ne retourne jamais un coût — seulement des comptages.
    """
    per_block = estimate_blocks_needing_review(blocks)
    token_counts = [item.tokens for item in per_block]
    method = per_block[0].method if per_block else "n/a"

    total_tokens = sum(token_counts)
    block_count = len(token_counts)

    batches: dict[str, dict] = {}

    for size in BATCH_SIZES:
        if block_count == 0:
            requests = 0
        else:
            requests = -(-block_count // size)  # ceil division sans import math

        system_prompt_tokens_total = requests * ASSUMED_SYSTEM_PROMPT_TOKENS

        batches[str(size)] = {
            "blocks_per_request": size,
            "request_count": requests,
            "content_tokens": total_tokens,
            "system_prompt_tokens_total": system_prompt_tokens_total,
            "total_tokens": total_tokens + system_prompt_tokens_total,
        }

    return {
        "method": method,
        "blocks_needing_review": block_count,
        "total_estimated_input_tokens": total_tokens,
        "mean_tokens_per_block": (
            round(statistics.mean(token_counts), 2) if token_counts else 0.0
        ),
        "median_tokens_per_block": (
            statistics.median(token_counts) if token_counts else 0
        ),
        "max_tokens_per_block": max(token_counts) if token_counts else 0,
        "min_tokens_per_block": min(token_counts) if token_counts else 0,
        "assumed_system_prompt_tokens": ASSUMED_SYSTEM_PROMPT_TOKENS,
        "batches": batches,
    }
