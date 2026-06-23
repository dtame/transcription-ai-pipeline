"""
TranscriptionAI — Tableau de bord local (Streamlit).

Lancement :
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

# S'assurer que la racine du projet est dans sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ─────────────────────────────────────────────────────────────────────────────
# Configuration de la page (doit être le premier appel Streamlit)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TranscriptionAI",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
# Imports du projet (après set_page_config)
# ─────────────────────────────────────────────────────────────────────────────
from app.paths import SORTIE_DIR
from app.ui_status_service import (
    STATUS_ERROR,
    STATUS_INTERRUPTED,
    STATUS_PARTIAL,
    STATUS_PENDING,
    STATUS_SUCCESS,
    STATUS_UNKNOWN,
    detect_interrupted_projects,
    get_all_errors,
    get_all_projects_status,
    get_all_run_logs,
    get_project_errors,
    get_project_status,
    get_incomplete_projects,
)

# ─────────────────────────────────────────────────────────────────────────────
# Initialisation du session state
# ─────────────────────────────────────────────────────────────────────────────
_DEFAULTS = {
    "selected_project":  None,
    "processing":        False,
    "sleep_active":      False,
    "last_result":       None,
    "show_all_errors":   False,
    "action_message":    None,   # (level, text)  level = "success"|"error"|"info"
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ─────────────────────────────────────────────────────────────────────────────
# Utilitaires
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def open_path(path: Path) -> None:
    """Ouvre un fichier ou dossier avec l'application par défaut du système."""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
    except Exception as exc:
        st.error(f"Impossible d'ouvrir {path} : {exc}")


_STATUS_EMOJI = {
    STATUS_SUCCESS:     "🟢",
    "running":          "🔵",
    STATUS_ERROR:       "🔴",
    STATUS_INTERRUPTED: "🟠",
    STATUS_PARTIAL:     "🟡",
    STATUS_PENDING:     "⚪",
    STATUS_UNKNOWN:     "❓",
    "skipped":          "⏭️",
}

def status_badge(status: str) -> str:
    emoji = _STATUS_EMOJI.get(status, "❓")
    return f"{emoji} {status}"


def _bool_icon(value: bool) -> str:
    return "✅" if value else "—"


def _run_action(label: str, fn) -> None:
    """
    Exécute une fonction de traitement avec :
    - anti-veille (prevent_sleep / allow_sleep_again)
    - spinner Streamlit
    - mise à jour de session_state
    - invalidation du cache
    """
    from app.sleep_guard import prevent_sleep, allow_sleep_again

    st.session_state.processing  = True
    st.session_state.sleep_active = True
    st.session_state.last_result  = None
    st.session_state.action_message = None

    t0 = time.time()
    prevent_sleep()
    try:
        with st.spinner(f"{label}…"):
            result = fn()
        st.session_state.last_result = result
        duration = time.time() - t0
        st.session_state.action_message = (
            "success",
            f"✅ {label} terminé en {_fmt_duration(duration)}.",
        )
    except Exception as exc:
        duration = time.time() - t0
        st.session_state.last_result = {"error": str(exc)}
        st.session_state.action_message = (
            "error",
            f"❌ {label} a échoué après {_fmt_duration(duration)} : {exc}",
        )
    finally:
        allow_sleep_again()
        st.session_state.processing  = False
        st.session_state.sleep_active = False

    # Invalide le cache pour forcer le rechargement
    st.cache_data.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Chargement des données (cachées 10 s pour éviter les rechargements répétés)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=10)
def _load_all_statuses() -> list[dict]:
    return get_all_projects_status()


@st.cache_data(ttl=10)
def _load_run_logs() -> list[dict]:
    return get_all_run_logs()


@st.cache_data(ttl=10)
def _load_interrupted() -> list[str]:
    return detect_interrupted_projects()


# ─────────────────────────────────────────────────────────────────────────────
# En-tête
# ─────────────────────────────────────────────────────────────────────────────

