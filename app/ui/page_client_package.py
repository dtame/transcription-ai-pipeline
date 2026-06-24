"""
Page — Package client.

Sections :
  1. ZIP Client (client_package.py) — publication finale
  2. ZIP Client Export (client_export_service.py) — export legacy
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.paths import SORTIE_DIR
from app.ui.ui_utils import file_date_human, file_size_human, open_path, run_action, show_action_message


def render(project_name: str) -> None:
    busy = st.session_state.get("processing", False)

    st.title("📦 Package client")
    show_action_message()

    if not project_name:
        st.warning("Aucun projet sélectionné.")
        return

    pub_dir = SORTIE_DIR / project_name / "publication"

    # ── Section 1 : ZIP Client principal (client_package.py) ─────────────────

    with st.container(border=True):
        st.subheader("📦 ZIP Client — Publication finale")

        from app.client_package import build_client_package, get_package_info

        pkg_info     = get_package_info(project_name)
        pkg_pdf_path = pub_dir / "publication.pdf"
        pkg_disabled = busy or not pkg_pdf_path.exists()

        if pkg_info["exists"]:
            st.success(f"Disponible : `{pkg_info['zip_name']}`")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Nom",          pkg_info["zip_name"])
            c2.metric("Généré le",    pkg_info["generated_at"] or "—")
            c3.metric("Taille",       pkg_info["size_human"])
            c4.metric("Fichiers",     str(len(pkg_info["included_files"])))
        else:
            st.info("ZIP Client non encore généré.")

        if not pkg_pdf_path.exists():
            st.warning("publication.pdf absent — générez d'abord la publication PDF.")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button(
                "📦 Créer le ZIP client",
                key=f"pkg_create_{project_name}",
                disabled=pkg_disabled,
                use_container_width=True,
                type="primary",
                help="Crée le ZIP depuis publication/ (PDF + DOCX + MD + rapport qualité).",
            ):
                run_action(
                    f"ZIP Client {project_name}",
                    lambda n=project_name: build_client_package(n),
                )
                st.rerun()

        with col2:
            if st.button("📂 Ouvrir ZIP", key=f"pkg_open_{project_name}", disabled=not pkg_info["exists"], use_container_width=True):
                if pkg_info["zip_path"]:
                    open_path(pkg_info["zip_path"])

        with col3:
            client_dir = SORTIE_DIR / project_name / "client"
            if st.button("📁 Dossier client/", key=f"pkg_dir_{project_name}", disabled=not client_dir.exists(), use_container_width=True):
                open_path(client_dir)

        # Téléchargement direct
        if pkg_info["exists"] and pkg_info.get("zip_path"):
            zip_path = Path(pkg_info["zip_path"])
            if zip_path.exists():
                st.download_button(
                    label=f"⬇ Télécharger {pkg_info['zip_name']}",
                    data=zip_path.read_bytes(),
                    file_name=pkg_info["zip_name"],
                    mime="application/zip",
                    key=f"pkg_dl_{project_name}",
                    use_container_width=True,
                )

        if pkg_info["exists"] and pkg_info["included_files"]:
            with st.expander("Contenu du ZIP", expanded=False):
                for f in pkg_info["included_files"]:
                    st.write(f"- {f}")

        if pkg_info.get("summary_path"):
            with st.expander("project_summary.json", expanded=False):
                try:
                    import json
                    data = json.loads(Path(pkg_info["summary_path"]).read_text(encoding="utf-8"))
                    st.json(data)
                except Exception:
                    st.caption("Impossible de lire le fichier.")

    # ── Section 2 : Export ZIP legacy (client_export_service.py) ─────────────

    with st.container(border=True):
        st.subheader("📦 Export ZIP — Livraison client")

        from app.client_export_service import export_client_zip, get_client_export_info

        ce_info = get_client_export_info(project_name)

        if ce_info["exists"]:
            st.success(f"Disponible : `{ce_info['zip_name']}`")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Nom",          ce_info["zip_name"])
            c2.metric("Généré le",    ce_info["generated_at"] or "—")
            c3.metric("Taille",       ce_info["size_human"])
            c4.metric("Fichiers",     str(ce_info["files_count"]))
        else:
            st.info("Export ZIP non encore généré.")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button(
                "📦 Exporter ZIP",
                key=f"ce_export_{project_name}",
                disabled=busy,
                use_container_width=True,
            ):
                run_action(
                    f"Export ZIP {project_name}",
                    lambda n=project_name: export_client_zip(n),
                )
                st.rerun()

        with col2:
            if st.button(
                "🔄 Régénérer ZIP",
                key=f"ce_regen_{project_name}",
                disabled=busy,
                use_container_width=True,
            ):
                run_action(
                    f"Régénération ZIP {project_name}",
                    lambda n=project_name: export_client_zip(n, force=True),
                )
                st.rerun()

        with col3:
            if st.button("📂 Ouvrir ZIP", key=f"ce_open_{project_name}", disabled=not ce_info["exists"], use_container_width=True):
                if ce_info["zip_path"]:
                    open_path(ce_info["zip_path"])

        with col4:
            ce_dir = SORTIE_DIR / project_name / "client"
            if st.button("📁 Dossier client/", key=f"ce_dir_{project_name}", disabled=not ce_dir.exists(), use_container_width=True):
                open_path(ce_dir)

        # Téléchargement direct
        if ce_info["exists"] and ce_info.get("zip_path"):
            ce_zip_path = Path(ce_info["zip_path"])
            if ce_zip_path.exists():
                st.download_button(
                    label=f"⬇ Télécharger {ce_info['zip_name']}",
                    data=ce_zip_path.read_bytes(),
                    file_name=ce_info["zip_name"],
                    mime="application/zip",
                    key=f"ce_dl_{project_name}",
                    use_container_width=True,
                )

        if ce_info["exists"] and ce_info.get("files"):
            with st.expander("Contenu du ZIP", expanded=False):
                for f in ce_info["files"]:
                    st.write(f"- {f}")

        final_dir = SORTIE_DIR / project_name / "final"
        _pdf_ok  = (final_dir / "document_publication.pdf").exists()
        _docx_ok = (final_dir / "document_publication.docx").exists()
        if not _pdf_ok:
            st.warning("document_publication.pdf absent (dossier final/).")
        if not _docx_ok:
            st.warning("document_publication.docx absent (dossier final/).")
