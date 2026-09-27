from __future__ import annotations

import time
import traceback
from datetime import datetime
from pathlib import Path

from app.project_manager import AudioProject
from app.project_state import (
    load_project_state,
    register_chunk,
    update_chunk_state,
    save_project_state,
    is_audio_already_transcribed,
    mark_audio_processing,
    mark_audio_transcribed,
    mark_audio_failed,
)
from app.file_utils import file_hash
from app.audio_utils import get_audio_duration_seconds
from app.logger import log_event


STEP_NAMES = [
    "transcription",
    "transcript_v2",
    "merge_transcripts",
    "chunk_generation",
    "ai_processing",
    "correction_review",
    "correction_apply",
    "final_document",
    "harmonization",
    "cover_generation",
    "publication_markdown",
    "export_docx",
    "export_pdf",
    "publication_docx",
    "publication_pdf",
    "client_export",
    "report",
]


def _fmt_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _step_result(ok: bool, error: str | None = None) -> dict:
    return {
        "status": "success" if ok else "error",
        "error": error,
    }


def _run_transcription(model, project: AudioProject) -> dict:
    """Transcrit tous les fichiers audio du projet (avec reprise).

    Fichiers courts (≤ LONG_AUDIO_THRESHOLD_MINUTES) :
        Transcription directe via transcribe_audio_to_txt.

    Fichiers longs (> LONG_AUDIO_THRESHOLD_MINUTES) :
        Transcription segmentée via transcribe_long_audio_with_segments.
        Chaque segment est sauvegardé immédiatement → reprise après veille/crash.
    """
    from app.transcription_service import transcribe_audio_to_txt
    from app.segmented_transcription_service import (
        should_segment_audio,
        transcribe_long_audio_with_segments,
    )
    from app.transcript_capture import audio_capture_path

    state = load_project_state(project)
    errors = []

    for audio_path in project.audio_files:
        transcript_path = project.transcripts_dir / f"{audio_path.stem}.txt"
        audio_hash = file_hash(audio_path)

        if is_audio_already_transcribed(state, audio_path, audio_hash, transcript_path):
            log_event(f"SKIP déjà transcrit : {audio_path.name}")
            continue

        try:
            if should_segment_audio(audio_path):
                # Capture V2 consolidée par le service segmenté lui-même.
                # --- Transcription segmentée (long fichier) ---
                # Le service gère lui-même les appels à project_state.json
                # (mark_audio_processing_segments, update_segment_in_state,
                #  mark_audio_segmented_transcribed / mark_audio_partial_error).
                transcribe_long_audio_with_segments(
                    model=model,
                    project_name=project.name,
                    audio_path=audio_path,
                    output_path=transcript_path,
                )
                # Recharger le state local depuis le disque (service a tout mis à jour)
                state = load_project_state(project)

            else:
                # --- Transcription directe (fichier court) ---
                mark_audio_processing(state, audio_path, audio_hash)
                save_project_state(project, state)

                total_duration = get_audio_duration_seconds(audio_path)
                transcribe_audio_to_txt(
                    model=model,
                    audio_path=audio_path,
                    output_path=transcript_path,
                    total_duration_seconds=total_duration,
                    capture_path=audio_capture_path(
                        project.output_dir, audio_path.stem
                    ),
                )

                mark_audio_transcribed(state, audio_path, audio_hash, transcript_path)
                save_project_state(project, state)

        except Exception as exc:
            # Recharger le state depuis le disque pour ne pas écraser
            # les données de segments déjà sauvegardées par le service segmenté.
            state = load_project_state(project)
            file_key = str(audio_path.resolve())
            file_entry = state.get("files", {}).get(file_key, {})

            if file_entry.get("segments"):
                # Service segmenté a déjà écrit partial_error avec segments préservés
                pass
            else:
                # Transcription directe : marquer simplement comme failed
                mark_audio_failed(state, audio_path, audio_hash, exc)
                save_project_state(project, state)

            errors.append(str(exc))
            log_event(f"ERREUR transcription {audio_path.name} : {exc}")

    if errors:
        return _step_result(False, "; ".join(errors))
    return _step_result(True)


