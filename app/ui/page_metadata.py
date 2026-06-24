"""
Page — Métadonnées du projet et de publication.

Deux onglets :
  1. Projet — project.yaml (identification, publication, couverture, options)
  2. Publication — publication_metadata dans project_state.json
"""

from __future__ import annotations

import streamlit as st

from app.ui.ui_utils import run_action, show_action_message


def render(project_name: str) -> None:
    busy = st.session_state.get("processing", False)

    st.title("📝 Métadonnées")
    show_action_message()

    if not project_name:
        st.warning("Aucun projet sélectionné.")
        return

    tab_proj, tab_pub = st.tabs(["Projet (project.yaml)", "Publication"])

    # ── Onglet 1 : Métadonnées projet ────────────────────────────────────────

    with tab_proj:
        _render_project_metadata(project_name, busy)

    # ── Onglet 2 : Métadonnées de publication ────────────────────────────────

    with tab_pub:
        _render_publication_metadata(project_name, busy)


# ─────────────────────────────────────────────────────────────────────────────
# Métadonnées projet (project.yaml)
# ─────────────────────────────────────────────────────────────────────────────

def _render_project_metadata(project_name: str, busy: bool) -> None:
    from app.metadata_editor_service import (
        load_editable_metadata,
        save_editable_metadata,
        validate_metadata,
        keywords_to_string,
        string_to_keywords,
        option_index,
        get_yaml_path,
        DOCTYPE_OPTIONS,
        TEMPLATE_OPTIONS,
        THEME_OPTIONS,
        PAGESIZE_OPTIONS,
        PUBFORMAT_OPTIONS,
        COVERMODE_OPTIONS,
        COVERSTYLE_OPTIONS,
        LANGUAGE_OPTIONS,
    )
    from app.project_state import load_project_state, save_project_state
    from app.ui.ui_utils import open_path

    # Boutons hors formulaire
    col_ext1, col_ext2, col_ext3, col_ext4 = st.columns(4)

    with col_ext1:
        if st.button("🔄 Recharger", key=f"meta_reload_{project_name}", use_container_width=True):
            for k in [k for k in st.session_state if k.startswith(f"meta_{project_name}_")]:
                del st.session_state[k]
            st.cache_data.clear()
            st.rerun()

    with col_ext2:
        _yaml_file = get_yaml_path(project_name)
        if st.button(
            "📄 Ouvrir YAML",
            key=f"meta_yaml_{project_name}",
            disabled=not _yaml_file.exists(),
            use_container_width=True,
        ):
            open_path(_yaml_file)

    with col_ext3:
        if st.button(
            "📦 Régénérer publication",
            key=f"meta_regen_pub_{project_name}",
            disabled=busy,
            use_container_width=True,
        ):
            from app.production_service import process_exports_only_project
            run_action(
                f"Régénération publication {project_name}",
                lambda n=project_name: process_exports_only_project(n),
            )
            st.rerun()

    with col_ext4:
        if st.button(
            "📦 Régénérer ZIP",
            key=f"meta_regen_zip_{project_name}",
            disabled=busy,
            use_container_width=True,
        ):
            from app.client_export_service import export_client_zip
            run_action(
                f"Régénération ZIP {project_name}",
                lambda n=project_name: export_client_zip(n, force=True),
            )
            st.rerun()

    # Alerte rebuild recommandé
    ps_full = load_project_state(project_name)
    ps_meta = ps_full.get("metadata", {})
    if ps_meta.get("needs_publication_rebuild") or ps_meta.get("needs_cover_rebuild"):
        st.info(
            "ℹ️ Les métadonnées ont été modifiées. "
            "Pensez à régénérer la publication, la couverture et le ZIP."
        )

    _current_pub_mode = ps_full.get("publication_mode") or "BOOK"
    _meta  = load_editable_metadata(project_name)
    _kw_str = keywords_to_string(_meta.get("keywords", []))

    with st.form(f"metadata_form_{project_name}"):

        st.markdown("##### A. Identification")
        _col_a1, _col_a2 = st.columns(2)
        with _col_a1:
            _f_title    = st.text_input("Titre *",     value=_meta.get("title", ""),       key=f"meta_{project_name}_title")
            _f_subtitle = st.text_input("Sous-titre",  value=_meta.get("subtitle", ""),    key=f"meta_{project_name}_subtitle")
        with _col_a2:
            _f_author   = st.text_input("Auteur",      value=_meta.get("author", ""),      key=f"meta_{project_name}_author")
            _f_org      = st.text_input("Organisation", value=_meta.get("organization", ""), key=f"meta_{project_name}_organization")

        _col_a3, _col_a4, _col_a5 = st.columns(3)
        with _col_a3:
            _f_date = st.text_input("Date", value=_meta.get("date", ""), key=f"meta_{project_name}_date", help="Format libre ou YYYY-MM-DD.")
        with _col_a4:
            _f_version = st.text_input("Version", value=_meta.get("version", "1.0"), key=f"meta_{project_name}_version")
        with _col_a5:
            _f_language = st.selectbox("Langue", options=LANGUAGE_OPTIONS, index=option_index(LANGUAGE_OPTIONS, _meta.get("language", "fr")), key=f"meta_{project_name}_language")

        st.divider()
        st.markdown("##### B. Publication")

        _PUBMODE = ["BOOK", "BOOKLET", "SERMON", "TRAINING", "CONSULTING_REPORT", "CORPORATE_REPORT", "PODCAST"]
        _pubmode_idx = _PUBMODE.index(_current_pub_mode) if _current_pub_mode in _PUBMODE else 0
        _f_pubmode = st.selectbox(
            "Mode de publication",
            options=_PUBMODE,
            index=_pubmode_idx,
            key=f"meta_{project_name}_publication_mode",
            help=(
                "• **BOOK** — Livre complet  \n• **BOOKLET** — Livret compact  \n"
                "• **SERMON** — Message/sermon  \n• **TRAINING** — Guide de formation  \n"
                "• **CONSULTING_REPORT** — Rapport conseil  \n"
                "• **CORPORATE_REPORT** — Rapport d'entreprise  \n• **PODCAST** — Retranscription"
            ),
        )

        _col_b1, _col_b2, _col_b3, _col_b4, _col_b5 = st.columns(5)
        with _col_b1:
            _f_doctype   = st.selectbox("Type document", options=DOCTYPE_OPTIONS,   index=option_index(DOCTYPE_OPTIONS,   _meta.get("document_type",       "auto")), key=f"meta_{project_name}_document_type")
        with _col_b2:
            _f_template  = st.selectbox("Gabarit",       options=TEMPLATE_OPTIONS,  index=option_index(TEMPLATE_OPTIONS,  _meta.get("template",            "auto")), key=f"meta_{project_name}_template")
        with _col_b3:
            _f_theme     = st.selectbox("Thème",         options=THEME_OPTIONS,     index=option_index(THEME_OPTIONS,     _meta.get("theme",               "auto")), key=f"meta_{project_name}_theme")
        with _col_b4:
            _f_pagesize  = st.selectbox("Format page",   options=PAGESIZE_OPTIONS,  index=option_index(PAGESIZE_OPTIONS,  _meta.get("page_size",           "auto")), key=f"meta_{project_name}_page_size")
        with _col_b5:
            _f_pubformat = st.selectbox("Format pub.",   options=PUBFORMAT_OPTIONS, index=option_index(PUBFORMAT_OPTIONS, _meta.get("publication_format",  "auto")), key=f"meta_{project_name}_publication_format")

        st.divider()
        st.markdown("##### C. Couverture")
        _col_c1, _col_c2, _col_c3 = st.columns(3)
        with _col_c1:
            _f_covermode  = st.selectbox("Mode génération", options=COVERMODE_OPTIONS, index=option_index(COVERMODE_OPTIONS, _meta.get("cover_generation_mode", "auto")), key=f"meta_{project_name}_cover_generation_mode")
        with _col_c2:
            _f_coverstyle = st.selectbox("Style",           options=COVERSTYLE_OPTIONS, index=option_index(COVERSTYLE_OPTIONS, _meta.get("cover_style", "editorial_realistic")), key=f"meta_{project_name}_cover_style")
        with _col_c3:
            _f_coverimage = st.text_input("Image", value=_meta.get("cover_image", "auto"), key=f"meta_{project_name}_cover_image", help="Chemin relatif ou « auto ».")

        st.divider()
        st.markdown("##### D. Options de publication")
        _col_d1, _col_d2, _col_d3, _col_d4 = st.columns(4)
        with _col_d1:
            _f_incl_cover   = st.checkbox("Couverture",        value=_meta.get("include_cover",        True),  key=f"meta_{project_name}_include_cover")
            _f_incl_toc     = st.checkbox("Table des matières", value=_meta.get("include_toc",          True),  key=f"meta_{project_name}_include_toc")
        with _col_d2:
            _f_incl_pages   = st.checkbox("N° de page",        value=_meta.get("include_page_numbers", True),  key=f"meta_{project_name}_include_page_numbers")
            _f_incl_headers = st.checkbox("En-têtes",          value=_meta.get("include_headers",      True),  key=f"meta_{project_name}_include_headers")
        with _col_d3:
            _f_incl_footers = st.checkbox("Pieds de page",     value=_meta.get("include_footers",      True),  key=f"meta_{project_name}_include_footers")
            _f_incl_date    = st.checkbox("Date",              value=_meta.get("include_date",         True),  key=f"meta_{project_name}_include_date")
        with _col_d4:
            _f_incl_author  = st.checkbox("Auteur",            value=_meta.get("include_author",       True),  key=f"meta_{project_name}_include_author")
            _f_incl_org     = st.checkbox("Organisation",      value=_meta.get("include_organization", True),  key=f"meta_{project_name}_include_organization")

        with st.expander("E. Informations avancées", expanded=False):
            _f_description = st.text_area("Description", value=_meta.get("description", ""), key=f"meta_{project_name}_description", height=80)
            _f_keywords    = st.text_input("Mots-clés (séparés par virgules)", value=_kw_str, key=f"meta_{project_name}_keywords")
            _col_e1, _col_e2 = st.columns(2)
            with _col_e1:
                _f_audience  = st.text_input("Public cible",  value=_meta.get("audience",  ""), key=f"meta_{project_name}_audience")
                _f_category  = st.text_input("Catégorie",     value=_meta.get("category",  ""), key=f"meta_{project_name}_category")
                _f_copyright = st.text_input("Copyright",     value=_meta.get("copyright", ""), key=f"meta_{project_name}_copyright")
                _f_license   = st.text_input("Licence",       value=_meta.get("license",   ""), key=f"meta_{project_name}_license")
            with _col_e2:
                _f_publisher = st.text_input("Éditeur",       value=_meta.get("publisher", ""), key=f"meta_{project_name}_publisher")
                _f_location  = st.text_input("Lieu",          value=_meta.get("location",  ""), key=f"meta_{project_name}_location")
                _f_isbn      = st.text_input("ISBN",          value=_meta.get("isbn",      ""), key=f"meta_{project_name}_isbn")

        _submitted = st.form_submit_button("💾 Enregistrer les métadonnées", disabled=busy, use_container_width=True)

    if _submitted:
        _new_meta = {
            "title":                _f_title.strip(),
            "subtitle":             _f_subtitle.strip(),
            "author":               _f_author.strip(),
            "organization":         _f_org.strip(),
            "language":             _f_language,
            "date":                 _f_date.strip(),
            "version":              _f_version.strip(),
            "document_type":        _f_doctype,
            "template":             _f_template,
            "theme":                _f_theme,
            "page_size":            _f_pagesize,
            "publication_format":   _f_pubformat,
            "cover_generation_mode": _f_covermode,
            "cover_style":          _f_coverstyle,
            "cover_image":          _f_coverimage.strip(),
            "include_cover":         _f_incl_cover,
            "include_toc":           _f_incl_toc,
            "include_page_numbers":  _f_incl_pages,
            "include_headers":       _f_incl_headers,
            "include_footers":       _f_incl_footers,
            "include_date":          _f_incl_date,
            "include_author":        _f_incl_author,
            "include_organization":  _f_incl_org,
            "description":           _f_description.strip(),
            "keywords":              string_to_keywords(_f_keywords),
            "audience":              _f_audience.strip(),
            "category":              _f_category.strip(),
            "copyright":             _f_copyright.strip(),
            "license":               _f_license.strip(),
            "publisher":             _f_publisher.strip(),
            "location":              _f_location.strip(),
            "isbn":                  _f_isbn.strip(),
        }
        from app.metadata_editor_service import validate_metadata
        ok, errors = validate_metadata(_new_meta)
        if not ok:
            for e in errors:
                st.error(f"❌ {e}")
        else:
            _yaml_path = get_yaml_path(project_name)
            if not _yaml_path.parent.exists():
                st.error("❌ Dossier projet introuvable dans depot/. Sauvegarde annulée.")
            else:
                try:
                    saved = save_editable_metadata(project_name, _new_meta)
                    from app.project_state import update_metadata_state
                    update_metadata_state(project_name, saved)
                    ps_state = load_project_state(project_name)
                    ps_state["publication_mode"] = _f_pubmode
                    save_project_state(project_name, ps_state)
                    st.success(f"✅ Métadonnées sauvegardées. Mode : **{_f_pubmode}**")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as exc:
                    st.error(f"❌ Erreur : {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Métadonnées de publication (project_state.json)
# ─────────────────────────────────────────────────────────────────────────────

def _render_publication_metadata(project_name: str, busy: bool) -> None:
    from app.publication_metadata import get_publication_metadata, save_publication_metadata

    st.caption(
        "Ces données sont affichées sur la couverture, la page de titre, "
        "les propriétés DOCX/PDF et le ZIP client."
    )

    pub_meta = get_publication_metadata(project_name)

    PUBMODE = ["BOOK", "BOOKLET", "SERMON", "TRAINING", "CONSULTING_REPORT", "CORPORATE_REPORT", "PODCAST"]

    with st.form(f"pub_meta_form_{project_name}"):
        col1, col2 = st.columns(2)
        with col1:
            pm_title    = st.text_input("Titre",       value=pub_meta.get("title",    ""), key=f"pm_{project_name}_title")
            pm_subtitle = st.text_input("Sous-titre",  value=pub_meta.get("subtitle", ""), key=f"pm_{project_name}_subtitle")
            pm_author   = st.text_input("Auteur",      value=pub_meta.get("author",   ""), key=f"pm_{project_name}_author")
        with col2:
            pm_org  = st.text_input("Organisation", value=pub_meta.get("organization", ""), key=f"pm_{project_name}_organization")
            pm_date = st.text_input("Date de publication", value=pub_meta.get("publication_date", ""), key=f"pm_{project_name}_publication_date", help="Format libre ou YYYY-MM-DD.")
            _pm_mode_idx = PUBMODE.index(pub_meta["publication_mode"]) if pub_meta.get("publication_mode") in PUBMODE else 0
            pm_mode = st.selectbox("Mode de publication", options=PUBMODE, index=_pm_mode_idx, key=f"pm_{project_name}_mode")

        st.info(
            f"Langue documentaire : **{pub_meta.get('document_language', '—').upper()}**  "
            "(détectée automatiquement — modifiable via le pipeline éditorial)"
        )

        _pm_submitted = st.form_submit_button("💾 Enregistrer", disabled=busy, use_container_width=True)

    if _pm_submitted:
        from datetime import date as _date_cls
        pm_new = {
            "title":             pm_title.strip(),
            "subtitle":          pm_subtitle.strip(),
            "author":            pm_author.strip(),
            "organization":      pm_org.strip(),
            "publication_date":  pm_date.strip() or _date_cls.today().isoformat(),
            "publication_mode":  pm_mode,
            "document_language": pub_meta.get("document_language", ""),
            "project_name":      project_name,
        }
        try:
            save_publication_metadata(project_name, pm_new)
            st.success("✅ Métadonnées de publication enregistrées.")
            st.cache_data.clear()
            st.rerun()
        except Exception as exc:
            st.error(f"❌ Erreur : {exc}")
