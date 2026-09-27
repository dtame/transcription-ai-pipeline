"""
Moteurs IA pour le traitement des chunks de transcription.

Ce module est le POINT D'ENTRÉE HISTORIQUE de la couche IA. Depuis la
Phase 2, les implémentations vivent dans le paquet `app/ai/` — ce fichier
n'en est plus que la façade, afin que les appelants V1 continuent de faire :

    from app.ai_engine import get_ai_engine, BaseAIEngine, FakeAIEngine

sans aucune modification, et que la couche ne soit implémentée qu'une fois.

Ce que la V1 continue de recevoir, à l'identique :

    get_ai_engine()             -> moteur selon app.config.AI_PROVIDER
    engine.send_prompt(prompt)  -> str (réponse brute du modèle)
    engine.build_prompt(text)   -> str
    engine.process(text)        -> str (Markdown structuré)
    provider inconnu            -> ValueError

Ce que la Phase 2 ajoute, sans rien imposer aux appelants existants :

    engine.generate(AIRequest)  -> AIResponse (texte, usage tokens, latence,
                                   sortie structurée, modèle, finish_reason)
    engine.capabilities(model)  -> ModelCapabilities

Voir app/ai/__init__.py pour l'architecture complète.

Moteurs disponibles :
- FakeAIEngine      : simulation locale pour les tests (aucun réseau)
- OllamaEngine      : moteur principal (Ollama local, ex. qwen3:8b)
- LMStudioEngine    : moteur alternatif (LM Studio, API compatible OpenAI)
- OpenAIEngine      : moteur cloud (OpenAI, OPENAI_API_KEY requise)
- AnthropicEngine   : moteur cloud (Anthropic, ANTHROPIC_API_KEY requise)

Commandes utiles :
    ollama pull qwen3:8b       # modèle principal recommandé
    ollama pull llama3.1:8b    # modèle alternatif stable
    ollama pull mistral:7b     # modèle léger de secours
"""

from app.ai.capabilities import ModelCapabilities
from app.ai.contracts import AIRequest, AIResponse
from app.ai.providers import (
    AnthropicEngine,
    BaseAIEngine,
    FakeAIEngine,
    LMStudioEngine,
    OllamaEngine,
    OpenAIEngine,
    ProviderResult,
)
from app.ai.registry import (
    available_providers,
    get_ai_engine,
    get_ai_provider,
    register_ai_engine,
)

__all__ = [
    "AIRequest",
    "AIResponse",
    "AnthropicEngine",
    "BaseAIEngine",
    "FakeAIEngine",
    "LMStudioEngine",
    "ModelCapabilities",
    "OllamaEngine",
    "OpenAIEngine",
    "ProviderResult",
    "available_providers",
    "get_ai_engine",
    "get_ai_provider",
    "register_ai_engine",
]
