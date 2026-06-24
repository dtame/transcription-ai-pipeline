"""
Utilitaires partagés pour toutes les pages de l'interface PublishForge.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import streamlit as st

from app.ui_status_service import (
    STATUS_ERROR,
    STATUS_INTERRUPTED,
    STATUS_PARTIAL,
    STATUS_PENDING,
    STATUS_SUCCESS,
    STATUS_UNKNOWN,
)

# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────

STATUS_EMOJI: dict[str, str] = {
    STATUS_SUCCESS:     "🟢",
    "running":          "🔵",
    STATUS_ERROR:       "🔴",
    STATUS_INTERRUPTED: "🟠",
    STATUS_PARTIAL:     "🟡",
    STATUS_PENDING:     "⚪",
    STATUS_UNKNOWN:     "❓",
    "skipped":          "⏭️",
}

PUBMODE_OPTIONS = [
    "BOOK",
    "BOOKLET",
    "SERMON",
    "TRAINING",
    "CONSULTING_REPORT",
    "CORPORATE_REPORT",
    "PODCAST",
]

IMAGE_MODE_OPTIONS = [
    "NONE",
    "LOCAL_FILE",
    "STABLE_DIFFUSION_WEBUI",
    "COMFYUI",
]


# ─────────────────────────────────────────────────────────────────────────────
# Formattage
# ─────────────────────────────────────────────────────────────────────────────

def fmt_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def bool_icon(value: bool) -> str:
    return "✅" if value else "—"


def status_badge(status: str) -> str:
    emoji = STATUS_EMOJI.get(status, "❓")
    return f"{emoji} {status}"


def file_size_human(path: Path) -> str:
    if not path.exists():
        return "—"
    size = path.stat().st_size
    if size < 1024:
        return f"{size} o"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} Ko"
    return f"{size / (1024 * 1024):.1f} Mo"


def file_date_human(path: Path) -> str:
    if not path.exists():
        return "—"
    import datetime
    ts = path.stat().st_mtime
    return datetime.datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")


# ─────────────────────────────────────────────────────────────────────────────
# Ouvrir un fichier ou dossier avec l'application par défaut
# ─────────────────────────────────────────────────────────────────────────────

def open_path(path: Path) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
    except Exception as exc:
        st.error(f"Impossible d'ouvrir {path} : {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Exécution d'une action avec spinner, anti-veille et session state
# ─────────────────────────────────────────────────────────────────────────────

def run_action(label: str, fn) -> None:
    """
    Exécute fn() avec :
    - spinner Streamlit
    - protection anti-veille système
    - mise à jour session_state (processing, last_result, action_message)
    - invalidation du cache données
    """
    from app.sleep_guard import prevent_sleep, allow_sleep_again

    st.session_state.processing   = True
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
            f"✅ {label} terminé en {fmt_duration(duration)}.",
        )
    except Exception as exc:
        duration = time.time() - t0
        st.session_state.last_result = {"error": str(exc)}
        st.session_state.action_message = (
            "error",
            f"❌ {label} a échoué après {fmt_duration(duration)} : {exc}",
        )
    finally:
        allow_sleep_again()
        st.session_state.processing   = False
        st.session_state.sleep_active = False

    st.cache_data.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Affichage du message d'action précédente
# ─────────────────────────────────────────────────────────────────────────────

def show_action_message() -> None:
    if st.session_state.get("action_message"):
        level, text = st.session_state.action_message
        if level == "success":
            st.success(text)
        elif level == "error":
            st.error(text)
        else:
            st.info(text)
