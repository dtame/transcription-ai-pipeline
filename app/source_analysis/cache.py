"""
Signature et idempotence de l'analyse de source.

Un appel au Source Analyzer coûte de l'argent. Relancer la Phase 3 sur un
projet inchangé doit donc coûter zéro : ni appel, ni facturation.

L'audit V1 a identifié la faiblesse exacte à ne pas reproduire : ses signatures
ne tenaient compte que des DONNÉES (le hash d'un fichier source), pas du CODE
qui les traitait. Modifier un prompt laissait alors le cache valide, et le
projet continuait d'exposer un résultat produit par une version disparue.

La signature d'ici couvre les deux :

    données     transcript_sha256, transcript_id
    contrat     prompt_version, schema_version
    code réel   prompt_sha256, response_schema_sha256
    routage     provider, model
    réglages    temperature, max_output_tokens, context_safety_ratio,
                output_language

`prompt_sha256` est le hash du prompt RÉELLEMENT construit, consigne système
comprise. Conséquence : une correction du texte du prompt sans incrément de
SOURCE_ANALYZER_PROMPT_VERSION invalide malgré tout le cache. La version reste
utile — elle est lisible par un humain dans le fichier publié — mais elle n'est
plus le seul rempart, et un oubli de bump ne peut plus ressusciter une analyse
périmée.

`response_schema_sha256` joue le même rôle pour la forme attendue de la réponse.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from app.file_utils import content_hash


@dataclass(frozen=True)
class SignatureInputs:
    """
    Tout ce dont dépend le résultat d'une analyse, et rien d'autre.

    Sciemment sans horodatage ni nom de machine : deux analyses identiques
    doivent produire la même signature, sinon le cache ne peut jamais toucher.
    """

    transcript_sha256: str
    transcript_id: str
    prompt_version: str
    prompt_sha256: str
    schema_version: str
    response_schema_sha256: str
    provider: str
    model: str
    temperature: float | None
    max_output_tokens: int | None
    context_safety_ratio: float
    output_language: str

    def to_dict(self) -> dict:
        return {
            "context_safety_ratio": self.context_safety_ratio,
            "max_output_tokens": self.max_output_tokens,
            "model": self.model,
            "output_language": self.output_language,
            "prompt_sha256": self.prompt_sha256,
            "prompt_version": self.prompt_version,
            "provider": self.provider,
            "response_schema_sha256": self.response_schema_sha256,
            "schema_version": self.schema_version,
            "temperature": self.temperature,
            "transcript_id": self.transcript_id,
            "transcript_sha256": self.transcript_sha256,
        }


def prompt_fingerprint(system_prompt: str, user_prompt: str) -> str:
    """
    Empreinte du matériel de prompt effectivement envoyé.

    Les deux parties sont séparées par un marqueur explicite pour qu'un
    déplacement de texte du prompt système vers le prompt utilisateur change
    l'empreinte : ce n'est pas le même appel.
    """
    return content_hash(
        "\n<<<SOURCE_ANALYZER_SYSTEM>>>\n"
        + (system_prompt or "")
        + "\n<<<SOURCE_ANALYZER_USER>>>\n"
        + (user_prompt or "")
    )


def build_signature(inputs: SignatureInputs) -> str:
    """
    Signature déterministe d'une analyse.

    `sort_keys=True` : l'ordre de déclaration des champs ne doit pas influencer
    la signature.
    """
    payload = json.dumps(inputs.to_dict(), ensure_ascii=False, sort_keys=True)

    return content_hash(payload)


def published_signature(payload: Mapping[str, Any] | None) -> str:
    """
    Signature portée par un source_map.json déjà publié.

    Lue dans le fichier lui-même, et non seulement dans project_state.json : un
    état peut affirmer qu'une analyse est à jour alors que le fichier a été
    remplacé, déplacé ou édité à la main. La double vérification empêche de
    servir un fichier dont on ne sait plus ce qu'il contient.
    """
    if not isinstance(payload, Mapping):
        return ""

    analysis = payload.get("analysis")

    if not isinstance(analysis, Mapping):
        return ""

    return str(analysis.get("signature") or "")


def is_cache_valid(
    *,
    signature: str,
    state_block: Mapping[str, Any] | None,
    published_payload: Mapping[str, Any] | None,
) -> bool:
    """
    Décide s'il est légitime de réutiliser une analyse sans rappeler le modèle.

    Exige la concordance de TROIS choses : la signature calculée, celle
    mémorisée dans l'état du projet, et celle inscrite dans le fichier publié.
    Une ancienne analyse dont la signature ne correspond plus n'est pas
    « presque à jour » : elle est incompatible, et la réutiliser serait servir
    silencieusement un résultat obsolète.
    """
    if not signature:
        return False

    if not isinstance(state_block, Mapping):
        return False

    if str(state_block.get("status") or "") != "completed":
        return False

    if str(state_block.get("signature") or "") != signature:
        return False

    return published_signature(published_payload) == signature
