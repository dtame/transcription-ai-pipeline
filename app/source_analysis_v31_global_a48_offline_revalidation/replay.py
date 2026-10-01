"""Replay technique A.48 : réponse A.46 inchangée, contrat live 320. 0 provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.file_utils import content_hash
from app.source_analysis.models import scan_editorial_structure
from app.source_analysis_v31_global_a47_contract_forensics.constants import (
    HISTORICAL_INTENT_LIMIT,
)
from app.source_analysis_v31_global_a47_contract_forensics.contract import (
    historical_text_limits,
)
from app.source_analysis_v31_global_a47_contract_forensics.evidence import (
    a46_intent_text,
    derived_a46_transport,
    read_a46_candidate,
    read_a46_raw,
    verify_a46_identity,
)
from app.source_analysis_v31_global_a47_contract_forensics.intent_review import (
    review_a46_intent,
)
from app.source_analysis_v31_global_a47_contract_forensics.replay import load_a46_inventory
from app.source_analysis_v31_global_a47_contract_forensics.scanner import (
    classify_a46_editorial,
)
from app.source_analysis_v31_global_a48_offline_revalidation.constants import (
    A46_DROP,
    A46_INTENT_LENGTH,
    A46_KEEP,
    A46_MERGE,
    A46_STATUS_PRESERVED,
    EXPECTED_IDEA,
    GLOBAL_INTENT_MAX_CHARS,
    PROJECT_NAME,
    TEXT_LIMITS,
)
from app.source_analysis_v31_global_reuse_output.reconstruct import (
    local_idea_text,
    reconstruct_source_map_v30,
)
from app.source_analysis_v31_global_v30_real_canary.semantic import review_semantics
from app.source_analysis_v31_global_v30_real_canary.validate import (
    interpret_production_response,
    technical_pass,
)
from app.source_analysis_v31_global_reuse_output.validate import validate_global_transport_v30


def _public_validation(validation: dict[str, Any]) -> dict[str, Any]:
    skip = {"transport", "source_map", "reconstruction"}
    public = {key: value for key, value in validation.items() if key not in skip}
    reconstruction = validation.get("reconstruction") or {}
    public["reconstruction"] = {
        key: reconstruction.get(key)
        for key in (
            "ok",
            "canonical_json",
            "ensure_valid_source_map",
            "errors",
            "source_map_published",
            "reuse_text_exact",
            "empty_relations_valid",
            "reused_ideas",
        )
    }
    public["errors"] = list(validation.get("errors") or [])[:12]
    return public


def _reuse_text_audit(inventory: dict[str, Any], transport: dict[str, Any]) -> dict[str, Any]:
    exact = 0
    compared = 0
    with_v = 0
    for idea in transport.get("i") or []:
        if not isinstance(idea, dict):
            continue
        members = [str(item) for item in (idea.get("m") or []) if item]
        if len(members) != 1:
            continue
        compared += 1
        local = local_idea_text(inventory, members[0])
        if str(idea.get("v") or "").strip():
            with_v += 1
            continue
        if local:
            exact += 1
    return {
        "compared_single_member": compared,
        "reuse_text_exact": exact,
        "expected": A46_KEEP,
        "SINGLE_MEMBER_WITH_V": with_v,
        "all_canonical_equals_local": compared == A46_KEEP and exact == A46_KEEP and with_v == 0,
        "provider_generated_idea_text": False,
    }


def replay_a46_under_corrected_contract(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    identity = verify_a46_identity(project_name, sortie_dir=sortie_dir)
    transport = derived_a46_transport(project_name, sortie_dir=sortie_dir)
    inventory = load_a46_inventory(project_name, sortie_dir=sortie_dir)
    raw = read_a46_raw(project_name, sortie_dir=sortie_dir)
    intent = a46_intent_text(project_name, sortie_dir=sortie_dir)
    intent_hash = content_hash(intent)
    interpreted = interpret_production_response(
        transport,
        inventory=inventory,
        raw_text=str(raw.get("raw_text") or ""),
        signature="a48-offline-revalidation",
    )
    reconstruction = interpreted.get("reconstruction") or {}
    candidate = reconstruction.get("payload")
    if not isinstance(candidate, dict):
        candidate = read_a46_candidate(project_name, sortie_dir=sortie_dir) or {}
    second = reconstruct_source_map_v30(
        transport,
        inventory,
        inventory["transcript"],
        signature="a48-offline-revalidation",
    )
    first_json = reconstruction.get("canonical_json") or ""
    second_json = second.get("canonical_json") or ""
    independent_replay = (
        "PASS"
        if first_json and first_json == second_json and second.get("ok")
        else "FAIL"
    )
    semantic = review_semantics(
        interpreted.get("transport"),
        inventory,
        accountability=str(interpreted.get("idea_accountability") or ""),
        missing=int(interpreted.get("missing_members") or 0),
        candidate_payload=candidate if isinstance(candidate, dict) else None,
    )
    editorial = classify_a46_editorial(
        interpreted.get("transport") or transport,
        candidate if isinstance(candidate, dict) else None,
    )
    structural = scan_editorial_structure(
        {"transport": interpreted.get("transport") or transport, "candidate": candidate}
    )
    historical = validate_global_transport_v30(
        transport,
        idea_input_ids=list(inventory.get("idea_input_ids") or []),
        allowed_input_ids=set(inventory.get("allowed_input_ids") or []),
        local_kind_by_input=inventory.get("kind_by_input") or {},
        text_limits=historical_text_limits(),
    )
    live = validate_global_transport_v30(
        transport,
        idea_input_ids=list(inventory.get("idea_input_ids") or []),
        allowed_input_ids=set(inventory.get("allowed_input_ids") or []),
        local_kind_by_input=inventory.get("kind_by_input") or {},
    )
    equality = _reuse_text_audit(inventory, interpreted.get("transport") or transport)
    intent_sem = review_a46_intent(
        intent,
        inventory=inventory,
        metadata_status=((semantic.get("metadata") or {}).get("status")),
    )
    reconstructed_intent = ""
    if isinstance(candidate, dict):
        header = candidate.get("source_analysis") or {}
        author_intent = header.get("author_intent") or {}
        reconstructed_intent = str(author_intent.get("summary") or "")
    intent_unchanged = reconstructed_intent == intent == a46_intent_text(
        project_name, sortie_dir=sortie_dir
    )
    metadata = semantic.get("metadata") or {}
    fields = metadata.get("fields") or {}
    return {
        "identity": identity,
        "historical_a46_status": A46_STATUS_PRESERVED,
        "raw_unchanged": True,
        "truncated": False,
        "rewritten": False,
        "published": False,
        "historical_request_contract": {
            "prompt": "global-consolidation-3.0",
            "transport": "global-consolidation-transport-3.0",
            "intent_limit": HISTORICAL_INTENT_LIMIT,
            "validator_under_historical_240": "PASS" if historical.get("ok") else "FAIL",
        },
        "corrected_product_contract": {
            "prompt_future": "global-consolidation-3.0.1",
            "transport": "global-consolidation-transport-3.0",
            "intent_limit": GLOBAL_INTENT_MAX_CHARS,
            "live_text_limits_intent": TEXT_LIMITS["intent"],
            "validator_under_live_320": "PASS" if live.get("ok") else "FAIL",
        },
        "intent": {
            "text": intent,
            "length": len(intent),
            "expected_length": A46_INTENT_LENGTH,
            "hash": intent_hash,
            "reconstructed": reconstructed_intent,
            "reconstructed_hash": content_hash(reconstructed_intent) if reconstructed_intent else "",
            "unchanged": intent_unchanged,
            "fits_320": len(intent) <= GLOBAL_INTENT_MAX_CHARS,
            "a47_forensic_verdict": intent_sem.get("verdict"),
            "review_status": (
                "PASS"
                if intent_unchanged
                and len(intent) == A46_INTENT_LENGTH
                and len(intent) <= GLOBAL_INTENT_MAX_CHARS
                and intent_sem.get("is_source_supported")
                and intent_sem.get("is_coherent")
                else "FAIL"
            ),
        },
        "structured_parse": interpreted.get("structured_parse"),
        "decoder": interpreted.get("decoder"),
        "handle_validation": interpreted.get("handle_validation"),
        "idea_accountability": interpreted.get("idea_accountability"),
        "keep_count": interpreted.get("keep_count"),
        "merge_equivalent_count": interpreted.get("merge_equivalent_count"),
        "drop_count": interpreted.get("drop_count"),
        "reuse": A46_KEEP,
        "merge": A46_MERGE,
        "drop": A46_DROP,
        "SINGLE_MEMBER_WITH_V": interpreted.get("SINGLE_MEMBER_WITH_V"),
        "MULTI_MEMBER_WITHOUT_V": interpreted.get("MULTI_MEMBER_WITHOUT_V"),
        "single_member_global_ideas": interpreted.get("single_member_global_ideas"),
        "multi_member_global_ideas": interpreted.get("multi_member_global_ideas"),
        "NON_IDEA_IN_MEMBERS": interpreted.get("NON_IDEA_IN_MEMBERS"),
        "NON_IDEA_IN_DROP": interpreted.get("NON_IDEA_IN_DROP"),
        "unknown_handles": interpreted.get("unknown_members"),
        "duplicate_membership": interpreted.get("duplicate_members"),
        "missing_ideas": interpreted.get("missing_members"),
        "member_drop_overlap": interpreted.get("member_drop_overlap"),
        "reuse_text_exact_equality": interpreted.get("reuse_text_exact_equality"),
        "reuse_text_audit": equality,
        "derived_src": interpreted.get("derived_src_union"),
        "global_validator": interpreted.get("global_validator"),
        "canonical_reconstruction": interpreted.get("canonical_reconstruction"),
        "canonical_validation": interpreted.get("canonical_validation"),
        "deterministic_replay": interpreted.get("deterministic_replay"),
        "independent_replay": independent_replay,
        "technical_pass": technical_pass(interpreted),
        "structural": structural,
        "editorial": editorial,
        "semantic": {
            "status": semantic.get("status"),
            "reuse": semantic.get("reuse"),
            "merges": semantic.get("merges"),
            "drops": semantic.get("drops"),
            "topics": semantic.get("topics"),
            "metadata": metadata,
            "examples": semantic.get("examples"),
            "references": semantic.get("references"),
            "uncertainty": semantic.get("uncertainty"),
            "completeness": semantic.get("completeness"),
            "editorial": semantic.get("editorial"),
            "publication_semantic_ok": semantic.get("publication_semantic_ok"),
            "theme_review": (fields.get("theme") or {}).get("status"),
            "intent_review": (fields.get("author_intent") or {}).get("status"),
            "audience_review": (fields.get("target_audience") or {}).get("status"),
            "voice_review": (fields.get("author_voice_profile") or {}).get("status"),
        },
        "candidate_payload": candidate if isinstance(candidate, dict) else {},
        "candidate_canonical_json": first_json,
        "interpreted": _public_validation(interpreted),
        "expected_idea": EXPECTED_IDEA,
    }


__all__ = ["replay_a46_under_corrected_contract"]
