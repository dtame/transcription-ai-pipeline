"""
Page — DOCX / PDF.

Deux cartes :
  1. Génération DOCX avec téléchargement direct
  2. Génération PDF avec téléchargement direct
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.paths import SORTIE_DIR
from app.ui.ui_utils import file_date_human, file_size_human, open_path, show_action_message


def render(project_name: str) -> None:
    busy = st.session_state.get("processing", False)

    st.title("📄 DOCX / PDF")
    show_action_message()

    if not project_name:
        st.warning("Aucun projet sélectionné.")
        return

    pub_dir = SORTIE_DIR / project_name / "publication"

    from app.project_state import load_project_state
    ps  = load_project_state(project_name)
    pub = ps.get("publication", {})

    pub_md        = pub_dir / "publication.md"
    pub_sanitized = pub_dir / "publication_sanitized.md"
    effective_md  = pub_sanitized if pub_sanitized.exists() else pub_md
    source_label  = "publication_sanitized.md" if pub_sanitized.exists() else "publication.md"

    # ── Carte DOCX ────────────────────────────────────────────────────────────

    with st.container(border=True):
        st.subheader("📄 DOCX")

        docx_path   = pub_dir / "publication.docx"
        docx_state  = pub.get("docx_engine", {})
        docx_ok     = docx_state.get("generated", False) and docx_path.exists()
        docx_at     = (docx_state.get("generated_at") or "")[:19]
        docx_error  = docx_state.get("error", "")

        c1, c2, c3 = st.columns(3)
        c1.metric("Statut",     "✅ Généré" if docx_ok else "—")
        c2.metric("Généré le",  docx_at or "—")
        c3.metric("Source",     source_label)

        if docx_ok:
            st.success(
                f"Disponible : `publication.docx`  "
                f"— {file_size_human(docx_path)}  "
                f"— {file_date_human(docx_path)}"
            )
        if docx_error and not docx_ok:
            st.error(f"Erreur : {docx_error}")
        if not effective_md.exists():
            st.info("Aucune publication disponible. Construisez d'abord la publication.")

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            if st.button(
                "📄 Générer DOCX",
                key=f"docx_gen_{project_name}",
                disabled=busy or not effective_md.exists(),
                use_container_width=True,
                help=f"Génère publication.docx depuis {source_label}.",
            ):
                with st.spinner("Génération DOCX…"):
                    from app.publication_docx_engine import generate_publication_docx
                    result = generate_publication_docx(project_name)
                if result and result.exists():
                    st.success(f"Généré : `{result.name}`")
                else:
                    st.error("Échec. Consultez les logs.")
                st.rerun()

        with col2:
            if st.button("📂 Ouvrir DOCX", key=f"docx_open_{project_name}", disabled=not docx_path.exists(), use_container_width=True):
                open_path(docx_path)

        with col3:
            if docx_path.exists():
                st.download_button(
                    label="⬇ Télécharger",
                    data=docx_path.read_bytes(),
                    file_name=f"{project_name}_publication.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"docx_dl_{project_name}",
                    use_container_width=True,
                )
            else:
                st.button("⬇ Télécharger", key=f"docx_dl_{project_name}", disabled=True, use_container_width=True)

    # ── Carte PDF ─────────────────────────────────────────────────────────────

    with st.container(border=True):
        st.subheader("📄 PDF")

        pdf_path  = pub_dir / "publication.pdf"
        pdf_state = pub.get("pdf_engine", {})
        pdf_ok    = pdf_state.get("generated", False) and pdf_path.exists()
        pdf_at    = (pdf_state.get("generated_at") or "")[:19]
        pdf_error = pdf_state.get("error", "")

        c1, c2, c3 = st.columns(3)
        c1.metric("Statut",    "✅ Généré" if pdf_ok else "—")
        c2.metric("Généré le", pdf_at or "—")
        c3.metric("Source",    source_label)

        if pdf_ok:
            st.success(
                f"Disponible : `publication.pdf`  "
                f"— {file_size_human(pdf_path)}  "
                f"— {file_date_human(pdf_path)}"
            )
        if pdf_error and not pdf_ok:
            st.error(f"Erreur : {pdf_error}")
        if not effective_md.exists():
            st.info("Aucune publication disponible. Construisez d'abord la publication.")

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            if st.button(
                "📄 Générer PDF",
                key=f"pdf_gen_{project_name}",
                disabled=busy or not effective_md.exists(),
                use_container_width=True,
                help=f"Génère publication.pdf depuis {source_label}.",
            ):
                with st.spinner("Génération PDF…"):
                    from app.publication_pdf_engine import generate_publication_pdf
                    result = generate_publication_pdf(project_name)
                if result and result.exists():
                    st.success(f"Généré : `{result.name}`")
                else:
                    st.error("Échec. Consultez les logs.")
                st.rerun()

        with col2:
            if st.button("📂 Ouvrir PDF", key=f"pdf_open_{project_name}", disabled=not pdf_path.exists(), use_container_width=True):
                open_path(pdf_path)

        with col3:
            if pdf_path.exists():
                st.download_button(
                    label="⬇ Télécharger",
                    data=pdf_path.read_bytes(),
                    file_name=f"{project_name}_publication.pdf",
                    mime="application/pdf",
                    key=f"pdf_dl_{project_name}",
                    use_container_width=True,
                )
            else:
                st.button("⬇ Télécharger", key=f"pdf_dl_{project_name}", disabled=True, use_container_width=True)

    # ── Fichiers finaux (dossier final/) ──────────────────────────────────────

    final_dir = SORTIE_DIR / project_name / "final"
    if final_dir.exists():
        with st.expander("Fichiers dans final/ (exports legacy)", expanded=False):
            _files = [
                ("document_final.md",          final_dir / "document_final.md"),
                ("document_final.docx",         final_dir / "document_final.docx"),
                ("document_final.pdf",          final_dir / "document_final.pdf"),
                ("document_publication.md",     final_dir / "document_publication.md"),
                ("document_publication.docx",   final_dir / "document_publication.docx"),
                ("document_publication.pdf",    final_dir / "document_publication.pdf"),
            ]
            cols = st.columns(3)
            for i, (label, fpath) in enumerate(_files):
                with cols[i % 3]:
                    if fpath.exists():
                        if st.button(f"📂 {label}", key=f"final_{project_name}_{i}", use_container_width=True):
                            open_path(fpath)
                    else:
                        st.button(f"❌ {label}", key=f"final_{project_name}_{i}", disabled=True, use_container_width=True)
