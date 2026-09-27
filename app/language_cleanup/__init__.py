"""
Phase 3A.1 — Audit linguistique et détection des traductions françaises.

CE PAQUET EST UN AUDIT, PAS UNE TRANSFORMATION.

Il lit sortie/<projet>/transcripts/transcript_data.json (Transcript V2, seule
source de vérité) et produit sortie/<projet>/audit/language_cleanup.json : un
manifeste de DÉCISIONS PROPOSÉES (KEEP / REMOVE_TRANSLATION / REVIEW) pour
chaque SRC. Rien n'est jamais supprimé, réécrit ou fusionné ici :

- transcript_data.json et transcript.txt ne sont jamais modifiés ;
- aucun SRC n'est renuméroté, créé ou fusionné ;
- aucun appel réseau, aucun LLM cloud, aucun modèle téléchargé.

La détection de langue et la mise en correspondance FR ↔ EN reposent
uniquement sur des heuristiques déterministes en Python pur (listes de mots
grammaticaux, diacritiques, un petit glossaire bilingue documenté, similarité
de chaînes via difflib de la bibliothèque standard). Voir language_detector.py
et translation_matcher.py pour le détail et les limites de la méthode.

Modules :

    models.py               contrat du manifeste (dataclasses, to_dict)
    transcript_source.py    lecture SEULE du Transcript V2 (jamais d'écriture)
    language_detector.py    classification EN / FR / MIXED / UNKNOWN par SRC
    blocks.py                groupement temporaire de SRC consécutifs compatibles
    translation_matcher.py  correspondance locale FR -> EN, fenêtre documentée
    auditor.py               orchestration : transcript -> manifeste
    validator.py             contrôle du manifeste publié
    writer.py                emplacement et publication atomique du manifeste

Ce paquet est volontairement indépendant de app/source_analysis : il ne
l'importe pas, et n'est importé par aucun pipeline automatique (ni main.py, ni
pipeline_runner.py). Il s'invoke explicitement, comme app/source_analysis.
"""

from __future__ import annotations

from app.language_cleanup.auditor import run_audit
from app.language_cleanup.models import AuditManifest

__all__ = ["run_audit", "AuditManifest"]
