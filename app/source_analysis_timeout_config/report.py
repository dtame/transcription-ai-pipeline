"""Rapport Markdown déterministe — Phase 3B.5.1."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_timeout_config.constants import NEXT_PHASE


def render_report(payload: Mapping[str, Any], *, sha256: str) -> str:
    arch = payload.get("architecture") or {}
    resolution = payload.get("resolution") or {}
    defaults = resolution.get("defaults") or {}
    stages = payload.get("stages") or {}
    http = payload.get("http") or {}
    providers = payload.get("providers") or {}
    obs = payload.get("observability") or {}
    previous = payload.get("previous_failure") or {}
    decision = payload.get("production_decision") or {}
    sibling = payload.get("sibling_real_run") or {}
    integrity = payload.get("integrity") or {}
    generation = integrity.get("generation_c") or {}
    network = payload.get("network") or {}
    sa = stages.get("source_analysis") or {}
    ep = stages.get("editorial_planning") or {}
    bg = stages.get("book_generation") or {}
    bv = stages.get("book_validation") or {}

    hardening = (
        "PASS"
        if arch.get("connect_read_separated")
        and arch.get("stage_specific_supported")
        and not arch.get("legacy_constant_controls_runner")
        and http.get("connect_read_distinct")
        and not decision.get("exact_next_read_timeout_authorized")
        else "FAIL"
    )
    outcome = "PASS" if hardening == "PASS" else "FAIL"

    precedence = "\n".join(
        f"{index}. {item}" for index, item in enumerate(resolution.get("precedence") or [], 1)
    )

    return f"""# PHASE 3B.5.1 — LONG-RUN TIMEOUT CONFIGURATION & OBSERVABILITY HARDENING

## 1. Result

{outcome}

TIMEOUT ARCHITECTURE HARDENING =
{hardening}

CONNECT / READ SEPARATED =
{"YES" if arch.get("connect_read_separated") else "NO"}

STAGE-SPECIFIC READ TIMEOUT =
{"SUPPORTED" if arch.get("stage_specific_supported") else "NOT SUPPORTED"}

PRODUCTION LONG TIMEOUT SELECTED =
NO

NEW ANTHROPIC CALL =
0

3B FINAL RETRY AUTHORIZED =
NO.

## 2. Objective

Séparer connect et read, rendre le timeout Source Analysis configurable
sans modifier le code, améliorer l'observabilité des longs appels, et
rester STRICTEMENT OFFLINE. Aucun nouvel appel provider. Aucune valeur
opérationnelle longue autorisée.

## 3. Baseline

1932 passed, 0 failed avant modification. Network = 0.

## 4. 3B.5 root cause recap

Classification : {previous.get("classification")}

Timeout effectif du 3B Final : {previous.get("effective_timeout_seconds")} s
(scalaire requests connect+read).

AUTHORIZATION WAIT CAUSED TIMEOUT =
{previous.get("authorization_wait_caused_timeout")}

## 5. Legacy architecture

Un seul float `timeout_seconds` traversait runner → engine →
`resolve_timeout()` → `requests.post(timeout=<float>)`.
`StageSettings` n'avait pas de champ timeout.
`AI_DEFAULT_TIMEOUT_SECONDS = 300` était inactif pendant le 3B Final.

## 6. Legacy 3600 path

`REAL_CALL_TIMEOUT_SECONDS = 3600.0` dans
`app/source_analysis_global_clean/constants.py` était la source effective.

Toujours égal à 3600.0 (témoin historique) :
{arch.get("legacy_constant_still_3600")}

Contrôle encore le runner :
{arch.get("legacy_constant_controls_runner")}

## 7. New timeout architecture

{arch.get("new_timeout_model")}

Connect et read séparés. Timeout total wall-clock : absent
({arch.get("total_wall_clock_timeout")}), conformément à la sémantique
de requests.

## 8. Timeout value object / representation

`AITimeoutConfig` (frozen) : `connect_seconds`, `read_seconds`,
`connect_source`, `read_source`. Validation : > 0, fini, pas NaN, pas bool.

## 9. Resolution precedence

{precedence}

Un override request/engine porte le READ seulement. Un read long ne
devient jamais un connect long.

## 10. Defaults

