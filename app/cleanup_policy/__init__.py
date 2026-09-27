"""
Phase 3A.2A — Simulation déterministe des politiques de nettoyage
linguistique.

Ce paquet ne fait QUE simuler. Il ne supprime rien, ne modifie aucune des
cinq sources protégées, n'appelle aucun service réseau (aucun import d'un
module `app.ai.*`, ni de `app.semantic_canary.runner` /
`app.semantic_batch.runner` — seule la lecture des artefacts déjà publiés
et leur hashing SHA-256 sont effectués).

Séparation stricte (cahier des charges §2) :

    CLASSIFICATION SÉMANTIQUE   déjà produite par la Phase 3A.1.2B
                                (semantic_translation_classification.json),
                                jamais recalculée ici.

    DÉCISION D'APPLICATION      couche ajoutée par ce paquet : transforme une
                                classification existante en
                                AUTO_REMOVE / HUMAN_REVIEW / KEEP, pour
                                trois politiques hypothétiques (A, B, C),
                                UNIQUEMENT en simulation.
"""
