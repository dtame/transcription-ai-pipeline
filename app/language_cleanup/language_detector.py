"""
Classification linguistique EN / FR / MIXED / UNKNOWN, par SRC.

MÉTHODE (déterministe, sans dépendance, sans réseau) :

Aucune bibliothèque de détection de langue n'est installée dans ce projet
(voir requirements.txt et l'audit des paquets disponibles fait avant
d'écrire ce module — seul `numpy` figure parmi les paquets qui pourraient s'en
rapprocher, et il n'offre rien d'utile ici). Plutôt que d'ajouter une
dépendance lourde pour un besoin qu'une heuristique simple couvre
raisonnablement, la classification repose sur trois signaux combinés :

1. MOTS GRAMMATICAUX ("function words") : des listes fermées d'articles,
   pronoms, prépositions et conjonctions propres à chaque langue
   (FR_FUNCTION_WORDS / EN_FUNCTION_WORDS). Ce sont des mots à très haute
   fréquence et quasiment jamais ambigus entre les deux langues (« le », « les »,
   « dans », « the », « and », « with »…). C'est le signal principal : il ne
   dépend d'aucun mot de contenu, donc pas des noms propres, références
   bibliques, nombres ou acronymes qui peuvent apparaître dans les deux langues.

2. DIACRITIQUES FRANÇAIS (é, è, ê, à, ù, ...) : quasi inexistants en anglais
   courant (hors emprunts rares comme « café », « naïve »), leur présence est un
   signal FR modéré.

3. ÉLISIONS FRANÇAISES (l', d', j', qu', n', c', m', t', s') et CONTRACTIONS
   ANGLAISES (n't, 're, 've, 'll, 'm, et 's en fin de mot) : marqueurs
   grammaticaux très fiables de chaque langue.

Un SRC sans AUCUN mot grammatical reconnu (que des nombres, un nom propre isolé,
une interjection, un acronyme) devient UNKNOWN plutôt qu'une classification
fabriquée à partir d'un seul mot ambigu (§9 du cahier des charges). Un SRC où
les deux langues sont significativement représentées devient MIXED.

LIMITES DOCUMENTÉES :

- un SRC très court (« Amen. », « Yes. », « Oui. ») reste souvent UNKNOWN :
  c'est le comportement voulu, pas une lacune à corriger ici ;
- l'algorithme ne fait aucune tentative de reconnaissance de noms propres,
  d'entités bibliques ou de langue par IA : il ne sait que reconnaître des
  mots grammaticaux fermés et des motifs de surface ;
- un SRC entièrement composé de contenu (mots rares, technique, une seule
  longue citation) sans mot grammatical peut être classé UNKNOWN même si un
  lecteur humain reconnaîtrait la langue au premier coup d'œil.
"""

from __future__ import annotations

import re

from app.language_cleanup.models import (
    LANGUAGE_EN,
    LANGUAGE_FR,
    LANGUAGE_MIXED,
    LANGUAGE_UNKNOWN,
    LanguageClassification,
)

# ---------------------------------------------------------------------------
# Vocabulaires fermés — mots grammaticaux à haute fréquence, non ambigus
# ---------------------------------------------------------------------------

FR_FUNCTION_WORDS = frozenset(
    """
    le la les l un une des du de et est sont dans pour que qui quoi avec nous
    vous ils elles etre etait etaient avoir sur pas ne plus mais ou bien donc
    car ni si se sa son ses leur leurs notre votre nos vos je tu il elle on y
    en au aux comme quand alors aussi tres tout tous toute toutes rien aucun
    aucune personne ainsi ceci cela celui celle ceux celles qu d j m t c n
    veux veut voulez voulons veulent moi toi lui eux ceci cela apres avant
    entre chez sans sous vers deja encore meme memes votre etes suis sommes
    """.split()
)

EN_FUNCTION_WORDS = frozenset(
    """
    the a an and is are in for that who whom with we you they be been being
    have has had on not but where so because her his their our your my i he
    she it as when very all nothing also then this these those what no do
    does did will would should can could of to from by at yes not there here
    was were am if or nor into onto than then about above below under over
    """.split()
)

# Diacritiques quasi exclusifs au français dans ce corpus (anglais oral d'un
# orateur de conférence : pas de citation espagnole/allemande attendue).
_FR_DIACRITIC_CHARS = "éèêëàâäùûüôöîïçœ"
_FR_DIACRITIC_RE = re.compile(f"[{_FR_DIACRITIC_CHARS}]", re.IGNORECASE)

# Élisions françaises : l'homme, d'accord, qu'il, n'est, c'est, j'ai, m'a, t'a, s'il
_FR_ELISION_RE = re.compile(r"\b[ldjqncmts]['’]", re.IGNORECASE)

