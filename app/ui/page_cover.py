"""
Page — Couverture.

Sections :
  1. Couverture éditoriale (cover_builder) — cover.pdf + cover.png
  2. Image de couverture (cover_image_engine) — moteur image optionnel
  3. Génération SDXL locale (expander)
  4. Import d'une image personnalisée
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from app.paths import SORTIE_DIR
from app.ui.ui_utils import file_date_human, file_size_human, open_path, run_action, show_action_message


def render(project_name: str) -> None:
    busy = st.session_state.get("processing", False)

    st.title("🎨 Couverture")
    show_action_message()

    if not project_name:
        st.warning("Aucun projet sélectionné.")
        return

    from app.project_state import load_project_state
    ps = load_project_state(project_name)

    # ── Couverture éditoriale ─────────────────────────────────────────────────

    with st.container(border=True):
        st.subheader("🖼 Couverture éditoriale")

        cb_cover_dir = SORTIE_DIR / project_name / "publication" / "cover"
        cb_cover_pdf = cb_cover_dir / "cover.pdf"
        cb_cover_png = cb_cover_dir / "cover.png"

        cb_state     = ps.get("cover", {})
        cb_ok        = cb_state.get("generated", False) and cb_cover_pdf.exists()
        cb_at        = (cb_state.get("generated_at") or "")[:19]
        cb_style     = cb_state.get("cover_style") or "—"
        cb_error     = cb_state.get("error") or ""

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Statut",       "✅ Générée" if cb_ok else "—")
        c2.metric("Style",        cb_style)
        c3.metric("PDF",          "✅" if cb_cover_pdf.exists() else "—")
        c4.metric("PNG",          "✅" if cb_cover_png.exists() else "—")

        if cb_ok:
            st.success(f"Disponible : `cover.pdf` — {cb_at}")
        elif cb_error and not cb_ok:
            st.error(f"Erreur : {cb_error}")
        else:
            st.info("Aucune couverture générée. Cliquez sur « Générer » pour créer cover.pdf et cover.png.")

        # Aperçu
        if cb_cover_png.exists() and cb_cover_png.stat().st_size > 100:
            col_prev, col_info = st.columns([1, 2])
            with col_prev:
                st.image(str(cb_cover_png), caption="Aperçu couverture", use_container_width=True)
            with col_info:
                st.caption(f"Taille : {file_size_human(cb_cover_png)}")
                st.caption(f"Date   : {file_date_human(cb_cover_png)}")
                try:
                    from PIL import Image as _PIL
                    with _PIL.open(cb_cover_png) as img:
                        w, h = img.size
                    st.caption(f"Dimensions : {w} × {h} px")
                except Exception:
                    pass

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("🖼 Générer couverture", key=f"cb_gen_{project_name}", disabled=busy, use_container_width=True):
                from app.cover_builder import generate_cover
                run_action(f"Couverture {project_name}", lambda n=project_name: generate_cover(n))
                st.rerun()
        with col2:
            if st.button("📄 cover.pdf", key=f"cb_pdf_{project_name}", disabled=not cb_cover_pdf.exists(), use_container_width=True):
                open_path(cb_cover_pdf)
        with col3:
            if st.button("🖼 cover.png", key=f"cb_png_{project_name}", disabled=not cb_cover_png.exists(), use_container_width=True):
                open_path(cb_cover_png)
        with col4:
            if st.button("📁 Dossier", key=f"cb_dir_{project_name}", disabled=not cb_cover_dir.exists(), use_container_width=True):
                open_path(cb_cover_dir)

    # ── Image de couverture (moteur) ──────────────────────────────────────────

    with st.container(border=True):
        st.subheader("🖼 Image de couverture")

        from app.cover_image_engine import (
            COVER_IMAGE_MODES as CIM_MODES,
            get_cover_image_mode,
            save_cover_image_mode,
            generate_cover_image,
            cover_image_path,
            cover_prompt_path,
            source_dir as cim_source_dir,
        )

        cim_image_file    = cover_image_path(project_name)
        cim_prompt_file   = cover_prompt_path(project_name)
        cim_source_folder = cim_source_dir(project_name)
        cim_mode_saved    = get_cover_image_mode(project_name)
        cim_state         = ps.get("cover_image", {})
        cim_ok            = cim_state.get("generated", False)
        cim_at            = (cim_state.get("generated_at") or "")[:19]

        c1, c2, c3 = st.columns(3)
        c1.metric("Mode image",      cim_mode_saved)
        c2.metric("Image disponible", "✅" if cim_image_file.exists() else "—")
        c3.metric("Générée le",      cim_at or "—")

        st.caption(
            "Moteur optionnel. Compatible : Stable Diffusion · SDXL · Flux Schnell · ComfyUI · Forge."
        )

        _cim_mode_idx = list(CIM_MODES).index(cim_mode_saved) if cim_mode_saved in CIM_MODES else 0
        _selected_mode = st.selectbox(
            "Mode image",
            options=list(CIM_MODES),
            index=_cim_mode_idx,
            key=f"cim_mode_{project_name}",
            help=(
                "NONE : couverture textuelle uniquement.  \n"
                "LOCAL_FILE : déposez cover.jpg/png dans le dossier source/.  \n"
                "STABLE_DIFFUSION_WEBUI / COMFYUI : placeholder (non implémenté)."
            ),
        )

        if _selected_mode != cim_mode_saved:
            try:
                save_cover_image_mode(project_name, _selected_mode)
                st.success(f"Mode mis à jour : {_selected_mode}")
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.error(f"Erreur : {exc}")

        if _selected_mode == "LOCAL_FILE":
            st.info(
                f"Déposez votre image dans : `{cim_source_folder}`  \n"
                "Fichiers acceptés : `cover.jpg`, `cover.jpeg`, `cover.png`"
            )
        elif _selected_mode in ("STABLE_DIFFUSION_WEBUI", "COMFYUI"):
            st.warning(f"Mode **{_selected_mode}** — non encore implémenté. Prompt généré uniquement.")

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            if st.button(
                "🖼 Préparer l'image de couverture",
                key=f"cim_prep_{project_name}",
                disabled=busy,
                use_container_width=True,
            ):
                run_action(f"Image couverture {project_name}", lambda n=project_name: generate_cover_image(n))
                st.rerun()
        with col2:
            if st.button("📄 cover_prompt.txt", key=f"cim_prompt_{project_name}", disabled=not cim_prompt_file.exists(), use_container_width=True):
                open_path(cim_prompt_file)
        with col3:
            if st.button("📁 Dossier source/", key=f"cim_src_{project_name}", use_container_width=True):
                cim_source_folder.mkdir(parents=True, exist_ok=True)
                open_path(cim_source_folder)

        if cim_prompt_file.exists():
            with st.expander("cover_prompt.txt", expanded=False):
                try:
                    st.code(cim_prompt_file.read_text(encoding="utf-8"), language="text")
                except Exception:
                    st.caption("Impossible de lire le fichier.")

        if cim_image_file.exists() and cim_image_file.stat().st_size > 0:
            col_prev, col_info = st.columns([1, 2])
            with col_prev:
                st.image(str(cim_image_file), caption="cover_image.png", use_container_width=True)
            with col_info:
                st.caption(f"Taille : {file_size_human(cim_image_file)}")
                st.caption("Sera utilisée automatiquement à la prochaine génération PDF/DOCX.")

    # ── Génération SDXL locale ────────────────────────────────────────────────

    with st.expander("Générer image de couverture (SDXL local)", expanded=False):
        st.caption(
            "Génère une image PNG avec Stable Diffusion XL local (~6 Go au premier usage). "
            "Requiert : diffusers, transformers, accelerate, safetensors, torch."
        )
        from app.project_metadata import load_project_metadata as _load_meta
        sdxl_meta     = _load_meta(project_name)
        sdxl_title    = st.text_input("Titre",                          value=sdxl_meta.get("title",    ""),  key=f"sdxl_title_{project_name}")
        sdxl_subtitle = st.text_input("Sous-titre (optionnel)",          value=sdxl_meta.get("subtitle", ""), key=f"sdxl_sub_{project_name}")
        sdxl_theme    = st.text_input("Résumé thématique visuel",        value="",                            key=f"sdxl_theme_{project_name}", placeholder="ex: peaceful nature retreat, light")
        sdxl_seed_raw = st.text_input("Seed (optionnel)",                value="42",                          key=f"sdxl_seed_{project_name}")
        sdxl_seed: int | None = None
        try:
            sdxl_seed = int(sdxl_seed_raw) if sdxl_seed_raw.strip() else None
        except ValueError:
            st.warning("Seed invalide.")

        if st.button(
            "Générer image SDXL",
            key=f"sdxl_gen_{project_name}",
            disabled=busy or not sdxl_title.strip(),
            use_container_width=True,
        ):
            def _run_sdxl(n=project_name, t=sdxl_title, sub=sdxl_subtitle, th=sdxl_theme, s=sdxl_seed):
                from app.image_engine.image_service import generate_project_cover_image
                return str(generate_project_cover_image(
                    project_name=n, title=t, subtitle=sub or None,
                    theme_summary=th or None, seed=s,
                ))
            run_action(f"SDXL couverture {project_name}", _run_sdxl)
            st.rerun()

        sdxl_png = SORTIE_DIR / project_name / "images" / "cover_front" / "cover_front.png"
        if sdxl_png.exists():
            st.image(str(sdxl_png), caption="Couverture SDXL", use_container_width=True)

    # ── Import image personnalisée ────────────────────────────────────────────

    st.markdown("**Importer une image personnalisée**")
    uploaded = st.file_uploader(
        "Choisir une image (jpg, jpeg, png)",
        type=["jpg", "jpeg", "png"],
        key=f"cover_upload_{project_name}",
    )
    if uploaded is not None:
        import tempfile
        suffix = Path(uploaded.name).suffix.lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded.read())
            tmp_path = Path(tmp.name)
        try:
            from app.cover_generation_service import import_user_cover
            dest = import_user_cover(project_name, tmp_path)
            st.success(f"Image importée : {dest.name}")
            st.cache_data.clear()
            st.rerun()
        except Exception as exc:
            st.error(f"Erreur import : {exc}")
        finally:
            tmp_path.unlink(missing_ok=True)
