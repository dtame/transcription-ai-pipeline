"""
Phase 3A.2B — Application déterministe de POLICY_B+ et génération d'une
vue nettoyée du transcript.

Ce paquet APPLIQUE une suppression réelle dans une NOUVELLE VUE :

    transcripts/clean/transcript_data.json
    transcripts/clean/transcript.txt
    audit/cleanup_application.json

Il ne modifie JAMAIS le transcript original, ne recalcule aucune
classification sémantique, et n'appelle aucun service réseau.

Séparation stricte :

    CLASSIFICATION SÉMANTIQUE   déjà produite (Phase 3A.1.2B)
    SIMULATION DES POLITIQUES   déjà produite (Phase 3A.2A)
    APPLICATION RÉELLE          ce paquet : POLICY_B_PLUS_V1 uniquement,
                                plus prudente que POLICY_B simulée.
"""
