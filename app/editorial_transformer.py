"""
Editorial Transformer — Transforme le manuscrit structuré en langage écrit
fidèle à l'original.

PRINCIPE FONDAMENTAL : fidélité, pas réécriture créative.

Ce module ne :
  - résume pas
  - n'invente pas d'idées
  - n'ajoute pas de doctrines ou d'arguments
  - ne modifie pas le sens
  - ne simplifie pas à l'excès
  - ne supprime pas d'éléments importants

Il transforme uniquement la syntaxe orale en syntaxe écrite lisible.

Pipeline :
  sortie/<project>/final/manuscript_structured.md
  ↓ [section par section via Ollama]
  ↓
  sortie/<project>/final/manuscript_rewritten.md
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from app.ai_engine import get_ai_engine
from app.document_language import get_document_language
from app.logger import log_event
from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state


# ---------------------------------------------------------------------------
# Prompts stricts de transformation éditoriale
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_EN = """\
You are an editorial transformer.

Your mission is NOT to summarize.

Your mission is NOT to create new content.

Your mission is NOT to explain the author.

Your mission is NOT to analyze the content.

Your mission is to transform spoken language into clean written language.

Rules:

- Keep all original ideas.
- Keep all original arguments.
- Keep all theological concepts.
- Keep all examples.
- Keep the author's voice.
- Preserve first-person language whenever present.
- Do not use phrases such as:
  "the speaker explains"
  "the author says"
  "the speaker teaches"
- Do not add interpretations.
- Do not add conclusions.
- Do not remove important information.
- Rewrite only for readability.
- Output only the transformed text.
- Output only in English."""

_SYSTEM_PROMPT_FR = """\
Tu es un transformateur éditorial.

Tu ne dois pas résumer.

Tu ne dois pas créer de contenu.

Tu ne dois pas expliquer l'auteur.

Tu ne dois pas analyser le contenu.

Tu dois uniquement transformer un langage oral en langage écrit.

Règles :

- conserver toutes les idées originales
- conserver tous les arguments
- conserver les concepts théologiques
- conserver les exemples
- conserver la voix de l'auteur
- conserver la première personne lorsqu'elle est présente
- ne jamais écrire :
  "l'auteur dit"
  "le conférencier explique"
  "l'orateur affirme"
