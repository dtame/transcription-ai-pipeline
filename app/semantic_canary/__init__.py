"""
Phase 3A.1.2A — Canary réel de classification sémantique FR <-> EN.

Ce paquet n'est branché nulle part automatiquement : ni main.py, ni
pipeline_runner.py, ni le Source Analyzer ne l'importent. C'est un
DIAGNOSTIC autonome, invoqué explicitement via `python -m
app.semantic_canary.cli <projet>`.

Un canary complet ne doit produire qu'UN SEUL appel réseau réel vers
Anthropic (voir app/semantic_canary/guard.py). Il ne modifie jamais :

    transcripts/transcript_data.json
    audit/language_cleanup.json
    audit/language_blocks.json

Il ne produit qu'un artefact de diagnostic :

    audit/semantic_translation_canary.json
"""

from __future__ import annotations