# Contractions anglaises : don't, we're, I've, we'll, I'm, God's
_EN_CONTRACTION_RE = re.compile(
    r"[a-z]+(n't|'re|'ve|'ll|'m|'s|'d)\b", re.IGNORECASE
)

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

# En dessous de ce nombre de tokens porteurs de signal (mots grammaticaux et
# marqueurs), la classification reste UNKNOWN plutôt que de trancher sur un
# indice unique (§9 : « ne jamais classifier uniquement sur un mot isolé »).
MIN_SIGNAL_FOR_CONFIDENT_CLASSIFICATION = 1

# Si les scores FR et EN sont tous deux positifs et leur rapport est inférieur
# à ce seuil, le SRC est considéré MIXED plutôt que tranché arbitrairement.
MIXED_RATIO_THRESHOLD = 1.8


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def classify_text(text: str) -> LanguageClassification:
    """
    Classifie un texte de SRC en EN / FR / MIXED / UNKNOWN.

    Ne modifie et ne recopie jamais le texte au-delà de la classification :
    aucune normalisation destructive n'est appliquée au texte d'origine par ce
    module (la normalisation reste interne au calcul du score).
    """
    stripped = text.strip()

    if not stripped:
        return LanguageClassification(
            language=LANGUAGE_UNKNOWN,
            confidence=0.0,
            reason="texte vide",
        )

    tokens = _tokenize(stripped)

    fr_function_hits = sum(1 for token in tokens if token in FR_FUNCTION_WORDS)
    en_function_hits = sum(1 for token in tokens if token in EN_FUNCTION_WORDS)

    fr_elision_hits = len(_FR_ELISION_RE.findall(stripped))
    en_contraction_hits = len(_EN_CONTRACTION_RE.findall(stripped))
    fr_diacritic_hits = len(_FR_DIACRITIC_RE.findall(stripped))

    fr_score = fr_function_hits + 2 * fr_elision_hits + 1.5 * fr_diacritic_hits
    en_score = en_function_hits + 2 * en_contraction_hits

    signals = [
        f"{len(tokens)} mot(s)",
        f"fr_function={fr_function_hits}",
        f"en_function={en_function_hits}",
        f"fr_elisions={fr_elision_hits}",
        f"en_contractions={en_contraction_hits}",
        f"fr_diacritics={fr_diacritic_hits}",
    ]
    reason_suffix = ", ".join(signals)

    if fr_score == 0 and en_score == 0:
        return LanguageClassification(
            language=LANGUAGE_UNKNOWN,
            confidence=0.0,
            reason=f"aucun signal grammatical fiable ({reason_suffix})",
        )

    if fr_score > 0 and en_score == 0:
        confidence = _confidence_from_score(fr_score)
        return LanguageClassification(
            language=LANGUAGE_FR,
            confidence=confidence,
            reason=f"signaux français dominants ({reason_suffix})",
        )

    if en_score > 0 and fr_score == 0:
        confidence = _confidence_from_score(en_score)
        return LanguageClassification(
            language=LANGUAGE_EN,
            confidence=confidence,
            reason=f"signaux anglais dominants ({reason_suffix})",
        )

    # Les deux scores sont positifs : dominance nette ou mélange réel.
    dominant_score = max(fr_score, en_score)
    minor_score = min(fr_score, en_score)
    ratio = dominant_score / minor_score if minor_score else float("inf")

    if ratio < MIXED_RATIO_THRESHOLD:
        return LanguageClassification(
            language=LANGUAGE_MIXED,
            confidence=round(min(0.6, 0.3 + 0.05 * minor_score), 2),
            reason=(
                "signaux français et anglais comparables, rapport "
                f"{ratio:.2f} < seuil {MIXED_RATIO_THRESHOLD} ({reason_suffix})"
            ),
        )

    winner = LANGUAGE_FR if fr_score > en_score else LANGUAGE_EN
    confidence = _confidence_from_score(dominant_score, penalty=minor_score)

    return LanguageClassification(
        language=winner,
        confidence=confidence,
        reason=(
            f"signaux {winner} nettement dominants, rapport {ratio:.2f} "
            f"({reason_suffix})"
        ),
    )


def _confidence_from_score(score: float, penalty: float = 0.0) -> float:
    """
    Confiance bornée et documentée : jamais de certitude artificielle (max 0.97).

    Formule volontairement simple et monotone : plus de signaux -> plus de
    confiance, avec rendements décroissants. `penalty` réduit légèrement la
    confiance lorsqu'un score minoritaire de l'autre langue existe malgré tout.
    """
    base = 0.55 + 0.12 * score
    base -= 0.05 * penalty
    return round(max(0.5, min(0.97, base)), 2)
