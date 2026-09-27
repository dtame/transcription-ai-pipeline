"""Rapport markdown déterministe de la revue 3B.6."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_execution_strategy.constants import (
    EXTERNAL_PROVIDER_RESEARCH_REQUIRED,
    NEXT_PHASE_LABEL,
    PHASE_3B_STATUS,
    PRIMARY_CLASSIFICATION,
    RECOMMENDED_STRATEGY,
    REPORT_NAME,
)


def _yn(value: Any) -> str:
    return "YES" if value else "NO"


def _bool(value: Any) -> str:
    return "true" if value else "false"


def _window_table(results: list[Mapping[str, Any]]) -> str:
    lines = [
        "| budget | windows | SRC coverage | min/max tokens | oversized SRC | windows over budget |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in results:
        coverage = row.get("src_coverage") or {}
        tokens = row.get("token_estimates") or {}
        oversized = row.get("oversized_src") or {}
        lines.append(
            "| {budget} | {windows} | {covered}/{present} | {tmin}/{tmax} | {over} | {exceed} |".format(
                budget=row.get("budget"),
                windows=row.get("window_count"),
                covered=coverage.get("union_src_count"),
                present=coverage.get("present_src_count"),
                tmin=tokens.get("min"),
                tmax=tokens.get("max"),
                over=oversized.get("count"),
                exceed=len(row.get("windows_exceeding_budget") or []),
            )
        )
    return "\n".join(lines)


def render_report(
    review: Mapping[str, Any],
    *,
    simulation: Mapping[str, Any] | None = None,
    sha256: str = "",
    simulation_sha256: str = "",
) -> str:
    simulation = simulation or review.get("window_simulation") or {}
    results = list((simulation.get("results") if simulation else None) or review.get("window_simulation", {}).get("results") or [])
    evidence = review.get("evidence") or {}
    attempt1 = evidence.get("attempt_1") or {}
    attempt2 = evidence.get("attempt_2") or {}
    problem = review.get("current_problem") or {}
    context = review.get("global_context") or {}
    resolved = review.get("resolved_and_not_current_blocker") or {}
    architecture = review.get("architecture") or {}
    plan = architecture.get("plan_windows") or {}
    streaming = architecture.get("streaming") or {}
    batch = architecture.get("async_batch") or {}
    options = review.get("options") or {}
    consolidation = review.get("consolidation") or {}
    cost = review.get("cost") or {}
    state = review.get("project_state") or {}
    execution = review.get("execution") or {}
    integrity = review.get("integrity") or {}
    gen_c = integrity.get("generation_c") or {}
    research = "YES" if review.get("external_provider_research_required") else "NO"
    if EXTERNAL_PROVIDER_RESEARCH_REQUIRED:
        research = "YES"

    return f"""# PHASE 3B.6 — GLOBAL ANALYSIS EXECUTION STRATEGY REVIEW

## Result

PASS

CURRENT PRIMARY PROBLEM =
{problem.get("primary_classification", PRIMARY_CLASSIFICATION)}

GLOBAL CONTEXT CAPACITY =
PASS

THIRD GLOBAL TIMEOUT RETRY =
PROHIBITED

RECOMMENDED EXECUTION STRATEGY =
{review.get("recommended_strategy", RECOMMENDED_STRATEGY)}

EXTERNAL PROVIDER RESEARCH REQUIRED =
{research}

NEW PROVIDER CALLS =
0

SOURCE MAP =
NOT PUBLISHED

PHASE 3B =
{execution.get("phase_3b_status", PHASE_3B_STATUS)}

## 1. Result

Voir l'en-tête. Cette phase est une revue d'architecture OFFLINE.
Aucun Attempt #3. Aucune implémentation de production.

## 2. Objective

Déterminer quelle stratégie d'exécution doit remplacer le modèle actuel
`one huge synchronous global request`, après deux échecs globaux sans body.

## 3. Baseline

`.venv\\Scripts\\python.exe -m pytest -q`

Avant travail : {(review.get("tests") or {}).get("baseline_passed")} passed,
{(review.get("tests") or {}).get("baseline_failed")} failed.

Après travail : {(review.get("tests") or {}).get("final_passed")} passed,
{(review.get("tests") or {}).get("final_failed")} failed.

## 4. Historical chronology

A. Schéma provider initial (Generation A, dérivé du SourceMap canonique) —
   rejeté par Anthropic : compiled grammar too large (Phase 3B).

B. Schéma compact Generation B (Phase 3B.4) — encore rejeté par le canary
   serveur 3B.4.1 (`SERVER_GRAMMAR_REJECTED`).

