"""
Seuils déterministes de la Phase 3A.1.1 — AUDITÉS sur le projet réel
pastoral_retreat_v2_validation avant d'être fixés ici (§8, §14 du cahier des
charges : « ne pas choisir arbitrairement une valeur sans regarder les
données »). Aucune de ces constantes n'est recalculée à l'exécution : elles
sont fixées ici, documentées, et appliquées identiquement à tout projet.

Toutes les mesures citées dans les docstrings ci-dessous portent sur
sortie/pastoral_retreat_v2_validation/{transcripts/transcript_data.json,
audit/language_cleanup.json} — 8415 SRC, 828 FR, calibrées le jour de
l'écriture de ce module. Elles ne sont pas recalculées automatiquement à
chaque exécution : c'est un CHOIX DE SEUIL FIXE, documenté et reproductible,
pas une heuristique adaptative par projet.

RAPPEL DE SÉCURITÉ (même principe que app/language_cleanup/auditor.py) :
chaque seuil ci-dessous est délibérément conservateur. Un bloc découpé « un
peu trop finement » n'est pas dangereux (§14 de ce cahier des charges : cette
phase ne décide rien, elle mesure) ; un bloc qui absorbe à tort un véritable
SRC anglais dans un pont FR serait, lui, un vrai problème structurel.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# §8 — Frontières temporelles : seuil de coupure d'un bloc FR sur un gap
# ---------------------------------------------------------------------------
#
# Distribution mesurée des gaps FR->FR STRICTEMENT ADJACENTS (deux SRC
# classifiés FR consécutifs dans la liste des segments, même AUDIO, sans rien
# entre eux) sur le corpus réel : n=480 paires.
#
#     median = 0.02 s   p90 = 1.34 s   p95 = 2.24 s   p99 = 4.08 s   max = 5.00 s
#
# Distribution de TOUS les gaps consécutifs même-AUDIO (toutes langues,
# n=8411), pour situer ce que serait une pause franchement anormale :
#
#     median = 0.04 s   p90 = 2.02 s   p95 = 2.82 s   p99 = 4.92 s
#     p99.9 = 9.14 s   max = 28.00 s
#
# FR_GAP_SPLIT_THRESHOLD_SECONDS = 6.0 s est choisi strictement au-dessus du
# maximum réellement observé entre deux SRC FR adjacents (5.0 s) : ce seuil ne
# fragmente donc AUCUNE intervention FR continue du corpus de calibration,
# tout en restant nettement sous la queue des pauses franchement anormales
# (> 7 s) visibles ailleurs dans le transcript. Un gap plus grand que ce seuil,
# à l'intérieur d'un run FR autrement continu, ferme le bloc courant et en
# ouvre un nouveau (§8 : « une pause importante peut signaler une nouvelle
# intervention »).
FR_GAP_SPLIT_THRESHOLD_SECONDS = 6.0

# ---------------------------------------------------------------------------
# §5-6 — Règle de bridge (petite interruption technique dans un bloc FR)
# ---------------------------------------------------------------------------
#
# 27 « runs pont » candidats identifiés sur le corpus réel : un ou plusieurs
# SRC classifiés UNKNOWN/MIXED strictement entre deux SRC classifiés FR, même
# AUDIO, sans aucun SRC EN entre les deux.
#
# Répartition par longueur de run : {1: 21, 2: 4, 3: 2}.
#
# BRIDGE_MAX_RUN_SEGMENTS = 1 : les runs de 2-3 SRC observés sont TOUJOURS de
# courts échanges ou suites de mots (« OK. » / « OK. », « papa God » / « papa
# Dieu » / « send him back », énumérations de type glossolalie) plutôt qu'une
# interjection isolée — absorber automatiquement plusieurs SRC reviendrait à
# absorber ce qui pourrait être un vrai échange distinct. Un seul SRC pont à la
# fois, jamais plus.
BRIDGE_MAX_RUN_SEGMENTS = 1

# BRIDGE_MAX_WORDS_PER_SEGMENT = 3 : parmi les 21 runs candidats d'un seul SRC,
# les textes de 1 à 3 mots sont systématiquement des interjections, réponses
# courtes ou fragments (« Wow. », « OK. », « Hein ? », « Amen. », « Non, non. »,
# « Go ahead. », « Exact hour. », « Treat them well. »...) ; à 4 mots et plus,
# on retrouve des propositions complètes dans une langue ou l'autre (« Il a
# voulu prier. », « God created everybody. », « Isaiah 28, verset 11. »,
# « yeah like every child »). La coupure à 3 mots suit exactement ce saut
# observé dans les données, pas un choix arbitraire.
BRIDGE_MAX_WORDS_PER_SEGMENT = 3

# BRIDGE_MAX_DURATION_SECONDS = 2.0 : les durées des runs d'un seul SRC
# retenus par les deux règles ci-dessus s'étalent de 0.16 s à 1.60 s. Un seul
# candidat texturellement éligible (« comment », 1 mot) atteint 2.58 s — une
# durée anormalement longue pour un seul mot, signe probable d'une hésitation
# ou d'un contenu plus substantiel qu'une simple marque de pont. Le seuil de
# 2.0 s conserve tous les candidats plausibles et exclut cet unique cas
# atypique.
BRIDGE_MAX_DURATION_SECONDS = 2.0

# Le gap total (fin du FR précédent -> début du FR suivant, à travers le pont)
# doit rester dans les mêmes bornes que la continuité FR->FR ordinaire : un
# pont textuellement court mais séparé par un silence anormalement long n'est
# pas structurellement local. Réutilise volontairement le même seuil que la
# coupure de bloc (§8) plutôt qu'un troisième chiffre inventé.
BRIDGE_MAX_TOTAL_GAP_SECONDS = FR_GAP_SPLIT_THRESHOLD_SECONDS

# ---------------------------------------------------------------------------
# §11 (repris) — Fenêtre de recherche du contexte anglais local
# ---------------------------------------------------------------------------
#
# Reprend explicitement le même principe que
# app.language_cleanup.translation_matcher.WINDOW_MAX_BLOCK_SKIP : au-delà
# d'un unique run non-anglais (UNKNOWN/MIXED, non absorbé comme bridge) qui ne
# sépare pas déjà deux blocs FR, on cesse de chercher — comparer un bloc FR à
# un contexte lointain produirait de faux voisinages (interdit par §14 du
# cahier des charges Phase 3A.1.1, comme par le §11 de Phase 3A.1).
CONTEXT_WINDOW_MAX_BLOCK_SKIP = 1

# ---------------------------------------------------------------------------
# §14 — Taille du contexte anglais local
# ---------------------------------------------------------------------------
#
# Distribution mesurée des runs anglais IMMÉDIATEMENT adjacents à un run FR
# (avant OU après, même AUDIO) sur le corpus réel : n=595 contextes.
#
#     segment_count : median=1   p90=3    p95=4-5   max=26-35
#     word_count     : median=6   p90=14-16 p95=23-26 max=145-199
#
# Avec les trois plafonds ci-dessous, seuls 6 des 595 contextes locaux
# (~1 %) dépassent au moins un plafond — la quasi-totalité du contexte
# anglais local est donc capturée EN ENTIER, et seule la queue rare d'un long
# monologue anglais est tronquée (en gardant la partie la plus proche du bloc
# FR, la plus pertinente pour une future comparaison BEFORE/AFTER).
MAX_CONTEXT_SEGMENTS = 20
MAX_CONTEXT_WORDS = 150
MAX_CONTEXT_SECONDS = 90.0
