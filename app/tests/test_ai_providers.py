"""
Providers — normalisation, usage, erreurs, sortie structurée.

Aucun test de ce module n'ouvre de connexion : le transport HTTP et le SDK
OpenAI sont remplacés par les doubles de app/tests/ai_fakes.py. Un appel
réseau involontaire fait échouer le test (fixture `no_ai_network`) au lieu de
contacter un service réel.

Chaque moteur reçoit une politique de rejeu sans attente : un test qui
simule une erreur 500 ne doit pas payer le backoff de production.
"""

from __future__ import annotations

import copy

import pytest
import requests

import app.config as config

from app.ai.contracts import AIRequest, USAGE_UNAVAILABLE
from app.ai.errors import (
    AIAuthenticationError,
    AIConfigurationError,
    AIConnectionError,
    AIRateLimitError,
    AIRequestError,
    AIResponseError,
    AIServerError,
    AIStructuredOutputError,
    AITimeoutError,
)
from app.ai.providers import (
    AnthropicEngine,
    FakeAIEngine,
    FakeReply,
    LMStudioEngine,
    OllamaEngine,
    OpenAIEngine,
)
from app.ai.retry import no_delay_policy
from app.tests import ai_fakes
from app.tests.ai_fakes import (
    FakeCompletion,
    FakeHttpResponse,
    FakeOpenAIClient,
    FakeUsage,
    RecordingPost,
    anthropic_response,
    ollama_response,
    openai_style_response,
)


@pytest.fixture(autouse=True)
def _reseau_interdit(no_ai_network):
    """Tous les tests de ce module partent d'un réseau fermé."""


@pytest.fixture
def post(monkeypatch):
    """Installe un double de requests.post et retourne l'enregistreur."""
    import app.ai.providers._http as http_module

    def _install(*responses):
        recorder = RecordingPost(responses)
        monkeypatch.setattr(http_module.requests, "post", recorder)
        return recorder

    return _install


def _policy():
    """Rejeu désactivé : un seul essai, aucune attente."""
    return no_delay_policy(max_attempts=1)


# ---------------------------------------------------------------------------
# Fake
# ---------------------------------------------------------------------------