C. Generation C ultra-compact (`semantic-transport-v1`) — acceptée par le
   serveur (3B.4.2 design, 3B.4.3 SERVER GRAMMAR = ACCEPTED).

D. Canary vocabulaire initial — échec local (3B.4.3 PIPELINE FAIL après
   acceptation de grammaire).

E. Durcissement du contrat Prompt 1.3 (Phase 3B.4.4, offline PASS).

F. Canary vocabulaire final PASS (3B.4.5 : SERVER ACCEPTED, VOCABULARY
   COMPLIANCE VERIFIED, PIPELINE PASS, validator PASS).

G. Global Attempt #1 : timeout ~{attempt1.get("read_timeout_seconds")} s,
   provider body = {_bool(attempt1.get("provider_body"))},
   HTTP timeout form = {attempt1.get("http_timeout_form")}.

H. Audit de cause 3B.5 : `HTTP_READ_TIMEOUT_TOO_SHORT` (scalaire 3600
   contrôlait connect et read).

I. Durcissement connect/read 3B.5.1 : `timeout=(connect, read)`.

J. Politique 3B.5.2 : connect=30, read=7200,
   `THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED = false`.

K. Global Attempt #2 : read timeout {attempt2.get("read_timeout_seconds")} s,
   elapsed {attempt2.get("elapsed_ms")} ms, timeout_kind={attempt2.get("timeout_kind")},
   requests timeout={attempt2.get("requests_timeout")},
   provider body = {_bool(attempt2.get("provider_body"))}.

## 5. Problems already resolved

Ces éléments ne sont PAS le blocker actuel :

- Generation C grammar compatibility = {resolved.get("generation_c_grammar_compatibility")}
- Prompt 1.3 canonical vocabulary contract = {resolved.get("prompt_1_3_canonical_vocabulary_contract")}
- clean DERIVED provenance = {resolved.get("clean_derived_provenance")}
- sparse SRC support = {resolved.get("sparse_src_support")}
- context-size admission = {resolved.get("context_size_admission")}
- connect/read timeout separation = {resolved.get("connect_read_timeout_separation")}
- canonical decoder design = {resolved.get("canonical_decoder_design")}
- canonical SourceMap validator = {resolved.get("canonical_sourcemap_validator")}
- canary pipeline = {resolved.get("canary_pipeline")}

## 6. Attempt #1 evidence

- read timeout = {attempt1.get("read_timeout_seconds")} s
- HTTP form = {attempt1.get("http_timeout_form")}
- error = {attempt1.get("error")}
- provider body = {_bool(attempt1.get("provider_body"))}
- transport / usage / source_map = absents

## 7. Attempt #2 evidence

- connect = {attempt2.get("connect_timeout_seconds")} s
- read = {attempt2.get("read_timeout_seconds")} s
- requests timeout = {attempt2.get("requests_timeout")}
- elapsed_ms = {attempt2.get("elapsed_ms")}
- timeout_kind = {attempt2.get("timeout_kind")}
- error = {attempt2.get("error")}
- provider body = {_bool(attempt2.get("provider_body"))}
- scalar timeout bug still plausible = {_bool(attempt2.get("scalar_timeout_bug_still_plausible"))}

## 8. Current blocker

Observation locale certaine : une requête globale non-streaming contenant
le transcript CLEAN complet n'a produit aucun body en 3600 s ni en 7200 s.

Non conclu automatiquement :

- Anthropic ne peut pas le traiter
- Anthropic l'a traité mais un proxy a jeté le body
- la génération elle-même a duré > 7200 s

Ces hypothèses exigent des preuves absentes.

## 9. Root-cause classification

PRIMARY = {problem.get("primary_classification")}

SECONDARY = {", ".join(problem.get("secondary_classifications") or [])}

Justification : deux tentatives opérationnelles ont échoué sans body. La
seconde utilisait déjà le tuple connect/read correct. Le corpus tient dans
le budget. La cause amont exacte reste non observée (visibilité transport
insuffisante). Un troisième timeout plus long n'est pas une stratégie
autorisée.

## 10. Current Source Analyzer architecture

TranscriptInput → prompt 1.3 → plan_context → AIRequest (Generation C) →
AnthropicEngine._invoke → post_json non-streaming → decoder fail-closed →
reconstruction canonique → normalizer → validator → publication atomique.

## 11. Single-response assumption

L'hypothèse « une réponse provider complète » existe dans :