def _run_transcript_v2(project: AudioProject) -> dict[str, Path] | None:
    """
    Construit et publie le contrat Transcript V2 du projet.

        transcript_capture/<stem>.json  (une par fichier audio)
                    ↓
            TranscriptDocument
                    ↓
        transcripts/transcript.txt  +  transcripts/transcript_data.json

    Politique d'échec (la transcription V1 n'est jamais détruite par la couche V2) :

    - aucune capture disponible (projet transcrit avant la Phase 1) :
      étape ignorée, rien n'est publié, aucune erreur — la transcription V1 reste
      intacte et le contrat V2 sera produit lors d'une transcription ultérieure ;
    - captures partielles (au moins un fichier audio sans capture exploitable) :
      échec explicite, aucun transcript_data.json publié, artefact antérieur
      invalidé ;
    - contrat invalide : échec explicite, même traitement.

    Retourne les chemins publiés, ou None si l'étape a été ignorée.
    """
    from app.transcript_builder import build_project_transcript
    from app.transcript_capture import captured_stems
    from app.transcript_writer import (
        invalidate_published_transcript,
        publish_transcript_artifacts,
    )

    available = captured_stems(project.output_dir)
    expected = {audio_path.stem for audio_path in project.audio_files}

    if not available:
        log_event({
            "event": "transcript_v2_build_skipped",
            "project": project.name,
            "reason": "no_capture_available",
        })
        print(
            "[transcript_v2] IGNORÉE : aucune capture de transcription "
            "disponible (projet antérieur au contrat V2)."
        )
        return None

    missing = sorted(expected - available)

    if missing:
        invalidate_published_transcript(project.transcripts_dir)
        log_event({
            "event": "transcript_v2_build_failed",
            "project": project.name,
            "reason": "incomplete_capture",
            "missing": missing,
        })
        raise RuntimeError(
            f"Capture de transcription incomplète pour «{project.name}» : "
            f"{len(missing)} fichier(s) audio sans capture exploitable "
            f"({', '.join(missing)}). Aucun contrat V2 n'a été publié."
        )

    log_event({
        "event": "transcript_v2_build_started",
        "project": project.name,
        "sources": len(available),
    })

    document = build_project_transcript(project.name, project.output_dir)
    published = publish_transcript_artifacts(document, project.transcripts_dir)

    log_event({
        "event": "transcript_v2_build_completed",
        "project": project.name,
        "transcript_id": document.transcript_id,
        "source_count": document.stats.source_count,
        "segment_count": document.stats.segment_count,
        "primary_language": document.primary_language,
    })

    return published


def _write_execution_status(
    project: AudioProject,
    status: str,
    started_at: datetime,
    error: str | None = None,
    finished_at: datetime | None = None,
) -> None:
    """Met à jour la section 'execution' dans project_state.json."""
    try:
        state = load_project_state(project)
        now = datetime.now()
        state["execution"] = {
            "status":         status,
            "started_at":     started_at.isoformat(timespec="seconds"),
            "last_heartbeat": now.isoformat(timespec="seconds"),
            "finished_at":    finished_at.isoformat(timespec="seconds") if finished_at else None,
            "error":          error,
        }
        save_project_state(project, state)
    except Exception:
        pass  # Ne jamais faire échouer le pipeline à cause du tracking