class TestFakeProvider:

    def test_texte_et_usage_scriptes(self):
        engine = FakeAIEngine(
            script=[
                FakeReply(
                    text="analyse",
                    input_tokens=12_000,
                    output_tokens=2_000,
                    finish_reason="stop",
                    request_id="fake-1",
                )
            ]
        )

        response = engine.generate(AIRequest(prompt="texte source"))

        assert response.text == "analyse"
        assert response.provider == "fake"
        assert response.input_tokens == 12_000
        assert response.output_tokens == 2_000
        assert response.total_tokens == 14_000
        assert response.finish_reason == "stop"
        assert response.request_id == "fake-1"
        assert response.usage_source == "provider"

    def test_modele_par_defaut_et_surcharge(self):
        assert FakeAIEngine().generate(AIRequest(prompt="x")).model == "fake-model"
        assert FakeAIEngine(model="fake-editor").generate(
            AIRequest(prompt="x")
        ).model == "fake-editor"

    def test_sans_usage_les_compteurs_restent_none(self):
        response = FakeAIEngine(script=[FakeReply(text="ok")]).generate(
            AIRequest(prompt="x")
        )

        assert response.input_tokens is None
        assert response.total_tokens is None
        assert response.usage_source == USAGE_UNAVAILABLE

    def test_latence_simulee_sans_attente_reelle(self):
        import time

        engine = FakeAIEngine(script=[FakeReply(text="ok", latency_seconds=4.21)])

        debut = time.monotonic()
        response = engine.generate(AIRequest(prompt="x"))
        duree_reelle = time.monotonic() - debut

        assert response.latency_ms == 4210
        assert duree_reelle < 0.5

    def test_erreur_scriptee(self):
        engine = FakeAIEngine(script=[AITimeoutError("trop lent")])

        with pytest.raises(AITimeoutError):
            engine.generate(AIRequest(prompt="x"))

    def test_rejeu_transitoire_puis_succes(self):
        engine = FakeAIEngine(
            script=[AITimeoutError("1"), FakeReply(text="réussi", output_tokens=5)],
            retry_policy=no_delay_policy(max_attempts=3),
        )

        response = engine.generate(AIRequest(prompt="x"))

        assert response.text == "réussi"
        assert engine.call_count == 2

    def test_journal_des_requetes(self):
        engine = FakeAIEngine()
        engine.generate(AIRequest(prompt="premier", metadata={"stage": "source_analysis"}))

        assert engine.call_count == 1
        assert engine.last_request.stage == "source_analysis"

    def test_metadonnees_recopiees_dans_la_reponse(self):
        response = FakeAIEngine().generate(
            AIRequest(prompt="x", metadata={"stage": "book_generation"})
        )

        assert response.stage == "book_generation"

    def test_sortie_structuree_valide(self):
        engine = FakeAIEngine(script=[FakeReply(text='{"titre": "Un titre"}')])

        response = engine.generate(
            AIRequest(prompt="x", response_schema={"type": "object"})
        )

        assert response.parsed == {"titre": "Un titre"}
        assert response.text == '{"titre": "Un titre"}'

    def test_sortie_structuree_invalide_echoue(self):
        engine = FakeAIEngine(script=[FakeReply(text="Voici votre analyse :")])

        with pytest.raises(AIStructuredOutputError):
            engine.generate(AIRequest(prompt="x", response_schema={"type": "object"}))

    def test_sortie_structuree_validee_par_schema(self):
        engine = FakeAIEngine(script=[FakeReply(text='{"titre": "t"}')])
        schema = {"type": "object", "required": ["titre", "sections"]}

        with pytest.raises(AIStructuredOutputError, match="sections"):
            engine.generate(AIRequest(prompt="x", response_schema=schema))

    def test_sortie_structuree_invalide_conserve_l_usage_provider(self):
        """
        Phase 3B.2 — un appel dont le transport a réussi (usage RÉEL rapporté
        par le fournisseur) mais dont la sortie structurée échoue ENSUITE ne
        doit pas perdre cet usage : il est attaché à l'exception levée.
        """
        engine = FakeAIEngine(
            script=[
                FakeReply(
                    text="Voici votre analyse :",
                    input_tokens=1_000,
                    output_tokens=200,
                    finish_reason="stop",
                    request_id="fake-usage-perdu",
                )
            ]
        )

        with pytest.raises(AIStructuredOutputError) as excinfo:
            engine.generate(AIRequest(prompt="x", response_schema={"type": "object"}))

        response = excinfo.value.response

        assert response is not None
        assert response.parsed is None
        assert response.provider == "fake"
        assert response.input_tokens == 1_000
        assert response.output_tokens == 200
        assert response.total_tokens == 1_200
        assert response.usage_source == "provider"
        assert response.request_id == "fake-usage-perdu"

    def test_sortie_structuree_invalide_sans_usage_provider_reste_none(self):
        """Sans usage rapporté, l'AIResponse attachée le dit honnêtement."""
        engine = FakeAIEngine(script=[FakeReply(text="pas du JSON")])

        with pytest.raises(AIStructuredOutputError) as excinfo:
            engine.generate(AIRequest(prompt="x", response_schema={"type": "object"}))

        response = excinfo.value.response

        assert response is not None
        assert response.input_tokens is None
        assert response.usage_source == USAGE_UNAVAILABLE

    def test_une_erreur_avant_l_appel_transport_ne_porte_aucune_reponse(self):
        """
        Une erreur qui survient AVANT tout ProviderResult (timeout, config…)
        n'a rien à attacher : `response` reste None, comme avant Phase 3B.2.
        """
        engine = FakeAIEngine(script=[AITimeoutError("trop lent")])

        with pytest.raises(AITimeoutError) as excinfo:
            engine.generate(AIRequest(prompt="x"))

        assert excinfo.value.response is None

    def test_une_sortie_structuree_reussie_n_est_pas_affectee(self):
        """Aucune régression du chemin normal : `response` reste None sur succès."""
        engine = FakeAIEngine(
            script=[FakeReply(text='{"titre": "ok"}', input_tokens=50, output_tokens=10)]
        )

        response = engine.generate(
            AIRequest(prompt="x", response_schema={"type": "object"})
        )

        assert response.parsed == {"titre": "ok"}
        assert response.input_tokens == 50
        assert response.output_tokens == 10

    def test_derniere_reponse_rejouee(self):
        engine = FakeAIEngine(script=[FakeReply(text="unique")])

        assert engine.generate(AIRequest(prompt="a")).text == "unique"
        assert engine.generate(AIRequest(prompt="b")).text == "unique"


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