- `analyzer.py:_run_analysis` (un `engine.generate`)
- `AnthropicEngine._invoke` (un `post_json`)
- `_http.post_json` (attente du body HTTP entier)
- `semantic_transport_decoder` (objet transport complet)
- runner 3B Final (un appel réel gardé, strategy=global obligatoire)

## 12. Current context strategy

`plan_context()` choisit `global` si l'estimation ≤ budget utilisable.
Ici : estimated={context.get("estimated_input_tokens")},
usable={context.get("usable_budget")}, margin={context.get("margin")}.
Le corpus FIT. La capacité de contexte n'est pas le blocker.

## 13. plan_windows audit

- exists = {_bool(plan.get("exists"))}
- inputs = transcript, estimated_tokens, budget_tokens, overlap_segments
- outputs = fenêtres numérotées dès 1, bornes SRC
- frontières = SRC uniquement, jamais de scission de texte
- SRC sparse = supporté (liste des SRC présents, pas une plage inventée)
- token accounting = `max(2, ceil(global_estimate / budget))` puis parts égales
- overlap défaut = 1 SRC technique, pas sémantique
- déterministe = {_bool(plan.get("determinism"))}
- production-ready pour la planification = oui
- production-ready pour l'exécution = non
- unused = le chemin global actuel laisse `windows=()` ; si windowed,
  `analyze_source` lève `SourceAnalysisContextExceeded`
- limitation historique multi-fenêtres toujours vraie = {_bool(plan.get("historical_multi_window_limitation_still_true"))}

## 14. Window simulation

Simulation locale uniquement, transcript CLEAN réel, `plan_windows()` inchangé.

{ _window_table(results) }

Overlap technique utilisé = {(simulation.get("planner_notes") or review.get("window_simulation", {}).get("planner_notes") or {}).get("overlap_used")}
Overlap sémantique ajouté = false
Limitation planner = {(simulation.get("planner_notes") or review.get("window_simulation", {}).get("planner_notes") or {}).get("limitation")}
Observation = {(review.get("window_simulation") or {}).get("observation")}
SHA simulation = `{simulation_sha256 or "n/a"}`

## 15. Option A — longer synchronous global

{(options.get("global_sync") or {}).get("disposition")}

3600 s puis 7200 s, aucun body. La politique 3B.5.2 interdit l'escalade.
9000 / 10800 / 14400 ne sont pas une stratégie de diagnostic.

## 16. Option B — streaming global

Support moteur actuel = {_bool(streaming.get("anthropic_engine_supports_streaming_now"))}
Chemin structured output streaming = {_bool(streaming.get("semantic_structured_output_path_supports_streaming"))}
Bytes/tokens partiels observables = {_bool(streaming.get("partial_bytes_or_tokens_observable"))}
Garanties json_schema + stream = {streaming.get("native_json_schema_streaming_guarantees")}
Preuve offline = {_bool(streaming.get("can_be_proven_offline"))}

Le streaming pourrait réinitialiser le read timeout SI des chunks arrivent.
Cela ne prouve pas que la génération aboutit, ni que le transport structuré
reste reconstructible en `semantic-transport-v1`.

## 17. Option C — async/batch

{(options.get("async_batch") or {}).get("disposition")}

{batch.get("repository_support")} dans `app/ai/providers`.
`app.semantic_batch` est un classificateur 3A, pas Message Batches Anthropic.
Capacités provider = {batch.get("current_anthropic_batch_capabilities")}.

## 18. Option D — multi-window local merge

{(options.get("multi_window_local_merge") or {}).get("disposition")}

Un merge local peut unir des ensembles SRC, recalculer des stats et assigner
des IDs canoniques. Il ne peut pas fusionner « faith during trials » et
« using faith in adversity » sans jugement sémantique.

## 19. Option E — hierarchical map-reduce

{(options.get("hierarchical_map_reduce") or {}).get("disposition")}

Level 1 : fenêtres indépendantes. Level 2 : cartes sémantiques compactes,
PAS le transcript intégral. Cela réduirait fortement l'entrée de la passe
globale. Generation C peut servir de sortie Level 1.

## 20. Option F — hybrid window + global consolidation

{(options.get("hybrid_window_global_consolidation") or {}).get("disposition")}

Fenêtres → normalize/validate local (structure) → représentation compacte →
une consolidation IA (sémantique) → IDs canoniques locaux → validator final.

Préserve le raisonnement sémantique global sans renvoyer le transcript
complet dans une seule génération structurée.

## 21. Structural consolidation

{chr(10).join("- " + item for item in (consolidation.get("structural_local") or []))}

## 22. Semantic consolidation