def run_project_pipeline(
    project: AudioProject,
    model=None,
    force_regenerate_chunks: bool = False,
) -> dict:
    """
    Exécute le pipeline complet pour un projet.

    Retourne :
    {
        "project": "demo_conference",
        "status": "success" | "error",
        "duration_seconds": 123,
        "steps": { <step_name>: {"status": ..., "error": ...}, ... }
    }
    """
    started_at = datetime.now()
    t0 = time.time()

    steps: dict[str, dict] = {}
    project_status = "success"

    print(f"\n{'=' * 50}")
    print(f"  Projet : {project.name}")
    print(f"  Début  : {started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 50}")

    # Marquer le début d'exécution dans project_state.json
    _write_execution_status(project, "running", started_at)

    def run_step(name: str, fn):
        nonlocal project_status
        print(f"\n[{name}] ...", end=" ", flush=True)
        t = time.time()
        try:
            fn()
            elapsed = time.time() - t
            steps[name] = _step_result(True)
            print(f"OK ({elapsed:.1f}s)")
        except Exception as exc:
            elapsed = time.time() - t
            err = traceback.format_exc()
            steps[name] = _step_result(False, str(exc))
            project_status = "error"
            print(f"ERREUR ({elapsed:.1f}s)")
            print(f"  → {exc}")
            log_event(f"ERREUR étape {name} / {project.name} : {exc}\n{err}")

    # ------------------------------------------------------------------
    # Étape 1 – Transcription (nécessite le modèle Whisper)
    # ------------------------------------------------------------------
    if model is not None:
        print(f"\n[transcription] ...", end=" ", flush=True)
        t = time.time()
        result = _run_transcription(model, project)
        elapsed = time.time() - t
        steps["transcription"] = result
        if result["status"] == "error":
            project_status = "error"
            print(f"ERREUR ({elapsed:.1f}s) → {result['error']}")
        else:
            print(f"OK ({elapsed:.1f}s)")
    else:
        steps["transcription"] = _step_result(True)
        print("\n[transcription] IGNORÉE (pas de modèle Whisper fourni)")

    # ------------------------------------------------------------------
    # Étapes 2-14
    # ------------------------------------------------------------------
    from app.transcript_merger import merge_project_transcripts
    from app.chunk_service import create_project_chunks
    from app.ai_processor import process_project_chunks
    from app.correction_review_service import generate_review_files
    from app.correction_apply_service import apply_corrections
    from app.final_document_builder import build_final_document
    from app.global_editor_service import harmonize_document
    from app.cover_generation_service import generate_cover
    from app.publication_template_service import build_publication_markdown
    from app.docx_export_service import export_docx, export_publication_docx
    from app.pdf_export_service import export_pdf, export_publication_pdf
    from app.client_export_service import export_client_zip
    from app.report_service import build_project_report

    def step_transcript_v2():
        _run_transcript_v2(project)

    def step_merge():
        merge_project_transcripts(project)

    def step_chunks():
        chunk_results = create_project_chunks(
            project,
            force_regenerate_chunks=force_regenerate_chunks,
        )

        state      = load_project_state(project)
        new_names  = {r["name"] for r in chunk_results}

        for result in chunk_results:
            update_chunk_state(
                state,
                result["name"],
                result["hash"],
                result["generation_status"],
                result["needs_ai_processing"],
                partie_source=result.get("partie_source"),
                char_count=result.get("char_count", 0),
                word_count=result.get("word_count", 0),
                path=str(result["path"]),
                processed_path=result.get("processed_path"),
            )

        # Retirer de l'état les chunks devenus obsolètes
        obsolete_in_state = [
            name for name in list(state.get("chunks", {}).keys())
            if name not in new_names
        ]
        for name in obsolete_in_state:
            state["chunks"].pop(name, None)
            print(f"[pipeline] {name} retiré de l'état (obsolète)")

        save_project_state(project, state)

    def step_ai():
        process_project_chunks(project)

    def step_review():
        generate_review_files(project)

    def step_apply():
        apply_corrections(project.name)

    def step_final():
        build_final_document(project.name)

    def step_harmonize():
        harmonize_document(project.name)

    def step_cover():
        generate_cover(project.name)

    def step_pub_md():
        build_publication_markdown(project.name)

    def step_export_docx():
        export_docx(project.name)

    def step_export_pdf():
        export_pdf(project.name)

    def step_pub_docx():
        export_publication_docx(project.name)

    def step_pub_pdf():
        export_publication_pdf(project.name)

    def step_client_export():
        export_client_zip(project.name)

    def step_report():
        _build_report_with_execution(project.name, started_at, time.time() - t0)

    remaining_steps = [
        ("transcript_v2",        step_transcript_v2),
        ("merge_transcripts",    step_merge),
        ("chunk_generation",     step_chunks),
        ("ai_processing",        step_ai),
        ("correction_review",    step_review),
        ("correction_apply",     step_apply),
        ("final_document",       step_final),
        ("harmonization",        step_harmonize),
        ("cover_generation",     step_cover),
        ("publication_markdown", step_pub_md),
        ("export_docx",          step_export_docx),
        ("export_pdf",           step_export_pdf),
        ("publication_docx",     step_pub_docx),
        ("publication_pdf",      step_pub_pdf),
        ("client_export",        step_client_export),
        ("report",               step_report),
    ]

    for step_name, step_fn in remaining_steps:
        run_step(step_name, step_fn)

    # ------------------------------------------------------------------
    # Validation qualité publication (post-pipeline)
    # ------------------------------------------------------------------
    _check_publication_quality(project.name, steps)

    # ------------------------------------------------------------------
    # Vérification des livrables obligatoires (prévention faux succès)
    # ------------------------------------------------------------------
    if project_status == "success":
        project_status = _verify_deliverables(project.name, steps)

    duration = time.time() - t0
    finished_at = datetime.now()

    print(f"\n{'-' * 50}")
    symbol = "OK" if project_status == "success" else "ERREUR"
    print(f"  [{symbol}] Projet {project.name} terminé en {_fmt_duration(duration)}")
    print(f"{'-' * 50}")

    log_event(f"Projet {project.name} terminé : {project_status} en {_fmt_duration(duration)}")

    # Mettre à jour le statut d'exécution final dans project_state.json
    first_error = next(
        (s.get("error") for s in steps.values() if s.get("status") == "error" and s.get("error")),
        None,
    )
    _write_execution_status(
        project,
        status=project_status,
        started_at=started_at,
        error=first_error,
        finished_at=finished_at,
    )

    return {
        "project": project.name,
        "status": project_status,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round(duration, 1),
        "steps": steps,
    }