class TestOllamaProvider:

    def test_payload_conforme_a_la_v1(self, post):
        recorder = post(ollama_response())
        engine = OllamaEngine(retry_policy=_policy())

        engine.generate(AIRequest(prompt="mon prompt"))

        payload = recorder.last_payload

        assert recorder.calls[0]["url"].endswith("/api/generate")
        assert payload["model"] == config.OLLAMA_MODEL
        assert payload["prompt"] == "mon prompt"
        assert payload["stream"] is False
        assert "options" in payload

    def test_num_ctx_vient_des_capacites(self, post):
        recorder = post(ollama_response())
        engine = OllamaEngine(retry_policy=_policy())

        engine.generate(AIRequest(prompt="x"))

        assert recorder.last_payload["options"]["num_ctx"] == (
            config.OLLAMA_OPTIONS["num_ctx"]
        )

    def test_num_ctx_suit_un_override_de_capacites(self, post, monkeypatch):
        """La fenêtre de contexte n'est plus une constante applicative."""
        monkeypatch.setattr(
            config,
            "AI_MODEL_CAPABILITIES",
            {"ollama:*": {"context_window": 32_768, "max_output_tokens": 4_096}},
        )
        recorder = post(ollama_response())

        OllamaEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))

        assert recorder.last_payload["options"]["num_ctx"] == 32_768

    def test_metadonnees_jamais_transmises(self, post):
        """`metadata` sert à l'observabilité interne, pas au fournisseur."""
        recorder = post(ollama_response())

        OllamaEngine(retry_policy=_policy()).generate(
            AIRequest(
                prompt="x",
                metadata={"stage": "source_analysis", "secret_interne": "ne pas fuiter"},
            )
        )

        assert "metadata" not in recorder.last_payload
        assert "ne pas fuiter" not in str(recorder.last_payload)

    def test_usage_normalise(self, post):
        post(ollama_response(prompt_eval_count=350, eval_count=120))

        response = OllamaEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))

        assert response.input_tokens == 350
        assert response.output_tokens == 120
        assert response.total_tokens == 470
        assert response.usage_source == "provider"

    def test_usage_absent_reste_none(self, post):
        post(ollama_response(prompt_eval_count=None, eval_count=None))

        response = OllamaEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))

        assert response.input_tokens is None
        assert response.output_tokens is None
        assert response.usage_source == USAGE_UNAVAILABLE

    def test_texte_normalise_et_finish_reason(self, post):
        post(ollama_response(text="  contenu  ", done_reason="stop"))

        response = OllamaEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))

        assert response.text == "contenu"
        assert response.finish_reason == "stop"
        assert response.provider == "ollama"

    def test_system_prompt_transmis(self, post):
        recorder = post(ollama_response())

        OllamaEngine(retry_policy=_policy()).generate(
            AIRequest(prompt="x", system_prompt="Tu es un éditeur.")
        )

        assert recorder.last_payload["system"] == "Tu es un éditeur."

    def test_sortie_structuree_par_prompt_et_format(self, post):
        recorder = post(ollama_response(text='{"a": 1}'))

        response = OllamaEngine(retry_policy=_policy()).generate(
            AIRequest(prompt="analyse", response_schema={"type": "object"})
        )

        # Ollama ne contraint pas au schéma : la consigne est annexée au prompt.
        assert recorder.last_payload["format"] == "json"
        assert "JSON" in recorder.last_payload["prompt"]
        assert recorder.last_payload["prompt"].startswith("analyse")
        assert response.parsed == {"a": 1}

    def test_max_output_tokens_devient_num_predict(self, post):
        recorder = post(ollama_response())

        OllamaEngine(retry_policy=_policy()).generate(
            AIRequest(prompt="x", max_output_tokens=512)
        )

        assert recorder.last_payload["options"]["num_predict"] == 512

    def test_reponse_sans_champ_response(self, post):
        post(FakeHttpResponse({"autre": "chose"}))

        with pytest.raises(AIResponseError, match="'response' absent"):
            OllamaEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))

    def test_timeout_traduit(self, post):
        post(requests.exceptions.Timeout())

        with pytest.raises(AITimeoutError):
            OllamaEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))

    def test_service_injoignable_traduit(self, post):
        post(requests.exceptions.ConnectionError())

        with pytest.raises(AIConnectionError, match="ollama serve"):
            OllamaEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))

    def test_erreur_serveur_traduite(self, post):
        post(FakeHttpResponse({}, status_code=500, text="boom"))

        with pytest.raises(AIServerError):
            OllamaEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))

    def test_timeout_configure(self, post):
        recorder = post(ollama_response())

        OllamaEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))

        assert recorder.calls[0]["timeout"] == (
            config.AI_DEFAULT_CONNECT_TIMEOUT_SECONDS,
            config.OLLAMA_TIMEOUT_SECONDS,
        )

    def test_timeout_surchargeable_par_requete(self, post):
        recorder = post(ollama_response())

        OllamaEngine(retry_policy=_policy()).generate(
            AIRequest(prompt="x", timeout_seconds=12)
        )

        assert recorder.calls[0]["timeout"] == (
            config.AI_DEFAULT_CONNECT_TIMEOUT_SECONDS,
            12,
        )


# ---------------------------------------------------------------------------
# LM Studio
# ---------------------------------------------------------------------------

