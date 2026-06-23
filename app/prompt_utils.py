"""
Utilitaire de rendu de prompts IA sécurisé.

Utilise des placeholders de type {{VARIABLE_NAME}} pour éviter les conflits
avec les accolades littérales présentes dans les prompts (exemples JSON,
structures Markdown, \\boxed{}, dictionnaires Python, etc.).

Contrairement à str.format(), render_prompt() ne lève jamais :
    - KeyError      sur des accolades inconnues
    - IndexError    sur des accolades vides {}
    - ValueError    sur des accolades mal formées
"""


def render_prompt(template: str, variables: dict) -> str:
    """
    Remplace uniquement des placeholders explicites de type {{VARIABLE_NAME}}
    sans interpréter les autres accolades du prompt.

    Contrairement à str.format(), cette fonction ne plante jamais sur :
    - des accolades JSON      : {"key": "value"}
    - des formules LaTeX      : \\boxed{}
    - des accolades vides     : {}
    - des placeholders Python : {0}

    Args:
        template:  Texte du prompt avec placeholders {{NOM_VARIABLE}}.
        variables: Dictionnaire {nom_variable: valeur_à_injecter}.

    Returns:
        Le prompt avec les placeholders remplacés par leurs valeurs.

    Example:
        >>> render_prompt("Texte : {{TEXT}}", {"TEXT": "bonjour"})
        'Texte : bonjour'
    """
    result = template
    for key, value in variables.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result
