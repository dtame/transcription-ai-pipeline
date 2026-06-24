"""
PublishForge — Interface principale Streamlit.

Lancement :
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Configuration de la page (doit être le PREMIER appel Streamlit) ──────────

st.set_page_config(
    page_title="PublishForge",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Imports projet ────────────────────────────────────────────────────────────

from app.paths import DEPOT_DIR, SORTIE_DIR
from app.ui_status_service import get_all_projects_status, get_project_status

# ── Session state par défaut ──────────────────────────────────────────────────

_DEFAULTS = {
    "selected_project":  None,
    "processing":        False,
    "sleep_active":      False,
    "last_result":       None,
    "action_message":    None,
    "current_page":      "🏠 Tableau de bord",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Lecture de la version ──────────────────────────────────────────────────────

_version_file = ROOT / "VERSION"
_version = _version_file.read_text(encoding="utf-8").strip() if _version_file.exists() else "1.0"

# ── Liste des projets ─────────────────────────────────────────────────────────

@st.cache_data(ttl=10)
def _load_projects() -> list[str]:
    """Découvre les projets depuis depot/ ET sortie/."""
    projects: set[str] = set()

    # Projets dans depot/
    if DEPOT_DIR.exists():
        for d in DEPOT_DIR.iterdir():
            if d.is_dir():
                # Normalise le nom (remplace espaces)
                projects.add(d.name.replace(" ", "_"))

    # Projets dans sortie/
    if SORTIE_DIR.exists():
        for d in SORTIE_DIR.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                projects.add(d.name)

    return sorted(projects)


@st.cache_data(ttl=10)
def _load_statuses() -> dict[str, dict]:
    """Charge les statuts pour tous les projets connus."""
    try:
        statuses = get_all_projects_status()
        return {s["name"]: s for s in statuses}
    except Exception:
        return {}


_STATUS_EMOJI = {
    "success":     "🟢",
    "running":     "🔵",
    "error":       "🔴",
    "interrupted": "🟠",
    "partial":     "🟡",
    "pending":     "⚪",
    "unknown":     "❓",
}

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:

    # ── Zone 1 : Identité ────────────────────────────────────────────────────

    st.markdown(
        """
        <div style="text-align:center;padding:0.5rem 0 0.25rem 0">
            <div style="font-size:1.6rem;font-weight:700;letter-spacing:1px">📚 PublishForge</div>
            <div style="font-size:0.8rem;color:#888;margin-top:2px">Audio → Publication</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_v1, col_v2 = st.columns(2)
    col_v1.caption(f"Version {_version}")
    col_v2.caption("🖥 Local AI")

    st.divider()

    # ── Zone 2 : Projet actif ────────────────────────────────────────────────

    projects     = _load_projects()
    all_statuses = _load_statuses()

    if not projects:
        st.warning("Aucun projet trouvé.  \nCréez un dossier dans `depot/`.")
        st.session_state.selected_project = None
    else:
        # Maintient le projet sélectionné ou prend le premier
        current = st.session_state.selected_project
        if current not in projects:
            current = projects[0]
            st.session_state.selected_project = current

        # Sélecteur de projet
        _default_idx = projects.index(current) if current in projects else 0

        def _fmt_project(name: str) -> str:
            s = all_statuses.get(name, {})
            emoji = _STATUS_EMOJI.get(s.get("status", "unknown"), "❓")
            return f"{emoji}  {name}"

        selected = st.selectbox(
            "Projet",
            options=projects,
            index=_default_idx,
            format_func=_fmt_project,
            key="sidebar_project_select",
            label_visibility="collapsed",
        )

        if selected != st.session_state.selected_project:
            st.session_state.selected_project = selected
            st.session_state.last_result      = None
            st.session_state.action_message   = None
            st.cache_data.clear()
            st.rerun()

        # Infos projet actif
        pname = st.session_state.selected_project
        if pname:
            pstatus = all_statuses.get(pname, {})
            from app.project_state import load_project_state as _lps
            _ps = _lps(pname)

            st.markdown(
                f"""
                <div style="background:#1e1e2e;border-radius:8px;padding:0.6rem 0.8rem;margin:0.4rem 0">
                    <div style="font-size:0.72rem;color:#888;text-transform:uppercase;letter-spacing:0.8px">Projet actif</div>
                    <div style="font-size:1rem;font-weight:600;margin-top:2px">{pname}</div>
                    <div style="font-size:0.78rem;color:#aaa;margin-top:4px">
                        Langue : <b>{(_ps.get('editorial', {}).get('document_language') or '—').upper()}</b>
                    </div>
                    <div style="font-size:0.78rem;color:#aaa">
                        Mode : <b>{_ps.get('publication_mode') or '—'}</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()

    # ── Zone 3 : Indicateur traitement en cours ──────────────────────────────

    if st.session_state.get("processing"):
        st.info("⏳ Traitement en cours…")

    # ── Zone 4 : Menu principal ──────────────────────────────────────────────

    _PAGES = [
        "🏠 Tableau de bord",
        "📝 Métadonnées",
        "📚 Pipeline éditorial",
        "📖 Publication",
        "🎨 Couverture",
        "📄 DOCX / PDF",
        "📦 Package client",
        "⚙ Paramètres",
    ]

    page = st.radio(
        "Navigation",
        options=_PAGES,
        index=_PAGES.index(st.session_state.current_page)
            if st.session_state.current_page in _PAGES else 0,
        key="sidebar_nav",
        label_visibility="collapsed",
    )

    if page != st.session_state.current_page:
        st.session_state.current_page = page
        st.rerun()

    st.divider()
    st.caption(
        f"PublishForge v{_version}  \n"
        f"Mis à jour : {datetime.now().strftime('%H:%M:%S')}"
    )

# ─────────────────────────────────────────────────────────────────────────────
# Contenu principal — dispatch vers les pages
# ─────────────────────────────────────────────────────────────────────────────

pname = st.session_state.get("selected_project")

if page == "🏠 Tableau de bord":
    from app.ui.page_dashboard import render
    render(pname)

elif page == "📝 Métadonnées":
    from app.ui.page_metadata import render
    render(pname)

elif page == "📚 Pipeline éditorial":
    from app.ui.page_editorial import render
    render(pname)

elif page == "📖 Publication":
    from app.ui.page_publication import render
    render(pname)

elif page == "🎨 Couverture":
    from app.ui.page_cover import render
    render(pname)

elif page == "📄 DOCX / PDF":
    from app.ui.page_docx_pdf import render
    render(pname)

elif page == "📦 Package client":
    from app.ui.page_client_package import render
    render(pname)

elif page == "⚙ Paramètres":
    from app.ui.page_settings import render
    render(pname)
