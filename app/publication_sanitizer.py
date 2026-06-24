"""
Publication Sanitizer — Couche finale de sécurité avant génération DOCX / PDF / ZIP.

Garantit que les livrables clients ne contiennent jamais :
  - commentaires HTML internes  (<!-- ... -->)
  - placeholders techniques     (TODO, TBD, FIXME, …)
  - sections vides              (titre sans contenu)
  - artefacts IA connus         ("Let me know if", "En tant qu'IA", …)
  - traces techniques           (chunk_, processed/, …)
  - séparateurs techniques      (===, ---, ───…)
  - lignes vides excessives     (> 1 ligne vide consécutive)
  - espaces parasites           (trailing spaces, espaces multiples)

Entrée  : sortie/<project_name>/publication/publication.md
Sortie  : sortie/<project_name>/publication/publication_sanitized.md
Rapport : sortie/<project_name>/publication/publication_sanitizer_report.md
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from app.logger import log_event
from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state


# ─────────────────────────────────────────────────────────────────────────────
# Patterns de nettoyage
# ─────────────────────────────────────────────────────────────────────────────

# 1. Commentaires HTML Markdown  <!-- ... -->
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# 2. Placeholders techniques (ligne entière)
_PLACEHOLDER_LINE_RE = re.compile(
    r"^\s*(TODO|TBD|FIXME|PLACEHOLDER|À compléter|To be completed|WIP)\s*$",
    re.IGNORECASE,
)

# 4. Artefacts IA (lignes contenant ces phrases — anglais + français)
_AI_ARTIFACT_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"Let me know if",
        r"This summary preserves",
        r"This structured summary",
        r"Possible interpretations",
        r"Possible contexts",
        r"Questions for further exploration",
        r"Questions for further clarity",
        r"As an AI",
        r"Faites-moi savoir si",
        r"Ce résumé préserve",
        r"Interprétations possibles",
        r"Contextes possibles",
        r"Questions pour approfondir",
        r"En tant qu'IA",
        r"En tant qu'assistant",
    ]
]

# 5. Traces techniques (lignes contenant ces fragments)
_TECH_TRACE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bchunk_\d+",
        r"\bprocessed/",
        r"\bcorrections/",
        r"\bDocument final\b",
        r"\bNombre de chunks\b",
        r"\bChunks avec corrections\b",
    ]
]

# 6. Séparateurs techniques excessifs (ligne entière)
_TECH_SEPARATOR_RE = re.compile(
    r"^\s*[=\-─━]{6,}\s*$"
)

# Titres Markdown (#, ##, ###)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


# ─────────────────────────────────────────────────────────────────────────────
# Nettoyage du texte
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_publication_content(
    text: str,
    document_language: str = "en",
) -> tuple[str, dict[str, int]]:
    """
    Nettoie le contenu destiné aux livrables finaux.

    Retourne (texte_nettoyé, compteurs) où compteurs est un dict avec le
    nombre d'éléments supprimés par catégorie.
    """
    counters: dict[str, int] = {
        "html_comments":     0,
        "placeholders":      0,
        "empty_sections":    0,
        "ai_artifacts":      0,
        "technical_traces":  0,
        "separators":        0,
        "blank_lines":       0,
    }

    # ── 1. Supprimer les commentaires HTML ────────────────────────────────────
    def _count_html(m: re.Match) -> str:
        counters["html_comments"] += 1
        return ""

    text = _HTML_COMMENT_RE.sub(_count_html, text)

    # ── Découpage en lignes pour les traitements suivants ─────────────────────
    lines = text.splitlines()
    cleaned: list[str] = []

    for line in lines:
        # ── 2. Placeholders techniques ─────────────────────────────────────
        if _PLACEHOLDER_LINE_RE.match(line):
            counters["placeholders"] += 1
            continue

        # ── 4. Artefacts IA ────────────────────────────────────────────────
        if any(p.search(line) for p in _AI_ARTIFACT_PATTERNS):
            counters["ai_artifacts"] += 1
            continue

        # ── 5. Traces techniques ───────────────────────────────────────────
        if any(p.search(line) for p in _TECH_TRACE_PATTERNS):
            counters["technical_traces"] += 1
            continue

        # ── 6. Séparateurs techniques ──────────────────────────────────────
        if _TECH_SEPARATOR_RE.match(line):
            counters["separators"] += 1
            continue

        # ── 8. Normaliser les espaces (trailing + multiples internes) ──────
        line = line.rstrip()
        # Éviter de toucher aux lignes de code (indentées)
        if not line.startswith("    ") and not line.startswith("\t"):
            line = re.sub(r"  +", " ", line)

        cleaned.append(line)

    # ── 3. Supprimer les sections vides ───────────────────────────────────────
    # Un titre est "vide" si tout ce qui le suit jusqu'au prochain titre (ou
    # fin de document) est constitué uniquement de lignes vides.
    cleaned = _remove_empty_sections(cleaned, counters)

    # ── 7. Supprimer les lignes vides multiples ────────────────────────────────
    cleaned, extra_blanks = _collapse_blank_lines(cleaned)
    counters["blank_lines"] = extra_blanks

    return "\n".join(cleaned) + "\n", counters


def _remove_empty_sections(lines: list[str], counters: dict[str, int]) -> list[str]:
    """
    Parcourt les lignes et supprime tout titre dont le contenu jusqu'au
    prochain titre (ou fin) est entièrement vide.
    """
    result: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        m = _HEADING_RE.match(lines[i])
        if not m:
            result.append(lines[i])
            i += 1
            continue

        # Chercher jusqu'au prochain titre
        j = i + 1
        body: list[str] = []
        while j < n and not _HEADING_RE.match(lines[j]):
            body.append(lines[j])
            j += 1

        # Le corps est-il vide (seulement des lignes blanches) ?
        if all(ln.strip() == "" for ln in body):
            counters["empty_sections"] += 1
            # Sauter ce titre et son corps vide
            i = j
        else:
            result.append(lines[i])
            result.extend(body)
            i = j

    return result


def _collapse_blank_lines(lines: list[str]) -> tuple[list[str], int]:
    """Remplace les suites de plus d'une ligne vide par une seule."""
    result: list[str] = []
    blank_count = 0
    removed = 0
    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 1:
                result.append(line)
            else:
                removed += 1
        else:
            blank_count = 0
            result.append(line)
    return result, removed


