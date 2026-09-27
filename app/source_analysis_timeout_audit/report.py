"""Rapport markdown Phase 3B.5 — structure imposée par le protocole."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_global_clean.constants import REAL_CALL_TIMEOUT_SECONDS
from app.source_analysis_timeout_audit.constants import (
    DIAGNOSTIC_ARTIFACT_NAME,
    REPORT_NAME,
)


def _yn(value) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    if value is None:
        return "UNKNOWN"
    return str(value)


def _bool(value) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "n/a"


def _layers_table(layers: list[Mapping[str, Any]]) -> str:
    lines = [
        "| Layer | File | Symbol | Type | Configured | Default | Effective 3B Final | Timeout kind | Exception | Wrapping | Retry | Stage-specific? | Active in 3B Final? |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for layer in layers:
        lines.append(
            "| {layer} | `{file}` | `{symbol}` | {type} | {cfg} | {default} | {eff} | {kind} | {exc} | {wrap} | {retry} | {stage} | {active} |".format(
                layer=layer.get("layer"),
                file=layer.get("file") or "n/a",
                symbol=layer.get("symbol") or "n/a",
                type=layer.get("type"),
                cfg=layer.get("configured_seconds"),
                default=layer.get("default_seconds"),
                eff=layer.get("effective_seconds"),
                kind=layer.get("timeout_kind"),
                exc=layer.get("exception") or "n/a",
                wrap=layer.get("exception_wrapping") or "n/a",
                retry=layer.get("retry_behavior"),
                stage=_bool(layer.get("stage_specific")),
                active=_bool(layer.get("active_in_failed_run")),
            )
        )
    return "\n".join(lines)


def _chain(rows: list[Mapping[str, Any]]) -> str:
    lines = []
    for row in rows:
        lines.append(
            f"- **{row.get('layer')}** : {row.get('incoming')} → {row.get('outgoing')}"
            f" ; wrap={_bool(row.get('wrapped'))}"
            f" ; response={_bool(row.get('response_attached'))}"
            f" ; usage={_bool(row.get('usage_attached'))}"
        )
    return "\n".join(lines)


def render_report(payload: Mapping[str, Any], *, sha256: str) -> str:
    failed = payload.get("failed_run") or {}
    effective = payload.get("effective_timeout") or {}
    auth = payload.get("authorization_wait") or {}
    http = payload.get("http") or {}
    decision = payload.get("decision") or {}
    request = payload.get("failed_request") or {}
    architecture = payload.get("architecture") or {}
    canary = payload.get("canary_comparison") or {}
    origin = payload.get("aitimeouterror_origin") or {}
    clock = payload.get("clock") or {}
    streaming = payload.get("streaming_option") or {}
    network = payload.get("network") or {}
    layers = list(payload.get("timeout_layers") or [])
    chain = list(payload.get("exception_chain") or [])
    gaps = list(payload.get("observability_gaps") or [])
    risks = list(architecture.get("global_run_risks") or [])
    benefits = list(architecture.get("global_run_benefits") or [])
    canary_small = canary.get("canary_3b45") or {}
    canary_final = canary.get("final_3b") or {}
    timeout_cfg = architecture.get("timeout_config") or {}

    return f"""# PHASE 3B.5 — GLOBAL TIMEOUT ROOT-CAUSE AUDIT

## 1. Result

PASS

ROOT CAUSE CLASSIFICATION = {decision.get("primary_classification")}

AUTHORIZATION WAIT CAUSED TIMEOUT =
{_yn(auth.get("counts_toward_timeout"))}

EFFECTIVE TIMEOUT =
{effective.get("seconds")} seconds
({effective.get("source")})

INCREASING 3600 ONLY SUFFICIENT =
{decision.get("increase_3600_only_sufficient")}

NEW ANTHROPIC CALLS =
0.

## 2. Objective

Déterminer offline où le timeout 3600 s est défini, quelle couche l'applique,
quelle couche a produit AITimeoutError, et si augmenter uniquement cette
valeur suffirait. Aucun appel réseau. Aucune modification du timeout de
production.

## 3. Failed 3B Final recap

- error : `{failed.get("error")}`
- configured guard : {failed.get("configured_guard_seconds")} s
- provider body received : {_bool(failed.get("provider_body_received"))}
- transport created : {_bool(failed.get("transport_created"))}
- source_map published : {_bool(failed.get("source_map_published"))}

Le run a consommé son unique appel Anthropic autorisé. Aucun body exploitable.
Aucun `source_analysis_global_clean_transport.json`. `source_analysis` reste
`failed`.