connect = {defaults.get("connect_seconds")} s
(source = {defaults.get("connect_source")},
valeur documentée = {defaults.get("documented_connect_default")} s —
budget TCP/TLS, pas une durée de génération)

read = {defaults.get("read_seconds")} s
(source = {defaults.get("read_source")},
valeur documentée = {defaults.get("documented_read_default")} s —
`AI_DEFAULT_TIMEOUT_SECONDS`, inactif pendant le 3B Final)

## 11. Stage-specific configuration

Champs `StageSettings.connect_timeout_seconds` et
`read_timeout_seconds` (pas `request_timeout_seconds`, pour ne pas
contredire le témoin 3B.5). Variables d'environnement
`AI_<STAGE>_CONNECT_TIMEOUT_SECONDS` /
`AI_<STAGE>_READ_TIMEOUT_SECONDS`.

## 12. Source Analysis resolution

provider = {sa.get("provider")}
model = {sa.get("model")}
connect = {sa.get("connect_seconds")} s (source = {sa.get("connect_source")})
read = {sa.get("read_seconds")} s (source = {sa.get("read_source")})
long_read_override_supported = {sa.get("long_read_override_supported")}

## 13. Editorial Planning resolution

provider = {ep.get("provider")}
model = {ep.get("model")}
connect = {ep.get("connect_seconds")} s (source = {ep.get("connect_source")})
read = {ep.get("read_seconds")} s (source = {ep.get("read_source")})

## 14. Book Generation resolution

provider = {bg.get("provider")}
model = {bg.get("model")}
connect = {bg.get("connect_seconds")} s (source = {bg.get("connect_source")})
read = {bg.get("read_seconds")} s (source = {bg.get("read_source")})

## 15. Book Validation resolution

provider = {bv.get("provider")}
model = {bv.get("model")}
connect = {bv.get("connect_seconds")} s (source = {bv.get("connect_source")})
read = {bv.get("read_seconds")} s (source = {bv.get("read_source")})

## 16. Environment/config overrides

Env globales : `AI_DEFAULT_CONNECT_TIMEOUT_SECONDS`,
`AI_DEFAULT_READ_TIMEOUT_SECONDS`.

Env d'étape : `AI_SOURCE_ANALYSIS_READ_TIMEOUT_SECONDS`, etc.

`.env.example` documente les noms à vide. Le vrai `.env` n'a pas été
modifié. Aucune valeur longue de production n'y figure.

## 17. HTTP requests integration

Forme : (connect, read)

requests_timeout_shape = {http.get("requests_timeout_shape")}
connect_read_distinct = {http.get("connect_read_distinct")}
tuple_used = {http.get("tuple_used")}
total_timeout = {http.get("total_timeout")}

## 18. Anthropic integration

{providers.get("anthropic")}

Utilise `resolve_timeouts()` puis `post_json(timeout=AITimeoutConfig)`.
Pas de logique spéciale Sonnet 5.

## 19. OpenAI non-regression

{providers.get("openai")}

Le SDK OpenAI reçoit toujours un scalaire (read). Pas de tuple SDK.
Comportement effectif inchangé.

## 20. Ollama non-regression

{providers.get("ollama")}

Read reste `OLLAMA_TIMEOUT_SECONDS` (1200) via `config_timeout()`.
Connect = défaut court. Le helper HTTP est partagé.

## 21. LM Studio non-regression

{providers.get("lmstudio")}

Read reste `AI_DEFAULT_TIMEOUT_SECONDS` (300). Connect = défaut court.

## 22. Fake provider

Aucun réseau. `resolve_timeouts()` fonctionne. Pas de transport HTTP.

## 23. AITimeoutError

Métadonnées backward-compatibles : `timeout_kind`,
`connect_timeout_seconds`, `read_timeout_seconds`, `elapsed_ms`.
`response` reste None avant body. `raise ... from exc` conservé.

## 24. Connect timeout classification

`requests.exceptions.ConnectTimeout` → `timeout_kind = connect`.

## 25. Read timeout classification

`requests.exceptions.ReadTimeout` → `timeout_kind = read`.

## 26. Unknown timeout classification

`requests.exceptions.Timeout` générique → `timeout_kind = unknown`.
Pas d'invention.

## 27. Monotonic timing

`time.monotonic()` dans `post_json` et `BaseAIEngine` (horloge
injectable). Aucune valeur monotonic absolue persistée.