class TestLMStudioProvider:

    def test_payload_messages(self, post):
        recorder = post(openai_style_response())

        LMStudioEngine(retry_policy=_policy()).generate(
            AIRequest(prompt="mon prompt", system_prompt="consigne")
        )

        payload = recorder.last_payload

        assert recorder.calls[0]["url"].endswith("/chat/completions")
        assert payload["model"] == config.LMSTUDIO_MODEL
        assert payload["messages"][0] == {"role": "system", "content": "consigne"}
        assert payload["messages"][1] == {"role": "user", "content": "mon prompt"}
        assert payload["temperature"] == config.LMSTUDIO_TEMPERATURE

    def test_usage_normalise(self, post):
        post(
            openai_style_response(
                usage={"prompt_tokens": 800, "completion_tokens": 200, "total_tokens": 1000}
            )
        )

        response = LMStudioEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))

        assert response.input_tokens == 800
        assert response.output_tokens == 200
        assert response.total_tokens == 1000
        assert response.provider == "lmstudio"

    def test_usage_absent_reste_none(self, post):
        post(openai_style_response(usage=None))

        response = LMStudioEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))

        assert response.input_tokens is None
        assert response.usage_source == USAGE_UNAVAILABLE

    def test_texte_finish_reason_et_request_id(self, post):
        post(openai_style_response(text="  contenu  ", finish_reason="length"))

        response = LMStudioEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))

        assert response.text == "contenu"
        assert response.finish_reason == "length"
        assert response.request_id == "chatcmpl-test"

    def test_metadonnees_jamais_transmises(self, post):
        recorder = post(openai_style_response())

        LMStudioEngine(retry_policy=_policy()).generate(
            AIRequest(prompt="x", metadata={"stage": "book_generation"})
        )

        assert "metadata" not in recorder.last_payload
        assert "book_generation" not in str(recorder.last_payload)

    def test_sortie_structuree(self, post):
        recorder = post(openai_style_response(text='{"a": 1}'))

        response = LMStudioEngine(retry_policy=_policy()).generate(
            AIRequest(prompt="x", response_schema={"type": "object"})
        )

        assert recorder.last_payload["response_format"] == {"type": "json_object"}
        assert response.parsed == {"a": 1}

    def test_structure_invalide(self, post):
        post(FakeHttpResponse({"choices": []}))

        with pytest.raises(AIResponseError, match="structure de réponse invalide"):
            LMStudioEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))

    def test_timeout_par_defaut_configure(self, post):
        recorder = post(openai_style_response())

        LMStudioEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))

        assert recorder.calls[0]["timeout"] == (
            config.AI_DEFAULT_CONNECT_TIMEOUT_SECONDS,
            config.AI_DEFAULT_TIMEOUT_SECONDS,
        )

    def test_erreur_429_traduite(self, post):
        post(FakeHttpResponse({}, status_code=429, text="slow down"))

        with pytest.raises(AIRateLimitError):
            LMStudioEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

