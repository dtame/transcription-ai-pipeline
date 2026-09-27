"""
Implémentations de providers de la couche IA.

Un seul point d'entrée pour en obtenir un : app.ai.registry.get_ai_engine().
Importer un provider directement reste possible pour les tests, mais le code
de production passe par le registre, afin qu'il n'existe jamais deux chemins
de création concurrents.
"""

from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.providers.base import BaseAIEngine, ProviderResult
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.providers.lmstudio import LMStudioEngine
from app.ai.providers.ollama import OllamaEngine
from app.ai.providers.openai_engine import OpenAIEngine

__all__ = [
    "AnthropicEngine",
    "BaseAIEngine",
    "FakeAIEngine",
    "FakeReply",
    "LMStudioEngine",
    "OllamaEngine",
    "OpenAIEngine",
    "ProviderResult",
]