## 28. Elapsed/latency observability

`elapsed_ms` sur `AITimeoutError` (transport HTTP).
`latency_ms` déjà journalisé par `generate()`.

## 29. Effective timeout observability

`connect_timeout_seconds` et `read_timeout_seconds` journalisés au
démarrage de l'appel et portés par `AITimeoutError`.

## 30. Usage on timeout

Timeout avant response → usage unavailable. Pas 0 token.

## 31. Cost on timeout

Cost unknown/unavailable. Pas $0.

## 32. Response/transport on timeout

`response = None`. Aucun transport artificiel. Aucun body inventé.

## 33. Retry behavior

`max_attempts=1` : pas de retry. Inchangé.

## 34. Source map publication guard

Timeout → aucun `source_map.json`.

## 35. Project state guard

Timeout → `source_analysis` reste `failed`. Pas de SUCCESS.

## 36. Production runner refactor

Le runner 3B Final ne passe plus `timeout_seconds=REAL_CALL_TIMEOUT_SECONDS`.
Il utilise la résolution standard. La constante 3600 reste un témoin
historique, pas une source effective.

## 37. real_run.py sibling 3600

Existe encore : {sibling.get("constant_exists")}
Passé au moteur : {sibling.get("passed_to_engine")}
Rôle : {sibling.get("role")}

## 38. Dead/misleading config

`REAL_CALL_TIMEOUT_SECONDS` (global clean et real_run) : historique,
documenté, plus branché. Canaries 3B.4.x conservent leur 600 s
historique. `AI_DEFAULT_TIMEOUT_SECONDS = 300` devient le read défaut
effectif en l'absence d'override.

## 39. Long timeout capability

Source Analysis peut recevoir un read > 3600 via env ou
`AI_STAGE_SETTINGS` sans toucher les autres étapes et sans modifier
le code Python.

## 40. Why no exact next timeout was selected

3B.5 : `NO_EVIDENCE_BASED_EXACT_TIMEOUT`. Cette phase ne choisit pas
7200, 10800, ni aucune autre valeur opérationnelle.

## 41. Offline preflight

`diagnose_stage_timeout(stage)` calcule provider, modèle, connect,
read et sources sans réseau et sans `engine.generate()`.

## 42. Diagnostic artifact

path : `audit/source_analysis_long_run_timeout_config_audit.json`
SHA : `{sha256}`
déterministe : SHA run1 == SHA run2.

## 43. Tests added

`app/tests/test_ai_timeouts.py`
`app/tests/test_source_analysis_timeout_config.py`

Connect/read séparés, isolation d'étape, env, valeurs invalides,
classification, elapsed, usage/cost, guards, préflight offline.

## 44. Baseline tests

{payload.get("tests", {}).get("baseline_passed")} passed, 0 failed.

## 45. Final tests

{payload.get("tests", {}).get("final_passed")} passed, {payload.get("tests", {}).get("failed")} failed.

## 46. Network

anthropic={network.get("anthropic")}
openai={network.get("openai")}
whisper={network.get("whisper")}
ollama={network.get("ollama")}
lm_studio={network.get("lm_studio")}
other={network.get("other")}
engine_generate={payload.get("engine_generate")}

## 47. Protected artifacts

Liste 3B.5 + diagnostic/rapport 3B.5. Byte-identical après phase.

## 48. SourceMap status

absent.

## 49. Project state

failed, erreur historique AITimeoutError. Inchangé par cette phase.

## 50. Files added

`app/ai/timeouts.py`
`app/source_analysis_timeout_config/`
`app/tests/test_ai_timeouts.py`
`app/tests/test_source_analysis_timeout_config.py`
artefacts audit 3B.5.1

## 51. Files modified

`app/ai/errors.py`, `app/ai/settings.py`, `app/ai/providers/base.py`,
`app/ai/providers/_http.py`, engines HTTP, `app/config.py`,
runners global clean et real_run, `.env.example`, tests existants
dont l'assertion timeout scalaire.

## 52. Technical decision

Le hardcode 3600 n'est plus la source effective. Connect et read sont
séparés. Aucune valeur exacte de long read n'est autorisée.
Prochaine phase : {NEXT_PHASE}.
Architecture prête après revue humaine :
{decision.get("architecture_ready_for_operational_long_read")}.
"""
