"""
Payload envoyé au modèle — vue SANITISÉE d'un bloc sélectionné (§15-16).

Frontière de sécurité explicite : ce module est le SEUL endroit qui
construit ce qui part réellement dans le prompt utilisateur. Toute
information de la Phase 3A.1 (phase_3a1_status, REMOVE_TRANSLATION,
ALREADY_RESOLVED, score ou confidence antérieurs, décision antérieure) est
strictement absente de sa sortie — §15 l'interdit explicitement, pour ne pas
biaiser le canary.

Champs transmis (§16), et rien d'autre :

    block_id
    french.source_refs / french.text
    english_before.source_refs / english_before.text   (ou null)
    english_after.source_refs / english_after.text      (ou null)
"""

from __future__ import annotations

from typing import Any

from app.semantic_canary.models import SelectedBlock

# Champs strictement interdits dans le payload réseau (§15). Documentés ici
# pour que le test de non-fuite (§30.3) ait une liste explicite à vérifier
# plutôt qu'une intuition.
FORBIDDEN_FIELDS = (
    "phase_3a1_status",
    "phase_3a1_decisions",
    "phase_3a1_remove_refs",
    "phase_3a1_review_refs",
    "phase_3a1_keep_refs",
    "already_resolved",
    "needs_semantic_review",
    "semantic_review_status",
)


def _context_payload(context: dict | None) -> dict | None:
    """Vue sanitisée d'un english_before/english_after — refs + texte seuls."""
    if context is None:
        return None

    return {
        "source_refs": list(context.get("source_refs") or []),
        "text": str(context.get("text", "")),
    }


def build_block_payload(selected: SelectedBlock) -> dict[str, Any]:
    """
    Construit le payload conceptuel d'un bloc (§16), sans aucune donnée de
    Phase 3A.1 (§15). N'invente jamais de texte : `english_before` /
    `english_after` valent `None` si le bloc n'a pas ce contexte.
    """
    return {
        "block_id": selected.block_id,
        "french": {
            "source_refs": list(selected.fr_source_refs),
            "text": str(selected.raw_block.get("text", "")),
        },
        "english_before": _context_payload(selected.english_before),
        "english_after": _context_payload(selected.english_after),
    }


def build_canary_payloads(selected_blocks: list[SelectedBlock]) -> list[dict[str, Any]]:
    """Payloads de tous les blocs sélectionnés, dans l'ordre de sélection."""
    return [build_block_payload(block) for block in selected_blocks]


def assert_no_forbidden_leak(payload: dict[str, Any]) -> None:
    """
    Garde-fou explicite (§15, §30.3) : aucune clé interdite, à aucun niveau
    de profondeur, ne doit apparaître dans un payload réseau.
    """

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN_FIELDS:
                    raise AssertionError(
                        f"Fuite de donnée Phase 3A.1 dans le payload réseau : « {key} »."
                    )
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(payload)