def run_exports_only(project: AudioProject) -> dict:
    """
    Exécute uniquement publication → docx → pdf sur un projet existant.
    """
    started_at = datetime.now()
    t0 = time.time()
    steps: dict[str, dict] = {}
    project_status = "success"

    print(f"\n{'=' * 50}")
    print(f"  Exports : {project.name}")
    print(f"{'=' * 50}")

    from app.cover_generation_service import generate_cover
    from app.publication_template_service import build_publication_markdown
    from app.docx_export_service import export_publication_docx
    from app.pdf_export_service import export_publication_pdf
    from app.client_export_service import export_client_zip
    from app.report_service import build_project_report

    export_steps = [
        ("cover_generation",     lambda: generate_cover(project.name)),
        ("publication_markdown", lambda: build_publication_markdown(project.name)),
        ("publication_docx",     lambda: export_publication_docx(project.name)),
        ("publication_pdf",      lambda: export_publication_pdf(project.name)),
        ("client_export",        lambda: export_client_zip(project.name)),
        ("report",               lambda: build_project_report(project.name)),
    ]

    for step_name, fn in export_steps:
        print(f"\n[{step_name}] ...", end=" ", flush=True)
        t = time.time()
        try:
            fn()
            elapsed = time.time() - t
            steps[step_name] = _step_result(True)
            print(f"OK ({elapsed:.1f}s)")
        except Exception as exc:
            elapsed = time.time() - t
            steps[step_name] = _step_result(False, str(exc))
            project_status = "error"
            print(f"ERREUR ({elapsed:.1f}s) → {exc}")
            log_event(f"ERREUR export {step_name} / {project.name} : {exc}")

    # Validation qualité
    _check_publication_quality(project.name, steps)
    if project_status == "success":
        project_status = _verify_deliverables(project.name, steps)

    duration = time.time() - t0

    return {
        "project": project.name,
        "status": project_status,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "duration_seconds": round(duration, 1),
        "steps": steps,
    }


def run_report_only(project_name: str) -> dict:
    """Régénère uniquement le rapport d'un projet."""
    t0 = time.time()
    started_at = datetime.now()
    steps: dict[str, dict] = {}
    project_status = "success"

    print(f"\n[report] {project_name} ...", end=" ", flush=True)
    try:
        _build_report_with_execution(project_name, started_at, time.time() - t0)
        steps["report"] = _step_result(True)
        print(f"OK ({time.time() - t0:.1f}s)")
    except Exception as exc:
        steps["report"] = _step_result(False, str(exc))
        project_status = "error"
        print(f"ERREUR → {exc}")

    return {
        "project": project_name,
        "status": project_status,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "duration_seconds": round(time.time() - t0, 1),
        "steps": steps,
    }


