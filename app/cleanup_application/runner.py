"""
Orchestration de la Phase 3A.2B.

    charge + valide les sources
          |
    hash AVANT (7 artefacts protégés)
          |
    population + POLICY_B_PLUS_V1
          |
    préflight removal_set          STOP si échec
          |
    transformer (vue clean en mémoire)
          |
    validation clean + réversibilité
          |
    audit en mémoire (+ hashes clean)
          |
    hash APRÈS (sources protégées inchangées)
          |
    si apply : publication atomique des 3 sorties
    sinon    : dry-run, aucun fichier final
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.cleanup_application import audit as audit_module
from app.cleanup_application import integrity as integrity_module
from app.cleanup_application import loader as loader_module
from app.cleanup_application import planner as planner_module
from app.cleanup_application import restore as restore_module
from app.cleanup_application import transformer as transformer_module
from app.cleanup_application import validator as validator_module
from app.cleanup_application import writer as writer_module
from app.cleanup_application.constants import DECISION_AUTO_REMOVE, POLICY_B_PLUS
from app.cleanup_application.models import ApplicationPlan
from app.transcript_models import TranscriptDocument


@dataclass(frozen=True)
class CleanupApplicationResult:
    project_name: str
    dry_run: bool
    plan: ApplicationPlan
    original: TranscriptDocument
    clean: TranscriptDocument
    clean_txt: str
    audit: dict
    paths: dict[str, Path]
    integrity_before: integrity_module.IntegritySnapshot
    integrity_after: integrity_module.IntegritySnapshot
    published: bool


def run_cleanup_application(
    project_name: str,
    *,
    apply: bool = False,
    sortie_dir: Path | None = None,
) -> CleanupApplicationResult:
    sources = loader_module.load_and_validate_sources(project_name, sortie_dir=sortie_dir)
    original: TranscriptDocument = sources["transcript_document"]

    integrity_before = integrity_module.snapshot_sources(project_name, sortie_dir=sortie_dir)

    records = planner_module.build_records(sources["blocks"], sources["classification"])
    plan = planner_module.plan_application(
        project_name=project_name,
        records=records,
        document=original,
        language_by_src=sources["language_by_src"],
        block_extras=sources["block_extras"],
    )

    validator_module.validate_removal_set(plan, original, sources["language_by_src"])

    clean = transformer_module.transform_document(original, plan)
    clean_txt = transformer_module.render_clean_text(clean)

    validator_module.validate_clean_transcript(
        original, clean, plan, sources["language_by_src"]
    )
    restore_module.assert_reversible(original, clean, plan.removal_snapshots)

    clean_json_payload = clean.to_dict()
    clean_json_text = writer_module.dumps_canonical(clean_json_payload)
    clean_data_sha = writer_module.sha256_of_text(clean_json_text)
    clean_txt_sha = writer_module.sha256_of_text(clean_txt)

    rendered_from_payload = transformer_module.render_clean_text(clean)
    txt_matches_json = rendered_from_payload == clean_txt

    validation = {
        "preflight_ok": True,
        "clean_transcript_ok": True,
        "reversibility_ok": True,
        "txt_matches_json": txt_matches_json,
        "removal_set_count": len(plan.removal_set),
        "removal_set_unique": len(plan.removal_set) == len(plan.removal_snapshots),
        "policy": POLICY_B_PLUS,
        "auto_remove_blocks": len(plan.blocks_with(DECISION_AUTO_REMOVE)),
    }
    if not txt_matches_json:
        from app.cleanup_application.errors import CleanTranscriptError

        raise CleanTranscriptError("transcript.txt clean ≠ rendu du transcript_data clean.")

    audit = audit_module.build_audit(
        plan=plan,
        original=original,
        clean=clean,
        integrity_before=integrity_before,
        simulation=sources["simulation"],
        clean_transcript_data_sha256=clean_data_sha,
        clean_transcript_txt_sha256=clean_txt_sha,
        validation=validation,
    )

    integrity_after = integrity_module.snapshot_sources(project_name, sortie_dir=sortie_dir)
    integrity_module.ensure_unchanged(integrity_before, integrity_after)

    published = False
    paths = writer_module.output_paths(project_name, sortie_dir=sortie_dir)
    if apply:
        paths = writer_module.publish_outputs(
            project_name=project_name,
            clean_json_payload=clean_json_payload,
            clean_txt=clean_txt,
            audit_payload=audit,
            sortie_dir=sortie_dir,
        )
        published = True
        integrity_after = integrity_module.snapshot_sources(
            project_name, sortie_dir=sortie_dir
        )
        integrity_module.ensure_unchanged(integrity_before, integrity_after)

    return CleanupApplicationResult(
        project_name=project_name,
        dry_run=not apply,
        plan=plan,
        original=original,
        clean=clean,
        clean_txt=clean_txt,
        audit=audit,
        paths=paths,
        integrity_before=integrity_before,
        integrity_after=integrity_after,
        published=published,
    )
