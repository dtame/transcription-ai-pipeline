"""
Signature déterministe d'un lot (§20).

Toute modification du contenu — ou de son contexte (sources, version de
prompt, schéma, provider/modèle, ordre des block_id) — doit invalider le
cache. La signature est un hash unique de tous ces éléments ; le hash du
contenu du payload lui-même (`payload_content_hash`) est calculé séparément
pour rester lisible dans un artefact de diagnostic.
"""

from __future__ import annotations

import json

from app.file_utils import content_hash


def payload_content_hash(payloads: list[dict]) -> str:
    """Empreinte du contenu réellement envoyé (ou qui serait envoyé) au modèle."""
    serialized = json.dumps(payloads, ensure_ascii=False, sort_keys=True)
    return content_hash(serialized)


def compute_batch_signature(
    *,
    language_blocks_sha256: str,
    prompt_version: str,
    response_schema_sha256: str,
    provider: str,
    model: str,
    block_ids: list[str],
    payload_hash: str,
) -> str:
    """
    §20 : signature couvrant au minimum language_blocks_sha256, prompt_version,
    response_schema_sha256, provider, model, les block_ids ORDONNÉS, et le
    hash du contenu du payload.
    """
    material = {
        "language_blocks_sha256": language_blocks_sha256,
        "prompt_version": prompt_version,
        "response_schema_sha256": response_schema_sha256,
        "provider": provider,
        "model": model,
        "block_ids": list(block_ids),
        "payload_content_hash": payload_hash,
    }
    serialized = json.dumps(material, ensure_ascii=False, sort_keys=True)
    return content_hash(serialized)