- ne jamais ajouter d'interprétation
- ne jamais ajouter de conclusion
- ne jamais supprimer une information importante
- améliorer uniquement la lisibilité
- produire uniquement le texte transformé
- produire uniquement en français"""


# ---------------------------------------------------------------------------
# Table des matières : labels connus
# ---------------------------------------------------------------------------

_TOC_LABELS: frozenset[str] = frozenset({
    "table of contents",
    "table des matières",
    "table des matieres",
    "sommaire",
    "contents",
    "toc",
})


# ---------------------------------------------------------------------------
# Fonction publique : transformer une section
# ---------------------------------------------------------------------------

def transform_section(text: str, language: str) -> str:
    """
    Transforme le contenu textuel d'une section du langage oral au langage écrit.

    Args:
        text:     Corps de la section (sans le titre Markdown).
        language: Langue documentaire — "en" ou "fr".

    Returns:
        Texte transformé. En cas de réponse vide du moteur IA, retourne
        le texte original non modifié.
    """
    if not text.strip():
        return text

    system_prompt = _SYSTEM_PROMPT_FR if language == "fr" else _SYSTEM_PROMPT_EN

    if language == "fr":
        full_prompt = (
            f"{system_prompt}\n\n"
            "---\n\n"
            "Texte à transformer :\n\n"
            f"{text}"
        )
    else:
        full_prompt = (
            f"{system_prompt}\n\n"
            "---\n\n"
            "Text to transform:\n\n"
            f"{text}"
        )

    engine = get_ai_engine()
    result = engine.send_prompt(full_prompt)
    transformed = result.strip() if result else ""

    if not transformed:
        print("[editorial_transformer] Avertissement : réponse vide — texte original conservé")
        return text

    return transformed


# ---------------------------------------------------------------------------
# Parsing interne de manuscript_structured.md
# ---------------------------------------------------------------------------

def _is_toc_heading(heading: str) -> bool:
    """Retourne True si le heading correspond à une table des matières."""
    normalized = re.sub(r"^#+\s*", "", heading).strip().lower()
    return normalized in _TOC_LABELS


def _parse_manuscript_blocks(content: str) -> list[tuple[str, str]]:
    """
    Découpe le contenu de manuscript_structured.md en blocs (heading, body).

    Séparateur : ``\\n---\\n`` (tel que produit par render_structured_manuscript).

    Retourne une liste de tuples :
      - heading : ligne `# Titre` ou `## Titre` (peut être vide si bloc sans titre)
      - body    : contenu du bloc, titre exclu
    """
    raw_blocks = re.split(r"\n---\n", content)
    parsed: list[tuple[str, str]] = []

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.splitlines()
        heading = ""
        body_start = 0

        for i, line in enumerate(lines):
            if re.match(r"^#{1,3}\s+", line.strip()):
                heading = line.strip()
                body_start = i + 1
                break

        body_lines = lines[body_start:]
        body = "\n".join(body_lines).strip()
        parsed.append((heading, body))

    return parsed


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def transform_editorial_manuscript(project_name: str) -> Path | None:
    """
    Transforme ``manuscript_structured.md`` en ``manuscript_rewritten.md``.

    Traitement section par section :
      - Titre principal       → conservé sans transformation
      - Table des matières    → conservée sans transformation
      - Introduction          → transformée
      - Chapitre / Section    → transformé(e)
      - Conclusion            → transformée

    Met à jour ``project_state.json`` :
      ``state["editorial"]["rewritten"]``        = True
      ``state["editorial"]["rewritten_path"]``   = chemin absolu
      ``state["editorial"]["document_language"]``= "en" ou "fr"
      ``state["editorial"]["generated_at"]``     = horodatage ISO

    Returns:
        Chemin de ``manuscript_rewritten.md``, ou ``None`` en cas d'erreur.
    """
    print(f"[editorial_transformer] Début — projet : {project_name}")
    log_event({
        "step": "editorial_transformer",
        "project": project_name,
        "action": "start",
        "message": f"Début transformation éditoriale pour {project_name}",
    })

    state = load_project_state(project_name)
    now_iso = datetime.now().isoformat(timespec="seconds")

    try:
        # ── Étape 1 : Localiser le fichier source ─────────────────────────────
        final_dir = SORTIE_DIR / project_name / "final"
        input_path = final_dir / "manuscript_structured.md"

        if not input_path.exists():
            msg = (
                f"manuscript_structured.md introuvable dans {final_dir}. "
                "Lancez d'abord la génération du manuscrit structuré "
                "(bouton « Générer le document éditorial final »)."
            )
            print(f"[editorial_transformer] ERREUR : {msg}")
            log_event({
                "step": "editorial_transformer",
                "project": project_name,
                "action": "error",
                "message": msg,
            })
            state["editorial"].update({
                "rewritten": False,
                "rewritten_error": msg,
                "generated_at": now_iso,
            })
            save_project_state(project_name, state)
            return None

        content = input_path.read_text(encoding="utf-8")
        print(
            f"[editorial_transformer] Fichier source : {input_path} "
            f"({len(content)} caractères)"
        )

        # ── Étape 2 : Langue documentaire ────────────────────────────────────
        document_language = get_document_language(project_name)
        print(f"[editorial_transformer] Langue documentaire : {document_language}")
        log_event({
            "step": "editorial_transformer",
            "project": project_name,
            "action": "language",
            "document_language": document_language,
        })

        # ── Étape 3 : Parser les blocs ────────────────────────────────────────
        blocks = _parse_manuscript_blocks(content)
        print(f"[editorial_transformer] Blocs détectés : {len(blocks)}")

        # ── Étape 4 : Transformer bloc par bloc ───────────────────────────────
        output_parts: list[str] = []
        sections_transformed = 0
        sections_preserved = 0

        for idx, (heading, body) in enumerate(blocks):
            is_toc = _is_toc_heading(heading)

            # Le premier bloc non-TOC qui est un H1 = titre principal du document
            is_main_title = (
                idx == 0
                and heading.startswith("# ")
                and not is_toc
            )

            if is_main_title or is_toc:
                # Conserver sans transformation
                reassembled = heading
                if body:
                    reassembled += "\n\n" + body
                output_parts.append(reassembled)
                sections_preserved += 1
                label = "titre principal" if is_main_title else "table des matières"
                print(
                    f"[editorial_transformer] Bloc {idx + 1}/{len(blocks)} "
                    f"— {label} (conservé)"
                )
                continue

            # Section à transformer
            section_label = re.sub(r"^#+\s*", "", heading).strip() if heading else f"Bloc {idx + 1}"
            char_count = len(body)
            print(
                f"[editorial_transformer] Bloc {idx + 1}/{len(blocks)} "
                f"— « {section_label} » ({char_count} chars) → transformation..."
            )
            log_event({
                "step": "editorial_transformer",
                "project": project_name,
                "action": "transform_section",
                "section": section_label,
                "index": idx + 1,
                "total": len(blocks),
                "chars": char_count,
            })

            transformed_body = transform_section(body, document_language)
            sections_transformed += 1

            reassembled = heading + "\n\n" + transformed_body if heading else transformed_body
            output_parts.append(reassembled)
            print(
                f"[editorial_transformer] « {section_label} » transformée "
                f"({len(transformed_body)} chars)"
            )

        # ── Étape 5 : Assembler et écrire ─────────────────────────────────────
        rewritten_content = "\n\n---\n\n".join(output_parts)
        output_path = final_dir / "manuscript_rewritten.md"
        final_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rewritten_content, encoding="utf-8")

        print(f"[editorial_transformer] Fichier généré : {output_path}")
        log_event({
            "step": "editorial_transformer",
            "project": project_name,
            "action": "success",
            "message": f"Manuscrit transformé généré : {output_path}",
            "sections_transformed": sections_transformed,
            "sections_preserved": sections_preserved,
            "document_language": document_language,
        })

        # ── Étape 6 : Mettre à jour project_state.json ────────────────────────
        state["editorial"].update({
            "rewritten": True,
            "rewritten_path": str(output_path),
            "document_language": document_language,
            "generated_at": now_iso,
        })
        save_project_state(project_name, state)

        return output_path

    except Exception as exc:
        err_msg = str(exc)
        print(f"[editorial_transformer] ERREUR inattendue : {err_msg}")
        log_event({
            "step": "editorial_transformer",
            "project": project_name,
            "action": "error",
            "message": err_msg,
        })
        state["editorial"].update({
            "rewritten": False,
            "rewritten_error": err_msg,
            "generated_at": now_iso,
        })
        save_project_state(project_name, state)
        return None
