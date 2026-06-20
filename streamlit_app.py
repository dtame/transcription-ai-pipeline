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