## 4. Baseline

Commande : `.venv\\Scripts\\python.exe -m pytest -q`

Avant modification : 1909 passed, 0 failed.

## 5. Artifacts inspected

- `audit/source_analysis_global_clean_dry_run.json`
- `audit/source_analysis_global_clean_result.json`
- `audit/PHASE_3B_FINAL_GLOBAL_CLEAN_SOURCE_ANALYZER_REPORT.md`
- `project_state.json` (lecture seule)
- code : runner 3B Final, `real_run.py`, `AnthropicEngine`, `_http.post_json`,
  `BaseAIEngine`, `RetryPolicy`, `StageSettings`

Aucun de ces artefacts historiques n'a été modifié.

## 6. Repository timeout inventory

Occurrences pertinentes de `3600` :

- `app/source_analysis_global_clean/constants.py` — `REAL_CALL_TIMEOUT_SECONDS = 3600.0`
  (valeur active du run 3B Final)
- `app/source_analysis/real_run.py` — même constante, runner frère, non utilisé
  par 3B Final
- autres `3600` : formatage HH:MM:SS ou durées audio de tests, hors chemin IA

Autres timeouts :

- `app/config.py` `AI_DEFAULT_TIMEOUT_SECONDS = 300` — surchargé, inactif
- canaries 3B.4.x : `REAL_CALL_TIMEOUT_SECONDS = 600.0` — hors run
- `OLLAMA_TIMEOUT_SECONDS = 1200` — mauvais provider
- `cover_image_engine` / `cover_engine` timeout 300 — hors Source Analyzer
- aucun `future.result`, `wait_for`, `HTTPAdapter`, `subprocess` timeout sur
  le chemin 3B Final

## 7. Timeout layers

{_layers_table(layers)}

## 8. Effective timeout hierarchy

Pour 3B Final :

1. `AIRequest.timeout_seconds` = None (non posé)
2. `engine._timeout_seconds` = 3600.0 (constructeur)
3. `config_timeout()` / `AI_DEFAULT_TIMEOUT_SECONDS` = 300 — **non utilisé**
4. `requests.post(timeout=3600)` — connect=3600 et read=3600
5. aucun `wait_for` / Future / subprocess
6. `max_attempts=1` — pas de retry qui prolongerait

Une seule limite locale active : 3600 s.

LOWEST_ACTIVE_TIMEOUT = {effective.get("lowest_active_timeout_seconds")}
HIGHEST_ACTIVE_TIMEOUT = {effective.get("highest_active_timeout_seconds")}

## 9. 3600 origin

- file : `app/source_analysis_global_clean/constants.py`
- symbol : `REAL_CALL_TIMEOUT_SECONDS`
- kind : hardcoded constant (ni CLI, ni env, ni StageSettings)
- resolution : runner → `get_ai_engine(..., timeout_seconds=3600)` →
  `resolve_timeout()` → `post_json(timeout=3600)` → `requests.post(timeout=3600)`
- OVERRIDDEN_BY = none

`real_run.py` définit la même constante mais n'est pas le runner 3B Final.

## 10. Timeout clock start

TIMEOUT_CLOCK_STARTS_AT =
{auth.get("timeout_clock_starts_at")}

Le chrono d'abort est celui de `requests` / urllib3, démarré à
`requests.post()`. L'horloge monotone de `generate()` mesure la latence et
ne coupe pas l'appel. Le préflight, l'écriture dry-run et le contrôle de
credential sont **avant** `generate()`.

## 11. Human authorization wait

AUTHORIZATION_WAIT_COUNTS_TOWARD_TIMEOUT = {_yn(auth.get("counts_toward_timeout"))}

{auth.get("evidence")}

L'autorisation Cursor d'une commande avant le lancement du processus Python
est hors de ce chrono. Le code applicatif n'a aucune étape d'autorisation.

## 12. Anthropic HTTP implementation

- client : `{http.get("client")}` (pas le SDK `anthropic`)
- POST : `{{base_url}}/v1/messages`
- timeout : `{http.get("timeout_argument")}`
- streaming : {_bool(http.get("streaming"))}
- response mode : {http.get("response_mode")}
- payload : `output_config.format` json_schema, pas de champ `stream`

## 13. Connect timeout

{http.get("connect_timeout")} seconds.

Un scalaire `timeout=3600` vaut connect=3600 **et** read=3600 d'après la
doc locale de `requests`. Ce n'est pas un timeout total.

