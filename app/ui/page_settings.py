"""
Page — Paramètres.

Sections :
  1. Mode de publication
  2. Mode image de couverture
  3. Langue documentaire
  4. Chemins système
"""

from __future__ import annotations

import streamlit as st

from app.paths import BASE_DIR, DEPOT_DIR, SORTIE_DIR, LOGS_DIR, TEMP_DIR
from app.ui.ui_utils import PUBMODE_OPTIONS, open_path


def render(project_name: str) -> None:
    busy = st.session_state.get("processing", False)

    st.title("⚙ Paramètres")

    if not project_name:
        st.warning("Aucun projet sélectionné.")
        return

    from app.project_state import load_project_state, save_project_state

    ps = load_project_state(project_name)

    tab_pub, tab_img, tab_lang, tab_paths = st.tabs([
        "Publication",
        "Image couverture",
        "Langue",
        "Chemins système",
    ])

    # ── Onglet Publication ────────────────────────────────────────────────────

    with tab_pub:
        st.subheader("Mode de publication")
        st.caption(
            "Détermine la structure et le style visuel du document final.  \n"
            "Ce choix est utilisé par la Publication Builder et la couverture."
        )

        current_mode = ps.get("publication_mode") or "BOOK"
        _mode_idx = PUBMODE_OPTIONS.index(current_mode) if current_mode in PUBMODE_OPTIONS else 0

        new_mode = st.selectbox(
            "Mode de publication",
            options=PUBMODE_OPTIONS,
            index=_mode_idx,
            key=f"settings_pubmode_{project_name}",
        )

        mode_descriptions = {
            "BOOK":             "Livre complet — Préface, chapitres, conclusion.",
            "BOOKLET":          "Livret compact — Sections, sans page de titre.",
            "SERMON":           "Message/sermon — Points clés, références bibliques.",
            "TRAINING":         "Guide de formation — Objectifs, modules, exercices.",
            "CONSULTING_REPORT": "Rapport conseil — Résumé exécutif, diagnostic, recommandations.",
            "CORPORATE_REPORT": "Rapport d'entreprise — Analyse, résultats, recommandations.",
            "PODCAST":          "Retranscription podcast — Résumé épisode, temps forts, citations.",
        }
        st.info(mode_descriptions.get(new_mode, ""))

        if st.button("💾 Enregistrer le mode", key=f"settings_save_mode_{project_name}", disabled=busy, use_container_width=True):
            ps["publication_mode"] = new_mode
            save_project_state(project_name, ps)
            st.success(f"Mode de publication mis à jour : **{new_mode}**")
            st.cache_data.clear()
            st.rerun()

    # ── Onglet Image couverture ───────────────────────────────────────────────

    with tab_img:
        st.subheader("Mode image de couverture")

        from app.cover_image_engine import (
            COVER_IMAGE_MODES,
            get_cover_image_mode,
            save_cover_image_mode,
        )

        img_mode_saved = get_cover_image_mode(project_name)
        _img_modes     = list(COVER_IMAGE_MODES)
        _img_idx       = _img_modes.index(img_mode_saved) if img_mode_saved in _img_modes else 0

        new_img_mode = st.selectbox(
            "Mode image",
            options=_img_modes,
            index=_img_idx,
            key=f"settings_imgmode_{project_name}",
        )

        img_descriptions = {
            "NONE":                   "Couverture textuelle uniquement (défaut recommandé).",
            "LOCAL_FILE":             "Utilise une image déposée manuellement dans depot/<projet>/assets/.",
            "STABLE_DIFFUSION_WEBUI": "Génération via Stable Diffusion WebUI (placeholder).",
            "COMFYUI":                "Génération via ComfyUI (placeholder).",
        }
        st.info(img_descriptions.get(new_img_mode, ""))

        if st.button("💾 Enregistrer le mode image", key=f"settings_save_img_{project_name}", disabled=busy, use_container_width=True):
            try:
                save_cover_image_mode(project_name, new_img_mode)
                st.success(f"Mode image mis à jour : **{new_img_mode}**")
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.error(f"Erreur : {exc}")

    # ── Onglet Langue ─────────────────────────────────────────────────────────

    with tab_lang:
        st.subheader("Langue documentaire")

        ed    = ps.get("editorial", {})
        lang  = ed.get("document_language") or "—"

        st.metric("Langue détectée", lang.upper() if lang != "—" else "—")

        st.caption(
            "La langue documentaire est détectée automatiquement lors de la "
            "transformation éditoriale. Elle ne peut pas être modifiée directement ici.  \n"
            "Pour changer la langue, modifiez le projet et relancez le pipeline éditorial."
        )

        from app.metadata_editor_service import LANGUAGE_OPTIONS, option_index
        from app.publication_metadata import get_publication_metadata, save_publication_metadata

        pub_meta = get_publication_metadata(project_name)
        _lang_override_idx = option_index(LANGUAGE_OPTIONS, pub_meta.get("document_language", "fr"))

        with st.form(f"settings_lang_form_{project_name}"):
            _lang_override = st.selectbox(
                "Forcer la langue (override)",
                options=LANGUAGE_OPTIONS,
                index=_lang_override_idx,
                key=f"settings_lang_{project_name}",
                help="Écrase la langue détectée automatiquement pour les exports.",
            )
            if st.form_submit_button("💾 Appliquer", disabled=busy, use_container_width=True):
                pub_meta_new = dict(pub_meta)
                pub_meta_new["document_language"] = _lang_override
                try:
                    save_publication_metadata(project_name, pub_meta_new)
                    st.success(f"Langue mise à jour : **{_lang_override}**")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as exc:
                    st.error(f"Erreur : {exc}")

    # ── Onglet Chemins système ────────────────────────────────────────────────

    with tab_paths:
        st.subheader("Chemins système")

        paths = {
            "Racine projet":   BASE_DIR,
            "Dépôt sources":   DEPOT_DIR,
            "Sortie":          SORTIE_DIR,
            "Logs":            LOGS_DIR,
            "Temp":            TEMP_DIR,
            "Sortie projet":   SORTIE_DIR / project_name,
            "Final":           SORTIE_DIR / project_name / "final",
            "Publication":     SORTIE_DIR / project_name / "publication",
            "Cover":           SORTIE_DIR / project_name / "publication" / "cover",
            "Client":          SORTIE_DIR / project_name / "client",
        }

        for label, path in paths.items():
            col_l, col_p, col_b = st.columns([2, 4, 1])
            col_l.markdown(f"**{label}**")
            exists = path.exists()
            col_p.code(str(path), language=None)
            if col_b.button(
                "📁" if exists else "❌",
                key=f"path_open_{project_name}_{label}",
                disabled=not exists,
                help=f"Ouvrir {path}" if exists else "Dossier inexistant",
            ):
                open_path(path)
