from book.local_ai_service import ask_local_ai

response = ask_local_ai(
    """
    Tu es un éditeur professionnel.

    Propose un titre court pour un livret
    traitant de la foi chrétienne dans les épreuves.

    Réponds uniquement avec le titre.
    """
)

print(response)