Une connexion à api.anthropic.com s'établit habituellement en secondes.
Le run a consommé le guard de 3600 s : la limite effective est donc le
**read** timeout, pas le connect. Le code ne distingue pas
`ConnectTimeout` vs `ReadTimeout` dans l'artefact (les deux deviennent
`AITimeoutError`).

## 14. Read timeout

{http.get("read_timeout")} seconds.

En non-streaming, le client attend le body final. Si le serveur n'envoie
aucun octet pendant 3600 s, `requests.exceptions.Timeout` est levé.

## 15. Total/runner timeout

total_timeout = {http.get("total_timeout")}

Aucun timeout total distinct. Aucun watchdog runner séparé : la constante
3600 **est** le timeout HTTP, pas un `wait_for` autour de `generate()`.

## 16. Future/thread/subprocess guards

Absents sur le chemin 3B Final. `RealCallGuard` compte les appels, il ne
mesure pas le temps.

## 17. Exception chain

{_chain(chain)}

## 18. AITimeoutError origin

AITimeoutError n'est **pas** levée par un timer interne applicatif.

Elle est construite dans `{origin.get("constructed_in")}` après capture de
`{origin.get("after_capture_of")}`.

`exc.response` reste None : aucun `ProviderResult` n'existait.

## 19. Retry behavior

`max_attempts = 1`. `retry = false`. Un timeout n'est pas rejoué.
`actual_real_calls = 1`.

## 20. Response/body behavior

Aucun body JSON exploitable. `_extract_text` n'a pas été atteint.
On ne peut pas savoir si un premier octet HTTP était arrivé : pas
d'instrumentation first-byte.

## 21. Transport behavior

Aucun transport n'a été créé. Correct : le runner n'écrit le transport
que si une `AIResponse` est attachée à l'exception. Un timeout de
transport n'en a pas. Aucun `{{}}` inventé.

## 22. Usage behavior

`usage_source` unavailable. `input_tokens` / `output_tokens` = None.
Ce n'est pas zéro. L'application n'a reçu aucun compteur provider.

## 23. Cost behavior

`cost.status = unavailable` / `unknown`. Cela signifie :

**l'application n'a reçu aucune donnée permettant de calculer le coût**

et **non** « Anthropic n'a rien facturé ».

{payload.get("cost_meaning")}

## 24. Request ID behavior

Le request ID n'est lu que dans le JSON de succès (`data.get("id")`).
Sans body, aucun identifiant local. Non récupérable depuis les données
locales. Pas de reprise possible via l'application.

request_id_recoverable = {_bool(payload.get("request_id_recoverable"))}

## 25. Could provider have continued?

{payload.get("provider_continuation")}

Le client abandonne la connexion HTTP. Le code local ne peut pas savoir
si Anthropic a annulé, continué, ou terminé plus tard. Aucune API de
cancel/status n'existe dans ce dépôt.

## 26. Failed request size

- segments : {request.get("segments")}
- words : {request.get("words")}
- estimated input tokens : {request.get("estimated_input_tokens")}
- usable input budget : {request.get("usable_input_budget")}
- remaining margin : {request.get("remaining_margin")}
- max output tokens : {request.get("max_output_tokens")}
- corpus fits context budget : {_bool(request.get("corpus_fits_context_budget"))}

## 27. Canary comparison

3B.4.5 : {canary_small.get("segments")} SRC, {canary_small.get("words")} words,
estimated {canary_small.get("estimated_total_preflight")}, provider
{canary_small.get("provider_input_tokens")} input +
{canary_small.get("provider_output_tokens")} output,
{canary_small.get("latency_ms")} ms.

3B Final : {canary_final.get("segments")} segments,
{canary_final.get("words")} words, estimated
{canary_final.get("estimated_input_tokens")}, timeout
{canary_final.get("timeout_seconds")} s, no body.

## 28. Scaling caveat

CANARY_SCALING_IS_NOT_LINEARLY_PREDICTIVE = {_bool(canary.get("CANARY_SCALING_IS_NOT_LINEARLY_PREDICTIVE"))}

Aucune extrapolation linéaire du ratio 37.3 s → corpus global n'est
autorisée ni effectuée.

## 29. Global single-call risks

{chr(10).join(f"- {item}" for item in risks)}

## 30. Global single-call benefits

{chr(10).join(f"- {item}" for item in benefits)}

## 31. Multi-window current status

`plan_windows()` existe. La consolidation multi-fenêtres n'est pas
implémentée ni autorisée. Le runner 3B Final exige `strategy=global`.
Non implémenté dans cette phase.