st.title("🎙️ TranscriptionAI — Tableau de bord local")
st.caption(f"Dernière mise à jour : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

# Indicateur anti-veille
if st.session_state.sleep_active:
    st.info("🔋 **Veille désactivée pendant le traitement : oui** — un traitement est en cours.")
else:
    st.success("💤 Veille désactivée pendant le traitement : **non** — aucun traitement actif.")

# Message d'action précédente
if st.session_state.action_message:
    level, text = st.session_state.action_message
    if level == "success":
        st.success(text)
    elif level == "error":
        st.error(text)
    else:
        st.info(text)


# ─────────────────────────────────────────────────────────────────────────────
# Chargement des données
# ─────────────────────────────────────────────────────────────────────────────

all_statuses    = _load_all_statuses()
run_logs        = _load_run_logs()
interrupted_now = _load_interrupted()

busy = st.session_state.processing  # raccourci


# ─────────────────────────────────────────────────────────────────────────────
# Section 1 — État global
# ─────────────────────────────────────────────────────────────────────────────

st.header("État global")

_total       = len(all_statuses)
_done        = sum(1 for s in all_statuses if s["status"] == STATUS_SUCCESS)
_errors      = sum(1 for s in all_statuses if s["status"] == STATUS_ERROR)
_incomplete  = _total - _done
_interrupted = len(interrupted_now)
_total_audio = sum(s["audio"]["total"] for s in all_statuses)
_total_chunks = sum(s["chunks"]["total"] for s in all_statuses)
_total_pdf   = sum(
    1 for s in all_statuses
    if s["publication"]["pdf"] or s["exports"]["pdf"]
)
_total_docx  = sum(
    1 for s in all_statuses
    if s["publication"]["docx"] or s["exports"]["docx"]
)

cols_metrics = st.columns(8)
cols_metrics[0].metric("Projets",      _total)
cols_metrics[1].metric("Terminés",     _done)
cols_metrics[2].metric("Incomplets",   _incomplete)
cols_metrics[3].metric("Erreurs",      _errors)
cols_metrics[4].metric("Interrompus",  _interrupted)
cols_metrics[5].metric("Audios",       _total_audio)
cols_metrics[6].metric("PDF",          _total_pdf)
cols_metrics[7].metric("DOCX",         _total_docx)


# ─────────────────────────────────────────────────────────────────────────────
# Section 2 — Actions globales
# ─────────────────────────────────────────────────────────────────────────────

st.header("Actions globales")

cols_actions = st.columns([2, 2, 2, 2, 1.5, 1.5])

with cols_actions[0]:
    if st.button(
        "▶ Traiter tous les projets",
        disabled=busy,
        use_container_width=True,
        help="Exécute le pipeline complet sur tous les projets détectés dans depot/.",
    ):
        from app.production_service import process_all_projects
        _run_action("Traitement de tous les projets", process_all_projects)
        st.rerun()

with cols_actions[1]:
    if st.button(
        "⏩ Reprendre tous les incomplets",
        disabled=busy,
        use_container_width=True,
        help="Relance uniquement les projets qui ne sont pas encore terminés.",
    ):
        from app.production_service import resume_incomplete_projects
        _run_action("Reprise des projets incomplets", resume_incomplete_projects)
        st.rerun()

with cols_actions[2]:
    if st.button(
        "📦 Exports seulement (tous)",
        disabled=busy,
        use_container_width=True,
        help="Génère publication + DOCX + PDF pour tous les projets, sans transcription ni IA.",
    ):
        from app.production_service import process_exports_only
        _run_action("Génération des exports (tous)", process_exports_only)
        st.rerun()

with cols_actions[3]:
    if st.button(
        "📊 Rapports seulement (tous)",
        disabled=busy,
        use_container_width=True,
        help="Régénère uniquement les fichiers report.json pour tous les projets.",
    ):
        from app.production_service import process_reports_only
        _run_action("Génération des rapports (tous)", process_reports_only)
        st.rerun()

with cols_actions[4]:
    if st.button(
        "🔍 Toutes les erreurs",
        use_container_width=True,
        help="Affiche ou masque les erreurs de tous les projets.",
    ):
        st.session_state.show_all_errors = not st.session_state.show_all_errors
        st.rerun()

with cols_actions[5]:
    if st.button(
        "🔄 Rafraîchir",
        use_container_width=True,
        help="Recharge les états, rapports et logs.",
    ):
        st.cache_data.clear()
        st.rerun()

# Panneau toutes les erreurs
if st.session_state.show_all_errors:
    st.subheader("Toutes les erreurs")
    all_errs = get_all_errors()
    if not all_errs:
        st.success("Aucune erreur détectée dans aucun projet.")
    else:
        for err in all_errs:
            proj_label = err.get("project", "?")
            step_label = err.get("step", "?")
            date_label = err.get("date", "")
            with st.expander(
                f"[{proj_label}] {step_label}  —  {date_label}  [{err.get('source', '?')}]",
                expanded=False,
            ):
                st.code(err.get("message") or "Pas de message d'erreur")
                if err.get("file"):
                    st.caption(f"Fichier : {err['file']}")


# ─────────────────────────────────────────────────────────────────────────────
# Section 3 — Tableau des projets
# ─────────────────────────────────────────────────────────────────────────────

st.header("Projets")

if not all_statuses:
    st.warning(
        "Aucun projet détecté dans `depot/`. "
        "Créez un sous-dossier avec des fichiers audio (.mp3, .m4a, .ogg…) pour commencer."
    )
    project_names: list[str] = []
else:
    project_names = [s["name"] for s in all_statuses]

    # Sélecteur de projet
    _default_idx = 0
    if st.session_state.selected_project in project_names:
        _default_idx = project_names.index(st.session_state.selected_project)

    selected_idx = st.selectbox(
        "Sélectionner un projet",
        options=range(len(project_names)),
        index=_default_idx,
        format_func=lambda i: f"{_STATUS_EMOJI.get(all_statuses[i]['status'], '❓')}  {project_names[i]}",
        key="project_selectbox",
    )
    st.session_state.selected_project = project_names[selected_idx]

    # Tableau récapitulatif
    table_rows = []
    for s in all_statuses:
        audio  = s["audio"]
        chunks = s["chunks"]
        table_rows.append({
            "Projet":          s["name"],
            "Statut":          status_badge(s["status"]),
            "Audio":           f"{audio['transcribed']}/{audio['total']}",
            "Chunks":          f"{chunks['done']}/{chunks['total']}",
            "Corrections":     str(s["corrections"]),
            "Harmonisation":   _bool_icon(s["harmonized"]),
            "Publication":     _bool_icon(s["publication"]["markdown"]),
            "DOCX":            _bool_icon(s["publication"]["docx"] or s["exports"]["docx"]),
            "PDF":             _bool_icon(s["publication"]["pdf"]  or s["exports"]["pdf"]),
            "Dernière exéc.":  s.get("last_run") or "—",
            "Erreurs":         str(s["error_count"]),
        })

    st.dataframe(table_rows, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# Section 4 — Détail du projet sélectionné
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.selected_project:
    pname = st.session_state.selected_project

    st.header(f"Projet : {pname}")

    # Recharger le statut en temps réel (non caché)
    pstatus = get_project_status(pname)

    # Avertissement interruption probable
    if pstatus["status"] == STATUS_INTERRUPTED or pname in interrupted_now:
        st.warning(
            "⚠️ **Statut : probablement interrompu.**  \n"
            "Le projet était marqué comme `running` au dernier démarrage mais "
            "aucun traitement actif n'a été détecté. "
            "Utilisez **Reprendre** pour relancer sans recommencer."
        )

    # Informations projet
    from app.project_manager import discover_projects

    all_projects = discover_projects()
    project_obj  = next((p for p in all_projects if p.name == pname), None)

    col_d1, col_d2, col_d3 = st.columns(3)

    with col_d1:
        st.metric("Statut global", status_badge(pstatus["status"]))
        if project_obj:
            st.caption(f"**Source :** {project_obj.source_dir}")
        st.caption(f"**Sortie :** {SORTIE_DIR / pname}")
        if pstatus.get("last_run"):
            st.caption(f"**Dernière exécution :** {pstatus['last_run']}")

    with col_d2:
        audio  = pstatus["audio"]
        chunks = pstatus["chunks"]
        st.metric("Audio transcrit",  f"{audio['transcribed']}/{audio['total']}")
        if audio["errors"]:
            st.caption(f"⚠️ {audio['errors']} fichier(s) en erreur")
        st.metric("Chunks IA traités", f"{chunks['done']}/{chunks['total']}")
        st.metric("Corrections",       str(pstatus["corrections"]))

    with col_d3:
        pub = pstatus["publication"]
        exp = pstatus["exports"]
        st.metric("Harmonisation",    _bool_icon(pstatus["harmonized"]))
        st.metric("Publication MD",   _bool_icon(pub["markdown"]))
        st.metric("DOCX",             _bool_icon(pub["docx"] or exp["docx"]))
        st.metric("PDF",              _bool_icon(pub["pdf"]  or exp["pdf"]))

    # ── Actions projet ───────────────────────────────────────────────────────

    st.subheader("Actions sur ce projet")

    col_pa1, col_pa2, col_pa3, col_pa4 = st.columns(4)

    with col_pa1:
        if st.button(
            f"▶ Traiter {pname}",
            disabled=busy,
            use_container_width=True,
            help="Pipeline complet : transcription → IA → corrections → exports.",
        ):
            from app.production_service import process_project
            _run_action(
                f"Traitement de {pname}",
                lambda name=pname: process_project(name),
            )
            st.rerun()

    with col_pa2:
        _resume_disabled = busy or pstatus["status"] == STATUS_SUCCESS
        if st.button(
            f"⏩ Reprendre {pname}",
            disabled=_resume_disabled,
            use_container_width=True,
            help=(
                "Reprend le projet là où il s'est arrêté "
                "(les étapes déjà faites sont ignorées)."
                if not _resume_disabled
                else "Ce projet est déjà terminé avec succès."
            ),
        ):
            from app.production_service import resume_project
            _run_action(
                f"Reprise de {pname}",
                lambda name=pname: resume_project(name),
            )
            st.rerun()

    with col_pa3:
        if st.button(
            "📦 Exports seulement",
            disabled=busy,
            use_container_width=True,
            help="Génère publication + DOCX + PDF sans refaire transcription ni IA.",
        ):
            from app.production_service import process_exports_only_project
            _run_action(
                f"Exports de {pname}",
                lambda name=pname: process_exports_only_project(name),
            )
            st.rerun()

    with col_pa4:
        if st.button(
            "📊 Rapport seulement",
            disabled=busy,
            use_container_width=True,
            help="Régénère uniquement report.json pour ce projet.",
        ):
            from app.production_service import process_reports_only_project
            _run_action(
                f"Rapport de {pname}",
                lambda name=pname: process_reports_only_project(name),
            )
            st.rerun()

    # ── Reconstruction complète (2e ligne) ───────────────────────────────────
    col_rb1, col_rb2, _col_rb3, _col_rb4 = st.columns(4)

    with col_rb1:
        st.markdown("")  # petit espacement
        if st.button(
            "🔁 Reconstruire depuis chunks",
            key=f"rebuild_chunks_{pname}",
            disabled=busy,
            use_container_width=True,
            help=(
                "Reconstruit TOUT depuis les chunks existants sans refaire la "
                "transcription. Utile après correction des prompts IA ou du "
                "pipeline pour obtenir un PDF propre."
            ),
        ):
            from app.production_service import rebuild_project_from_chunks
            _run_action(
                f"Reconstruction de {pname}",
                lambda name=pname: rebuild_project_from_chunks(name),
            )
            st.rerun()

    st.divider()

    # ── Métadonnées du projet ─────────────────────────────────────────────────

    st.subheader("Métadonnées du projet")

    from app.metadata_editor_service import (
        ensure_project_yaml,
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

    # Boutons hors formulaire
    col_meta_ext1, col_meta_ext2, col_meta_ext3, col_meta_ext4 = st.columns(4)

    with col_meta_ext1:
        if st.button(
            "🔄 Recharger les métadonnées",
            key=f"meta_reload_{pname}",
            use_container_width=True,
            help="Recharge les valeurs depuis project.yaml (les modifications non enregistrées seront perdues).",
        ):
            # Purge les valeurs de session pour ce projet afin de forcer
            # le rechargement depuis le fichier YAML
            _meta_keys_to_clear = [
                k for k in st.session_state
                if k.startswith(f"meta_{pname}_")
            ]
            for _mk in _meta_keys_to_clear:
                del st.session_state[_mk]
            st.cache_data.clear()
            st.rerun()

    with col_meta_ext2:
        _yaml_file = get_yaml_path(pname)
        if st.button(
            "📄 Ouvrir project.yaml",
            key=f"meta_open_yaml_{pname}",
            disabled=not _yaml_file.exists(),
            use_container_width=True,
            help="Ouvre project.yaml dans l'éditeur par défaut.",
        ):
            open_path(_yaml_file)

    with col_meta_ext3:
        if st.button(
            "📦 Régénérer publication",
            key=f"meta_regen_pub_{pname}",
            disabled=busy,
            use_container_width=True,
            help="Régénère la publication (MD, DOCX, PDF) avec les métadonnées actuelles.",
        ):
            from app.production_service import process_exports_only_project
            _run_action(
                f"Régénération publication {pname}",
                lambda name=pname: process_exports_only_project(name),
            )
            st.rerun()

    with col_meta_ext4:
        if st.button(
            "📦 Régénérer ZIP Client",
            key=f"meta_regen_zip_{pname}",
            disabled=busy,
            use_container_width=True,
            help="Régénère le ZIP Client avec les métadonnées actuelles.",
        ):
            from app.client_export_service import export_client_zip
            _run_action(
                f"Régénération ZIP Client {pname}",
                lambda name=pname: export_client_zip(name, force=True),
            )
            st.rerun()

    # Indiquer si une reconstruction est recommandée
    from app.project_state import load_project_state as _lps
    _ps_meta = _lps(pname).get("metadata", {})
    if _ps_meta.get("needs_publication_rebuild") or _ps_meta.get("needs_cover_rebuild"):
        st.info(
            "ℹ️ Les métadonnées ont été modifiées. "
            "Pensez à régénérer la publication, la couverture et le ZIP Client."
        )

    # Charger les métadonnées éditables
    _meta = load_editable_metadata(pname)
    _kw_str = keywords_to_string(_meta.get("keywords", []))

    # ── Formulaire ────────────────────────────────────────────────────────────
    with st.form(f"metadata_form_{pname}"):

        # A. Identification
        st.markdown("##### A. Identification")
        _col_a1, _col_a2 = st.columns(2)
        with _col_a1:
            _f_title = st.text_input(
                "Titre *",
                value=_meta.get("title", ""),
                key=f"meta_{pname}_title",
                help="Titre principal du document.",
            )
            _f_subtitle = st.text_input(
                "Sous-titre",
                value=_meta.get("subtitle", ""),
                key=f"meta_{pname}_subtitle",
            )
        with _col_a2:
            _f_author = st.text_input(
                "Auteur",
                value=_meta.get("author", ""),
                key=f"meta_{pname}_author",
                help=(
                    "L'auteur est le nom de la personne, organisation ou client "
                    "propriétaire du contenu.  \n"
                    "Exemples : Pasteur Jean Dupont, Église Espérance, "
                    "ABC Formation, Marie Tremblay, Service Communication."
                ),
            )
            _f_organization = st.text_input(
                "Organisation",
                value=_meta.get("organization", ""),
                key=f"meta_{pname}_organization",
            )

        _col_a3, _col_a4, _col_a5 = st.columns(3)
        with _col_a3:
            _f_date = st.text_input(
                "Date",
                value=_meta.get("date", ""),
                key=f"meta_{pname}_date",
                help="Format libre ou YYYY-MM-DD.",
            )
        with _col_a4:
            _f_version = st.text_input(
                "Version",
                value=_meta.get("version", "1.0"),
                key=f"meta_{pname}_version",
            )
        with _col_a5:
            _f_language = st.selectbox(
                "Langue",
                options=LANGUAGE_OPTIONS,
                index=option_index(LANGUAGE_OPTIONS, _meta.get("language", "fr")),
                key=f"meta_{pname}_language",
            )

        st.divider()

        # B. Publication
        st.markdown("##### B. Publication")
        _col_b1, _col_b2, _col_b3, _col_b4, _col_b5 = st.columns(5)
        with _col_b1:
            _f_doctype = st.selectbox(
                "Type de document",
                options=DOCTYPE_OPTIONS,
                index=option_index(DOCTYPE_OPTIONS, _meta.get("document_type", "auto")),
                key=f"meta_{pname}_document_type",
            )
        with _col_b2:
            _f_template = st.selectbox(
                "Gabarit",
                options=TEMPLATE_OPTIONS,
                index=option_index(TEMPLATE_OPTIONS, _meta.get("template", "auto")),
                key=f"meta_{pname}_template",
            )
        with _col_b3:
            _f_theme = st.selectbox(
                "Thème",
                options=THEME_OPTIONS,
                index=option_index(THEME_OPTIONS, _meta.get("theme", "auto")),
                key=f"meta_{pname}_theme",
            )
        with _col_b4:
            _f_pagesize = st.selectbox(
                "Format de page",
                options=PAGESIZE_OPTIONS,
                index=option_index(PAGESIZE_OPTIONS, _meta.get("page_size", "auto")),
                key=f"meta_{pname}_page_size",
            )
        with _col_b5:
            _f_pubformat = st.selectbox(
                "Format de publication",
                options=PUBFORMAT_OPTIONS,
                index=option_index(PUBFORMAT_OPTIONS, _meta.get("publication_format", "auto")),
                key=f"meta_{pname}_publication_format",
            )

        st.divider()

        # C. Couverture
        st.markdown("##### C. Couverture")
        _col_c1, _col_c2, _col_c3 = st.columns(3)
        with _col_c1:
            _f_covermode = st.selectbox(
                "Mode de génération",
                options=COVERMODE_OPTIONS,
                index=option_index(COVERMODE_OPTIONS, _meta.get("cover_generation_mode", "auto")),
                key=f"meta_{pname}_cover_generation_mode",
            )
        with _col_c2:
            _f_coverstyle = st.selectbox(
                "Style de couverture",
                options=COVERSTYLE_OPTIONS,
                index=option_index(COVERSTYLE_OPTIONS, _meta.get("cover_style", "editorial_realistic")),
                key=f"meta_{pname}_cover_style",
            )
        with _col_c3:
            _f_coverimage = st.text_input(
                "Image de couverture",
                value=_meta.get("cover_image", "auto"),
                key=f"meta_{pname}_cover_image",
                help="Chemin relatif vers une image personnalisée, ou « auto ».",
            )

        st.divider()

        # D. Options de publication
        st.markdown("##### D. Options de publication")
        _col_d1, _col_d2, _col_d3, _col_d4 = st.columns(4)
        with _col_d1:
            _f_incl_cover   = st.checkbox("Couverture",        value=_meta.get("include_cover", True),        key=f"meta_{pname}_include_cover")
            _f_incl_toc     = st.checkbox("Table des matières", value=_meta.get("include_toc", True),          key=f"meta_{pname}_include_toc")
        with _col_d2:
            _f_incl_pages   = st.checkbox("Numéros de page",   value=_meta.get("include_page_numbers", True), key=f"meta_{pname}_include_page_numbers")
            _f_incl_headers = st.checkbox("En-têtes",          value=_meta.get("include_headers", True),      key=f"meta_{pname}_include_headers")
        with _col_d3:
            _f_incl_footers = st.checkbox("Pieds de page",     value=_meta.get("include_footers", True),      key=f"meta_{pname}_include_footers")
            _f_incl_date    = st.checkbox("Date",              value=_meta.get("include_date", True),         key=f"meta_{pname}_include_date")
        with _col_d4:
            _f_incl_author  = st.checkbox("Auteur",            value=_meta.get("include_author", True),       key=f"meta_{pname}_include_author")
            _f_incl_org     = st.checkbox("Organisation",      value=_meta.get("include_organization", True), key=f"meta_{pname}_include_organization")

        st.divider()

        # E. Informations avancées
        with st.expander("E. Informations avancées", expanded=False):
            _f_description = st.text_area(
                "Description",
                value=_meta.get("description", ""),
                key=f"meta_{pname}_description",
                height=80,
            )
            _f_keywords = st.text_input(
                "Mots-clés (séparés par des virgules)",
                value=_kw_str,
                key=f"meta_{pname}_keywords",
                help="Exemple : foi, enseignement, leadership",
            )
            _col_e1, _col_e2 = st.columns(2)
            with _col_e1:
                _f_audience  = st.text_input("Public cible",   value=_meta.get("audience", ""),   key=f"meta_{pname}_audience")
                _f_category  = st.text_input("Catégorie",      value=_meta.get("category", ""),   key=f"meta_{pname}_category")
                _f_copyright = st.text_input("Copyright",      value=_meta.get("copyright", ""),  key=f"meta_{pname}_copyright")
                _f_license   = st.text_input("Licence",        value=_meta.get("license", ""),    key=f"meta_{pname}_license")
            with _col_e2:
                _f_publisher = st.text_input("Éditeur",        value=_meta.get("publisher", ""),  key=f"meta_{pname}_publisher")
                _f_location  = st.text_input("Lieu",           value=_meta.get("location", ""),   key=f"meta_{pname}_location")
                _f_isbn      = st.text_input("ISBN",           value=_meta.get("isbn", ""),       key=f"meta_{pname}_isbn")

        # ── Bouton de sauvegarde ──────────────────────────────────────────────
        _meta_submitted = st.form_submit_button(
            "💾 Enregistrer les métadonnées",
            disabled=busy,
            use_container_width=True,
        )

    # ── Traitement du formulaire ──────────────────────────────────────────────
    if _meta_submitted:
        _new_meta = {
            "title":                _f_title.strip(),
            "subtitle":             _f_subtitle.strip(),
            "author":               _f_author.strip(),
            "organization":         _f_organization.strip(),
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

        _meta_ok, _meta_errors = validate_metadata(_new_meta)
        if not _meta_ok:
            for _me in _meta_errors:
                st.error(f"❌ {_me}")
        else:
            _expected_yaml = get_yaml_path(pname)
            if not _expected_yaml.parent.exists():
                st.error(
                    f"❌ Le dossier projet `{pname}` n'existe pas dans depot/. "
                    f"Sauvegarde annulée — aucun dossier ne sera créé automatiquement."
                )
            else:
                try:
                    _saved_path = save_editable_metadata(pname, _new_meta)
                    from app.project_state import update_metadata_state
                    update_metadata_state(pname, _saved_path)
                    st.success(
                        f"✅ Métadonnées sauvegardées dans :  \n"
                        f"`depot/{pname}/project.yaml`"
                    )
                    st.cache_data.clear()
                    st.rerun()
                except Exception as _me:
                    st.error(f"❌ Erreur lors de la sauvegarde : {_me}")

    st.divider()

    # ── Couverture ───────────────────────────────────────────────────────────

    st.subheader("Couverture")

    _cover_dir = SORTIE_DIR / pname / "cover"
    _cover_jpg = _cover_dir / "cover.jpg"
    _cover_meta_path = _cover_dir / "cover_metadata.json"

    _cover_meta: dict = {}
    if _cover_meta_path.exists():
        try:
            import json as _json
            _cover_meta = _json.loads(_cover_meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    col_cov1, col_cov2 = st.columns([1, 2])

    with col_cov1:
        if _cover_jpg.exists() and _cover_jpg.stat().st_size > 100:
            st.image(str(_cover_jpg), caption="Couverture", use_container_width=True)
        else:
            st.info("Aucune couverture générée.")

    with col_cov2:
        if _cover_meta:
            st.markdown(f"**Type** : {_cover_meta.get('type', '—')}")
            st.markdown(f"**Style** : {_cover_meta.get('style', '—')}")
            st.markdown(f"**Source** : {_cover_meta.get('source', '—')}")
            st.markdown(f"**Moteur** : {_cover_meta.get('provider', '—')}")
            st.markdown(f"**Générée le** : {_cover_meta.get('generated_at', '—')}")
        else:
            st.caption("Aucune métadonnée de couverture disponible.")

        # Dimensions et taille du fichier
        if _cover_jpg.exists() and _cover_jpg.stat().st_size > 100:
            _size_kb = _cover_jpg.stat().st_size / 1024
            st.caption(f"Taille fichier : {_size_kb:.0f} Ko")
            try:
                from PIL import Image as _PILImage
                with _PILImage.open(_cover_jpg) as _pil_img:
                    _cw, _ch = _pil_img.size
                st.caption(f"Dimensions : {_cw} × {_ch} px")
            except Exception:
                pass

        # Actions sur la couverture
        col_ca1, col_ca2, col_ca3, col_ca4, col_ca5 = st.columns(5)

        with col_ca1:
            if st.button(
                "🖼 Générer couverture",
                key=f"cover_gen_{pname}",
                disabled=busy,
                use_container_width=True,
                help="Génère automatiquement une couverture pour ce projet.",
            ):
                from app.cover_generation_service import generate_cover
                _run_action(
                    f"Génération couverture {pname}",
                    lambda name=pname: generate_cover(name),
                )
                st.rerun()

        with col_ca2:
            if st.button(
                "🔄 Régénérer couverture",
                key=f"cover_regen_{pname}",
                disabled=busy,
                use_container_width=True,
                help="Force la régénération même si la couverture est à jour.",
            ):
                from app.cover_generation_service import generate_cover
                _run_action(
                    f"Régénération couverture {pname}",
                    lambda name=pname: generate_cover(name, force=True),
                )
                st.rerun()

        with col_ca3:
            if st.button(
                "📂 Ouvrir couverture",
                key=f"cover_open_{pname}",
                disabled=not _cover_jpg.exists(),
                use_container_width=True,
                help="Ouvre cover.jpg avec l'application par défaut.",
            ):
                open_path(_cover_jpg)

        with col_ca4:
            if st.button(
                "📁 Dossier couverture",
                key=f"cover_dir_{pname}",
                disabled=not _cover_dir.exists(),
                use_container_width=True,
                help="Ouvre le dossier contenant la couverture.",
            ):
                open_path(_cover_dir)

        with col_ca5:
            if st.button(
                "🗑 Supprimer couverture",
                key=f"cover_del_{pname}",
                disabled=not _cover_jpg.exists(),
                use_container_width=True,
                help="Supprime la couverture générée.",
            ):
                from app.cover_generation_service import delete_cover
                delete_cover(pname)
                st.cache_data.clear()
                st.rerun()

    # ── Génération SDXL locale (optionnel) ──────────────────────────────────
    with st.expander("Générer image de couverture (SDXL local)", expanded=False):
        st.caption(
            "Génère une image PNG haute résolution avec Stable Diffusion XL (local). "
            "Le modèle est téléchargé automatiquement lors du premier usage (~6 Go). "
            "Requiert : diffusers, transformers, accelerate, safetensors, torch."
        )

        from app.project_metadata import load_project_metadata as _load_meta
        _sdxl_meta = _load_meta(pname)
        _sdxl_title   = st.text_input(
            "Titre", value=_sdxl_meta.get("title", ""),
            key=f"sdxl_title_{pname}",
        )
        _sdxl_subtitle = st.text_input(
            "Sous-titre (optionnel)", value=_sdxl_meta.get("subtitle", ""),
            key=f"sdxl_subtitle_{pname}",
        )
        _sdxl_theme = st.text_input(
            "Résumé thématique visuel (quelques mots)",
            value="",
            key=f"sdxl_theme_{pname}",
            placeholder="ex: peaceful nature retreat, community, light and warmth",
        )
        _sdxl_seed_raw = st.text_input(
            "Seed (optionnel, entier)", value="42",
            key=f"sdxl_seed_{pname}",
        )
        _sdxl_seed: int | None = None
        try:
            _sdxl_seed = int(_sdxl_seed_raw) if _sdxl_seed_raw.strip() else None
        except ValueError:
            st.warning("Seed invalide, génération non déterministe.")

        if st.button(
            "Générer image SDXL",
            key=f"sdxl_gen_{pname}",
            disabled=busy or not _sdxl_title.strip(),
            use_container_width=True,
            help=(
                "Lance la génération SDXL. "
                "Le modèle doit être installé (pip install diffusers torch …)."
            ),
        ):
            def _run_sdxl(
                name: str = pname,
                title: str = _sdxl_title,
                subtitle: str = _sdxl_subtitle,
                theme: str = _sdxl_theme,
                seed: "int | None" = _sdxl_seed,
            ) -> str:
                from app.image_engine.image_service import generate_project_cover_image
                out = generate_project_cover_image(
                    project_name=name,
                    title=title,
                    subtitle=subtitle or None,
                    theme_summary=theme or None,
                    seed=seed,
                )
                return str(out)

            _run_action(f"Génération SDXL couverture {pname}", _run_sdxl)
            st.rerun()

        # Aperçu de l'image SDXL si elle existe
        _sdxl_png = SORTIE_DIR / pname / "images" / "cover_front" / "cover_front.png"
        if _sdxl_png.exists():
            st.image(str(_sdxl_png), caption="Couverture SDXL (cover_front.png)", use_container_width=True)
            _sdxl_meta_path = _sdxl_png.parent / "cover_front.metadata.json"
            if _sdxl_meta_path.exists():
                try:
                    import json as _sdxl_json
                    _smeta = _sdxl_json.loads(_sdxl_meta_path.read_text(encoding="utf-8"))
                    st.caption(
                        f"Provider : {_smeta.get('provider', '—')} | "
                        f"Modèle : {_smeta.get('model_id', '—')} | "
                        f"Généré le : {_smeta.get('generated_at', '—')[:19]}"
                    )
                except Exception:
                    pass

    # Upload utilisateur
    st.markdown("**Importer une image personnalisée**")
    _uploaded = st.file_uploader(
        "Choisir une image (jpg, jpeg, png)",
        type=["jpg", "jpeg", "png"],
        key=f"cover_upload_{pname}",
        help=(
            "L'image sera copiée dans depot/<projet>/assets/ "
            "et utilisée comme couverture."
        ),
    )
    if _uploaded is not None:
        import tempfile as _tempfile
        _suffix = Path(_uploaded.name).suffix.lower()
        with _tempfile.NamedTemporaryFile(delete=False, suffix=_suffix) as _tmp:
            _tmp.write(_uploaded.read())
            _tmp_path = Path(_tmp.name)
        try:
            from app.cover_generation_service import import_user_cover
            _dest = import_user_cover(pname, _tmp_path)
            st.success(f"Image importée : {_dest.name}")
            st.cache_data.clear()
            st.rerun()
        except Exception as _exc:
            st.error(f"Erreur import : {_exc}")
        finally:
            _tmp_path.unlink(missing_ok=True)

    st.divider()

    # ── Fichiers générés ─────────────────────────────────────────────────────

    st.subheader("Fichiers générés")

    final_dir = SORTIE_DIR / pname / "final"

    _files_to_show: list[tuple[str, Path]] = [
        ("document_final.md",           final_dir / "document_final.md"),
        ("document_final.docx",         final_dir / "document_final.docx"),
        ("document_final.pdf",          final_dir / "document_final.pdf"),
        ("document_publication.md",     final_dir / "document_publication.md"),
        ("document_publication.docx",   final_dir / "document_publication.docx"),
        ("document_publication.pdf",    final_dir / "document_publication.pdf"),
        ("report.json",                 SORTIE_DIR / pname / "report.json"),
        ("📂 Ouvrir dossier final",     final_dir),
    ]

    _file_cols = st.columns(4)
    for _fi, (_label, _fpath) in enumerate(_files_to_show):
        with _file_cols[_fi % 4]:
            if _fpath.exists():
                if st.button(
                    f"📂 {_label}" if not _label.startswith("📂") else _label,
                    key=f"open_{pname}_{_fi}",
                    use_container_width=True,
                ):
                    open_path(_fpath)
            else:
                st.button(
                    f"❌ {_label}" if not _label.startswith("📂") else f"❌ {_label}",
                    key=f"open_{pname}_{_fi}",
                    disabled=True,
                    use_container_width=True,
                )

    st.divider()

    # ── Livraison Client ──────────────────────────────────────────────────────

    st.subheader("Livraison Client")

    from app.client_export_service import export_client_zip, get_client_export_info

    _ce_info = get_client_export_info(pname)

    if _ce_info["exists"]:
        st.success(f"ZIP Client disponible : `{_ce_info['zip_name']}`")

        col_ce_m1, col_ce_m2, col_ce_m3, col_ce_m4 = st.columns(4)
        col_ce_m1.metric("Nom",               _ce_info["zip_name"])
        col_ce_m2.metric("Date de génération", _ce_info["generated_at"] or "—")
        col_ce_m3.metric("Taille",             _ce_info["size_human"])
        col_ce_m4.metric("Fichiers",           str(_ce_info["files_count"]))
    else:
        st.info("Le ZIP Client n'a pas encore été généré pour ce projet.")

    col_ce1, col_ce2, col_ce3, col_ce4 = st.columns(4)

    with col_ce1:
        if st.button(
            "📦 Exporter ZIP Client",
            key=f"ce_export_{pname}",
            disabled=busy,
            use_container_width=True,
            help="Génère le ZIP Client (document_publication.pdf + .docx + report.json + README_CLIENT.txt).",
        ):
            _run_action(
                f"Export ZIP Client {pname}",
                lambda name=pname: export_client_zip(name),
            )
            st.rerun()

    with col_ce2:
        if st.button(
            "🔄 Régénérer ZIP Client",
            key=f"ce_regen_{pname}",
            disabled=busy,
            use_container_width=True,
            help="Force la reconstruction du ZIP même si les fichiers sont inchangés.",
        ):
            _run_action(
                f"Régénération ZIP Client {pname}",
                lambda name=pname: export_client_zip(name, force=True),
            )
            st.rerun()

    with col_ce3:
        if st.button(
            "📂 Ouvrir ZIP Client",
            key=f"ce_open_zip_{pname}",
            disabled=not _ce_info["exists"],
            use_container_width=True,
            help="Ouvre le fichier ZIP avec l'application par défaut.",
        ):
            if _ce_info["zip_path"]:
                open_path(_ce_info["zip_path"])

    with col_ce4:
        _ce_folder = SORTIE_DIR / pname / "client"
        if st.button(
            "📁 Ouvrir dossier client",
            key=f"ce_open_dir_{pname}",
            disabled=not _ce_folder.exists(),
            use_container_width=True,
            help="Ouvre le dossier sortie/<projet>/client/ dans l'explorateur.",
        ):
            open_path(_ce_folder)

    if _ce_info["exists"] and _ce_info["files"]:
        with st.expander("Afficher contenu ZIP", expanded=False):
            for _fname in _ce_info["files"]:
                st.write(f"- {_fname}")

    _pdf_ok  = (SORTIE_DIR / pname / "final" / "document_publication.pdf").exists()
    _docx_ok = (SORTIE_DIR / pname / "final" / "document_publication.docx").exists()
    if not _pdf_ok:
        st.warning("Export publication PDF manquant.")
    if not _docx_ok:
        st.warning("Export publication DOCX manquant.")

    st.divider()

    # ── Erreurs du projet ────────────────────────────────────────────────────

    st.subheader("Erreurs du projet")

    proj_errors = get_project_errors(pname)
    if not proj_errors:
        st.success(f"Aucune erreur détectée pour le projet **{pname}**.")
    else:
        st.warning(f"{len(proj_errors)} erreur(s) détectée(s).")
        for _err in proj_errors:
            with st.expander(
                f"{_err.get('step', '?')}  —  {_err.get('date', '')}  "
                f"[{_err.get('source', '?')}]",
                expanded=False,
            ):
                st.code(_err.get("message") or "Pas de message d'erreur")
                if _err.get("file"):
                    st.caption(f"Fichier : {_err['file']}")


# ─────────────────────────────────────────────────────────────────────────────
# Section 5 — Résultat du dernier traitement
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.last_result:
    _res = st.session_state.last_result
    st.header("Résultat du dernier traitement")

    # Erreur fatale directe
    _fatal = _res.get("error") or _res.get("fatal_error")
    if _fatal:
        st.error(f"Erreur : {_fatal}")

    # Message de saut (skipped)
    if _res.get("status") == "skipped":
        st.info(_res.get("message", "Projet ignoré."))

    # Résumé multi-projets
    if "projects_total" in _res:
        _c1, _c2, _c3, _c4 = st.columns(4)
        _c1.metric("Projets traités", _res.get("projects_total", 0))
        _c2.metric("Succès",          _res.get("projects_success", 0))
        _c3.metric("Erreurs",         _res.get("projects_error", 0))
        _c4.metric("Durée",           _fmt_duration(_res.get("duration_seconds", 0)))

        for _pr in _res.get("projects", []):
            _sym = "✅" if _pr.get("status") == "success" else "❌"
            _dur = _pr.get("duration_seconds", 0)
            with st.expander(
                f"{_sym} {_pr.get('project', '?')}  ({_dur:.1f}s)",
                expanded=False,
            ):
                if _pr.get("fatal_error"):
                    st.error(_pr["fatal_error"])
                for _sname, _sinfo in _pr.get("steps", {}).items():
                    _ssym = "✅" if _sinfo.get("status") == "success" else "❌"
                    _serr = f"  — {_sinfo['error']}" if _sinfo.get("error") else ""
                    st.write(f"{_ssym} `{_sname}`{_serr}")

    # Résumé projet unique
    elif "project" in _res and "steps" in _res:
        _sym = "✅" if _res.get("status") == "success" else "❌"
        st.write(f"{_sym} **Statut :** {_res.get('status')}")
        st.write(f"**Durée :** {_fmt_duration(_res.get('duration_seconds', 0))}")
        if _res.get("steps"):
            with st.expander("Détail des étapes", expanded=False):
                for _sname, _sinfo in _res["steps"].items():
                    _ssym = "✅" if _sinfo.get("status") == "success" else "❌"
                    _serr = f"  — {_sinfo['error']}" if _sinfo.get("error") else ""
                    st.write(f"{_ssym} `{_sname}`{_serr}")


# ─────────────────────────────────────────────────────────────────────────────
# Section 6 — Logs d'exécution récents
# ─────────────────────────────────────────────────────────────────────────────

st.header("Logs d'exécution récents")

if not run_logs:
    st.info("Aucun log d'exécution trouvé dans `logs/`.")
else:
    for _log in run_logs[:10]:
        _started  = _log.get("started_at", "?")
        _total_p  = _log.get("projects_total", 0)
        _succ_p   = _log.get("projects_success", 0)
        _err_p    = _log.get("projects_error", 0)
        _dur      = _log.get("duration_seconds", 0)
        _logfile  = _log.get("_log_file", "")
        _label    = (
            f"{_started}  —  {_total_p} projet(s)  "
            f"✅ {_succ_p} / ❌ {_err_p}  —  {_fmt_duration(_dur)}"
        )
        with st.expander(_label, expanded=False):
            if _logfile:
                st.caption(f"Fichier : logs/{_logfile}")
            for _pr in _log.get("projects", []):
                _sym = "✅" if _pr.get("status") == "success" else "❌"
                st.write(
                    f"{_sym} **{_pr.get('project', '?')}**  "
                    f"({_pr.get('duration_seconds', 0):.1f}s)"
                )
                if _pr.get("fatal_error"):
                    st.error(_pr["fatal_error"])
                for _sname, _sinfo in _pr.get("steps", {}).items():
                    if _sinfo.get("status") == "error":
                        st.write(f"  ❌ `{_sname}` — {_sinfo.get('error', '')}")


# ─────────────────────────────────────────────────────────────────────────────
# Pied de page
# ─────────────────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    "TranscriptionAI  •  Pipeline audio → document  •  "
    "Traitement séquentiel uniquement (aucun parallélisme IA)"
)
