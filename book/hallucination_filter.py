FORBIDDEN_PHRASES = [
    # English
    "sure, please provide the text",
    "please provide the text",
    "please provide the content",
    "please provide the paragraph",
    "please send the text",
    "please paste the text",
    "could you provide",
    "can you provide",
    "how can i help you",
    "i would be happy to",
    "i'd be happy to",
    "here is the corrected text",
    "here's the corrected text",
    "here is the revised text",
    "here's the revised text",
    "as an ai",
    "i can help",
    "let me help",
    "please send",
    "please paste",

    # Français
    "bien sûr, veuillez fournir le texte",
    "veuillez fournir le texte",
    "merci de fournir le texte",
    "pouvez-vous fournir le texte",
    "peux-tu fournir le texte",
    "veuillez envoyer le texte",
    "merci d'envoyer le texte",
    "collez le texte",
    "copiez le texte",
    "comment puis-je vous aider",
    "je serais heureux de",
    "je serais ravie de",
    "voici le texte corrigé",
    "voici la version corrigée",
    "voici le texte révisé",
    "en tant qu'ia",
    "en tant qu'intelligence artificielle",
    "je peux vous aider",
    "je peux t'aider",
    "laissez-moi vous aider",
]


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def contains_hallucination(text: str) -> bool:
    normalized = normalize_text(text)

    return any(
        phrase in normalized
        for phrase in FORBIDDEN_PHRASES
    )


def too_different(
    original: str,
    corrected: str,
    max_ratio: float = 1.5
) -> bool:
    original_words = len(original.split())
    corrected_words = len(corrected.split())

    if original_words == 0:
        return False

    ratio = corrected_words / original_words

    return ratio > max_ratio


def filter_hallucinations(
    original_text: str,
    cleaned_text: str
) -> str:
    if contains_hallucination(cleaned_text):
        print("⚠️ Hallucination détectée - texte original conservé")
        return original_text

    if too_different(original_text, cleaned_text):
        print("Réécriture excessive détectée - texte original conservé")
        return original_text

    return cleaned_text