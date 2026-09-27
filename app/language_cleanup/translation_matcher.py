"""
Correspondance locale FR -> EN — recherche d'une relation de traduction.

STATUT : MATCHER_LIMITED (voir §13 du cahier des charges).

Aucun modèle d'embeddings multilingues local n'est disponible dans ce projet
(vérifié : requirements.txt et l'environnement virtuel ne contiennent ni
sentence-transformers, ni fasttext, ni aucune bibliothèque de similarité
sémantique — seul `numpy` est présent, sans modèle chargé dessus). Plutôt que
d'inventer une pseudo-sémantique ou de télécharger un modèle (interdit par
§7/§13), la correspondance combine trois signaux lexicaux DÉTERMINISTES et
strictement locaux (bibliothèque standard uniquement — `difflib`) :

1. JETONS PARTAGÉS À L'IDENTIQUE (après normalisation : minuscules, accents
   retirés, ponctuation retirée) : capture les nombres, emprunts lexicaux et
   noms propres orthographiés à l'identique dans les deux langues
   (« Bible », « Jésus/Jesus » une fois les accents retirés, « important »…).

2. GLOSSAIRE BILINGUE RESTREINT ET DOCUMENTÉ (FR_EN_GLOSSARY ci-dessous) :
   quelques dizaines de paires de mots grammaticaux/théologiques à très haute
   fréquence dans ce type de contenu (dieu/god, seigneur/lord, comprendre/
   understand, donner/give...) qui n'ont pas de racine commune détectable par
   similarité de chaîne. Liste FERMÉE, câblée en dur, jamais devinée à
   l'exécution : c'est une heuristique transparente et auditable, pas un
   dictionnaire de traduction généraliste.

3. SIMILARITÉ DE CHAÎNE (cognats latins partagés : autorité/authority,
   ministère/ministry...) via `difflib.SequenceMatcher`, seuil documenté
   COGNATE_RATIO_THRESHOLD.

LIMITES DOCUMENTÉES (à reporter telles quelles dans le rapport final) :

- cette méthode NE DÉTECTE PAS une paraphrase libre sans recouvrement lexical
  (ex. « Il faut faire confiance à Dieu » / « Trust him completely » ne
  partagent aucun jeton exploitable ici) ;
- le glossaire est volontairement restreint : il ne couvre pas tout le
  vocabulaire théologique possible, seulement les mots les plus fréquents
  identifiés lors de la calibration ;
- un score élevé reste un INDICE, jamais une preuve sémantique ; c'est
  pourquoi le seuil de REMOVE_TRANSLATION est délibérément conservateur et
  qu'une bande REVIEW existe entre « aucune relation » et « relation
  suffisamment claire pour proposer une suppression ».
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass

from app.language_cleanup.blocks import Block
from app.language_cleanup.models import (
    LANGUAGE_EN,
    LANGUAGE_FR,
    MATCH_AFTER,
    MATCH_BEFORE,
)

# ---------------------------------------------------------------------------
# Fenêtre de recherche (§11 du cahier des charges) — DOCUMENTÉE EXPLICITEMENT
# ---------------------------------------------------------------------------
#
# Priorité 1 : le bloc immédiatement adjacent (avant, puis après).
# Priorité 2 (fenêtre locale supplémentaire) : si le bloc immédiatement
# adjacent n'est PAS anglais (il est MIXED ou UNKNOWN — jamais FR, puisque les
# blocs sont des runs d'une seule langue), on regarde un bloc de plus dans la
# même direction. Au-delà, la recherche s'arrête : comparer un passage français
# à l'ensemble du transcript produirait de fausses correspondances sur des
# thèmes récurrents (interdit explicitement par §11).
WINDOW_MAX_BLOCK_SKIP = 1


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _tokenize(text: str) -> list[str]:
    normalized = _strip_accents(text.lower())
    return _TOKEN_RE.findall(normalized)


# Mots vides retirés avant comparaison : grammaticaux, non porteurs de sens
# comparable. Union volontairement large des deux langues (voir
# language_detector.py pour la liste utilisée à la classification — reprise
# ici sous forme normalisée, accents retirés).
_STOPWORDS_FR = frozenset(
    """
    le la les l un une des du de et est sont dans pour que qui quoi avec nous
    vous ils elles etre etait etaient avoir sur pas ne plus mais ou bien donc
    car ni si se sa son ses leur leurs notre votre nos vos je tu il elle on y
    en au aux comme quand alors aussi tres tout tous toute toutes rien aucun
    aucune personne ainsi ceci cela celui celle ceux celles qu d j m t c n
    moi toi lui eux apres avant entre chez sans sous vers deja encore meme
    memes etes suis sommes a
    """.split()
)

_STOPWORDS_EN = frozenset(
    """
    the a an and is are in for that who whom with we you they be been being
    have has had on not but where so because her his their our your my i he
    she it as when very all nothing also then this these those what no do
    does did will would should can could of to from by at yes there here
    was were am if or nor into onto than about above below under over
    """.split()
)

# ---------------------------------------------------------------------------
# Glossaire bilingue restreint (§13) — fermé, documenté, câblé en dur.
#
# Chaque entrée : forme française normalisée (accents retirés) -> ensemble de
# racines anglaises attendues. Le côté anglais est vérifié par préfixe
# (`token.startswith(stem)`) pour absorber les formes fléchies les plus
# courantes (want/wants/wanted -> stem "want") sans stemmer complet.
# ---------------------------------------------------------------------------

FR_EN_GLOSSARY: dict[str, tuple[str, ...]] = {
    "dieu": ("god",),
    "seigneur": ("lord",),
    "verite": ("truth", "true"),
    "amour": ("love",),
    "aimer": ("love",),
    "puissance": ("power",),
    "comprendre": ("understand",),
    "comprenez": ("understand",),
    "compreniez": ("understand",),
    "comprend": ("understand",),
    "donne": ("give", "given"),
    "donner": ("give", "given"),
    "donnee": ("given",),
    "vouloir": ("want",),
    "veut": ("want", "wants"),
    "veulent": ("want", "wants"),
    "voulez": ("want",),
    "coeur": ("heart",),
    "ame": ("soul",),
    "pardon": ("forgiv",),
    "pardonner": ("forgiv",),
    "peche": ("sin",),
    "pecheur": ("sinner",),
    "sauver": ("save", "saved"),
    "sauveur": ("savior", "saviour"),
    "salut": ("salvation",),
    "croire": ("believ",),
    "croyez": ("believ",),
    "pere": ("father",),
    "fils": ("son",),
    "eglise": ("church",),
    "roi": ("king",),
    "royaume": ("kingdom",),
    "terre": ("earth",),
    "ciel": ("heaven", "sky"),
    "vie": ("life",),
    "mort": ("death", "dead"),
    "jour": ("day",),
    "nuit": ("night",),
    "homme": ("man",),
    "femme": ("woman",),
    "enfant": ("child",),
    "enfants": ("children",),
    "peuple": ("people",),
    "parole": ("word",),
    "ecouter": ("listen",),
    "parler": ("speak",),
    "dire": ("say", "said"),
    "savoir": ("know",),
    "voir": ("see",),
    "temps": ("time",),
    "chemin": ("way", "path"),
    "lumiere": ("light",),
    "tenebres": ("darkness",),
    "esperance": ("hope",),
    "benir": ("bless",),
    "benediction": ("blessing",),
    "gloire": ("glory",),
    "puissant": ("mighty", "powerful"),
    "fort": ("strong",),
    "faible": ("weak",),
    "servir": ("serve",),
    "serviteur": ("servant",),
    "obeir": ("obey",),
}

# Seuil de similarité de chaîne (difflib.SequenceMatcher.ratio()) au-dessus
# duquel deux jetons sont considérés comme un cognat plausible. Calibré à la
# main sur des paires réelles du domaine (voir docstring du module) :
# ratio >= 0.75 capture autorite/authority (0.82), esprit/spirit (0.83),
# pasteur/pastor (0.77), exemple/example (0.86), ministere/ministry (0.82),
# tout en écartant des paires clairement non apparentées.
COGNATE_RATIO_THRESHOLD = 0.75

# Longueur minimale d'un jeton pour être éligible à la comparaison par cognat :
# sous ce seuil, le ratio de SequenceMatcher n'est pas significatif (trop de
# faux positifs sur des jetons courts).
COGNATE_MIN_TOKEN_LENGTH = 5


@dataclass(frozen=True)
class MatchScore:
    """Score de correspondance entre un bloc FR et un bloc EN candidat."""

    coverage: float
    matched_tokens: int
    total_fr_tokens: int
    confidence: float
    reason: str


def _content_tokens(text: str, stopwords: frozenset[str]) -> list[str]:
    return [token for token in _tokenize(text) if token and token not in stopwords]


def _glossary_match(fr_token: str, en_tokens: set[str]) -> bool:
    stems = FR_EN_GLOSSARY.get(fr_token)
    if not stems:
        return False
    return any(en_token.startswith(stem) for stem in stems for en_token in en_tokens)


def _cognate_match(fr_token: str, en_tokens: set[str]) -> bool:
    if len(fr_token) < COGNATE_MIN_TOKEN_LENGTH:
        return False
    for en_token in en_tokens:
        if len(en_token) < COGNATE_MIN_TOKEN_LENGTH:
            continue
        ratio = difflib.SequenceMatcher(None, fr_token, en_token).ratio()
        if ratio >= COGNATE_RATIO_THRESHOLD:
            return True
    return False


def score_translation(fr_text: str, en_text: str) -> MatchScore:
    """
    Score la relation de traduction potentielle entre un bloc FR et un bloc EN.

    `coverage` = proportion des jetons de contenu français qui trouvent une
    correspondance (identique, glossaire, ou cognat) côté anglais. Ne mesure
    jamais une égalité lexicale globale (interdit par §12) : seulement un
    recouvrement de contenu.
    """
    fr_tokens = _content_tokens(fr_text, _STOPWORDS_FR)
    en_tokens_list = _content_tokens(en_text, _STOPWORDS_EN)
    en_tokens = set(en_tokens_list)

    if not fr_tokens or not en_tokens:
        return MatchScore(
            coverage=0.0,
            matched_tokens=0,
            total_fr_tokens=len(fr_tokens),
            confidence=0.0,
            reason="aucun jeton de contenu comparable des deux côtés",
        )

    fr_unique = sorted(set(fr_tokens))
    matched: list[str] = []
    exact_or_glossary_matches = 0

    for token in fr_unique:
        if token in en_tokens:
            matched.append(token)
            exact_or_glossary_matches += 1
        elif _glossary_match(token, en_tokens):
            matched.append(token)
            exact_or_glossary_matches += 1
        elif _cognate_match(token, en_tokens):
            matched.append(token)

    coverage = len(matched) / len(fr_unique)

    length_ratio = len(fr_tokens) / len(en_tokens_list) if en_tokens_list else 0.0
    length_plausible = 0.4 <= length_ratio <= 2.5

    confidence = coverage * 0.8
    if exact_or_glossary_matches >= 1:
        confidence += 0.1
    if length_plausible:
        confidence += 0.1
    confidence = round(min(0.97, max(0.0, confidence)), 2)

    reason = (
        f"{len(matched)}/{len(fr_unique)} jeton(s) FR apparié(s) "
        f"(exact/glossaire={exact_or_glossary_matches}, cognats="
        f"{len(matched) - exact_or_glossary_matches}), "
        f"ratio de longueur FR/EN={length_ratio:.2f}"
    )

    return MatchScore(
        coverage=round(coverage, 4),
        matched_tokens=len(matched),
        total_fr_tokens=len(fr_unique),
        confidence=confidence,
        reason=reason,
    )


def find_candidate_en_blocks(
    blocks: tuple[Block, ...], fr_index: int
) -> tuple[Block | None, Block | None]:
    """
    Cherche un bloc anglais candidat avant et après le bloc FR d'indice
    `fr_index`, selon la fenêtre documentée en tête de ce module.

    Retourne (candidat_avant, candidat_apres), chacun pouvant être None.
    """
    before = _search_direction(blocks, fr_index, step=-1)
    after = _search_direction(blocks, fr_index, step=1)
    return before, after


def _search_direction(
    blocks: tuple[Block, ...], fr_index: int, *, step: int
) -> Block | None:
    position = fr_index + step
    skipped_non_en = 0

    while 0 <= position < len(blocks):
        candidate = blocks[position]

        if candidate.language == LANGUAGE_EN:
            return candidate

        if candidate.language == LANGUAGE_FR:
            # Un autre bloc FR marque la fin de la fenêtre locale dans cette
            # direction : au-delà, on quitterait le voisinage immédiat.
            return None

        skipped_non_en += 1
        if skipped_non_en > WINDOW_MAX_BLOCK_SKIP:
            return None

        position += step

    return None


@dataclass(frozen=True)
class BlockMatchCandidates:
    """
    Scores bruts avant/après pour un bloc FR, AVANT toute décision de seuil.

    L'auditeur (auditor.py) applique les seuils REMOVE_TRANSLATION / REVIEW à
    ces scores et décide si la direction retenue est BEFORE, AFTER ou BOTH
    (lorsque les deux candidats franchissent indépendamment le seuil de
    suppression). Ce module ne connaît lui-même aucun seuil de décision : il ne
    fait que mesurer.
    """

    before_block: Block | None
    before_score: MatchScore | None
    after_block: Block | None
    after_score: MatchScore | None

    @property
    def best_single(self) -> tuple[str, Block, MatchScore] | None:
        """
        Meilleure correspondance individuelle (celle avec la plus haute
        confiance), ou None si aucun candidat n'existe des deux côtés.
        """
        candidates = []
        if self.before_block is not None and self.before_score is not None:
            candidates.append((MATCH_BEFORE, self.before_block, self.before_score))
        if self.after_block is not None and self.after_score is not None:
            candidates.append((MATCH_AFTER, self.after_block, self.after_score))

        if not candidates:
            return None

        return max(candidates, key=lambda item: item[2].confidence)


def match_fr_block(blocks: tuple[Block, ...], fr_index: int) -> BlockMatchCandidates:
    """
    Mesure la correspondance d'un bloc FR avec son voisinage anglais local
    (avant ET après, séparément — voir BlockMatchCandidates).
    """
    fr_block = blocks[fr_index]
    before_block, after_block = find_candidate_en_blocks(blocks, fr_index)

    before_score = score_translation(fr_block.text, before_block.text) if before_block else None
    after_score = score_translation(fr_block.text, after_block.text) if after_block else None

    return BlockMatchCandidates(
        before_block=before_block,
        before_score=before_score,
        after_block=after_block,
        after_score=after_score,
    )
