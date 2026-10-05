"""Record CH003/CH004 human editorial acceptances. No copies. No rewrites."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.book_editorial_acceptance_4b219.hashes import file_sha256
from app.book_full_generation_preparation_4b226.constants import (
    CH003_EX005_STATUS,
    CH004_ALWAYS_FORMULATION,
    CH004_NEVER_FORMULATION,
    CH004_REF_ABSENT_STATUS,
    CH004_STRENGTHENED_DETAIL,
    DECISION_SOURCE,
    EDITORIAL_POLICY,
    EXPECTED_CH001_JSON_SHA256,
    EXPECTED_CH001_MD_SHA256,
    EXPECTED_CH002_RECOVERED_JSON_SHA256,
    EXPECTED_CH002_RECOVERED_MD_SHA256,
    EXPECTED_CH003_JSON_SHA256,
    EXPECTED_CH003_MD_SHA256,
    EXPECTED_CH004_JSON_SHA256,
    EXPECTED_CH004_MD_SHA256,
    EXPECTED_CH018_JSON_SHA256,
    EXPECTED_CH018_MD_SHA256,
    EXPECTED_ACCEPTED_JSON_SHA256,
    EXPECTED_ACCEPTED_MD_SHA256,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_PROMPT_1_1_SHA256,
    EXPECTED_SOURCE_MAP,
    EXPECTED_TRANSCRIPT,
    HUMAN_ACCEPTANCE_STATUS,
    MANIFEST_VERSION,
    MODEL,
    NARRATIVE_VOICE_CONTRACT,
    PHASE,
    PROMPT_VERSION,
    PROVIDER,
    RECORDING_DATE,
)
from app.book_full_generation_preparation_4b226.guard import (
    BookFullGenerationPreparation4226Error,
)
from app.book_full_generation_preparation_4b226.paths import (
    accepted_chapter_json_path,
    accepted_chapter_md_path,
    ch001_approved_json_path,
    ch001_approved_md_path,
    ch001_existing_manifest_path,
    ch002_approved_json_path,
    ch002_approved_md_path,
    ch002_existing_manifest_path,
    ch003_approved_json_path,
    ch003_approved_md_path,
    ch004_approved_json_path,
    ch004_approved_md_path,
    ch012_accepted_manifest_path,
    ch018_accepted_manifest_path,
    ch018_json_path,
    ch018_md_path,
    production_map_path,
    production_plan_path,
    production_transcript_path,
)


def _rel(path: Path) -> str:
    return str(path).replace("\\", "/")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise BookFullGenerationPreparation4226Error(f"Required artifact missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BookFullGenerationPreparation4226Error(f"Artifact is not an object: {path}")
    return payload


def _verify_hash(path: Path, expected: str, label: str) -> dict[str, Any]:
    hashed = file_sha256(path)
    if not hashed.get("exists"):
        raise BookFullGenerationPreparation4226Error(f"{label} is missing: {path}")
    if hashed.get("sha256") != expected:
        raise BookFullGenerationPreparation4226Error(
            f"{label} hash mismatch: {hashed.get('sha256')} ≠ {expected}. STOP."
        )
    return hashed


def _canonical_dependencies() -> dict[str, Any]:
    return {
        "source_map_path": _rel(production_map_path()),
        "source_map_sha256": EXPECTED_SOURCE_MAP,
        "editorial_plan_path": _rel(production_plan_path()),
        "editorial_plan_sha256": EXPECTED_EDITORIAL_PLAN,
        "clean_transcript_path": _rel(production_transcript_path()),
        "clean_transcript_sha256": EXPECTED_TRANSCRIPT,
    }


def inspect_existing_manifests() -> dict[str, Any]:
    rows = {
        "CH001": {
            "path": ch001_existing_manifest_path(),
            "expected_json": EXPECTED_CH001_JSON_SHA256,
            "expected_md": EXPECTED_CH001_MD_SHA256,
            "artifact_json": ch001_approved_json_path(),
            "artifact_md": ch001_approved_md_path(),
        },
        "CH002": {
            "path": ch002_existing_manifest_path(),
            "expected_json": EXPECTED_CH002_RECOVERED_JSON_SHA256,
            "expected_md": EXPECTED_CH002_RECOVERED_MD_SHA256,
            "artifact_json": ch002_approved_json_path(),
            "artifact_md": ch002_approved_md_path(),
        },
        "CH012": {
            "path": ch012_accepted_manifest_path(),
            "expected_json": EXPECTED_ACCEPTED_JSON_SHA256,
            "expected_md": EXPECTED_ACCEPTED_MD_SHA256,
            "artifact_json": accepted_chapter_json_path(),
            "artifact_md": accepted_chapter_md_path(),
        },
        "CH018": {
            "path": ch018_accepted_manifest_path(),
            "expected_json": EXPECTED_CH018_JSON_SHA256,
            "expected_md": EXPECTED_CH018_MD_SHA256,
            "artifact_json": ch018_json_path(),
            "artifact_md": ch018_md_path(),
        },
    }
    verified: dict[str, Any] = {}
    for chapter_id, spec in rows.items():
        manifest = _load_json(spec["path"])
        json_hash = _verify_hash(spec["artifact_json"], spec["expected_json"], f"{chapter_id} JSON")
        md_hash = _verify_hash(spec["artifact_md"], spec["expected_md"], f"{chapter_id} Markdown")
        status = str(
            manifest.get("status")
            or (manifest.get("human_acceptance") or {}).get("status")
            or ""
        )
        accepted = status in {
            HUMAN_ACCEPTANCE_STATUS,
            "accepted",
            "HUMAN_EDITORIALLY_ACCEPTED",
        }
        if not accepted:
            raise BookFullGenerationPreparation4226Error(
                f"{chapter_id} existing manifest status is {status!r}. STOP."
            )
        verified[chapter_id] = {
            "chapter_id": chapter_id,
            "manifest_path": _rel(spec["path"]),
            "manifest_exists": True,
            "status": HUMAN_ACCEPTANCE_STATUS,
            "json_sha256": json_hash["sha256"],
            "markdown_sha256": md_hash["sha256"],
            "json_path": _rel(spec["artifact_json"]),
            "markdown_path": _rel(spec["artifact_md"]),
            "unchanged": True,
        }
    return verified


def _trace_item(items: list[dict[str, Any]], kind: str, item_id: str) -> dict[str, Any]:
    for item in items:
        if item.get("kind") == kind and item.get("id") == item_id:
            return item
    return {}


def inspect_ch003() -> dict[str, Any]:
    json_path = ch003_approved_json_path()
    md_path = ch003_approved_md_path()
    json_hash = _verify_hash(json_path, EXPECTED_CH003_JSON_SHA256, "CH003 JSON")
    md_hash = _verify_hash(md_path, EXPECTED_CH003_MD_SHA256, "CH003 Markdown")
    structural = _load_json(json_path.parent / "structural_validation.json")
    idea = _load_json(json_path.parent / "idea_traceability_review.json")
    ex_ref = _load_json(json_path.parent / "ex_ref_traceability_review.json")
    prompt = _load_json(json_path.parent / "prompt_manifest.json")
    if structural.get("status") != "PASS":
        raise BookFullGenerationPreparation4226Error(
            f"CH003 structural validation is {structural.get('status')!r}. STOP."
        )
    if list(idea.get("ideas_missing_from_paras_e") or []):
        raise BookFullGenerationPreparation4226Error(
            "CH003 IDEA coverage is incomplete. STOP."
        )
    items = list(ex_ref.get("items") or [])
    ex005 = _trace_item(items, "EX", "EX005")
    if ex005.get("status") != CH003_EX005_STATUS:
        raise BookFullGenerationPreparation4226Error(
            f"CH003 EX005 status drifted: {ex005.get('status')!r}. STOP."
        )
    return {
        "chapter_id": "CH003",
        "json": json_hash,
        "markdown": md_hash,
        "structural_status": structural.get("status"),
        "validator_version": structural.get("validator_version"),
        "ideas_expected_count": idea.get("ideas_expected_count"),
        "ideas_found_count": idea.get("ideas_found_count"),
        "ideas_missing": list(idea.get("ideas_missing_from_paras_e") or []),
        "src_invalid": list(idea.get("src_handles_invalid") or []),
        "ex005": ex005,
        "prompt_version": prompt.get("version") or PROMPT_VERSION,
        "prompt_sha256": prompt.get("prompt_sha256") or EXPECTED_PROMPT_1_1_SHA256,
        "model_id": f"{PROVIDER}/{MODEL}",
        "copied": False,
        "modified": False,
    }


def inspect_ch004() -> dict[str, Any]:
    json_path = ch004_approved_json_path()
    md_path = ch004_approved_md_path()
    json_hash = _verify_hash(json_path, EXPECTED_CH004_JSON_SHA256, "CH004 JSON")
    md_hash = _verify_hash(md_path, EXPECTED_CH004_MD_SHA256, "CH004 Markdown")
    markdown = md_path.read_text(encoding="utf-8")
    if CH004_ALWAYS_FORMULATION not in markdown:
        raise BookFullGenerationPreparation4226Error(
            "Approved CH004 markdown no longer contains the always formulation. STOP."
        )
    if CH004_NEVER_FORMULATION not in markdown:
        raise BookFullGenerationPreparation4226Error(
            "Approved CH004 markdown no longer contains the never formulation. STOP."
        )
    structural = _load_json(json_path.parent / "structural_validation.json")
    idea = _load_json(json_path.parent / "idea_traceability_review.json")
    ex_ref = _load_json(json_path.parent / "ex_ref_traceability_review.json")
    editorial = _load_json(json_path.parent / "editorial_readiness_review.json")
    prompt = _load_json(json_path.parent / "prompt_manifest.json")
    if structural.get("status") != "PASS":
        raise BookFullGenerationPreparation4226Error(
            f"CH004 structural validation is {structural.get('status')!r}. STOP."
        )
    if list(idea.get("ideas_missing_from_paras_e") or []):
        raise BookFullGenerationPreparation4226Error(
            "CH004 IDEA coverage is incomplete. STOP."
        )
    items = list(ex_ref.get("items") or [])
    refs = {
        item_id: _trace_item(items, "REF", item_id)
        for item_id in ("REF011", "REF012", "REF013")
    }
    for item_id, item in refs.items():
        if item.get("status") != CH004_REF_ABSENT_STATUS:
            raise BookFullGenerationPreparation4226Error(
                f"CH004 {item_id} status drifted: {item.get('status')!r}. STOP."
            )
    strengthened = [
        row
        for row in (editorial.get("potential_substantive_issues") or [])
        if row.get("code") == "STRENGTHENED_CLAIM"
    ]
    if not strengthened:
        raise BookFullGenerationPreparation4226Error(
            "CH004 STRENGTHENED_CLAIM observation is missing. STOP."
        )
    if strengthened[0].get("detail") != CH004_STRENGTHENED_DETAIL:
        raise BookFullGenerationPreparation4226Error(
            "CH004 STRENGTHENED_CLAIM formulation drifted. STOP."
        )
    return {
        "chapter_id": "CH004",
        "json": json_hash,
        "markdown": md_hash,
        "structural_status": structural.get("status"),
        "validator_version": structural.get("validator_version"),
        "ideas_expected_count": idea.get("ideas_expected_count"),
        "ideas_found_count": idea.get("ideas_found_count"),
        "ideas_missing": list(idea.get("ideas_missing_from_paras_e") or []),
        "src_invalid": list(idea.get("src_handles_invalid") or []),
        "ref011": refs["REF011"],
        "ref012": refs["REF012"],
        "ref013": refs["REF013"],
        "always_formulation_present": True,
        "never_formulation_present": True,
        "always_formulation": CH004_ALWAYS_FORMULATION,
        "never_formulation": CH004_NEVER_FORMULATION,
        "strengthened_claim_detail": CH004_STRENGTHENED_DETAIL,
        "prompt_version": prompt.get("version") or PROMPT_VERSION,
        "prompt_sha256": prompt.get("prompt_sha256") or EXPECTED_PROMPT_1_1_SHA256,
        "model_id": f"{PROVIDER}/{MODEL}",
        "copied": False,
        "modified": False,
    }


def _manifest(
    *,
    chapter_id: str,
    inspection: dict[str, Any],
    extra: dict[str, Any],
) -> dict[str, Any]:
    json_info = inspection["json"]
    md_info = inspection["markdown"]
    payload = {
        "phase": PHASE,
        "manifest_version": MANIFEST_VERSION,
        "chapter_id": chapter_id,
        "approval_origin": DECISION_SOURCE,
        "approval_origin_detail": "explicit_user_decision",
        "approved_artifact_paths": {
            "json": json_info["path"],
            "markdown": md_info["path"],
        },
        "json_sha256": json_info["sha256"],
        "markdown_sha256": md_info["sha256"],
        "model_id": inspection["model_id"],
        "prompt_id": inspection["prompt_version"],
        "prompt_sha256": inspection["prompt_sha256"],
        "existing_structural_validation": inspection["structural_status"],
        "validator_version": inspection.get("validator_version"),
        "idea_coverage": {
            "expected": inspection.get("ideas_expected_count"),
            "found": inspection.get("ideas_found_count"),
            "missing": inspection.get("ideas_missing"),
        },
        "src_ex_ref_unc_state": extra.get("src_ex_ref_unc_state"),
        "status": HUMAN_ACCEPTANCE_STATUS,
        "automated_semantic_certification": "not_performed",
        "recording_date": RECORDING_DATE,
        "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "publication_authorization": "not_granted",
        "chapter_copied": False,
        "chapter_modified": False,
        "automatic_rewrite_forbidden": True,
        "canonical_dependencies": _canonical_dependencies(),
        "applicable_editorial_policy": EDITORIAL_POLICY,
        "applicable_narrative_voice_contract": NARRATIVE_VOICE_CONTRACT,
        "secrets_included": False,
    }
    for key, value in extra.items():
        if key != "src_ex_ref_unc_state":
            payload[key] = value
    return payload


def record_acceptances() -> dict[str, Any]:
    existing = inspect_existing_manifests()
    ch003 = inspect_ch003()
    ch004 = inspect_ch004()
    ch003_manifest = _manifest(
        chapter_id="CH003",
        inspection=ch003,
        extra={
            "approved_version": "4b225_generated_candidate",
            "src_ex_ref_unc_state": {
                "src_invalid": ch003["src_invalid"],
                "EX005": {
                    "status": CH003_EX005_STATUS,
                    "traced": False,
                    "in_allowed_handles": True,
                    "observation": (
                        "EX005 handle is absent from the candidate. Handle absence "
                        "is not treated as a content omission. The current "
                        "formulation is preserved. It does not trigger an "
                        "automatic rewrite of the accepted chapter."
                    ),
                },
            },
            "documented_observations_do_not_trigger_rewrite": True,
        },
    )
    ch004_manifest = _manifest(
        chapter_id="CH004",
        inspection=ch004,
        extra={
            "approved_version": "4b225_generated_candidate",
            "src_ex_ref_unc_state": {
                "src_invalid": ch004["src_invalid"],
                "REF011": {
                    "status": CH004_REF_ABSENT_STATUS,
                    "traced": False,
                    "in_allowed_handles": True,
                },
                "REF012": {
                    "status": CH004_REF_ABSENT_STATUS,
                    "traced": False,
                    "in_allowed_handles": True,
                },
                "REF013": {
                    "status": CH004_REF_ABSENT_STATUS,
                    "traced": False,
                    "in_allowed_handles": True,
                },
                "always_never_formulations": {
                    "always": CH004_ALWAYS_FORMULATION,
                    "never": CH004_NEVER_FORMULATION,
                    "preserved": True,
                    "strengthened_claim_detail": CH004_STRENGTHENED_DETAIL,
                    "observation": (
                        "REF011, REF012, and REF013 handles are absent. Handle "
                        "absence is not treated as a content omission. The "
                        "formulations always / never are preserved exactly. "
                        "These observations remain documented and do not "
                        "trigger an automatic rewrite of the accepted chapter."
                    ),
                },
            },
            "always_formulation_present": True,
            "never_formulation_present": True,
            "always_formulation": CH004_ALWAYS_FORMULATION,
            "never_formulation": CH004_NEVER_FORMULATION,
            "documented_observations_do_not_trigger_rewrite": True,
        },
    )
    verify_ch003 = inspect_ch003()
    verify_ch004 = inspect_ch004()
    if verify_ch003["json"]["sha256"] != ch003_manifest["json_sha256"]:
        raise BookFullGenerationPreparation4226Error("CH003 JSON changed after recording. STOP.")
    if verify_ch003["markdown"]["sha256"] != ch003_manifest["markdown_sha256"]:
        raise BookFullGenerationPreparation4226Error(
            "CH003 Markdown changed after recording. STOP."
        )
    if verify_ch004["json"]["sha256"] != ch004_manifest["json_sha256"]:
        raise BookFullGenerationPreparation4226Error("CH004 JSON changed after recording. STOP.")
    if verify_ch004["markdown"]["sha256"] != ch004_manifest["markdown_sha256"]:
        raise BookFullGenerationPreparation4226Error(
            "CH004 Markdown changed after recording. STOP."
        )
    inventory = accepted_chapters_inventory(
        existing=existing,
        ch003=ch003_manifest,
        ch004=ch004_manifest,
    )
    return {
        "phase": PHASE,
        "CH003_HUMAN_ACCEPTANCE": HUMAN_ACCEPTANCE_STATUS,
        "CH004_HUMAN_ACCEPTANCE": HUMAN_ACCEPTANCE_STATUS,
        "ch003": ch003_manifest,
        "ch004": ch004_manifest,
        "existing_manifests": existing,
        "accepted_chapters_inventory": inventory,
        "post_record_hash_verification": "PASS",
        "chapters_copied": False,
        "chapters_modified": False,
        "publication": False,
        "secrets_included": False,
    }


def accepted_chapters_inventory(
    *,
    existing: dict[str, Any],
    ch003: dict[str, Any],
    ch004: dict[str, Any],
) -> dict[str, Any]:
    chapters = [
        {
            "chapter_id": "CH001",
            "status": HUMAN_ACCEPTANCE_STATUS,
            "approved_version": "4b223_generated_candidate",
            "json_path": existing["CH001"]["json_path"],
            "markdown_path": existing["CH001"]["markdown_path"],
            "json_sha256": existing["CH001"]["json_sha256"],
            "markdown_sha256": existing["CH001"]["markdown_sha256"],
            "manifest_path": existing["CH001"]["manifest_path"],
            "protected": True,
        },
        {
            "chapter_id": "CH002",
            "status": HUMAN_ACCEPTANCE_STATUS,
            "approved_version": "offline_derived_recovered",
            "json_path": existing["CH002"]["json_path"],
            "markdown_path": existing["CH002"]["markdown_path"],
            "json_sha256": existing["CH002"]["json_sha256"],
            "markdown_sha256": existing["CH002"]["markdown_sha256"],
            "manifest_path": existing["CH002"]["manifest_path"],
            "protected": True,
        },
        {
            "chapter_id": "CH003",
            "status": HUMAN_ACCEPTANCE_STATUS,
            "approved_version": "4b225_generated_candidate",
            "json_path": ch003["approved_artifact_paths"]["json"],
            "markdown_path": ch003["approved_artifact_paths"]["markdown"],
            "json_sha256": ch003["json_sha256"],
            "markdown_sha256": ch003["markdown_sha256"],
            "protected": True,
        },
        {
            "chapter_id": "CH004",
            "status": HUMAN_ACCEPTANCE_STATUS,
            "approved_version": "4b225_generated_candidate",
            "json_path": ch004["approved_artifact_paths"]["json"],
            "markdown_path": ch004["approved_artifact_paths"]["markdown"],
            "json_sha256": ch004["json_sha256"],
            "markdown_sha256": ch004["markdown_sha256"],
            "protected": True,
        },
        {
            "chapter_id": "CH012",
            "status": HUMAN_ACCEPTANCE_STATUS,
            "approved_version": "chapter_candidate_authorial_v2",
            "json_path": existing["CH012"]["json_path"],
            "markdown_path": existing["CH012"]["markdown_path"],
            "json_sha256": existing["CH012"]["json_sha256"],
            "markdown_sha256": existing["CH012"]["markdown_sha256"],
            "manifest_path": existing["CH012"]["manifest_path"],
            "protected": True,
        },
        {
            "chapter_id": "CH018",
            "status": HUMAN_ACCEPTANCE_STATUS,
            "approved_version": "4b221_generated_candidate",
            "json_path": existing["CH018"]["json_path"],
            "markdown_path": existing["CH018"]["markdown_path"],
            "json_sha256": existing["CH018"]["json_sha256"],
            "markdown_sha256": existing["CH018"]["markdown_sha256"],
            "manifest_path": existing["CH018"]["manifest_path"],
            "protected": True,
        },
    ]
    return {
        "phase": PHASE,
        "accepted_chapter_ids": [row["chapter_id"] for row in chapters],
        "accepted_chapter_count": len(chapters),
        "all_protected": True,
        "must_not_be_regenerated": True,
        "must_not_be_rewritten": True,
        "semantic_certification": "not_performed",
        "publication_authorization": "not_granted",
        "chapters": chapters,
        "secrets_included": False,
    }


__all__ = [
    "accepted_chapters_inventory",
    "inspect_ch003",
    "inspect_ch004",
    "inspect_existing_manifests",
    "record_acceptances",
]
