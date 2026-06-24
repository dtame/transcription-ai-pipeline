"""
Editorial Quality Guard — Contrôle qualité éditorial du manuscrit transformé.

Compare manuscript_structured.md et manuscript_rewritten.md et génère un
rapport qualité markdown sans relancer aucun traitement IA ou Whisper.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from app.document_language import get_document_language
from app.logger import log_event
from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state


# ---------------------------------------------------------------------------
# Phrases interdites
# ---------------------------------------------------------------------------

_FORBIDDEN_EN: list[str] = [
    "the speaker explains",
    "the author says",
    "the speaker teaches",
    "the author explains",
    "this summary",
    "let me know if",
    "as an ai",
]

_FORBIDDEN_FR: list[str] = [
    "l'auteur dit",
    "le conférencier explique",
    "l'orateur affirme",
    "ce résumé",
    "en tant qu'ia",
]

# ---------------------------------------------------------------------------
# Marqueurs de langue croisée
# ---------------------------------------------------------------------------

_CROSS_LANG_EN_IN_FR: list[str] = [
    "table of contents",
    "chapter",
    "summary",
    "key points",
]

_CROSS_LANG_FR_IN_EN: list[str] = [
    "table des matières",
    "chapitre",
    "résumé",
    "points clés",
]

# ---------------------------------------------------------------------------
# Traces techniques résiduelles
# ---------------------------------------------------------------------------

_TECHNICAL_TRACES: list[str] = [
    "chunk_",
    "document final",
    "nombre de chunks",
    "chunks avec corrections",
    "let me know if",
    "this structured summary preserves",
]


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _extract_headings(text: str) -> list[str]:
    """Extrait les lignes commençant par # (titres Markdown)."""
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("#")
    ]


def _find_forbidden_phrases(text: str, phrases: list[str]) -> list[str]:
    """Retourne les phrases interdites trouvées dans le texte (insensible à la casse)."""
    text_lower = text.lower()
    return [phrase for phrase in phrases if phrase.lower() in text_lower]


def _find_technical_traces(text: str) -> list[str]:
    """Retourne les traces techniques trouvées dans le texte."""
    text_lower = text.lower()
    return [trace for trace in _TECHNICAL_TRACES if trace.lower() in text_lower]


def _find_cross_language_markers(
    text: str,
    document_language: str,
) -> list[str]:
    """
    Retourne les marqueurs de langue incorrecte détectés.

    Si document_language == "en" → cherche des marqueurs français.
    Si document_language == "fr" → cherche des marqueurs anglais.
    """
    text_lower = text.lower()
    if document_language == "en":
        return [m for m in _CROSS_LANG_FR_IN_EN if m.lower() in text_lower]
    if document_language == "fr":
        return [m for m in _CROSS_LANG_EN_IN_FR if m.lower() in text_lower]
    return []


def _compute_status(
    ratio: float | None,
    rewritten_empty: bool,
    rewritten_missing: bool,
    missing_headings: list[str],
    forbidden_hits: list[str],
    lang_issues: list[str],
    tech_traces: list[str],
) -> str:
    """Détermine le statut global : FAIL / WARNING / PASS."""
    if rewritten_missing or rewritten_empty:
        return "FAIL"
    if ratio is not None and (ratio < 0.60 or ratio > 1.60):
        return "FAIL"
    if missing_headings or forbidden_hits or lang_issues or tech_traces:
        return "WARNING"
    return "PASS"