## 32. Timeout configuration architecture

- défaut global : `AI_DEFAULT_TIMEOUT_SECONDS` (300)
- runner-specific hardcoded : `REAL_CALL_TIMEOUT_SECONDS` (3600)
- per-request : `AIRequest.timeout_seconds` (non utilisé ici)
- per-engine constructor : `timeout_seconds=`
- StageSettings : **pas de champ timeout**

{timeout_cfg.get("can_set_source_analysis_without_other_stages")}

## 33. Stage-specific capability

Aujourd'hui on peut changer uniquement
`app/source_analysis_global_clean/constants.py:REAL_CALL_TIMEOUT_SECONDS`
sans toucher editorial_planning / book_generation / book_validation /
canaries, parce que cette constante est locale au runner 3B Final.

Ce n'est pas une capacité StageSettings. Proposition pour la phase
suivante (non implémentée) :

`StageSettings.request_timeout_seconds` lu depuis
`AI_STAGE_SETTINGS["source_analysis"]`.

## 34. Observability gaps

{chr(10).join(f"- {item}" for item in gaps)}

Ne pas inventer un pourcentage de progression provider : l'API utilisée
ne le fournit pas. Distinguer elapsed time de provider progress.

## 35. Streaming option

Implemented : {_bool(streaming.get("implemented"))}

Read-timeout reset si chunks : {streaming.get("would_reset_read_timeout_if_chunks_arrive")}

Préservation partielle : {streaming.get("partial_response_preservation")}

Compatibilité structured output natif :
{streaming.get("structured_output_compatibility")}

Non implémenté. Vérification externe requise.

## 36. Async/batch option

{payload.get("async_batch_option")}

Absent du code et des docs locales. Ne pas inventer une capacité provider.

## 37. Recommendation

PRIMARY = HTTP_READ_TIMEOUT_TOO_SHORT

Le 3600 s actif est le timeout HTTP connect+read de `requests`. Il n'y a
pas d'autre limite locale plus basse. Augmenter cette seule valeur
permettrait **localement** d'attendre plus longtemps.

Cela ne prouve pas qu'un second appel réussirait. Risques secondaires :
architecture d'un unique très gros appel non-streaming ; limite upstream
non excludable.

Avant tout nouvel appel payant : configuration explicite + observabilité
(phase 3B.5.1). Pas de retry 3B maintenant.

## 38. Candidate next timeout

CURRENT_EFFECTIVE_TIMEOUT = {REAL_CALL_TIMEOUT_SECONDS}

MINIMUM_OTHER_ACTIVE_LIMIT = none (local)

SAFE_NEXT_TEST_TIMEOUT_CANDIDATE = {decision.get("next_timeout_candidate_seconds")}

JUSTIFICATION = {decision.get("next_timeout_justification")}

CONFIDENCE = {decision.get("next_timeout_confidence")}

Aucune valeur (7200 ou autre) n'est scientifiquement justifiable ici.

## 39. Confidence

Classification de la couche : {decision.get("recommendation_confidence")}

Valeur numérique suivante : {decision.get("next_timeout_confidence")}

## 40. Would increasing only 3600 be sufficient?

{decision.get("increase_3600_only_sufficient")}

Justification : une seule limite locale active, identique au HTTP
connect+read. Aucun runner guard plus bas. Limite Anthropic/proxy :
UNKNOWN.

## 41. Is another lower timeout active?

{decision.get("lower_timeout_elsewhere")}

Couches locales plus basses : aucune. Upstream : UNKNOWN.

## 42. Did human authorization consume the timeout?

{_yn(auth.get("counts_toward_timeout"))}

Le chrono d'abort commence à `requests.post()`, après `generate()`.
L'autorisation humaine de la tâche Cursor est hors processus.

## 43. Required changes before another paid call

1. Ne pas relancer 3B Final maintenant.
2. Phase 3B.5.1 : timeout configurable (stage ou runner) + observabilité
   (monotonic start, sous-classe Timeout, elapsed, effective timeout dans
   le result, request id dès que possible).
3. Revue humaine de la valeur et du risque d'appel global unique.
4. 3B.6 (redesign) reste une option stratégique, pas la conclusion forcée
   de cet audit.

Nouveau run Anthropic autorisé maintenant : NON.

## 44. Tests

Baseline : 1909 passed, 0 failed.

Nouveaux tests offline : configuration, traduction d'exception, pas de
retry, usage/coût unknown, pas de transport, pas de publication, pas de
SUCCESS, déterminisme, garde réseau.