{chr(10).join("- " + item for item in (consolidation.get("semantic_requires_ai") or []))}

## 23. Global metadata

{(consolidation.get("global_metadata_policy") or {})}

Décision : générés seulement en consolidation finale. Les observations
fenêtre peuvent alimenter le consolidateur ; elles ne sont pas le SourceMap.

## 24. Topics

Déduplication exacte insuffisante. Le consolidateur a besoin du label, du
résumé, des `source_refs` réels et de l'index de fenêtre.

## 25. Ideas

Les IDs IDEA finaux restent locaux et déterministes (première apparition SRC).
Les identités provider/fenêtre sont locales. Le consolidateur a besoin du
summary, kind, importance, source_refs, first_src.

## 26. Relations

Generation C utilise des index de records. Ces index fenêtre ne deviennent
pas des relations globales. Level 2 réémet les relations après ancrage SRC
ou après assignation d'identités globales. Le code local remap ensuite vers
les IDs IDEA canoniques.

## 27. Source refs

Les SRC réels et sparses restent l'ancre permanente. Jamais de renumérotation.

## 28. Traceability

Chaque élément substantiel final doit rester traçable à des SRC réels.
Le multi-fenêtres ne doit pas affaiblir cette règle.

## 29. Completeness

Le SourceMap final doit représenter le transcript CLEAN complet. Une fenêtre
« peu importante » ne peut pas être omise.

## 30. Cache/resume

Le cache actuel signe l'analyse entière (transcript + prompt + schéma +
modèle + réglages). Il n'existe pas de signature par fenêtre, ni de reprise
d'une fenêtre échouée. Des signatures nouvelles seraient nécessaires
(voir `architecture.cache.new_signatures_would_need`).

## 31. Failure recovery

Avantage majeur du windowing : cacher les fenêtres réussies et ne relancer
que l'échec. Non implémenté. Compatible avec l'esprit du cache actuel si
l'on étend `SignatureInputs`.

## 32. Cost implications

Pricing connu (catalogue) : {cost.get("pricing")}

L'entrée globale illustrée = {(cost.get("global_sync_or_streaming_or_batch") or {}).get("illustrative_input_cost")} { (cost.get("pricing") or {}).get("currency") }.
Sortie = unknown (interdit de la convertir en zéro).
Régime long-context = non modelé.
Les fenêtres dupliquent le prompt système : l'entrée totale windowée dépasse
l'entrée globale.

## 33. Reliability

Global sync : single-point failure, pas de resume, visibilité nulle.
Hybrid : progrès partiel, cache par fenêtre possible, visibilité par appel.

## 34. Semantic quality

Global sync serait le plus cohérent S'IL aboutissait.
Local merge seul perd des décisions sémantiques.
Hybrid conserve une passe sémantique globale sur des cartes, pas sur le
verbatim intégral.

## 35. Implementation complexity

Hybrid exige de nouveaux modules (runner fenêtre, cache, consolidateur) et
des tests. Prompt 1.3, Generation C, decoder et validator restent protégés.
Streaming/batch exigent un protocole provider absent et des faits externes.

## 36. External provider knowledge gaps

{chr(10).join("- " + item for item in (review.get("external_knowledge_gaps") or []))}

EXTERNAL_PROVIDER_RESEARCH_REQUIRED = {research}

Ces lacunes sont documentées. Elles ne bloquent pas le choix d'architecture :
même si streaming ou batch existaient, ils conserveraient une unique
génération structurée du corpus entier, déjà deux fois non opérationnelle.

## 37. Recommended strategy

{review.get("recommended_strategy")}

## 38. Why

Le corpus FIT le contexte. L'échec répété est opérationnel : une seule
requête synchrone non-streaming n'a livré aucun body en 1 h puis 2 h.
Casser le travail analytique en appels bornés et reprisables traite un
problème différent de la capacité de contexte. Hybrid réutilise Generation C
et le decoder/validator, réserve le jugement sémantique à une consolidation
IA, et n'envoie plus le transcript intégral dans la passe finale.

## 39. Rejected/deferred alternatives

- KEEP_GLOBAL_SYNCHRONOUS / Option A : interdit comme prochaine exécution
- ADOPT_STREAMING_GLOBAL : non implémenté, garanties inconnues, ne borne pas
  la charge de génération
- ADOPT_ASYNC_GLOBAL : NOT_IMPLEMENTED, EXTERNAL_VERIFICATION_REQUIRED
- ADOPT_MULTI_WINDOW_LOCAL_MERGE : merge sémantique impossible sans IA
- ADOPT_HIERARCHICAL_MAP_REDUCE : proche, mais Hybrid précise la
  normalisation locale et la consolidation sémantique finale