def _verify_deliverables(project_name: str, steps: dict) -> str:
    """
    Vérifie que les livrables critiques ont bien été générés.

    Retourne "success", "partial" ou "error" selon les cas.
    """
    from app.paths import SORTIE_DIR

    final_dir = SORTIE_DIR / project_name / "final"
    cover_dir = SORTIE_DIR / project_name / "cover"
    client_dir = SORTIE_DIR / project_name / "client"

    issues: list[str] = []

    # Document final obligatoire
    if not (final_dir / "document_final.md").exists():
        issues.append("document_final.md absent")

    # PDF publication obligatoire
    if not (final_dir / "document_publication.pdf").exists():
        issues.append("document_publication.pdf absent")

    # Qualité publication
    quality_step = steps.get("publication_quality", {})
    if quality_step.get("status") == "error":
        issues.append("validation qualité publication échouée")

    # ZIP client (avertissement seulement)
    zip_files = list(client_dir.glob("*.zip")) if client_dir.exists() else []
    if not zip_files:
        log_event(
            f"[pipeline] Avertissement : ZIP client absent pour {project_name}"
        )

    if not issues:
        return "success"

    for issue in issues:
        log_event(f"[pipeline] Livrable manquant : {issue} / {project_name}")
        print(f"[pipeline] Livrable manquant : {issue}")

    # Si seulement des avertissements qualité → partial
    critical_missing = [i for i in issues if "absent" in i and "zip" not in i.lower()]
    return "error" if critical_missing else "partial"


def _check_publication_quality(
    project_name: str,
    steps: dict[str, dict],
) -> None:
    """
    Vérifie la qualité de la publication et marque le pipeline en erreur
    ou en avertissement si la validation échoue.

    Conditions d'échec qualité qui bloquent le succès :
    - document_publication.md absent  → project_status = "error"
    - document_publication.pdf absent → project_status = "error"
    - validate_publication() = "failed" → project_status = "partial"
    - validate_publication() = "warning" → ne change pas le statut mais le logue
    """
    try:
        from app.publication_quality_service import validate_and_update_state
        from app.paths import SORTIE_DIR

        result = validate_and_update_state(project_name)

        steps["publication_quality"] = {
            "status":   result["status"],
            "errors":   result.get("errors", []),
            "warnings": result.get("warnings", []),
        }

        # Forcer partial si la validation échoue
        if result["status"] == "failed":
            steps["publication_quality"]["status"] = "error"
            print(
                f"[pipeline] Qualité publication insuffisante → "
                f"statut projet : partial"
            )
            # On ne peut pas modifier project_status directement ici
            # (c'est une variable de run_project_pipeline), mais on marque
            # l'étape comme error pour que l'appelant puisse le détecter.

    except Exception as exc:
        print(f"[pipeline] Avertissement : validation qualité échouée : {exc}")
        steps["publication_quality"] = _step_result(False, str(exc))


