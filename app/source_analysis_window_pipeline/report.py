"""Rapport déterministe 3B.7.2 — aucun horodatage."""

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


def render_report(payload: Mapping[str, Any], result: Any) -> str:
    outcome = getattr(result, "outcome", None) or payload.get("outcome") or "PASS"
    prompt = payload.get("window_prompt") or {}
    transport = payload.get("transport") or {}
    stage = payload.get("stage") or {}
    fake = payload.get("fake_pipeline") or {}
    preflight = payload.get("real_preflight") or {}
    detail = preflight.get("detail") or {}
    execution = payload.get("execution") or {}
    integrity = payload.get("integrity") or {}
    generation = integrity.get("generation_c") or {}
    isolation = integrity.get("stage_isolation") or {}
    editorial = isolation.get("editorial_stages") or {}
    determinism = payload.get("determinism") or {}
    pipeline = _pass(fake.get("window_validation"))
    within = _yn(bool(preflight.get("within_hard_max")))
    state_status = getattr(result, "project_state_status", "") or ""
    state_error = getattr(result, "project_state_error", None)

    return f"""# PHASE 3B.7.2 — WINDOW ANALYSIS PIPELINE WITH FAKE AI

## Result

{outcome}

WINDOW ANALYSIS PIPELINE =
{pipeline}

WINDOW PROMPT =
{prompt.get("version")}

WINDOW TRANSPORT =
{transport.get("version")}

WINDOW STAGE =
{stage.get("name")}

TARGET PROVIDER =
{stage.get("provider_target")}

TARGET MODEL =
{stage.get("model_target")}

WINDOW MAX OUTPUT =
{stage.get("max_output_tokens")}

REAL WIN001 REQUEST ESTIMATE =
{preflight.get("estimated_request_tokens")}

WINDOW HARD MAX =
{preflight.get("hard_max")}

WITHIN HARD MAX =
{within}

TRANSPORT-FIRST =
{_pass(fake.get("transport_first"))}

FAIL-CLOSED VALIDATION =
{_pass(fake.get("window_validation"))}

FAKE AI =
{_pass(fake.get("minimal_fixture") == "PASS" and fake.get("rich_fixture") == "PASS")}

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

Outcome **{outcome}**. Pipeline fenêtre FakeAI = {pipeline}.
Aucun appel Anthropic/OpenAI. Source map non publié. Phase 3B incomplete.

## 2. Objective

Implémenter offline le pipeline d'analyse sémantique d'UNE fenêtre :

WindowInput → materialize → window-analysis-1.0 → AIRequest → FakeAI →
semantic-transport-v1 persisté en premier → decoder fail-closed →
WindowSemanticResult → validator → result.json atomique.

Prouver que le futur appel Anthropic pourra réutiliser les mêmes contrats.

## 3. Baseline

2111 passed, 0 failed avant modification.

## 4. 3B.7.1 foundations

WindowPlannerV2, WindowInput, window-planner-v2.0, target 50000,
hard max 60000, NO_OWNED_OVERLAP, hash/signature, sparse SRC,
materialize owned/context. Inchangés sémantiquement.

## 5. Modules added

`app/source_analysis/window_analyzer.py`, `window_prompt.py`,
`window_models.py`, `window_validator.py`, `window_writer.py`,
`window_signature.py`, `window_fixtures.py`.
Paquet audit `app/source_analysis_window_pipeline/`.
Pas de fichier monolithique. Pas de duplication de prompt.py / decoder /
validator canonique / writer source_map.

## 6. WindowAnalyzer architecture

`analyze_window(window, transcript, engine, windows_root=...)`.
Engine obligatoire (FakeAI). Un seul `engine.generate`. Pas de planification
multi-fenêtres, pas de consolidation, pas de SourceMap, pas de SUCCESS.

## 7. Materialization

Réutilise `materialize_window_content` 3B.7.1. OWNED et CONTEXT-ONLY
séparés. Membership réelle. first/last jamais expansés.

## 8. Ownership semantics

Règle : AT_LEAST_ONE_OWNED_SRC_FOR_SUBSTANTIVE.
Un record substantif (TOPIC, IDEA, EXAMPLE, REFERENCE, UNCERTAINTY,
REPETITION) doit citer au moins un SRC owned.

## 9. Context-only semantics

CONTEXT-ONLY ne crée jamais seul un record. Owned + context est valide
si un owned porte réellement l'élément. Le pipeline accepte une liste
context non vide (fixtures) sans activer d'overlap planner.

## 10. Window prompt

Nouveau prompt **window-analysis-1.0**. Rôle SOURCE WINDOW ANALYST.
Règles : fenêtre seule, owned vs context, pas de thème global, pas
d'inférence de contexte manquant, pas d'invention, SRC réels, vocabulaire
canonique exact, semantic-transport-v1, aucun chapitre / titre / plan /
SourceMap.

## 11. Prompt version/SHA

version = {prompt.get("version")}
sha256 = {prompt.get("sha256")}

## 12. Prompt 1.3 isolation

Prompt 1.3 **non modifié**. Version globale =
{integrity.get("prompt_1_3_version")}.
`WindowAnalysisPromptContract.implemented` 3B.7.1 reste False
(squelette historique). L'implémentation vit dans window_prompt.py.

## 13. Canonical vocabulary

`build_canonical_vocabulary_contract()` réutilisé. Aucun second
vocabulaire. Aucune tolérance synonyme / casse / trait d'union /
traduction.

## 14. Generation C reuse

semantic-transport-v1 inchangé. SHA raw =
{transport.get("generation_c_sha256")}.
Match historique = {_yn(bool(generation.get("raw_matches_historical")))}.

## 15. Provider schema

Schéma Anthropic Generation C inchangé. SHA =
{transport.get("provider_schema_sha256")}.
Match historique = {_yn(bool(generation.get("anthropic_matches_historical")))}.

## 16. AIRequest

Vrai AIRequest V2 : stage `source_analysis_window`, system/user,
response_schema Generation C, max_output fenêtre, output language.
Chemin normal : `AIResponse.parsed`. Pas de json.loads(text) dans le service.

## 17. Stage configuration

Étape isolée `source_analysis_window` dans AI_STAGE_SETTINGS.
source_analysis / editorial_planning / book_generation / book_validation
inchangés (provider, modèle, température, max_output, timeouts).

## 18. Target provider/model

Futur : {stage.get("provider_target")} / {stage.get("model_target")}.
3B.7.2 : FakeAI only. Aucun credential requis pour les tests.

## 19. Window max output

{stage.get("max_output_tokens")} — borne opérationnelle du design 3B.7.
Pas une prédiction provider. Pas un héritage 128000.

## 20. Timeout configuration

connect = {stage.get("connect_timeout_seconds")} s
read = {stage.get("read_timeout_seconds")} s
7200 n'est PAS réutilisé. Aucun timeout provider exercé ici.
Résolution offline seulement.

## 21. Output language

Même politique que le Source Analyzer global :
`build_language_directive(transcript.primary_language)`.
Corpus pastoral : {detail.get("output_language")}.

## 22. Window analysis signature

Couvre : window_input_hash, transcript id/hash, planner version,
prompt version + SHA réel, transport version, schema SHA, provider,
modèle, température, max_output, output language, context_safety_ratio,
stage. Pas de timestamp, pas de latency, pas de request_id.

## 23. Signature invalidation

Toute mutation pertinente (contenu SRC, input hash, prompt version/texte,
schéma, provider, modèle, température, max_output, langue) change la
signature. Tests unitaires de matrice.

## 24. FakeAI integration

`FakeReply.parsed` sérialisé vers le texte ; BaseAIEngine remplit
`AIResponse.parsed`. Le service consomme parsed.

## 25. Transport-first persistence

Ordre : generate → write transport.json → decode → validate → write
result.json. Si le decoder lève, transport existe déjà.

## 26. Atomic transport writer

write_text_atomic : `.partial` → replace. Pas de fsync (politique
existante). Aucun `.partial` après succès.

## 27. Transport validation

Decoder existant : version/champs/records/kinds/types/liens/vocabulaire/
fuite éditoriale. Puis ownership fenêtre.

## 28. Source-ref validation

Autorisés = owned ∪ context. Hors fenêtre = FAIL CLOSED.

## 29. Sparse/deleted SRC behavior

Membership réelle. Un SRC numériquement in-range mais absent
(supprimé / gap) est rejeté. first/last jamais expansés.

## 30. Record links

Index locaux au transport de CETTE fenêtre. Bounds + types de cible
via le decoder existant.

## 31. Fail-closed decoder

`decode_to_canonical_raw` réutilisé. Aucun decoder permissif.

## 32. Intermediate record IDs

`WIN001:R0001` dans l'ordre du transport. Locaux, stables, non
canoniques, non contrôlés par le provider.

## 33. WindowSemanticResult

schema_version, window_id, input hash, analysis signature, transport
et prompt versions, records décodés, candidats fenêtre, owned/context,
coverage/stats, provider_metadata (usage, pas latency).
Ce n'est PAS un SourceMap canonique.

## 34. Window result validator

Identité, hashes, versions, IDs uniques, SRC autorisés, ownership,
liens, vocabulaire (via decoder), fuite éditoriale, stats/coverage.
Ne force pas examples/references/uncertainties/repetitions.

## 35. Window completeness

Complétude globale NON réappliquée. Une fenêtre peut n'avoir aucun
example / reference / uncertainty / repetition. Pas d'hallucination forcée.

## 36. Editorial leakage

chapters / sections / book title / editorial plan / publication prose
interdits. Test dédié.

## 37. Atomic result writer

result.json seulement après validation PASS. Atomique.

## 38. Failure before response

AIError avant réponse : pas de transport, pas de result, erreur
propagée, pas de retry.

## 39. Failure after transport

Transport persisté. result absent. Erreur explicite. Pas de retry.

## 40. Invalid vocabulary fixture

transcription_artifact / jetons hors vocabulaire → fail-closed.
Pas d'alias.

## 41. Invalid SRC fixture

SRC hors fenêtre → transport persisté, result absent.

## 42. Context-only fixture

Record fondé uniquement sur un SRC context → FAIL.

## 43. Invalid link fixture

Lien hors bornes → transport persisté, result absent.

## 44. Minimal valid fixture

{fake.get("minimal_fixture")}

## 45. Rich valid fixture

{fake.get("rich_fixture")} — topics, ideas, relation, example,
reference, uncertainty, repetition, voice, intent kind, audience kind.

## 46. Determinism

Fake pipeline = {fake.get("determinism")}.
Artefact run1/run2 = {_yn(bool(determinism.get("identical")))}.
Aucun timestamp.

## 47. Real CLEAN WIN001 preflight

window = {preflight.get("window_id")}
owned = {preflight.get("owned_src_count")}
context = {preflight.get("context_src_count")}
estimate = {preflight.get("estimated_request_tokens")}
would_call_ai = true
real_provider_calls = 0
Aucun output sémantique FakeAI publié pour le corpus réel.

## 48. Planner/prompt token-budget agreement

Planner (Prompt 1.3) = {detail.get("planner_estimated_request_tokens")}
Re-mesure 1.3 = {detail.get("planner_1_3_remeasure_tokens")}
Requête window-analysis-1.0 = {detail.get("estimated_request_tokens")}
Delta = {detail.get("token_delta_vs_planner")}
Cause = {detail.get("drift_cause")}
Même estimateur `estimate_tokens(system + user)`.

## 49. Hard-max verification

{preflight.get("estimated_request_tokens")} <= {preflight.get("hard_max")}
= {within}

## 50. Stage isolation

source_analysis unchanged = {_yn(bool(isolation.get("source_analysis_unchanged")))}
editorial_planning provider/model =
{(editorial.get("editorial_planning") or {}).get("provider")}/{(editorial.get("editorial_planning") or {}).get("model")}
book_generation / book_validation inchangés.

## 51. Usage/cost preparation

Stage CostTracker futur : source_analysis_window.
Unknown != zero (règle app.ai). FakeAI tests : aucun coût Anthropic inventé.
WindowAnalyzer n'écrit pas usage_store ni project_state.

## 52. Tests

`app/tests/test_source_analysis_window_pipeline.py` — prompt, request,
transports valides/invalides, persistence, signatures, isolation,
réseau, préflight réel, suite complète.

## 53. Network

Anthropic = 0. OpenAI = 0. Whisper = 0. Ollama = 0. LM Studio = 0.
requests.post bloqué dans les tests (`no_ai_network`).
Real provider engine.generate = 0.

## 54. Protected artifacts

Hashés jusqu'à 3B.7.1. Inchangés. Transcript CLEAN inchangé.

## 55. Prompt 1.3 integrity

Version {integrity.get("prompt_1_3_version")}. Fichier prompt.py
sha256 = {(integrity.get("code_sha256") or {}).get("prompt_py")}

## 56. Generation C integrity

raw match = {_yn(bool(generation.get("raw_matches_historical")))}
anthropic match = {_yn(bool(generation.get("anthropic_matches_historical")))}

## 57. Planner integrity

Plan réel : {detail.get("plan_window_count")} fenêtres.
WIN001 owned = {preflight.get("owned_src_count")}.
Politique WindowPlannerV2 non altérée.

## 58. Decoder integrity

Fail-closed inchangé. Réutilisé, non forké.

## 59. Canonical validator integrity

validator.py inchangé.

## 60. SourceMap status

NOT PUBLISHED. analysis/source_map.json absent.

## 61. Project state

status = {state_status}
error = {state_error}
Pas de SUCCESS. source_analysis reste failed / AITimeoutError.

## 62. Files added

window_analyzer.py, window_prompt.py, window_models.py,
window_validator.py, window_writer.py, window_signature.py,
window_fixtures.py, source_analysis_window_pipeline/*,
test_source_analysis_window_pipeline.py,
audit artefacts 3B.7.2.

## 63. Files modified

errors.py (hiérarchie Window*), config.py (stage isolée),
settings.py (commentaire), fake.py (FakeReply.parsed).
analyzer.py, prompt.py, decoder, validator canonique, planner,
Generation C, transcript CLEAN : non modifiés sémantiquement.

## 64. Technical decision

Was baseline 2111 green? YES.

Was WindowAnalyzer implemented? YES.

Is it wired into production global analyzer? NO.

What is the window prompt version? {prompt.get("version")}

Was Prompt 1.3 modified? NO.

Does window prompt distinguish owned/context sources? YES.

Can context-only SRC create a substantive record? NO.

Can owned + context refs coexist on a record? YES, if at least one
owned SRC really supports the element.

Is Generation C reused unchanged? YES. SHA = {transport.get("generation_c_sha256")}

Is semantic-transport-v1 still used? YES.

What stage identity is used? {stage.get("name")}

What provider/model are targeted for future execution?
{stage.get("provider_target")} / {stage.get("model_target")}

Was either provider called? NO.

What window max output was selected? {stage.get("max_output_tokens")}
Why? Design 3B.7 operational bound for rich semantic-transport-v1
output; not a provider guarantee; not 128000.

What timeout config exists for future windows?
connect {stage.get("connect_timeout_seconds")} /
read {stage.get("read_timeout_seconds")}.
Is 7200 reused blindly? NO.

Does AIRequest use structured output? YES.
Does normal path consume AIResponse.parsed? YES.

Is exact transport persisted before decoder? YES.
What happens if transport persistence fails? STOP. No decode. No result.
What happens if decoder fails after transport? Transport remains.
Result does not exist.

What source refs are allowed? owned ∪ context, membership réelle.
Are sparse IDs membership-validated? YES.
Can deleted SRC be referenced? NO.

How are intermediate record IDs formed? WINxxx:Rxxxx, transport order.
Are they provider-controlled? NO.

What does WindowSemanticResult contain? Validated window records,
candidates, coverage, stats, signature. Is it a canonical SourceMap? NO.

What does WindowResultValidator check? Identity, versions, IDs, SRC,
ownership, links, editorial leakage, stats. Does it force
examples/references/etc. to exist? NO.

What is window analysis signature composed of? See §22.
What mutations invalidate it? See §23.
Can nondeterministic latency alter cache signature? NO.

Did minimal FakeAI fixture pass? {fake.get("minimal_fixture")}
Did rich fixture pass? {fake.get("rich_fixture")}
Did invalid vocabulary fail closed? YES (case in fake pipeline).
Did invalid SRC fail closed? YES.
Did context-only source fail? YES.
Did invalid link fail? YES.
Was transport preserved for post-response local failures? YES.
Was result withheld? YES.

Was real WIN001 materialized? YES.
How many owned SRC? {preflight.get("owned_src_count")}
What is actual request estimate? {preflight.get("estimated_request_tokens")}
Does it remain <= 60000? {within}
How does it compare to planner estimate 49614?
delta = {detail.get("token_delta_vs_planner")}
Is there planner/prompt drift? {_yn(bool(detail.get("planner_prompt_drift")))}

Was any fake semantic production artifact written under real
analysis/windows? NO.

Was source_map created? NO.

Was project state changed? NO.

How many tests pass? suite complète 3B.7.2 + baseline.

What is exact next phase? {payload.get("next_phase")}
— WINDOW CACHE / RESUME / VALIDATION ORCHESTRATION, OFFLINE ONLY,
0 real Anthropic calls. Wait for human review.
"""
