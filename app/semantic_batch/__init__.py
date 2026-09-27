"""
Phase 3A.1.2B — Classification sémantique COMPLÈTE des 314 blocs FR NEEDED.

Ce paquet n'est branché nulle part automatiquement : ni main.py, ni
pipeline_runner.py, ni le Source Analyzer ne l'importent. C'est un
traitement de diagnostic autonome, invoqué explicitement via
`python -m app.semantic_batch.cli <projet>`.

Cette phase CLASSIFIE uniquement. Elle NE SUPPRIME RIEN et NE PRODUIT PAS
de transcript nettoyé. Elle ne modifie jamais :

    transcripts/transcript_data.json
    audit/language_cleanup.json
    audit/language_blocks.json
    audit/semantic_translation_canary.json   (Phase 3A.1.2A — expérience séparée)

Elle réutilise directement l'infrastructure de app.semantic_canary (prompt,
schéma, payload sanitisé, validateur, préflight, garde-fou d'appel réel,
vocabulaire fermé) plutôt que de la dupliquer (§10 du cahier des charges) :
seule la population traitée change (tous les blocs NEEDED, par lots de 20,
avec reprise/cache), pas la règle métier.

Artefacts produits :

    audit/semantic_batches/BATCH001.json, BATCH002.json, ...  (checkpoints)
    audit/semantic_translation_classification.json            (artefact final)
"""

from __future__ import annotations
