import re


FRENCH_FILLERS = [
    # Hésitations
    "euh",
    "heu",
    "hum",
    "humm",
    "hmmm",
    "mmm",
    "ben",
    "bah",
    "hein",

    # Expressions de remplissage
    "en fait",
    "du coup",
    "donc voilà",
    "voilà",
    "alors voilà",
    "eh bien",
    "et puis",
    "comment dire",
    "si vous voulez",
    "quelque part",
    "en quelque sorte",
    "on va dire",
    "j'ai envie de dire",
    "pour ainsi dire",
    "finalement",
    "globalement",
    "basiquement",
    "techniquement",
    "pratiquement",

    # Expressions orales
    "n'est-ce pas",
    "vous voyez",
    "tu vois",
    "vous savez",
    "tu sais",
    "d'accord",
    "ok",
    "okay",
    "bon",
    "bon ben",
    "bon bah",
    "alors",
    "alors bon"
]


ENGLISH_FILLERS = [
    # Hesitations
    "uh",
    "uhh",
    "uhhh",
    "um",
    "umm",
    "ummm",
    "er",
    "erm",
    "hmm",
    "hmmm",
    "mm",

    # Common fillers
    "you know",
    "i mean",
    "kind of",
    "sort of",
    "basically",
    "actually",
    "literally",
    "honestly",
    "seriously",
    "really",
    "obviously",
    "simply",
    "right",
    "okay",
    "ok",
    "well",

    # Spoken transitions
    "so",
    "so yeah",
    "and so",
    "like",
    "you see",
    "as i said",
    "what i'm saying is",
    "the thing is",
    "at the end of the day"
]


RELIGIOUS_EXPRESSIONS = [
    "amen",
    "amen amen",
    "hallelujah",
    "praise the lord",
    "glory to god",
    "thank you jesus"
]


def remove_fillers(text: str, fillers: list[str]) -> str:
    result = text

    # Trier du plus long au plus court
    # pour éviter que "so" soit supprimé avant "so yeah"
    fillers = sorted(fillers, key=len, reverse=True)

    for filler in fillers:
        pattern = rf"\b{re.escape(filler)}\b"

        result = re.sub(
            pattern,
            "",
            result,
            flags=re.IGNORECASE
        )

    return result


def normalize_spaces(text: str) -> str:

    # Espaces multiples
    text = re.sub(r"\s+", " ", text)

    # Espace avant ponctuation
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)

    # Ponctuation doublée
    text = re.sub(r",\s*,+", ",", text)
    text = re.sub(r"\.\s*\.+", ".", text)

    # Début de phrase avec ponctuation orpheline
    text = re.sub(r"^[,.;:!?]+\s*", "", text)

    # Fin de phrase avec ponctuation orpheline
    text = re.sub(r"\s*[,;:]+\s*$", "", text)

    return text.strip()

def normalize_sentence(text: str) -> str:

    if not text:
        return text

    text = text.strip()

    text = text[0].upper() + text[1:]

    if text[-1] not in ".!?":
        text += "."

    return text

def clean_text(
    text: str,
    remove_fillers_enabled: bool = True,
    remove_religious_expressions: bool = False
) -> str:

    result = text

    if remove_fillers_enabled:
        result = remove_fillers(
            result,
            FRENCH_FILLERS + ENGLISH_FILLERS
        )

    if remove_religious_expressions:
        result = remove_fillers(
            result,
            RELIGIOUS_EXPRESSIONS
        )

    result = normalize_spaces(result)

    return result