import re
from collections import Counter
from book.local_ai_service import ask_local_ai

STOP_WORDS = {
    # Français
    "le", "la", "les", "un", "une", "des", "du", "de", "d",
    "au", "aux", "et", "ou", "mais", "donc", "or", "ni", "car",
    "à", "dans", "par", "pour", "avec", "sans", "sur", "sous",
    "entre", "vers", "chez", "ce", "cet", "cette", "ces",
    "mon", "ton", "son", "notre", "votre", "leur",
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles",
    "qui", "que", "quoi", "dont", "où", "est", "sont", "était",
    "étaient", "être", "avoir", "ne", "pas", "plus", "moins", "très",
    "aujourd", "hui", "comme", "tout", "tous", "toutes",

    # Anglais
    "the", "a", "an", "and", "or", "but", "so", "because",
    "to", "of", "in", "on", "at", "for", "from", "with", "without",
    "into", "through", "this", "that", "these", "those",
    "my", "your", "his", "her", "our", "their",
    "i", "you", "he", "she", "we", "they",
    "who", "what", "which", "where", "when", "why", "how",
    "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "not", "no", "very", "more", "most"
}

RELIGIOUS_STOP_WORDS = {
    # Français
    "dieu", "seigneur", "jésus", "jesus", "christ",
    "foi", "église", "eglise", "évangile", "evangile",

    # Anglais
    "god", "lord", "jesus", "christ",
    "faith", "church", "gospel"
}


def extract_keywords(
    paragraphs: list[str],
    max_keywords: int = 5,
    ignore_religious_words: bool = False
) -> list[str]:
    text = " ".join(paragraphs).lower()

    words = re.findall(r"[a-zA-ZÀ-ÿ']+", text)

    excluded_words = set(STOP_WORDS)

    if ignore_religious_words:
        excluded_words.update(RELIGIOUS_STOP_WORDS)

    keywords = [
        word for word in words
        if len(word) > 2 and word not in excluded_words
    ]

    counter = Counter(keywords)

    return [word for word, _ in counter.most_common(max_keywords)]

def build_title(paragraphs: list[str]) -> str:

    content = "\n\n".join(paragraphs[:10])

    prompt = f"""
Tu es un éditeur professionnel.

Analyse le contenu suivant et propose un titre de livret.

Contraintes :
- Maximum 8 mots.
- Langue du texte analysé.
- Pas de guillemets.
- Pas de sous-titre.
- Réponds uniquement avec le titre.

Contenu :

{content}
"""

    try:
        title = ask_local_ai(
            prompt=prompt,
            temperature=0.3
        )

        title = title.strip()

        if title:
            return title

    except Exception as ex:
        print(f"Erreur IA locale : {ex}")

    return "Livret généré automatiquement"