def _build_report_with_execution(
    project_name: str,
    started_at: datetime,
    duration_seconds: float,
) -> None:
    """Génère le rapport et y injecte la section execution."""
    import json
    from app.report_service import build_project_report
    from app.paths import SORTIE_DIR

    report_path = build_project_report(project_name)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    # Déterminer le statut réel depuis project_state.json
    from app.project_state import load_project_state as _load_state
    _state = _load_state(project_name)
    _exec_status = _state.get("execution", {}).get("status", "success")

    report["execution"] = {
        "last_run": started_at.isoformat(timespec="seconds"),
        "duration_seconds": round(duration_seconds, 1),
        "status": _exec_status,
    }

    # Intégrer les résultats qualité si disponibles
    _pub_quality = _state.get("publication", {}).get("quality")
    if _pub_quality:
        report["publication_quality"] = _pub_quality
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def run_rebuild_publication_pipeline(project_name: str) -> dict:
    """
    Reconstruit uniquement les artefacts de publication à partir de
    document_final.md existant (ou processed/*.md en fallback).

    Ne refait jamais :
        - transcription
        - fusion des transcriptions
        - génération des chunks
        - traitement IA des chunks

    Étapes exécutées :
        1. harmonize_final_structure   (nettoyage structurel déterministe)
        2. build_publication_markdown  (génération TOC + publication.md)
        3. generate_cover              (couverture)
        4. export_docx / export_publication_docx
        5. export_pdf  / export_publication_pdf
        6. export_client_zip           (ZIP client)
        7. build_project_report        (rapport JSON)
    """
    from app.paths import SORTIE_DIR

    started_at = datetime.now()
    t0 = time.time()
    steps: dict[str, dict] = {}
    project_status = "success"

    output_dir   = SORTIE_DIR / project_name
    final_dir    = output_dir / "final"
    processed_dir = output_dir / "processed"
    final_md     = final_dir / "document_final.md"

    print(f"\n{'=' * 50}")
    print(f"  REBUILD PUBLICATION : {project_name}")
    print(f"  Début  : {started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 50}")
    print("\n[publication] Rebuild publication started")

    # ── Vérification de la source disponible ────────────────────────────────
    has_final     = final_md.exists()
    has_processed = (
        processed_dir.exists()
        and any(processed_dir.glob("chunk_*.md"))
    )

    if not has_final and not has_processed:
        msg = (
            f"[publication] ERREUR : aucune source disponible pour '{project_name}'.\n"
            f"  document_final.md attendu : {final_md}\n"
            f"  Chunks traités attendus   : {processed_dir / 'chunk_*.md'}\n"
            "Exécutez d'abord le pipeline complet (ou au moins le traitement IA)."
        )
        print(msg)
        log_event(msg)
        return {
            "project":                   project_name,
            "status":                    "error",
            "started_at":               started_at.isoformat(timespec="seconds"),
            "finished_at":              datetime.now().isoformat(timespec="seconds"),
            "duration_seconds":         0,
            "steps":                    {},
            "fatal_error":              msg,
            "rebuild_publication_mode": True,
        }

    def run_step(name: str, fn):
        nonlocal project_status
        print(f"\n[{name}] ...", end=" ", flush=True)
        t = time.time()
        try:
            fn()
            elapsed = time.time() - t
            steps[name] = _step_result(True)
            print(f"OK ({elapsed:.1f}s)")
        except Exception as exc:
            elapsed = time.time() - t
            err = traceback.format_exc()
            steps[name] = _step_result(False, str(exc))
            project_status = "error"
            print(f"ERREUR ({elapsed:.1f}s)")
            print(f"  → {exc}")
            log_event(
                f"ERREUR rebuild publication {name} / {project_name} : "
                f"{exc}\n{err}"
            )

    from app.final_document_builder import (
        build_final_document,
        harmonize_final_structure,
    )
    from app.cover_generation_service import generate_cover
    from app.publication_template_service import build_publication_markdown
    from app.docx_export_service import export_docx, export_publication_docx
    from app.pdf_export_service import export_pdf, export_publication_pdf
    from app.client_export_service import export_client_zip

    # ── Fallback : reconstruire document_final.md depuis processed/ ─────────
    if not has_final:
        print(
            "\n[publication] document_final.md absent — "
            "reconstruction depuis processed/*.md"
        )
        run_step("final_document", lambda: build_final_document(project_name))
        if project_status == "error":
            duration = time.time() - t0
            return {
                "project":                   project_name,
                "status":                    project_status,
                "started_at":               started_at.isoformat(timespec="seconds"),
                "finished_at":              datetime.now().isoformat(timespec="seconds"),
                "duration_seconds":         round(duration, 1),
                "steps":                    steps,
                "rebuild_publication_mode": True,
            }
    else:
        print("\n[publication] Reusing existing document_final.md")

    # ── Étapes de publication ────────────────────────────────────────────────
    print("\n[publication] Regenerating TOC")
    run_step("publication_markdown", lambda: build_publication_markdown(project_name))

    print("\n[publication] Regenerating cover")
    run_step("cover_generation", lambda: generate_cover(project_name))

    print("\n[publication] Regenerating DOCX")
    run_step("export_docx",      lambda: export_docx(project_name))
    run_step("publication_docx", lambda: export_publication_docx(project_name))

    print("\n[publication] Regenerating PDF")
    run_step("export_pdf",       lambda: export_pdf(project_name))
    run_step("publication_pdf",  lambda: export_publication_pdf(project_name))

    print("\n[publication] Regenerating ZIP")
    run_step("client_export", lambda: export_client_zip(project_name))

    run_step(
        "harmonize_structure",
        lambda: harmonize_final_structure(project_name),
    )

    run_step(
        "report",
        lambda: _build_report_with_execution(
            project_name, started_at, time.time() - t0
        ),
    )

    # ── Validation post-pipeline ─────────────────────────────────────────────
    _check_publication_quality(project_name, steps)
    if project_status == "success":
        project_status = _verify_deliverables(project_name, steps)

    duration = time.time() - t0
    finished_at = datetime.now()

    print(f"\n{'-' * 50}")
    symbol = "OK" if project_status == "success" else "ERREUR"
    print(
        f"  [{symbol}] Rebuild publication {project_name} terminé en "
        f"{_fmt_duration(duration)}"
    )
    print(f"{'-' * 50}")
    print("\n[publication] Rebuild completed")

    log_event(
        f"Rebuild publication {project_name} : {project_status} "
        f"en {_fmt_duration(duration)}"
    )

    return {
        "project":                   project_name,
        "status":                    project_status,
        "started_at":               started_at.isoformat(timespec="seconds"),
        "finished_at":              finished_at.isoformat(timespec="seconds"),
        "duration_seconds":         round(duration, 1),
        "steps":                    steps,
        "rebuild_publication_mode": True,
    }