def _build_recommendation(status: str, issues: dict) -> str:
    """Génère une recommandation textuelle en fonction des problèmes détectés."""
    if status == "FAIL":
        if issues.get("rewritten_missing"):
            return (
                "Le fichier manuscript_rewritten.md est absent. "
                "Lancez d'abord la transformation éditoriale."
            )
        if issues.get("rewritten_empty"):
            return (
                "Le fichier manuscript_rewritten.md est vide. "
                "Relancez la transformation éditoriale."
            )
        ratio = issues.get("ratio")
        if ratio is not None:
            if ratio < 0.60:
                return (
                    f"Le texte réécrit est trop court ({ratio:.0%} du structuré). "
                    "Le modèle a peut-être résumé au lieu de transformer fidèlement. "
                    "Vérifiez le prompt de transformation et relancez."
                )
            if ratio > 1.60:
                return (
                    f"Le texte réécrit est trop long ({ratio:.0%} du structuré). "
                    "Le modèle a peut-être ajouté du contenu fictif. "
                    "Vérifiez le prompt de transformation et relancez."
                )

    if status == "WARNING":
        parts: list[str] = []
        if issues.get("missing_headings"):
            parts.append("corriger les titres manquants")
        if issues.get("forbidden_hits"):
            parts.append("supprimer les phrases interdites détectées")
        if issues.get("lang_issues"):
            parts.append("corriger les incohérences de langue")
        if issues.get("tech_traces"):
            parts.append("nettoyer les traces techniques résiduelles")
        if parts:
            return (
                "Des corrections mineures sont nécessaires : "
                + ", ".join(parts)
                + ". Vous pouvez corriger manuellement ou relancer la transformation."
            )

    return "Le manuscrit transformé est conforme. Vous pouvez procéder à la publication."


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def run_editorial_quality_guard(project_name: str) -> Path | None:
    """
    Compare manuscript_structured.md et manuscript_rewritten.md.
    Génère un rapport qualité éditorial dans final/editorial_quality_report.md.

    Retourne le chemin du rapport généré, ou None en cas d'erreur fatale.
    """
    final_dir       = SORTIE_DIR / project_name / "final"
    structured_path = final_dir / "manuscript_structured.md"
    rewritten_path  = final_dir / "manuscript_rewritten.md"
    report_path     = final_dir / "editorial_quality_report.md"

    print(f"[quality_guard] Démarrage du contrôle qualité pour : {project_name}")

    # ── 1. Vérifier l'existence des fichiers ────────────────────────────────
    rewritten_missing = not rewritten_path.exists()
    structured_missing = not structured_path.exists()

    if structured_missing and rewritten_missing:
        _write_fail_report(
            report_path,
            project_name,
            reason="Les deux fichiers source sont absents (manuscript_structured.md et manuscript_rewritten.md).",
        )
        _update_state(project_name, "FAIL", report_path)
        return report_path

    if structured_missing:
        _write_fail_report(
            report_path,
            project_name,
            reason="Le fichier source manuscript_structured.md est absent.",
        )
        _update_state(project_name, "FAIL", report_path)
        return report_path

    if rewritten_missing:
        issues = {"rewritten_missing": True}
        status = "FAIL"
        recommendation = _build_recommendation(status, issues)
        _write_report(
            report_path,
            project_name,
            status=status,
            structured_len=None,
            rewritten_len=None,
            ratio=None,
            missing_headings=[],
            forbidden_hits=[],
            lang_issues=[],
            tech_traces=[],
            recommendation=recommendation,
            notes=["⚠️ manuscript_rewritten.md absent."],
        )
        _update_state(project_name, status, report_path)
        return report_path

    structured_text = structured_path.read_text(encoding="utf-8")
    rewritten_text  = rewritten_path.read_text(encoding="utf-8")

    # ── 2. Vérifier que le fichier réécrit n'est pas vide ───────────────────
    rewritten_empty = not rewritten_text.strip()

    # ── 3. Comparer les longueurs ────────────────────────────────────────────
    structured_len = len(structured_text)
    rewritten_len  = len(rewritten_text)

    if structured_len > 0 and not rewritten_empty:
        ratio: float | None = rewritten_len / structured_len
    else:
        ratio = None

    # ── 4. Vérifier la conservation des titres ───────────────────────────────
    structured_headings = _extract_headings(structured_text)
    rewritten_headings  = _extract_headings(rewritten_text)
    rewritten_heading_set = {h.lstrip("#").strip().lower() for h in rewritten_headings}

    missing_headings: list[str] = []
    for heading in structured_headings:
        normalized = heading.lstrip("#").strip().lower()
        if normalized and normalized not in rewritten_heading_set:
            missing_headings.append(heading)

    # ── 5. Détecter les phrases interdites ──────────────────────────────────
    forbidden_hits: list[str] = []
    if not rewritten_empty:
        forbidden_hits = (
            _find_forbidden_phrases(rewritten_text, _FORBIDDEN_EN)
            + _find_forbidden_phrases(rewritten_text, _FORBIDDEN_FR)
        )

    # ── 6. Cohérence de langue ───────────────────────────────────────────────
    document_language = get_document_language(project_name, fallback_text=structured_text)
    lang_issues: list[str] = []
    if not rewritten_empty:
        raw_markers = _find_cross_language_markers(rewritten_text, document_language)
        for marker in raw_markers:
            if document_language == "en":
                lang_issues.append(
                    f"Marqueur français détecté dans un document EN : « {marker} »"
                )
            else:
                lang_issues.append(
                    f"Marqueur anglais détecté dans un document FR : « {marker} »"
                )

    # ── 7. Traces techniques résiduelles ────────────────────────────────────
    tech_traces: list[str] = []
    if not rewritten_empty:
        tech_traces = _find_technical_traces(rewritten_text)

    # ── 8. Calculer le statut ────────────────────────────────────────────────
    issues = {
        "rewritten_missing": rewritten_missing,
        "rewritten_empty": rewritten_empty,
        "ratio": ratio,
        "missing_headings": missing_headings,
        "forbidden_hits": forbidden_hits,
        "lang_issues": lang_issues,
        "tech_traces": tech_traces,
    }
    status = _compute_status(
        ratio=ratio,
        rewritten_empty=rewritten_empty,
        rewritten_missing=rewritten_missing,
        missing_headings=missing_headings,
        forbidden_hits=forbidden_hits,
        lang_issues=lang_issues,
        tech_traces=tech_traces,
    )
    recommendation = _build_recommendation(status, issues)

    notes: list[str] = []
    if rewritten_empty:
        notes.append("⚠️ manuscript_rewritten.md est vide.")

    # ── 9. Écrire le rapport ─────────────────────────────────────────────────
    _write_report(
        report_path,
        project_name,
        status=status,
        structured_len=structured_len,
        rewritten_len=rewritten_len,
        ratio=ratio,
        missing_headings=missing_headings,
        forbidden_hits=forbidden_hits,
        lang_issues=lang_issues,
        tech_traces=tech_traces,
        recommendation=recommendation,
        notes=notes,
    )

    # ── 10. Mettre à jour project_state.json ─────────────────────────────────
    _update_state(project_name, status, report_path)

    log_event({
        "step": "editorial_quality_guard",
        "project": project_name,
        "status": status,
        "ratio": round(ratio, 4) if ratio is not None else None,
        "missing_headings": len(missing_headings),
        "forbidden_hits": forbidden_hits,
        "lang_issues": lang_issues,
        "tech_traces": tech_traces,
    })

    print(f"[quality_guard] Statut : {status} — Rapport : {report_path}")
    return report_path


