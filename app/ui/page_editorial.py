"""
Page — Pipeline éditorial.

Trois cartes :
  1. Manuscrit       — génération du manuscrit éditorial (editorial_finalizer)
  2. Transformation  — transformation fidèle (editorial_transformer)
  3. Qualité         — contrôle qualité éditorial (editorial_quality_guard)
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.paths import SORTIE_DIR
from app.ui.ui_utils import open_path, run_action, show_action_message


def render(project_name: str) -> None:
    busy = st.session_state.get("processing", False)

    st.title("📚 Pipeline éditorial")
    show_action_message()

    if not project_name:
        st.warning("Aucun projet sélectionné.")
        return

    final_dir = SORTIE_DIR / project_name / "final"

    from app.project_state import load_project_state
    ps  = load_project_state(project_name)
    ed  = ps.get("editorial", {})

    # ── Carte 1 : Manuscrit ──────────────────────────────────────────────────

    with st.container(border=True):
        st.subheader("📄 Manuscrit éditorial")

        from app.editorial_finalizer import list_processed_chunks
        ed_chunks  = list_processed_chunks(project_name)
        ms_path    = Path(ed["manuscript_path"]) if ed.get("manuscript_path") else None
        ms_exists  = ms_path is not None and ms_path.exists()

        c1, c2, c3 = st.columns(3)
        c1.metric("Chunks traités", len(ed_chunks))
        c2.metric("Manuscrit", "✅ Disponible" if ms_exists else "—")
        c3.metric("Généré le", (ed.get("generated_at") or "—")[:19])

        if ms_exists:
            st.success(f"Disponible : `{ms_path.name}`")
        elif ed.get("error"):
            st.warning(f"Dernière erreur : {ed['error']}")
        elif not ed_chunks:
            st.info("Aucun chunk traité. Lancez le traitement IA avant de générer le manuscrit.")

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            if st.button(
                "✍️ Générer le manuscrit éditorial",
                key=f"ed_ms_gen_{project_name}",
                disabled=busy or len(ed_chunks) == 0,
                use_container_width=True,
                help="Fusionne les chunks traités → final/manuscript.md",
            ):
                from app.editorial_finalizer import generate_editorial_manuscript
                run_action(
                    f"Manuscrit éditorial {project_name}",
                    lambda n=project_name: generate_editorial_manuscript(n),
                )
                st.rerun()
        with col2:
            if st.button("📂 Ouvrir", key=f"ed_ms_open_{project_name}", disabled=not ms_exists, use_container_width=True):
                open_path(ms_path)
        with col3:
            if st.button("📁 Dossier final/", key=f"ed_ms_dir_{project_name}", disabled=not final_dir.exists(), use_container_width=True):
                open_path(final_dir)

    # ── Carte 2 : Transformation ─────────────────────────────────────────────

    with st.container(border=True):
        st.subheader("✍️ Transformation éditoriale")

        structured_path = final_dir / "manuscript_structured.md"
        rewritten_path  = final_dir / "manuscript_rewritten.md"
        struct_ok       = structured_path.exists()
        rewrit_ok       = rewritten_path.exists()

        c1, c2, c3 = st.columns(3)
        c1.metric("Manuscrit structuré",   "✅" if struct_ok  else "—")
        c2.metric("Manuscrit transformé",  "✅" if rewrit_ok  else "—")
        c3.metric("Langue", (ed.get("document_language") or "—").upper())

        if rewrit_ok:
            st.success(f"Disponible : `{rewritten_path.name}`")
        elif ed.get("rewritten_error"):
            st.warning(f"Dernière erreur : {ed['rewritten_error']}")
        elif not struct_ok:
            st.info("manuscript_structured.md absent. Générez d'abord le manuscrit.")

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            if st.button(
                "✍️ Transformer le manuscrit",
                key=f"ed_tr_gen_{project_name}",
                disabled=busy or not struct_ok,
                use_container_width=True,
                help="Transforme manuscript_structured.md → manuscript_rewritten.md via Ollama.",
            ):
                from app.editorial_transformer import transform_editorial_manuscript
                run_action(
                    f"Transformation {project_name}",
                    lambda n=project_name: transform_editorial_manuscript(n),
                )
                st.rerun()
        with col2:
            if st.button("📂 Rewritten", key=f"ed_tr_rw_{project_name}", disabled=not rewrit_ok, use_container_width=True):
                open_path(rewritten_path)
        with col3:
            if st.button("📄 Structured", key=f"ed_tr_st_{project_name}", disabled=not struct_ok, use_container_width=True):
                open_path(structured_path)

    # ── Carte 3 : Contrôle qualité ───────────────────────────────────────────

    with st.container(border=True):
        st.subheader("🔍 Contrôle qualité éditorial")

        qg_report_path  = Path(ed["quality_report_path"]) if ed.get("quality_report_path") else None
        qg_report_ok    = qg_report_path is not None and qg_report_path.exists()
        qg_status       = ed.get("quality_status")
        qg_at           = (ed.get("quality_checked_at") or "")[:19]
        qg_icon         = {"PASS": "✅", "WARNING": "⚠️", "FAIL": "❌"}.get(qg_status or "", "—")

        c1, c2, c3 = st.columns(3)
        c1.metric("Statut qualité",    f"{qg_icon} {qg_status}" if qg_status else "—")
        c2.metric("Rapport",           "✅ Disponible" if qg_report_ok else "—")
        c3.metric("Vérifié le",        qg_at if qg_at else "—")

        if qg_status == "PASS":
            st.success("Tous les contrôles qualité sont passés.")
        elif qg_status == "WARNING":
            st.warning("Des avertissements détectés. Consultez le rapport.")
        elif qg_status == "FAIL":
            st.error("Problèmes critiques détectés. Consultez le rapport.")
        elif not rewrit_ok:
            st.info("manuscript_rewritten.md absent. Transformez d'abord le manuscrit.")

        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button(
                "🔍 Vérifier la qualité",
                key=f"qg_check_{project_name}",
                disabled=busy or not (struct_ok or rewrit_ok),
                use_container_width=True,
                help="Compare structured ↔ rewritten et génère editorial_quality_report.md.",
            ):
                from app.editorial_quality_guard import run_editorial_quality_guard
                run_action(
                    f"Qualité éditoriale {project_name}",
                    lambda n=project_name: run_editorial_quality_guard(n),
                )
                st.rerun()
        with col2:
            if st.button("📋 Rapport", key=f"qg_open_{project_name}", disabled=not qg_report_ok, use_container_width=True):
                open_path(qg_report_path)

        if qg_report_ok:
            with st.expander("Aperçu du rapport qualité", expanded=False):
                try:
                    st.markdown(qg_report_path.read_text(encoding="utf-8"))
                except Exception:
                    st.caption("Impossible de lire le rapport.")