def run_full_rebuild_pipeline(project: AudioProject) -> dict:
    """
    Reconstruction complète depuis les chunks.

    - Ne refait PAS la transcription (transcript_complet.txt est préservé).
    - Ne refait PAS la fusion (merged/ est préservé).
    - Force la régénération des chunks depuis transcript_complet.txt.
    - Remet TOUS les chunks à "pending" et supprime processed/ + reviewed/.
    - Remet à zéro final_document, publication, exports dans le state.
    - Exécute ensuite toutes les étapes depuis chunk_generation jusqu'à report.

    Utilisation :
        Après correction du pipeline ou des prompts, pour forcer un
        retraitement complet sans relancer la transcription (coûteuse).
    """
    from app.project_state import force_reset_project_for_rebuild
    from app.paths import SORTIE_DIR

    started_at = datetime.now()
    t0 = time.time()
    steps: dict[str, dict] = {}
    project_status = "success"

    print(f"\n{'=' * 50}")
    print(f"  REBUILD COMPLET : {project.name}")
    print(f"  Début  : {started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 50}")

    # ── 1. Réinitialisation de l'état ────────────────────────────────────────
    print("\n[rebuild] Réinitialisation de l'état du projet...")

    output_dir = SORTIE_DIR / project.name
    processed_dir = output_dir / "processed"
    reviewed_dir  = output_dir / "reviewed"
    final_dir     = output_dir / "final"

    # Supprimer tous les fichiers processed/ et reviewed/
    deleted = 0
    for d in (processed_dir, reviewed_dir):
        if d.is_dir():
            for f in d.glob("chunk_*.md"):
                f.unlink(missing_ok=True)
                deleted += 1

    # Supprimer les fichiers document_*.(md|pdf|docx) dans final/
    # mais conserver document_final.docx de l'ancien export si présent
    for pattern in ("document_clean.md", "document_publication.md",
                    "document_publication.pdf", "document_publication.docx",
                    "document_final.md", "document_final.pdf"):
        target = final_dir / pattern
        if target.exists():
            target.unlink(missing_ok=True)
            deleted += 1

    print(f"[rebuild] {deleted} fichier(s) obsolète(s) supprimé(s).")

    # Réinitialiser le state (chunks → pending, final/publication/exports → {})
    force_reset_project_for_rebuild(project.name, reset_cover=False)

    _write_execution_status(project, "running", started_at)

    def run_step(name: str, fn):
        nonlocal project_status
        print(f"\n[{name}] ...", end=" ", flush=True)
        t = time.time()
        try:
            fn()
            elapsed = time.time() - t
            steps[name] = _step_result(True)
            print(f"OK ({elapsed:.1f}s)")
        except Exception as exc:
            elapsed = time.time() - t
            err = traceback.format_exc()
            steps[name] = _step_result(False, str(exc))
            project_status = "error"
            print(f"ERREUR ({elapsed:.1f}s)")
            print(f"  → {exc}")
            log_event(f"ERREUR rebuild {name} / {project.name} : {exc}\n{err}")

    # ── 2. Pipeline depuis chunk_generation ──────────────────────────────────
    from app.chunk_service import create_project_chunks
    from app.ai_processor import process_project_chunks
    from app.correction_review_service import generate_review_files
    from app.correction_apply_service import apply_corrections
    from app.final_document_builder import build_final_document
    from app.global_editor_service import harmonize_document
    from app.cover_generation_service import generate_cover
    from app.publication_template_service import build_publication_markdown
    from app.docx_export_service import export_docx, export_publication_docx
    from app.pdf_export_service import export_pdf, export_publication_pdf
    from app.client_export_service import export_client_zip
    from app.report_service import build_project_report

    def step_chunks():
        chunk_results = create_project_chunks(
            project,
            force_regenerate_chunks=True,
        )
        state = load_project_state(project)
        for result in chunk_results:
            update_chunk_state(
                state,
                result["name"],
                result["hash"],
                result["generation_status"],
                result["needs_ai_processing"],
                partie_source=result.get("partie_source"),
                char_count=result.get("char_count", 0),
                word_count=result.get("word_count", 0),
                path=str(result["path"]),
                processed_path=result.get("processed_path"),
            )
        # Retirer de l'état les entrées devenues obsolètes
        new_names = {r["name"] for r in chunk_results}
        for name in list(state.get("chunks", {}).keys()):
            if name not in new_names:
                state["chunks"].pop(name, None)
        save_project_state(project, state)

    rebuild_steps = [
        ("chunk_generation",     step_chunks),
        ("ai_processing",        lambda: process_project_chunks(project)),
        ("correction_review",    lambda: generate_review_files(project)),
        ("correction_apply",     lambda: apply_corrections(project.name)),
        ("final_document",       lambda: build_final_document(project.name)),
        ("harmonization",        lambda: harmonize_document(project.name)),
        ("cover_generation",     lambda: generate_cover(project.name)),
        ("publication_markdown", lambda: build_publication_markdown(project.name)),
        ("export_docx",          lambda: export_docx(project.name)),
        ("export_pdf",           lambda: export_pdf(project.name)),
        ("publication_docx",     lambda: export_publication_docx(project.name)),
        ("publication_pdf",      lambda: export_publication_pdf(project.name)),
        ("client_export",        lambda: export_client_zip(project.name)),
        ("report",               lambda: _build_report_with_execution(
            project.name, started_at, time.time() - t0
        )),
    ]

    for step_name, step_fn in rebuild_steps:
        run_step(step_name, step_fn)

    _check_publication_quality(project.name, steps)

    if project_status == "success":
        project_status = _verify_deliverables(project.name, steps)

    duration = time.time() - t0
    finished_at = datetime.now()

    print(f"\n{'-' * 50}")
    symbol = "OK" if project_status == "success" else "ERREUR"
    print(
        f"  [{symbol}] Rebuild {project.name} terminé en "
        f"{_fmt_duration(duration)}"
    )
    print(f"{'-' * 50}")

    log_event(
        f"Rebuild {project.name} terminé : {project_status} "
        f"en {_fmt_duration(duration)}"
    )

    _write_execution_status(
        project,
        status=project_status,
        started_at=started_at,
        error=next(
            (s.get("error") for s in steps.values()
             if s.get("status") == "error" and s.get("error")),
            None,
        ),
        finished_at=finished_at,
    )

    return {
        "project":           project.name,
        "status":            project_status,
        "started_at":        started_at.isoformat(timespec="seconds"),
        "finished_at":       finished_at.isoformat(timespec="seconds"),
        "duration_seconds":  round(duration, 1),
        "steps":             steps,
        "rebuild_mode":      True,
    }