class TestOpenAIProvider:

    def test_normalisation_complete(self):
        client = FakeOpenAIClient(
            FakeCompletion(
                content="  texte  ",
                finish_reason="stop",
                usage=FakeUsage(prompt_tokens=1200, completion_tokens=300, total_tokens=1500),
                response_id="chatcmpl-42",
                model="modele-retourne",
            )
        )

        response = OpenAIEngine(client=client, retry_policy=_policy()).generate(
            AIRequest(prompt="x")
        )

        assert response.text == "texte"
        assert response.provider == "openai"
        assert response.model == "modele-retourne"
        assert response.input_tokens == 1200
        assert response.output_tokens == 300
        assert response.total_tokens == 1500
        assert response.finish_reason == "stop"
        assert response.request_id == "chatcmpl-42"

    def test_usage_de_l_api_prioritaire_sur_toute_estimation(self):
        """Le texte n'est jamais re-tokenisé quand l'API donne les compteurs."""
        long_texte = "mot " * 5000
        client = FakeOpenAIClient(
            FakeCompletion(
                content=long_texte,
                usage=FakeUsage(prompt_tokens=7, completion_tokens=3, total_tokens=10),
            )
        )

        response = OpenAIEngine(client=client, retry_policy=_policy()).generate(
            AIRequest(prompt="x")
        )

        assert response.input_tokens == 7
        assert response.output_tokens == 3
        assert response.total_tokens == 10

    def test_usage_absent_reste_none(self):
        client = FakeOpenAIClient(FakeCompletion(usage=None))

        response = OpenAIEngine(client=client, retry_policy=_policy()).generate(
            AIRequest(prompt="x")
        )

        assert response.input_tokens is None
        assert response.usage_source == USAGE_UNAVAILABLE

    def test_payload_messages_et_temperature(self):
        client = FakeOpenAIClient()

        OpenAIEngine(client=client, retry_policy=_policy()).generate(
            AIRequest(prompt="p", system_prompt="s", temperature=0.4, max_output_tokens=900)
        )

        appel = client.calls[0]

        assert appel["model"] == config.OPENAI_MODEL
        assert appel["messages"][0] == {"role": "system", "content": "s"}
        assert appel["messages"][1] == {"role": "user", "content": "p"}
        assert appel["temperature"] == 0.4
        assert appel["max_tokens"] == 900
        assert "max_completion_tokens" not in appel

    def test_terra_uses_max_completion_tokens(self):
        engine = OpenAIEngine(client=FakeOpenAIClient(), retry_policy=_policy())
        payload = engine.build_payload(
            AIRequest(
                prompt="p",
                model="gpt-5.6-terra",
                temperature=None,
                max_output_tokens=8192,
                response_schema={"type": "object"},
            ),
            "gpt-5.6-terra",
        )
        assert payload["max_completion_tokens"] == 8192
        assert "max_tokens" not in payload
        assert "temperature" not in payload

    def test_terra_rejects_explicit_temperature(self):
        engine = OpenAIEngine(client=FakeOpenAIClient(), retry_policy=_policy())
        with pytest.raises(AIConfigurationError, match="temperature"):
            engine.build_payload(
                AIRequest(
                    prompt="p",
                    model="gpt-5.6-terra",
                    temperature=0.2,
                    max_output_tokens=16,
                ),
                "gpt-5.6-terra",
            )

    def test_metadonnees_jamais_transmises(self):
        client = FakeOpenAIClient()

        OpenAIEngine(client=client, retry_policy=_policy()).generate(
            AIRequest(prompt="x", metadata={"stage": "source_analysis"})
        )

        assert "metadata" not in client.calls[0]
        assert "source_analysis" not in str(client.calls[0])

    def test_sortie_structuree(self):
        client = FakeOpenAIClient(FakeCompletion(content='{"a": 1}'))

        response = OpenAIEngine(client=client, retry_policy=_policy()).generate(
            AIRequest(prompt="x", response_schema={"type": "object"})
        )

        assert client.calls[0]["response_format"] == {"type": "json_object"}
        assert response.parsed == {"a": 1}

    @pytest.mark.parametrize(
        "erreur, attendu",
        [
            (ai_fakes.RateLimitError("429"), AIRateLimitError),
            (ai_fakes.AuthenticationError("401"), AIAuthenticationError),
            (ai_fakes.APITimeoutError("timeout"), AITimeoutError),
            (ai_fakes.BadRequestError("400"), AIRequestError),
        ],
    )
    def test_traduction_des_erreurs_du_sdk(self, erreur, attendu):
        client = FakeOpenAIClient(error=erreur)

        with pytest.raises(attendu):
            OpenAIEngine(client=client, retry_policy=_policy()).generate(
                AIRequest(prompt="x")
            )

    def test_traduction_par_code_http(self):
        client = FakeOpenAIClient(error=ai_fakes.StatusOnlyError(status_code=503))

        with pytest.raises(AIServerError):
            OpenAIEngine(client=client, retry_policy=_policy()).generate(
                AIRequest(prompt="x")
            )

    def test_contenu_vide_signale(self):
        client = FakeOpenAIClient(FakeCompletion(content=None))

        with pytest.raises(AIResponseError, match="vide"):
            OpenAIEngine(client=client, retry_policy=_policy()).generate(
                AIRequest(prompt="x")
            )

    def test_cle_absente_echoue_clairement(self):
        """Sans OPENAI_API_KEY, l'échec nomme la variable d'environnement."""
        with pytest.raises(AIConfigurationError, match="OPENAI_API_KEY"):
            OpenAIEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))

    def test_usage_en_dict_supporte(self):
        client = FakeOpenAIClient(
            FakeCompletion(
                usage={"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11}
            )
        )

        response = OpenAIEngine(client=client, retry_policy=_policy()).generate(
            AIRequest(prompt="x")
        )

        assert response.input_tokens == 5
        assert response.output_tokens == 6


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

class TestAnthropicProvider:

    def _engine(self, **kwargs):
        kwargs.setdefault("model", "un-modele-de-test")
        kwargs.setdefault("api_key", "cle-de-test")
        kwargs.setdefault("retry_policy", _policy())
        return AnthropicEngine(**kwargs)

    def test_payload_messages(self, post):
        recorder = post(anthropic_response())

        self._engine().generate(AIRequest(prompt="mon prompt", system_prompt="consigne"))

        payload = recorder.last_payload

        assert recorder.calls[0]["url"].endswith("/v1/messages")
        assert payload["model"] == "un-modele-de-test"
        assert payload["messages"] == [{"role": "user", "content": "mon prompt"}]
        assert payload["system"] == "consigne"

    def test_max_tokens_toujours_present(self, post):
        """Anthropic exige max_tokens : il vient des capacités à défaut."""
        recorder = post(anthropic_response())

        self._engine().generate(AIRequest(prompt="x"))

        assert recorder.last_payload["max_tokens"] > 0

    def test_max_tokens_explicite_respecte(self, post):
        recorder = post(anthropic_response())

        self._engine().generate(AIRequest(prompt="x", max_output_tokens=777))

        assert recorder.last_payload["max_tokens"] == 777

    def test_entetes_authentification(self, post):
        recorder = post(anthropic_response())

        self._engine().generate(AIRequest(prompt="x"))

        entetes = recorder.last_headers

        assert entetes["x-api-key"] == "cle-de-test"
        assert entetes["anthropic-version"] == config.ANTHROPIC_VERSION

    def test_cle_lue_depuis_l_environnement(self, post, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-env")
        recorder = post(anthropic_response())

        AnthropicEngine(model="m", retry_policy=_policy()).generate(AIRequest(prompt="x"))

        assert recorder.last_headers["x-api-key"] == "cle-env"

    def test_usage_normalise(self, post):
        post(anthropic_response(input_tokens=12_450, output_tokens=2_180))

        response = self._engine().generate(AIRequest(prompt="x"))

        assert response.input_tokens == 12_450
        assert response.output_tokens == 2_180
        assert response.total_tokens == 14_630
        assert response.provider == "anthropic"

    def test_blocs_de_texte_concatenes(self, post):
        post(
            FakeHttpResponse(
                {
                    "id": "msg_1",
                    "stop_reason": "end_turn",
                    "content": [
                        {"type": "text", "text": "première "},
                        {"type": "text", "text": "partie"},
                    ],
                }
            )
        )

        response = self._engine().generate(AIRequest(prompt="x"))

        assert response.text == "première partie"
        assert response.finish_reason == "end_turn"
        assert response.request_id == "msg_1"

    def test_reponse_sans_bloc_texte(self, post):
        post(FakeHttpResponse({"content": [{"type": "tool_use"}], "stop_reason": "tool_use"}))

        with pytest.raises(AIResponseError, match="sans bloc de texte"):
            self._engine().generate(AIRequest(prompt="x"))

    def test_content_absent(self, post):
        post(FakeHttpResponse({"id": "msg"}))

        with pytest.raises(AIResponseError, match="'content' absent"):
            self._engine().generate(AIRequest(prompt="x"))

    def test_cle_absente_echoue_clairement(self, post):
        post(anthropic_response())

        with pytest.raises(AIConfigurationError, match="ANTHROPIC_API_KEY"):
            AnthropicEngine(model="m", retry_policy=_policy()).generate(
                AIRequest(prompt="x")
            )

    def test_aucun_modele_configure_echoue_clairement(self):
        """Aucun nom de modèle cloud n'est supposé par la Phase 2."""
        assert config.ANTHROPIC_MODEL == ""

        with pytest.raises(AIConfigurationError, match="ANTHROPIC_MODEL"):
            AnthropicEngine(api_key="k", retry_policy=_policy()).generate(
                AIRequest(prompt="x")
            )

    def test_erreur_401_traduite(self, post):
        post(FakeHttpResponse({}, status_code=401, text="unauthorized"))

        with pytest.raises(AIAuthenticationError):
            self._engine().generate(AIRequest(prompt="x"))

    def test_metadonnees_jamais_transmises(self, post):
        recorder = post(anthropic_response())

        self._engine().generate(
            AIRequest(prompt="x", metadata={"stage": "editorial_planning"})
        )

        assert "metadata" not in recorder.last_payload
        assert "editorial_planning" not in str(recorder.last_payload)

    # -- Structured Outputs natif (Phase 3B.3) ----------------------------

    def test_response_schema_envoie_output_config_json_schema(self, post):
        """
        Le schéma part RÉELLEMENT dans la requête HTTP, sous
        output_config.format — pas seulement annexé au prompt (avant
        Phase 3B.3, il n'était transmis nulle part : ni ici, ni dans le
        prompt, malgré capabilities.supports_structured_output = True).

        Modèle "claude-sonnet-5" utilisé explicitement : c'est le seul dont
        les capacités déclarent supports_structured_output=True (voir
        app/config.py, AI_MODEL_CAPABILITIES). Le modèle de test générique
        ("un-modele-de-test") retombe sur le repli non structuré et ferait
        passer ce test pour une mauvaise raison.

        Depuis Phase 3B.3.1, le schéma transmis est FERMÉ pour Anthropic
        (additionalProperties: false ajouté sur chaque objet, exigé par
        Structured Outputs) : le payload contient donc le schéma canonique
        adapté, pas le schéma canonique tel quel.
        """
        recorder = post(anthropic_response(text='{"titre": "t"}'))
        schema = {"type": "object", "required": ["titre"], "properties": {"titre": {"type": "string"}}}
        snapshot = copy.deepcopy(schema)

        self._engine(model="claude-sonnet-5").generate(
            AIRequest(prompt="analyse", response_schema=schema)
        )

        payload = recorder.last_payload

        assert payload["output_config"] == {
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "required": ["titre"],
                    "properties": {"titre": {"type": "string"}},
                    "additionalProperties": False,
                },
            }
        }
        # Le schéma canonique de la requête n'a pas été muté par la
        # transformation (Phase 3B.3.1, section 5 du protocole).
        assert schema == snapshot
        # Le schéma n'est pas injecté dans le prompt : le prompt reste
        # exactement celui fourni par l'appelant.
        assert payload["messages"] == [{"role": "user", "content": "analyse"}]
        assert "titre" not in payload["messages"][0]["content"]

    def test_sans_response_schema_aucun_output_config(self, post):
        """Comportement texte normal inchangé : aucun output_config envoyé."""
        recorder = post(anthropic_response())

        self._engine().generate(AIRequest(prompt="x"))

        assert "output_config" not in recorder.last_payload

    def test_sans_response_schema_la_transformation_n_est_jamais_appelee(
        self, post, monkeypatch
    ):
        """
        Section 14 du protocole Phase 3B.3.1 : sans response_schema, ni
        output_config.format, ni prepare_anthropic_json_schema() ne doivent
        être invoqués.
        """
        import app.ai.providers.anthropic_engine as anthropic_engine_module

        def _echoue_si_appelee(schema):
            raise AssertionError("prepare_anthropic_json_schema appelée sans response_schema")

        monkeypatch.setattr(
            anthropic_engine_module, "prepare_anthropic_json_schema", _echoue_si_appelee
        )
        recorder = post(anthropic_response())

        self._engine().generate(AIRequest(prompt="x"))

        assert "output_config" not in recorder.last_payload

    def test_schema_source_analyzer_reel_transmis_intact(self, post):
        """
        Le VRAI schéma du Source Analyzer (build_response_schema()) doit
        arriver dans output_config.format.schema fermé pour Anthropic
        (additionalProperties: false sur chaque objet, Phase 3B.3.1) — et
        SANS que le schéma canonique de la requête n'ait été modifié : aucune
        transformation silencieuse du CANONIQUE, seule une copie dédiée part
        au provider.
        """
        from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
        from app.source_analysis.schema import build_response_schema

        schema = build_response_schema()
        snapshot = copy.deepcopy(schema)
        recorder = post(anthropic_response(text="{}"))

        # {} ne respecte pas le schéma réel : la validation locale échoue
        # ensuite, mais ce n'est pas ce que ce test vérifie — seulement que
        # le payload HTTP a bien transporté le schéma (adapté) intact.
        with pytest.raises(AIStructuredOutputError):
            self._engine(model="claude-sonnet-5").generate(
                AIRequest(prompt="analyse", response_schema=schema)
            )

        assert schema == snapshot  # le canonique n'a pas été muté
        assert recorder.last_payload["output_config"]["format"]["schema"] == (
            prepare_anthropic_json_schema(schema)
        )

    def test_payload_reel_source_analyzer_sans_minlength_ni_minitems_incompatible(
        self, post
    ):
        """
        Phase 3B.3.2, section 13 du protocole : audite directement le
        schéma réellement transporté dans le payload HTTP (pas seulement
        le résultat de `prepare_anthropic_json_schema` appelé séparément) —
        `output_config.format.type == "json_schema"`, aucun `minLength`,
        aucun `minItems` hors {0, 1}, et `additionalProperties: false`
        partout.
        """
        from app.ai.providers._anthropic_schema import audit_unsupported_features
        from app.source_analysis.schema import build_response_schema

        schema = build_response_schema()
        recorder = post(anthropic_response(text="{}"))

        with pytest.raises(AIStructuredOutputError):
            self._engine(model="claude-sonnet-5").generate(
                AIRequest(prompt="analyse", response_schema=schema)
            )

        output_format = recorder.last_payload["output_config"]["format"]
        assert output_format["type"] == "json_schema"

        findings = audit_unsupported_features(output_format["schema"])

        assert all(occurrences == [] for occurrences in findings.values()), findings

    def test_json_invalide_reste_rejete_localement_avec_output_config_envoye(
        self, post
    ):
        """
        Même avec Structured Outputs natif demandé, une réponse JSON cassée
        reste rejetée localement (defense in depth) — et l'usage réel du
        fournisseur est conservé sur l'exception (Phase 3B.2, non régressé).
        """
        recorder = post(
            anthropic_response(
                text="{ceci n'est pas du JSON",
                input_tokens=311_362,
                output_tokens=14_494,
            )
        )

        with pytest.raises(AIStructuredOutputError):
            self._engine().generate(
                AIRequest(prompt="x", response_schema={"type": "object"})
            )

        # Le schéma a bien été envoyé à Anthropic : l'échec est un échec de
        # DÉCODAGE local, pas une absence de mécanisme natif.
        assert "output_config" in recorder.last_payload

    def test_json_invalide_conserve_usage_et_cout(self, post):
        recorder = post(
            anthropic_response(
                text="{ trop court",
                input_tokens=1_000,
                output_tokens=200,
                response_id="msg_invalide",
            )
        )

        with pytest.raises(AIStructuredOutputError) as excinfo:
            self._engine().generate(
                AIRequest(prompt="x", response_schema={"type": "object"})
            )

        response = excinfo.value.response

        assert response is not None
        assert response.parsed is None
        assert response.provider == "anthropic"
        assert response.input_tokens == 1_000
        assert response.output_tokens == 200
        assert response.request_id == "msg_invalide"
        assert recorder.call_count == 1  # aucun retry automatique

    def test_schema_invalide_reste_rejete_localement(self, post):
        """JSON syntaxiquement valide mais qui ne respecte pas le schéma."""
        recorder = post(anthropic_response(text='{"autre_champ": 1}'))
        schema = {"type": "object", "required": ["titre"]}

        with pytest.raises(AIStructuredOutputError, match="titre"):
            self._engine().generate(AIRequest(prompt="x", response_schema=schema))

        assert recorder.call_count == 1  # aucun retry automatique

    def test_aucun_retry_automatique_sur_echec_structure(self, post):
        """
        Structured-output/schema failure reste non rejouable : une seule
        tentative HTTP, même avec une politique de rejeu à plusieurs essais.
        """
        recorder = post(anthropic_response(text="pas du JSON du tout"))
        engine = self._engine(retry_policy=no_delay_policy(max_attempts=3))

        with pytest.raises(AIStructuredOutputError):
            engine.generate(AIRequest(prompt="x", response_schema={"type": "object"}))

        assert recorder.call_count == 1

    def test_capability_sonnet_5_correspond_a_un_mecanisme_reellement_utilise(
        self, post
    ):
        """
        capabilities.supports_structured_output = True pour
        anthropic:claude-sonnet-5 ne signifie plus seulement « on sait
        parser du JSON localement » : le moteur envoie réellement
        output_config pour ce modèle exact de configuration.
        """
        recorder = post(anthropic_response(text="{}"))
        engine = AnthropicEngine(
            model="claude-sonnet-5", api_key="cle-de-test", retry_policy=_policy()
        )

        assert engine.supports_native_structured_output("claude-sonnet-5") is True

        engine.generate(AIRequest(prompt="x", response_schema={"type": "object"}))

        assert "output_config" in recorder.last_payload


