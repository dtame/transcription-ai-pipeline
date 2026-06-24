"""
Page — Publication.

Deux cartes :
  1. Publication Builder  — construit publication.md
  2. Publication Sanitizer — nettoie publication.md → publication_sanitized.md
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.paths import SORTIE_DIR
from app.ui.ui_utils import file_date_human, file_size_human, open_path, run_action, show_action_message


def render(project_name: str) -> None:
    busy = st.session_state.get("processing", False)

    st.title("📖 Publication")
    show_action_message()

    if not project_name:
        st.warning("Aucun projet sélectionné.")
        return

    final_dir = SORTIE_DIR / project_name / "final"
    pub_dir   = SORTIE_DIR / project_name / "publication"

    from app.project_state import load_project_state
    ps  = load_project_state(project_name)
    pub = ps.get("publication", {})

    pub_source_avail = (
        (final_dir / "manuscript_rewritten.md").exists()
        or (final_dir / "manuscript_structured.md").exists()
    )

    # ── Carte 1 : Publication Builder ────────────────────────────────────────

    with st.container(border=True):
        st.subheader("📖 Publication Builder")

        pub_path   = Path(pub.get("publication_path", "")) if pub.get("publication_path") else None
        pub_exists = pub_path is not None and pub_path.exists()
        pub_ok     = pub.get("generated", False) and pub_exists
        pub_at     = (pub.get("generated_at") or "")[:19]
        pub_lang   = (pub.get("language") or "—").upper()
        pub_source = pub.get("source") or "—"

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Statut",      "✅ Générée" if pub_ok else "—")
        c2.metric("Langue",      pub_lang)
        c3.metric("Générée le",  pub_at or "—")
        c4.metric("Source",      pub_source)

        if pub_ok:
            st.success(f"Disponible : `{pub_path.name}`")
        elif not pub_source_avail:
            st.info("Aucun manuscrit source. Lancez d'abord le pipeline éditorial.")

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            if st.button(
                "📖 Construire la publication",
                key=f"pub_build_{project_name}",
                disabled=busy or not pub_source_avail,
                use_container_width=True,
                help="Construit publication.md depuis le manuscrit éditorial.",
            ):
                from app.publication_builder import build_publication
                run_action(
                    f"Publication Builder {project_name}",
                    lambda n=project_name: build_publication(n),
                )
                st.rerun()
        with col2:
            if st.button("📂 publication.md", key=f"pub_open_{project_name}", disabled=not pub_exists, use_container_width=True):
                open_path(pub_path)
        with col3:
            if st.button("📁 Dossier pub/", key=f"pub_dir_{project_name}", disabled=not pub_dir.exists(), use_container_width=True):
                open_path(pub_dir)

    # ── Carte 2 : Publication Sanitizer ──────────────────────────────────────

    with st.container(border=True):
        st.subheader("🧹 Publication Sanitizer")

        san_source = pub_dir / "publication.md"
        san_output = pub_dir / "publication_sanitized.md"
        san_report = pub_dir / "publication_sanitizer_report.md"

        san_state     = pub.get("publication_sanitizer", {})
        san_ok        = san_state.get("generated", False) and san_output.exists()
        san_at        = (san_state.get("generated_at") or "")[:19]
        san_error     = san_state.get("error", "")

        c1, c2, c3 = st.columns(3)
        c1.metric("Statut",     "✅ Générée" if san_ok else "—")
        c2.metric("Générée le", san_at or "—")
        c3.metric("Source",     "publication.md")

        if san_ok:
            st.success(f"Disponible : `{san_output.name}`")
        if san_error and not san_ok:
            st.error(f"Erreur : {san_error}")
        if not san_source.exists():
            st.info("publication.md introuvable. Construisez d'abord la publication.")

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            if st.button(
                "🧹 Nettoyer la publication",
                key=f"san_clean_{project_name}",
                disabled=busy or not san_source.exists(),
                use_container_width=True,
                help="Nettoie publication.md → publication_sanitized.md.",
            ):
                with st.spinner("Nettoyage en cours…"):
                    from app.publication_sanitizer import generate_sanitized_publication
                    result = generate_sanitized_publication(project_name)
                if result and result.exists():
                    st.success(f"Généré : `{result.name}`")
                else:
                    st.error("Échec du nettoyage.")
                st.rerun()
        with col2:
            if st.button("📂 Sanitized", key=f"san_open_{project_name}", disabled=not san_output.exists(), use_container_width=True):
                open_path(san_output)
        with col3:
            if st.button("📋 Rapport", key=f"san_report_{project_name}", disabled=not san_report.exists(), use_container_width=True):
                open_path(san_report)

        if san_ok:
            with st.expander("Aperçu — publication_sanitized.md", expanded=False):
                try:
                    text = san_output.read_text(encoding="utf-8")
                    st.text_area(
                        "Contenu",
                        value=text[:4000] + ("\n…(tronqué)" if len(text) > 4000 else ""),
                        height=300,
                        key=f"san_preview_{project_name}",
                        disabled=True,
                    )
                except Exception:
                    st.caption("Impossible de lire le fichier.")

        if san_report.exists():
            with st.expander("Rapport de nettoyage", expanded=False):
                try:
                    st.markdown(san_report.read_text(encoding="utf-8"))
                except Exception:
                    st.caption("Impossible de lire le rapport.")