## 45. Network

- Anthropic : {network.get("anthropic", 0)}
- OpenAI : {network.get("openai", 0)}
- Whisper : {network.get("whisper", 0)}
- Ollama : {network.get("ollama", 0)}
- LM Studio : {network.get("lm_studio", 0)}
- other : {network.get("other", 0)}

## 46. Protected artifacts

Tous les artefacts historiques listés (transcripts, cleanup, 3B.4.x,
3B Final dry-run/result/report) doivent rester byte-identical.

`analysis/source_map.json` reste absent.
`project_state.source_analysis` reste `failed` / `AITimeoutError`.

## 47. Diagnostic artifact

- path : `audit/{DIAGNOSTIC_ARTIFACT_NAME}`
- SHA-256 : `{sha256}`
- déterminisme : run1 == run2

## 48. Files modified

Ajouts uniquement :

- `app/source_analysis_timeout_audit/*`
- `app/tests/test_source_analysis_timeout_audit.py`
- `audit/{DIAGNOSTIC_ARTIFACT_NAME}`
- `audit/{REPORT_NAME}`

Timeout de production inchangé : {effective.get("production_timeout_unchanged")}
(`REAL_CALL_TIMEOUT_SECONDS` reste 3600.0).

## 49. Technical decision

Où 3600 est-il défini ?
`app/source_analysis_global_clean/constants.py:REAL_CALL_TIMEOUT_SECONDS`

Est-il hardcoded ?
Oui.

Quelle couche applique ce délai ?
`requests.post(timeout=3600)` via `post_json` / `AnthropicEngine._invoke`.

Quand le compteur commence-t-il ?
À l'émission du POST HTTP, pas avant l'autorisation humaine, pas pendant
le préflight.

Le temps d'autorisation humaine compte-t-il ?
NON.

Quel client HTTP est utilisé ?
`requests` (pas le SDK Anthropic).

Streaming ou non ?
NON_STREAMING.

Quel connect timeout ?
3600 s (scalaire).

Quel read timeout ?
3600 s (scalaire).

Quel total timeout ?
Aucun.

Existe-t-il un runner guard séparé ?
Non. La constante 3600 **est** le timeout HTTP.

Existe-t-il un Future/thread timeout ?
Non.

Quelle exception basse couche a été transformée en AITimeoutError ?
`requests.exceptions.Timeout` (parent de ConnectTimeout et ReadTimeout).

Quelle couche fait cette transformation ?
`app/ai/providers/_http.py:post_json`

Quelle est la limite active la plus basse ?
3600 s.

Le provider body avait-il commencé à arriver ?
UNKNOWN. Aucune observabilité first-byte.

Anthropic a-t-il pu continuer côté serveur après notre abandon ?
UNKNOWN.

Pourquoi aucun transport n'a-t-il été créé ?
Timeout avant `ProviderResult` / `AIResponse` : le runner n'écrit un
transport que si une réponse est attachée.

Pourquoi usage/cost sont-ils unknown plutôt que zéro ?
Aucun compteur provider reçu. Un zéro serait un chiffre inventé.

Le request ID est-il récupérable depuis les données locales ?
NON.

Le corpus tenait-il toujours dans le context budget ?
OUI (142953 estimés, budget 572000, marge 429047).

Max output était-il 128000 ?
OUI.

Le timeout est-il configurable par stage ?
NON (pas de champ StageSettings). Runner-hardcoded seulement.

Changer seulement 3600 permettrait-il réellement d'attendre plus longtemps ?
LIKELY, localement. Upstream UNKNOWN.

Une autre limite couperait-elle avant ?
NON localement. UNKNOWN upstream.

Quelle valeur recommander pour un prochain test ?
NO_EVIDENCE_BASED_EXACT_TIMEOUT.

Avec quel niveau de confiance ?
HIGH pour la couche. LOW pour toute valeur suivante.

Faut-il simplement augmenter le timeout ou envisager une adaptation
architecturale avant un second run ?
D'abord 3B.5.1 (config + observabilité). Le risque d'appel global unique
est documenté mais ne force pas l'abandon. 3B.6 reste optionnel.

Un nouveau run Anthropic est-il autorisé maintenant ?
NON.

Quelle est exactement la prochaine phase recommandée ?
3B.5.1 — LONG-RUN TIMEOUT CONFIGURATION & OBSERVABILITY HARDENING

Ne pas l'exécuter maintenant.
"""