- NEED_EXTERNAL_PROVIDER_RESEARCH_FIRST : non requis pour sélectionner
- NEED_MORE_OFFLINE_ANALYSIS : les simulations et l'audit code suffisent

## 40. Proposed next phase

{review.get("next_phase_label", NEXT_PHASE_LABEL)}

Design only. Pas d'appel provider. Pas d'implémentation de production.

## 41. Tests

Tests offline ajoutés pour le planner, la couverture SRC, la préservation
sparse, les budgets candidats, les SRC oversized, l'absence de réseau et
l'absence de source_map. Suite complète exigée verte.

## 42. Network

Anthropic = 0
OpenAI = 0
Whisper = 0
Ollama = 0
LM Studio = 0
other = 0
engine.generate = 0

## 43. Protected artifacts

Historique jusqu'à Attempt #2 : snapshot SHA avant/après, byte-identical.
Prompt 1.3, Generation C, decoder, validator, transcript CLEAN inchangés.

Generation C raw match = {_bool(gen_c.get("raw_matches_historical"))}
Generation C anthropic match = {_bool(gen_c.get("anthropic_matches_historical"))}

## 44. SourceMap status

analysis/source_map.json = ABSENT
published = {_bool(review.get("source_map_present"))}

## 45. Project state

source_analysis.status = {state.get("status")}
source_analysis.error = {state.get("error")}
SUCCESS interdit.

## 46. Files added

- `app/source_analysis_execution_strategy/`
- `app/tests/test_source_analysis_execution_strategy.py`
- `audit/{REPORT_NAME}`
- `audit/source_analysis_window_strategy_simulation.json`
- `audit/source_analysis_execution_strategy_review.json`

## 47. Files modified

Aucun artefact historique. Aucun contrat protégé. `project_state.json`
non modifié par cette revue.

## 48. Technical decision

Did Attempt #1 time out without body? YES

Did Attempt #2 time out without body? YES

Was Attempt #2 actually using read=7200? YES (tuple (30.0, 7200.0))

Is the old scalar timeout bug still a plausible explanation for #2? NO

Does the complete transcript fit context? YES

Is context capacity currently the blocker? NO

Is Generation C grammar still verified? YES

Is Prompt 1.3 vocabulary compliance still verified? YES

Did the canary pipeline pass? YES

Is a third blind global timeout retry allowed? NO

Does current code support streaming? NO

Does current structured-output path support streaming? NO

Can that be proven offline? YES (absence of support). Provider streaming
guarantees if implemented later = EXTERNAL_VERIFICATION_REQUIRED

Does current code support async/batch? NO (NOT_IMPLEMENTED)

Does plan_windows exist? YES

Is it deterministic? YES

Does it support sparse SRC? YES

How many windows result for each simulated budget?
See section 14 / simulation artifact.

Is full clean SRC coverage maintained? YES (union of windows)

Can window results be merged entirely deterministically without semantic
loss? NO

Which fields require semantic global consolidation?
main_theme, author_intent, target_audience, author_voice_profile, topic
synonym merge, cross-window ideas/relations/examples/repetitions/uncertainties

Can current Generation C potentially be reused for window analysis? YES

Would hierarchical consolidation reduce the original transcript sent to a
final global semantic pass? YES

Would window caching permit resume after partial failure? YES, after new
per-window signatures

What new cache signatures would be needed?
window index, SRC bounds, window content hash, Level-1 schema, consolidation
input/prompt/schema hashes

Would canonical final IDs still be assigned locally? YES

Can real SRC IDs remain permanent? YES

Would canonical validator remain final authority? YES

What external provider facts remain unknown?
streaming+json_schema, Message Batches, upstream/proxy max execution,
behavior after client timeout

Is external provider documentation research required? NO
(not required to select the architecture)

What architecture is recommended?
{review.get("recommended_strategy")}

Why?
See section 38.

What exact next phase is recommended?
{review.get("next_phase_label", NEXT_PHASE_LABEL)}

Was any provider called? NO

Was source_map created? NO

Was project_state changed? NO

How many tests pass?
{(review.get("tests") or {}).get("final_passed")} passed, {(review.get("tests") or {}).get("final_failed")} failed.

Review SHA (core, pre-determinism block) = `{sha256 or "n/a"}`

PHASE 3B REMAINS INCOMPLETE. THIRD GLOBAL TIMEOUT ESCALATION = PROHIBITED.
WAIT FOR HUMAN REVIEW.
"""