# ---------------------------------------------------------------------------
# Helpers d'écriture
# ---------------------------------------------------------------------------

def _write_fail_report(report_path: Path, project_name: str, reason: str) -> None:
    """Écrit un rapport FAIL minimal quand les fichiers source sont absents."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = (
        f"# Rapport qualité éditoriale\n\n"
        f"Projet : {project_name}  \n"
        f"Généré le : {now}\n\n"
        f"## Statut global\n\n"
        f"**FAIL**\n\n"
        f"## Raison\n\n"
        f"{reason}\n"
    )
    report_path.write_text(content, encoding="utf-8")


def _write_report(
    report_path: Path,
    project_name: str,
    *,
    status: str,
    structured_len: int | None,
    rewritten_len: int | None,
    ratio: float | None,
    missing_headings: list[str],
    forbidden_hits: list[str],
    lang_issues: list[str],
    tech_traces: list[str],
    recommendation: str,
    notes: list[str],
) -> None:
    """Écrit le rapport qualité markdown complet."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    status_emoji = {"PASS": "✅", "WARNING": "⚠️", "FAIL": "❌"}.get(status, "")

    lines: list[str] = [
        "# Rapport qualité éditoriale",
        "",
        f"Projet : {project_name}  ",
        f"Généré le : {now}",
        "",
        "## Statut global",
        "",
        f"**{status_emoji} {status}**",
        "",
    ]

    if notes:
        for note in notes:
            lines.append(f"> {note}")
        lines.append("")

    # Section longueur
    lines += ["## Longueur", ""]
    if structured_len is not None and rewritten_len is not None:
        lines.append(f"Texte structuré : {structured_len:,} caractères")
        lines.append(f"Texte réécrit   : {rewritten_len:,} caractères")
        if ratio is not None:
            ratio_pct = f"{ratio:.1%}"
            alert = ""
            if ratio < 0.60:
                alert = "  ⚠️ Possible résumé excessif (< 60 %)"
            elif ratio > 1.60:
                alert = "  ⚠️ Possible ajout excessif (> 160 %)"
            lines.append(f"Ratio           : {ratio_pct}{alert}")
    else:
        lines.append("_Données indisponibles (fichier absent ou vide)._")
    lines.append("")

    # Section titres manquants
    lines += ["## Titres manquants", ""]
    if missing_headings:
        for h in missing_headings:
            lines.append(f"- {h}")
    else:
        lines.append("_Aucun titre manquant._")
    lines.append("")

    # Section phrases interdites
    lines += ["## Phrases interdites détectées", ""]
    if forbidden_hits:
        for phrase in forbidden_hits:
            lines.append(f"- `{phrase}`")
    else:
        lines.append("_Aucune phrase interdite détectée._")
    lines.append("")

    # Section langue
    lines += ["## Problèmes de langue", ""]
    if lang_issues:
        for issue in lang_issues:
            lines.append(f"- {issue}")
    else:
        lines.append("_Aucun problème de langue détecté._")
    lines.append("")

    # Section traces techniques
    lines += ["## Traces techniques résiduelles", ""]
    if tech_traces:
        for trace in tech_traces:
            lines.append(f"- `{trace}`")
    else:
        lines.append("_Aucune trace technique résiduelle détectée._")
    lines.append("")

    # Recommandation
    lines += ["## Recommandation", "", recommendation, ""]

    report_path.write_text("\n".join(lines), encoding="utf-8")


def _update_state(project_name: str, status: str, report_path: Path) -> None:
    """Met à jour la section editorial de project_state.json."""
    state = load_project_state(project_name)
    state.setdefault("editorial", {}).update({
        "quality_checked": True,
        "quality_status": status,
        "quality_report_path": str(report_path),
        "quality_checked_at": datetime.now().isoformat(),
    })
    save_project_state(project_name, state)
