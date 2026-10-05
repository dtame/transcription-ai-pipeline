"""Audit report for the single experimental cover image. No secrets."""

from __future__ import annotations

from typing import Any


def render(outcome: dict[str, Any]) -> str:
    result = outcome.get("result")
    lines = [
        "# PHASE 4B.2.34.4 — FIRST REAL COVER IMAGE",
        "",
        f"RESULT = {result}",
        f"REAL PROVIDER CALLS = {outcome.get('real_provider_calls')}",
        "PROVIDER = OpenAI",
        "MODEL = gpt-image-2",
        "ART DIRECTION = The Door Already Open",
        "POLICY = EXPERIMENTAL_AUTHORIZED",
        f"USER AUTHORIZATION = {outcome.get('user_authorization')}",
        f"AUTHORIZATION USE = {outcome.get('authorization_use')}",
        f"IMAGE COUNT REQUESTED = {outcome.get('image_count_requested')}",
        f"IMAGE COUNT RECEIVED = {outcome.get('image_count_received')}",
        "RESOLUTION REQUESTED = 1024 × 1536",
        f"RESOLUTION RECEIVED = {outcome.get('resolution_received')}",
        "QUALITY = medium",
        "FORMAT = PNG",
        f"IMAGE SHA256 = {outcome.get('image_sha256')}",
        f"IMAGE PATH = {outcome.get('image_path')}",
        f"ESTIMATED COST = {outcome.get('estimated_cost_display')}",
        f"OBSERVED COST = {outcome.get('observed_cost_usd')}",
        f"COST RECONCILIATION = {outcome.get('cost_reconciliation')}",
        "AUTOMATIC RETRIES = 0",
        "FALLBACK CALLS = 0",
        "SECOND PAID CALL = NO",
        f"TECHNICAL IMAGE VALIDATION = {outcome.get('technical_image_validation')}",
        f"HUMAN VISUAL REVIEW = {outcome.get('human_visual_review')}",
        "FRONT COVER GENERATED = NO",
        "BACK COVER GENERATED = NO",
        "COVER DOCX GENERATED = NO",
        "COVER PDF GENERATED = NO",
        f"CANONICAL HASHES = {outcome.get('canonical_hashes')}",
        f"NEXT STEP = {outcome.get('next_step')}",
        "",
        "## Déroulement",
        "",
        outcome.get("narrative") or "",
        "",
        "## Soumission",
        "",
        f"- Appel commencé : {outcome.get('submission_started')}",
        f"- Socket ouvert : {outcome.get('socket_opened')}",
        f"- Statut HTTP : {outcome.get('http_status')}",
        f"- Provider request ID : {outcome.get('provider_request_id')}",
        f"- Statut d'autorisation : {outcome.get('authorization_status')}",
        f"- Identifiant d'autorisation : {outcome.get('authorization_id')}",
        f"- Facturation connue : {outcome.get('billing_known')}",
        f"- Type d'exception : {outcome.get('exception_type')}",
        f"- Statut d'exception : {outcome.get('exception_status')}",
        "",
        "## Coût",
        "",
        "Le coût complet de la requête reste inconnu. "
        "0.041 USD est la cellule publiée de sortie image pour 1024 × 1536 en qualité medium. "
        "Ce n'est pas une facture et ce n'est pas un plafond garanti par OpenAI. "
        "0.10 USD est le budget de planification de Transcriptor-ia.",
        "",
        f"- estimated_cost_usd = {outcome.get('estimated_cost_usd')}",
        f"- observed_cost_usd = {outcome.get('observed_cost_usd')}",
        f"- verified_maximum_cost_usd = {outcome.get('verified_maximum_cost_usd')}",
        f"- documented_image_output_estimate_usd = {outcome.get('documented_image_output_estimate_usd')}",
        "",
        "## Image",
        "",
        "Aucun titre, sous-titre, nom d'auteur, dos, code-barres ou fichier de couverture "
        "n'a été produit. L'examen artistique reste humain.",
        "",
        f"Signal dimension : {outcome.get('output_dimension_status')}",
        "",
    ]
    if outcome.get("block_reason"):
        lines.extend(["## Blocage", "", str(outcome["block_reason"]), ""])
    lines.extend(
        [
            "Arrêt après cette tentative. Aucun second appel payant n'a été effectué.",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = ["render"]
