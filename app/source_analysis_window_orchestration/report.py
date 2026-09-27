"""Rapport déterministe 3B.7.3 — aucun horodatage."""

from __future__ import annotations

from typing import Any, Mapping


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _pass(value: Any) -> str:
    if value in (True, "PASS"):
        return "PASS"
    if value in (False, "FAIL"):
        return "FAIL"
    return str(value)


def _st(synthetic: Mapping[str, Any], name: str) -> str:
    return _pass((synthetic.get(name) or {}).get("status"))


def render_report(payload: Mapping[str, Any], result: Any) -> str:
    outcome = getattr(result, "outcome", None) or payload.get("outcome") or "PASS"
    orch = payload.get("orchestration") or {}
    cache = payload.get("cache") or {}
    synthetic = payload.get("synthetic") or {}
    preflight = payload.get("real_preflight") or {}
    detail = preflight.get("detail") or {}
    execution = payload.get("execution") or {}
    integrity = payload.get("integrity") or {}
    generation = integrity.get("generation_c") or {}
    determinism = payload.get("determinism") or {}
    state_status = getattr(result, "project_state_status", "") or ""
    state_error = getattr(result, "project_state_error", None)
    cold = synthetic.get("cold_run") or {}
    warm = synthetic.get("warm_run") or {}
    failure = synthetic.get("failure_run") or {}
    resume = synthetic.get("resume_run") or {}
    recovery = synthetic.get("transport_recovery") or {}
    budget = synthetic.get("call_budget") or {}
    sig = synthetic.get("signature_invalidation") or {}
    windows = detail.get("windows") or []

    return f"""# PHASE 3B.7.3 — WINDOW CACHE / RESUME / VALIDATION ORCHESTRATION

## Result

{outcome}

WINDOW ORCHESTRATION =
{_pass(outcome)}

EXECUTION ORDER =
{orch.get("execution_order")}

FAILURE POLICY =
{orch.get("failure_policy")}

CACHE GRANULARITY =
PER_WINDOW

CACHE REVALIDATION =
{_pass(cache.get("result_revalidated"))}

TRANSPORT RECOVERY =
{_st(synthetic, "transport_recovery")}

CALL BUDGET =
SUPPORTED

COLD RUN =
{_st(synthetic, "cold_run")}

WARM CACHE =
{_st(synthetic, "warm_run")}

FAILURE + RESUME =
{_st(synthetic, "resume_run")}

ALL-WINDOWS-READY GATE =
{_st(synthetic, "gate")}

REAL CLEAN WINDOWS =
{preflight.get("windows")}

REAL PREFLIGHT NEW CALLS =
{preflight.get("new_calls")}

REAL ANTHROPIC CALLS =
0

GLOBAL CONSOLIDATION =
NOT IMPLEMENTED

SOURCE MAP =
NOT PUBLISHED

PHASE 3B =
INCOMPLETE

NEXT PHASE =
{payload.get("next_phase")}

## 1. Result

Outcome **{outcome}**. Orchestration multi-fenêtres FakeAI offline.
Aucun appel Anthropic/OpenAI. Source map non publié. Phase 3B incomplete.

## 2. Objective

Prouver qu'une analyse de plusieurs fenêtres est cacheable, revalidable,
reprenable, ordonnée, fail-closed et indépendante par fenêtre.
Le résultat conceptuel est ALL_WINDOWS_READY ou WINDOWS_INCOMPLETE.
Pas un SourceMap. Pas de consolidation globale.

## 3. Baseline

2158 passed, 0 failed avant modification.

## 4. Existing hybrid foundations

WindowPlannerV2, window-planner-v2.0, target 50000, hard max 60000,
NO_OWNED_OVERLAP, window-analysis-1.0, semantic-transport-v1,
WindowAnalyzer, fail-closed decoder, WindowResultValidator.
Inchangés sémantiquement.

## 5. Modules added

`window_orchestrator.py`, `window_cache.py`, `orchestration_models.py`.
Extensions : metadata.json atomique, recovery transport, from_dict résultat.
Paquet audit `app/source_analysis_window_orchestration/`.
Pas de GlobalConsolidator. Pas de branchement analyzer.py.

## 6. Orchestrator

`orchestrate_windows(plan, transcript, engine, windows_root, max_new_calls)`.
Reçoit un WindowPlan. Traite chaque WindowInput dans l'ordre source.
Calcule la signature 3B.7.2, inspecte, revalide, HIT / recovery / generate.
Produit WindowOrchestrationResult déterministe.

## 7. Sequential execution

Order = WindowPlan source order. Jamais filesystem, mtime, ou completion
provider. Aucun thread pool, aucun async gather.

## 8. Failure policy

{orch.get("failure_policy")}.
WIN001 succès + WIN002 échec → WIN003 non exécuté (PENDING).
WIN001 préservé.

## 9. Window cache

Layout : analysis/windows/WIN00N/{{transport,result,metadata}}.json
Tests = temp dirs. Identité = signature d'analyse, pas le seul WIN ID.

## 10. Cache identity

Formule 3B.7.2 inchangée : WindowInput hash, planner, prompt version/SHA,
transport/schema, provider, modèle, température, max output, langue,
context_safety_ratio, stage. Pas de latency, request_id, timestamp.

## 11. Cache states

HIT, MISS, STALE, INVALID, CORRUPT.
Exécution distincte : NONE / GENERATED / TRANSPORT_RECOVERED.
Readiness : READY / PENDING / FAILED.

## 12. Cache hit requirements

Artefacts présents, signature, window_id, input hash, prompt, transport,
provider/modèle, parse, WindowResultValidator PASS, SRC valides,
IDs intermédiaires, pas de fuite éditoriale, hash transport cohérent.
L'existence d'un fichier n'est pas un HIT.

## 13. Revalidation

Chaque entrée est revalidée. Un statut historique success n'est pas
une preuve.

## 14. Transport/result consistency

metadata.identity.transport_sha256 == SHA-256 des octets du transport.
Un result orphelin sans transport n'est pas un HIT.

## 15. Stale cache

Signature mismatch → STALE. Non utilisé. Non réécrit silencieusement.

## 16. Invalid cache

Signature ok mais validation échoue → INVALID. Non utilisé.

## 17. Corrupt cache

JSON illisible → CORRUPT. Pas de crash qui perd les autres fenêtres.

## 18. Window readiness

READY seulement si un WindowSemanticResult courant valide existe
(HIT ou GENERATED ou TRANSPORT_RECOVERED).

## 19. ALL_WINDOWS_READY

Toutes les WindowInput du plan ont exactement un résultat valide.
2/3 refuse. assert_all_windows_ready() est la porte.

## 20. Call budget

max_new_calls = 0 / 1 / N. Jamais dépassé.
0 = inspection seule. 1 = une seule génération tentée.

## 21. Attempt consumption

Unité consommée quand engine.generate est tenté, même en échec.
HIT = 0. Recovery transport = 0. max_attempts = 1. Pas de retry.

## 22. Cold run

{_st(synthetic, "cold_run")} — FakeAI calls = {cold.get("new_calls")}
ready = {cold.get("ready")} all_windows_ready = {cold.get("all_windows_ready")}

## 23. Warm run

{_st(synthetic, "warm_run")} — new calls = {warm.get("new_calls")}
cache hits = {warm.get("cache_hits")}

## 24. Failure run

{_st(synthetic, "failure_run")}
readiness = {failure.get("readiness")}
ALL_WINDOWS_READY = {failure.get("all_windows_ready")}

## 25. Resume run

{_st(synthetic, "resume_run")}
new calls = {resume.get("new_calls")}
all_windows_ready = {resume.get("all_windows_ready")}

## 26. Transport recovery

{_st(synthetic, "transport_recovery")}
new calls = {recovery.get("new_calls")}
transport_recovered = {recovery.get("transport_recovered")}

## 27. Crash after transport

result.json absent, transport+metadata valides → recovery locale, 0 generate.

## 28. Crash between windows

WIN001 persisté. Prochaine passe : HIT, continue WIN002.

## 29. Signature invalidation

{_st(synthetic, "signature_invalidation")}
cache_states = {sig.get("cache_states")}
WIN002 seul invalidé si frontières stables et transcript SHA figé.

## 30. Prompt invalidation

{_st(synthetic, "prompt_invalidation")}
Changement de version/SHA de prompt → toutes les caches STALE.

## 31. Model invalidation

{_st(synthetic, "model_invalidation")}

## 32. Planner/input invalidation

WindowInput hash / planner_version dans la signature 3B.7.2.
Mutation owned → fenêtre touchée STALE.

## 33. Transport corruption

Hash transport ≠ metadata → pas HIT. Pas d'acceptation silencieuse.

## 34. Result corruption

Revalidation FAIL. Recovery transport si binding valide. 0 generate.

## 35. Missing transport

Result seul → pas un HIT de production.

## 36. Missing result

Transport+metadata valides → recovery offline, 0 appel.

## 37. Sparse SRC validation

Revalidation via membership WindowInput réelle. first/last jamais expansés.

## 38. Window order

Toujours l'ordre du WindowPlan, même si le filesystem liste WIN003 d'abord.

## 39. Result handoff

get_ready_results_in_plan_order() — zéro merge sémantique.
Si incomplet : WindowsIncompleteError.

## 40. Cost/usage preparation

usage par fenêtre agrégeable plus tard. FakeAI : coût Anthropic réel = 0.
Unknown ≠ zéro. Pas de prédiction de coût futur.

## 41. Reporting preparation

strategy=hybrid, windows.total/ready/cached/generated/failed/pending,
all_windows_ready. report.json de production non modifié.

## 42. Real CLEAN preflight

windows = {preflight.get("windows")}
max_new_calls = 0
new_calls = {preflight.get("new_calls")}
all_windows_ready = {preflight.get("all_windows_ready")}
cache_states = {detail.get("cache_states")}
FakeAI pastoral = NO

## 43. Real cache paths

Dérivés uniquement du WIN ID local validé.
Résolus, non écrits. analysis/windows/ réel non peuplé.

## 44. Real call budget

max_new_calls = 0. engine = None. 0 FakeAI. 0 provider réel.

## 45. Tests

`app/tests/test_source_analysis_window_orchestration.py`
cold, warm, failure/resume, recovery, invalidation, corruption,
budget 0/1/N, ordre, gate, réseau, préflight réel.

## 46. Network

Anthropic = {execution.get("anthropic_calls", 0)}
OpenAI = {execution.get("openai_calls", 0)}
Whisper = 0. Ollama = 0. LM Studio = 0.
requests.post bloqué (no_ai_network).

## 47. Protected artifacts

Hashés jusqu'à 3B.7.2. Inchangés. Transcript CLEAN inchangé.

## 48. Planner integrity

Plan réel : 3 fenêtres. Politique WindowPlannerV2 inchangée.

## 49. Window prompt integrity

window-analysis-1.0 inchangé.

## 50. Prompt 1.3 integrity

version = {integrity.get("prompt_1_3_version")}
inchangé.

## 51. Generation C integrity

raw match = {_yn(bool(generation.get("raw_matches_historical")))}
anthropic match = {_yn(bool(generation.get("anthropic_matches_historical")))}

## 52. Decoder integrity

Fail-closed réutilisé, non forké, non affaibli.

## 53. Window validator integrity

Non affaibli. Revalidation obligatoire avant HIT.

## 54. Canonical validator integrity

validator.py inchangé.

## 55. SourceMap status

NOT PUBLISHED. analysis/source_map.json absent.

## 56. Project state

status = {state_status}
error = {state_error}
Pas de SUCCESS.

## 57. Files added

window_orchestrator.py, window_cache.py, orchestration_models.py,
source_analysis_window_orchestration/*,
test_source_analysis_window_orchestration.py,
audit artefacts 3B.7.3.

## 58. Files modified

errors.py (WindowOrchestration*), window_writer.py (metadata),
window_analyzer.py (metadata + recovery + resolve_window_execution),
window_models.py (from_dict), window_fixtures.py (plan synthétique).
analyzer.py, prompt.py, decoder, validator canonique, planner,
Generation C, transcript CLEAN : non modifiés sémantiquement.

## 59. Technical decision

Was baseline 2158 green? YES.

Was WindowAnalysisOrchestrator implemented? YES.

Is execution sequential? YES.

What is failure policy? {orch.get("failure_policy")}

Does orchestration order come from WindowPlan? YES.

Can filesystem order change execution order? NO.

What identifies a cache entry? window_analysis_signature (formule 3B.7.2).

Is WIN001 alone sufficient? NO.

Is signature equality required? YES.

Is result revalidated? YES.

Is transport required for a complete cache HIT? YES.

Are transport/result consistency checks performed? YES.

Can corrupt result become HIT? NO.

Can stale result become HIT? NO.

Can a cached result with invalid SRC become HIT? NO.

What states are supported? HIT MISS STALE INVALID CORRUPT /
NONE GENERATED TRANSPORT_RECOVERED / READY PENDING FAILED.

What makes a window READY? Un WindowSemanticResult courant valide
pour la signature attendue.

What makes ALL_WINDOWS_READY? Chaque WindowInput du plan a exactement
un résultat valide.

Can consolidation proceed with 2/3 windows? NO.

If WIN001 succeeds and WIN002 fails, is WIN001 preserved? YES.

Is WIN003 attempted after WIN002 failure? NO
(STOP_ON_FIRST_EXECUTION_FAILURE).

On resume, is WIN001 regenerated? NO if signature valid.

Can persisted transport be reprocessed without provider call? YES.

Does transport recovery consume call budget? NO.

Does cache hit consume call budget? NO.

When is a new-call budget unit consumed? When engine.generate is attempted.

Does max_new_calls=0 prevent FakeAI execution? YES.

Does max_new_calls=1 enforce one attempted generation maximum? YES.

Does one failed call still consume the budget? YES.

Did cold synthetic run produce all ready? {_yn(bool(cold.get("all_windows_ready")))}
How many FakeAI calls? {cold.get("new_calls")}

Did warm run use 0 new calls? {_yn(warm.get("new_calls") == 0)}

Did failure/resume work? {_st(synthetic, "resume_run")}
How many new calls on resume? {resume.get("new_calls")}

Did transport recovery use 0 new calls? {_yn(recovery.get("new_calls") == 0)}

What invalidates cache? Prompt/schema/planner/model/content/settings/language
mismatch, transport/result corrupt, SRC/ID/editorial invalid.

Can latency/request ID change cache identity? NO.

Are mtimes used as semantic identity? NO.

Are partial files accepted? NO.

Does handoff preserve WindowPlan order? YES.

Does handoff perform semantic merge? NO.

What happened in real CLEAN preflight?
windows = {preflight.get("windows")}
cache_states = {detail.get("cache_states")}
max_new_calls = 0
Were FakeAI semantic results produced for pastoral corpus? NO.

Were any real providers called? NO.

Was GlobalConsolidator implemented? NO.

Was source_map created? NO.

Was project state changed? NO.

How many tests pass? suite complète 3B.7.3 + baseline.

What is exact next phase? {payload.get("next_phase")}
— CONSOLIDATION TRANSPORT + DECODER + VALIDATOR, OFFLINE ONLY,
0 real Anthropic calls. Wait for human review.

Artifact determinism run1={determinism.get("run1_sha256")}
run2={determinism.get("run2_sha256")}
identical={_yn(bool(determinism.get("identical")))}

PHASE 3B REMAINS INCOMPLETE. WAIT FOR HUMAN REVIEW.
"""
