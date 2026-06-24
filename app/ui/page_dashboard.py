"""
Page — Tableau de bord du projet.

Affiche un résumé visuel du projet sélectionné, les statuts des grandes
étapes du pipeline et les actions rapides, y compris le bouton principal
🚀 Générer le package client complet.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.paths import SORTIE_DIR
from app.ui.ui_utils import (
    bool_icon,
    file_date_human,
    file_size_human,
    fmt_duration,
    open_path,
    run_action,
    show_action_message,
    status_badge,
)
from app.ui_status_service import get_project_status


def render(project_name: str) -> None:
    busy = st.session_state.get("processing", False)

    st.title("🏠 Tableau de bord")
    show_action_message()

    if not project_name:
        st.warning("Aucun projet sélectionné. Choisissez un projet dans la barre latérale.")
        return

    pstatus = get_project_status(project_name)
    audio   = pstatus["audio"]
    chunks  = pstatus["chunks"]
    pub     = pstatus["publication"]
    exp     = pstatus["exports"]

    final_dir = SORTIE_DIR / project_name / "final"
    pub_dir   = SORTIE_DIR / project_name / "publication"
    client_dir = SORTIE_DIR / project_name / "client"

    docx_exists = (pub_dir / "publication.docx").exists()
    pdf_exists  = (pub_dir / "publication.pdf").exists()
    zip_exists  = any(client_dir.glob("*.zip")) if client_dir.exists() else False

    # ── Métriques clés ────────────────────────────────────────────────────────

    st.subheader("Résumé du projet")

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Audios",  f"{audio['transcribed']}/{audio['total']}")
    c2.metric("Chunks",  f"{chunks['done']}/{chunks['total']}")
    c3.metric("Corrections", str(pstatus["corrections"]))
    c4.metric("DOCX",    "✅" if (pub["docx"] or exp["docx"] or docx_exists) else "—")
    c5.metric("PDF",     "✅" if (pub["pdf"]  or exp["pdf"]  or pdf_exists)  else "—")
    c6.metric("ZIP",     "✅" if zip_exists else "—")

    # ── Statut global du pipeline ─────────────────────────────────────────────

    st.subheader("Statut du pipeline")

    from app.project_state import load_project_state
    ps = load_project_state(project_name)
    ed = ps.get("editorial", {})
    cv = ps.get("cover", {})
    pbl = ps.get("publication", {})

    manuscript_ok   = (final_dir / "manuscript.md").exists() or (final_dir / "manuscript_structured.md").exists()
    rewritten_ok    = (final_dir / "manuscript_rewritten.md").exists()
    publication_ok  = (pub_dir / "publication.md").exists()
    cover_ok        = (pub_dir / "cover" / "cover.pdf").exists()
    docx_final_ok   = docx_exists
    pdf_final_ok    = pdf_exists

    pipeline_stages = [
        ("Transcription",      audio["transcribed"] > 0 and audio["transcribed"] == audio["total"]),
        ("Manuscrit éditorial", manuscript_ok),
        ("Transformation",     rewritten_ok),
        ("Publication",        publication_ok),
        ("Couverture",         cover_ok),
        ("DOCX",               docx_final_ok),
        ("PDF",                pdf_final_ok),
        ("ZIP client",         zip_exists),
    ]

    stage_cols = st.columns(len(pipeline_stages))
    for col, (label, done) in zip(stage_cols, pipeline_stages):
        icon = "✅" if done else "○"
        col.markdown(
            f"<div style='text-align:center'>"
            f"<div style='font-size:1.4rem'>{icon}</div>"
            f"<div style='font-size:0.75rem;color:#888'>{label}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("")

    # ── Bouton principal ──────────────────────────────────────────────────────

    st.divider()

    col_orch, col_orch_info = st.columns([2, 3])

    with col_orch:
        if st.button(
            "🚀 Générer le package client complet",
            key="btn_orchestrate",
            disabled=busy,
            use_container_width=True,
            type="primary",
            help=(
                "Exécute automatiquement : Transformation → Qualité → "
                "Publication → Sanitizer → Couverture → DOCX → PDF → ZIP"
            ),
        ):
            _run_orchestrator(project_name)
            st.rerun()

    with col_orch_info:
        report_path = SORTIE_DIR / project_name / "orchestrator_report.md"
        if report_path.exists():
            st.caption(
                f"Dernier rapport : {file_date_human(report_path)}"
            )
            if st.button("📋 Voir le rapport", key="btn_orch_report", use_container_width=True):
                open_path(report_path)

    # Afficher le résultat de l'orchestrateur si disponible
    last = st.session_state.get("last_result")
    if last and "steps" in last and last.get("project") == project_name:
        _show_orchestrator_result(last)

    # ── Actions rapides ───────────────────────────────────────────────────────

    st.divider()
    st.subheader("Actions rapides")

    col_a1, col_a2, col_a3, col_a4 = st.columns(4)

    with col_a1:
        if st.button(
            "▶ Traiter ce projet",
            key="dash_process",
            disabled=busy,
            use_container_width=True,
            help="Pipeline complet : transcription → IA → corrections → exports.",
        ):
            from app.production_service import process_project
            run_action(
                f"Traitement de {project_name}",
                lambda n=project_name: process_project(n),
            )
            st.rerun()

    with col_a2:
        _resume_disabled = busy or pstatus["status"] == "success"
        if st.button(
            "⏩ Reprendre",
            key="dash_resume",
            disabled=_resume_disabled,
            use_container_width=True,
            help="Reprend le projet là où il s'est arrêté.",
        ):
            from app.production_service import resume_project
            run_action(
                f"Reprise de {project_name}",
                lambda n=project_name: resume_project(n),
            )
            st.rerun()

    with col_a3:
        if st.button(
            "🔁 Reconstruire depuis chunks",
            key="dash_rebuild",
            disabled=busy,
            use_container_width=True,
            help="Reconstruit tout depuis les chunks sans refaire la transcription.",
        ):
            from app.production_service import rebuild_project_from_chunks
            run_action(
                f"Reconstruction de {project_name}",
                lambda n=project_name: rebuild_project_from_chunks(n),
            )
            st.rerun()

    with col_a4:
        if st.button(
            "🔄 Rafraîchir",
            key="dash_refresh",
            use_container_width=True,
        ):
            st.cache_data.clear()
            st.rerun()

    # ── Informations du projet ────────────────────────────────────────────────

    st.divider()
    st.subheader("Informations")

    from app.project_manager import discover_projects
    all_projects = discover_projects()
    project_obj  = next((p for p in all_projects if p.name == project_name), None)

    info_c1, info_c2 = st.columns(2)
    with info_c1:
        st.markdown(f"**Statut global :** {status_badge(pstatus['status'])}")
        if project_obj:
            st.caption(f"Source : {project_obj.source_dir}")
        st.caption(f"Sortie : {SORTIE_DIR / project_name}")
        if pstatus.get("last_run"):
            st.caption(f"Dernière exécution : {pstatus['last_run']}")

    with info_c2:
        lang = ed.get("document_language") or ps.get("publication_mode") or "—"
        mode = ps.get("publication_mode") or "—"
        st.markdown(f"**Mode de publication :** `{mode}`")
        st.markdown(f"**Langue documentaire :** `{lang.upper() if lang != '—' else '—'}`")
        if audio.get("errors"):
            st.warning(f"⚠️ {audio['errors']} fichier(s) audio en erreur")

    # ── Erreurs récentes ─────────────────────────────────────────────────────

    from app.ui_status_service import get_project_errors
    proj_errors = get_project_errors(project_name)
    if proj_errors:
        with st.expander(f"⚠️ {len(proj_errors)} erreur(s) détectée(s)", expanded=False):
            for err in proj_errors[:5]:
                st.error(
                    f"**{err.get('step', '?')}** — {err.get('date', '')}  \n"
                    f"{err.get('message', 'Pas de message')}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrateur
# ─────────────────────────────────────────────────────────────────────────────

def _run_orchestrator(project_name: str) -> None:
    """Lance l'orchestrateur avec affichage de progression."""
    from app.publication_orchestrator import generate_complete_client_package
    from app.sleep_guard import prevent_sleep, allow_sleep_again
    import time as _time

    st.session_state.processing   = True
    st.session_state.sleep_active = True
    st.session_state.action_message = None

    progress_placeholder = st.empty()
    status_lines: list[str] = []

    def _callback(label: str, status: str) -> None:
        icons = {"running": "🔵", "success": "✅", "error": "❌", "skipped": "⏭️"}
        icon  = icons.get(status, "?")
        status_lines.append(f"{icon} {label}")
        progress_placeholder.info("\n\n".join(status_lines[-6:]))

    t0 = _time.time()
    prevent_sleep()
    try:
        result = generate_complete_client_package(project_name, _callback)
        duration = _time.time() - t0
        st.session_state.last_result = result
        if result.get("status") == "success":
            st.session_state.action_message = (
                "success",
                f"✅ Package client complet généré en {fmt_duration(duration)}.",
            )
        else:
            st.session_state.action_message = (
                "error",
                f"❌ Pipeline terminé avec des erreurs après {fmt_duration(duration)}. "
                "Consultez le rapport.",
            )
    except Exception as exc:
        duration = _time.time() - t0
        st.session_state.last_result = {"error": str(exc)}
        st.session_state.action_message = (
            "error",
            f"❌ Erreur inattendue après {fmt_duration(duration)} : {exc}",
        )
    finally:
        allow_sleep_again()
        st.session_state.processing   = False
        st.session_state.sleep_active = False
        progress_placeholder.empty()

    st.cache_data.clear()


def _show_orchestrator_result(result: dict) -> None:
    """Affiche le détail des étapes du dernier run d'orchestrateur."""
    steps = result.get("steps", {})
    if not steps:
        return

    with st.expander("Détail des étapes — dernier run", expanded=False):
        labels = {
            "editorial_transformer": "Transformation éditoriale",
            "quality_guard":         "Contrôle qualité",
            "publication_builder":   "Publication Builder",
            "publication_sanitizer": "Publication Sanitizer",
            "cover_builder":         "Cover Builder",
            "docx_engine":           "Génération DOCX",
            "pdf_engine":            "Génération PDF",
            "client_package":        "Package Client ZIP",
        }
        for key, info in steps.items():
            status  = info.get("status", "?")
            icon    = {"success": "✅", "error": "❌", "skipped": "⏭️"}.get(status, "?")
            dur     = info.get("duration_seconds")
            dur_str = f" ({dur:.1f}s)" if dur is not None else ""
            line    = f"{icon} **{labels.get(key, key)}**{dur_str}"
            if info.get("error"):
                line += f"  \n  `{info['error']}`"
            st.markdown(line)
