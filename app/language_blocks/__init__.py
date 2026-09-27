"""
Phase 3A.1.1 — Analyse structurelle des blocs français et de leur contexte anglais.

CE PAQUET EST UNE ANALYSE STRUCTURELLE, PAS UNE DÉCISION SÉMANTIQUE.

Il lit :

    sortie/<projet>/transcripts/transcript_data.json   (Transcript V2, source de vérité)
    sortie/<projet>/audit/language_cleanup.json         (manifeste Phase 3A.1)

et produit :

    sortie/<projet>/audit/language_blocks.json

Ce manifeste regroupe les SRC classifiés FR consécutifs en « blocs » (une
intervention française continue), identifie leur contexte anglais local avant
et après, et mesure la taille du problème avant toute classification
sémantique future. Il ne modifie ni ne supprime rien :

- transcript_data.json et language_cleanup.json ne sont jamais réécrits ;
- aucune décision Phase 3A.1 (KEEP / REMOVE_TRANSLATION / REVIEW) n'est
  changée, promue ou rétrogradée ;
- aucun appel réseau, aucun LLM, aucun embedding, aucune traduction
  automatique, aucun nouveau score de similarité FR↔EN.

Modules :

    constants.py        seuils déterministes, audités sur les données réelles
    models.py            contrat du manifeste (dataclasses, to_dict)
    combined_source.py   lecture SEULE et fusion transcript + manifeste 3A.1
    runs.py               regroupement en « runs » de même langue, par AUDIO
    bridging.py           fusion des runs FR à travers de petits ponts
    context.py            recherche du contexte anglais local avant/après
    classifier.py         structure, direction candidate, revue sémantique
    estimation.py         estimation hors-ligne de la charge IA future
    builder.py             orchestration complète : sources -> manifeste
    validator.py           contrôle du manifeste publié
    writer.py               emplacement et publication atomique
    cli.py                   invocation manuelle

Ce paquet est indépendant de app/source_analysis. Il DÉPEND explicitement de
app/language_cleanup (lecture de son manifeste et réutilisation de son lecteur
de transcript en lecture seule) : Phase 3A.1.1 est une analyse structurelle
BÂTIE SUR le résultat de Phase 3A.1, pas un audit indépendant qui devrait tout
recalculer. Il n'est branché nulle part automatiquement (ni main.py, ni
pipeline_runner.py) : il s'invoque explicitement, comme app/language_cleanup.
"""

from __future__ import annotations

from app.language_blocks.builder import run_block_analysis
from app.language_blocks.models import LanguageBlocksManifest

__all__ = ["run_block_analysis", "LanguageBlocksManifest"]