# ---------------------------------------------------------------------------
# Garanties transverses
# ---------------------------------------------------------------------------

class TestGarantiesTransverses:

    def test_latence_mesuree_sur_horloge_monotone(self, post):
        post(ollama_response())

        response = OllamaEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))

        assert isinstance(response.latency_ms, int)
        assert response.latency_ms >= 0

    def test_echec_ne_fabrique_aucune_reponse(self, post):
        post(requests.exceptions.Timeout())

        with pytest.raises(AITimeoutError):
            OllamaEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))

    def test_journal_sans_prompt_ni_cle(self, monkeypatch):
        """Les logs portent des métriques, jamais le contenu du projet."""
        import app.ai.providers.base as base_module

        evenements = []
        monkeypatch.setattr(base_module, "log_event", evenements.append)

        engine = FakeAIEngine(script=[FakeReply(text="réponse", output_tokens=4)])
        engine.generate(
            AIRequest(
                prompt="CONTENU SECRET DU PROJET",
                system_prompt="CONSIGNE SECRETE",
                metadata={"stage": "source_analysis"},
            )
        )

        journal = str(evenements)

        assert "CONTENU SECRET" not in journal
        assert "CONSIGNE SECRETE" not in journal
        assert "réponse" not in journal

        noms = [event["event"] for event in evenements]
        assert noms == ["ai_call_started", "ai_call_completed"]
        assert evenements[0]["stage"] == "source_analysis"
        assert evenements[0]["prompt_chars"] == len("CONTENU SECRET DU PROJET")
        assert evenements[1]["output_tokens"] == 4

    def test_journal_d_echec(self, monkeypatch):
        import app.ai.providers.base as base_module

        evenements = []
        monkeypatch.setattr(base_module, "log_event", evenements.append)

        engine = FakeAIEngine(script=[AITimeoutError("trop lent")])

        with pytest.raises(AITimeoutError):
            engine.generate(AIRequest(prompt="x", metadata={"stage": "book_validation"}))

        assert [event["event"] for event in evenements] == [
            "ai_call_started",
            "ai_call_failed",
        ]
        assert evenements[1]["error_type"] == "AITimeoutError"
        assert evenements[1]["stage"] == "book_validation"

    def test_capabilities_accessibles_depuis_le_moteur(self):
        caps = FakeAIEngine().capabilities()

        assert caps.provider == "fake"
        assert caps.context_window > 0
        assert caps.usable_context(0.5) == caps.context_window // 2