# ─────────────────────────────────────────────────────────────────────────────
# Traitement de fichier
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_publication_file(
    source_path: Path,
    output_path: Path,
    document_language: str,
) -> tuple[Path, dict[str, int]]:
    """
    Lit source_path, nettoie le contenu, écrit le résultat dans output_path.

    Retourne (output_path, compteurs).
    Lève FileNotFoundError si source_path n'existe pas.
    """
    if not source_path.exists():
        raise FileNotFoundError(f"Source introuvable : {source_path}")

    text = source_path.read_text(encoding="utf-8")
    sanitized, counters = sanitize_publication_content(text, document_language)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(sanitized, encoding="utf-8")

    return output_path, counters


# ─────────────────────────────────────────────────────────────────────────────
# Rapport de nettoyage
# ─────────────────────────────────────────────────────────────────────────────

def _write_sanitizer_report(
    report_path: Path,
    project_name: str,
    counters: dict[str, int],
    now: str,
) -> None:
    total = sum(counters.values())
    lines = [
        "# Publication Sanitizer Report",
        "",
        f"Project : {project_name}",
        "",
        f"Removed HTML comments    : {counters['html_comments']}",
        f"Removed placeholders     : {counters['placeholders']}",
        f"Removed empty sections   : {counters['empty_sections']}",
        f"Removed AI artifacts     : {counters['ai_artifacts']}",
        f"Removed technical traces : {counters['technical_traces']}",
        f"Removed separators       : {counters['separators']}",
        f"Collapsed blank lines    : {counters['blank_lines']}",
        f"Total items removed      : {total}",
        "",
        f"Generated at : {now}",
        "",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée principal
# ─────────────────────────────────────────────────────────────────────────────

def generate_sanitized_publication(project_name: str) -> Path | None:
    """
    Génère publication_sanitized.md et publication_sanitizer_report.md.

    Entrée  : sortie/<project_name>/publication/publication.md
    Sortie  : sortie/<project_name>/publication/publication_sanitized.md
    Rapport : sortie/<project_name>/publication/publication_sanitizer_report.md

    Met à jour project_state.json["publication_sanitizer"].
    Retourne le chemin de publication_sanitized.md, ou None en cas d'erreur.
    """
    pub_dir     = SORTIE_DIR / project_name / "publication"
    source_path = pub_dir / "publication.md"
    output_path = pub_dir / "publication_sanitized.md"
    report_path = pub_dir / "publication_sanitizer_report.md"
    now         = datetime.now().isoformat(timespec="seconds")

    print(f"[publication_sanitizer] Publication Sanitizer started — projet : {project_name}")
    log_event({
        "step":    "publication_sanitizer",
        "project": project_name,
        "action":  "start",
    })

    # ── Vérification source ───────────────────────────────────────────────────
    if not source_path.exists():
        msg = f"publication.md introuvable : {source_path}"
        print(f"[publication_sanitizer] ERREUR : {msg}")
        log_event({"step": "publication_sanitizer", "project": project_name, "action": "error", "error": msg})
        _save_sanitizer_state(project_name, generated=False, error=msg, now=now)
        return None

    # ── Langue documentaire ───────────────────────────────────────────────────
    try:
        from app.document_language import get_document_language
        lang = get_document_language(project_name)
    except Exception:
        lang = "en"

    # ── Nettoyage ─────────────────────────────────────────────────────────────
    try:
        _, counters = sanitize_publication_file(source_path, output_path, lang)
    except Exception as exc:
        msg = str(exc)
        print(f"[publication_sanitizer] ERREUR nettoyage : {msg}")
        log_event({"step": "publication_sanitizer", "project": project_name, "action": "error", "error": msg})
        _save_sanitizer_state(project_name, generated=False, error=msg, now=now)
        return None

    # ── Logs par catégorie ────────────────────────────────────────────────────
    print(f"[publication_sanitizer] Removed HTML comments    : {counters['html_comments']}")
    print(f"[publication_sanitizer] Removed placeholders     : {counters['placeholders']}")
    print(f"[publication_sanitizer] Removed empty sections   : {counters['empty_sections']}")
    print(f"[publication_sanitizer] Removed AI artifacts     : {counters['ai_artifacts']}")
    print(f"[publication_sanitizer] Removed technical traces : {counters['technical_traces']}")
    print(f"[publication_sanitizer] Removed separators       : {counters['separators']}")
    print(f"[publication_sanitizer] Collapsed blank lines    : {counters['blank_lines']}")
    log_event({
        "step":    "publication_sanitizer",
        "project": project_name,
        "action":  "counters",
        **counters,
    })

    # ── Rapport ───────────────────────────────────────────────────────────────
    try:
        _write_sanitizer_report(report_path, project_name, counters, now)
        print(f"[publication_sanitizer] Rapport généré : {report_path}")
    except Exception as exc:
        print(f"[publication_sanitizer] AVERTISSEMENT rapport : {exc}")

    print(f"[publication_sanitizer] Sanitized publication generated : {output_path}")
    log_event({
        "step":    "publication_sanitizer",
        "project": project_name,
        "action":  "generated",
        "path":    str(output_path),
    })

    _save_sanitizer_state(
        project_name,
        generated=True,
        path=str(output_path),
        report_path=str(report_path),
        now=now,
    )
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# Mise à jour project_state.json
# ─────────────────────────────────────────────────────────────────────────────

def _save_sanitizer_state(
    project_name: str,
    *,
    generated: bool,
    now: str,
    path: str | None = None,
    report_path: str | None = None,
    error: str | None = None,
) -> None:
    state = load_project_state(project_name)
    state.setdefault("publication", {})

    entry: dict = {"generated": generated, "generated_at": now}
    if generated and path:
        entry["path"] = path
    if generated and report_path:
        entry["report_path"] = report_path
    if not generated and error:
        entry["error"] = error

    state["publication"]["publication_sanitizer"] = entry
    save_project_state(project_name, state)
    print("[publication_sanitizer] project_state.json mis à jour.")
